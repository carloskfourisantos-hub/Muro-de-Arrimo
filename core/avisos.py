"""Avisos de consistência dos dados — port de ``Resumo!C35`` (19 condições).

Na planilha qualquer aviso leva o resultado a "NÃO ATENDE"; o aplicativo
mantém essa regra e acrescenta um nível a cada aviso, só para a apresentação.
"""
from __future__ import annotations

from dataclasses import dataclass

from .enums import MetodoEmpuxo, PosicaoContraforte
from .forcas import Forcas
from .geometria import TOL, Geometria
from .verificacoes import Verificacoes

ERRO, ALERTA, INFO = "erro", "alerta", "info"
_TOL = 1e-9   # o Excel compara com ~15 dígitos: 1,4 − 0,4 não é "menor que" 1,0


def maior(a: float, b: float) -> bool:
    return a > b + _TOL


def menor(a: float, b: float) -> bool:
    return a < b - _TOL


@dataclass(frozen=True)
class Aviso:
    codigo: str
    texto: str
    nivel: str


def calcular_avisos(e, g: Geometria, F: Forcas, V: Verificacoes) -> tuple[Aviso, ...]:
    B, a = g.B_base, F.anc
    frente = e.cf_tipo == PosicaoContraforte.FRENTE
    fora = lambda x: menor(x, 0) or maior(x, B)  # noqa: E731
    regras = [
        ("beta_phi", e.beta_t > e.phi_at, "β > φ do aterro: teorias de empuxo inválidas", ERRO),
        ("n_neg", F.F_N <= 0, "N ≤ 0: base sem compressão", ERRO),
        ("fora_base", V.R_Bef <= 0, "Resultante fora da base (B' ≤ 0)", ERRO),
        ("topo_base", maior(e.t_topo, e.t_base), "Espessura do topo maior que a da base", ALERTA),
        ("cf_talao", e.cf_usar and not frente and maior(e.cf_Lb, e.b_talao),
         "Contraforte mais longo que o talão (limitado ao talão)", INFO),
        ("cf_ponta", e.cf_usar and frente and maior(e.cf_Lb, e.b_ponta),
         "Contraforte frontal mais largo que a ponta (limitado à ponta)", INFO),
        ("trav_cota", e.trav_usar and (e.trav_z <= 0 or maior(e.trav_z, e.H_muro)),
         "Cota do travamento fora da altura do muro", ERRO),
        ("estaca_fora", e.anc_usar and (fora(a.anc_xe) or (e.anc_n2 > 0 and fora(e.anc_x2))),
         "Estaca fora da base", ERRO),
        ("bloco_largo", e.bl_usar and (a.bl_xe - e.bl_B / 2 < -0.001 or a.bl_xe + e.bl_B / 2 > B + 0.001),
         "Bloco ultrapassa a largura da sapata", ALERTA),
        ("estaca_bloco", e.bl_usar and e.anc_usar and (
            abs(a.anc_xe - a.bl_xe) > e.bl_B / 2 - e.anc_d / 2 + 0.0001
            or (e.anc_n2 > 0 and abs(e.anc_x2 - a.bl_xe) > e.bl_B / 2 - e.anc_d / 2 + 0.0001)),
         "Estaca fora do bloco", ERRO),
        ("linhas_prox", e.bl_usar and e.anc_usar and e.anc_n2 > 0 and menor(abs(e.anc_x2 - a.anc_xe), 2.5 * e.anc_d),
         "Linhas de estacas com espaçamento < 2,5·d", ALERTA),
        ("bloco_curto", e.bl_usar and e.anc_usar
         and menor(e.bl_L, e.anc_d * (1 + 2.5 * (max(e.anc_n1, e.anc_n2) - 1))),
         "Bloco curto para o nº de estacas por linha (espaçamento < 2,5·d)", ALERTA),
        ("bloco_longo", e.bl_usar and maior(e.bl_L, e.anc_esp), "Bloco mais longo que o espaçamento entre blocos", ALERTA),
        ("cf_alto", e.cf_usar and maior(e.cf_h, g.h_cort), "Contraforte mais alto que a cortina (limitado à cortina)", INFO),
        ("na_alto", maior(e.hw_at, g.z_ter), "NA atrás acima do terreno (peso do solo limitado à cota do terreno)", ALERTA),
        ("terreno_baixo", maior(e.h_reb, g.h_cort), "Terreno abaixo do topo da sapata", ALERTA),
        ("talao_longo", g.cv == 0 and g.hit_t == 1 and e.b_talao > TOL and g.th_c > 0.001,
         "Cunha inclinada atinge o terreno antes do tardoz (talão longo): caso não validado contra o GEO5", ALERTA),
        ("rankine_cunha", e.metodo_emp == MetodoEmpuxo.RANKINE and g.cv == 0 and e.b_talao > TOL,
         "Rankine com cunha inclinada: empuxo de Rankine aplicado em cada trecho como plano vertical", ALERTA),
        ("delta_phi", e.metodo_emp == MetodoEmpuxo.COULOMB and maior(e.delta_dv, e.phi_at), "δ > φ no dorso virtual", ALERTA),
    ]
    return tuple(Aviso(c, t, n) for c, cond, t, n in regras if cond)


def texto_planilha(avisos: tuple[Aviso, ...]) -> str:
    """Mesma string de ``Resumo!C35``."""
    return "".join(a.texto + "; " for a in avisos) or "Nenhum"
