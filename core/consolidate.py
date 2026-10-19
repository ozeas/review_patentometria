"""Consolidação de registros em famílias por encadeamento de números.

Dois registros pertencem à mesma família quando compartilham ao menos um
número de publicação ou de prioridade normalizado (ou um identificador de
família da própria base: família simples da Lens, família DOCDB do
Espacenet). A ligação é transitiva (union-find; TARJAN, 1975).
"""
from __future__ import annotations

import difflib
from collections import Counter, defaultdict
from dataclasses import dataclass, field

from .normalize import name_key, priority_link_eligible
from .records import SOURCES, Family, Record


class UnionFind:
    def __init__(self, n: int):
        self.parent = list(range(n))

    def find(self, x: int) -> int:
        while self.parent[x] != x:
            self.parent[x] = self.parent[self.parent[x]]
            x = self.parent[x]
        return x

    def union(self, a: int, b: int) -> bool:
        ra, rb = self.find(a), self.find(b)
        if ra == rb:
            return False
        if ra > rb:
            ra, rb = rb, ra
        self.parent[rb] = ra
        return True


@dataclass
class ManualLink:
    """Ligação manual entre duas famílias sem número em comum, registrada
    por números de publicação (estáveis entre rodadas)."""

    id: int
    number_a: str
    number_b: str
    reason: str = ""


@dataclass
class ConsolidationResult:
    identified: list[Record]
    excluded_utility: list[Record]
    eligible: list[Record]
    families: list[Family]
    record_family: dict[str, str] = field(default_factory=dict)  # record_id -> family key
    unmatched_links: list[ManualLink] = field(default_factory=list)

    # ------------------------------------------------------------ estatísticas
    def stats(self) -> dict:
        by_src = Counter(r.source for r in self.identified)
        excl = Counter(r.source for r in self.excluded_utility)
        n_sources = Counter(len(f.sources) for f in self.families)
        exclusive = Counter(f.sources[0] for f in self.families if len(f.sources) == 1)
        n_elig = len(self.eligible)
        n_fam = len(self.families)
        return {
            "identified": len(self.identified),
            "identified_by_source": {s: by_src.get(s, 0) for s in SOURCES},
            "excluded_utility": len(self.excluded_utility),
            "excluded_utility_by_source": {s: excl.get(s, 0) for s in SOURCES},
            "eligible": n_elig,
            "families": n_fam,
            "redundant": n_elig - n_fam,
            "redundant_pct": round(100 * (n_elig - n_fam) / n_elig, 1) if n_elig else 0.0,
            "families_by_n_sources": {k: n_sources.get(k, 0) for k in range(1, len(SOURCES) + 1)},
            "exclusive_by_source": {s: exclusive.get(s, 0) for s in SOURCES},
            "manual_links_applied": sum(len(f.manual_link_ids) for f in self.families),
            "manual_links_unmatched": len(self.unmatched_links),
        }


def link_tokens(rec: Record, prio_min_digits: int) -> list[str]:
    toks = [f"P:{n}" for n in rec.pub_numbers]
    toks += [f"R:{p.number}" for p in rec.priorities if priority_link_eligible(p, prio_min_digits)]
    toks += rec.family_ids
    return toks


def consolidate(
    records: list[Record],
    *,
    utility_kinds: tuple[str, ...] = ("U",),
    prio_min_digits: int = 8,
    manual_links: list[ManualLink] | None = None,
    sort_key=None,
) -> ConsolidationResult:
    excluded = [r for r in records if r.is_utility_model_only(utility_kinds)]
    excluded_ids = {r.record_id for r in excluded}
    eligible = [r for r in records if r.record_id not in excluded_ids]

    uf = UnionFind(len(eligible))
    owner: dict[str, int] = {}
    for idx, rec in enumerate(eligible):
        for tok in link_tokens(rec, prio_min_digits):
            if tok in owner:
                uf.union(owner[tok], idx)
            else:
                owner[tok] = idx

    # Ligações manuais (por número de publicação)
    applied: dict[int, list[int]] = defaultdict(list)
    unmatched = []
    for ml in manual_links or []:
        a, b = owner.get(f"P:{ml.number_a}"), owner.get(f"P:{ml.number_b}")
        if a is None or b is None:
            unmatched.append(ml)
            continue
        uf.union(a, b)
        applied[uf.find(a)].append(ml.id)

    groups: dict[int, list[Record]] = defaultdict(list)
    for idx, rec in enumerate(eligible):
        groups[uf.find(idx)].append(rec)
    link_by_root: dict[int, list[int]] = defaultdict(list)
    for root, ids in applied.items():
        link_by_root[uf.find(root)].extend(ids)

    fams = []
    for root, recs in groups.items():
        f = Family(key="", records=recs, manual_link_ids=sorted(link_by_root.get(root, [])))
        fams.append(f)

    def _default_sort(f: Family):
        dates = [r.earliest_priority for r in f.records if r.earliest_priority]
        return (min(dates).isoformat() if dates else "9999", f.anchor)

    fams.sort(key=sort_key or _default_sort)
    width = max(3, len(str(len(fams))))
    rec_fam = {}
    for i, f in enumerate(fams, start=1):
        f.key = f"F{i:0{width}d}"
        for r in f.records:
            rec_fam[r.record_id] = f.key
    return ConsolidationResult(records, excluded, eligible, fams, rec_fam, unmatched)


# ---------------------------------------------------------------- sugestões
def _title_of(f: Family) -> str:
    for src in ("lens", "espacenet", "google"):
        for r in f.records:
            if r.source == src and r.title:
                return r.title
    for r in f.records:
        if r.dwpi_title:
            return r.dwpi_title
    return ""


def _earliest(f: Family):
    d = [r.earliest_priority for r in f.records if r.earliest_priority]
    return min(d) if d else None


def suggest_links(families: list[Family], *, min_title_ratio: float = 0.6,
                  harmonize=None) -> list[dict]:
    """Pares de famílias sem número em comum com a mesma prioridade mais
    antiga, depositante em comum e título semelhante — candidatos a ligação
    manual (sempre sujeitos à verificação do analista)."""
    harmonize = harmonize or (lambda n: name_key(n))
    by_date: dict = defaultdict(list)
    for f in families:
        d = _earliest(f)
        if d:
            by_date[d].append(f)
    out = []
    for d, fs in by_date.items():
        if len(fs) < 2:
            continue
        for i in range(len(fs)):
            for j in range(i + 1, len(fs)):
                a, b = fs[i], fs[j]
                apps_a = {harmonize(n) for r in a.records for n in r.applicants}
                apps_b = {harmonize(n) for r in b.records for n in r.applicants}
                common = apps_a & apps_b
                if not common:
                    continue
                ta, tb = _title_of(a).upper(), _title_of(b).upper()
                ratio = difflib.SequenceMatcher(None, ta, tb).ratio() if ta and tb else 0.0
                if ratio < min_title_ratio:
                    continue
                out.append({
                    "family_a": a.key, "family_b": b.key,
                    "number_a": a.anchor, "number_b": b.anchor,
                    "priority_date": d.isoformat(),
                    "common_applicants": sorted(common),
                    "title_a": _title_of(a), "title_b": _title_of(b),
                    "title_ratio": round(ratio, 3),
                })
    out.sort(key=lambda x: -x["title_ratio"])
    return out


def map_subset_to_families(subset: list[Record], result: ConsolidationResult,
                           prio_min_digits: int = 8) -> dict:
    """Associa registros de um recorte separado (ex.: BR) às famílias do
    núcleo, pelos mesmos critérios de encadeamento."""
    owner = {}
    for f in result.families:
        for r in f.records:
            for tok in link_tokens(r, prio_min_digits):
                owner.setdefault(tok, f.key)
    sub = consolidate(subset, prio_min_digits=prio_min_digits)
    mapping = {}
    for f in sub.families:
        hits = set()
        for r in f.records:
            for tok in link_tokens(r, prio_min_digits):
                if tok in owner:
                    hits.add(owner[tok])
        mapping[f.key] = {"family": f, "core_families": sorted(hits)}
    return {"subset_result": sub, "mapping": mapping}
