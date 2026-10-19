"""Indicadores descritivos sobre um conjunto de famílias consolidadas.

Todas as funções recebem listas de dicionários ``fields`` (ver
``prevalence.consolidate_fields``) e devolvem linhas com contagem,
denominador explícito e percentual.
"""
from __future__ import annotations

from collections import Counter
from statistics import mean, median


def pct(n: int, d: int) -> float:
    return round(100.0 * n / d, 1) if d else 0.0


def distribution(values: list, order: list | None = None, denominator: int | None = None) -> list[dict]:
    c = Counter(v for v in values if v is not None)
    d = denominator if denominator is not None else sum(c.values())
    keys = order if order else [k for k, _ in c.most_common()]
    rows = [{"categoria": k, "n": c.get(k, 0), "pct": pct(c.get(k, 0), d)} for k in keys]
    if order:
        rows += [{"categoria": k, "n": v, "pct": pct(v, d)} for k, v in c.most_common() if k not in order]
    return rows


def multi_distribution(lists: list[list], denominator: int, top: int | None = None) -> list[dict]:
    """Cada família contribui uma vez para cada categoria que contém (percentuais não somam 100%)."""
    c = Counter()
    for vals in lists:
        c.update(set(v for v in vals if v))
    items = c.most_common(top)
    return [{"categoria": k, "n": n, "pct": pct(n, denominator)} for k, n in items]


def concentration(counts: list[int]) -> dict:
    """CR4, CR8 (% das atribuições), HHI (0–10 000) e Gini sobre as contagens por grupo."""
    counts = sorted((c for c in counts if c > 0), reverse=True)
    total = sum(counts)
    if not total:
        return {"grupos": 0, "atribuicoes": 0, "CR4": 0.0, "CR8": 0.0, "HHI": 0.0, "Gini": 0.0}
    shares = [c / total for c in counts]
    hhi = sum((100 * s) ** 2 for s in shares)
    asc = sorted(counts)
    n = len(asc)
    gini = (2 * sum((i + 1) * x for i, x in enumerate(asc)) / (n * total) - (n + 1) / n) if n > 1 else 0.0
    return {
        "grupos": n, "atribuicoes": total,
        "CR4": round(100 * sum(shares[:4]), 1), "CR8": round(100 * sum(shares[:8]), 1),
        "HHI": round(hhi, 1), "Gini": round(gini, 3),
    }


def citations_summary(values: list) -> dict:
    v = [x for x in values if x is not None]
    if not v:
        return {"n_com_dado": 0}
    return {
        "n_com_dado": len(v), "n_citadas": sum(1 for x in v if x > 0),
        "pct_citadas": pct(sum(1 for x in v if x > 0), len(v)),
        "media": round(mean(v), 2), "mediana": median(v), "maximo": max(v),
    }


def internal_citation_edges(fams: list[dict]) -> list[tuple[str, str]]:
    """Rede de citações internas ao corpus (campo de patentes citadas do
    Derwent): aresta citante→citada quando a citada pertence a outra família."""
    owner = {}
    for f in fams:
        for n in f["fields"].get("all_numbers", []):
            owner[n] = f["key"]
    edges = set()
    for f in fams:
        for c in f["fields"].get("cited_patents", []):
            tgt = owner.get(c)
            if tgt and tgt != f["key"]:
                edges.add((f["key"], tgt))
    return sorted(edges)


def compute_all(fams: list[dict], periods: list[list[int]], top_n: int = 15) -> dict:
    """``fams`` = [{"key":..., "fields": {...}}]."""
    F = [f["fields"] for f in fams]
    n = len(F)
    with_prio = [x for x in F if x.get("priority_year")]
    period_order = [f"{a}–{b}" for a, b in periods]
    with_ipc = [x for x in F if x.get("ipc")]
    with_lens = [x for x in F if x.get("has_lens")]
    groups = multi_distribution([x.get("groups", []) for x in F], n)
    group_counts = Counter()
    for x in F:
        group_counts.update(set(x.get("groups", [])))
    edges = internal_citation_edges(fams)
    res = {
        "n": n,
        "periodos": {"denominador": len(with_prio),
                     "linhas": distribution([x["period"] for x in with_prio], period_order)},
        "anos": distribution([x["priority_year"] for x in with_prio],
                             sorted({x["priority_year"] for x in with_prio})),
        "jurisdicao_origem": {"denominador": sum(1 for x in F if x.get("origin_jurisdiction")),
                              "linhas": distribution([x.get("origin_jurisdiction") for x in F])},
        "fonte_jurisdicao": distribution([x.get("_origin", {}).get("origin_jurisdiction") for x in F]),
        "grupos": {"denominador": n, "linhas": groups[:top_n], "todas": groups,
                   "concentracao": concentration(list(group_counts.values()))},
        "inventores": {"denominador": n,
                       "linhas": multi_distribution([x.get("inventors", []) for x in F], n, top_n)},
        "ipc_subclasses": {"denominador": len(with_ipc),
                           "linhas": multi_distribution([x["ipc_subclasses"] for x in with_ipc], len(with_ipc), top_n)},
        "ipc_grupos": {"denominador": len(with_ipc),
                       "linhas": multi_distribution([x["ipc_main_groups"] for x in with_ipc], len(with_ipc), top_n)},
        "janela_recente": {"n": sum(1 for x in F if x.get("recent_window")), "denominador": n,
                           "pct": pct(sum(1 for x in F if x.get("recent_window")), n)},
        "situacao_juridica": {"denominador": len(with_lens),
                              "linhas": distribution([x.get("legal_status") for x in with_lens],
                                                     ["vigente", "em exame", "inativa"], len(with_lens))},
        "citacoes": citations_summary([x.get("cited_by_max") for x in with_lens]),
        "citacoes_top": sorted(
            ({"familia": f["key"], "titulo": f["fields"].get("title", ""),
              "citacoes": f["fields"].get("cited_by_max")}
             for f in fams if f["fields"].get("cited_by_max")),
            key=lambda r: -r["citacoes"])[:top_n],
        "rede_citacoes_internas": {"arestas": len(edges),
                                   "familias_envolvidas": len({a for e in edges for a in e})},
        "fontes": distribution([x.get("n_sources") for x in F], [1, 2, 3, 4]),
        "tipo_resumo": distribution([x.get("abstract_kind") for x in F]),
    }
    hits = [x.get("block_class_hits") for x in F if x.get("block_class_hits")]
    if hits:
        codes = list(hits[0].keys())
        rows = []
        for code in codes:
            only = sum(1 for h in hits if h[code] and not any(h[c] for c in codes if c != code))
            rows.append({"codigo": code, "n_com_codigo": sum(1 for h in hits if h[code]),
                         "n_exclusivo": only})
        res["bloco_classificacao"] = {"denominador": n, "linhas": rows,
                                      "sem_ipc": n - len(with_ipc)}
    return res
