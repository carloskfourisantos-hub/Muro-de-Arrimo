"""Caso de referência do GEO5 5.2026 (Muro de Flexão) com dados e resultados completos.

Muro sem talão: cortina 0,20 × 3,00 m, sapata 1,70 × 0,25 m (ponta de 1,50 m), argila
φ = 30°, c = 5 kPa, γ = 20 kN/m³, δ = 10°, q = 10 kPa, 0,60 m de solo na frente com
resistência frontal em repouso, Coulomb, fatores de segurança. Memorial do GEO5 de 13/11/2026.

Com os critérios do GEO5 selecionados, o núcleo reproduz o GEO5; com os padrões do
aplicativo (δb = 2/3·φ, sem adesão, sem resistência frontal) o deslizamento cai de 1,26 para 0,58.
"""
import pytest

from core.fases import calcular
from core.models import Entrada

MURO = dict(H_muro=3.25, h_sap=0.25, t_topo=0.2, t_base=0.2, b_ponta=1.5, b_talao=0.0, D_frente=0.6,
            solo_ponta=True, q_sc=10, gam_at=20, gsat_at=20, phi_at=30, c_at=5, delta_est=10, gam_f=20, gsat_f=20,
            phi_f=30, c_f=5, ar_tz_phi=16, ar_tz_s=12.0, ar_bi_phi=16, ar_bi_s=15)
CRITERIOS_GEO5 = dict(k_phi=1.0, k_c=1.0, ff_tipo="Em repouso", conv_res="Descontar da ação (GEO5)",
                      sc_vert="Como GEO5", bef_desl="Como GEO5", cc_modo="Informada", qult_inf=100,
                      FSt_min=1.5, FSd_min=1.3, FScc_min=1.5, eB_lim=0.333, v_mod="0,6·fctd·b·d (GEO5)",
                      ponta_mod="Igual à cortina (GEO5)", sig_dim="Retangular (Meyerhof)")


@pytest.fixture(scope="module")
def geo5():
    return calcular(Entrada(**MURO, **CRITERIOS_GEO5))


def test_empuxo_e_forcas(geo5):
    emp, F = geo5.fase1.emp, geo5.fase1.forcas
    assert emp.p_Pah_s == pytest.approx(17.43, abs=0.01)          # empuxo ativo, horizontal
    assert emp.p_Pah_q == pytest.approx(8.04, abs=0.01)           # sobrecarga, horizontal
    assert emp.p_Pav == pytest.approx(3.07 + 1.74, abs=0.01)      # verticais
    assert emp.p_Rff == pytest.approx(1.80, abs=0.005)            # resistência frontal em repouso
    assert geo5.dim.v["dm_KaC"] == pytest.approx(0.308, abs=0.0005)
    pesos = {f.nome: f for f in F.linhas}
    assert pesos["Peso da cortina"].Fz + pesos["Peso da sapata"].Fz == pytest.approx(25.62, abs=0.01)
    assert pesos["Solo sobre a ponta"].Fz == pytest.approx(10.50, abs=0.005)
    assert F.F_N == pytest.approx(40.95, abs=0.02)


def test_tombamento_deslizamento_e_tensoes(geo5):
    F, v = geo5.fase1.forcas, geo5.fase1.verif
    assert F.F_Mres == pytest.approx(49.08, abs=0.03)
    assert F.F_Movr == pytest.approx(24.22, abs=0.03)
    assert v.R_FSt == pytest.approx(2.03, abs=0.006)
    assert v.R_Hres == pytest.approx(29.71, abs=0.02)
    assert v.R_Hact == pytest.approx(23.67, abs=0.01)
    assert v.R_FSd == pytest.approx(1.26, abs=0.006)
    assert v.R_eB == pytest.approx(0.143, abs=0.0006)
    assert v.R_sef == pytest.approx(33.72, abs=0.05)
    assert v.R_FScc == pytest.approx(2.97, abs=0.006)
    assert v.ok_tomb and not v.ok_desl and v.ok_exc and v.ok_cap       # mesmo veredito do GEO5


def test_dimensionamento_da_haste_e_do_avanco(geo5):
    d = geo5.dim.v
    assert d["dm_MSdp"] == pytest.approx(94.33, rel=0.002)        # momento na base da haste
    assert d["dm_VSd"] == pytest.approx(83.33, rel=0.004)
    assert d["dm_Asnp"] * 100 == pytest.approx(1552.2, rel=0.003)  # armadura necessária (mm²)
    assert d["dm_Ast"] * 100 == pytest.approx(1674.8, rel=0.002)   # 8,33 ϕ16 por metro
    assert d["dm_VRd"] == pytest.approx(124.42, rel=0.003)        # 0,6·fctd·b·d
    assert d["dm_MSd_pt"] == pytest.approx(94.33, rel=0.002)      # avanço: igual à haste
    assert d["dm_As_pt"] * 100 == pytest.approx(1106.0, rel=0.003)
    assert d["dm_MRd_pt"] == pytest.approx(112.41, rel=0.002)
    assert d["dm_VRd_pt"] == pytest.approx(162.82, rel=0.003)
    # diferenças conhecidas (o aplicativo fica a favor da segurança):
    assert d["dm_MRdp"] == pytest.approx(101.75, rel=0.015) and d["dm_MRdp"] < 101.75   # GEO5 soma N / armadura comprimida
    assert d["dm_VSd_pt"] > 23.00                                 # cortante do avanço: γf em toda a reação do solo


def test_criterios_padrao_do_aplicativo_sao_mais_conservadores(geo5):
    """O que separa 0,58 de 1,26 no deslizamento são critérios, não o modelo."""
    def fsd(**mud):
        return calcular(Entrada(**{**MURO, **mud})).fase1.verif.R_FSd
    assert fsd() == pytest.approx(0.58, abs=0.006)                                     # δb = 2/3·φ, sem adesão
    assert fsd(k_phi=1.0) == pytest.approx(0.92, abs=0.006)                            # δb = φ
    assert fsd(k_phi=1.0, k_c=1.0) == pytest.approx(1.15, abs=0.006)                   # + adesão c·B'
    quase = fsd(k_phi=1.0, k_c=1.0, ff_tipo="Em repouso", conv_res="Descontar da ação (GEO5)")
    assert quase == pytest.approx(1.244, abs=0.003)                                    # + resistência frontal
    assert quase < geo5.fase1.verif.R_FSd                                              # falta só o Pa,v da sobrecarga
