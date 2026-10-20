"""Instala o wheel em ambiente efêmero e valida a CLI (roda no CI, 3 sistemas)."""
from __future__ import annotations

import shutil
import subprocess
import sys
import tempfile
from pathlib import Path

RAIZ = Path(__file__).resolve().parent.parent
wheels = sorted((RAIZ / "dist").glob("patentometria-*.whl"))
if not wheels:
    sys.exit("nenhum wheel em dist/ — rode `uv build` antes")
wheel = wheels[-1]
dados = tempfile.mkdtemp(prefix="pm-smoke-")

cmd = [shutil.which("uv") or "uv", "run", "--isolated", "--with", str(wheel),
       "patentometria", "--data-dir", dados, "check"]
r = subprocess.run(cmd, capture_output=True, text=True)
print(r.stdout.strip())
if r.returncode != 0 or "OK: banco migrado" not in r.stdout:
    print(r.stderr, file=sys.stderr)
    sys.exit(f"smoke falhou (exit {r.returncode})")
print("SMOKE OK")
shutil.rmtree(dados, ignore_errors=True)
