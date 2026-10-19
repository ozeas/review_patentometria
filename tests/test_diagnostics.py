"""Avisos quando a configuração não adere ao corpus exportado."""
import copy
import unittest
from pathlib import Path

from core.config import DEFAULT_CONFIG
from core.diagnostics import diagnosticar
from core.parsers import parse_bytes
from core.pipeline import run
from core.presets import carregar_preset

DADOS = Path.home() / "Documents/Shared/ppgen-doutorado/patentometria"


def _corpus():
    recs = []
    for f in sorted(DADOS.iterdir()):
        if f.suffix.lower() in (".csv", ".txt", ".tsv"):
            recs.extend(parse_bytes(f.read_bytes(), None, "nucleo")[1])
    return recs


class DiagnosticsTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.recs = _corpus()
        if not cls.recs:
            raise unittest.SkipTest("exportações reais não encontradas")

    def test_config_de_outro_tema_gera_aviso_de_lexico(self):
        cfg = copy.deepcopy(DEFAULT_CONFIG)
        cfg["blocks"] = [{"name": "(i) sensoriamento", "terms": ["fiber optic", "bragg grating"]}]
        cfg["classification_block"] = ["G02B"]
        d = diagnosticar(run(self.recs, config=cfg))
        self.assertGreater(d["lexical_ausente_pct"], 90.0)
        self.assertTrue(any("lexical" in a.lower() for a in d["avisos"]))
        self.assertTrue(any("sensoriamento" in a for a in d["avisos"]))

    def test_config_do_estudo_nao_gera_aviso_de_lexico(self):
        artigo = carregar_preset(Path(__file__).parent.parent / "presets" / "gc-petroleo-upstream.json")
        d = diagnosticar(run(self.recs, config=artigo))
        self.assertLess(d["lexical_ausente_pct"], 50.0)
        self.assertFalse(any("lexical" in a.lower() for a in d["avisos"]))

    def test_matriz_por_base_mostra_o_que_foi_exportado(self):
        d = diagnosticar(run(self.recs, config=copy.deepcopy(DEFAULT_CONFIG)))
        self.assertEqual(d["por_base"]["google"]["abstract"], 0)
        self.assertGreater(d["por_base"]["lens"]["abstract"], 0)
        self.assertEqual(d["por_base"]["google"]["ipc"], 0)
