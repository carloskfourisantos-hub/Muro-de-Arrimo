"""Projeto em JSON versionado (um arquivo = um muro)."""
from __future__ import annotations

import json
from datetime import datetime

from core.models import Entrada

VERSAO = 1


def salvar(entrada: Entrada, nome: str = "", obra: str = "", autor: str = "") -> str:
    return json.dumps({
        "formato": "muro-arrimo", "versao": VERSAO, "salvo_em": datetime.now().isoformat(timespec="seconds"),
        "nome": nome, "obra": obra, "autor": autor, "entrada": entrada.model_dump(mode="json"),
    }, ensure_ascii=False, indent=2)


def carregar(texto: str | bytes) -> tuple[Entrada, dict]:
    """Devolve (entrada, metadados). Campos desconhecidos de versões futuras são ignorados."""
    d = json.loads(texto)
    if d.get("formato") != "muro-arrimo":
        raise ValueError("O arquivo não é um projeto de muro de arrimo deste aplicativo.")
    campos = set(Entrada.model_fields)
    dados = {k: v for k, v in d.get("entrada", {}).items() if k in campos}
    meta = {k: d.get(k, "") for k in ("nome", "obra", "autor", "salvo_em")}
    return Entrada(**dados), meta
