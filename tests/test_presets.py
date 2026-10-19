"""Presets de configuração: criar estudo novo a partir de um modelo."""
import io
import json
import tempfile
from pathlib import Path

from django.core.management import call_command
from django.test import TestCase

from core.config import DEFAULT_CONFIG
from core.presets import DIR_PADRAO, carregar_preset, listar_presets, salvar_preset
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


class DefaultPresetTests(TestCase):
    """Sem preset, o estudo nasce genérico (patentometria); o artigo é só preset."""

    def test_config_padrao_e_generico_nao_o_artigo(self):
        self.assertEqual(DEFAULT_CONFIG["blocks"][0]["name"], "(i) termo do tema")
        self.assertEqual(DEFAULT_CONFIG["classification_block"], [])
        self.assertEqual([s["code"] for s in DEFAULT_CONFIG["strata"]], ["S1", "S2"])

    def test_novo_estudo_sem_preset_nasce_generico(self):
        call_command("novo_estudo", "--nome", "Genérico", stdout=io.StringIO())
        s = m.Study.objects.get(name="Genérico")
        self.assertEqual(s.config["blocks"][0]["name"], "(i) termo do tema")
        self.assertEqual(s.config["classification_block"], [])

    def test_novo_estudo_com_preset_do_artigo_reproduz_o_artigo(self):
        call_command("novo_estudo", "--nome", "Artigo", "--preset",
                     str(DIR_PADRAO / "gc-petroleo-upstream.json"), stdout=io.StringIO())
        s = m.Study.objects.get(name="Artigo")
        self.assertEqual(s.config["blocks"][0]["name"], "(i) cromatografia gasosa")
        self.assertEqual(s.config["classification_block"], ["G01N", "C10G", "E21B 49"])


class StudyCreationUITests(TestCase):
    def test_ui_sem_preset_nasce_generico(self):
        r = self.client.post("/", {"name": "UI genérico", "description": ""})
        self.assertEqual(r.status_code, 302)
        s = m.Study.objects.get(name="UI genérico")
        self.assertEqual(s.config["blocks"][0]["name"], "(i) termo do tema")
        self.assertEqual(s.config["classification_block"], [])

    def test_ui_com_preset_do_artigo_reproduz_o_artigo(self):
        r = self.client.post("/", {"name": "UI artigo", "description": "",
                                   "preset": "gc-petroleo-upstream.json"})
        self.assertEqual(r.status_code, 302)
        s = m.Study.objects.get(name="UI artigo")
        self.assertEqual(s.config["blocks"][0]["name"], "(i) cromatografia gasosa")
        self.assertEqual(s.config["classification_block"], ["G01N", "C10G", "E21B 49"])
