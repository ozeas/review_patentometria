"""Orquestração do pipeline: registros → famílias → campos → elegibilidade
→ estratos → indicadores e fluxo PRISMA."""
from __future__ import annotations

from dataclasses import dataclass, field
from datetime import date

from . import indicators as ind
from .consolidate import ConsolidationResult, ManualLink, consolidate, map_subset_to_families, suggest_links
from .lexical import compile_blocks, lexical_profile
from .prevalence import DEFAULT_PREVALENCE, Dictionaries, consolidate_fields
from .records import Record

DEFAULT_CONFIG = {
    "core_recorte": "nucleo",
    "utility_kinds": ["U"],
    "prio_link_min_digits": 8,
    "periods": [[1971, 1999], [2000, 2009], [2010, 2014], [2015, 2019], [2020, 2026]],
    "window_months": 36,
    "collection_date": "2026-10-15",
    "prevalence": DEFAULT_PREVALENCE,
    "blocks": [
        {"name": "(i) cromatografia gasosa",
         "terms": ["gas chromatography", "gas chromatograph", "GCxGC", "GC-MS", "GC-FID"]},
        {"name": "(ii) petróleo e poço",
         "terms": ["crude oil", "reservoir fluid", "borehole", "wellbore", "downhole",
                   "drilling fluid", "geochemical"]},
    ],
    "classification_block": ["G01N", "C10G", "E21B 49"],
    "stage1": {
        "label": "Relação entre cromatografia gasosa e petróleo",
        "exclusion_reasons": ["Falso positivo lexical", "Óleo não petrolífero",
                              "Petróleo não é objeto da análise"],
    },
    "stage2": {
        "label": "Segmento upstream",
        "inclusion_segments": ["Exploração", "Perfuração e avaliação de formação",
                               "Reservatório e produção"],
        "exclusion_reasons": ["Downstream", "Transversal", "Midstream", "Ambiental/forense"],
    },
    "strata": [
        {"code": "C1", "name": "núcleo",
         "definition": "A cromatografia gasosa é nomeada no título e constitui o objeto da invenção."},
        {"code": "C2", "name": "aplicado",
         "definition": "A cromatografia gasosa é o instrumento de um método voltado a outra finalidade."},
        {"code": "C3", "name": "periférico",
         "definition": "Relação indireta com a cromatografia gasosa ou pertinência a confirmar."},
    ],
    "top_n": 15,
}


@dataclass
class Decision:
    """Decisão de elegibilidade de uma família, ancorada em seus números."""

    numbers: list[str]
    stage1: str = ""  # "incluir" | "excluir" | ""
    stage1_reason: str = ""
    stage2: str = ""  # "incluir" | "excluir" | ""
    stage2_reason: str = ""  # segmento (inclusão) ou motivo (exclusão)
    stratum: str = ""
    notes: str = ""
    id: int | None = None


@dataclass
class PipelineResult:
    config: dict
    consolidation: ConsolidationResult
    families: list[dict]  # [{"key", "fields", "origin", "decision", "lexical", "records"}]
    br: dict | None = None
    suggestions: list[dict] = field(default_factory=list)

    @property
    def stats(self) -> dict:
        return self.consolidation.stats()

    def stage(self, name: str) -> list[dict]:
        if name == "unificada":
            return self.families
        if name == "etapa1":
            return [f for f in self.families if f["decision"] and f["decision"].stage1 == "incluir"]
        if name == "final":
            return [f for f in self.families if f["decision"] and f["decision"].stage1 == "incluir"
                    and f["decision"].stage2 == "incluir"]
        raise KeyError(name)

    def prisma(self) -> dict:
        s = self.stats
        fams = self.families
        dec = [f["decision"] for f in fams]
        st1_ex = [d for d in dec if d and d.stage1 == "excluir"]
        st1_in = [d for d in dec if d and d.stage1 == "incluir"]
        st2_ex = [d for d in st1_in if d.stage2 == "excluir"]
        final = [d for d in st1_in if d.stage2 == "incluir"]

        def _count(ds, attr, labels):
            out = {k: 0 for k in labels}
            for d in ds:
                v = getattr(d, attr) or "(sem motivo)"
                out[v] = out.get(v, 0) + 1
            return out

        cfg = self.config
        return {
            **s,
            "pending_stage1": sum(1 for d in dec if not d or not d.stage1),
            "stage1_excluded": len(st1_ex),
            "stage1_excluded_by_reason": _count(st1_ex, "stage1_reason", cfg["stage1"]["exclusion_reasons"]),
            "stage1_included": len(st1_in),
            "pending_stage2": sum(1 for d in st1_in if not d.stage2),
            "stage2_excluded": len(st2_ex),
            "stage2_excluded_by_reason": _count(st2_ex, "stage2_reason", cfg["stage2"]["exclusion_reasons"]),
            "final": len(final),
            "final_by_segment": _count(final, "stage2_reason", cfg["stage2"]["inclusion_segments"]),
            "strata": _count(final, "stratum", [x["code"] for x in cfg["strata"]]),
        }

    def indicators(self, subset: str = "final", stratum: str | None = None) -> dict:
        fams = self.stage(subset)
        if stratum:
            fams = [f for f in fams if f["decision"] and f["decision"].stratum == stratum]
        payload = [{"key": f["key"], "fields": {**f["fields"], "_origin": f["origin"]}} for f in fams]
        return ind.compute_all(payload, self.config["periods"], self.config.get("top_n", 15))


def match_decision(numbers: list[str], decisions: list[Decision]) -> Decision | None:
    nums = set(numbers)
    best, overlap = None, 0
    for d in decisions:
        k = len(nums & set(d.numbers))
        if k > overlap:
            best, overlap = d, k
    return best


def run(
    records: list[Record],
    *,
    config: dict | None = None,
    dictionaries: Dictionaries | None = None,
    manual_links: list[ManualLink] | None = None,
    decisions: list[Decision] | None = None,
) -> PipelineResult:
    cfg = {**DEFAULT_CONFIG, **(config or {})}
    core = [r for r in records if r.recorte == cfg["core_recorte"]]
    other = [r for r in records if r.recorte != cfg["core_recorte"]]
    res = consolidate(core, utility_kinds=tuple(cfg["utility_kinds"]),
                      prio_min_digits=cfg["prio_link_min_digits"], manual_links=manual_links)
    cdate = date.fromisoformat(cfg["collection_date"]) if cfg.get("collection_date") else None
    blocks = compile_blocks(cfg.get("blocks", []))
    fams = []
    for f in res.families:
        consolidate_fields(f, prevalence=cfg.get("prevalence"), dictionaries=dictionaries,
                           periods=cfg["periods"], collection_date=cdate,
                           window_months=cfg["window_months"],
                           block_codes=cfg.get("classification_block"))
        lex = lexical_profile(f.fields.get("original_title") or f.fields.get("title", ""),
                              f.fields.get("abstract", ""), blocks)
        f.fields["lexical_level"] = lex["level"]
        fams.append({
            "key": f.key, "fields": f.fields, "origin": f.origin, "lexical": lex,
            "decision": match_decision(f.numbers, decisions or []),
            "records": f.records, "family": f,
        })
    br = None
    if other:
        sub = map_subset_to_families(other, res, cfg["prio_link_min_digits"])
        by_key = {f["key"]: f for f in fams}
        rows = []
        for k, v in sub["mapping"].items():
            sf = v["family"]
            core_keys = v["core_families"]
            in_final = any(
                by_key[c]["decision"] and by_key[c]["decision"].stage1 == "incluir"
                and by_key[c]["decision"].stage2 == "incluir" for c in core_keys if c in by_key)
            apps = sorted({a for r in sf.records for a in r.applicants})
            rows.append({"familia_recorte": k, "fontes": sf.sources, "numeros": sf.numbers,
                         "familias_nucleo": core_keys, "na_base_final": in_final,
                         "depositantes": apps})
        br = {"stats": sub["subset_result"].stats(), "families": rows,
              "in_core": sum(1 for r in rows if r["familias_nucleo"]),
              "in_final": sum(1 for r in rows if r["na_base_final"])}
    harmonize = None
    if dictionaries:
        harmonize = lambda n: dictionaries.applicant(n)[1].upper()  # noqa: E731
    sugg = suggest_links(res.families, harmonize=harmonize)
    return PipelineResult(cfg, res, fams, br, sugg)
