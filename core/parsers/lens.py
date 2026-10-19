"""Lens.org — exportação CSV (campos multivalorados separados por ';;')."""
from __future__ import annotations

import csv
import io

from ..normalize import clean_name, dedupe, normalize_ipc, normalize_priority, normalize_pub, parse_date
from ..records import Record


def _multi(v: str) -> list[str]:
    return [x.strip() for x in (v or "").split(";;") if x.strip()]


def _int(v: str):
    try:
        return int(str(v).strip())
    except (TypeError, ValueError):
        return None


def parse(text: str, recorte: str) -> list[Record]:
    reader = csv.DictReader(io.StringIO(text.lstrip("﻿")))
    out: list[Record] = []
    for i, row in enumerate(reader, start=1):
        key = (row.get("Display Key") or "").strip()
        if not key:
            continue
        pub = normalize_pub(key, parse_date(row.get("Publication Date", "")))
        eprio = parse_date(row.get("Earliest Priority Date", ""))
        prios = []
        for p in _multi(row.get("Priority Numbers", "")):
            np = normalize_priority(p)
            if np:
                prios.append(np)
        # A Lens não associa data a cada prioridade; a data mais antiga é atribuída
        # à prioridade de menor ano embutido no número (ou à única existente).
        if prios and eprio:
            def _yr(p):
                d = "".join(ch for ch in p.number if ch.isdigit())
                return int(d[:4]) if len(d) >= 4 and d[:2] in ("19", "20") else 9999
            min(prios, key=_yr).date = eprio
        lens_id = (row.get("Lens ID") or "").strip()
        fam = [f"LENS:{x}" for x in _multi(row.get("Simple Family Members", ""))]
        if lens_id:
            fam.append(f"LENS:{lens_id}")
        rec = Record(
            source="lens", recorte=recorte, row=i,
            pubs=[pub] if pub else [],
            priorities=prios,
            earliest_priority=eprio,
            title=(row.get("Title") or "").strip(),
            abstract=(row.get("Abstract") or "").strip(),
            applicants=dedupe(clean_name(a) for a in _multi(row.get("Applicants", ""))),
            inventors=dedupe(clean_name(a) for a in _multi(row.get("Inventors", ""))),
            ipc=dedupe(normalize_ipc(c) for c in _multi(row.get("IPCR Classifications", ""))),
            cpc=dedupe(normalize_ipc(c) for c in _multi(row.get("CPC Classifications", ""))),
            family_ids=dedupe(fam),
            legal_status=(row.get("Legal Status") or "").strip().upper(),
            cited_by=_int(row.get("Cited by Patent Count")),
            doc_type=(row.get("Document Type") or "").strip(),
        )
        out.append(rec)
    return out
