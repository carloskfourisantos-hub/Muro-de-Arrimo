"""Gera ``core/campos.py`` a partir da aba ``Entrada`` da planilha.

Uso (uma vez, ou quando a planilha ganhar entradas novas):
    .venv\\Scripts\\python tools\\gerar_campos.py

Lê rótulo (col. B), valor padrão (C), unidade (D) e ajuda (E) de cada célula
nomeada da aba Entrada. Limites de validação e vínculos ficam na tabela abaixo.
"""
from __future__ import annotations

import io
import sys
from pathlib import Path

import openpyxl

RAIZ = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(RAIZ))
from core.enums import CAMPOS_SIM_NAO, ENUM_DO_CAMPO  # noqa: E402

PLANILHA = RAIZ / "Verificacao_Muro_Arrimo_NBR11682.xlsx"

# (mínimo, máximo) inclusivos; None = sem limite
LIM = {
    "H_muro": (0.3, 30), "h_sap": (0.05, 5), "t_topo": (0.05, 3), "t_base": (0.05, 3),
    "b_ponta": (0, 20), "b_talao": (0, 20), "D_frente": (0, 30),
    "cf_esp": (0.3, 30), "cf_t": (0.05, 3), "cf_h": (0, 30), "cf_Lb": (0, 20), "cf_Lt": (0, 20),
    "anc_x": (0, 40), "anc_n1": (0, 20), "anc_x2": (0, 40), "anc_n2": (0, 20), "anc_L": (0, 60),
    "anc_d": (0.05, 3), "anc_esp": (0.2, 30), "anc_a": (0, 2000), "anc_FS": (1, 10),
    "anc_ds": (5, 100), "anc_fy": (100, 2000), "anc_H": (0, 1e5),
    "bl_B": (0.1, 20), "bl_L": (0.1, 30), "bl_H": (0, 5),
    "trav_z": (0, 30), "trav_F": (0, 1e5),
    "h_reb": (0, 30), "beta_t": (0, 45), "q_sc": (0, 1000),
    "gam_at": (5, 30), "gsat_at": (5, 30), "phi_at": (5, 50), "c_at": (0, 500),
    "delta_dv": (0, 50), "delta_est": (0, 50),
    "gam_f": (5, 30), "gsat_f": (5, 30), "phi_f": (0, 50), "c_f": (0, 1000),
    "k_phi": (0, 1), "k_c": (0, 1),
    "hw_at": (0, 30), "hw_fr": (0, 30), "gam_w": (9, 11), "gam_c": (15, 30),
    "qult_inf": (1, 1e5), "FSt_min": (1, 10), "FSd_min": (1, 10), "FScc_min": (1, 10), "eB_lim": (0.01, 0.5),
    "fck_c": (15, 90), "fyk_s": (200, 700), "gc_c": (1, 2), "gs_s": (1, 2), "gf_f": (1, 2),
    "cob_ct": (1, 10), "cob_bs": (1, 10), "gw_f": (1, 2), "gf_sp": (0, 2), "gf_cs": (1, 2),
    "cf_n": (1, 40),
}
# Campos que só existem no aplicativo (sem célula na planilha). Chave = campo da planilha
# depois do qual entram; valor = lista de (nome, rótulo, unidade, tipo, padrão, mín, máx, ajuda).
SO_APP = {
    "q_estab": [
        ("sc_fx_q", "Carga em faixa paralela ao muro: intensidade", "kPa", "float", 0.0, 0.0, 5000.0,
         "0 = sem carga em faixa. Ex.: via, calçada carregada, sapata corrida de edificação vizinha. Somada à "
         "sobrecarga uniforme q. Pressão no muro pela teoria da elasticidade (Boussinesq)"),
        ("sc_fx_a", "Carga em faixa: distância do tardoz ao início da faixa", "m", "float", 1.0, 0.0, 100.0,
         "Medida na superfície do terreno, a partir do tardoz da cortina"),
        ("sc_fx_b", "Carga em faixa: largura da faixa", "m", "float", 1.0, 0.05, 100.0, ""),
        ("sc_ln_Q", "Carga em linha paralela ao muro", "kN/m", "float", 0.0, 0.0, 1e5,
         "0 = sem carga em linha. Ex.: muro de divisa, parede, trilho"),
        ("sc_ln_x", "Carga em linha: distância ao tardoz", "m", "float", 1.0, 0.0, 100.0, ""),
        ("sc_pt_P", "Carga concentrada (pontual)", "kN", "float", 0.0, 0.0, 1e6,
         "0 = sem carga concentrada. Ex.: pilar, roda, apoio de equipamento"),
        ("sc_pt_x", "Carga concentrada: distância ao tardoz", "m", "float", 1.0, 0.0, 100.0, ""),
        ("sc_pt_L", "Carga concentrada: comprimento de muro que a resiste", "m", "float", 3.0, 0.5, 100.0,
         "A pressão da carga pontual varia ao longo do muro (cos² 1,1θ); o cálculo por metro usa a média nesse "
         "comprimento, centrado na carga. Use o trecho entre juntas ou o painel; quanto menor, mais conservador"),
        ("sc_bq", "Cargas concentradas e em faixa: rigidez do muro", "-", "enum",
         "Parede rígida (×2 — Terzaghi/NAVFAC)", None, None,
         "'Parede rígida': dobro da solução elástica (muro que não se desloca; equivale a ν = 0,5) — padrão e a "
         "favor da segurança | 'Parede que se desloca': solução elástica de Boussinesq sem dobrar"),
    ],
    "bl_H": [
        ("bl_pos", "Posição do bloco na seção", "-", "enum", "Alinhado ao tardoz", None, None,
         "'Alinhado ao tardoz' (padrão): a face do bloco coincide com o tardoz da cortina na base (lado da "
         "terra) e o bloco avança para a ponta; com uma só linha de estacas, a estaca fica no eixo do bloco | "
         "'Centrado nas estacas (planilha)': o bloco acompanha as estacas | 'Posição informada': você define "
         "onde o bloco começa"),
        ("bl_x", "Início do bloco (x a partir da ponta)", "m", "float", 0.35, -5.0, 40.0,
         "Só usado com 'Posição informada': x da face do bloco voltada para a ponta"),
    ],
    "xd_lim": [
        ("comb_base", "Combinações de ações na base (ponta e talão)", "-", "enum", "Equilíbrio + local do GEO5",
         None, None,
         "'Equilíbrio + local do GEO5' (padrão): pior caso entre as combinações em equilíbrio (cada grupo de ações "
         "em 1,0 ou γf, com a reação do solo de cada uma) e a combinação local do GEO5 (empuxo vertical × γf, "
         "pesos e reação do solo de serviço × 1,0) | 'Equilíbrio + todas as locais': acrescenta as 8 combinações "
         "locais com reação, pesos e empuxo vertical em 1,0 ou γf — não equilibradas e bem mais severas no talão"),
    ],
    "cf_phi": [
        ("laje_cf", "Modelo da cortina e da base entre contrafortes", "-", "enum", "Laje com borda livre (placa)",
         None, None,
         "'Laje com borda livre (placa)' (padrão): painel engastado na sapata e contínuo nos contrafortes, com "
         "a borda superior livre, resolvido como placa — momentos nas duas direções | 'Coeficientes do GEO5 "
         "(planilha)': 0,03·σH·H1·l, σp·l²/12 e σp·l²/20"),
    ],
}

# Padrões do aplicativo diferentes dos da planilha (decisão do projetista em 16/11/2026).
# Chave = campo; valor = (padrão do aplicativo, texto de ajuda).
PADRAO_APP = {
    "k_phi": (0.75, "Padrão 3/4 (concreto moldado contra o solo). A planilha usa 2/3; a literatura indica de 1/2 a "
                    "2/3 (Das) até 1,0 (GEO5)"),
    "k_c": (0.5, "α da adesão a = α·c. Padrão 0,5 (solo coesivo sem tipo definido). Por tipo de solo: areias e "
                 "siltes sem argila 0; solos argilosos 0,5; argila mole a média 2/3; não drenado, α pela "
                 "resistência Su (NAVFAC DM-7.2). As páginas de solo preenchem este valor. A planilha usa 0"),
    "ff_tipo": ("Em repouso", "Padrão: 'Em repouso' = K0·σ' com K0 = 1 − sen φf, na altura D. Só conte com esse "
                              "solo se ele não puder ser escavado ou erodido; senão use 'Nenhuma' (planilha)"),
    "eB_lim": (None, "Padrão B/6 (resultante no terço médio, base 100% comprimida). Entre esse limite e B/4 o "
                     "aplicativo aceita o muro se a base resistir à distribuição triangular de tensões "
                     "(descolamento parcial); acima de B/4 reprova. GEO5 usa 0,333 por padrão"),
}

# campos cujo padrão é "igual a outro campo" (fórmula na planilha)
VINCULO = {"delta_dv": "phi_at", "gw_f": "gf_f", "gf_cs": "gf_f"}
INTEIROS = {"anc_n1", "anc_n2", "cf_n"}
BITOLAS = {"ar_tz_phi", "ar_fr_phi", "ar_bi_phi", "ar_bs_phi", "ar_hz_tz_phi", "ar_hz_fr_phi",
           "ar_bl_i_phi", "ar_bl_s_phi", "cf_phi", "anc_ds"}
ESPACAMENTOS = {"ar_tz_s", "ar_fr_s", "ar_bi_s", "ar_bs_s", "ar_hz_tz_s", "ar_hz_fr_s",
                "ar_bl_i_s", "ar_bl_s_s"}


def main() -> None:
    wbf = openpyxl.load_workbook(PLANILHA, data_only=False)
    wbv = openpyxl.load_workbook(PLANILHA, data_only=True)
    ws, wv = wbf["Entrada"], wbv["Entrada"]
    nome_da_celula = {}
    for nome, dn in wbf.defined_names.items():
        ref = dn.value.replace("$", "").replace("'", "")
        if ref.startswith("Entrada!"):
            nome_da_celula[ref.split("!")[1]] = nome

    linhas = []
    secao = ""
    for r in range(5, ws.max_row + 1):
        rot = ws[f"B{r}"].value
        cel = f"C{r}"
        if cel not in nome_da_celula:
            if rot:
                secao = str(rot)
            continue
        nome = nome_da_celula[cel]
        bruto = ws[cel].value
        valor = wv[cel].value
        unidade = ws[f"D{r}"].value or "-"
        ajuda = ws[f"E{r}"].value or ""
        if nome in CAMPOS_SIM_NAO:
            tipo, padrao = "bool", (valor == CAMPOS_SIM_NAO[nome][0])
        elif nome in ENUM_DO_CAMPO:
            tipo, padrao = "enum", str(valor)
            ENUM_DO_CAMPO[nome](padrao)  # valida
        elif nome in INTEIROS:
            tipo, padrao = "int", int(valor)
        else:
            tipo, padrao = "float", float(valor)
        if nome in PADRAO_APP:
            pad_app, ajuda = PADRAO_APP[nome]
            if pad_app is not None:
                padrao = pad_app
        vinculo = VINCULO.get(nome)
        if isinstance(bruto, str) and bruto.startswith("=") and vinculo:
            padrao = None  # None = segue o campo vinculado
        if nome in ESPACAMENTOS:
            lim = (5.0, 40.0)
        elif nome in BITOLAS and nome != "anc_ds":
            lim = (5.0, 40.0)
        else:
            lim = LIM.get(nome, (None, None))
        if tipo in ("float", "int") and lim == (None, None):
            raise SystemExit(f"sem limites para {nome}")
        linhas.append(
            f"    Campo({nome!r}, {secao!r}, {str(rot)!r}, {unidade!r}, {tipo!r}, {padrao!r}, "
            f"{lim[0]!r}, {lim[1]!r}, {vinculo!r}, {'Entrada!' + cel!r},\n          {ajuda!r}),"
        )
        for n2, rot2, un2, tipo2, pad2, mn2, mx2, aj2 in SO_APP.get(nome, ()):
            if tipo2 == "enum":
                ENUM_DO_CAMPO[n2](pad2)
            linhas.append(f"    Campo({n2!r}, {secao!r}, {rot2!r}, {un2!r}, {tipo2!r}, {pad2!r}, {mn2!r}, {mx2!r}, "
                          f"None, '',\n          {aj2!r}),")

    src = '''"""Tabela de campos da Entrada — GERADO por tools/gerar_campos.py a partir da
aba ``Entrada`` da planilha. Fonte única de: rótulo, unidade, padrão, limites e
texto de ajuda. O modelo pydantic (core/models.py) e os widgets (ui/inputs.py)
são construídos a partir desta tabela.
"""
from __future__ import annotations

from dataclasses import dataclass


@dataclass(frozen=True)
class Campo:
    nome: str          # nome definido na planilha
    secao: str         # título da seção da aba Entrada
    rotulo: str
    unidade: str
    tipo: str          # "float" | "int" | "bool" | "enum"
    padrao: object     # None = segue o campo ``vinculo``
    minimo: float | None
    maximo: float | None
    vinculo: str | None
    celula: str        # "" = campo só do aplicativo (não existe na planilha)
    ajuda: str


CAMPOS: tuple[Campo, ...] = (
''' + "\n".join(linhas) + '''
)

CAMPO: dict[str, Campo] = {c.nome: c for c in CAMPOS}
SECOES: tuple[str, ...] = tuple(dict.fromkeys(c.secao for c in CAMPOS))
'''
    destino = RAIZ / "core" / "campos.py"
    io.open(destino, "w", encoding="utf-8", newline="\n").write(src)
    print(f"{len(linhas)} campos -> {destino}")


if __name__ == "__main__":
    main()
