"""Os quatro memoriais do GEO5 rodados na planilha revisada (recalculada no LibreOffice).

Estabilidade e armaduras batem com o GEO5; as diferenças conhecidas ficam do lado da segurança, salvo
o momento do dente (talão), em que o GEO5 soma o momento do empuxo horizontal.
"""
import sys
from pathlib import Path

import pytest

RAIZ = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(RAIZ / "tools"))
import geo5_na_planilha as gp  # noqa: E402

pytestmark = pytest.mark.skipif(gp.RECALC is None, reason="LibreOffice/recalc.py indisponível")

ESTAB_GEO5 = {          # N, Mres, Movr, FSt, FSd, e/B, σ, FScc
    "sem_talao": (40.95, 49.08, 24.22, 2.03, 1.26, 0.143, 33.72, 2.97),
    "ancoragem": (52.51, 25.57, 12.71, 2.01, 2.20, 0.194, 107.14, 0.93),
    "contrafortes": (75.75, 45.56, 22.97, 1.98, 2.05, 0.202, 127.03, 1.18),
    "talao_C25": (139.11, 158.48, 31.83, 4.98, 2.88, 0.021, 76.40, 1.96),
}
VEREDITO_GEO5 = {"sem_talao": "NÃO ATENDE", "ancoragem": "NÃO ATENDE", "contrafortes": "NÃO ATENDE",
                 "talao_C25": "ATENDE"}


@pytest.fixture(scope="module")
def planilha(tmp_path_factory):
    pasta = tmp_path_factory.mktemp("geo5")
    return {n: gp.rodar(n, pasta / f"{n}.xlsx") for n in gp.MODELOS}


@pytest.mark.parametrize("nome", list(gp.MODELOS))
def test_estabilidade_igual_ao_geo5(planilha, nome):
    r = planilha[nome]
    for chave, geo in zip(("F_N", "F_Mres", "F_Movr", "R_FSt", "R_FSd", "R_eB", "R_sef", "R_FScc"), ESTAB_GEO5[nome]):
        assert r[chave] == pytest.approx(geo, abs=0.006 if geo < 10 else 0.1), chave
    assert r["Estabilidade (Resumo)"] == VEREDITO_GEO5[nome]


def test_dimensionamento(planilha):
    s, a, c, t = (planilha[n] for n in ("sem_talao", "ancoragem", "contrafortes", "talao_C25"))
    assert s["dm_MSdp"] == pytest.approx(94.33, rel=0.002) and a["dm_MSdp"] == pytest.approx(58.15, rel=0.002)
    assert t["dm_Asnp"] * 100 == pytest.approx(869.6, rel=0.003) and t["dm_MRd_pt"] == pytest.approx(141.57, rel=0.001)
    assert c["bd_s"] == pytest.approx(269.24, rel=0.001) and c["bd_M12"] * 0.8 == pytest.approx(90.87, rel=0.001)
    assert t["dm_VSd_tl"] == pytest.approx(21.26, rel=0.004)                   # dente: cortante igual
    # diferenças conhecidas, do lado da segurança
    assert s["dm_VSd_pt"] > 23.00 and a["dm_VSd_pt"] > 46.01 and t["dm_VSd_pt"] > 59.05
    assert t["dm_MSd_pt"] > 67.68                                              # nó com o talão da planilha
    assert c["cf_MSd"] == pytest.approx(1.4 * 178.40, rel=0.003)              # contraforte com γf
    assert c["Dimensionamento (linha 47)"] == "NÃO ATENDE"                    # base reprova, como no GEO5
    # diferença contra a segurança, registrada: dente 26,68 no GEO5 (soma o momento do empuxo horizontal)
    assert t["dm_MSd_tl"] < 26.68
