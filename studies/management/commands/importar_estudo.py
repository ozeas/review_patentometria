"""Importa um JSON gerado por ``exportar_estudo``.

    python manage.py importar_estudo estudo_1.json                 # atualiza o estudo de mesmo nome
    python manage.py importar_estudo estudo_1.json --estudo 2      # aplica no estudo 2
    python manage.py importar_estudo estudo_1.json --renomear "GC x petróleo (restaurado)"

Decisões e ligações são casadas por número de publicação, de modo que
reimportar o mesmo arquivo não duplica nada. ``--substituir`` apaga antes as
decisões, ligações, dicionários e tesauro do estudo de destino.
"""
import json
from pathlib import Path

from django.core.management.base import BaseCommand, CommandError
from django.db import transaction

from studies import models as m

FORMATO = "patentometria/estudo/1"


class Command(BaseCommand):
    help = "Restaura configuração e trabalho manual de um estudo a partir de JSON."

    def add_arguments(self, p):
        p.add_argument("arquivo")
        p.add_argument("--estudo", type=int, help="id do estudo de destino (padrão: mesmo nome do JSON)")
        p.add_argument("--renomear", help="nome novo para o estudo criado/atualizado")
        p.add_argument("--substituir", action="store_true",
                       help="apaga decisões, ligações, dicionários e tesauro antes de importar")

    @transaction.atomic
    def handle(self, *a, **o):
        path = Path(o["arquivo"])
        if not path.exists():
            raise CommandError(f"Arquivo não encontrado: {path}")
        payload = json.loads(path.read_text(encoding="utf-8"))
        if payload.get("formato") != FORMATO:
            raise CommandError(f"Formato não reconhecido: {payload.get('formato')!r} (esperado {FORMATO})")
        dados = payload["estudo"]
        if o["estudo"]:
            study = m.Study.objects.get(pk=o["estudo"])
        else:
            # com --renomear o estudo é procurado pelo nome novo, para que
            # reimportar o mesmo arquivo não crie uma cópia a cada execução
            alvo = o["renomear"] or dados["nome"]
            study, _ = m.Study.objects.get_or_create(name=alvo)
        if o["renomear"]:
            study.name = o["renomear"]
        study.description = dados.get("descricao", study.description)
        study.config = dados["config"]
        study.save()

        if o["substituir"]:
            study.decisions.all().delete()
            study.manual_links.all().delete()
            study.applicant_aliases.all().delete()
            study.inventor_aliases.all().delete()
            study.thesaurus.all().delete()

        dec_n = 0
        index = {tuple(sorted(d.numbers)): d for d in study.decisions.all()}
        for d in payload.get("decisoes", []):
            nums = sorted(d.get("numbers") or [])
            obj = index.get(tuple(nums))
            if obj is None:
                obj = m.Decision(study=study, anchor=d.get("anchor") or (nums[0] if nums else ""), numbers=nums)
            for campo in ("stage1", "stage1_reason", "stage2", "stage2_reason", "stratum", "notes"):
                setattr(obj, campo, d.get(campo) or "")
            obj.save()
            index[tuple(nums)] = obj
            dec_n += 1

        link_n = 0
        existentes = {(l.number_a, l.number_b) for l in study.manual_links.all()}
        for l in payload.get("ligacoes", []):
            par = (l["number_a"], l["number_b"])
            if par in existentes:
                continue
            m.ManualLink.objects.create(study=study, number_a=par[0], number_b=par[1],
                                        reason=l.get("reason", ""))
            existentes.add(par)
            link_n += 1

        from studies import services
        for a in payload.get("depositantes", []):
            services.upsert_applicant(study, a["raw_example"], a.get("harmonized", ""),
                                      a.get("group", ""), a.get("is_person", False), a.get("note", ""))
        for a in payload.get("inventores", []):
            services.upsert_inventor(study, a["raw_example"], a.get("standard", ""), a.get("note", ""))

        tes_n = 0
        for t in payload.get("tesauro", []):
            m.ThesaurusEntry.objects.update_or_create(
                study=study, label=t["label"],
                defaults={"replace_by": t.get("replace_by", ""), "category": t.get("category", ""),
                          "note": t.get("note", "")})
            tes_n += 1

        self.stdout.write(self.style.SUCCESS(
            f"Estudo {study.id} «{study.name}» — decisões {dec_n}, ligações {link_n}, "
            f"depositantes {len(payload.get('depositantes', []))}, "
            f"inventores {len(payload.get('inventores', []))}, tesauro {tes_n}. "
            "Reexecute a consolidação para aplicar."))
