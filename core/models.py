"""Modelo de entrada (``Entrada``) — construído a partir de ``core.campos.CAMPOS``.

Cada campo tem o MESMO nome da célula nomeada na aba ``Entrada`` da planilha
(``H_muro``, ``b_talao``, ``phi_at`` ...). Campos Sim/Não são ``bool``; listas
são os enums de ``core.enums``; três campos aceitam ``None`` = "igual ao campo
vinculado" (``delta_dv`` → ``phi_at``; ``gw_f`` e ``gf_cs`` → ``gf_f``).
"""
from __future__ import annotations

from typing import Any, Optional

from pydantic import BaseModel, ConfigDict, Field, create_model, model_validator

from .campos import CAMPO, CAMPOS
from .enums import CAMPOS_SIM_NAO, ENUM_DO_CAMPO, OPCOES_LEGADAS


class _Base(BaseModel):
    model_config = ConfigDict(frozen=True, extra="forbid")

    @model_validator(mode="after")
    def _coerencia(self):
        erros = []
        if self.H_muro <= self.h_sap:
            erros.append("A altura total H deve ser maior que a espessura da sapata hs.")
        if self.beta_t > self.phi_at:
            erros.append("β > φ do aterro: as teorias de empuxo não se aplicam (talude instável).")
        if self.gsat_at < self.gam_w or self.gsat_f < self.gam_w:
            erros.append("Peso específico saturado menor que o da água.")
        if erros:
            raise ValueError(" | ".join(erros))
        return self

    # ------------------------------------------------------------------ utilidades
    def resolvida(self) -> "Entrada":
        """Devolve a entrada com os campos vinculados (None) substituídos."""
        troca = {c.nome: getattr(self, c.vinculo) for c in CAMPOS
                 if c.vinculo and getattr(self, c.nome) is None}
        return self.model_copy(update=troca) if troca else self

    def com(self, **mudancas: Any) -> "Entrada":
        """Cópia validada com alguns campos alterados."""
        dados = self.model_dump()
        dados.update(mudancas)
        return type(self)(**dados)

    def opcoes_legadas_ativas(self) -> list[str]:
        """Rótulos das opções de compatibilidade GEO5 que estão selecionadas."""
        ativas = []
        for nome, legadas in OPCOES_LEGADAS.items():
            if getattr(self, nome) in legadas:
                ativas.append(f"{CAMPO[nome].rotulo}: {getattr(self, nome).value}")
        return ativas

    # ---------------------------------------------------------- formato da planilha
    def para_planilha(self, so_app: bool = False) -> dict[str, Any]:
        """Valores como aparecem nas células da aba Entrada (Sim/Não, textos).

        Campos que só existem no aplicativo ficam de fora, a menos de ``so_app=True``.
        """
        r = self.resolvida()
        saida: dict[str, Any] = {}
        for c in CAMPOS:
            if not c.celula and not so_app:
                continue
            v = getattr(r, c.nome)
            if c.tipo == "bool":
                sim, nao = CAMPOS_SIM_NAO[c.nome]
                v = sim if v else nao
            elif c.tipo == "enum":
                v = v.value
            saida[c.nome] = v
        return saida

    @classmethod
    def da_planilha(cls, valores: dict[str, Any]) -> "Entrada":
        """Constrói a entrada a partir dos valores das células nomeadas."""
        dados: dict[str, Any] = {}
        for c in CAMPOS:
            if c.nome not in valores or valores[c.nome] is None:
                continue
            v = valores[c.nome]
            if c.tipo == "bool":
                v = (str(v).strip() == CAMPOS_SIM_NAO[c.nome][0])
            elif c.tipo == "int":
                v = int(round(float(v)))
            elif c.tipo == "float":
                v = float(v)
            dados[c.nome] = v
        return cls(**dados)


def _definicao(c) -> tuple[Any, Any]:
    if c.tipo == "bool":
        return (bool, Field(default=c.padrao, description=c.rotulo))
    if c.tipo == "enum":
        cls = ENUM_DO_CAMPO[c.nome]
        return (cls, Field(default=cls(c.padrao), description=c.rotulo))
    tipo = int if c.tipo == "int" else float
    lim = {}
    if c.minimo is not None:
        lim["ge"] = c.minimo
    if c.maximo is not None:
        lim["le"] = c.maximo
    if c.vinculo:
        return (Optional[tipo], Field(default=c.padrao, description=c.rotulo, **lim))
    return (tipo, Field(default=c.padrao, description=c.rotulo, **lim))


Entrada = create_model("Entrada", __base__=_Base, **{c.nome: _definicao(c) for c in CAMPOS})
Entrada.__doc__ = "Dados de entrada do muro (aba Entrada da planilha). Padrões = exemplo da planilha."
