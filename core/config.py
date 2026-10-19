"""Esquema, validação e normalização da configuração de um estudo.

Um estudo é descrito por um dicionário (``Study.config``). Aqui ficam o padrão,
as chaves obrigatórias e as validações que evitam rodar um corpus com a
configuração de outro projeto.
"""
from __future__ import annotations

import copy

from .prevalence import DEFAULT_PREVALENCE
from .records import SOURCES

OBRIGATORIAS = ("blocks", "periods", "stage1", "stage2", "strata")

DEFAULT_CONFIG = {
    "core_recorte": "nucleo",
    "recortes": {"nucleo": "conjunto principal", "BR": "Brasil"},
    "utility_kinds": ["U"],
    "prio_link_min_digits": 8,
    "periods": [[1971, 2009], [2010, 2019], [2020, 2026]],
    "window_months": 36,
    "collection_date": "2026-01-01",
    "prevalence": DEFAULT_PREVALENCE,
    "blocks": [
        {"name": "(i) termo do tema", "terms": ["substitua por um termo do tema"]},
        {"name": "(ii) contexto de aplicação", "terms": ["substitua por um termo de contexto"]},
    ],
    "classification_block": [],
    "stage1": {"label": "Relação entre o tema e o contexto",
               "exclusion_reasons": ["Falso positivo lexical", "Outro domínio de aplicação"]},
    "stage2": {"label": "Segmento",
               "inclusion_segments": ["Segmento incluído"],
               "exclusion_reasons": ["Segmento excluído", "Transversal"]},
    "strata": [{"code": "S1", "name": "núcleo",
                "definition": "O tema é nomeado no título e constitui o objeto da invenção."},
               {"code": "S2", "name": "aplicado",
                "definition": "O tema é instrumento de um método voltado a outra finalidade."}],
    "top_n": 15,
}


def normalize_config(cfg: dict | None) -> dict:
    """Devolve a config completa: o que veio do estudo manda, o resto vem do padrão."""
    base = copy.deepcopy(DEFAULT_CONFIG)
    for k, v in (cfg or {}).items():
        base[k] = copy.deepcopy(v)
    for k in ("recortes", "prevalence"):
        if not base.get(k):
            base[k] = copy.deepcopy(DEFAULT_CONFIG[k])
    if base.get("top_n") in (None, 0):
        base["top_n"] = DEFAULT_CONFIG["top_n"]
    recortes = base.get("recortes")
    if isinstance(recortes, dict) and base.get("core_recorte") not in recortes:
        recortes[base["core_recorte"]] = "conjunto principal"
    return base


def validate_config(cfg: dict | None) -> list[str]:
    """Lista de erros (vazia = configuração válida)."""
    if not isinstance(cfg, dict):
        return ["configuração precisa ser um objeto JSON"]

    erros: list[str] = []
    for chave in OBRIGATORIAS:
        if not cfg.get(chave):
            erros.append(f"chave obrigatória ausente: {chave}")
    if erros:
        return erros

    for i, bloco in enumerate(cfg["blocks"]):
        bloco = bloco or {}
        if not bloco.get("name"):
            erros.append(f"bloco {i + 1} sem nome")
        if not [t for t in bloco.get("terms", []) if str(t).strip()]:
            erros.append(f"bloco {i + 1} sem termos: um bloco de busca precisa de pelo menos um termo")

    periodos = cfg["periods"]
    if any((not isinstance(p, (list, tuple)) or len(p) != 2 or p[0] > p[1]) for p in periodos):
        erros.append("período inválido: use [ano_inicial, ano_final] com início ≤ fim")
    elif any(periodos[i][0] <= periodos[i - 1][0] for i in range(1, len(periodos))):
        erros.append("períodos devem estar em ordem crescente e não se sobrepor")

    codigos = [s.get("code") for s in cfg["strata"] if isinstance(s, dict)]
    if not codigos:
        erros.append("estrato ausente: defina pelo menos um estrato")
    elif len(codigos) != len(set(codigos)):
        erros.append("estrato repetido: cada estrato precisa de um código único")

    for campo, bases in (cfg.get("prevalence") or {}).items():
        for base in bases:
            if base not in SOURCES:
                erros.append(f"prevalência de '{campo}' aponta para base desconhecida: {base}")

    from .sources import validar_prevalencia  # import tardio: evita ciclo
    erros.extend(validar_prevalencia(cfg))
    return erros
