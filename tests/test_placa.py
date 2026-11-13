"""Solver de placa, laje com borda livre no muro com contrafortes, blocos e desenho das armaduras."""
import matplotlib.pyplot as plt
import numpy as np
import pytest

from core.fases import calcular
from core.models import Entrada
from core.placa import APOIO as A
from core.placa import ENGASTE as E
from core.placa import LIVRE as L
from core.placa import classificar, resolver
from core.planilha import MODO_PLANILHA
from ui import armacao, graficos

Q = 10.0


def _uniforme(n=14):
    return tuple([Q] * (n + 1))


# ------------------------------------------------------- soluções clássicas (Timoshenko)
def test_placa_quadrada_engastada():
    p = resolver(1.0, 1.0, _uniforme(), (E, E, E, E), 14, 0.3)
    assert p.Mx[7, 7] / Q == pytest.approx(0.0231, abs=0.0005)        # centro
    assert p.Mx[7, 0] / Q == pytest.approx(-0.0513, abs=0.0008)       # meio da borda
    assert np.nanmax(p.Vx0) / Q == pytest.approx(0.441, abs=0.005)    # cortante máximo na borda
    assert p.reacao_total == pytest.approx(p.carga_total, rel=1e-9)


def test_placa_quadrada_apoiada():
    p = resolver(1.0, 1.0, _uniforme(), (A, A, A, A), 14, 0.3)
    assert p.Mx[7, 7] / Q == pytest.approx(0.0479, abs=0.0006)
    assert p.My[7, 7] == pytest.approx(p.Mx[7, 7], rel=1e-9)          # simetria


def test_borda_livre_painel_largo_vira_balanco():
    """Vão muito maior que a altura: no meio, balanço vertical engastado na base."""
    p = resolver(20.0, 1.0, _uniforme(), (E, E, E, L))
    assert p.My[0, 7] / Q == pytest.approx(-0.5, abs=0.003)           # p·h²/2
    tri = tuple(Q * (1 - j / 14) for j in range(15))
    p = resolver(20.0, 1.0, tri, (E, E, E, L))
    assert p.My[0, 7] / Q == pytest.approx(-1 / 6, abs=0.002)         # p·h²/6
    assert np.nanmax(p.Vy0) / Q == pytest.approx(0.5, abs=0.01)       # p·h/2


def test_borda_livre_painel_alto_vira_viga_entre_contrafortes():
    p = resolver(1.0, 20.0, _uniforme(40), (E, E, E, L))
    meio = 30                                                         # longe da base e do topo
    assert p.Mx[meio, 0] / Q == pytest.approx(-1 / 12, abs=0.002)     # p·l²/12
    assert p.Mx[meio, 7] / Q == pytest.approx(1 / 24, abs=0.002)      # p·l²/24
    assert p.Vx0[meio] / Q == pytest.approx(0.5, abs=0.01)            # p·l/2


def test_convergencia_e_equilibrio_do_painel_tipico():
    def caso(n):
        tri = tuple(40 * (1 - j / n) for j in range(n + 1))
        return resolver(2.75, 3.6, tri, (E, E, E, L), n)
    a, b = caso(14), caso(28)
    assert a.reacao_total == pytest.approx(a.carga_total, rel=1e-9)
    assert -a.Mx[:, 0].min() == pytest.approx(-b.Mx[:, 0].min(), rel=0.02)
    assert -a.My[0].min() == pytest.approx(-b.My[0].min(), rel=0.03)
    assert a.Mx.max() == pytest.approx(b.Mx.max(), rel=0.03)


def test_classificacao_do_painel():
    assert "duas direções" in classificar(2.75, 3.6)[1]
    assert "horizontal" in classificar(1.5, 4.0)[1]
    assert "balanço" in classificar(6.0, 2.5)[1]


# ---------------------------------------------------------- muro com contrafortes
def test_contrafortes_placa_e_o_padrao_e_da_momentos_nas_duas_direcoes():
    r = calcular(Entrada(cf_usar=True))
    pc = r.dim.placas["cortina"]
    assert min(pc["Mht"], pc["Mhf"], pc["Mvt"], pc["Mvf"]) > 0          # duas direções, duas faces
    v = r.dim.v
    # mesma ordem de grandeza dos coeficientes do GEO5, sem ser igual
    assert 0.5 * v["cs_Mht"] < pc["Mht"] < 1.5 * v["cs_Mht"]
    assert 0.5 * v["cs_Mvt"] < pc["Mvt"] < 1.5 * v["cs_Mvt"]
    assert r.dim.checks[7].solicitante == pc["Asht"] and r.dim.checks[0].solicitante == pc["Asvt"]
    assert any("transversal na junção" in x.nome for x in r.dim.extras)
    assert any("borda superior livre" in n for n in r.dim.notas)


def test_contrafortes_modo_planilha_mantem_os_coeficientes_do_geo5():
    r = calcular(Entrada(cf_usar=True, **MODO_PLANILHA))
    assert not r.dim.placas
    assert r.dim.checks[7].solicitante == r.dim.v["cs_Asht"]
    assert len(Entrada(cf_usar=True, **MODO_PLANILHA).opcoes_legadas_ativas()) == 1


def test_contraforte_na_frente_carrega_a_ponta_por_baixo():
    r = calcular(Entrada(cf_usar=True, cf_tipo="Na frente (sobre a ponta)", cf_Lb=0.8))
    pb = r.dim.placas["base"]
    assert pb["b"] == 0.8 and pb["Mi"] == pb["M_sup"] and pb["Ms"] == pb["M_vao"]   # apoios tracionam embaixo
    atras = calcular(Entrada(cf_usar=True)).dim.placas["base"]
    assert atras["Ms"] == atras["M_sup"]                                           # talão: apoios tracionam em cima


def test_muro_sem_contrafortes_nao_muda():
    a, b = calcular(Entrada()), calcular(Entrada(**MODO_PLANILHA))
    assert [c.solicitante for c in a.dim.checks] == [c.solicitante for c in b.dim.checks]


# ------------------------------------------------------------------------- blocos
def test_bloco_alinhado_ao_tardoz_e_o_padrao():
    e = Entrada(bl_usar=True, anc_usar=True)
    r = calcular(e)
    a = r.fase1.forcas.anc
    assert a.bl_xe + e.bl_B / 2 == pytest.approx(r.geo.x_tb)        # face do bloco no tardoz
    assert a.anc_xe == pytest.approx(a.bl_xe)                       # uma linha: estaca no eixo do bloco
    assert not r.fase1.avisos


def test_bloco_centrado_nas_estacas_e_posicao_informada():
    r = calcular(Entrada(bl_usar=True, anc_usar=True, **MODO_PLANILHA))
    assert r.fase1.forcas.anc.bl_xe == 0.4 == r.fase1.forcas.anc.anc_xe          # como na planilha
    r = calcular(Entrada(bl_usar=True, anc_usar=True, bl_pos="Posição informada", bl_x=1.5))
    assert r.fase1.forcas.anc.bl_xe == pytest.approx(1.9)
    duas = calcular(Entrada(bl_usar=True, anc_usar=True, anc_n2=1, anc_x=0.5, anc_x2=1.0, bl_B=1.2))
    a = duas.fase1.forcas.anc
    assert (a.anc_xe, a.bl_xe) == (0.5, pytest.approx(duas.geo.x_tb - 0.6))      # duas linhas: posições do projetista
    fora = calcular(Entrada(bl_usar=True, anc_usar=True, bl_B=2.0))
    assert any("Bloco ultrapassa" in x.texto for x in fora.fase1.avisos)


def test_campos_do_aplicativo_nao_vao_para_a_planilha():
    p = Entrada().para_planilha()
    assert "bl_pos" not in p and "laje_cf" not in p and len(p) == 108
    assert {"bl_pos", "bl_x", "laje_cf"} <= set(Entrada().para_planilha(so_app=True))


# ------------------------------------------------------------------------ desenho
@pytest.mark.parametrize("mud", [{}, dict(cf_usar=True), dict(cf_usar=True, cf_tipo="Na frente (sobre a ponta)"),
                                 dict(b_talao=0, b_ponta=2.2), dict(b_ponta=0, b_talao=2.6),
                                 dict(cf_usar=True, **MODO_PLANILHA)])
def test_desenho_e_quadro_de_ferros(mud):
    r = calcular(Entrada(**mud))
    ferros = armacao.quadro_de_ferros(r)
    assert [f.pos for f in ferros][:4] == ["N1", "N2", "N3", "N4"]
    assert len(ferros) == (9 if mud.get("cf_usar") else 8)
    assert all("ϕ" in f.descricao for f in ferros)
    assert len(armacao.tabela(ferros)) == len(ferros)
    fig = armacao.desenho(r)
    textos = " ".join(t.get_text() for t in fig.axes[0].texts)
    assert all(f.pos in textos for f in ferros)                     # toda posição tem indicação no desenho
    plt.close(fig)
    fig = armacao.diagrama_placa(r)
    assert (fig is not None) == bool(r.dim.placas)
    if fig is not None:
        plt.close(fig)


def test_quadro_marca_a_posicao_que_reprova():
    r = calcular(Entrada(ar_tz_phi=8, ar_tz_s=20))
    f = {x.pos: x for x in armacao.quadro_de_ferros(r)}
    assert f["N1"].ok is False and f["N2"].ok is True and f["N5"].sugerido
    assert not r.dim.atende


def test_croqui_com_bloco():
    fig = graficos.croqui(calcular(Entrada(bl_usar=True, anc_usar=True)), 1)
    assert fig.axes
    plt.close(fig)
