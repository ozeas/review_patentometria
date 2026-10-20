"""Instalação: pasta de dados, mídia e healthcheck."""
import os
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path

from django.test import TestCase, override_settings


class SettingsDataDirTests(TestCase):
    def test_data_dir_define_banco_e_media(self):
        d = tempfile.mkdtemp()
        env = {**os.environ, "PATENTOMETRIA_DATA_DIR": d}
        code = (
            "import os, django;"
            "os.environ.setdefault('DJANGO_SETTINGS_MODULE','config.settings');"
            "django.setup();"
            "from django.conf import settings;"
            "print(settings.DATABASES['default']['NAME']);"
            "print(settings.MEDIA_ROOT)"
        )
        out = subprocess.run([sys.executable, "-c", code], env=env,
                             capture_output=True, text=True)
        self.assertEqual(out.returncode, 0, out.stderr)
        linhas = out.stdout.split()
        self.assertEqual(Path(linhas[0]), Path(d) / "db.sqlite3")
        self.assertEqual(Path(linhas[1]), Path(d) / "media")


class MediaTests(TestCase):
    def test_media_servida_com_debug_desligado(self):
        d = Path(tempfile.mkdtemp())
        (d / "rodadas").mkdir()
        (d / "rodadas" / "teste.txt").write_text("ok", encoding="utf-8")
        with override_settings(DEBUG=False, MEDIA_ROOT=d):
            resp = self.client.get("/media/rodadas/teste.txt")
        self.assertEqual(resp.status_code, 200)
        self.assertEqual(b"".join(resp.streaming_content), b"ok")


class HealthTests(TestCase):
    def test_healthz(self):
        r = self.client.get("/healthz/")
        self.assertEqual(r.status_code, 200)
        self.assertEqual(r.json()["status"], "ok")
        self.assertIn("version", r.json())


if __name__ == "__main__":
    unittest.main()
