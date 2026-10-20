"""INPI: reconhecimento pelo cabeçalho e recusa explícita de formato desconhecido.

A fixture é **sintética** (não havia exportação real do INPI em 19/10/2026). O
teste exercita o contrato documentado em ``docs/formatos/inpi.md``; quando uma
exportação real chegar, ela vira a fixture e este arquivo é ajustado.
"""
import unittest

from core.parsers.inpi import parse


class InpiTests(unittest.TestCase):
    CABECALHO = ("Pedido;Título;Classificação;Depositante;Data de depósito;Data de publicação\n"
                 "BR102020000001;Método de análise de solo;G01N27/22;NORTHWIND SENSORS;2020-01-02;2021-06-01\n")

    def test_le_csv_com_colunas_mapeadas(self):
        recs = parse(self.CABECALHO, "nucleo")
        self.assertEqual(len(recs), 1)
        rec = recs[0]
        self.assertEqual(rec.source, "inpi")
        self.assertEqual(rec.title, "Método de análise de solo")
        self.assertEqual(rec.pubs[0].number, "BR102020000001")
        self.assertTrue(rec.ipc and rec.ipc[0].startswith("G01N"))
        self.assertEqual(rec.applicants, ["NORTHWIND SENSORS"])

    def test_formato_desconhecido_levanta_erro_com_instrucao(self):
        with self.assertRaises(ValueError) as ctx:
            parse("coluna1,coluna2\n1,2\n", "nucleo")
        self.assertIn("docs/formatos/inpi.md", str(ctx.exception))

    def test_arquivo_vazio_levanta_erro(self):
        with self.assertRaises(ValueError):
            parse("", "nucleo")
