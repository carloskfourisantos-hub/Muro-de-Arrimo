"""Revisão 01 da planilha (tools/revisar_planilha.py): estrutura, padrões e correções.

A conferência numérica completa contra o aplicativo (LibreOffice, ~90 cenários) é feita por
``tools/conferir_revisao.py``; aqui só o que dá para conferir sem recalcular.
"""
import sys
from pathlib import Path

import openpyxl
import pytest

RAIZ = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(RAIZ / "tools"))
pytestmark = pytest.mark.skipif(not (RAIZ / "Verificacao_Muro_Arrimo_NBR11682.xlsx").exists(),
                                reason="planilha de origem ausente")


@pytest.fixture(scope="module")
def rev(tmp_path_factory):
    import revisar_planilha
    destino = tmp_path_factory.mktemp("rev") / "rev01.xlsx"
    revisar_planilha.revisar(destino=destino)
    return openpyxl.load_workbook(destino)


def _cel(wb, nome):
    aba, cel = wb.defined_names[nome].attr_text.split("!")
    return wb[aba.strip("'")][cel.replace("$", "")]


def test_padroes_novos(rev):
    assert _cel(rev, "k_phi").value == 0.75 and _cel(rev, "k_c").value == 0.5
    assert _cel(rev, "ff_tipo").value == "Em repouso"
    assert _cel(rev, "comb_base").value == "Equilíbrio + local do GEO5"
    assert _cel(rev, "bl_pos").value == "Alinhado ao tardoz"
    assert _cel(rev, "sc_bq").value == "Parede rígida (×2 — Terzaghi/NAVFAC)"


def test_correcoes_da_planilha(rev):
    for ws in rev.worksheets:
        for row in ws.iter_rows():
            for c in row:
                if isinstance(c.value, str) and c.value.startswith("="):
                    assert "_xlfn.CONCAT(" not in c.value, f"{ws.title}!{c.coordinate}"
                    assert 'TEXT(' not in c.value, f"{ws.title}!{c.coordinate}"
    listas = {str(dv.sqref): dv.formula1 for dv in rev["Entrada"].data_validations.dataValidation}
    assert listas["C100"].startswith("=Listas!") and listas["C113"].startswith("=Listas!")
    assert rev["Listas"].sheet_state == "hidden"


def test_original_nao_muda(rev):
    """A original continua sendo a referência da paridade: a revisão é um arquivo novo."""
    orig = openpyxl.load_workbook(RAIZ / "Verificacao_Muro_Arrimo_NBR11682.xlsx")
    assert orig["Entrada"]["C69"].value == "=2/3" and "Combinações" not in orig.sheetnames


def test_estrutura_nova(rev):
    assert {"Combinações", "Boussinesq", "Listas"} <= set(rev.sheetnames)
    for nome in ("dm_atende", "dm_M_no", "dm_MSd_pt_comb", "dm_VSd_tl", "bq_Fh", "bq_zF", "cb_eq_M_tl", "bd_s_comb"):
        assert nome in rev.defined_names, nome
    d = rev["Dimensionamento"]
    assert "dm_MSd_pt_comb" in d["I39"].value and "dm_M_no" in d["I39"].value
    assert "anc_Fe" not in d["I30"].value and "anc_Fe" not in d["I32"].value     # ancoragem não alivia a ponta
    assert "(gf_f-1)*V84" in d["M84"].value                                       # solo da frente com 1,0
    assert "R108" in d["M108"].value                                              # cargas de Boussinesq na cortina
    assert "+C38+C39" in rev["Forças"]["C22"].value and "+C38+C39" in rev["Forças F2"]["C22"].value
    assert 'LEFT(F23,2)="OK"' in rev["Resumo"]["C33"].value
    assert rev["Resumo"]["I38"].value == "=dm_atende"
    assert any("REVISÃO 01" in str(c.value) for c in rev["Notas"]["B"])
