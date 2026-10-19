"""Declara a consulta registrada de uma exportação.

    python manage.py registrar_consulta 3 --texto "G01N30 AND oil"
    python manage.py registrar_consulta 3 --de consultas/espacenet_2026-10-15.txt

É o único caminho previsto para preencher ``query_text``: o conteúdo do arquivo
de resultado nunca é lido aqui — o texto vem do histórico da base, colado pelo
analista.
"""
from pathlib import Path

from django.core.management.base import BaseCommand, CommandError

from studies import models as m


class Command(BaseCommand):
    help = "Grava a consulta declarada de um arquivo de exportação."

    def add_arguments(self, p):
        p.add_argument("arquivo", type=int, help="id do SourceFile")
        grupo = p.add_mutually_exclusive_group(required=True)
        grupo.add_argument("--texto", help="consulta colada na linha de comando")
        grupo.add_argument("--de", help="arquivo de texto com a consulta")

    def handle(self, *a, **o):
        sf = m.SourceFile.objects.get(pk=o["arquivo"])
        if o["de"]:
            path = Path(o["de"])
            if not path.exists():
                raise CommandError(f"Arquivo não encontrado: {path}")
            texto = path.read_text(encoding="utf-8-sig")
        else:
            texto = o["texto"]
        sf.query_text = " ".join((texto or "").split())
        if not sf.query_text:
            raise CommandError("Consulta vazia — nada foi gravado.")
        sf.save(update_fields=["query_text"])
        self.stdout.write(self.style.SUCCESS(
            f"{sf.original_name}: consulta declarada ({len(sf.query_text)} caracteres)"))
