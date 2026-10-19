"""Validação e normalização da configuração de um estudo."""
import copy
import unittest

from core.config import DEFAULT_CONFIG, normalize_config, validate_config


class ConfigTests(unittest.TestCase):
    def test_config_padrao_e_valida(self):
        self.assertEqual(validate_config(copy.deepcopy(DEFAULT_CONFIG)), [])

    def test_bloco_sem_termos_e_erro(self):
        cfg = copy.deepcopy(DEFAULT_CONFIG)
        cfg["blocks"] = [{"name": "(i) x", "terms": []}]
        self.assertTrue(any("bloco" in e.lower() for e in validate_config(cfg)))

    def test_estratos_precisam_de_codigo_unico(self):
        cfg = copy.deepcopy(DEFAULT_CONFIG)
        cfg["strata"] = [{"code": "C1", "name": "a", "definition": "x"},
                         {"code": "C1", "name": "b", "definition": "y"}]
        self.assertTrue(any("estrato" in e.lower() for e in validate_config(cfg)))

    def test_periodos_precisam_ser_crescentes(self):
        cfg = copy.deepcopy(DEFAULT_CONFIG)
        cfg["periods"] = [[2010, 2019], [2000, 2009]]
        self.assertTrue(any("período" in e.lower() for e in validate_config(cfg)))

    def test_prevalencia_para_base_desconhecida_e_erro(self):
        cfg = copy.deepcopy(DEFAULT_CONFIG)
        cfg["prevalence"] = {"title": ["openalex", "lens"]}
        self.assertTrue(any("openalex" in e for e in validate_config(cfg)))

    def test_prevalencia_que_prefere_base_sem_o_campo_e_erro(self):
        cfg = copy.deepcopy(DEFAULT_CONFIG)
        cfg["prevalence"] = {"abstract": ["google", "lens"]}
        self.assertTrue(any("abstract" in e and "google" in e for e in validate_config(cfg)))

    def test_prevalencia_padrao_passa(self):
        self.assertEqual([e for e in validate_config(copy.deepcopy(DEFAULT_CONFIG))
                          if "prevalência" in e], [])

    def test_normalizacao_preenche_opcionais_e_mantem_obrigatorios(self):
        cfg = {"blocks": [{"name": "(i) x", "terms": ["alpha"]}], "periods": [[2000, 2026]],
               "stage1": {"label": "a", "exclusion_reasons": ["r"]},
               "stage2": {"label": "b", "inclusion_segments": ["s"], "exclusion_reasons": ["r"]},
               "strata": [{"code": "C1", "name": "n", "definition": "d"}]}
        c = normalize_config(cfg)
        self.assertEqual(c["collection_date"], DEFAULT_CONFIG["collection_date"])
        self.assertEqual(c["utility_kinds"], DEFAULT_CONFIG["utility_kinds"])
        self.assertEqual(c["blocks"][0]["terms"], ["alpha"])
