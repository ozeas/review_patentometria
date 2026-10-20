from pathlib import Path

from django.core.management.base import BaseCommand

from studies import export
from studies import models as m


class Command(BaseCommand):
    help = "Gera a planilha base (.xlsx) e, opcionalmente, o pacote do VOSviewer de uma rodada."

    def add_arguments(self, p):
        p.add_argument("rodada", type=int)
        p.add_argument("-o", "--saida", default=None)
        p.add_argument("--vos", default=None, help="caminho do .zip do VOSviewer")

    def handle(self, *a, **o):
        rnd = m.Round.objects.get(pk=o["rodada"])
        out = Path(o["saida"] or f"base_patentometria_rodada{rnd.id}.xlsx")
        out.write_bytes(export.workbook_bytes(rnd))
        self.stdout.write(self.style.SUCCESS(f"Planilha: {out}"))
        if o["vos"]:
            Path(o["vos"]).write_bytes(export.vos_package(rnd))
            self.stdout.write(self.style.SUCCESS(f"Pacote VOSviewer: {o['vos']}"))
