"""Exporta o estudo inteiro (configuração + trabalho manual) para um JSON.

    python manage.py exportar_estudo 1 -o estudo_1.json

O JSON é o espelho de ``importar_estudo``: é o backup portátil das decisões,
ligações manuais, dicionários e tesauro, que são o que uma nova coleta herda.
O banco SQLite e a pasta ``media/`` não são versionados — este arquivo é o que
sobrevive a uma troca de máquina.
"""
import json
from pathlib import Path

from django.core.management.base import BaseCommand
from django.utils import timezone

from studies import models as m
from studies import services

FORMATO = "patentometria/estudo/1"


def dump_study(study: m.Study) -> dict:
    rounds = []
    for r in study.rounds.all():
        rounds.append({
            "rotulo": r.label,
            "data_coleta": r.collection_date.isoformat() if r.collection_date else None,
            "observacoes": r.notes,
            "procedencia": services.provenance(r),
            "resumo": r.run_summary,
        })
    return {
        "formato": FORMATO,
        "gerado_em": timezone.now().isoformat(timespec="seconds"),
        "estudo": {"nome": study.name, "descricao": study.description, "config": study.cfg},
        "decisoes": [{"anchor": d.anchor, "numbers": d.numbers, "stage1": d.stage1,
                      "stage1_reason": d.stage1_reason, "stage2": d.stage2,
                      "stage2_reason": d.stage2_reason, "stratum": d.stratum,
                      "notes": d.notes} for d in study.decisions.all()],
        "ligacoes": [{"number_a": l.number_a, "number_b": l.number_b, "reason": l.reason}
                     for l in study.manual_links.all()],
        "depositantes": [{"raw_example": a.raw_example, "harmonized": a.harmonized,
                          "group": a.group, "is_person": a.is_person, "note": a.note}
                         for a in study.applicant_aliases.all()],
        "inventores": [{"raw_example": a.raw_example, "standard": a.standard, "note": a.note}
                       for a in study.inventor_aliases.all()],
        "tesauro": [{"label": t.label, "replace_by": t.replace_by, "category": t.category,
                     "note": t.note} for t in study.thesaurus.all()],
        "rodadas": rounds,
    }


class Command(BaseCommand):
    help = "Exporta configuração e trabalho manual de um estudo para JSON (backup/transporte)."

    def add_arguments(self, p):
        p.add_argument("estudo", type=int)
        p.add_argument("-o", "--saida", required=True)

    def handle(self, *a, **o):
        study = m.Study.objects.get(pk=o["estudo"])
        payload = dump_study(study)
        out = Path(o["saida"])
        out.write_text(json.dumps(payload, ensure_ascii=False, indent=2), encoding="utf-8")
        n = {k: len(payload[k]) for k in ("decisoes", "ligacoes", "depositantes", "inventores", "tesauro")}
        self.stdout.write(self.style.SUCCESS(f"{out} — {n}, {len(payload['rodadas'])} rodada(s)"))
