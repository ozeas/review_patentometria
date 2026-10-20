"""Porteiro de metadados para o PyPI (roda antes de `uv build` no publish).

Falha (exit 1) quando falta campo obrigatório ou quando a licença ainda não foi
decidida — publicar sem licença é decisão do autor, não do acaso.
"""
from __future__ import annotations

import re
import sys
import tomllib
from pathlib import Path

RAIZ = Path(__file__).resolve().parent.parent
PYPROJECT = RAIZ / "pyproject.toml"
NOME_VALIDO = re.compile(r"^[a-z0-9][a-z0-9._-]*$")
VERSAO_VALIDA = re.compile(r"^\d+\.\d+\.\d+([a-zA-Z0-9.+-]*)$")


def validar(meta: dict, raiz: Path = RAIZ) -> list[str]:
    projeto = meta.get("project", {})
    erros: list[str] = []

    for campo in ("name", "version", "description", "readme", "requires-python"):
        if not projeto.get(campo):
            erros.append(f"campo obrigatório ausente: project.{campo}")

    nome = projeto.get("name", "")
    if nome and not NOME_VALIDO.match(nome):
        erros.append(f"nome inválido para o PyPI: {nome!r}")
    versao = projeto.get("version", "")
    if versao and not VERSAO_VALIDA.match(versao):
        erros.append(f"versão fora do padrão PEP 440: {versao!r}")
    if len(projeto.get("description", "")) > 512:
        erros.append("description acima de 512 caracteres")

    if not projeto.get("authors"):
        erros.append("project.authors vazio")
    if not projeto.get("classifiers"):
        erros.append("project.classifiers vazio")
    elif not any(c.startswith("Programming Language :: Python :: 3") for c in projeto["classifiers"]):
        erros.append("classifiers sem 'Programming Language :: Python :: 3'")

    if not (meta.get("project", {}).get("scripts", {}) or {}).get("patentometria"):
        erros.append("entry point 'patentometria' ausente em project.scripts")

    if not projeto.get("license") and not projeto.get("license-files"):
        erros.append("licença não definida (project.license ou project.license-files)")

    readme = projeto.get("readme")
    if isinstance(readme, str) and not (raiz / readme).exists():
        erros.append(f"readme não encontrado: {readme}")

    return erros


def main() -> int:
    with PYPROJECT.open("rb") as f:
        meta = tomllib.load(f)
    erros = validar(meta)
    if erros:
        print("PyPI: metadados incompletos")
        for e in erros:
            print(f"  - {e}")
        return 1
    projeto = meta["project"]
    print(f"PyPI OK: {projeto['name']} {projeto['version']}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
