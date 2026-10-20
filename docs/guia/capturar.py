"""Captura as telas do guia a partir de uma demonstração em execução.

Pré-requisito: `docs/guia/demo.sh` e o servidor rodando em 127.0.0.1:8090 com
`PATENTOMETRIA_DATA_DIR` apontando para a pasta de demonstração.
"""
from __future__ import annotations

import subprocess
import sys
from pathlib import Path

from PIL import Image, ImageChops

BASE = "http://127.0.0.1:8090"
SAIDA = Path(__file__).resolve().parent / "img"
ALTURA = 2600
LARGURA = 900

TELAS = [
    ("01_home", "/"),
    ("02_estudo", "/s/1/"),
    ("03_config", "/s/1/config/"),
    ("04_rodada", "/r/1/"),
    ("06_familias", "/r/1/familias/"),
    ("07_familia", "/r/1/f/F002/"),
    ("08_triagem", "/r/1/triagem/1/"),
    ("09_ligacoes", "/r/1/ligacoes/"),
    ("10_depositantes", "/r/1/depositantes/"),
    ("11_inventores", "/r/1/inventores/"),
    ("12_indicadores", "/r/1/indicadores/?conjunto=unificada"),
    ("13_vosviewer", "/r/1/vosviewer/"),
    ("14_importar", "/r/1/importar/"),
    ("15_tesauro", "/s/1/tesauro/"),
]


def cortar(caminho: Path) -> None:
    """Remove o rodapé vazio da captura, preservando 28 px de respiro."""
    imagem = Image.open(caminho).convert("RGB")
    fundo = Image.new("RGB", imagem.size, imagem.getpixel((5, imagem.height - 5)))
    diferenca = ImageChops.difference(imagem, fundo).convert("L")
    caixa = diferenca.point(lambda v: 255 if v > 6 else 0).getbbox()
    if not caixa:
        return
    altura = min(imagem.height, caixa[3] + 28)
    imagem.crop((0, 0, imagem.width, altura)).save(caminho, optimize=True)


def capturar(nome: str, caminho_url: str) -> None:
    destino = SAIDA / f"{nome}.png"
    subprocess.run(
        [
            "chromium", "--headless", "--disable-gpu", "--hide-scrollbars", "--no-sandbox",
            f"--window-size={LARGURA},{ALTURA}", f"--screenshot={destino}",
            f"{BASE}{caminho_url}",
        ],
        check=True,
        capture_output=True,
        timeout=60,
    )
    cortar(destino)
    print(f"{nome}.png {Image.open(destino).size}")


def recortar() -> None:
    """Gera os recortes usados no PDF (telas altas demais para uma figura)."""
    recortes = {
        "03_config_topo": ("03_config.png", (0, 0, LARGURA, 760)),
        "04_rodada_topo": ("04_rodada.png", (0, 0, LARGURA, 1080)),
        "07_familia_topo": ("07_familia.png", (0, 0, LARGURA, 1000)),
        "08_triagem_topo": ("08_triagem.png", (0, 0, LARGURA, 900)),
        "08_triagem_painel": ("08_triagem.png", (640, 90, LARGURA, 900)),
        "03_upload_painel": ("04_rodada.png", (18, 690, 470, 1310)),
        "12_indicadores_1": ("12_indicadores.png", (0, 0, LARGURA, 760)),
        "12_indicadores_2": ("12_indicadores.png", (0, 650, LARGURA, 1410)),
        "12_indicadores_3": ("12_indicadores.png", (0, 1300, LARGURA, 2082)),
    }
    for nome, (origem, caixa) in recortes.items():
        imagem = Image.open(SAIDA / origem)
        imagem.crop(caixa).save(SAIDA / f"{nome}.png", optimize=True)
        print(f"{nome}.png {caixa}")


def main() -> None:
    SAIDA.mkdir(parents=True, exist_ok=True)
    for nome, url in TELAS:
        capturar(nome, url)
    recortar()


if __name__ == "__main__":
    sys.exit(main())
