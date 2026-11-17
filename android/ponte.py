"""Ponte entre o núcleo de cálculo (``core/``) e a interface do aplicativo Android.

A interface é uma página web (HTML + JavaScript) que roda este mesmo código Python dentro do
celular, com o Pyodide (Python em WebAssembly). A interface só desenha: quem define o formulário,
valida os dados e calcula é este módulo, com o núcleo usado pelo aplicativo de computador.

Tudo entra e sai como texto JSON. Roda igual no CPython (testes em ``tests/test_android.py``).
"""
from __future__ import annotations

import json
import math

from core import solos as _solos
from core.campos import CAMPO, CAMPOS, SECOES
from core.enums import CAMPOS_SIM_NAO, ENUM_DO_CAMPO, OPCOES_LEGADAS
from core.fases import calcular
from core.models import Entrada

VERSAO = 1
BITOLAS = [5.0, 6.3, 8.0, 10.0, 12.5, 16.0, 20.0, 25.0, 32.0]
TITULOS = {
    "1.": "1 · Geometria do muro", "2.": "2 · Contrafortes", "2b.": "2b · Ancoragem na base (estacas)",
    "2c.": "2c · Blocos de coroamento", "2d.": "2d · Travamento do muro", "3.": "3 · Terrapleno e sobrecarga",
    "4.": "4 · Solo arrimado (aterro)", "5.": "5 · Solo de fundação", "6.": "6 · Água", "7.": "7 · Material",
    "8.": "8 · Capacidade de carga da fundação", "9.": "9 · Fatores de segurança mínimos (NBR 11682)",
    "10.": "10 · Dimensionamento estrutural (NBR 6118)", "10b.": "10b · Contrafortes — lajes e viga (NBR 6118)",
}
CHAVE_DA_SECAO = {"2.": "cf_usar", "2b.": "anc_usar", "2c.": "bl_usar", "2d.": "trav_usar", "10b.": "cf_usar"}
PASSO = {"m": 0.05, "°": 1.0, "kPa": 1.0, "kN/m³": 0.5, "-": 0.05, "cm": 0.5, "mm": 1.0, "MPa": 5.0, "kN": 5.0,
         "kN/m": 5.0, "un": 1.0}


# ------------------------------------------------------------------ formatação pt-BR
def num(v, casas: int = 2, vazio: str = "—") -> str:
    if v is None or (isinstance(v, float) and (math.isnan(v) or math.isinf(v))):
        return vazio
    s = f"{v:,.{casas}f}"
    return s.replace(",", "§").replace(".", ",").replace("§", ".")


def fs(v) -> str:
    return "∞" if isinstance(v, float) and math.isinf(v) else num(v)


def _limpo(v):
    """Valor serializável: inf/nan viram None."""
    if isinstance(v, float) and (math.isnan(v) or math.isinf(v)):
        return None
    return v


# ------------------------------------------------------------------ formulário
def esquema() -> str:
    """Seções e campos do formulário, com rótulo, unidade, limites, opções, padrão e ajuda."""
    padrao = Entrada()
    secoes = []
    for sec in SECOES:
        pref = sec.split(" ")[0]
        campos = []
        for c in (x for x in CAMPOS if x.secao == sec):
            item = dict(nome=c.nome, rotulo=c.rotulo, unidade="" if c.unidade in ("-", "un") else c.unidade,
                        tipo=c.tipo, ajuda=c.ajuda or "", min=c.minimo, max=c.maximo,
                        passo=PASSO.get(c.unidade, 0.1), vinculo=c.vinculo,
                        vinculo_rotulo=CAMPO[c.vinculo].rotulo if c.vinculo else None)
            v = getattr(padrao, c.nome)
            item["padrao"] = v.value if hasattr(v, "value") else v
            if c.tipo == "enum":
                legadas = {m.value for m in OPCOES_LEGADAS.get(c.nome, ())}
                item["opcoes"] = [dict(valor=m.value, legada=m.value in legadas) for m in ENUM_DO_CAMPO[c.nome]]
            elif c.tipo == "bool":
                item["sim_nao"] = list(CAMPOS_SIM_NAO.get(c.nome, ("Sim", "Não")))
            elif c.nome.endswith("_phi") and c.unidade == "mm":
                item["tipo"] = "bitola"
                item["opcoes"] = BITOLAS
            campos.append(item)
        secoes.append(dict(prefixo=pref, titulo=TITULOS.get(pref, sec), chave=CHAVE_DA_SECAO.get(pref),
                           estrutural=pref in ("10.", "10b."), campos=campos))
    return json.dumps(dict(versao=VERSAO, secoes=secoes, tipos_de_solo=_solos.TIPOS), ensure_ascii=False)


def habilitado(nome: str, d: dict) -> bool:
    """Mesmas regras de ``ui/inputs.py``: campo só faz sentido com certas opções ligadas."""
    c = CAMPO[nome]
    chave = CHAVE_DA_SECAO.get(c.secao.split(" ")[0])
    if chave and nome != chave and not d.get(chave):
        return False
    regras = {
        "rk_conv": d.get("metodo_emp") == "Rankine", "delta_dv": d.get("metodo_emp") == "Coulomb",
        "qult_inf": d.get("cc_modo") == "Informada", "anc_x2": (d.get("anc_n2") or 0) > 0,
        "bl_x": d.get("bl_pos") == "Posição informada",
        "anc_x": not (d.get("bl_usar") and d.get("bl_pos") != "Centrado nas estacas (planilha)"
                      and (d.get("anc_n2") or 0) == 0),
    }
    return regras.get(nome, True)


def _mensagens(exc: Exception) -> list[str]:
    erros = getattr(exc, "errors", None)
    if not callable(erros):
        return [str(exc)]
    saida = []
    for er in erros():
        loc = er.get("loc") or ()
        nome = loc[0] if loc else ""
        rot = CAMPO[nome].rotulo if nome in CAMPO else ""
        msg = er.get("msg", "")
        ctx = er.get("ctx") or {}
        if "ge" in ctx:
            msg = f"deve ser maior ou igual a {num(float(ctx['ge']), 3)}"
        elif "le" in ctx:
            msg = f"deve ser menor ou igual a {num(float(ctx['le']), 3)}"
        elif "gt" in ctx:
            msg = f"deve ser maior que {num(float(ctx['gt']), 3)}"
        elif "lt" in ctx:
            msg = f"deve ser menor que {num(float(ctx['lt']), 3)}"
        saida.append(f"{rot}: {msg}" if rot else msg)
    return saida


# ------------------------------------------------------------------ cálculo
def _verificacoes(res) -> list[dict]:
    e = res.entrada
    fases = [res.fase1] + ([res.fase2] if res.tem_fase2 else [])
    V, F = [f.verif for f in fases], [f.forcas for f in fases]

    def lin(rot, vals, lim="", ok=None, un=""):
        return dict(rot=rot, vals=vals, lim=lim, ok=ok, un=un)
    faixa = any(v.exc_faixa for v in V)
    return [
        lin("Momento estabilizante Mres", [num(f.F_Mres) for f in F], un="kN·m/m"),
        lin("Momento tombador Movr", [num(f.F_Movr) for f in F], un="kN·m/m"),
        lin("FS ao tombamento", [fs(v.R_FSt) for v in V], f"≥ {num(e.FSt_min)}", all(v.ok_tomb for v in V)),
        lin("Força normal na base N", [num(f.F_N) for f in F], un="kN/m"),
        lin("Força horizontal atuante", [num(v.R_Hact) for v in V], un="kN/m"),
        lin("Resistência: atrito N·tan δb", [num(v.Hres_atrito) for v in V], un="kN/m"),
        lin("Resistência: adesão a·B'", [num(v.Hres_adesao) for v in V], un="kN/m"),
        lin("Resistência: solo da frente e outras", [num(v.Hres_externas + v.Hres_estacas) for v in V], un="kN/m"),
        lin("Força resistente total", [num(v.R_Hres) for v in V], un="kN/m"),
        lin("FS ao deslizamento", [fs(v.R_FSd) for v in V], f"≥ {num(e.FSd_min)}", all(v.ok_desl for v in V)),
        lin("Excentricidade e", [num(v.R_e, 3) for v in V], un="m"),
        lin("e / B", [num(v.R_eB, 3) for v in V],
            f"≤ {num(e.eB_lim, 3)}" + (" (até 0,250 com base verificada)" if faixa else ""),
            all(v.exc_aceita for v in V)),
        lin("Fração comprimida da base", [num(100 * v.frac_comp, 0) + " %" for v in V]),
        lin("Base efetiva B'", [num(v.R_Bef, 3) for v in V], un="m"),
        lin("Tensão máxima (linear)", [num(v.sig_max, 1, "fora da base") + f" ({v.sig_max_em})" for v in V], un="kPa"),
        lin("Tensão mínima (linear)", [num(v.sig_min, 1) for v in V], un="kPa"),
        lin("Tensão de Meyerhof N / B'", [num(v.R_sef, 1, "fora da base") for v in V], un="kPa"),
        lin("Capacidade de carga qult", [num(v.R_qult, 1) for v in V], un="kPa"),
        lin("FS à capacidade de carga", [fs(v.R_FScc) for v in V], f"≥ {num(e.FScc_min)}", all(v.ok_cap for v in V)),
        lin("Resultado da fase", ["ATENDE" if f.atende else "NÃO ATENDE" for f in fases], "",
            all(f.atende for f in fases)),
    ]


def _croqui(res) -> dict:
    e, g, f = res.entrada, res.geo, res.fase1
    v, emp = f.verif, f.emp
    c = dict(B=g.B_base, H=e.H_muro, hs=e.h_sap, D=e.D_frente, q=e.q_sc,
             **{k: [list(p) for p in pts] for k, pts in g.croqui.items()},
             Pah=emp.p_Pah, zPa=emp.p_zPa, Pav=emp.p_Pav, xPav=emp.p_xPav, N=f.forcas.F_N, xR=v.R_xR,
             sig_max=_limpo(v.sig_max), sig_min=v.sig_min, sig_em=v.sig_max_em, Bef=v.R_Bef,
             x_bt=g.x_bt, z_ter=g.z_ter, beta=e.beta_t,
             faixa=[e.sc_fx_q, e.sc_fx_a, e.sc_fx_b], linha=[e.sc_ln_Q, e.sc_ln_x], ponto=[e.sc_pt_P, e.sc_pt_x],
             estacas=[e.anc_x if e.anc_usar else None, e.anc_x2 if (e.anc_usar and e.anc_n2 > 0) else None,
                      e.anc_L, e.anc_d])
    return c


def calcular_json(texto: str) -> str:
    """Recebe os dados do formulário (JSON) e devolve os resultados prontos para exibir (JSON)."""
    try:
        dados = json.loads(texto)
        dados = {k: v for k, v in dados.items() if k in CAMPO}
        entrada = Entrada(**dados)
    except Exception as exc:                       # dados inválidos: mensagens para o formulário
        return json.dumps(dict(ok=False, erros=_mensagens(exc)), ensure_ascii=False)
    try:
        res = calcular(entrada)
    except Exception as exc:                       # falha de cálculo: mostra em vez de travar a tela
        return json.dumps(dict(ok=False, erros=[f"Falha no cálculo: {type(exc).__name__}: {exc}"]),
                          ensure_ascii=False)
    e = res.entrada
    fases = [res.fase1] + ([res.fase2] if res.tem_fase2 else [])
    pior = lambda attr, fn=min: fn(getattr(f.verif, attr) for f in fases)   # noqa: E731
    na_faixa = any(f.verif.exc_faixa for f in fases)
    cartoes = [
        dict(t="FS tombamento", v=fs(pior("R_FSt")), lim=f"mín. {num(e.FSt_min)}",
             ok=all(f.verif.ok_tomb for f in fases)),
        dict(t="FS deslizamento", v=fs(pior("R_FSd")), lim=f"mín. {num(e.FSd_min)}",
             ok=all(f.verif.ok_desl for f in fases)),
        dict(t="Excentricidade e/B", v=num(pior("R_eB", max), 3),
             lim=f"máx. {num(e.eB_lim, 3)}" + (" · até 0,250 c/ base verificada" if na_faixa else ""),
             ok=all(f.verif.exc_aceita for f in fases)),
        dict(t="FS capacidade de carga", v=fs(pior("R_FScc")), lim=f"mín. {num(e.FScc_min)}",
             ok=all(f.verif.ok_cap for f in fases)),
    ]
    forcas = []
    for f in fases:
        F = f.forcas
        forcas.append(dict(
            fase=f.numero,
            linhas=[dict(nome=ln.nome, Fx=num(ln.Fx), Fz=num(ln.Fz), x=num(ln.x, 3), z=num(ln.z, 3),
                         Mres=num(ln.Mres), Movr=num(ln.Movr))
                    for ln in F.linhas if (ln.Fx or ln.Fz)],
            total=dict(Fx=num(F.F_Hnet), Fz=num(F.F_N), Mres=num(F.F_Mres), Movr=num(F.F_Movr))))
    d = res.dim
    checks = [dict(grupo=c.grupo, nome=c.nome, sol=num(c.solicitante), res=num(c.resistente), un=c.unidade,
                   sit=c.situacao) for c in d.checks + d.extras if c.situacao != "—"]
    saida = dict(
        ok=True, estab=res.atende_estabilidade, dim=d.atende, geral=res.atende, cartoes=cartoes,
        fases=[f.numero for f in fases], verif=_verificacoes(res), forcas=forcas, checks=checks,
        notas=list(d.notas),
        avisos=[dict(fase=f.numero, texto=a.texto, nivel=a.nivel) for f in fases for a in f.avisos],
        legadas=e.opcoes_legadas_ativas(), croqui=_croqui(res),
        entrada=json.loads(entrada.model_dump_json()))
    return json.dumps(saida, ensure_ascii=False)


# ------------------------------------------------------------------ parâmetros do solo por NSPT
def solo_json(texto: str) -> str:
    p = json.loads(texto)
    s = _solos.sugerir(p["tipo"], float(p["nspt"]), float(p.get("postura", 0.0)), bool(p.get("nao_drenado")))
    cl = s.classe
    faixa = lambda f, casas=0: f"{num(f[0], casas)} a {num(f[1], casas)}"   # noqa: E731
    return json.dumps(dict(
        classe=cl.nome, gama=round(s.gama, 1), phi=round(s.phi, 1), c=round(s.c, 1), delta=round(s.delta, 1),
        alfa=round(s.alfa, 2), qult=round(s.qult),
        faixas=[["Peso específico γ", faixa(cl.gama), "kN/m³"], ["Ângulo de atrito φ", faixa(cl.phi), "°"],
                ["Coesão c", faixa(cl.c), "kPa"], ["δ / φ", faixa(cl.delta_phi, 2), "-"],
                ["Capacidade de carga última indicativa", faixa(cl.qult), "kPa"]],
        obs=list(s.obs)), ensure_ascii=False)


def desabilitados_json(texto: str) -> str:
    """Campos que não se aplicam com as opções atuais (a interface os desativa)."""
    d = json.loads(texto)
    base = json.loads(Entrada().model_dump_json())
    base.update({k: v for k, v in d.items() if k in CAMPO})
    return json.dumps([c.nome for c in CAMPOS if not habilitado(c.nome, base)])
