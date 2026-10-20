"""Garante que o app não voltou a carregar contexto da pesquisa local."""
import subprocess
import unittest
from pathlib import Path

RAIZ = Path(__file__).resolve().parent.parent
EXTENSOES = {".py", ".md", ".txt", ".toml", ".yml", ".yaml", ".sh", ".command",
             ".ps1", ".html", ".css", ".json", ".in"}
IGNORAR = {"tests/test_generic_context.py", "uv.lock"}
IGNORAR_PREFIXOS = ("tests/fixtures/",)
TERMOS = [
    "PGEN1075", "PGEN 1075", "UFES", "doutorado", "cromatografia", "petróleo",
    "petroleo", "crude oil", "GC x", "GC ×", "upstream", "base_unificada",
    "referencia_2026", "669", "272 famílias",
]


class ContextoGenericoTests(unittest.TestCase):
    def test_sem_contexto_de_pesquisa(self):
        arquivos = subprocess.run(["git", "ls-files"], cwd=RAIZ, capture_output=True,
                                  text=True, check=True).stdout.splitlines()
        achados = []
        for nome in arquivos:
            if nome in IGNORAR or nome.startswith(IGNORAR_PREFIXOS):
                continue
            if Path(nome).suffix.lower() not in EXTENSOES:
                continue
            try:
                texto = (RAIZ / nome).read_text(encoding="utf-8")
            except (UnicodeDecodeError, FileNotFoundError):
                continue
            for i, linha in enumerate(texto.splitlines(), 1):
                for termo in TERMOS:
                    if termo.lower() in linha.lower():
                        achados.append(f"{nome}:{i}: {termo}")
        self.assertFalse(achados, "contexto de pesquisa encontrado:\n" + "\n".join(achados))
