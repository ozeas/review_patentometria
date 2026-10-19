"""Leitura da consulta no cabeçalho da exportação e comparação com a declarada.

Usa ``unittest.TestCase`` (e não funções soltas) porque o runner do projeto é
``python manage.py test tests``: funções ``def test_...`` não seriam descobertas
e o teste passaria sem rodar.
"""
import unittest

from core.queries import consulta_do_arquivo, consultas_divergem, normalizar_consulta

ESPACENET = (
    '"Espacenet";"";"";"";"";"";"";"";"";"";\n'
    '"Patent search";"";"";"";"";"";"";"";"";"";\n'
    '"156 results found for (ta = ""gas chromatography"" OR ta = ""GC-MS"") '
    'AND (ipc =/low ""G01N"" OR ipc =/low ""C10G"")";"";\n'
    '"No";"Title";"Publication number"\n'
)
GOOGLE = (
    "search URL:,https://patents.google.com/?q=%28TI%253d%28%22gas+chromatography%22"
    "%29%29&country=WO%2CUS&type=PATENT\n"
    "id,title,publication date\nUS1,T,2020-01-01\n"
)


class ConsultaDoArquivoTests(unittest.TestCase):
    def test_espacenet_extrai_a_consulta_do_cabecalho(self):
        c = consulta_do_arquivo("espacenet", ESPACENET)
        self.assertTrue(c.startswith('(ta = "gas chromatography"'), c)
        self.assertIn('ipc =/low "C10G"', c)
        self.assertNotIn("results found for", c)

    def test_google_extrai_a_url_da_consulta(self):
        c = consulta_do_arquivo("google", GOOGLE)
        self.assertEqual(c, "https://patents.google.com/?q=%28TI%253d%28%22gas+chromatography%22"
                            "%29%29&country=WO%2CUS&type=PATENT")

    def test_bases_sem_consulta_no_arquivo_devolvem_vazio(self):
        self.assertEqual(consulta_do_arquivo("lens", '\ufeff"#",Jurisdiction\n1,US\n'), "")
        self.assertEqual(consulta_do_arquivo("derwent", "PN \t TI\nUS1\tT\n"), "")
        self.assertEqual(consulta_do_arquivo("google", "id,title\nUS1,T\n"), "")

    def test_normalizacao_ignora_caixa_espacos_aspas_e_prefixo(self):
        a = '156 results found for (ta = ""gas chromatography"")'
        b = '(TA = "gas chromatography")'
        self.assertEqual(normalizar_consulta(a), normalizar_consulta(b))

    def test_divergencia_so_quando_os_dois_lados_existem(self):
        self.assertFalse(consultas_divergem("", "(ta = x)"))
        self.assertFalse(consultas_divergem("(ta = x)", ""))
        self.assertFalse(consultas_divergem("(ta = x)", "(ta = x)"))
        self.assertTrue(consultas_divergem("(ta = x)", "(ta = y)"))
