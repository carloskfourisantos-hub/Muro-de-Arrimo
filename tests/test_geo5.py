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
from core.planilha import PADROES_PLANILHA

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
        return calcular(Entrada(**{**MURO, **PADROES_PLANILHA, **mud})).fase1.verif.R_FSd
    assert fsd() == pytest.approx(0.58, abs=0.006)                                     # δb = 2/3·φ, sem adesão
    assert fsd(k_phi=1.0) == pytest.approx(0.92, abs=0.006)                            # δb = φ
    assert fsd(k_phi=1.0, k_c=1.0) == pytest.approx(1.15, abs=0.006)                   # + adesão c·B'
    quase = fsd(k_phi=1.0, k_c=1.0, ff_tipo="Em repouso", conv_res="Descontar da ação (GEO5)")
    assert quase == pytest.approx(1.244, abs=0.003)                                    # + resistência frontal
    assert quase < geo5.fase1.verif.R_FSd                                              # falta só o Pa,v da sobrecarga


# ---------------------------------------------------------------------------------------------------
# Segundo caso de referência: memorial do GEO5 de 16/11/2026, muro com ancoragem na base.
# Cortina 0,20 × 2,50 m, sapata 0,80 × 0,20 m (ponta de 0,60 m, sem talão), mesmo solo, q = 10 kPa,
# estacas de 0,40 m × 5 m a cada 3 m em x = 0,40 m (a = 20 kPa, SFe = 1,5, barra de 25 mm), C20,
# ϕ12,5 c/ 12 na haste (8,33/m) e ϕ12,5 c/ 13,3 no avanço (7,50/m).
MURO_ANC = dict(H_muro=2.70, h_sap=0.20, t_topo=0.2, t_base=0.2, b_ponta=0.6, b_talao=0.0, D_frente=0.6,
                solo_ponta=True, q_sc=10, gam_at=20, gsat_at=20, phi_at=30, c_at=5, delta_est=10, gam_f=20,
                gsat_f=20, phi_f=30, c_f=5, fck_c=20, ar_tz_phi=12.5, ar_tz_s=12.0, ar_bi_phi=12.5,
                ar_bi_s=100 / 7.5, anc_usar=True, anc_x=0.4, anc_n1=1, anc_n2=0, anc_L=5, anc_d=0.4,
                anc_esp=3.0, anc_a=20, anc_FS=1.5, anc_ds=25, anc_fy=500)
CRITERIOS_ANC = {**CRITERIOS_GEO5, "FSt_min": 2.0, "FSd_min": 1.5}


@pytest.fixture(scope="module")
def geo5_anc():
    return calcular(Entrada(**MURO_ANC, **CRITERIOS_ANC))


def test_ancoragem_empuxo_e_forcas(geo5_anc):
    emp, F = geo5_anc.fase1.emp, geo5_anc.fase1.forcas
    assert emp.p_Pah_s == pytest.approx(10.35, abs=0.01)
    assert emp.p_Pah_q == pytest.approx(6.37, abs=0.01)
    assert emp.p_Pav == pytest.approx(1.82 + 1.45, abs=0.01)
    assert emp.p_Rff == pytest.approx(1.80, abs=0.005)
    pesos = {f.nome: f for f in F.linhas}
    assert pesos["Peso da cortina"].Fz + pesos["Peso da sapata"].Fz == pytest.approx(16.50, abs=0.01)
    assert pesos["Solo sobre a ponta"].Fz == pytest.approx(4.80, abs=0.005)
    assert pesos["Ancoragem na base — 1ª linha de estacas"].Fz == pytest.approx(27.93, abs=0.01)
    assert F.anc.anc_Tp == pytest.approx(83.78, abs=0.01)         # arrancamento por estaca
    assert F.anc.anc_Rt == pytest.approx(163.62, abs=0.01)        # barra
    assert F.F_N == pytest.approx(52.51, abs=0.02)


def test_ancoragem_estabilidade(geo5_anc):
    F, v = geo5_anc.fase1.forcas, geo5_anc.fase1.verif
    assert F.F_Mres == pytest.approx(25.57, abs=0.02)
    assert F.F_Movr == pytest.approx(12.71, abs=0.02)
    assert v.R_FSt == pytest.approx(2.01, abs=0.006)
    assert v.R_Hres == pytest.approx(32.77, abs=0.02)
    assert v.R_Hact == pytest.approx(14.92, abs=0.015)
    assert v.R_FSd == pytest.approx(2.20, abs=0.006)
    assert v.R_eB == pytest.approx(0.194, abs=0.0006)
    assert v.R_sef == pytest.approx(107.14, abs=0.1)
    assert v.R_FScc == pytest.approx(0.93, abs=0.006)
    assert v.ok_tomb and v.ok_desl and v.ok_exc and not v.ok_cap       # mesmo veredito do GEO5


def test_ancoragem_dimensionamento(geo5_anc):
    d = geo5_anc.dim.v
    assert d["dm_MSdp"] == pytest.approx(58.15, rel=0.002)
    assert d["dm_VSd"] == pytest.approx(60.40, rel=0.002)
    assert d["dm_Asnp"] * 100 == pytest.approx(906.7, rel=0.002)
    assert d["dm_Ast"] * 100 == pytest.approx(1022.2, rel=0.001)
    assert d["dm_VRd"] == pytest.approx(108.57, rel=0.001)
    assert d["dm_MSd_pt"] == pytest.approx(58.15, rel=0.002)      # avanço: igual à haste
    assert d["dm_As_pt"] * 100 == pytest.approx(906.7, rel=0.002)
    assert d["dm_MRd_pt"] == pytest.approx(58.93, rel=0.001)      # x/d < 0,259: coincide
    assert d["dm_VRd_pt"] == pytest.approx(108.57, rel=0.001)
    # diferenças conhecidas:
    assert d["dm_MRdp"] == pytest.approx(64.36, rel=0.006)        # haste com x/d = 0,28 > 0,259: GEO5 0,5 % menor
    # cortante do avanço: nenhum dos dois desconta a ancoragem. GEO5 = 46,01 (γf só no empuxo, excentricidade
    # recalculada); aplicativo = γf em toda a reação de serviço, mais conservador.
    assert d["dm_VSd_pt"] == pytest.approx(70.75, abs=0.05) and d["dm_VSd_pt"] > 46.01


def test_ancoragem_nao_alivia_a_ponta():
    """A força da ancoragem sob a ponta não reduz o momento nem o cortante da ponta."""
    base = {**MURO_ANC, **CRITERIOS_ANC, "ponta_mod": "Pressões na base"}
    def ponta(**mud):
        d = calcular(Entrada(**{**base, **mud})).dim.v
        return d["dm_MtP1"], d["dm_VtP"]
    M, V = ponta()
    assert V == pytest.approx(70.75 / 1.4, abs=0.05)
    # com o dobro da adesão a reação do solo aumenta; os esforços da ponta não podem diminuir
    M2, V2 = ponta(anc_a=40)
    assert M2 >= M and V2 >= V


# ---------------------------------------------------------------------------------------------------
# Terceiro caso de referência: memorial do GEO5 de 16/11/2026, muro com contrafortes na frente.
# Cortina 0,20 × 3,00 m, sapata 1,00 × 0,20 m (ponta de 0,80 m, sem talão), contrafortes de 0,40 × 0,80 m
# com vão livre de 2,25 m (o "espaçamento l" do GEO5 é o vão livre: entre eixos são 2,65 m), estacas de
# 0,40 m × 8 m a cada 3 m em x = 0,50 m, C20, Rd = 150 kPa.
MURO_CF = dict(H_muro=3.20, h_sap=0.20, t_topo=0.2, t_base=0.2, b_ponta=0.8, b_talao=0.0, D_frente=0.6,
               solo_ponta=True, q_sc=10, gam_at=20, gsat_at=20, phi_at=30, c_at=5, delta_est=10, gam_f=20,
               gsat_f=20, phi_f=30, c_f=5, fck_c=20, cf_usar=True, cf_tipo="Na frente (sobre a ponta)",
               cf_peso=False, cf_esp=2.65, cf_t=0.40, cf_h=3.0, cf_Lb=0.8, cf_Lt=0.8, cf_n=5, cf_phi=20,
               ar_tz_phi=12.5, ar_tz_s=12.0, ar_fr_phi=10, ar_fr_s=20, ar_hz_tz_phi=8, ar_hz_tz_s=300 / 19,
               ar_hz_fr_phi=8, ar_hz_fr_s=300 / 19, ar_bl_i_phi=12.5, ar_bl_i_s=12.0, ar_bl_s_phi=12.5,
               ar_bl_s_s=12.0, anc_usar=True, anc_x=0.5, anc_n1=1, anc_n2=0, anc_L=8, anc_d=0.4, anc_esp=3.0,
               anc_a=20, anc_FS=1.5, anc_ds=25, anc_fy=500)
CRITERIOS_CF = {**CRITERIOS_GEO5, "FSt_min": 2.0, "FSd_min": 1.5, "qult_inf": 150,
                "laje_cf": "Coeficientes do GEO5 (planilha)"}


@pytest.fixture(scope="module")
def geo5_cf():
    return calcular(Entrada(**MURO_CF, **CRITERIOS_CF))


def test_contrafortes_estabilidade(geo5_cf):
    emp, F, v = geo5_cf.fase1.emp, geo5_cf.fase1.forcas, geo5_cf.fase1.verif
    assert emp.p_Pah_s == pytest.approx(16.71, abs=0.01)
    assert emp.p_Pah_q == pytest.approx(7.88, abs=0.01)
    assert emp.p_Pav == pytest.approx(2.95 + 1.71, abs=0.01)
    assert F.anc.anc_Tp == pytest.approx(134.04, abs=0.01)
    assert F.F_N == pytest.approx(75.75, abs=0.02)               # peso dos contrafortes fora, como no GEO5
    assert F.F_Mres == pytest.approx(45.56, abs=0.02)
    assert F.F_Movr == pytest.approx(22.97, abs=0.02)
    assert v.R_FSt == pytest.approx(1.98, abs=0.006)
    assert v.R_Hres == pytest.approx(46.72, abs=0.02)
    assert v.R_Hact == pytest.approx(22.80, abs=0.01)
    assert v.R_FSd == pytest.approx(2.05, abs=0.006)
    assert v.R_eB == pytest.approx(0.202, abs=0.0006)
    assert v.R_sef == pytest.approx(127.03, abs=0.1)
    assert v.R_FScc == pytest.approx(1.18, abs=0.006)
    assert not v.ok_tomb and v.ok_desl and v.ok_exc and not v.ok_cap   # mesmo veredito do GEO5


def test_contrafortes_dimensionamento(geo5_cf):
    d = geo5_cf.dim.v
    assert d["cs_l"] == pytest.approx(2.25)
    assert d["cs_MRht"] == pytest.approx(66.56 / 3.0, rel=0.001)   # GEO5 dá o total em 3,00 m de altura
    assert d["cf_MRd"] == pytest.approx(607.62, rel=0.001)
    assert d["cf_VRd"] == pytest.approx(254.59, rel=0.001)
    assert d["bd_Ai"] * 100 == pytest.approx(818.5 / 0.8, rel=0.001)
    # cortina: mesmas fórmulas; o GEO5 não majora a parcela da sobrecarga (49,80 × 51,80 kPa na base)
    assert d["cs_sH"] == pytest.approx(49.80 + 0.4 * 5.0, rel=0.001)
    for chave, geo in (("cs_Mvt", 10.07), ("cs_Mvf", 2.52), ("cs_Mht", 34.68 / 3), ("cs_Mhf", 20.81 / 3),
                       ("cs_V", 30.83)):
        assert geo < d[chave] < 1.08 * geo, chave
    # contraforte: o GEO5 usa coeficiente 1,0 nas ações; o aplicativo aplica γf
    assert d["cf_MSd"] == pytest.approx(1.4 * 178.40, rel=0.003)
    assert d["cf_VSd"] == pytest.approx(1.4 * 156.78, rel=0.006)
    # base entre contrafortes — diferença CONTRA a segurança, pendente de decisão: o GEO5 majora só o
    # empuxo (pesos e ancoragem com 1,0), a excentricidade cresce e a tensão sobe para 269,24 kPa
    assert d["bd_s"] == pytest.approx(224.08, abs=0.05) and d["bd_s"] < 269.24
