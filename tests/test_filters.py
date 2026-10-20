"""Filtros de template usados nas telas de indicadores e de rodada."""
import unittest

from studies.templatetags.pt import get, pct1


class FiltroGetTests(unittest.TestCase):
    def test_chave_inteira_em_dicionario_com_chave_texto(self):
        # O resumo passa por JSON e as chaves inteiras viram texto.
        self.assertEqual(get({"4": 3}, 4), 3)

    def test_chave_ausente_devolve_none(self):
        self.assertIsNone(get({"1": 2}, 4))

    def test_lista_por_indice(self):
        self.assertEqual(get(["a", "b"], 1), "b")


class FiltroPctTests(unittest.TestCase):
    def test_virgula_decimal(self):
        self.assertEqual(pct1(61.53), "61,5")
        self.assertIsNone(pct1(None))
