"""Modelo de entrada, soluções analíticas, invariantes físicos e NBR 6118."""
import math

import numpy as np

import pytest
from hypothesis import given, settings
from hypothesis import strategies as st
from pydantic import ValidationError

from core.concreto import criar_concreto
from core.fases import calcular, travamento_minimo_exato
from core.models import Entrada


# ------------------------------------------------------------------ modelo
def test_padrao_e_o_exemplo_da_planilha():
    e = Entrada()
    assert (e.H_muro, e.b_talao, e.phi_at, e.FSt_min) == (4.0, 1.85, 30.0, 2.0)
    assert e.delta_dv is None and e.resolvida().delta_dv == 30.0
    assert e.resolvida().gw_f == e.gf_f


def test_ida_e_volta_formato_planilha_e_json():
    e = Entrada(cf_usar=True, metodo_emp="Rankine", hw_at=1.5, cf_peso=True)
    p = e.para_planilha()
    assert p["cf_usar"] == "Sim" and p["anc_usar"] == "Não" and p["cf_peso"] == "Sim"
    assert Entrada.da_planilha(p) == e.resolvida()
    assert Entrada(**e.model_dump(mode="json")) == e


@pytest.mark.parametrize("mud", [dict(h_sap=5.0), dict(beta_t=35), dict(phi_at=0), dict(metodo_emp="Bishop"),
                                 dict(H_muro=-1), dict(campo_inexistente=1)])
def test_entradas_invalidas_sao_recusadas(mud):
    with pytest.raises(ValidationError):
        Entrada(**mud)


def test_opcoes_legadas_sao_sinalizadas():
    assert Entrada().opcoes_legadas_ativas() == []
    e = Entrada(peso_na="Submerso (GEO5)", bef_desl="Como GEO5", xd_lim="0,259 (GEO5)")
    assert len(e.opcoes_legadas_ativas()) == 3


# ------------------------------------------------------- soluções analíticas
def test_rankine_fechado_dorso_virtual():
    """c = 0, β = 0, dorso virtual vertical: Pa = Ka·γ·H²/2 + Ka·q·H, aplicado conforme o diagrama."""
    e = Entrada(metodo_emp="Rankine", modo_cunha="Vertical")
    r = calcular(e)
    Ka = math.tan(math.radians(45 - e.phi_at / 2)) ** 2
    H = e.H_muro
    Ps, Pq = Ka * e.gam_at * H**2 / 2, Ka * e.q_sc * H
    emp = r.fase1.emp
    assert emp.p_Pah == pytest.approx(Ps + Pq, rel=1e-12)
    assert emp.p_Pav == pytest.approx(0, abs=1e-12)
    # braço de alavanca: regra do ponto médio (40 + 20 fatias) → erro ~2e-4
    assert emp.p_zPa == pytest.approx((Ps * H / 3 + Pq * H / 2) / (Ps + Pq), rel=5e-4)
    fino = calcular(e, fatias=(4000, 1, 2000)).fase1.emp.p_zPa
    assert fino == pytest.approx((Ps * H / 3 + Pq * H / 2) / (Ps + Pq), rel=1e-7)


def test_repouso_na_fase_2():
    e = Entrada(trav_usar=True, modo_cunha="Vertical")
    emp = calcular(e).fase2.emp
    K0 = 1 - math.sin(math.radians(e.phi_at))
    assert emp.p_Pah == pytest.approx(K0 * (e.gam_at * e.H_muro**2 / 2 + e.q_sc * e.H_muro), rel=1e-12)
    assert emp.p_Pav == 0


def test_hidrostatica_e_subpressao():
    e = Entrada(hw_at=2.0, hw_fr=1.0)
    emp = calcular(e).fase1.emp
    assert emp.p_U == pytest.approx(0.5 * 10 * 2.0**2)
    assert emp.p_Usub == pytest.approx((10 * 1.0 + 10 * 2.0) / 2 * 3.0)


def test_convergencia_da_integracao():
    e = Entrada(c_at=8, beta_t=10, metodo_emp="Rankine", hw_at=1.5)
    a = calcular(e).fase1.emp.p_Pah
    b = calcular(e, fatias=(400, 400, 200)).fase1.emp.p_Pah
    assert a == pytest.approx(b, rel=5e-3)


def test_vesic_fatores():
    cap = calcular(Entrada(phi_f=30)).fase1.verif.cap
    assert cap.CC_Nq == pytest.approx(18.40, abs=0.01)
    assert cap.CC_Nc == pytest.approx(30.14, abs=0.01)
    assert cap.CC_Ng == pytest.approx(22.40, abs=0.01)


def test_equilibrio_das_tensoes_na_base():
    v = calcular(Entrada()).fase1
    B = 3.0
    assert (v.verif.sig_max + v.verif.sig_min) / 2 * B == pytest.approx(v.forcas.F_N)
    assert v.verif.R_sef * v.verif.R_Bef == pytest.approx(v.forcas.F_N)


# ---------------------------------------------------------------- travamento
def test_travamento_minimo_exato_atende_os_fs():
    e = Entrada(trav_usar=True, k_c=0.5)
    t = travamento_minimo_exato(e)
    v = t.resultado.fase2.verif
    assert v.R_FSt >= e.FSt_min - 1e-6 and v.R_FSd >= e.FSd_min - 1e-3
    pouco_menos = calcular(e.com(trav_F=t.F_min - 0.05)).fase2.verif
    assert pouco_menos.R_FSd < e.FSd_min or pouco_menos.R_FSt < e.FSt_min


def test_travamento_exato_coincide_com_a_planilha_sem_adesao():
    """Sem adesão (kc = 0) B' não entra na resistência e a estimativa da planilha é exata."""
    e = Entrada(trav_usar=True, k_c=0.0)
    est = calcular(e).trav.TR_Fd
    assert travamento_minimo_exato(e).F_desl == pytest.approx(est, abs=2e-3)


# ---------------------------------------------------------------- invariantes
muros = st.fixed_dictionaries(dict(
    H_muro=st.floats(2.0, 7.0), b_talao=st.floats(0.0, 4.0), b_ponta=st.floats(0.0, 2.0),
    q_sc=st.floats(0, 40), phi_at=st.floats(22, 40), c_at=st.floats(0, 15), beta_t=st.floats(0, 20),
    hw_at=st.floats(0, 2.0), metodo_emp=st.sampled_from(["Rankine", "Coulomb"]),
    modo_cunha=st.sampled_from(["Inclinada (GEO5)", "Vertical"])))


@settings(max_examples=150, deadline=None)
@given(muros)
def test_invariantes_fisicos(d):
    e = Entrada(**d)
    r = calcular(e)
    f, v = r.fase1, r.fase1.verif
    assert f.emp.p_Pah >= 0 and f.emp.p_Pa >= f.emp.p_Pah - 1e-9
    assert 0 <= v.R_Bef <= r.geo.B_base + 1e-12
    assert v.sig_min >= 0 and v.sig_max >= v.sig_min
    assert f.forcas.F_Movr >= 0
    assert 0 <= v.cap.CC_iq <= 1 and 0 <= v.cap.CC_ig <= 1
    # mais sobrecarga nunca reduz o empuxo horizontal
    mais_q = calcular(e.com(q_sc=e.q_sc + 10)).fase1.emp.p_Pah
    assert mais_q >= f.emp.p_Pah - 1e-9
    # refinamento da malha não muda o resultado de forma relevante
    fino = calcular(e, fatias=(200, 200, 100)).fase1.emp.p_Pah
    assert fino == pytest.approx(f.emp.p_Pah, rel=0.02, abs=0.05)


# ------------------------------------------------------------------ NBR 6118
def test_concreto_ate_c40_igual_a_planilha():
    c = criar_concreto(25, 500, 1.4, 1.15)
    assert (c.k_bloco, c.k_meio, c.lam, c.rho_min) == (0.68, 0.425, 0.8, 0.0015)
    assert c.fctm == pytest.approx(0.3 * 25 ** (2 / 3))
    assert not c.desvio_planilha


def test_as_necessaria_fecha_o_equilibrio():
    c = criar_concreto(30, 500, 1.4, 1.15)
    As = c.as_nec(120.0, 0.30)
    assert c.mrd(As, 0.30) == pytest.approx(120.0, rel=1e-9)
    assert c.as_nec(0, 0.3) == 0 and c.as_nec(1e6, 0.3) == -1


@pytest.mark.parametrize("fck,rho", [(20, 0.0015), (30, 0.0015), (35, 0.00164), (40, 0.00179), (45, 0.00194),
                                     (50, 0.00208), (60, 0.00219), (90, 0.00256)])
def test_rho_min_tabela_17_3(fck, rho):
    assert criar_concreto(fck, 500, 1.4, 1.15).rho_min == rho


def test_fck_acima_de_40_segue_a_nbr_e_nao_a_planilha():
    c45, c70 = criar_concreto(45, 500, 1.4, 1.15), criar_concreto(70, 500, 1.4, 1.15)
    assert c45.desvio_planilha and c45.k_bloco == pytest.approx(0.68 * (40 / 45) ** (1 / 3))
    assert c70.lam == pytest.approx(0.75) and c70.xd_lim_nbr == 0.35
    assert c70.fctm == pytest.approx(2.12 * math.log(1 + 0.11 * 70))
    # menos resistência que a fórmula da planilha → mais armadura
    planilha = 0.68 * (45 / 1.4) * 1000 * 1.25 * (0.3 - math.sqrt(0.3**2 - 150 / (0.425 * 45 / 1.4 * 1000))) \
        / (500 / 1.15 * 1000) * 10000
    assert c45.as_nec(150, 0.3) > planilha
    assert any("fck" in n for n in calcular(Entrada(fck_c=45)).dim.notas)


def test_verificacao_extra_do_cortante_no_talao():
    r = calcular(Entrada())
    extra = r.dim.extras[0]
    assert "Talão" in extra.nome and extra.extra and extra.situacao in ("OK", "NÃO OK")
    assert extra.solicitante == pytest.approx(r.dim.v["dm_VSd_tl"])


# ------------------------------------------------- padrões de 16/11/2026 e faixa de excentricidade
def test_padroes_do_aplicativo():
    e = Entrada()
    assert e.k_phi == 0.75 and e.k_c == 0.5 and e.ff_tipo == "Em repouso"
    v = calcular(e).fase1.verif
    assert v.delta_b == pytest.approx(0.75 * e.phi_f)
    assert v.adesao == pytest.approx(0.5 * e.c_f)
    assert v.Hres_externas > 0                                # solo da frente em repouso, somado à resistência


def test_alfa_da_adesao_por_tipo_de_solo():
    from core import solos
    for tipo in ("Areia", "Silte", "Silte arenoso", "Areia siltosa"):       # coesão aparente
        assert solos.sugerir(tipo, 12).alfa == 0.0
    for tipo in ("Areia argilosa", "Silte argiloso", "Argila arenosa"):
        assert solos.sugerir(tipo, 12).alfa == 0.5
    assert solos.sugerir("Argila", 6).alfa == pytest.approx(2 / 3)          # média
    assert solos.sugerir("Argila", 12).alfa == 0.5                          # rija
    assert all(0.0 <= solos.sugerir(t, n).alfa <= 2 / 3 + 1e-12 for t in solos.TIPOS for n in (1, 5, 10, 20, 40))
    # não drenado: razão adesão/Su do NAVFAC DM-7.2, decrescente com a consistência
    assert solos.alfa_nao_drenado(10) == 1.0 and solos.alfa_nao_drenado(24) == 1.0
    assert solos.alfa_nao_drenado(48) == pytest.approx(0.75)
    assert solos.alfa_nao_drenado(72) == pytest.approx(0.61)
    assert solos.alfa_nao_drenado(500) == pytest.approx(0.32)
    assert solos.sugerir("Argila", 6, nao_drenado=True).alfa == pytest.approx(solos.alfa_nao_drenado(60))


_FAIXA = dict(b_talao=0.8, cc_modo="Informada", qult_inf=2000)             # e/B = 0,22


def test_excentricidade_entre_B6_e_B4_exige_verificacao_da_base():
    r = calcular(Entrada(**_FAIXA))
    v, d = r.fase1.verif, r.dim.v
    assert 1 / 6 < v.R_eB < 0.25
    assert not v.ok_exc and v.exc_faixa and v.exc_aceita
    assert v.frac_comp == pytest.approx(3 * (0.5 - v.R_eB)) and v.frac_comp >= 0.75
    desc = [c for c in r.dim.extras if "descolamento" in c.nome]
    assert len(desc) == 5 and all(c.situacao == "OK" for c in desc)
    assert d["ex_Lcomp"] + d["ex_Ldesc"] == pytest.approx(r.geo.B_base)
    # ponta: solução fechada do balanço sob a distribuição triangular menos o peso próprio
    B, a, e = r.geo.B_base, r.entrada.b_ponta, r.entrada
    Lc, smax = d["ex_Lcomp"], v.sig_max
    assert smax == pytest.approx(2 * r.fase1.forcas.F_N / Lc)
    sa = smax * (1 - a / Lc)
    M = sa * a**2 / 2 + (smax - sa) * a**2 / 3 - e.gam_c * e.h_sap * a**2 / 2
    gf = e.gf_f
    assert d["ex_MSd_pt"] >= gf * M * (1 - 2e-3)                      # envoltória: nunca abaixo de γf × serviço
    assert d["ex_MSd_pt"] == pytest.approx(max(gf * M, d["ex_MSd_pt"]))
    assert d["ex_face_pt"] == "inferior" and d["ex_face_tl"] == "superior"
    assert d["ex_dAs_pt"] == 0.0 and d["ex_dAs_tl"] == 0.0 and r.dim.atende


def test_excentricidade_na_faixa_com_armadura_insuficiente_reprova():
    r = calcular(Entrada(**_FAIXA, ar_bi_phi=5.0, ar_bi_s=20.0, ar_bs_phi=5.0, ar_bs_s=20.0))
    d = r.dim.v
    assert r.fase1.verif.exc_faixa and not r.dim.atende and not r.atende
    assert d["ex_dAs_pt"] == pytest.approx(d["ex_As_pt"] - d["dm_Abi"]) and d["ex_dAs_pt"] > 0
    assert d["ex_dAs_tl"] == pytest.approx(d["ex_As_tl"] - d["dm_Abs"]) and d["ex_dAs_tl"] > 0
    assert any("faltam" in n for n in r.dim.notas)


def test_excentricidade_fora_da_faixa():
    dentro = calcular(Entrada(b_talao=1.2)).fase1.verif                     # e/B < 1/6
    assert dentro.ok_exc and not dentro.exc_faixa and dentro.frac_comp == 1.0
    acima = calcular(Entrada(b_talao=0.7)).fase1.verif                      # e/B > 1/4
    assert acima.R_eB > 0.25 and not acima.ok_exc and not acima.exc_faixa and not acima.exc_aceita
    geo5 = calcular(Entrada(b_talao=0.8, eB_lim=0.333)).fase1.verif         # limite já acima de B/4
    assert geo5.ok_exc and not geo5.exc_faixa


def test_estudo_de_solo_preenche_alfa():
    from core.perfil import Estrato, equivalente
    a = Estrato(0, 1, "Argila", 6, 17, 19, 22, 6.0, 14, False, 2 / 3)
    b = Estrato(1, 3, "Areia", 12, 18, 20, 32, 0.0, 22, False, 0.0)
    eq = equivalente((a, b))
    assert eq.alfa * eq.c == pytest.approx((2 / 3 * 6.0 * 1 + 0) / 3)        # preserva a adesão média


# ------------------------------------------------ cargas em faixa, em linha e concentrada (Boussinesq)
def _z(H, n=4000):
    return (np.arange(n) + 0.5) * H / n


def test_boussinesq_linha_resultante_de_terzaghi():
    """Resultantes clássicas: 0,64·Q/(m² + 1) para m > 0,4 e 0,55·Q para m ≤ 0,4 (NAVFAC DM-7.2)."""
    from core import boussinesq as bq
    H, Q = 5.0, 80.0
    for x in (2.5, 4.0, 7.5):
        m = x / H
        P = bq.s_linha(_z(H), Q, x, H).sum() * H / 4000
        assert P == pytest.approx(2 / math.pi * Q / (m**2 + 1), rel=1e-4)
    for x in (0.0, 1.0, 2.0):
        assert bq.s_linha(_z(H), Q, x, H).sum() * H / 4000 == pytest.approx(0.549 * Q, rel=2e-3)
    assert bq.s_linha(_z(H), Q, 3.0, H, 0.5).sum() == pytest.approx(0.5 * bq.s_linha(_z(H), Q, 3.0, H).sum())


def test_boussinesq_faixa():
    from core import boussinesq as bq
    z = _z(4.0)
    # faixa muito larga encostada no muro: metade de q na solução elástica, q na parede rígida
    assert bq.s_faixa(z, 10.0, 0.0, 1e6, 0.5) == pytest.approx(np.full_like(z, 5.0), rel=1e-4)
    assert bq.s_faixa(z, 10.0, 0.0, 1e6) == pytest.approx(np.full_like(z, 10.0), rel=1e-4)
    # superposição: duas faixas contíguas = uma faixa com a largura somada
    assert bq.s_faixa(z, 10, 1, 1) + bq.s_faixa(z, 10, 2, 2) == pytest.approx(bq.s_faixa(z, 10, 1, 3))
    # faixa estreita tende à carga em linha (m > 0,4)
    assert bq.s_faixa(z, 1000.0, 2.995, 0.01) == pytest.approx(bq.s_linha(z, 10.0, 3.0, 4.0), rel=1e-3)
    assert (bq.s_faixa(z, 10, 1, 2) >= 0).all()


def test_boussinesq_ponto():
    from core import boussinesq as bq
    H, P, z = 4.0, 100.0, _z(4.0)
    assert bq.fator_planta(3.0, 0.01) == pytest.approx(1.0, abs=1e-4)          # seção em frente à carga
    assert bq.fator_planta(3.0, 6.0) < bq.fator_planta(3.0, 3.0) < 1.0          # média cai com o comprimento
    pico = bq.s_ponto(z, P, 2.0, H, 0.01)
    n = z / H
    assert pico == pytest.approx(1.77 * P / H**2 * 0.25 * n**2 / (0.25 + n**2) ** 3, rel=1e-3)
    assert bq.s_ponto(z, P, 0.5, H, 3.0) == pytest.approx(bq.s_ponto(z, P, 1.6, H, 3.0))   # m ≤ 0,4: independe de m


def test_cargas_concentradas_entram_na_estabilidade_e_na_cortina():
    base = calcular(Entrada())
    r = calcular(Entrada(sc_ln_Q=50.0, sc_ln_x=3.0))
    c, F, F0 = r.fase1.forcas.conc, r.fase1.forcas, base.fase1.forcas
    assert not F0.conc.ativo and len(F0.linhas) == 17 and len(F.linhas) == 18
    assert c.Fh == pytest.approx(0.549 * 50.0, rel=3e-3)                       # 3,0 − talão 1,85 → m < 0,4
    assert c.zF == pytest.approx(0.6 * c.H_est, abs=0.05)                      # resultante a ~0,6·H
    assert F.F_Hact == pytest.approx(F0.F_Hact + c.Fh)
    assert F.F_Movr == pytest.approx(F0.F_Movr + c.Fh * c.zF)
    assert F.F_N == pytest.approx(F0.F_N)                                      # sem componente vertical
    assert r.fase1.verif.R_FSd < base.fase1.verif.R_FSd and r.fase1.verif.R_FSt < base.fase1.verif.R_FSt
    # cortina: momento na base aumenta do momento das pressões no tardoz (γf)
    e, g = r.entrada, r.geo
    y = r.dim.fatias["y"]
    dM = (r.dim.fatias["sh_concentradas"] * (y - e.h_sap)).sum() * g.h_cort / len(y)
    assert dM > 0
    assert r.dim.v["dm_MSdp"] == pytest.approx(base.dim.v["dm_MSdp"] + e.gf_f * dM, rel=1e-9)
    flex = calcular(Entrada(sc_ln_Q=50.0, sc_ln_x=3.0, sc_bq="Parede que se desloca (×1 — Boussinesq)"))
    assert flex.fase1.forcas.conc.Fh == pytest.approx(c.Fh / 2)


def test_cargas_sobre_o_talao():
    e = Entrada(sc_fx_q=20.0, sc_fx_a=1.0, sc_fx_b=2.0, sc_pt_P=90.0, sc_pt_x=0.5, sc_pt_L=3.0)
    r = calcular(e)
    c = r.fase1.forcas.conc
    talao = r.geo.B_base - r.geo.x_bt
    assert c.W_talao == pytest.approx(20.0 * (talao - 1.0) + 90.0 / 3.0)
    assert len(r.fase1.forcas.linhas) == 18                                    # peso não entra por padrão
    r2 = calcular(e.com(q_estab=True))
    assert len(r2.fase1.forcas.linhas) == 19
    sem = calcular(e.com(sc_fx_q=0.0, sc_pt_P=0.0))
    sem2 = calcular(e.com(sc_fx_q=0.0, sc_pt_P=0.0, q_estab=True))
    assert r2.fase1.forcas.F_N == pytest.approx(sem2.fase1.forcas.F_N + c.W_talao, rel=1e-9)
    # o talão é dimensionado com o peso das cargas que estão sobre ele
    assert r.dim.base["carga_talao"].max() == pytest.approx(sem.dim.base["carga_talao"].max() + c.W_talao / e.b_talao)


def test_cargas_concentradas_na_interface_e_no_memorial():
    from io_ import memorial
    from ui import graficos
    import matplotlib.pyplot as plt
    r = calcular(Entrada(sc_fx_q=20.0, sc_ln_Q=30.0, sc_ln_x=2.5, sc_pt_P=100.0, sc_pt_x=9.0))
    for fig in (graficos.croqui(r, 1), graficos.grafico_concentradas(r)):
        plt.close(fig)
    assert memorial.gerar_pdf(r, {"nome": "teste"})[:4] == b"%PDF"
    assert any("Boussinesq" in n for n in r.dim.notas)


# ------------------------------------- base: envoltória com a combinação de ações favoráveis em 1,0
def test_base_usa_a_envoltoria_das_duas_combinacoes():
    r = calcular(Entrada(b_talao=0.0, b_ponta=2.2, ponta_mod="Pressões na base"))
    d, gf = r.dim.v, r.entrada.gf_f
    assert d["dm_fav_gov"] and any("combinações de ações" in n for n in r.dim.notas)
    assert d["dm_MSd_pt_fav"] > gf * d["dm_MtP1"]                    # só o empuxo majorado supera γf × serviço
    assert d["dm_MSd_pt"] == pytest.approx(d["dm_MSd_pt_comb"]) and d["dm_MSd_pt"] >= d["dm_MSd_pt_fav"]
    assert d["dm_VSd_pt"] == pytest.approx(max(gf * d["dm_VtP"], d["dm_VSd_pt_comb"]))
    # N e excentricidade de cálculo: só o empuxo com γf
    F = r.fase1.forcas
    emp_v = sum(f.Fz for f in F.linhas if f.nome.startswith("Empuxo —"))
    assert d["dm_N_fav"] == pytest.approx(F.F_N + (gf - 1) * emp_v)
    assert abs(d["dm_e_fav"]) > abs(r.fase1.verif.R_e)               # excentricidade maior que a de serviço
    # exemplo padrão: entre as combinações em equilíbrio governa γf × serviço (todas as ações com γf)
    p = calcular(Entrada()).dim.v
    assert p["dm_MSd_tl_eq"] == pytest.approx(gf * p["dm_Mtt"], rel=1e-6)
    assert p["dm_MSd_pt_eq"] == pytest.approx(gf * p["dm_MtP1"], rel=1e-6)


def test_base_pior_caso_de_todas_as_combinacoes():
    """Cada grupo de ações com 1,0 ou γf; reação de serviço com 1,0 ou γf; vale o pior caso."""
    r = calcular(Entrada())
    d, e, g = r.dim.v, r.entrada, r.geo
    gf = e.gf_f
    assert d["dm_n_comb"] == 12                                      # 4 em equilíbrio (sem água) + 8 locais
    assert calcular(Entrada(hw_at=1.5)).dim.v["dm_n_comb"] == 16     # com água: 8 + 8
    # talão: pior caso = pesos e empuxo vertical com γf contra a reação de serviço com 1,0
    b = r.dim.base
    tal = b["zona"] == "Talão"
    dx = g.B_base / len(b["x"])
    braco = b["x"] - g.x_tb
    emp = r.fase1.emp
    pesos = ((b["peso"] + b["carga_talao"]) * braco)[tal].sum() * dx
    reacao = ((b["sig1"] + b["u"]) * braco)[tal].sum() * dx
    pav = emp.p_Pav * (emp.p_xPav - g.x_tb)
    assert d["dm_MSd_tl"] == pytest.approx(gf * pesos + gf * pav - reacao, rel=1e-9)
    assert d["dm_MSd_tl"] > d["dm_MSd_tl_eq"] > 0
    # ponta: pior caso = reação com γf contra o peso próprio com 1,0
    pt = b["zona"] == "Ponta"
    bp = g.x_fb - b["x"]
    assert d["dm_MSd_pt_comb"] == pytest.approx(((gf * (b["sig1"] + b["u"]) - b["peso"]) * bp)[pt].sum() * dx, rel=1e-9)
    # nunca abaixo de γf × serviço
    assert d["dm_MSd_tl"] >= gf * d["dm_Mtt"] and d["dm_VSd_tl"] >= gf * d["dm_VtT"]
    assert d["dm_MSd_pt"] >= gf * d["dm_MtP1"] and d["dm_VSd_pt"] >= gf * d["dm_VtP"]


def test_equilibrio_do_no_cortina_sapata():
    """A ponta absorve o momento da cortina que o talão não absorve (modo 'Máximo')."""
    from tests.test_geo5 import CRITERIOS_TALAO, MURO_TALAO
    r = calcular(Entrada(**MURO_TALAO, **{**CRITERIOS_TALAO, "ponta_mod": "Máximo"}))
    d = r.dim.v
    assert d["dm_no_gov"] and any("equilíbrio do nó" in n for n in r.dim.notas)
    assert d["dm_MSd_pt"] == pytest.approx(d["dm_MSdp"] - d["dm_MSd_tl"], rel=1e-6)
    assert d["dm_MSd_pt"] + d["dm_MSd_tl"] == pytest.approx(94.35, rel=0.002)   # = haste do GEO5 (67,68 + 26,68)
    assert d["dm_MSd_pt"] > 67.68                                               # ponta acima da do GEO5
    # sem talão a regra é a da planilha: ponta = cortina
    s = calcular(Entrada(b_talao=0.0, b_ponta=1.5)).dim.v
    assert s["dm_MSd_pt"] >= s["dm_MSdp"] - 1e-9 and not s["dm_no_gov"]
    # com contrafortes a base é laje: a regra do nó não se aplica ao balanço
    assert calcular(Entrada(cf_usar=True)).dim.v["dm_M_no"] == 0.0


def test_combinacao_favoravel_reproduz_o_cortante_da_ponta_do_geo5():
    from tests.test_geo5 import CRITERIOS_ANC, CRITERIOS_GEO5, MURO, MURO_ANC
    d1 = calcular(Entrada(**MURO, **CRITERIOS_GEO5)).dim.v
    d2 = calcular(Entrada(**MURO_ANC, **CRITERIOS_ANC)).dim.v
    assert d1["dm_VSd_pt_fav"] == pytest.approx(23.00, rel=0.02)      # memorial de 13/11/2026
    assert d2["dm_VSd_pt_fav"] == pytest.approx(46.01, rel=0.02)      # memorial de 16/11/2026
