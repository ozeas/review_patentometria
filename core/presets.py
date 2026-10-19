"""Presets de configuração de estudo (JSON versionado em ``presets/``)."""
from __future__ import annotations

import json
from pathlib import Path

from .config import normalize_config, validate_config

DIR_PADRAO = Path(__file__).resolve().parent.parent / "presets"


def listar_presets(dir_: Path | None = None) -> list[Path]:
    """Presets disponíveis. ``dir_`` vazio usa ``DIR_PADRAO`` (lido na chamada, não no import)."""
    dir_ = Path(dir_) if dir_ else DIR_PADRAO
    if not dir_.is_dir():
        return []
    return sorted(dir_.glob("*.json"))


def carregar_preset(caminho: Path) -> dict:
    cfg = json.loads(Path(caminho).read_text(encoding="utf-8"))
    erros = validate_config(cfg)
    if erros:
        raise ValueError("; ".join(erros))
    return normalize_config(cfg)


def salvar_preset(estudo, caminho: Path) -> Path:
    caminho = Path(caminho)
    caminho.parent.mkdir(parents=True, exist_ok=True)
    caminho.write_text(json.dumps(normalize_config(estudo.config), ensure_ascii=False, indent=2),
                       encoding="utf-8")
    return caminho
