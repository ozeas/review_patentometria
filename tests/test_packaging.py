"""Metadados do pacote para publicação no PyPI."""
import tomllib
import unittest
from pathlib import Path

from scripts.check_pypi import validar

RAIZ = Path(__file__).resolve().parent.parent


def _meta() -> dict:
    with (RAIZ / "pyproject.toml").open("rb") as f:
        return tomllib.load(f)


def _completo() -> dict:
    meta = _meta()
    meta["project"]["license"] = "MIT"
    return meta


class PyPiMetaTests(unittest.TestCase):
    def test_meta_completa_e_valida(self):
        self.assertEqual(validar(_completo(), RAIZ), [])

    def test_nome_precisa_ser_pypi(self):
        meta = _completo()
        meta["project"]["name"] = "Patentometria Nacional"
        self.assertTrue(any("nome inválido" in e for e in validar(meta, RAIZ)))

    def test_versao_precisa_pep440(self):
        meta = _completo()
        meta["project"]["version"] = "0.3"
        self.assertTrue(any("PEP 440" in e for e in validar(meta, RAIZ)))

    def test_entry_point_obrigatorio(self):
        meta = _completo()
        meta["project"]["scripts"] = {}
        self.assertTrue(any("entry point" in e for e in validar(meta, RAIZ)))

    def test_licenca_pendente_reprova(self):
        meta = _meta()
        meta["project"].pop("license", None)
        meta["project"].pop("license-files", None)
        self.assertTrue(any("licença" in e for e in validar(meta, RAIZ)))

    def test_classifier_de_python_obrigatorio(self):
        meta = _completo()
        meta["project"]["classifiers"] = ["Environment :: Console"]
        self.assertTrue(any("Programming Language" in e for e in validar(meta, RAIZ)))
