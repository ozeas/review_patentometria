"""Regra de prevalência de metadados e campos derivados por família.

Para famílias presentes em mais de uma base, cada campo é tomado da base
preferencial; na ausência do campo, da seguinte na ordem configurada. A
base de origem de cada campo é registrada por família.
"""
from __future__ import annotations

from dataclasses import dataclass, field
from datetime import date

from .normalize import dedupe, has_cjk, ipc_main_group, ipc_subclass, name_key, pinyin_name, token_key
from .records import Family, Record

DEFAULT_PREVALENCE = {
    "publications": ["derwent", "lens", "espacenet", "google"],
    "title": ["lens", "espacenet", "google", "derwent"],
    "abstract": ["lens", "derwent"],
    "ipc": ["espacenet", "lens", "derwent"],
    "cpc": ["lens", "espacenet"],
    "applicants": ["lens", "espacenet", "derwent", "google"],
    "inventors": ["lens", "espacenet", "google", "derwent"],
    "priority_number": ["derwent", "lens"],
}

LEGAL_STATUS_MAP = {
    "ACTIVE": "vigente", "PATENTED": "vigente",
    "PENDING": "em exame",
    "DISCONTINUED": "inativa", "INACTIVE": "inativa", "EXPIRED": "inativa",
}
LEGAL_RANK = {"vigente": 0, "em exame": 1, "inativa": 2}


@dataclass
class Dictionaries:
    """Dicionários editáveis pelo analista (chave = ``name_key`` do nome bruto)."""

    applicants: dict[str, tuple[str, str]] = field(default_factory=dict)  # key -> (nome harmonizado, grupo)
    inventors: dict[str, str] = field(default_factory=dict)  # key -> forma padronizada

    def applicant(self, raw: str) -> tuple[str, str, bool]:
        """Retorna (harmonizado, grupo, mapeado?)."""
        k = name_key(raw)
        if k in self.applicants:
            h, g = self.applicants[k]
            return h, (g or h), True
        return raw, raw, False

    def inventor(self, raw: str) -> tuple[str, str]:
        """Retorna (forma padronizada, procedência: dicionario|pinyin|original)."""
        k = name_key(raw)
        if k in self.inventors:
            return self.inventors[k], "dicionario"
        if has_cjk(raw):
            return pinyin_name(raw), "pinyin"
        return raw, "original"


def _by_source(f: Family, src: str) -> list[Record]:
    return sorted((r for r in f.records if r.source == src), key=lambda r: r.row)


def _first_text(f: Family, order: list[str], attr_map: dict[str, str]):
    for src in order:
        for r in _by_source(f, src):
            v = getattr(r, attr_map.get(src, "title"), "")
            if v:
                return v, src
    return "", None


def _first_list(f: Family, order: list[str], attr: str):
    for src in order:
        vals = []
        for r in _by_source(f, src):
            vals.extend(getattr(r, attr))
        vals = dedupe(vals)
        if vals:
            return vals, src
    return [], None


def period_of(year: int | None, periods: list[list[int]]) -> str:
    if year is None:
        return "sem prioridade"
    for a, b in periods:
        if a <= year <= b:
            return f"{a}–{b}"
    return "fora dos períodos"


def months_before(d: date, months: int) -> date:
    y, m = d.year, d.month - months
    while m <= 0:
        m += 12
        y -= 1
    day = min(d.day, [31, 29 if y % 4 == 0 and (y % 100 or y % 400 == 0) else 28, 31, 30, 31, 30,
                      31, 31, 30, 31, 30, 31][m - 1])
    return date(y, m, day)


def consolidate_fields(
    f: Family,
    *,
    prevalence: dict | None = None,
    dictionaries: Dictionaries | None = None,
    periods: list[list[int]] | None = None,
    collection_date: date | None = None,
    window_months: int = 36,
    block_codes: list[str] | None = None,
) -> None:
    pv = {**DEFAULT_PREVALENCE, **(prevalence or {})}
    dic = dictionaries or Dictionaries()
    out, origin = {}, {}

    # Publicações
    pubs, src = [], None
    for s in pv["publications"]:
        pubs = [p for r in _by_source(f, s) for p in r.pubs]
        if pubs:
            src = s
            break
    out["publications"] = sorted({p.number for p in pubs})
    origin["publications"] = src
    out["all_numbers"] = f.numbers

    # Título e resumo
    title, src = _first_text(f, pv["title"], {"derwent": "dwpi_title"})
    out["title"], origin["title"] = title, src
    abstract, src = _first_text(f, pv["abstract"], {"lens": "abstract", "derwent": "dwpi_abstract"})
    out["abstract"], origin["abstract"] = abstract, src
    out["abstract_kind"] = {"lens": "original", "derwent": "DWPI"}.get(src, "") if src else "ausente"
    nov, _ = _first_text(f, ["derwent"], {"derwent": "dwpi_novelty"})
    use, _ = _first_text(f, ["derwent"], {"derwent": "dwpi_use"})
    out["dwpi_novelty_use"] = " ".join(x for x in (nov, use) if x)
    orig_abs, _ = _first_text(f, ["lens"], {"lens": "abstract"})
    orig_title, _ = _first_text(f, ["lens", "espacenet", "google"], {})
    out["original_title"] = orig_title
    out["original_abstract"] = orig_abs

    # Classificações
    ipc, src = _first_list(f, pv["ipc"], "ipc")
    out["ipc"], origin["ipc"] = ipc, src
    cpc, src = _first_list(f, pv["cpc"], "cpc")
    out["cpc"], origin["cpc"] = cpc, src
    out["ipc_subclasses"] = dedupe(ipc_subclass(c) for c in ipc)
    out["ipc_main_groups"] = dedupe(ipc_main_group(c) for c in ipc if "/" in c)
    all_ipc = dedupe(c for r in f.records for c in r.ipc)
    out["ipc_exported_all"] = all_ipc
    if block_codes:
        hits = {}
        for code in block_codes:
            c = code.replace(" ", "").upper()
            hits[code] = any(x.replace(" ", "").upper().startswith(c) for x in all_ipc)
        out["block_class_hits"] = hits

    # Depositantes e grupos econômicos
    apps, src = _first_list(f, pv["applicants"], "applicants")
    origin["applicants"] = src
    harmonized, groups, unmapped = [], [], []
    for a in apps:
        h, g, ok = dic.applicant(a)
        harmonized.append(h)
        groups.append(g)
        if not ok:
            unmapped.append(a)
    out["applicants_raw"] = apps
    out["applicants"] = dedupe(harmonized)
    out["groups"] = dedupe(groups)
    out["applicants_unmapped"] = unmapped
    out["applicants_cjk"] = [a for a in unmapped if has_cjk(a)]

    # Inventores (deduplicação por conjunto de tokens)
    invs, src = _first_list(f, pv["inventors"], "inventors")
    origin["inventors"] = src
    seen, std, how = set(), [], []
    for raw in invs:
        s, kind = dic.inventor(raw)
        k = token_key(s)
        if k in seen:
            continue
        seen.add(k)
        std.append(s)
        how.append(kind)
    out["inventors_raw"] = invs
    out["inventors"] = std
    out["inventors_pinyin"] = [s for s, k in zip(std, how) if k == "pinyin"]

    # Datas
    prio_dates = [r.earliest_priority for r in f.records if r.earliest_priority]
    eprio = min(prio_dates) if prio_dates else None
    out["earliest_priority"] = eprio.isoformat() if eprio else None
    out["priority_year"] = eprio.year if eprio else None
    out["period"] = period_of(eprio.year if eprio else None, periods or [])
    pub_dates = [(p.date, p.number, p.country) for r in f.records for p in r.pubs if p.date]
    all_pub_dates = [d for d, _, _ in pub_dates] + [r.earliest_publication for r in f.records
                                                   if r.earliest_publication]
    first_pub = min(all_pub_dates) if all_pub_dates else None
    out["first_publication"] = first_pub.isoformat() if first_pub else None
    if collection_date and first_pub:
        start = months_before(collection_date, window_months)
        out["recent_window"] = start <= first_pub <= collection_date
    else:
        out["recent_window"] = False

    # Jurisdição de origem (escritório do pedido de prioridade mais antigo)
    juris, jsrc, jnum = None, None, None
    for src in pv["priority_number"]:
        cands = [p for r in _by_source(f, src) for p in r.priorities]
        if not cands:
            continue
        dated = [p for p in cands if p.date]
        best = min(dated, key=lambda p: p.date) if dated else cands[0]
        if best.country and best.country.isalpha():
            juris, jsrc, jnum = best.country, src, best.raw
            break
    if juris is None:
        national = sorted((d, n, c) for d, n, c in pub_dates if c and c != "WO")
        if national:
            juris, jsrc, jnum = national[0][2], "publicacao_mais_antiga", national[0][1]
    out["origin_jurisdiction"] = juris
    out["origin_priority_number"] = jnum
    origin["origin_jurisdiction"] = jsrc
    out["publication_jurisdictions"] = dedupe(p.country for r in f.records for p in r.pubs)

    # Situação jurídica (Lens) — situação mais favorável entre as publicações
    statuses = [LEGAL_STATUS_MAP.get(r.legal_status) for r in f.records if r.source == "lens"]
    statuses = [s for s in statuses if s]
    out["legal_status"] = min(statuses, key=LEGAL_RANK.get) if statuses else None
    out["legal_status_raw"] = dedupe(r.legal_status for r in f.records if r.source == "lens" and r.legal_status)
    # Citações recebidas (Lens) — máximo entre publicações, não a soma
    cites = [r.cited_by for r in f.records if r.source == "lens" and r.cited_by is not None]
    out["cited_by_max"] = max(cites) if cites else None
    out["has_lens"] = any(r.source == "lens" for r in f.records)
    out["cited_patents"] = dedupe(c for r in f.records for c in r.cited_patents)

    out["sources"] = f.sources
    out["n_sources"] = len(f.sources)
    out["n_records"] = len(f.records)
    f.fields, f.origin = out, origin


def vos_text(fields: dict, mode_order=("original", "dwpi", "title")) -> tuple[str, str]:
    """Texto do corpus para o VOSviewer: título + resumo original; sem
    resumo original, título + seções NOVELTY e USE do DWPI; senão, título."""
    title = fields.get("original_title") or fields.get("title") or ""
    for mode in mode_order:
        if mode == "original" and fields.get("original_abstract"):
            return f"{title}. {fields['original_abstract']}", "original"
        if mode == "dwpi" and fields.get("dwpi_novelty_use"):
            return f"{title}. {fields['dwpi_novelty_use']}", "dwpi"
        if mode == "title":
            return title, "titulo"
    return title, "titulo"
