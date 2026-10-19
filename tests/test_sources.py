"""Registro declarativo das bases: parser, campos exportados e consulta no arquivo."""
import unittest

from core.parsers import PARSERS
from core.records import SOURCES
from core.sources import REGISTRY, base_pelo_nome, bases_que_exportam, campos_ausentes, matriz, spec


class RegistroTests(unittest.TestCase):
    def test_registro_cobre_exatamente_as_fontes(self):
        self.assertEqual(set(REGISTRY), set(SOURCES))

    def test_parsers_do_registro_sao_os_do_modulo(self):
        self.assertEqual({k: v.parser for k, v in REGISTRY.items()}, PARSERS)

    def test_campos_exportados_por_base(self):
        self.assertIn("abstract", spec("lens").exporta)
        self.assertNotIn("abstract", spec("google").exporta)
        self.assertNotIn("priorities", spec("google").exporta)
        self.assertEqual(bases_que_exportam("dwpi_abstract"), ("derwent",))

    def test_campos_ausentes_para_uma_base(self):
        self.assertIn("abstract", campos_ausentes("google"))
        self.assertNotIn("abstract", campos_ausentes("lens"))

    def test_matriz_de_campos_e_renderizavel(self):
        m = matriz()
        self.assertEqual(m["google"]["abstract"], False)
        self.assertEqual(m["lens"]["abstract"], True)

    def test_base_deduzida_pelo_nome_do_arquivo(self):
        self.assertEqual(base_pelo_nome("lens_nucleo.csv"), "lens")
        self.assertEqual(base_pelo_nome("darwent_nucleo.txt"), "derwent")
        self.assertEqual(base_pelo_nome("wos_export.txt"), "derwent")
        self.assertIsNone(base_pelo_nome("planilha.csv"))

    def test_base_nova_sem_consulta_no_arquivo_nao_quebra(self):
        self.assertIsNone(spec("lens").consulta_no_arquivo)
        self.assertIsNotNone(spec("espacenet").consulta_no_arquivo)

    def test_toda_base_tem_contrato_documentado(self):
        from pathlib import Path as P
        faltando = [k for k in REGISTRY
                    if not (P(__file__).parent.parent / "docs" / "formatos" / f"{k}.md").exists()]
        self.assertEqual(faltando, [])
