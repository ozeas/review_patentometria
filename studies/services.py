"""Ponte entre o núcleo do pipeline (``core``) e o banco de dados."""
from __future__ import annotations

import json
import re
from datetime import date
from hashlib import sha256 as _sha256
from pathlib import Path

from django.db import transaction
from django.utils import timezone

from core import consolidate as ccons
from core.diagnostics import diagnosticar
from core.normalize import has_cjk, name_key, pinyin_name
from core.parsers import detect_source, parse_bytes, decode
from core.pipeline import Decision as CoreDecision
from core.pipeline import PipelineResult, run
from core.prevalence import Dictionaries
from core.queries import consultas_divergem
from core.records import Record as CoreRecord

from . import models as m


# ------------------------------------------------------------------ ingestão
def guess_from_filename(name: str, recortes: dict[str, str] | None = None) -> tuple[str | None, str]:
    """Deduz base e recorte pelo nome do arquivo.

    'espacenet_BR.csv' → ('espacenet', 'BR'); 'lens_nucleo.csv' → ('lens', 'nucleo').
    Os rótulos de recorte vêm da configuração do estudo (``config['recortes']``);
    o que não casar cai no recorte principal.
    """
    from core.sources import base_pelo_nome

    low = Path(name).stem.lower()
    src = base_pelo_nome(name)
    recortes = recortes or {"nucleo": "conjunto principal"}
    principal = next(iter(recortes), "nucleo")
    for rotulo in recortes:
        if rotulo == principal:
            continue
        if re.search(rf"(^|[_\-.\s]){re.escape(rotulo.lower())}($|[_\-.\s])", low):
            return src, rotulo
    return src, principal


@transaction.atomic
def ingest(round_: m.Round, uploaded, source: str | None = None, recorte: str | None = None,
           query_text: str = "", executed_at: str = "", recortes: dict[str, str] | None = None) -> m.SourceFile:
    data = uploaded.read()
    recortes = recortes or round_.study.cfg.get("recortes")
    g_src, g_rec = guess_from_filename(uploaded.name, recortes)
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
    """Registro de procedência: consulta **declarada**, data/hora e hash de cada
    exportação, mais a consulta que o arquivo imprime (evidência, campo à parte).

    Só a declarada conta como registro: o texto lido do cabeçalho da exportação
    é evidência do que foi executado e nunca substitui a declaração.
    """
    files = list(round_.files.all().order_by("recorte", "source"))
    rows = []
    for f in files:
        declarada = (f.query_text or "").strip()
        no_arquivo = (f.query_no_arquivo or "").strip()
        rows.append({"arquivo": f.original_name, "base": f.source, "recorte": f.recorte,
                     "registros": f.n_records, "sha256": f.sha256, "executado_em": f.executed_at,
                     "consulta_declarada": declarada, "consulta_no_arquivo": no_arquivo,
                     "consulta_divergente": consultas_divergem(declarada, no_arquivo),
                     "consulta_registrada": bool(declarada)})
    return {
        "arquivos": rows,
        "n_arquivos": len(rows),
        "sem_consulta": [r["arquivo"] for r in rows if not r["consulta_registrada"]],
        "consulta_divergente": [r["arquivo"] for r in rows if r["consulta_divergente"]],
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
    round_.cache = {"inputs_version": inputs_version(round_), "prisma": result.prisma(),
                    "br": result.br, "n_suggestions": len(result.suggestions),
                    "procedencia": round_.run_summary["procedencia"],
                    "diagnostico": diagnosticar(result),
                    "ligacoes": {"aplicadas": sorted({i for f in result.families
                                                      for i in f["family"].manual_link_ids}),
                                 "sem_correspondencia": sorted(ml.id for ml in result.consolidation.unmatched_links),
                                 "sugestoes": result.suggestions}}
    round_.save(update_fields=["last_run", "run_summary", "cache"])
    return result


# ------------------------------------------------------------------ cache
def inputs_version(round_: m.Round) -> str:
    """Hash de tudo que entra no pipeline.

    Config, arquivos, decisões, ligações, dicionários e tesauro: se qualquer
    insumo mudar, o hash muda e o cache é refeito. Invalidar por hash (e não por
    evento) evita número velho quando alguém esquece de limpar o cache.
    """
    h = _sha256()
    h.update(json.dumps(round_config(round_), sort_keys=True, default=str).encode())
    for f in round_.files.order_by("id"):
        h.update(f"{f.id}:{f.sha256}:{f.n_records}:{f.recorte}".encode())
    study = round_.study
    for d in study.decisions.order_by("id"):
        h.update(f"d{d.id}:{d.updated.isoformat()}:{d.stage1}:{d.stage2}:{d.stratum}:"
                 f"{','.join(d.numbers or [])}".encode())
    for l in study.manual_links.order_by("id"):
        h.update(f"l{l.id}:{l.number_a}:{l.number_b}".encode())
    for a in study.applicant_aliases.order_by("id"):
        h.update(f"a{a.id}:{a.raw_key}:{a.harmonized}:{a.group}".encode())
    for i in study.inventor_aliases.order_by("id"):
        h.update(f"i{i.id}:{i.raw_key}:{i.standard}".encode())
    for t in study.thesaurus.order_by("id"):
        h.update(f"t{t.id}:{t.label}:{t.replace_by}".encode())
    return h.hexdigest()


class Resumo:
    """Fachada leve sobre o resultado guardado: prisma e BR sem recalcular o pipeline."""

    def __init__(self, round_: m.Round):
        self.round = round_
        self.dados = round_.cache or {}

    def prisma(self) -> dict:
        return self.dados.get("prisma", {})

    @property
    def br(self):
        return self.dados.get("br")

    @property
    def n_suggestions(self) -> int:
        return self.dados.get("n_suggestions", 0)

    @property
    def procedencia(self) -> dict:
        return self.dados.get("procedencia") or {}

    @property
    def diagnostico(self) -> dict:
        return self.dados.get("diagnostico") or {}

    @property
    def ligacoes(self) -> dict:
        return self.dados.get("ligacoes") or {"aplicadas": [], "sem_correspondencia": [], "sugestoes": []}

    def indicators(self, subset: str = "final", stratum: str | None = None) -> dict:
        return indicators(self.round, subset, stratum)


def resumo(round_: m.Round) -> Resumo:
    """Resumo da rodada, refeito só quando algum insumo mudou (``inputs_version``)."""
    if (round_.cache or {}).get("inputs_version") != inputs_version(round_):
        run_round(round_)
        round_.refresh_from_db(fields=["cache", "run_summary", "last_run"])
    return Resumo(round_)


# ------------------------------------------------------------------ indicadores sem pipeline
def _familias_db(round_: m.Round, subset: str = "unificada", stratum: str | None = None) -> list[dict]:
    """Famílias gravadas pela última execução, filtradas por conjunto e estrato."""
    fams = list(round_.families.all())
    dec = decisions_map(round_.study, fams)
    out = []
    for f in fams:
        d = dec.get(f.key)
        st1 = d.stage1 if d else ""
        st2 = d.stage2 if d else ""
        if subset == "etapa1" and st1 != "incluir":
            continue
        if subset == "final" and not (st1 == "incluir" and st2 == "incluir"):
            continue
        if stratum and not (d and d.stratum == stratum):
            continue
        out.append({"key": f.key, "fields": {**f.fields, "_origin": f.origin}})
    return out


def indicators(round_: m.Round, subset: str = "final", stratum: str | None = None) -> dict:
    """Indicadores calculados sobre as famílias gravadas (não roda o pipeline)."""
    from core import indicators as ind

    cfg = round_config(round_)
    return ind.compute_all(_familias_db(round_, subset, stratum), cfg["periods"], cfg.get("top_n", 15))


def contagem_final(round_: m.Round) -> int:
    return len(_familias_db(round_, "final"))


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
