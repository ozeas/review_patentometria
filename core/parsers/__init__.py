"""Adaptadores de exportação por base.

Cada adaptador recebe o conteúdo textual de uma exportação e devolve uma
lista de ``Record`` normalizados. Para acrescentar uma base, implemente
uma função ``parse(text, recorte) -> list[Record]`` e registre-a em
``PARSERS``.
"""
from __future__ import annotations

from . import derwent, espacenet, google, lens

PARSERS = {
    "lens": lens.parse,
    "espacenet": espacenet.parse,
    "google": google.parse,
    "derwent": derwent.parse,
}


def decode(data: bytes) -> str:
    for enc in ("utf-8-sig", "utf-16", "cp1252", "latin-1"):
        try:
            text = data.decode(enc)
            if enc == "utf-16" and "\x00" in text:
                continue
            return text
        except (UnicodeDecodeError, UnicodeError):
            continue
    return data.decode("utf-8", errors="replace")


def detect_source(text: str) -> str | None:
    """Identifica a base pelo cabeçalho da exportação."""
    head = text.lstrip("﻿")[:2000]
    if head.startswith('"Espacenet"') or head.startswith("Espacenet"):
        return "espacenet"
    if head.startswith("search URL:"):
        return "google"
    first = head.splitlines()[0] if head else ""
    if "Lens ID" in first and "Display Key" in first:
        return "lens"
    if first.replace(" ", "").startswith("PN\tTI"):
        return "derwent"
    return None


def parse_bytes(data: bytes, source: str | None, recorte: str):
    text = decode(data)
    src = source or detect_source(text)
    if src not in PARSERS:
        raise ValueError("Formato de exportação não reconhecido. Informe a base.")
    return src, PARSERS[src](text, recorte)
