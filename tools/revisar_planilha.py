"""Gera a Revisão 01 da planilha a partir da original, com as alterações feitas no aplicativo.

    .venv/bin/python tools/revisar_planilha.py

Lê ``Verificacao_Muro_Arrimo_NBR11682.xlsx`` (que continua intacta: é a referência dos testes de
paridade) e grava ``Verificacao_Muro_Arrimo_NBR11682_Rev01.xlsx``. Cada alteração fica registrada
aqui e na aba Notas da revisão. A conferência contra o aplicativo é feita por
``tools/conferir_revisao.py`` (recalcula a revisão no LibreOffice e compara com o núcleo).

Fica de fora da planilha (só no aplicativo): laje com borda livre por elementos finitos (a revisão
mantém os coeficientes do GEO5), concreto acima de C40 (ηc e grupo II), força mínima de travamento
exata (iterativa), leitura de sondagem e as versões desktop/Android.
"""
from __future__ import annotations

import re
import sys
from copy import copy
from datetime import date
from pathlib import Path

import openpyxl
from openpyxl.styles import Alignment, Font, PatternFill
from openpyxl.utils import get_column_letter
from openpyxl.workbook.defined_name import DefinedName
from openpyxl.worksheet.datavalidation import DataValidation

RAIZ = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(RAIZ))
from core.campos import CAMPO  # noqa: E402
from core.enums import ENUM_DO_CAMPO  # noqa: E402

ORIGEM = RAIZ / "Verificacao_Muro_Arrimo_NBR11682.xlsx"
DESTINO = RAIZ / "Verificacao_Muro_Arrimo_NBR11682_Rev01.xlsx"
REVISAO = "Revisão 01"
DATA = "17/11/2026"
N_INT = 400          # fatias da integração de Boussinesq (igual a core/boussinesq.py)
N_PLANTA = 200       # pontos da média de cos²(1,1θ) da carga concentrada


def _nome(wb, nome: str, ref: str) -> None:
    if nome in wb.defined_names:
        del wb.defined_names[nome]
    wb.defined_names[nome] = DefinedName(nome, attr_text=ref)


def _estilo(dst, src) -> None:
    dst.font, dst.fill, dst.border = copy(src.font), copy(src.fill), copy(src.border)
    dst.alignment, dst.number_format, dst.protection = copy(src.alignment), src.number_format, copy(src.protection)


def _trocar(ws, cel: str, antigo: str, novo: str) -> None:
    v = ws[cel].value
    assert isinstance(v, str) and antigo in v, f"{ws.title}!{cel}: trecho não encontrado: {antigo[:60]}"
    ws[cel] = v.replace(antigo, novo)


# ============================================================================ 1. Entrada
def revisar_entrada(wb) -> dict:
    ws = wb["Entrada"]
    # padrões novos (decisão do projetista em 16/11/2026) e textos de ajuda do aplicativo
    for nome, valor in (("k_phi", 0.75), ("k_c", 0.5), ("ff_tipo", "Em repouso")):
        cel = wb.defined_names[nome].attr_text.split("!")[1].replace("$", "")
        ws[cel] = valor
        ws["E" + cel[1:]] = CAMPO[nome].ajuda
    ws["E90"] = CAMPO["eB_lim"].ajuda
    ws["B4"] = (f"{REVISAO} ({DATA}): padrões de deslizamento e de solo na frente alterados, novas cargas e "
                "opções nas seções 11 e 12 e dimensionamento revisado. Lista completa na aba Notas.")
    ws["B4"].font = Font(name="Arial", size=10, italic=True, color="FF1F4E78")

    # seções novas no fim da aba (inserir linhas no meio quebraria as referências)
    cab, rot, ent_num, ent_txt, un, aj = ws["B49"], ws["B50"], ws["C50"], ws["C71"], ws["D50"], ws["E50"]
    linha = 128
    celulas = {}

    def secao(titulo):
        nonlocal linha
        for col in "BCDE":
            _estilo(ws[f"{col}{linha}"], ws[f"{col}49"])
        ws[f"B{linha}"] = titulo
        linha += 1

    def campo(nome):
        nonlocal linha
        c = CAMPO[nome]
        _estilo(ws[f"B{linha}"], rot)
        _estilo(ws[f"C{linha}"], ent_txt if c.tipo == "enum" else ent_num)
        _estilo(ws[f"D{linha}"], un)
        _estilo(ws[f"E{linha}"], aj)
        ws[f"B{linha}"] = c.rotulo
        ws[f"C{linha}"] = c.padrao
        ws[f"D{linha}"] = c.unidade
        ws[f"E{linha}"] = c.ajuda or None
        if c.tipo != "enum":
            ws[f"C{linha}"].number_format = "0.00"
        _nome(wb, nome, f"Entrada!$C${linha}")
        celulas[nome] = f"C{linha}"
        linha += 1

    secao(f"11. CARGAS EM FAIXA, EM LINHA E CONCENTRADA NO TERRAPLENO (Boussinesq) — {REVISAO}")
    for n in ("sc_fx_q", "sc_fx_a", "sc_fx_b", "sc_ln_Q", "sc_ln_x", "sc_pt_P", "sc_pt_x", "sc_pt_L", "sc_bq"):
        campo(n)
    linha += 1
    secao(f"12. OPÇÕES INCLUÍDAS NA {REVISAO.upper()}")
    for n in ("comb_base", "bl_pos", "bl_x"):
        campo(n)

    # listas de opções numa aba oculta: as listas com vírgula dentro da opção ('0,45 (NBR 6118)')
    # ficavam quebradas na validação digitada
    li = wb.create_sheet("Listas")
    li.sheet_state = "hidden"
    li["A1"] = "Opções das listas de validação da aba Entrada (não editar)"
    alvo = {"v_mod": "C100", "xd_lim": "C113", **{n: celulas[n] for n in ("sc_bq", "comb_base", "bl_pos")}}
    novas = []
    for i, (nome, cel) in enumerate(alvo.items()):
        col = get_column_letter(i + 1)
        opcoes = [m.value for m in ENUM_DO_CAMPO[nome]]
        li[f"{col}2"] = nome
        for j, o in enumerate(opcoes):
            li[f"{col}{3 + j}"] = o
        novas.append((cel, f"=Listas!${col}$3:${col}${2 + len(opcoes)}"))
    manter = [dv for dv in ws.data_validations.dataValidation if str(dv.sqref) not in ("C100", "C113")]
    ws.data_validations.dataValidation = manter
    for cel, ref in novas:
        dv = DataValidation(type="list", formula1=ref, allow_blank=False)
        dv.add(cel)
        ws.add_data_validation(dv)
    return celulas


# ============================================================================ 2. Boussinesq
def _fator_planta(ws, col: str, x: str, L: str, titulo: str, linha0: int) -> str:
    """Média de cos²(min(1,1·atan(y/x); π/2)) em y ∈ (0; L/2), como core/boussinesq.fator_planta."""
    ws[f"{col}{linha0 - 1}"] = titulo
    for i in range(N_PLANTA):
        y = f"({i}+0.5)*({L})/2/{N_PLANTA}"
        ws[f"{col}{linha0 + i}"] = f"=COS(MIN(1.1*ATAN2(MAX({x},0.000001),{y}),PI()/2))^2"
    return f"AVERAGE({col}{linha0}:{col}{linha0 + N_PLANTA - 1})"


def _s_faixa(z, q, a, b, k):
    t1, t2 = f"ATAN2({z},{a})", f"ATAN2({z},({a})+({b}))"
    return f"{k}*(2*{q}/PI())*(({t2})-({t1})-SIN(({t2})-({t1}))*COS(({t1})+({t2})))"


def _s_linha(z, Q, x, H, k):
    m = f"MAX(({x})/({H}),0.4)"
    return f"{k}*4*{Q}/(PI()*({H}))*{m}^2*(({z})/({H}))/({m}^2+(({z})/({H}))^2)^2"


def _s_ponto(z, P, x, H, k, fp):
    m = f"MAX(({x})/({H}),0.4)"
    return f"{k}*1.77*{P}/({H})^2*{m}^2*(({z})/({H}))^2/({m}^2+(({z})/({H}))^2)^3*{fp}"


def criar_boussinesq(wb) -> None:
    ws = wb.create_sheet("Boussinesq", index=wb.sheetnames.index("Geometria"))
    negrito = Font(name="Arial", size=11, bold=True)
    normal = Font(name="Arial", size=10)
    ws["B1"] = f"CARGAS EM FAIXA, EM LINHA E CONCENTRADA NO TERRAPLENO — teoria da elasticidade ({REVISAO})"
    ws["B1"].font = Font(name="Arial", size=13, bold=True)
    ws["B2"] = ("Terzaghi (1954) / NAVFAC DM-7.2: faixa σh = k·(2q/π)(β − sen β·cos 2α); linha σh = k·(4Q/πH)·m²n/(m²+n²)²; "
                "ponto σh = k·1,77·(P/H²)·m²n²/(m²+n²)³·cos²(1,1θ), com m = máx(x/H; 0,4). k = 1 (parede rígida, dobro da "
                "solução elástica) ou 0,5. Pressões horizontais, sem atrito, somadas ao empuxo de terra.")
    ws["B2"].font = normal
    ws["B2"].alignment = Alignment(wrap_text=True, vertical="top")
    ws.row_dimensions[2].height = 45
    ws.column_dimensions["B"].width = 58
    for c in "CDEFGHI":
        ws.column_dimensions[c].width = 14
    itens = [
        ("bq_ativo", "Há carga em faixa, linha ou ponto? (1 = sim)", "=IF(OR(sc_fx_q>0,sc_ln_Q>0,sc_pt_P>0),1,0)", "-"),
        ("bq_k", "k (1 = parede rígida; 0,5 = parede que se desloca)", '=IF(sc_bq="Parede rígida (×2 — Terzaghi/NAVFAC)",1,0.5)', "-"),
        ("bq_H", "Altura do plano de cálculo da estabilidade (vertical pela extremidade do talão)", "=MAX(z_dv,0.000001)", "m"),
        ("bq_recuo", "Recuo do plano em relação ao tardoz (talão ao nível do terreno)", "=MAX(0,B_base-x_bt)", "m"),
        ("bq_ini", "Faixa: início em relação ao plano", "=MAX(sc_fx_a,bq_recuo)", "m"),
        ("bq_larg", "Faixa: largura além do plano", "=sc_fx_a+sc_fx_b-bq_ini", "m"),
        ("bq_xl", "Linha: distância ao plano", "=MAX(0,sc_ln_x-bq_recuo)", "m"),
        ("bq_xp", "Ponto: distância ao plano", "=MAX(0,sc_pt_x-bq_recuo)", "m"),
        ("bq_fp_est", "Ponto: média de cos²(1,1θ) no comprimento — plano da estabilidade", None, "-"),
        ("bq_fp_cort", "Ponto: média de cos²(1,1θ) no comprimento — tardoz (cortina)", None, "-"),
        ("bq_Fh_faixa", "Resultante horizontal — faixa", "=SUM(E42:E441)*bq_H/400", "kN/m"),
        ("bq_Fh_linha", "Resultante horizontal — linha", "=SUM(F42:F441)*bq_H/400", "kN/m"),
        ("bq_Fh_ponto", "Resultante horizontal — ponto (média no comprimento)", "=SUM(G42:G441)*bq_H/400", "kN/m"),
        ("bq_Fh", "Resultante horizontal total na estabilidade", "=IF(bq_ativo=1,SUM(H42:H441)*bq_H/400,0)", "kN/m"),
        ("bq_zF", "Cota da resultante acima do fundo da sapata", "=IF(bq_Fh>0,SUMPRODUCT(H42:H441,D42:D441)*bq_H/400/bq_Fh,0)", "m"),
        ("bq_W", "Peso das cargas que ficam sobre o talão", None, "kN/m"),
        ("bq_Mw", "Momento desse peso em torno da ponta", None, "kN·m/m"),
        ("bq_xW", "Posição desse peso (x a partir da ponta)", "=IF(bq_W>0,bq_Mw/bq_W,0)", "m"),
    ]
    ws["B4"], ws["C4"], ws["D4"] = "Grandeza", "Valor", "Unidade"
    for c in ("B4", "C4", "D4"):
        ws[c].font = negrito
    lin = {}
    for i, (nome, rot, f, u) in enumerate(itens):
        r = 5 + i
        ws[f"B{r}"], ws[f"D{r}"] = rot, u
        ws[f"B{r}"].font = ws[f"D{r}"].font = ws[f"C{r}"].font = normal
        if f:
            ws[f"C{r}"] = f
        ws[f"C{r}"].number_format = "0.000"
        _nome(wb, nome, f"Boussinesq!$C${r}")
        lin[nome] = r
    # médias de cos²(1,1θ) (colunas K e L) e peso sobre o talão
    fe = _fator_planta(ws, "K", "MAX(bq_xp,0.4*bq_H)", "sc_pt_L", "cos² estab.", 42)
    fc = _fator_planta(ws, "L", "MAX(sc_pt_x,0.4*z_ter)", "sc_pt_L", "cos² cortina", 42)
    ws[f"C{lin['bq_fp_est']}"] = "=" + fe
    ws[f"C{lin['bq_fp_cort']}"] = "=" + fc
    fim = "MIN(sc_fx_a+sc_fx_b,bq_recuo)"
    ws[f"C{lin['bq_W']}"] = ("=IF(AND(sc_fx_q>0,sc_fx_a<bq_recuo),sc_fx_q*(" + fim + "-sc_fx_a),0)"
                             "+IF(AND(sc_ln_Q>0,sc_ln_x<bq_recuo),sc_ln_Q,0)"
                             "+IF(AND(sc_pt_P>0,sc_pt_x<bq_recuo),sc_pt_P/sc_pt_L,0)")
    ws[f"C{lin['bq_Mw']}"] = ("=IF(AND(sc_fx_q>0,sc_fx_a<bq_recuo),sc_fx_q*(" + fim + "-sc_fx_a)*(x_bt+(sc_fx_a+" + fim + ")/2),0)"
                              "+IF(AND(sc_ln_Q>0,sc_ln_x<bq_recuo),sc_ln_Q*(x_bt+sc_ln_x),0)"
                              "+IF(AND(sc_pt_P>0,sc_pt_x<bq_recuo),sc_pt_P/sc_pt_L*(x_bt+sc_pt_x),0)")
    # integração na altura do plano (400 fatias)
    ws["B40"] = "Integração na altura do plano de cálculo da estabilidade (400 fatias)"
    ws["B40"].font = negrito
    for col, t in zip("BCDEFGH", ("Fatia", "z (prof., m)", "cota (m)", "σh faixa", "σh linha", "σh ponto", "σh total (kPa)")):
        ws[f"{col}41"] = t
        ws[f"{col}41"].font = negrito
    for i in range(N_INT):
        r = 42 + i
        z = f"C{r}"
        ws[f"B{r}"] = i + 1
        ws[f"C{r}"] = f"=({i}+0.5)*bq_H/{N_INT}"
        ws[f"D{r}"] = f"=bq_H-C{r}"
        ws[f"E{r}"] = (f"=IF(AND(sc_fx_q>0,bq_larg>0),"
                       f"{_s_faixa(z, 'sc_fx_q', 'bq_ini-bq_recuo', 'bq_larg', 'bq_k')},0)")
        ws[f"F{r}"] = f"=IF(sc_ln_Q>0,{_s_linha(z, 'sc_ln_Q', 'bq_xl', 'bq_H', 'bq_k')},0)"
        ws[f"G{r}"] = f"=IF(sc_pt_P>0,{_s_ponto(z, 'sc_pt_P', 'bq_xp', 'bq_H', 'bq_k', 'bq_fp_est')},0)"
        ws[f"H{r}"] = f"=E{r}+F{r}+G{r}"


def bq_na_cortina(D: str) -> str:
    """σh das cargas no tardoz real a uma profundidade D abaixo do terreno (core.boussinesq.na_cortina)."""
    return (f"IF(OR(bq_ativo=0,{D}<=0),0,"
            f"IF(sc_fx_q>0,{_s_faixa(D, 'sc_fx_q', 'sc_fx_a', 'sc_fx_b', 'bq_k')},0)"
            f"+IF(sc_ln_Q>0,{_s_linha(D, 'sc_ln_Q', 'sc_ln_x', 'z_ter', 'bq_k')},0)"
            f"+IF(sc_pt_P>0,{_s_ponto(D, 'sc_pt_P', 'sc_pt_x', 'z_ter', 'bq_k', 'bq_fp_cort')},0))")


# ============================================================================ 3. Forças
def revisar_forcas(wb) -> None:
    for aba in ("Forças", "Forças F2"):
        ws = wb[aba]
        for r in (38, 39):
            for col in "BCDEFGHI":
                _estilo(ws[f"{col}{r}"], ws[f"{col}20"])
        ws["B37"] = f"Cargas em faixa, linha e ponto — {REVISAO} (somadas aos totais da linha 22)"
        ws["B37"].font = copy(ws["B28"].font)
        ws["B38"] = "Cargas em faixa, linha e ponto — empuxo (Boussinesq)"
        ws["C38"], ws["D38"], ws["E38"], ws["F38"] = "=bq_Fh", "=0", "=B_base", "=bq_zF"
        ws["G38"], ws["H38"] = "=0", "=C38*F38"
        ws["I38"] = "Horizontal, sem atrito; soma-se ao empuxo de terra (aba Boussinesq)"
        ws["B39"] = "Cargas em faixa, linha e ponto sobre o talão (peso)"
        ws["C39"], ws["D39"] = "=0", '=IF(AND(q_estab="Sim",bq_W>0),bq_W,0)'
        ws["E39"], ws["F39"], ws["G39"], ws["H39"] = "=bq_xW", "=z_ter", "=D39*E39", "=0"
        ws["I39"] = "Somente se a sobrecarga sobre o talão for estabilizante"
        ws["C22"], ws["D22"] = "=SUM(C5:C21)+C38+C39", "=SUM(D5:D21)+D38+D39"
        ws["G22"], ws["H22"] = "=SUM(G5:G21)+G38+G39", "=SUM(H5:H21)+H38+H39"
        ws["C24"] = '=SUMIF(C5:C21,">0")+MAX(0,C38)'
        # posição do bloco de coroamento (padrão do aplicativo: alinhado ao tardoz)
        xe0 = "IF(AND(anc_n2=0,OR(b_ponta<=0.0001,b_talao<=0.0001)),B_base/2,anc_x)"
        proprio = 'AND(bl_usar="Sim",bl_pos<>"Centrado nas estacas (planilha)")'
        ws["C32"] = (f'=IF({proprio},IF(bl_pos="Alinhado ao tardoz",x_tb-bl_B,bl_x)+bl_B/2,'
                     f"IF(anc_n2>0,({xe0}+anc_x2)/2,{xe0}))")
        ws["C31"] = f"=IF(AND({proprio},anc_n2=0),bl_xe,{xe0})"
        ws["B31"] = ("Posição adotada da 1ª linha (B/2 se só uma linha e base para um lado só; no eixo do bloco "
                     "quando o bloco tem posição própria e há uma só linha)")
        ws["B32"] = "Centro do bloco (alinhado ao tardoz, informado ou centrado nas estacas — Entrada, seção 12)"


# ============================================================================ 4. Resumo
def revisar_resumo(wb) -> None:
    for aba, sufixo in (("Resumo", ""), ("Resumo F2", "_2")):
        ws = wb[aba]
        for row in ws.iter_rows():
            for c in row:
                if isinstance(c.value, str) and c.value.startswith("="):
                    v = c.value.replace("_xlfn.CONCAT(", "CONCATENATE(")      # CONCAT não existe no Excel 2016
                    # TEXT(x;"0.00") mostra "003" no Excel em português; FIXED usa o separador do sistema
                    v = re.sub(r'TEXT\(([^,()]+),"0\.(0+)"\)', lambda m: f"FIXED({m.group(1)},{len(m.group(2))})", v)
                    c.value = v
        ws["F23"] = f'=IF(C23<=D23,"OK",IF(AND(F_N{sufixo}>0,C23<=0.25+0.000000001),"OK*","NÃO OK"))'
        _trocar(ws, "C33", 'F23="OK"', 'LEFT(F23,2)="OK"')
        ws["B36"] = ("OK* em e/B: entre o limite e 0,25 a base descola em parte; só é aceita se passar nas verificações "
                     "da base (aba Dimensionamento, verificações adicionais e linha 47).")
        ws["B36"].font = Font(name="Arial", size=9, italic=True)
    wb["Resumo"]["I38"] = "=dm_atende"


# ============================================================================ 5. Combinações da base
COL0 = 4      # coluna D
LIN_Q = 23    # primeira fatia


def criar_combinacoes(wb) -> None:
    ws = wb.create_sheet("Combinações", index=wb.sheetnames.index("Forças"))
    negrito = Font(name="Arial", size=10, bold=True)
    normal = Font(name="Arial", size=10)
    ws["B1"] = f"COMBINAÇÕES DE AÇÕES PARA DIMENSIONAR A BASE (ponta e talão) — {REVISAO}"
    ws["B1"].font = Font(name="Arial", size=13, bold=True)
    ws["B2"] = ("Equilíbrio: empuxo (kE), pesos/ancoragem/resistências (kP) e água (kA) com 1,0 ou γf; a reação do solo sai "
                "do equilíbrio de cada combinação. Local do GEO5: empuxo vertical × γf, pesos e reação de serviço × 1,0. "
                "Locais (todas): reação de serviço (kR), pesos (kW) e empuxo vertical (kV) com 1,0 ou γf — não equilibradas, "
                "só entram com a opção 'Equilíbrio + todas as locais'. Vale o pior caso (NBR 8681).")
    ws["B2"].alignment = Alignment(wrap_text=True, vertical="top")
    ws["B2"].font = normal
    ws.merge_cells("B2:Q2")
    ws.row_dimensions[2].height = 48
    ws.column_dimensions["B"].width = 44
    ws.column_dimensions["C"].width = 3

    # somas por grupo de ações (por fase)
    grupos = {1: "Forças", 2: "'Forças F2'"}
    ws["AM4"], ws["AN4"], ws["AO4"] = "Somas por grupo de ações", "Fase 1", "Fase 2"
    for c in ("AM4", "AN4", "AO4"):
        ws[c].font = negrito
    defs = [
        ("NE", "N empuxo (linhas 12, 13 e 38)", "{F}!$D$12+{F}!$D$13+{F}!$D$38"),
        ("ME", "M empuxo (Mres − Movr)", "{F}!$G$12-{F}!$H$12+{F}!$G$13-{F}!$H$13+{F}!$G$38-{F}!$H$38"),
        ("NA", "N água (linhas 14, 17 e 21)", "{F}!$D$14+{F}!$D$17+{F}!$D$21"),
        ("MA", "M água", "{F}!$G$14-{F}!$H$14+{F}!$G$17-{F}!$H$17+{F}!$G$21-{F}!$H$21"),
        ("NS", "N solo sobre a ponta (linha 10)", "{F}!$D$10"),
        ("MS", "M solo sobre a ponta", "{F}!$G$10-{F}!$H$10"),
        ("NP", "N pesos e demais", "{F}!$D$22-{F}!$D$12-{F}!$D$13-{F}!$D$38-{F}!$D$14-{F}!$D$17-{F}!$D$21-{F}!$D$10"),
        ("MP", "M pesos e demais", ""),     # montado abaixo (total − empuxo − água − solo da ponta)
        ("AG", "Há água? (1 = sim)", "IF(OR({F}!$C$14<>0,{F}!$D$14<>0,{F}!$C$17<>0,{F}!$D$17<>0,{F}!$C$21<>0,{F}!$D$21<>0),1,0)"),
        ("Pav", "Pa,v (componente vertical do empuxo)", "p_Pav{s}"),
        ("xPav", "x de Pa,v", "p_xPav{s}"),
        ("FN", "N de serviço", "F_N{s}"),
        ("Re", "e de serviço", "R_e{s}"),
    ]
    gref = {}
    for i, (k, rot, f) in enumerate(defs):
        r = 5 + i
        ws[f"AM{r}"] = rot
        for fase, col in ((1, "AN"), (2, "AO")):
            ff = f.format(F=grupos[fase], s="" if fase == 1 else "_2")
            if k == "MP":
                ff = f"{grupos[fase]}!$G$22-{grupos[fase]}!$H$22-{col}6-{col}8-{col}10"
            ws[f"{col}{r}"] = "=" + ff
            gref[(k, fase)] = f"${col}${r}"
    ws.column_dimensions["AM"].width = 40
    _nome(wb, "cb_agua", "Combinações!$AN$13")
    ws["AM19"] = "Fase 2 considerada (travamento)"
    ws["AN19"] = '=IF(trav_usar="Sim",1,0)'

    rotulos = {5: "Fase", 6: "Tipo", 7: "k1 (eq.: kE · local: kV)", 8: "k2 (eq.: kP · local: kW)",
               9: "k3 (eq.: kA · local: kR)", 10: "Fase considerada (1/0)", 11: "N de cálculo (kN/m)",
               12: "Mres − Movr de cálculo (kN·m/m)", 13: "Excentricidade e (m)", 14: "Resultante dentro da base (1/0)",
               15: "B' = B − 2|e| (m)", 16: "σ máx. linear (kPa; 0 se fora)", 17: "M ponta — tração embaixo (kN·m/m)",
               18: "V ponta (kN/m)", 19: "M talão — tração em cima (kN·m/m)", 20: "V talão (kN/m)",
               22: "Carga líquida na base q (kPa, ↑ +) — 40 fatias (x na aba Dimensionamento)"}
    for r, t in rotulos.items():
        ws[f"B{r}"] = t
        ws[f"B{r}"].font = negrito if r in (5, 6, 22) else normal

    colunas = []   # (letra, fase, tipo, k1, k2, k3)
    for fase in (1, 2):
        for kE in ("1", "gf_f"):
            for kP in ("1", "gf_f"):
                for kA in ("1", "gw_f"):
                    colunas.append((fase, "Equilíbrio", kE, kP, kA))
        colunas.append((fase, "Local GEO5", "gf_f", "1", "1"))
        for kR in ("1", "gf_f"):
            for kW in ("1", "gf_f"):
                for kV in ("1", "gf_f"):
                    colunas.append((fase, "Local", kV, kW, kR))
    dim = "Dimensionamento!"
    x, zona = f"{dim}$C$212:$C$251", f"{dim}$I$212:$I$251"
    anc_m = ('IF(anc_usar="Sim",(anc_n1*MAX(0,anc_xe-x_tb)+anc_n2*MAX(0,anc_x2-x_tb))*anc_Fe/anc_esp,0)')
    anc_v = 'IF(anc_usar="Sim",(anc_n1*(anc_xe>x_tb)+anc_n2*(anc_x2>x_tb))*anc_Fe/anc_esp,0)'
    info = []
    for j, (fase, tipo, k1, k2, k3) in enumerate(colunas):
        L = get_column_letter(COL0 + j)
        ws.column_dimensions[L].width = 11
        g = lambda k: gref[(k, fase)]   # noqa: E731
        ws[f"{L}5"], ws[f"{L}6"] = fase, tipo
        ws[f"{L}7"], ws[f"{L}8"], ws[f"{L}9"] = f"={k1}", f"={k2}", f"={k3}"
        ws[f"{L}10"] = "=1" if fase == 1 else "=$AN$19"
        q = f"{L}${LIN_Q}:{L}${LIN_Q + 39}"
        if tipo == "Equilíbrio":
            ksp = f"IF({L}8>1,gf_sp,MIN(gf_sp,1))"
            ws[f"{L}11"] = f"={L}7*{g('NE')}+{L}8*{g('NP')}+{L}9*{g('NA')}+{ksp}*{g('NS')}"
            ws[f"{L}12"] = f"={L}7*{g('ME')}+{L}8*{g('MP')}+{L}9*{g('MA')}+{ksp}*{g('MS')}"
            ws[f"{L}13"] = f"=IF({L}11>0,B_base/2-{L}12/{L}11,0)"
            ws[f"{L}14"] = f"=IF(AND({L}11>0,ABS({L}13)<B_base/2),1,0)"
            ws[f"{L}15"] = f"=MAX(0,B_base-2*ABS({L}13))"
            ws[f"{L}16"] = (f"=IF({L}11<=0,0,IF(ABS({L}13)>=B_base/2,0,IF(ABS({L}13)<=B_base/6,"
                            f"{L}11/B_base*(1+6*ABS({L}13)/B_base),2*{L}11/(3*(B_base/2-ABS({L}13))))))")
        else:
            for r in (11, 12, 13, 15, 16):
                ws[f"{L}{r}"] = "—"
            ws[f"{L}14"] = f"=IF(AND({g('FN')}>0,ABS({g('Re')})<B_base/2),1,0)"
        for i in range(40):
            r = LIN_Q + i
            xi = f"{dim}$C${212 + i}"
            u, w, h = f"{dim}$F${212 + i}", f"{dim}$G${212 + i}", f"{dim}$H${212 + i}"
            if tipo == "Equilíbrio":
                N, e, Bef = f"{L}$11", f"{L}$13", f"{L}$15"
                sig = (f'IF(sig_dim="Retangular (Meyerhof)",IF(OR(AND({e}>=0,{xi}<={Bef}),AND({e}<0,{xi}>=B_base-{Bef})),'
                       f"{N}/{Bef},0),IF(ABS({e})<=B_base/6,{N}/B_base+12*{N}*{e}*(B_base/2-{xi})/B_base^3,"
                       f"2*{N}/(3*(B_base/2-ABS({e})))*MAX(0,1-IF({e}>=0,{xi},B_base-{xi})/(3*(B_base/2-ABS({e}))))))")
                ws[f"{L}{r}"] = f"=IF({L}$14=1,{sig}+{L}$9*{u}-{L}$8*({w}+{h}),0)"
            else:
                sig_s = f"{dim}${'D' if fase == 1 else 'E'}${212 + i}"
                ws[f"{L}{r}"] = f"=IF({L}$14=1,{L}$9*({sig_s}+{u})-{L}$8*({w}+{h}),0)"
        ok = f"{L}14=1"
        ws[f"{L}17"] = f'=IF(AND({ok},b_ponta>0.0001),SUMPRODUCT(({zona}="Ponta")*{q}*(x_fb-{x}))*B_base/40,0)'
        ws[f"{L}18"] = f'=IF(AND({ok},b_ponta>0.0001),SUMPRODUCT(({zona}="Ponta")*{q})*B_base/40,0)'
        pav = f"IF({g('xPav')}>x_tb,{L}7*{g('Pav')},0)"
        ws[f"{L}19"] = (f'=IF(AND({ok},b_talao>0.0001),-SUMPRODUCT(({zona}="Talão")*{q}*({x}-x_tb))*B_base/40+{anc_m}'
                        f"+{pav}*({g('xPav')}-x_tb),0)")
        ws[f"{L}20"] = f'=IF(AND({ok},b_talao>0.0001),-SUMPRODUCT(({zona}="Talão")*{q})*B_base/40+{anc_v}+{pav},0)'
        for r in range(5, 21):
            ws[f"{L}{r}"].font = normal
            if r >= 11:
                ws[f"{L}{r}"].number_format = "0.00"
        ws[f"{L}5"].font = ws[f"{L}6"].font = negrito
        info.append((L, fase, tipo, k1, k2, k3))

    # envoltórias (contribuição 0 quando a combinação não vale)
    R0 = 66
    ws[f"B{R0 - 1}"] = "Envoltórias (máximo das combinações consideradas; 0 quando nenhuma)"
    ws[f"B{R0 - 1}"].font = negrito
    alvos = [("M_pt", 17, False), ("V_pt", 18, True), ("M_tl", 19, False), ("V_tl", 20, True)]
    conjuntos = {"eq": "Equilíbrio", "geo": "Local GEO5", "loc": "Local"}
    linha = R0
    resumo = {}
    for cj, tipo in conjuntos.items():
        for nome, r, absoluto in alvos + [("N_pt", 17, None), ("N_tl", 19, None)]:
            ws[f"B{linha}"] = f"{tipo}: {nome}"
            ws[f"B{linha}"].font = normal
            for (L, fase, tp, *_k) in info:
                if tp != tipo:
                    continue
                val = f"ABS({L}{r})" if absoluto else (f"-{L}{r}" if absoluto is None else f"{L}{r}")
                ws[f"{L}{linha}"] = f"=IF(AND({L}10=1,{L}14=1),{val},0)"
                ws[f"{L}{linha}"].number_format = "0.00"
            primeira, ultima = get_column_letter(COL0), get_column_letter(COL0 + len(info) - 1)
            ws[f"C{linha}"] = f"=MAX(0,{primeira}{linha}:{ultima}{linha})"
            ws[f"C{linha}"].number_format = "0.00"
            resumo[(cj, nome)] = f"Combinações!$C${linha}"
            linha += 1
    # combinação "ações favoráveis em 1,0" (kE = γf, kP = 1, kA = γw): critério do GEO5
    fav_cols = [L for (L, fase, tp, k1, k2, k3) in info if tp == "Equilíbrio" and k1 == "gf_f" and k2 == "1" and k3 == "gw_f"]
    for nome, r, absoluto in alvos:
        ws[f"B{linha}"] = f"Favoráveis em 1,0: {nome}"
        partes = ",".join(f"IF(AND({L}10=1,{L}14=1),{'ABS(' + L + str(r) + ')' if absoluto else L + str(r)},0)"
                          for L in fav_cols)
        ws[f"C{linha}"] = f"=MAX(0,{partes})"
        ws[f"C{linha}"].number_format = "0.00"
        resumo[("fav", nome)] = f"Combinações!$C${linha}"
        linha += 1
    eq_cols = [L for (L, fase, tp, *_k) in info if tp == "Equilíbrio"]
    ws[f"B{linha}"] = "Combinação de equilíbrio com a resultante fora da base (1 = sim)"
    ws[f"C{linha}"] = "=IF(OR(" + ",".join(f"AND({L}10=1,{L}14=0,IF({L}5=1,F_N,F_N_2)>0)" for L in eq_cols) + "),1,0)"
    resumo["fora"] = f"Combinações!$C${linha}"
    linha += 1
    ws[f"B{linha}"] = "σ máx. linear de cálculo (combinações de equilíbrio)"
    ws[f"C{linha}"] = "=MAX(0," + ",".join(f"IF({L}10=1,{L}16,0)" for L in eq_cols) + ")"
    resumo["sig"] = f"Combinações!$C${linha}"
    linha += 1
    for k, v in resumo.items():
        nome = {"fora": "cb_fora", "sig": "bd_s_comb"}.get(k) if isinstance(k, str) else f"cb_{k[0]}_{k[1]}"
        _nome(wb, nome, v)
    ws.freeze_panes = "D7"
    wb._combinacoes_fav = fav_cols[0]


# ============================================================================ 6. Dimensionamento
def revisar_dimensionamento(wb) -> None:
    ws = wb["Dimensionamento"]
    gf = "gf_f"
    # 6.1 cortina: resistência do solo da frente com fator 1,0 (ação favorável — NBR 8681)
    for c, t in (("V83", "Mk frente"), ("W83", "Vk frente"), ("X83", "VSd")):
        ws[c] = t
        _estilo(ws[c], ws["U83"])
    for r in range(84, 105):
        ws[f"V{r}"] = f"=SUMPRODUCT(($C$108:$C$207>C{r})*$Q$108:$Q$207*($C$108:$C$207-C{r}))"
        ws[f"W{r}"] = f"=SUMPRODUCT(($C$108:$C$207>C{r})*$Q$108:$Q$207)"
        ws[f"M{r}"] = f'=MAX(0,{gf}*E{r}+({gf}-1)*V{r},IF(trav_usar="Sim",{gf}*G{r}+({gf}-1)*V{r},0))'
        ws[f"R{r}"] = f'=MAX(0,-({gf}*E{r}+({gf}-1)*V{r}),IF(trav_usar="Sim",-({gf}*G{r}+({gf}-1)*V{r}),0))'
        ws[f"X{r}"] = (f'=MAX(ABS({gf}*F{r}+({gf}-1)*W{r}),IF(trav_usar="Sim",ABS({gf}*H{r}+({gf}-1)*W{r}),0))')
        for c in "VWX":
            _estilo(ws[f"{c}{r}"], ws[f"U{r}"])
            ws[f"{c}{r}"].number_format = "0.00"
    ws["I13"], ws["F13"] = "=MAX(M84:M104)", "MSd+ = γf·(solo, q, água) − 1,0·(solo da frente)"
    ws["I19"], ws["F19"] = "=MAX(R84:R104)", "MSd− = idem, tração na face frontal"
    ws["I22"], ws["F22"] = "=MAX(X84:X104)", "VSd (solo da frente com 1,0)"
    # 6.2 cortina: cargas em faixa, linha e ponto (coluna R das fatias)
    ws["R107"] = "σh cargas (Boussinesq)"
    _estilo(ws["R107"], ws["Q107"])
    for r in range(108, 208):
        ws[f"R{r}"] = "=" + bq_na_cortina(f"D{r}")
        _estilo(ws[f"R{r}"], ws[f"Q{r}"])
        ws[f"M{r}"] = f'=(IF(emp_dim="Repouso (K0)",H{r},K{r})+R{r}+F{r}-L{r})*dm_dy'
        ws[f"N{r}"] = f"=(H{r}+R{r}+F{r}-L{r})*dm_dy"
        ws[f"O{r}"] = f'=(IF(emp_dim="Repouso (K0)",H{r},K{r})+R{r})*dm_dy'
    # 6.3 base: sem tensões quando a resultante sai da base; peso das cargas sobre o talão
    for r in range(212, 252):
        for col, s in (("D", ""), ("E", "_2")):
            _trocar(ws, f"{col}{r}", f"IF(F_N{s}<=0,0,IF(ABS(R_e{s})<=B_base/6",
                    f"IF(OR(F_N{s}<=0,ABS(R_e{s})>=B_base/2),0,IF(ABS(R_e{s})<=B_base/6")
        _trocar(ws, f"H{r}", "*MAX(0,IF(cv=1,B_base-x_bt,x_P-x_bt)))/b_talao",
                "*MAX(0,IF(cv=1,B_base-x_bt,x_P-x_bt))+bq_W)/b_talao")
    # 6.4 ponta: a ancoragem sob a ponta não alivia momento nem cortante
    anc_mp = ('-IF(anc_usar="Sim",(anc_n1*MAX(0,x_fb-anc_xe)*(anc_xe<x_fb)+anc_n2*MAX(0,x_fb-anc_x2)*(anc_x2<x_fb))'
              '*anc_Fe/anc_esp,0)')
    anc_vp = '-IF(anc_usar="Sim",(anc_n1*(anc_xe<x_fb)+anc_n2*(anc_x2<x_fb))*anc_Fe/anc_esp,0)'
    _trocar(ws, "I30", anc_mp, "")
    _trocar(ws, "I31", anc_mp, "")
    v = ws["I32"].value
    assert v.count(anc_vp) == 2
    ws["I32"] = v.replace(anc_vp, "")
    ws["F30"] = "Mk ponta pelas pressões na base — Fase 1 (ancoragem não descontada)"
    # 6.5 ponta e talão: pior caso das combinações e equilíbrio do nó cortina-sapata
    bloco = [
        ("dm_MSdA0", "MSd na base da cortina — caso A (com sinal)", f"={gf}*E84+({gf}-1)*V84", "kN·m/m"),
        ("dm_MSd_pt_comb", "Ponta: MSd pior combinação (Combinações)",
         '=MAX(cb_eq_M_pt,IF(comb_base="Equilíbrio + todas as locais (mais severo)",cb_loc_M_pt,cb_geo_M_pt))', "kN·m/m"),
        ("dm_VSd_pt_comb", "Ponta: VSd pior combinação",
         '=MAX(cb_eq_V_pt,IF(comb_base="Equilíbrio + todas as locais (mais severo)",cb_loc_V_pt,cb_geo_V_pt))', "kN/m"),
        ("dm_MSd_tl_comb", "Talão: MSd pior combinação",
         '=MAX(cb_eq_M_tl,IF(comb_base="Equilíbrio + todas as locais (mais severo)",cb_loc_M_tl,cb_geo_M_tl))', "kN·m/m"),
        ("dm_VSd_tl_comb", "Talão: VSd pior combinação",
         '=MAX(cb_eq_V_tl,IF(comb_base="Equilíbrio + todas as locais (mais severo)",cb_loc_V_tl,cb_geo_V_tl))', "kN/m"),
        ("dm_MSd_pt_sup", "Ponta: MSd com tração em cima (face superior)",
         '=MAX(cb_eq_N_pt,IF(comb_base="Equilíbrio + todas as locais (mais severo)",cb_loc_N_pt,cb_geo_N_pt))', "kN·m/m"),
        ("dm_MSd_tl_inf", "Talão: MSd com tração embaixo (face inferior)",
         '=MAX(cb_eq_N_tl,IF(comb_base="Equilíbrio + todas as locais (mais severo)",cb_loc_N_tl,cb_geo_N_tl))', "kN·m/m"),
        ("dm_M_no", "Equilíbrio do nó: MSd cortina − MSd talão (modo 'Máximo')",
         '=IF(OR(b_talao<=0.0001,cf_usar<>"Sim"),MAX(0,dm_MSdA0-dm_MSd_tl),0)', "kN·m/m"),
        ("dm_VtT1", "Vk talão — Fase 1",
         '=IF(b_talao<=0.0001,0,-SUMPRODUCT(($I$212:$I$251="Talão")*$J$212:$J$251)*B_base/40+'
         'IF(anc_usar="Sim",(anc_n1*(anc_xe>x_tb)+anc_n2*(anc_x2>x_tb))*anc_Fe/anc_esp,0)+IF(p_xPav>x_tb,p_Pav,0))', "kN/m"),
        ("dm_VtT2", "Vk talão — Fase 2",
         '=IF(OR(b_talao<=0.0001,trav_usar="Não"),0,-SUMPRODUCT(($I$212:$I$251="Talão")*$K$212:$K$251)*B_base/40+'
         'IF(anc_usar="Sim",(anc_n1*(anc_xe>x_tb)+anc_n2*(anc_x2>x_tb))*anc_Fe/anc_esp,0)+IF(p_xPav_2>x_tb,p_Pav_2,0))', "kN/m"),
        ("dm_VtT", "Vk talão adotado", "=MAX(ABS(dm_VtT1),ABS(dm_VtT2))", "kN/m"),
        ("dm_VSd_tl", "VSd talão = máx(γf·Vk; pior combinação)", f"=MAX({gf}*dm_VtT,dm_VSd_tl_comb)", "kN/m"),
        ("dm_VRd_tl", "VRd do talão (face superior)",
         '=IF(v_mod="VRd1 (NBR lajes)",0.25*dm_fctd*MAX(1,1.6-dm_db_s)*(1.2+40*MIN(0.02,dm_Abs/10000/dm_db_s))*dm_db_s*1000,'
         "0.6*dm_fctd*dm_db_s*1000)", "kN/m"),
        ("dm_N_fav", "N de cálculo — só empuxo e água majorados (Fase 1)", f"=Combinações!{{fav}}11", "kN/m"),
        ("dm_e_fav", "Excentricidade de cálculo — idem", f"=Combinações!{{fav}}13", "m"),
        ("dm_MSd_pt_fav", "Ponta: MSd — só empuxo e água majorados", "=cb_fav_M_pt", "kN·m/m"),
        ("dm_VSd_pt_fav", "Ponta: VSd — idem", "=cb_fav_V_pt", "kN/m"),
        ("dm_MSd_tl_fav", "Talão: MSd — idem", "=cb_fav_M_tl", "kN·m/m"),
        ("dm_VSd_tl_fav", "Talão: VSd — idem", "=cb_fav_V_tl", "kN/m"),
        ("dm_MSd_pt_eq", "Ponta: MSd — combinações de equilíbrio", "=cb_eq_M_pt", "kN·m/m"),
        ("dm_MSd_tl_eq", "Talão: MSd — combinações de equilíbrio", "=cb_eq_M_tl", "kN·m/m"),
        ("dm_MSd_pt_geo", "Ponta: MSd — local do GEO5", "=cb_geo_M_pt", "kN·m/m"),
        ("dm_MSd_tl_geo", "Talão: MSd — local do GEO5", "=cb_geo_M_tl", "kN·m/m"),
        ("dm_MSd_pt_loc", "Ponta: MSd — todas as locais", "=cb_loc_M_pt", "kN·m/m"),
        ("dm_MSd_tl_loc", "Talão: MSd — todas as locais", "=cb_loc_M_tl", "kN·m/m"),
        ("dm_n_comb", "Nº de combinações consideradas",
         '=IF(cb_agua=1,8,4)+IF(comb_base="Equilíbrio + todas as locais (mais severo)",8,1)', "-"),
        ("bd_s_plan", "Laje da base: σ máx. com γf em tudo (critério da planilha)", None, "kPa"),
        ("bd_s_fav", "Laje da base: σ máx. — só empuxo e água majorados", None, "kPa"),
        ("dm_base_invalida", "Resultante fora da base (serviço ou alguma combinação de equilíbrio)? 1 = sim",
         '=IF(OR(AND(F_N>0,ABS(R_e)>=B_base/2),AND(trav_usar="Sim",F_N_2>0,ABS(R_e_2)>=B_base/2),cb_fora=1),1,0)', "-"),
        ("dm_faixa", "Excentricidade entre o limite e B/4 em alguma fase? 1 = sim",
         '=IF(OR(AND(F_N>0,R_eB>eB_lim+0.000000001,R_eB<=0.25+0.000000001),'
         'AND(trav_usar="Sim",F_N_2>0,R_eB_2>eB_lim+0.000000001,R_eB_2<=0.25+0.000000001)),1,0)', "-"),
        ("ex_frac", "Fração comprimida da base na pior fase da faixa",
         '=MIN(IF(AND(F_N>0,R_eB>eB_lim+0.000000001,R_eB<=0.25+0.000000001),MIN(1,MAX(0,3*(0.5-R_eB))),1),'
         'IF(AND(trav_usar="Sim",F_N_2>0,R_eB_2>eB_lim+0.000000001,R_eB_2<=0.25+0.000000001),MIN(1,MAX(0,3*(0.5-R_eB_2))),1))', "-"),
    ]
    ws["F50"] = f"Base — {REVISAO}: combinações de ações, equilíbrio do nó e verificações adicionais"
    _estilo(ws["F50"], ws["F27"])
    fav = wb._combinacoes_fav
    for i, (nome, rot, f, u) in enumerate(bloco):
        r = 51 + i
        ws[f"F{r}"], ws[f"J{r}"] = rot, u
        _estilo(ws[f"F{r}"], ws["F28"])
        _estilo(ws[f"I{r}"], ws["I28"])
        _estilo(ws[f"J{r}"], ws["J28"])
        if f:
            ws[f"I{r}"] = f.replace("{fav}", fav)
        ws[f"I{r}"].number_format = "0.00" if u != "-" else "0.000"
        _nome(wb, nome, f"Dimensionamento!$I${r}")
    # laje da base: σ = máx(γf em tudo; combinações de equilíbrio)
    orig = ws["T40"].value
    linha_plan = 51 + [b[0] for b in bloco].index("bd_s_plan")
    ws[f"I{linha_plan}"] = orig
    favs = [wb._combinacoes_fav, _col_fav_f2(wb)]
    fora = ",".join(f"AND(Combinações!{L}10=1,Combinações!{L}11>0,Combinações!{L}14=0)" for L in favs)
    ws[f"I{linha_plan + 1}"] = (f"=IF(OR({fora}),10000,MAX(0," +
                                ",".join(f"IF(Combinações!{L}10=1,Combinações!{L}16,0)" for L in favs) + "))")
    ws["T40"] = "=MAX(bd_s_plan,bd_s_comb)"
    # N e M de cálculo da laje (γf em tudo) passam a incluir as cargas em faixa, linha e ponto
    ws["T37"] = "=SUMPRODUCT(Forças!$D$5:$D$21,$X$6:$X$22)+gf_f*(Forças!$D$38+Forças!$D$39)"
    ws["T38"] = ("=SUMPRODUCT(Forças!$G$5:$G$21,$X$6:$X$22)-SUMPRODUCT(Forças!$H$5:$H$21,$X$6:$X$22)"
                 "+gf_f*(Forças!$G$38-Forças!$H$38+Forças!$G$39-Forças!$H$39)")
    ws["Q40"] = "σ máx. de cálculo no solo = máx(γf em tudo; combinações de equilíbrio)"
    # ponta, talão e cortante adotados
    ws["I39"] = ('=IF(b_ponta<=0.0001,0,IF(ponta_mod="Igual à cortina (GEO5)",dm_MSdA0,IF(ponta_mod="Pressões na base",'
                 f'MAX({gf}*dm_Mtp,dm_MSd_pt_comb),MAX({gf}*dm_MtP1,{gf}*dm_MtP2,dm_MSd_pt_comb,dm_M_no))))')
    ws["F39"] = "MSd ponta = máx(γf·Mk; pior combinação; equilíbrio do nó no modo 'Máximo')"
    ws["I42"], ws["F42"] = f"=MAX({gf}*dm_Mtt,dm_MSd_tl_comb)", "MSd talão = máx(γf·Mk; pior combinação)"
    ws["I46"], ws["F46"] = f"=MAX({gf}*dm_VtP,dm_VSd_pt_comb)", "VSd ponta = máx(γf·Vk; pior combinação)"
    # 6.6 verificações adicionais
    ws["L36"] = f"VERIFICAÇÕES ADICIONAIS ({REVISAO} — NBR 6118 e NBR 6122)"
    _estilo(ws["L36"], ws["L33"])
    for c in "MNO":
        _estilo(ws[f"{c}36"], ws[f"{c}33"])
    tl_on = 'NOT(AND(cf_usar="Sim",NOT(cf_tipo="Na frente (sobre a ponta)")))'
    pt_on = 'NOT(AND(cf_usar="Sim",cf_tipo="Na frente (sobre a ponta)"))'
    asn = lambda M, d: (f"IF({M}<=0,0,IF({d}^2<={M}/(0.425*dm_fcd*1000),-1,0.68*dm_fcd*1000*1.25*({d}-SQRT({d}^2-{M}/"
                        f"(0.425*dm_fcd*1000)))/(dm_fyd*1000)*10000))")   # noqa: E731
    st_as = lambda r: f'IF(M{r}<0,"NÃO OK",IF(N{r}>=M{r}-0.000000001,"OK","NÃO OK"))'   # noqa: E731
    st_max = lambda r: f'IF(M{r}<=N{r}+0.000000001,"OK","NÃO OK")'   # noqa: E731
    extras = [
        ("Talão em balanço: VSd ≤ VRd (NBR 6118 19.4.1)", "=dm_VSd_tl", "=dm_VRd_tl",
         f'=IF(AND({tl_on},b_talao>0.0001),{st_max(37)},"—")'),
        ("Cortina — face do tardoz: espaçamento ≤ mín(20 cm; 2h) (NBR 6118 20.1)", "=ar_tz_s", "=MIN(20,2*t_base*100)",
         "=" + st_max(38)),
        ("Cortina — face frontal: espaçamento ≤ mín(20 cm; 2h)", "=ar_fr_s", "=MIN(20,2*t_base*100)", "=" + st_max(39)),
        ("Base — face inferior: espaçamento ≤ mín(20 cm; 2h)", "=ar_bi_s", "=MIN(20,2*h_sap*100)", "=" + st_max(40)),
        ("Base — face superior: espaçamento ≤ mín(20 cm; 2h)", "=ar_bs_s", "=MIN(20,2*h_sap*100)", "=" + st_max(41)),
        ("Talão — face inferior (tração embaixo em alguma combinação): As ef ≥ As nec",
         "=" + asn("dm_MSd_tl_inf", "dm_db_i"), "=dm_Abi",
         f'=IF(AND(dm_MSd_tl_inf>0.000001,b_talao>0.0001,{tl_on}),{st_as(42)},"—")'),
        ("Ponta — face superior (tração em cima em alguma combinação): As ef ≥ As nec",
         "=" + asn("dm_MSd_pt_sup", "dm_db_s"), "=dm_Abs",
         f'=IF(AND(dm_MSd_pt_sup>0.000001,b_ponta>0.0001,{pt_on}),{st_as(43)},"—")'),
        ("Resultante de cálculo dentro da base (serviço e combinações de equilíbrio)", "=dm_base_invalida", "=0",
         '=IF(dm_base_invalida=0,"OK","NÃO OK")'),
        ("Base com descolamento (e entre o limite e B/4): área comprimida ≥ 2/3 (NBR 6122 7.6.2)", "=2/3", "=ex_frac",
         f'=IF(dm_faixa=1,{st_max(45)},"—")'),
    ]
    for i, (rot, sol, res, st) in enumerate(extras):
        r = 37 + i
        for c, src in (("L", "L31"), ("M", "M31"), ("N", "N31"), ("O", "O31")):
            _estilo(ws[f"{c}{r}"], ws[src])
        ws[f"L{r}"], ws[f"M{r}"], ws[f"N{r}"], ws[f"O{r}"] = rot, sol, res, st
    ws["L47"] = "RESULTADO DO DIMENSIONAMENTO (todas as verificações)"
    _estilo(ws["L47"], ws["L33"])
    _estilo(ws["O47"], ws["O33"])
    ws["O47"] = '=IF(AND(dm_geral="ATENDE",' + ",".join(f'O{r}<>"NÃO OK"' for r in range(37, 46)) + '),"ATENDE","NÃO ATENDE")'
    _nome(wb, "dm_atende", "Dimensionamento!$O$47")
    ws["L48"] = ("A linha 33 mantém o critério da planilha original (26 verificações). Vale a linha 47.")
    ws["L48"].font = Font(name="Arial", size=9, italic=True)


def _col_fav_f2(wb) -> str:
    """Coluna da combinação 'favoráveis em 1,0' da Fase 2 (17 colunas depois da Fase 1)."""
    from openpyxl.utils import column_index_from_string
    return get_column_letter(column_index_from_string(wb._combinacoes_fav) + 17)


# ============================================================================ 7. Notas
NOTAS_REV = [
    ("t", f"{REVISAO.upper()} — {DATA}: alterações em relação à versão original"),
    ("p", "A planilha passou a seguir o aplicativo (núcleo em Python, conferido contra esta revisão por "
          "tools/conferir_revisao.py). A versão original continua no repositório como referência histórica."),
    ("s", "Padrões alterados (Entrada)"),
    ("p", "• Atrito base-solo δb = 3/4·φf (era 2/3)."),
    ("p", "• Adesão base-solo a = α·cf com α = 0,5 (era 0). α por tipo de solo, sem norma brasileira que o fixe: areias e "
          "siltes sem argila 0 (coesão aparente); solos argilosos mistos e argilas rijas a duras 0,5; argila muito mole a "
          "média 2/3 (faixa de 1/2 a 2/3 de Das); condição não drenada pela razão adesão/coesão do NAVFAC DM-7.2."),
    ("p", "• Solo na frente do muro: resistência em repouso K0·σ' (era nenhuma). Só conte com ela se o solo não puder ser "
          "escavado nem erodido."),
    ("s", "Estabilidade"),
    ("p", "• Excentricidade: limite continua B/6. Entre o limite e B/4 a situação aparece como 'OK*': a base descola em parte "
          "e só é aceita se a área comprimida for ≥ 2/3 (NBR 6122 7.6.2) e a ponta e o talão passarem nas verificações da "
          "aba Dimensionamento. Acima de B/4, NÃO OK."),
    ("p", "• Cargas em faixa, em linha e concentrada no terrapleno (Entrada, seção 11; aba Boussinesq): pressões da teoria "
          "da elasticidade na forma de Terzaghi/NAVFAC, parede rígida (×2) por padrão. Entram na estabilidade (Forças, "
          "linhas 38–39, somadas aos totais), na cortina (coluna R das fatias) e no talão (peso)."),
    ("p", "• Bloco de coroamento: face alinhada ao tardoz por padrão (Entrada, seção 12); as outras opções são centrado nas "
          "estacas (comportamento original) ou posição informada."),
    ("s", "Dimensionamento"),
    ("p", "• Cortina: a resistência do solo da frente é ação favorável e entra com fator 1,0 (antes era multiplicada por γf)."),
    ("p", "• Ponta: a força das estacas sob a ponta não é mais descontada do momento nem do cortante (é resistência passiva, "
          "mobilizada só na ruptura; o GEO5 também não desconta)."),
    ("p", "• Base: pior caso entre as combinações em equilíbrio (empuxo, pesos e água com 1,0 ou γf — NBR 8681) e a "
          "combinação local do GEO5 (empuxo vertical × γf; pesos e reação do solo de serviço × 1,0). A opção 'Equilíbrio + "
          "todas as locais' acrescenta 8 combinações não equilibradas, bem mais severas no talão. Aba Combinações."),
    ("p", "• Equilíbrio do nó cortina-sapata (modo 'Máximo'): a ponta recebe no mínimo o momento da cortina menos o do talão."),
    ("p", "• Laje da base entre contrafortes: σ máx. = maior entre γf em tudo e as combinações de equilíbrio."),
    ("p", "• Resultante fora da base (no serviço ou em alguma combinação de equilíbrio): a base é reprovada; as tensões "
          "deixam de ser negativas."),
    ("p", "• Verificações adicionais (Dimensionamento, linhas 37–45): cortante no talão, espaçamento máximo das barras, "
          "faces opostas de ponta e talão, resultante dentro da base e área comprimida na faixa até B/4. O resultado final "
          "do dimensionamento passou a ser a linha 47."),
    ("s", "Correções da planilha"),
    ("p", "• Avisos: CONCAT trocado por CONCATENATE (o Excel 2016 e anteriores mostravam #NOME?)."),
    ("p", "• Títulos: TEXT(x;\"0.00\") trocado por FIXED(x;2) — no Excel em português aparecia 'B = 003 m'."),
    ("p", "• Listas de validação com vírgula dentro da opção ('0,45 (NBR 6118)', '0,6·fctd·b·d (GEO5)') passaram para a "
          "aba oculta Listas."),
    ("s", "Não incluído na planilha (só no aplicativo)"),
    ("p", "• Cortina e base entre contrafortes como laje com borda livre por elementos finitos: a planilha mantém os "
          "coeficientes do GEO5."),
    ("p", "• Concreto acima de C40 (ηc e parâmetros do grupo II), força mínima de travamento exata (iterativa), verificações "
          "de descolamento com a distribuição triangular quando a opção de tensão é 'Retangular (Meyerhof)', leitura de "
          "sondagem em PDF e as versões para computador e Android."),
]


def revisar_notas(wb) -> None:
    ws = wb["Notas"]
    r = ws.max_row + 2
    for tipo, texto in NOTAS_REV:
        c = ws[f"B{r}"]
        c.value = texto
        if tipo == "t":
            c.font = Font(name="Arial", size=14, bold=True, color="FF1F4E78")
        elif tipo == "s":
            _estilo(c, ws["B2"])
        else:
            _estilo(c, ws["B3"])
        c.alignment = Alignment(wrap_text=True, vertical="top")
        r += 1


def _gravar_valores(destino: Path) -> None:
    """Se houver LibreOffice, grava os valores calculados no arquivo (o Excel recalcula ao abrir de
    qualquer forma; os valores servem para visualizadores que não calculam)."""
    import json
    import subprocess
    recalc = next(Path("/root/.claude/skills").rglob("xlsx/scripts/recalc.py"), None) if Path("/root/.claude/skills").exists() else None
    if recalc is None:
        print("aviso: LibreOffice/recalc.py ausente — arquivo gravado sem valores calculados (o Excel calcula ao abrir)")
        return
    r = subprocess.run([sys.executable, str(recalc), str(destino), "180"], capture_output=True, text=True)
    try:
        info = json.loads(r.stdout)
    except ValueError:
        print("aviso: recálculo no LibreOffice falhou:", r.stdout[-300:], r.stderr[-300:])
        return
    print(f"recalculado no LibreOffice: {info.get('total_formulas')} fórmulas, {info.get('total_errors')} erros")


def _restaurar_grafico(origem: Path, destino: Path) -> None:
    """O openpyxl regrava o gráfico do croqui perdendo parte da formatação: devolve o XML original
    (as séries apontam para a aba Geometria, que a revisão não altera)."""
    import shutil
    import zipfile
    with zipfile.ZipFile(origem) as zo:
        original = zo.read("xl/charts/chart1.xml")
    tmp = destino.with_suffix(".tmp.xlsx")
    with zipfile.ZipFile(destino) as zi, zipfile.ZipFile(tmp, "w", zipfile.ZIP_DEFLATED) as zw:
        for item in zi.infolist():
            zw.writestr(item, original if item.filename == "xl/charts/chart1.xml" else zi.read(item.filename))
    shutil.move(tmp, destino)


# ============================================================================
def revisar(origem: Path = ORIGEM, destino: Path = DESTINO) -> Path:
    wb = openpyxl.load_workbook(origem)
    revisar_entrada(wb)
    criar_boussinesq(wb)
    revisar_forcas(wb)
    criar_combinacoes(wb)
    revisar_resumo(wb)
    revisar_dimensionamento(wb)
    revisar_notas(wb)
    wb.properties.title = f"Verificação de muro de arrimo — NBR 11682 / NBR 6118 — {REVISAO}"
    wb.save(destino)
    _restaurar_grafico(origem, destino)
    _gravar_valores(destino)
    print(f"gravado: {destino}")
    return destino


if __name__ == "__main__":
    revisar()
