"""Ponte entre o núcleo do pipeline (``core``) e o banco de dados."""
from __future__ import annotations

import re
from datetime import date
from hashlib import sha256 as _sha256
from pathlib import Path

from django.db import transaction
from django.utils import timezone

from core import consolidate as ccons
from core.normalize import has_cjk, name_key, pinyin_name
from core.parsers import detect_source, parse_bytes, decode
from core.pipeline import Decision as CoreDecision
from core.pipeline import PipelineResult, run
from core.prevalence import Dictionaries
from core.records import Record as CoreRecord

from . import models as m


# ------------------------------------------------------------------ ingestão
def guess_from_filename(name: str) -> tuple[str | None, str]:
    """'espacenet_BR.csv' → ('espacenet', 'BR'); 'lens_nucleo.csv' → ('lens', 'nucleo')."""
    low = Path(name).stem.lower()
    src = None
    for key, alias in (("lens", "lens"), ("espacenet", "espacenet"), ("google", "google"),
                       ("derwent", "derwent"), ("darwent", "derwent"), ("clarivate", "derwent"),
                       ("wos", "derwent")):
        if key in low:
            src = alias
            break
    rec = "BR" if re.search(r"(^|[_\-\s])br($|[_\-\s])", low) else "nucleo"
    return src, rec


@transaction.atomic
def ingest(round_: m.Round, uploaded, source: str | None = None, recorte: str | None = None,
           query_text: str = "", executed_at: str = "") -> m.SourceFile:
    data = uploaded.read()
    g_src, g_rec = guess_from_filename(uploaded.name)
    text = decode(data)
    src = source or detect_source(text) or g_src
    rec = recorte or g_rec
    src, records = parse_bytes(data, src, rec)
    uploaded.seek(0)
    sf = m.SourceFile.objects.create(round=round_, source=src, recorte=rec, file=uploaded,
                                     original_name=Path(uploaded.name).name,
                                     sha256=_sha256(data).hexdigest(),
                                     query_text=query_text,
                                     executed_at=executed_at, n_records=len(records))
    m.Record.objects.bulk_create([
        m.Record(round=round_, source_file=sf, source=r.source, recorte=r.recorte, row=r.row,
                 data=r.to_dict()) for r in records
    ])
    return sf


def load_records(round_: m.Round) -> list[CoreRecord]:
    return [CoreRecord.from_dict(r.data) for r in round_.records.all().order_by("source", "recorte", "row")]


# ------------------------------------------------------------------ insumos do estudo
def dictionaries_for(study: m.Study) -> Dictionaries:
    return Dictionaries(
        applicants={a.raw_key: (a.harmonized, a.group or a.harmonized) for a in study.applicant_aliases.all()},
        inventors={i.raw_key: i.standard for i in study.inventor_aliases.all()},
    )


def manual_links_for(study: m.Study) -> list[ccons.ManualLink]:
    return [ccons.ManualLink(ml.id, ml.number_a, ml.number_b, ml.reason) for ml in study.manual_links.all()]


def decisions_for(study: m.Study) -> list[CoreDecision]:
    return [CoreDecision(numbers=d.numbers, stage1=d.stage1, stage1_reason=d.stage1_reason,
                         stage2=d.stage2, stage2_reason=d.stage2_reason, stratum=d.stratum,
                         notes=d.notes, id=d.id) for d in study.decisions.all()]


def round_config(round_: m.Round) -> dict:
    cfg = round_.study.cfg
    if round_.collection_date:
        cfg["collection_date"] = round_.collection_date.isoformat()
    return cfg


# ------------------------------------------------------------------ procedência
def provenance(round_: m.Round) -> dict:
    """Registro de procedência da rodada: consulta, data/hora e hash de cada
    exportação, mais o que está faltando para a rodada ser rastreável."""
    files = list(round_.files.all().order_by("recorte", "source"))
    rows = [{"arquivo": f.original_name, "base": f.source, "recorte": f.recorte,
             "registros": f.n_records, "sha256": f.sha256, "executado_em": f.executed_at,
             "consulta_registrada": bool(f.query_text.strip()),
             "consulta": f.query_text.strip()} for f in files]
    return {
        "arquivos": rows,
        "n_arquivos": len(rows),
        "sem_consulta": [r["arquivo"] for r in rows if not r["consulta_registrada"]],
        "sem_hash": [r["arquivo"] for r in rows if not r["sha256"]],
        "sem_data_execucao": [r["arquivo"] for r in rows if not r["executado_em"]],
        "data_coleta": round_.collection_date.isoformat() if round_.collection_date else None,
    }


def compute(round_: m.Round) -> PipelineResult:
    """Executa o pipeline em memória (rápido para alguns milhares de registros)."""
    study = round_.study
    result = run(load_records(round_), config=round_config(round_), dictionaries=dictionaries_for(study),
                 manual_links=manual_links_for(study), decisions=decisions_for(study))
    rejected = {frozenset((r.number_a, r.number_b)) for r in study.rejected_suggestions.all()}
    result.suggestions = [s for s in result.suggestions
                          if frozenset((s["number_a"], s["number_b"])) not in rejected]
    return result


@transaction.atomic
def run_round(round_: m.Round) -> PipelineResult:
    result = compute(round_)
    cons = result.consolidation
    excluded = {r.record_id for r in cons.excluded_utility}
    rec_map = cons.record_family
    for rec in round_.records.all():
        rid = rec.record_id
        rec.excluded_utility = rid in excluded
        rec.family_key = rec_map.get(rid, "")
        rec.save(update_fields=["excluded_utility", "family_key"])
    round_.families.all().delete()
    m.Family.objects.bulk_create([
        m.Family(round=round_, key=f["key"], anchor=f["family"].anchor, numbers=f["family"].numbers,
                 fields=f["fields"], origin=f["origin"], lexical=f["lexical"],
                 n_sources=f["fields"]["n_sources"], title=f["fields"].get("title", ""))
        for f in result.families
    ])
    round_.last_run = timezone.now()
    round_.run_summary = {"prisma": result.prisma(), "br": _br_summary(result),
                          "n_suggestions": len(result.suggestions),
                          "procedencia": provenance(round_)}
    round_.save(update_fields=["last_run", "run_summary"])
    return result


def _br_summary(result: PipelineResult):
    if not result.br:
        return None
    return {"families": len(result.br["families"]), "in_core": result.br["in_core"],
            "in_final": result.br["in_final"], "by_source": result.br["stats"]["identified_by_source"]}


# ------------------------------------------------------------------ decisões
def decision_for_family(study: m.Study, numbers: list[str]) -> m.Decision | None:
    nums = set(numbers)
    best, overlap = None, 0
    for d in study.decisions.all():
        k = len(nums & set(d.numbers))
        if k > overlap:
            best, overlap = d, k
    return best


def save_decision(study: m.Study, family: m.Family, **values) -> m.Decision:
    d = decision_for_family(study, family.numbers)
    if d is None:
        d = m.Decision(study=study, anchor=family.anchor, numbers=family.numbers)
    else:
        d.numbers = sorted(set(d.numbers) | set(family.numbers))
    for k, v in values.items():
        setattr(d, k, v or "")
    if d.stage1 == "excluir":
        d.stage2 = d.stage2_reason = d.stratum = ""
    if d.stage1 != "excluir" and d.stage1 != "incluir":
        d.stage1_reason = ""
    if d.stage1 == "incluir":
        d.stage1_reason = ""
    if d.stage2 == "excluir":
        d.stratum = ""
    d.save()
    return d


def decisions_map(study: m.Study, families) -> dict[str, m.Decision | None]:
    decs = list(study.decisions.all())
    index: dict[str, m.Decision] = {}
    for d in decs:
        for n in d.numbers:
            index.setdefault(n, d)
    out = {}
    for f in families:
        hits = {}
        for n in f.numbers:
            if n in index:
                hits[index[n].id] = hits.get(index[n].id, 0) + 1
        if hits:
            best = max(hits, key=hits.get)
            out[f.key] = next(d for d in decs if d.id == best)
        else:
            out[f.key] = None
    return out


# ------------------------------------------------------------------ dicionários
def applicant_inventory(round_: m.Round) -> list[dict]:
    """Grafias de depositantes da rodada (na base de prevalência), com o
    número de famílias e o mapeamento atual."""
    study = round_.study
    aliases = {a.raw_key: a for a in study.applicant_aliases.all()}
    counts: dict[str, dict] = {}
    for f in round_.families.all():
        for raw in f.fields.get("applicants_raw", []):
            k = name_key(raw)
            row = counts.setdefault(k, {"raw_key": k, "raw": raw, "families": set(), "cjk": has_cjk(raw)})
            row["families"].add(f.key)
    out = []
    for k, row in counts.items():
        a = aliases.get(k)
        out.append({**row, "n": len(row["families"]), "families": sorted(row["families"]),
                    "alias": a, "harmonized": a.harmonized if a else "", "group": a.group if a else ""})
    out.sort(key=lambda r: (-r["n"], r["raw"]))
    return out


def inventor_inventory(round_: m.Round, only_cjk: bool = True) -> list[dict]:
    study = round_.study
    aliases = {a.raw_key: a for a in study.inventor_aliases.all()}
    counts: dict[str, dict] = {}
    for f in round_.families.all():
        for raw in f.fields.get("inventors_raw", []):
            if only_cjk and not has_cjk(raw):
                continue
            k = name_key(raw)
            row = counts.setdefault(k, {"raw_key": k, "raw": raw, "families": set()})
            row["families"].add(f.key)
    out = []
    for k, row in counts.items():
        a = aliases.get(k)
        out.append({**row, "n": len(row["families"]), "families": sorted(row["families"]),
                    "alias": a, "standard": a.standard if a else "",
                    "suggestion": pinyin_name(row["raw"]) if has_cjk(row["raw"]) else row["raw"]})
    out.sort(key=lambda r: (-r["n"], r["raw"]))
    return out


def upsert_applicant(study, raw, harmonized, group="", is_person=False, note=""):
    k = name_key(raw)
    obj, _ = m.ApplicantAlias.objects.update_or_create(
        study=study, raw_key=k,
        defaults={"raw_example": raw, "harmonized": harmonized.strip(), "group": group.strip(),
                  "is_person": is_person, "note": note})
    return obj


def upsert_inventor(study, raw, standard, note=""):
    k = name_key(raw)
    obj, _ = m.InventorAlias.objects.update_or_create(
        study=study, raw_key=k, defaults={"raw_example": raw, "standard": standard.strip(), "note": note})
    return obj


def parse_date_or_none(s: str):
    try:
        return date.fromisoformat(s)
    except (TypeError, ValueError):
        return None
