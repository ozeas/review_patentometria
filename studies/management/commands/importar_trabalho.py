"""Importa trabalho manual para um estudo.

    python manage.py importar_trabalho 1 decisoes decisoes.csv
    python manage.py importar_trabalho 1 depositantes depositantes.xlsx
    python manage.py importar_trabalho 1 inventores inventores.csv
    python manage.py importar_trabalho 1 ligacoes ligacoes.csv
    python manage.py importar_trabalho 1 tesauro thesaurus.txt
"""
from pathlib import Path

from django.core.files import File
from django.core.management.base import BaseCommand, CommandError

from studies import models as m
from studies import tabular


class Command(BaseCommand):
    help = "Importa decisões, dicionários, ligações ou tesauro para um estudo."

    def add_arguments(self, p):
        p.add_argument("estudo", type=int)
        p.add_argument("tipo", choices=["decisoes", "depositantes", "inventores", "ligacoes", "tesauro"])
        p.add_argument("arquivo")
        p.add_argument("--substituir", action="store_true", help="(tesauro) substitui as entradas atuais")

    def handle(self, *a, **o):
        study = m.Study.objects.get(pk=o["estudo"])
        path = Path(o["arquivo"])
        if not path.exists():
            raise CommandError(f"Arquivo não encontrado: {path}")
        if o["tipo"] == "tesauro":
            n = tabular.import_thesaurus(study, path.read_text(encoding="utf-8-sig"), replace=o["substituir"])
            self.stdout.write(self.style.SUCCESS(f"{n} entradas do tesauro"))
            return
        with path.open("rb") as fh:
            rows = tabular.read_table(File(fh, name=path.name))
        fn = {"decisoes": tabular.import_decisions, "depositantes": tabular.import_applicants,
              "inventores": tabular.import_inventors, "ligacoes": tabular.import_links}[o["tipo"]]
        self.stdout.write(self.style.SUCCESS(str(fn(study, rows))))
