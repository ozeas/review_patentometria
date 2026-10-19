"""Google Patents — exportação CSV (primeira linha com a URL da consulta).

Não exporta resumo, IPC/CPC nem números de prioridade; cada linha traz uma
publicação representativa da família.
"""
from __future__ import annotations

import csv
import io
import re

from ..normalize import clean_name, dedupe, has_cjk, normalize_pub, parse_date
from ..records import Record

# Sufixos societários que não devem ser separados do nome pela vírgula
_SUFFIX = re.compile(
    r"^(inc|inc\.|ltd|ltd\.|llc|l\.l\.c\.|co|co\.|corp|corp\.|corporation|s\.a\.|sa|ag|gmbh|"
    r"b\.v\.|bv|n\.v\.|nv|plc|lp|l\.p\.|limited|company|s\.p\.a\.|spa|ab|as|oy|kk|k\.k\.)$",
    re.I,
)


def split_names(v: str) -> list[str]:
    parts = [p.strip() for p in (v or "").split(",")]
    out: list[str] = []
    for p in parts:
        if not p:
            continue
        if out and _SUFFIX.match(p):
            out[-1] = f"{out[-1]}, {p}"
        else:
            out.append(p)
    return out


def _up(name: str) -> str:
    """Maiúsculas, como nas demais bases (grafias em chinês preservadas)."""
    return name if has_cjk(name) else name.upper()


def parse(text: str, recorte: str) -> list[Record]:
    lines = text.lstrip("﻿").splitlines()
    start = 1 if lines and lines[0].startswith("search URL:") else 0
    reader = csv.DictReader(io.StringIO("\n".join(lines[start:])))
    out: list[Record] = []
    for i, row in enumerate(reader, start=1):
        pid = (row.get("id") or "").strip()
        if not pid:
            continue
        pub = normalize_pub(pid, parse_date(row.get("publication date", "")))
        rec = Record(
            source="google", recorte=recorte, row=i,
            pubs=[pub] if pub else [],
            earliest_priority=parse_date(row.get("priority date", "")),
            title=(row.get("title") or "").strip(),
            applicants=dedupe(_up(clean_name(a)) for a in split_names(row.get("assignee", ""))),
            inventors=dedupe(_up(clean_name(a)) for a in split_names(row.get("inventor/author", ""))),
        )
        out.append(rec)
    return out
