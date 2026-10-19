"""Espacenet — exportação CSV com ';' e linhas de cabeçalho da consulta.

Células multivaloradas usam quebra de linha dentro do campo. A coluna
'Family number' é o identificador da família DOCDB.
"""
from __future__ import annotations

import csv
import io

from ..normalize import clean_name, dedupe, normalize_ipc, normalize_pub, parse_date
from ..records import Record


def _lines(v: str) -> list[str]:
    return [x.strip() for x in (v or "").replace("\r", "\n").split("\n") if x.strip()]


def parse(text: str, recorte: str) -> list[Record]:
    rows = list(csv.reader(io.StringIO(text.lstrip("﻿")), delimiter=";"))
    hdr_idx = next((i for i, r in enumerate(rows) if r and r[0].strip() == "No"), None)
    if hdr_idx is None:
        raise ValueError("Cabeçalho 'No;Title;...' não encontrado na exportação do Espacenet.")
    header = [h.strip() for h in rows[hdr_idx]]
    out: list[Record] = []
    for i, r in enumerate(rows[hdr_idx + 1:], start=1):
        if not r or not any(c.strip() for c in r):
            continue
        row = dict(zip(header, r))
        nums = _lines(row.get("Publication number", ""))
        dates = [parse_date(d) for d in _lines(row.get("Publication date", ""))]
        pubs = []
        for j, n in enumerate(nums):
            p = normalize_pub(n, dates[j] if j < len(dates) else None)
            if p:
                pubs.append(p)
        if not pubs:
            continue
        fam = (row.get("Family number") or "").strip()
        rec = Record(
            source="espacenet", recorte=recorte, row=i,
            pubs=pubs,
            earliest_priority=parse_date(row.get("Earliest priority", "")),
            earliest_publication=parse_date(row.get("Earliest publication", "")),
            title=(row.get("Title") or "").strip(),
            applicants=dedupe(clean_name(a) for a in _lines(row.get("Applicants", ""))),
            inventors=dedupe(clean_name(a) for a in _lines(row.get("Inventors", ""))),
            ipc=dedupe(normalize_ipc(c) for c in _lines(row.get("IPC", ""))),
            cpc=dedupe(normalize_ipc(c) for c in _lines(row.get("CPC", ""))),
            family_ids=[f"DOCDB:{fam.lstrip('0')}"] if fam else [],
        )
        out.append(rec)
    return out
