"""Presets de configuração: criar estudo novo a partir de um modelo."""
import io
import json
import tempfile
from pathlib import Path

from django.core.management import call_command
from django.test import TestCase

from core.presets import carregar_preset, listar_presets, salvar_preset
from studies import models as m


class PresetTests(TestCase):
    def test_salvar_e_listar_preset(self):
        d = Path(tempfile.mkdtemp())
        estudo = m.Study.objects.create(name="Modelo")
        caminho = salvar_preset(estudo, d / "modelo.json")
        self.assertTrue(caminho.exists())
        self.assertIn("blocks", json.loads(caminho.read_text(encoding="utf-8")))
        self.assertEqual([p.name for p in listar_presets(d)], ["modelo.json"])

    def test_novo_estudo_a_partir_de_preset(self):
        d = Path(tempfile.mkdtemp())
        base = m.Study.objects.create(name="Base")
        base.config = {**base.config, "blocks": [{"name": "(i) sensoriamento", "terms": ["fiber optic"]}]}
        base.save()
        caminho = salvar_preset(base, d / "sensores.json")

        call_command("novo_estudo", "--nome", "Projeto novo", "--preset", str(caminho), stdout=io.StringIO())

        novo = m.Study.objects.get(name="Projeto novo")
        self.assertEqual(novo.config["blocks"][0]["terms"], ["fiber optic"])
        self.assertNotEqual(novo.id, base.id)

    def test_preset_invalido_e_recusado(self):
        d = Path(tempfile.mkdtemp())
        ruim = d / "ruim.json"
        ruim.write_text('{"blocks": [], "periods": [], "stage1": {}, "stage2": {}, "strata": []}')
        with self.assertRaises(ValueError):
            carregar_preset(ruim)
