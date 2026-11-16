"""Testes de fumaça das páginas Streamlit (sem navegador)."""
from pathlib import Path

import pytest
from streamlit.testing.v1 import AppTest

RAIZ = Path(__file__).resolve().parents[1]


def _pagina(nome: str) -> AppTest:
    at = AppTest.from_file(str(RAIZ / "app.py"), default_timeout=60)
    at.run()
    at.switch_page(f"paginas/{nome}.py")
    at.run()
    assert not at.exception, [e.value for e in at.exception]
    return at


def test_inicio():
    at = AppTest.from_file(str(RAIZ / "app.py"), default_timeout=60).run()
    assert not at.exception
    assert at.title[0].value == "Muro de arrimo"


def test_verificacao_padrao():
    at = _pagina("verificacao")
    texto = " ".join(m.value for m in at.markdown)
    assert "4,04" in texto and "1,53" in texto and "6,91" in texto      # FSt, FSd, FScc do exemplo
    assert "Estabilidade externa (NBR 11682): ATENDE" in texto
    # com o pior caso de todas as combinações o talão do exemplo pede 8,65 cm²/m e tem 8,18
    assert "Dimensionamento estrutural (NBR 6118): NÃO ATENDE" in texto


@pytest.mark.parametrize("secao", ["Forças", "Empuxo", "Geometria", "Capacidade de carga", "Ferramentas",
                                   "Premissas"])
def test_secoes_de_detalhamento(secao):
    at = _pagina("verificacao")
    at.session_state["secao"] = secao
    at.run()
    assert not at.exception, [e.value for e in at.exception]


def test_alterar_entrada_recalcula():
    from core.models import Entrada
    from core.solver import menor_valor
    talao, _ = menor_valor(Entrada(modo_cunha="Vertical"), "b_talao", 8.0)
    at = _pagina("verificacao")
    at.selectbox(key="w_modo_cunha").set_value("Vertical")
    at.number_input(key="w_b_talao").set_value(talao).run()
    texto = " ".join(m.value for m in at.markdown)
    assert not at.exception
    assert "Estabilidade externa (NBR 11682): ATENDE" in texto
    # talão longo com cunha inclinada: verificações OK, mas o aviso mantém "NÃO ATENDE" (como na planilha)
    at.selectbox(key="w_modo_cunha").set_value("Inclinada (GEO5)")
    at.number_input(key="w_b_talao").set_value(2.85).run()
    assert any("talão longo" in w.value for w in at.warning)
    assert "Estabilidade externa (NBR 11682): NÃO ATENDE" in " ".join(m.value for m in at.markdown)


def test_entrada_invalida_mostra_erro_em_vez_de_quebrar():
    at = _pagina("verificacao")
    at.number_input(key="w_beta_t").set_value(40.0).run()
    assert not at.exception
    assert any("β > φ" in e.value for e in at.error)


def test_opcoes_ativas_e_legadas():
    at = _pagina("verificacao")
    for k in ("w_cf_usar", "w_anc_usar", "w_bl_usar", "w_trav_usar"):
        at.toggle(key=k).set_value(True)
    at.selectbox(key="w_peso_na").set_value("Submerso (GEO5)")
    at.run()
    assert not at.exception, [e.value for e in at.exception]
    assert any("Opções legadas" in w.value for w in at.warning)
    for secao in ("Resultados", "Forças"):
        at.session_state["secao"] = secao
        at.run()
        assert not at.exception, (secao, [e.value for e in at.exception])


def test_pagina_de_dimensionamento():
    at = _pagina("dimensionamento")
    texto = " ".join(m.value for m in at.markdown)
    assert "Dimensionamento estrutural (NBR 6118): NÃO ATENDE" in texto
    chaves = {w.key for w in at.number_input}
    assert "w_cob_ct" in chaves and "w_H_muro" not in chaves            # geometria fica na verificação
    at.selectbox(key="w_ar_tz_phi").set_value(8.0)
    at.number_input(key="w_ar_tz_s").set_value(20.0).run()
    assert not at.exception, [e.value for e in at.exception]
    assert "Dimensionamento estrutural (NBR 6118): NÃO ATENDE" in " ".join(m.value for m in at.markdown)
    next(b for b in at.button if b.label.startswith("Sugerir armaduras")).click().run()
    next(b for b in at.button if b.label == "Aplicar sugestão às entradas").click().run()
    assert not at.exception, [e.value for e in at.exception]
    assert "Dimensionamento estrutural (NBR 6118): ATENDE" in " ".join(m.value for m in at.markdown)


def test_dimensionamento_com_contrafortes_nos_dois_modelos():
    at = _pagina("verificacao")
    at.toggle(key="w_cf_usar").set_value(True).run()
    at.switch_page("paginas/dimensionamento.py").run()
    assert not at.exception, [e.value for e in at.exception]
    assert any("borda livre" in e.label for e in at.expander)
    at.selectbox(key="w_laje_cf").set_value("Coeficientes do GEO5 (planilha)").run()
    assert not at.exception, [e.value for e in at.exception]
    assert any("GEO5" in e.label for e in at.expander)
    assert any("Opção legada" in c.value for c in at.caption)


def test_solos_aplica_parametros():
    at = _pagina("solos")
    at.selectbox[0].set_value("Areia").run()
    assert not at.exception
    botao = next(b for b in at.button if b.label == "Aplicar à fundação")
    botao.click().run()
    assert not at.exception
    assert at.session_state["dados"]["phi_f"] == 32.0
