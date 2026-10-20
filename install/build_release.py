"""Gera o wheel e os três zips de instalação em dist/."""
from __future__ import annotations

import subprocess
import zipfile
from pathlib import Path

RAIZ = Path(__file__).resolve().parent.parent
VER = "0.4.1"
DIST = RAIZ / "dist"
PACOTES = {
    "windows": ["install.ps1", "LEIA-ME.txt"],
    "macos": ["install.command", "LEIA-ME.txt"],
    "linux": ["install.sh", "LEIA-ME.txt"],
}
EXECUTAVEIS = {"install.sh", "install.command"}


def _add(z: zipfile.ZipFile, arquivo: Path, nome: str) -> None:
    info = zipfile.ZipInfo(nome)
    info.compress_type = zipfile.ZIP_DEFLATED
    info.external_attr = (0o755 if nome in EXECUTAVEIS else 0o644) << 16
    z.writestr(info, arquivo.read_bytes())


def main() -> None:
    subprocess.run(["uv", "build"], cwd=RAIZ, check=True)
    wheel = next(DIST.glob(f"patentometria-{VER}-*.whl"))
    for so, arquivos in PACOTES.items():
        destino = DIST / f"patentometria-{VER}-{so}.zip"
        with zipfile.ZipFile(destino, "w", zipfile.ZIP_DEFLATED) as z:
            _add(z, wheel, wheel.name)
            for nome in arquivos:
                _add(z, RAIZ / "install" / nome, nome)
        print(destino)


if __name__ == "__main__":
    main()
