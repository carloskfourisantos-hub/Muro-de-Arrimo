"""Leitura de boletim de sondagem (PDF sintético), perfil → muro e esforço lateral."""
import math

import matplotlib.pyplot as plt
import pymupdf
import pytest
from streamlit.testing.v1 import AppTest

from core import perfil
from core.fases import calcular
from core.models import Entrada
from io_ import sondagem
from ui import graficos

PPM = 28.35   # pontos por metro (escala 1:100)
CAMADAS = [(0.60, "AT", "Argila siltosa, pouco arenosa, com entulhos, cor marrom."),
           (2.85, "S", "Argila siltosa, pouco arenosa, mole, cor amarela."),
           (6.80, "S", "Areia média argilosa, medianamente compacta, cor cinza."),
           (10.45, "S", "Argila arenosa, rija, cor vermelha.")]
GOLPES = [(1, 1, 1), (2, 2, 2), (2, 3, 3), (4, 6, 8), (4, 7, 8), (5, 7, 9), (6, 8, 9), (5, 7, 9), (6, 9, 11),
          (7, 10, 12)]


def _boletim(base_no_rodape: bool = True, texto: bool = True) -> bytes:
    """Boletim no estilo 'base da camada à esquerda da descrição', com o NSPT em INI./FIN."""
    doc = pymupdf.open()
    pg = doc.new_page(width=595, height=842)
    if not texto:
        pg.draw_rect(pymupdf.Rect(50, 50, 300, 300))
        return doc.tobytes()
    y0 = 150.0

    def t(x, y, s, tam=7):
        pg.insert_text((x, y), s, fontsize=tam)
    t(60, 30, "SONDAGEM DE SIMPLES RECONHECIMENTO DO SOLO COM SPT - NBR 6484/2020", 9)
    t(405, 45, "SONDAGEM À PERCUSSÃO:  SP 03")
    t(352, 100, "AMOSTRADOR BIPARTIDO:")              # mesma coluna das descrições, fora do corpo
    for k, (g1, g2, g3) in enumerate(GOLPES, 1):
        y = y0 + k * PPM
        t(133, y, f"{k},00")
        for x, g in zip((168, 188, 208), (g1, g2, g3)):
            t(x, y, str(g))
            t(x - 1, y + 7.7, "15")
        t(229, y + 3.8, str(g1 + g2))
        t(249, y + 3.8, str(g2 + g3))
    topo = 0.0
    for base, origem, desc in CAMADAS:
        t(318, y0 + base * PPM, f"{base:.2f}".replace(".", ","))
        t(268, y0 + base * PPM, origem)
        t(352, y0 + (topo + base) / 2 * PPM, desc)
        topo = base
    if base_no_rodape:
        t(483, 720, "N.A. LEITURAS:")
        t(483, 729, "1) 4,38m em 05/12/2024")
        t(483, 738, "2) 4,22m em 05/12/2024")
    return doc.tobytes()


def test_le_boletim_sintetico():
    leitura = sondagem.ler_pdf(_boletim())
    assert not leitura.avisos and len(leitura.furos) == 1
    f = leitura.furos[0]
    assert f.nome == "SP-03" and f.na == 4.22
    assert f.spt == tuple((float(k), g2 + g3) for k, (_, g2, g3) in enumerate(GOLPES, 1))
    assert [(c.topo, c.base) for c in f.camadas] == [(0.0, 0.6), (0.6, 2.85), (2.85, 6.8), (6.8, 10.45)]
    assert [c.tipo for c in f.camadas] == ["Argila siltosa", "Argila siltosa", "Areia argilosa", "Argila arenosa"]
    assert [c.aterro for c in f.camadas] == [True, False, False, False]
    assert f.camadas[2].nspt == pytest.approx((6 + 14 + 15 + 16) / 4)        # ensaios de 3 a 6 m
    assert not any("descrições" in a for a in f.avisos)


def test_pdf_sem_texto_e_pdf_invalido():
    leitura = sondagem.ler_pdf(_boletim(texto=False))
    assert not leitura.furos and "escaneado" in leitura.avisos[0]
    with pytest.raises(ValueError):
        sondagem.ler_pdf(b"isto nao e um pdf")


@pytest.mark.parametrize("desc,tipo,aterro", [
    ("Argila siltosa, pouco arenosa, rija, cor roxa.", "Argila siltosa", False),
    ("ARGILA POUCO ARENOSA, DE GRANULAÇÃO FINA, COR CINZA", "Argila", False),
    ("ARGILA SILTO-ARENOSA, COR AMARELA", "Argila siltosa", False),
    ("Areia média argilosa, compacta", "Areia argilosa", False),
    ("AREIA FINA A GROSSA, POUCO ARGILOSA", "Areia", False),
    ("Silte arenoso, compacto, cor variegada", "Silte arenoso", False),
    ("CAMADA DE ENTULHO SOBRE ARGILA POUCO ARENOSA", "Argila", True),
    ("Camada de concreto.", perfil.SEM_SOLO, False),
    ("CONCREÇÕES LIMONÍTICAS, CORES CINZA E ROXA", perfil.SEM_SOLO, False),
])
def test_classificacao_da_descricao(desc, tipo, aterro):
    assert perfil.classificar_descricao(desc) == (tipo, aterro)


def _furo():
    return sondagem.ler_pdf(_boletim()).furos[0]


def test_esforco_lateral_homogeneo_confere_com_rankine():
    e = perfil.Estrato(0, 4, "Areia", 15, 18.0, 19.0, 30.0, 0.0, 20.0)
    r = perfil.esforco_lateral((e,), 0.0, 4.0, q=10.0)
    Ka = math.tan(math.radians(30)) ** 2
    assert r.E_ativo == pytest.approx(Ka * 18 * 16 / 2 + Ka * 10 * 4, rel=1e-6)
    assert r.E_repouso == pytest.approx(0.5 * (18 * 16 / 2 + 10 * 4), rel=1e-6)
    assert r.z_ativo == pytest.approx((Ka * 144 * 4 / 3 + Ka * 40 * 2) / r.E_ativo, rel=1e-4)
    assert r.E_agua == 0
    com_agua = perfil.esforco_lateral((e,), 0.0, 4.0, na=2.0)
    assert com_agua.E_agua == pytest.approx(10 * 2**2 / 2, rel=1e-4)
    assert com_agua.E_ativo < perfil.esforco_lateral((e,), 0.0, 4.0).E_ativo      # γ' abaixo do NA


def test_proposta_preenche_o_muro():
    f = _furo()
    p = perfil.propor(f, 0.6, 4.6, largura_base=3.0, q=10.0)
    assert p.campos["H_muro"] == 4.0 and p.campos["hw_at"] == pytest.approx(0.38)      # NA 4,22 → 4,6 − 4,22
    assert [(e.topo, e.base) for e in p.arrimado] == [(0.6, 2.85), (2.85, 4.6)]
    assert all(e.c == 0 for e in p.arrimado)                                           # coesão desprezada
    assert p.fundacao[0].topo == 4.6 and p.fundacao_eq.phi > 20
    assert min(e.phi for e in p.arrimado) <= p.arrimado_eq.phi <= max(e.phi for e in p.arrimado)
    desf = perfil.propor(f, 0.6, 4.6, q=10.0, criterio=perfil.DESFAVORAVEL)
    assert desf.arrimado_eq.phi == min(e.phi for e in p.arrimado)
    assert desf.homogeneo.E_ativo >= p.por_camadas.E_ativo - 1e-9
    res = calcular(Entrada().com(**p.campos))                                          # forma um muro calculável
    assert res.geo.h_cort == pytest.approx(3.6)
    fig = graficos.grafico_esforco_lateral(f, p, 0.6, 4.6, 10.0)
    assert len(fig.axes) == 2
    plt.close(fig)


def test_trecho_com_aterro_e_sem_nspt_gera_avisos():
    f = _furo()
    p = perfil.propor(f, 0.0, 3.0)
    assert any("ATERRO" in a for a in p.avisos)
    sem = perfil.Furo("X", (perfil.Camada(0, 5, "Camada de concreto."),))
    vazio = perfil.propor(perfil.completar(sem), 0.0, 3.0)
    assert vazio.arrimado_eq is None and "gam_at" not in vazio.campos and vazio.avisos


def test_pagina_inicial_com_estudo_de_solo():
    from pathlib import Path
    at = AppTest.from_file(str(Path(__file__).resolve().parents[1] / "app.py"), default_timeout=60)
    at.session_state["sondagem"] = {"arquivo": "teste.pdf", "furos": [_furo()], "avisos": []}
    at.run()
    assert not at.exception, [e.value for e in at.exception]
    at.number_input(key="sond_zf_SP-03").set_value(4.0).run()
    assert not at.exception, [e.value for e in at.exception]
    next(b for b in at.button if b.label == "Preencher a verificação").click().run()
    assert not at.exception, [e.value for e in at.exception]
    d = at.session_state["dados"]
    assert d["H_muro"] == 4.0 and d["c_at"] == 0.0 and d["phi_at"] != 30.0
