"""Cria um estudo a partir de um preset de configuração.

    python manage.py novo_estudo --nome "Sensoriamento em poços" \\
        --preset presets/sensoriamento-exemplo.json

Sem ``--preset`` o estudo nasce com a configuração padrão (cromatografia ×
petróleo) — use isto só quando for exatamente esse o tema.
"""
from django.core.management.base import BaseCommand, CommandError

from core.config import DEFAULT_CONFIG, normalize_config, validate_config
from core.presets import carregar_preset
from studies import models as m


class Command(BaseCommand):
    help = "Cria um estudo com a configuração de um preset (ou com o padrão)."

    def add_arguments(self, p):
        p.add_argument("--nome", required=True)
        p.add_argument("--preset", help="arquivo JSON de preset; vazio = configuração padrão")
        p.add_argument("--descricao", default="")

    def handle(self, *a, **o):
        try:
            cfg = carregar_preset(o["preset"]) if o["preset"] else normalize_config(DEFAULT_CONFIG)
        except ValueError as e:
            raise CommandError(f"preset inválido: {e}")
        erros = validate_config(cfg)
        if erros:
            raise CommandError("; ".join(erros))
        estudo = m.Study.objects.create(name=o["nome"], description=o["descricao"], config=cfg)
        self.stdout.write(self.style.SUCCESS(
            f"Estudo {estudo.id} «{estudo.name}» — blocos: {[b['name'] for b in cfg['blocks']]}"))
