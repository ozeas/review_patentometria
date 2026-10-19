from django.core.management.base import BaseCommand

from core.presets import salvar_preset
from studies import models as m


class Command(BaseCommand):
    help = "Exporta a configuração de um estudo como preset JSON."

    def add_arguments(self, p):
        p.add_argument("estudo", type=int)
        p.add_argument("-o", "--saida", required=True)

    def handle(self, *a, **o):
        estudo = m.Study.objects.get(pk=o["estudo"])
        caminho = salvar_preset(estudo, o["saida"])
        self.stdout.write(self.style.SUCCESS(f"{caminho}"))
