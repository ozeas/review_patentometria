"""Triagem lexical: ocorrência dos termos de cada bloco no título e no
título+resumo (suporte à comparação exigida na seção 3.5)."""
from __future__ import annotations

import re


def term_pattern(term: str) -> re.Pattern:
    """Termo como frase; hífen e espaço equivalentes; '*' como truncamento."""
    t = term.strip().lower()
    parts = re.split(r"[\s\-]+", t)
    pat = r"[\s\-]+".join(re.escape(p).replace(r"\*", r"\w*") for p in parts)
    return re.compile(rf"(?<![\w]){pat}(?![\w])", re.I)


def compile_blocks(blocks: list[dict]) -> list[tuple[str, list[tuple[str, re.Pattern]]]]:
    out = []
    for b in blocks:
        terms = [t for t in b.get("terms", []) if t.strip()]
        if not terms:
            continue
        out.append((b.get("name", ""), [(t, term_pattern(t)) for t in terms]))
    return out


def match_blocks(text: str, compiled) -> dict[str, list[str]]:
    res = {}
    for name, pats in compiled:
        res[name] = [t for t, p in pats if p.search(text or "")]
    return res


def lexical_profile(title: str, abstract: str, compiled) -> dict:
    """Classifica a família quanto à presença de todos os blocos lexicais:
    'titulo' (no título), 'titulo+resumo' (só com o resumo) ou 'ausente'."""
    t = match_blocks(title, compiled)
    ta = match_blocks(f"{title} {abstract}", compiled)
    all_t = all(t[n] for n, _ in compiled) if compiled else False
    all_ta = all(ta[n] for n, _ in compiled) if compiled else False
    level = "titulo" if all_t else ("titulo+resumo" if all_ta else "ausente")
    return {"title_hits": t, "title_abstract_hits": ta, "level": level}


def highlight(text: str, compiled) -> str:
    """Marca termos com <mark> (texto já escapado por quem chama)."""
    for _, pats in compiled:
        for _, p in pats:
            text = p.sub(lambda m: f"\x00{m.group(0)}\x01", text)
    return text.replace("\x00", "<mark>").replace("\x01", "</mark>")
