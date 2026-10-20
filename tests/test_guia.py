"""Estrutura do guia de uso (docs/guia) e do site publicado no GitHub Pages."""
import re
import shutil
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path

RAIZ = Path(__file__).resolve().parent.parent
GUIA = RAIZ / "docs" / "guia"


class GuiaTests(unittest.TestCase):
    def test_arquivos_referenciados_existem(self):
        tex = (GUIA / "guia.tex").read_text(encoding="utf-8")
        refs = re.findall(r"\\input\{([^}]+)\}", tex)
        refs += re.findall(r"\\includegraphics(?:\[[^\]]*\])?\{([^}]+)\}", tex)
        faltando = [r for r in refs if not (GUIA / r).exists() and not (GUIA / f"{r}.tex").exists()]
        self.assertFalse(faltando, faltando)

    def test_cada_passo_tem_blocos_didaticos(self):
        passos = sorted((GUIA / "secoes").glob("passo_*.tex"))
        self.assertGreaterEqual(len(passos), 12)
        for passo in passos:
            texto = passo.read_text(encoding="utf-8")
            for bloco in ("Objetivo", "O que fazer", "Como interpretar", "Checkpoint"):
                self.assertIn(bloco, texto, f"{passo.name}: falta {bloco}")

    @unittest.skipUnless(shutil.which("pdfinfo"), "pdfinfo não instalado")
    def test_pdf_existe_e_tem_paginas(self):
        pdf = GUIA / "guia.pdf"
        self.assertTrue(pdf.exists())
        saida = subprocess.run(["pdfinfo", str(pdf)], capture_output=True, text=True, check=True).stdout
        paginas = int(re.search(r"Pages:\s+(\d+)", saida).group(1))
        self.assertGreaterEqual(paginas, 15)

    def test_site_gerado_a_partir_do_pdf(self):
        destino = Path(tempfile.mkdtemp())
        subprocess.run([sys.executable, str(GUIA / "site.py"), "--out", str(destino)],
                       check=True, capture_output=True, text=True)
        html = (destino / "index.html").read_text(encoding="utf-8")
        self.assertTrue((destino / "guia.pdf").exists())
        self.assertGreaterEqual(html.count("guia.pdf#page="), 12)
        self.assertIn("GitHub Pages", html)
