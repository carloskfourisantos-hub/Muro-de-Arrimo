"""Importa a aba ``Entrada`` da planilha original e exporta os resultados em .xlsx."""
from __future__ import annotations

import io

import openpyxl
from openpyxl.styles import Alignment, Font, PatternFill

from core.campos import CAMPOS
from core.fases import Resultado
from core.models import Entrada
from core.planilha import nomes_planilha


def importar(arquivo) -> Entrada:
    """Lê as células nomeadas da aba Entrada de ``Verificacao_Muro_Arrimo_NBR11682.xlsx``."""
    wb = openpyxl.load_workbook(arquivo, data_only=True)
    if "Entrada" not in wb.sheetnames:
        raise ValueError("A planilha não tem a aba 'Entrada'.")
    valores = {}
    for nome, dn in wb.defined_names.items():
        ref = dn.value.replace("$", "").replace("'", "")
        if "!" not in ref:
            continue
        aba, cel = ref.split("!")
        if aba == "Entrada":
            valores[nome] = wb[aba][cel].value
    faltam = [c.nome for c in CAMPOS if c.nome not in valores]
    if len(faltam) > 60:
        raise ValueError("A planilha não tem as células nomeadas esperadas na aba 'Entrada'.")
    return Entrada.da_planilha(valores)


def _titulo(ws, linha: list[str]) -> None:
    ws.append(linha)
    for c in ws[ws.max_row]:
        c.font = Font(bold=True, color="FFFFFF")
        c.fill = PatternFill("solid", fgColor="2A78D6")
        c.alignment = Alignment(horizontal="center", wrap_text=True)


def exportar(res: Resultado, meta: dict | None = None) -> bytes:
    """Planilha de resultados (valores, sem fórmulas)."""
    e = res.entrada
    wb = openpyxl.Workbook()
    ws = wb.active
    ws.title = "Entrada"
    if meta:
        for k, v in meta.items():
            if v:
                ws.append([k, v])
        ws.append([])
    _titulo(ws, ["Seção", "Dado", "Valor", "Unidade", "Nome na planilha"])
    plan = e.para_planilha(so_app=True)
    for c in CAMPOS:
        ws.append([c.secao, c.rotulo, plan[c.nome], c.unidade, c.nome if c.celula else "(só no aplicativo)"])

    ws = wb.create_sheet("Resumo")
    _titulo(ws, ["Verificação", "Fase 1", "Fase 2", "Limite", "Unidade"])
    f1, f2 = res.fase1.verif, res.fase2.verif
    usa2 = res.tem_fase2
    nomes = nomes_planilha(res)

    def lin(rot, k, lim="", un="-"):
        ws.append([rot, nomes[k], nomes[k + "_2"] if usa2 else "—", lim, un])
    ws.append(["Momento estabilizante Mres", res.fase1.forcas.F_Mres, res.fase2.forcas.F_Mres if usa2 else "—", "",
               "kN·m/m"])
    ws.append(["Momento tombador Movr", res.fase1.forcas.F_Movr, res.fase2.forcas.F_Movr if usa2 else "—", "",
               "kN·m/m"])
    lin("FS ao tombamento", "R_FSt", e.FSt_min)
    ws.append(["Força normal N", res.fase1.forcas.F_N, res.fase2.forcas.F_N if usa2 else "—", "", "kN/m"])
    lin("Força horizontal atuante H_act", "R_Hact", un="kN/m")
    lin("Força resistente H_res", "R_Hres", un="kN/m")
    lin("FS ao deslizamento", "R_FSd", e.FSd_min)
    lin("Excentricidade e", "R_e", un="m")
    lin("e / B", "R_eB", e.eB_lim)
    lin("Base efetiva B'", "R_Bef", un="m")
    lin("Tensão máxima σmax", "sig_max", un="kPa")
    lin("Tensão mínima σmin", "sig_min", un="kPa")
    lin("Tensão de Meyerhof σef", "R_sef", un="kPa")
    lin("Capacidade de carga qult", "R_qult", un="kPa")
    lin("FS à capacidade de carga", "R_FScc", e.FScc_min)
    ws.append(["Avisos", nomes["avisos"], nomes["avisos_2"] if usa2 else "—"])
    ws.append(["Resultado da fase", nomes["resultado"], nomes["resultado_2"] if usa2 else "—"])
    ws.append(["RESULTADO GERAL — estabilidade", nomes["resultado_geral"]])
    ws.append(["RESULTADO — dimensionamento NBR 6118", "ATENDE" if res.dim.atende else "NÃO ATENDE"])
    _ = f1, f2

    for fase in (res.fase1, res.fase2) if usa2 else (res.fase1,):
        ws = wb.create_sheet(f"Forças F{fase.numero}")
        _titulo(ws, ["Força", "Fx (kN/m)", "Fz (kN/m)", "x (m)", "z (m)", "M estabilizante (kN·m/m)",
                     "M tombador (kN·m/m)", "Observação"])
        for f in fase.forcas.linhas:
            ws.append([f.nome, f.Fx, f.Fz, f.x, f.z, f.Mres, f.Movr, f.obs])
        F = fase.forcas
        ws.append(["TOTAIS", F.F_Hnet, F.F_N, "", "", F.F_Mres, F.F_Movr])
        ws = wb.create_sheet(f"Empuxo F{fase.numero}")
        t = fase.emp.fatias
        _titulo(ws, ["Fatia", "z (m)", "Trecho", "σz' (kPa)", "σa (kPa)", "incl. (rad)", "dPa,h (kN/m)",
                     "dPa,v (kN/m)"])
        for i in range(len(t["z"])):
            ws.append([i + 1, float(t["z"][i]), str(t["trecho"][i]), float(t["sz"][i]), float(t["sa"][i]),
                       float(t["incl"][i]), float(t["dPah"][i]), float(t["dPav"][i])])

    ws = wb.create_sheet("Dimensionamento")
    _titulo(ws, ["Grupo", "Verificação", "Solicitante", "Resistente / limite", "Unidade", "Situação", "Origem"])
    for c in res.dim.checks + res.dim.extras:
        ws.append([c.grupo, c.nome, c.solicitante, c.resistente, c.unidade, c.situacao,
                   "aplicativo (NBR 6118)" if c.extra else "planilha"])
    ws.append([])
    for n in res.dim.notas:
        ws.append(["Nota", n])

    ws = wb.create_sheet("Valores nomeados")
    _titulo(ws, ["Nome (como na planilha)", "Valor"])
    for k in sorted(nomes):
        v = nomes[k]
        ws.append([k, v if isinstance(v, (int, float, str)) else float(v)])

    for ws in wb.worksheets:
        for col in ws.columns:
            larg = max((len(str(c.value)) for c in col[:60] if c.value is not None), default=8)
            ws.column_dimensions[col[0].column_letter].width = min(70, max(10, larg + 2))
    buf = io.BytesIO()
    wb.save(buf)
    return buf.getvalue()
