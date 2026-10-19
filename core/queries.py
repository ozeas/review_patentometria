"""Leitura e comparação de consultas de busca.

A consulta **registrada** é declarada pelo analista (colada do histórico da
base). O que a exportação de resultado imprime no cabeçalho é outra coisa:
é evidência do que foi executado, gravada em campo próprio e nunca promovida
a consulta registrada — o cabeçalho é texto de interface, sujeito a
truncamento, tradução e mudança de formato entre exportações.
"""
from __future__ import annotations

import re
from urllib.parse import unquote_plus

_ESPACENET = re.compile(r"\d+\s+results?\s+found\s+for\s+(.+)", re.I | re.S)
_PREFIXO = re.compile(r"^\d+\s+results?\s+found\s+for\s+", re.I)


def consulta_espacenet(text: str) -> str:
    """Linha 'N results found for <consulta>', nas primeiras linhas do CSV.

    As aspas do campo CSV vêm dobradas (``""``) e são desdobradas aqui: o
    conteúdo da célula é a consulta, não a codificação.
    """
    for line in (text or "").lstrip("\ufeff").splitlines()[:8]:
        m = _ESPACENET.search(line.strip().strip('";'))
        if m:
            return m.group(1).strip().rstrip('";').strip().replace('""', '"')
    return ""


def consulta_google(text: str) -> str:
    """Primeira linha 'search URL:,<url>' — a consulta vai codificada na URL."""
    lines = (text or "").lstrip("\ufeff").splitlines()[:1]
    if not lines:
        return ""
    line = lines[0].strip()
    if not line.lower().startswith("search url:"):
        return ""
    return line.split(",", 1)[1].strip() if "," in line else ""


_FONTES = {"espacenet": consulta_espacenet, "google": consulta_google}


def consulta_do_arquivo(source: str, text: str) -> str:
    """Consulta que a exportação imprime no cabeçalho (vazio quando não há)."""
    fn = _FONTES.get(source)
    return fn(text) if fn else ""


def normalizar_consulta(t: str) -> str:
    """Forma comparável: URL decodificada, aspas desdobradas, espaços colapsados."""
    t = unquote_plus((t or "").strip())
    t = t.replace('""', '"')
    t = _PREFIXO.sub("", t)
    return re.sub(r"\s+", " ", t).strip().casefold()


def consultas_divergem(declarada: str, no_arquivo: str) -> bool:
    """Só há divergência quando os dois lados existem e diferem."""
    a, b = normalizar_consulta(declarada), normalizar_consulta(no_arquivo)
    return bool(a and b and a != b)
