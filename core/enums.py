"""Opções de lista da aba ``Entrada``.

Os valores são os textos EXATOS das listas de validação da planilha
``Verificacao_Muro_Arrimo_NBR11682.xlsx``: isso mantém a rastreabilidade e
permite importar/exportar a planilha sem tradução.

Opções marcadas em ``OPCOES_LEGADAS`` existem só para reproduzir o GEO5; o
aplicativo as oferece como "legado" e sinaliza quando estão ativas.
"""
from __future__ import annotations

from enum import Enum


class _Opcao(str, Enum):
    def __str__(self) -> str:  # rótulo = valor
        return self.value


class FaceInclinada(_Opcao):
    FRONTAL = "Frontal"
    TARDOZ = "Tardoz"


class PosicaoContraforte(_Opcao):
    ATRAS = "Atrás (sobre o talão)"
    FRENTE = "Na frente (sobre a ponta)"


class ConvTravamento(_Opcao):
    SOMAR = "Somar à resistência"
    DESCONTAR = "Descontar da ação"
    GEO5 = "Como GEO5"


class TipoEmpuxo(_Opcao):
    REPOUSO = "Repouso (K0)"
    ATIVO = "Ativo"


class MetodoEmpuxo(_Opcao):
    RANKINE = "Rankine"
    COULOMB = "Coulomb"


class ConvRankine(_Opcao):
    CLASSICA = "Clássica (com cos β)"
    GEO5 = "Como GEO5"


class ModoCunha(_Opcao):
    INCLINADA = "Inclinada (GEO5)"
    VERTICAL = "Vertical"


class ResFrontal(_Opcao):
    NENHUMA = "Nenhuma"
    REPOUSO = "Em repouso"


class ConvResistentes(_Opcao):
    SOMAR = "Somar à resistência"
    DESCONTAR = "Descontar da ação (GEO5)"


class ScVertical(_Opcao):
    CONSISTENTE = "Consistente"
    GEO5 = "Como GEO5"


class LarguraEfetiva(_Opcao):
    PADRAO = "B − 2|e|"
    GEO5 = "Como GEO5"


class Subpressao(_Opcao):
    LINEAR = "Distribuição linear"
    NAO = "Não considerar"


class PesoNA(_Opcao):
    SATURADO = "Saturado (γsat)"
    SUBMERSO = "Submerso (GEO5)"


class ModoCapacidade(_Opcao):
    VESIC = "Calculada (Vesic)"
    INFORMADA = "Informada"


class ModeloCortante(_Opcao):
    VRD1 = "VRd1 (NBR lajes)"
    GEO5 = "0,6·fctd·b·d (GEO5)"


class MomentoPonta(_Opcao):
    MAXIMO = "Máximo"
    PRESSOES = "Pressões na base"
    GEO5 = "Igual à cortina (GEO5)"


class TensaoDim(_Opcao):
    LINEAR = "Linear"
    RETANGULAR = "Retangular (Meyerhof)"


class LimiteXd(_Opcao):
    NBR = "0,45 (NBR 6118)"
    GEO5 = "0,259 (GEO5)"


class PressaoLaje(_Opcao):
    FUNDO = "Até o fundo da base (GEO5)"
    TOPO = "Até o topo da base"


class PosicaoBloco(_Opcao):      # só no aplicativo (não existe na planilha)
    TARDOZ = "Alinhado ao tardoz"
    ESTACAS = "Centrado nas estacas (planilha)"
    INFORMADA = "Posição informada"


class ModeloLajeCF(_Opcao):      # só no aplicativo
    PLACA = "Laje com borda livre (placa)"
    GEO5 = "Coeficientes do GEO5 (planilha)"


# Opções que só existem para reproduzir o GEO5 e se afastam do critério
# padrão (NBR / prática conservadora). Chave = nome do campo da Entrada.
OPCOES_LEGADAS: dict[str, tuple[_Opcao, ...]] = {
    "trav_conv": (ConvTravamento.GEO5,),
    "rk_conv": (ConvRankine.GEO5,),
    "conv_res": (ConvResistentes.DESCONTAR,),
    "sc_vert": (ScVertical.GEO5,),
    "bef_desl": (LarguraEfetiva.GEO5,),
    "peso_na": (PesoNA.SUBMERSO,),
    "v_mod": (ModeloCortante.GEO5,),
    "ponta_mod": (MomentoPonta.GEO5,),
    "xd_lim": (LimiteXd.GEO5,),
    "laje_cf": (ModeloLajeCF.GEO5,),
}

# Campo da Entrada -> classe da opção (os demais campos são numéricos ou Sim/Não)
ENUM_DO_CAMPO: dict[str, type[_Opcao]] = {
    "face_inc": FaceInclinada,
    "cf_tipo": PosicaoContraforte,
    "trav_conv": ConvTravamento,
    "trav_emp": TipoEmpuxo,
    "metodo_emp": MetodoEmpuxo,
    "rk_conv": ConvRankine,
    "modo_cunha": ModoCunha,
    "ff_tipo": ResFrontal,
    "conv_res": ConvResistentes,
    "sc_vert": ScVertical,
    "bef_desl": LarguraEfetiva,
    "subp": Subpressao,
    "peso_na": PesoNA,
    "cc_modo": ModoCapacidade,
    "emp_dim": TipoEmpuxo,
    "v_mod": ModeloCortante,
    "ponta_mod": MomentoPonta,
    "sig_dim": TensaoDim,
    "xd_lim": LimiteXd,
    "laje_pres": PressaoLaje,
    "bl_pos": PosicaoBloco,
    "laje_cf": ModeloLajeCF,
}

# Campos Sim/Não (bool no modelo). Valor = (texto para True, texto para False)
CAMPOS_SIM_NAO: dict[str, tuple[str, str]] = {
    "solo_ponta": ("Sim", "Não"),
    "cf_usar": ("Sim", "Não"),
    "cf_peso": ("Sim", "Não (como GEO5)"),
    "anc_usar": ("Sim", "Não"),
    "bl_usar": ("Sim", "Não"),
    "trav_usar": ("Sim", "Não"),
    "q_estab": ("Sim", "Não"),
}
