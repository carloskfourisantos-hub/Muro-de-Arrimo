"""Projeto JSON, importação/exportação Excel, memorial PDF, gráficos e ferramentas."""
import io
from pathlib import Path

import matplotlib.pyplot as plt
import openpyxl
import pytest

from core.fases import calcular
from core.models import Entrada
from core.planilha import PADROES_PLANILHA
from core.solver import base_minima, estabilidade_ok, estudo_parametrico, menor_valor, sugerir_armaduras
from io_ import excel, memorial, projeto
from ui import graficos

PLANILHA = Path(__file__).resolve().parents[1] / "Verificacao_Muro_Arrimo_NBR11682.xlsx"
COMPLETO = dict(cf_usar=True, anc_usar=True, anc_n2=1, anc_x2=1.6, bl_usar=True, bl_B=1.8, trav_usar=True,
                hw_at=1.8, hw_fr=0.5, beta_t=8, c_at=3)


def test_projeto_json_ida_e_volta():
    e = Entrada(**COMPLETO)
    e2, meta = projeto.carregar(projeto.salvar(e, nome="Muro M1", obra="Obra X"))
    assert e2 == e and meta["nome"] == "Muro M1"
    with pytest.raises(ValueError):
        projeto.carregar('{"formato": "outro"}')


@pytest.mark.skipif(not PLANILHA.exists(), reason="planilha de origem ausente")
def test_importar_planilha_original_reproduz_o_padrao():
    # a planilha traz os padrões dela (δb = 2/3·φ, sem adesão, sem resistência frontal), não os do aplicativo
    assert excel.importar(PLANILHA) == Entrada(**PADROES_PLANILHA).resolvida()


def test_exportar_xlsx():
    res = calcular(Entrada(**COMPLETO))
    wb = openpyxl.load_workbook(io.BytesIO(excel.exportar(res, {"nome": "M1"})))
    assert {"Entrada", "Resumo", "Forças F1", "Forças F2", "Dimensionamento", "Valores nomeados"} <= set(wb.sheetnames)
    assert wb["Forças F1"].max_row == 19


@pytest.mark.parametrize("mud", [{}, COMPLETO, dict(b_talao=0, b_ponta=0.1, q_sc=40)],
                         ids=["padrao", "completo", "fora_da_base"])
def test_memorial_pdf(mud):
    pdf = memorial.gerar_pdf(calcular(Entrada(**mud)), {"nome": "Muro M1", "autor": "Eng."})
    assert pdf[:5] == b"%PDF-" and len(pdf) > 60_000


@pytest.mark.parametrize("mud", [{}, COMPLETO, dict(b_talao=0, b_ponta=2.0), dict(modo_cunha="Vertical", hw_at=3),
                                 dict(b_talao=0, b_ponta=0.1, q_sc=40)])
def test_graficos_nao_falham(mud):
    res = calcular(Entrada(**mud))
    for fig in (graficos.croqui(res, 1), graficos.croqui(res, 2), graficos.diagrama_empuxo(res, 1),
                graficos.diagrama_base(res), graficos.diagrama_cortina(res)):
        assert fig.axes
        plt.close(fig)


def test_ferramentas():
    e = Entrada(**PADROES_PLANILHA)             # exemplo da planilha: reprova no deslizamento
    assert not estabilidade_ok(calcular(e))
    v, r = menor_valor(e, "b_talao", 8.0)
    assert v > e.b_talao and estabilidade_ok(r)
    assert not estabilidade_ok(calcular(e.com(b_talao=round(v - 0.05, 4))))
    b = base_minima(e)
    assert b.encontrado and estabilidade_ok(b.resultado)
    linhas = estudo_parametrico(e, "q_sc", [0, 10, 20, 40])
    assert [ln["FSt"] for ln in linhas] == sorted((ln["FSt"] for ln in linhas), reverse=True)
    fig = graficos.grafico_parametrico(linhas, "q (kPa)", dict(FSt=2, FSd=1.5, eB=1 / 6, FScc=3))
    plt.close(fig)
    nova, sug = sugerir_armaduras(e.com(ar_tz_phi=8, ar_tz_s=20))
    assert all(s.atende for s in sug) and calcular(nova).dim.atende
