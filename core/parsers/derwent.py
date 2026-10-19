"""Derwent Innovations Index (Web of Science) — exportação TXT com tags WoS
separadas por tabulação (PN, TI, AU, AE, AB, IP, PD, PI, CP...).

Cada registro corresponde a uma família Derwent e traz a lista completa
de publicações (PN), título e resumo reescritos pelo DWPI.
"""
from __future__ import annotations

import re

from ..normalize import clean_name, dedupe, normalize_ipc, normalize_priority, normalize_pub, parse_date
from ..records import Record

_SECTION = re.compile(
    r"\b(NOVELTY|USE|ADVANTAGE|DETAILED DESCRIPTION|DESCRIPTION OF DRAWING\(S\)|"
    r"TECHNOLOGY FOCUS|ACTIVITY|MECHANISM OF ACTION|EXTENSION ABSTRACT)\s+-\s+"
)
_PUBTOK = re.compile(r"\b([A-Z]{2}\d{4,}[A-Z]?\d*(?:-[A-Z]\d?)?)\b")
_DATE = r"(\d{1,2}\s+[A-Z][a-z]{2}\s+\d{4})"


def _semi(v: str) -> list[str]:
    return [x.strip() for x in (v or "").split(";") if x.strip()]


def dwpi_sections(ab: str) -> dict[str, str]:
    ab = re.sub(r"\s+", " ", ab or "").strip()
    parts = _SECTION.split(ab)
    out: dict[str, str] = {}
    # parts = [prefixo, NOME, texto, NOME, texto, ...]
    for k in range(1, len(parts) - 1, 2):
        out.setdefault(parts[k], parts[k + 1].strip())
    return out


def parse(text: str, recorte: str) -> list[Record]:
    text = text.lstrip("﻿").replace("\r\n", "\n").replace("\r", "\n")
    lines = [ln for ln in text.split("\n") if ln.strip()]
    if not lines:
        return []
    header = [h.strip() for h in lines[0].split("\t")]
    out: list[Record] = []
    for i, ln in enumerate(lines[1:], start=1):
        cells = ln.split("\t")
        row = {header[j]: cells[j].strip() if j < len(cells) else "" for j in range(len(header))}
        pn = _semi(row.get("PN", ""))
        if not pn:
            continue
        # Datas por publicação (campo PD: "US2012011919-A1   19 Jan 2012   ...")
        pdates = {}
        for entry in _semi(row.get("PD", "")):
            m = re.match(r"(\S+)\s+" + _DATE, entry)
            if m:
                pdates[m.group(1)] = parse_date(m.group(2))
        pubs = [p for p in (normalize_pub(n, pdates.get(n)) for n in pn) if p]
        own = {p.number for p in pubs}
        prios = []
        for entry in _semi(row.get("PI", "")):
            m = re.match(r"(\S+)\s+" + _DATE, entry)
            if m:
                p = normalize_priority(m.group(1), parse_date(m.group(2)))
            else:
                p = normalize_priority(entry.split()[0])
            if p:
                prios.append(p)
        dated = [p.date for p in prios if p.date]
        sections = dwpi_sections(row.get("AB", ""))
        cited = []
        for tok in _PUBTOK.findall(row.get("CP", "")):
            p = normalize_pub(tok)
            if p and p.number not in own:
                cited.append(p.number)
        rec = Record(
            source="derwent", recorte=recorte, row=i,
            pubs=pubs,
            priorities=prios,
            earliest_priority=min(dated) if dated else None,
            title="",
            dwpi_title=re.sub(r"\s+", " ", row.get("TI", "")).strip(),
            dwpi_abstract=re.sub(r"\s+", " ", row.get("AB", "")).strip(),
            dwpi_novelty=sections.get("NOVELTY", ""),
            dwpi_use=sections.get("USE", ""),
            applicants=dedupe(clean_name(a) for a in _semi(row.get("AE", ""))),
            inventors=dedupe(clean_name(a) for a in _semi(row.get("AU", ""))),
            ipc=dedupe(normalize_ipc(c) for c in _semi(row.get("IP", ""))),
            cited_patents=dedupe(cited),
        )
        out.append(rec)
    return out
