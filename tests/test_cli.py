"""CLI instalada: pasta de dados, segredo e porta."""
import os
import tempfile
import unittest
from pathlib import Path

from django.test import SimpleTestCase

from config import cli


class CliTests(SimpleTestCase):
    def test_data_dir_respeita_flag(self):
        d = tempfile.mkdtemp()
        self.assertEqual(cli.resolver_data_dir(d), Path(d).resolve())

    def test_data_dir_respeita_env(self):
        d = tempfile.mkdtemp()
        os.environ["PATENTOMETRIA_DATA_DIR"] = d
        try:
            self.assertEqual(cli.resolver_data_dir(None), Path(d).resolve())
        finally:
            del os.environ["PATENTOMETRIA_DATA_DIR"]

    def test_data_dir_cria_media_e_logs(self):
        d = cli.resolver_data_dir(tempfile.mkdtemp())
        self.assertTrue((d / "media").is_dir())
        self.assertTrue((d / "logs").is_dir())

    def test_secret_key_persistente(self):
        d = Path(tempfile.mkdtemp())
        a = cli.garantir_secret_key(d)
        b = cli.garantir_secret_key(d)
        self.assertEqual(a, b)
        self.assertGreaterEqual(len(a), 40)
        self.assertTrue((d / "secret.key").exists())

    def test_porta_livre_pula_porta_ocupada(self):
        import socket
        s = socket.socket()
        s.bind(("127.0.0.1", 0))
        ocupada = s.getsockname()[1]
        try:
            livre = cli.encontrar_porta("127.0.0.1", ocupada, tentativas=5)
        finally:
            s.close()
        self.assertNotEqual(livre, ocupada)
        self.assertLess(livre, ocupada + 5)

    def test_ambiente_local_por_padrao(self):
        d = Path(tempfile.mkdtemp())
        cli.preparar_ambiente(d, "127.0.0.1")
        self.assertEqual(os.environ["PATENTOMETRIA_DEBUG"], "0")
        hosts = os.environ["PATENTOMETRIA_ALLOWED_HOSTS"].split(",")
        self.assertIn("127.0.0.1", hosts)
        self.assertIn("localhost", hosts)

    def test_migra_dados_da_pasta_antiga(self):
        novo = Path(tempfile.mkdtemp())
        antigo = Path(tempfile.mkdtemp())
        (antigo / "db.sqlite3").write_bytes(b"x")
        (antigo / "media").mkdir()
        (antigo / "media" / "a.txt").write_text("ok", encoding="utf-8")
        self.assertTrue(cli.migrar_dados_legados(novo, antigo))
        self.assertTrue((novo / "db.sqlite3").exists())
        self.assertTrue((novo / "media" / "a.txt").exists())
        self.assertFalse(cli.migrar_dados_legados(novo, antigo))

    def test_check_flag_curto(self):
        import subprocess
        import sys
        d = tempfile.mkdtemp()
        r = subprocess.run([sys.executable, "-m", "config.cli", "--data-dir", d, "--check"],
                           capture_output=True, text=True, timeout=120)
        self.assertEqual(r.returncode, 0, r.stderr)
        self.assertIn("OK: banco migrado", r.stdout)

    def test_manage_migra_antes_de_executar(self):
        import subprocess
        import sys
        d = tempfile.mkdtemp()
        r = subprocess.run([sys.executable, "-m", "config.cli", "--data-dir", d,
                            "manage", "showmigrations", "studies"],
                           capture_output=True, text=True, timeout=120)
        self.assertEqual(r.returncode, 0, r.stderr)
        self.assertIn("[X] 0001_initial", r.stdout)


if __name__ == "__main__":
    unittest.main()
