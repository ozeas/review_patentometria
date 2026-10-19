"""Registro declarativo das bases de patente: o que cada exportação traz.

Antes disto, base nova exigia editar a tupla em ``records.py``, o dicionário em
``parsers/__init__.py`` e, se tivesse consulta no cabeçalho, ``queries.py``.
Agora a base é um dado: um ``SourceSpec``.

``SOURCES`` e ``SOURCE_LABELS`` continuam em ``records.py`` porque os parsers
importam de lá — o registro é aditivo e um teste garante que não divergem.
"""
from __future__ import annotations

from dataclasses import dataclass

from .parsers import PARSERS
from .queries import consulta_espacenet, consulta_google
from .records import SOURCES, SOURCE_LABELS

CAMPOS = ("title", "abstract", "dwpi_abstract", "ipc", "cpc", "priorities",
          "family_ids", "legal_status", "cited_by", "doc_type", "applicants", "inventors")


@dataclass(frozen=True)
class SourceSpec:
    key: str
    label: str
    parser: object
    exporta: tuple[str, ...]
    apelidos_arquivo: tuple[str, ...] = ()
    consulta_no_arquivo: object | None = None
    observacao: str = ""


REGISTRY: dict[str, SourceSpec] = {
    "lens": SourceSpec(
        "lens", SOURCE_LABELS["lens"], PARSERS["lens"],
        exporta=("title", "abstract", "ipc", "cpc", "priorities", "family_ids", "legal_status",
                 "cited_by", "doc_type", "applicants", "inventors"),
        apelidos_arquivo=("lens",),
        observacao="exporta família simples (LENS:) e a família DOCDB por campo próprio"),
    "espacenet": SourceSpec(
        "espacenet", SOURCE_LABELS["espacenet"], PARSERS["espacenet"],
        exporta=("title", "ipc", "cpc", "family_ids", "applicants", "inventors"),
        apelidos_arquivo=("espacenet",),
        consulta_no_arquivo=consulta_espacenet,
        observacao="sem resumo; data de prioridade sem número de prioridade; família DOCDB"),
    "google": SourceSpec(
        "google", SOURCE_LABELS["google"], PARSERS["google"],
        exporta=("title", "applicants", "inventors"),
        apelidos_arquivo=("google",),
        consulta_no_arquivo=consulta_google,
        observacao="sem resumo, IPC/CPC nem número de prioridade"),
    "derwent": SourceSpec(
        "derwent", SOURCE_LABELS["derwent"], PARSERS["derwent"],
        # 'abstract' via DWPI: a prevalência mapeia derwent -> dwpi_abstract
        exporta=("title", "abstract", "dwpi_abstract", "ipc", "priorities", "family_ids",
                 "applicants", "inventors"),
        apelidos_arquivo=("derwent", "darwent", "clarivate", "wos"),
        observacao="resumo reescrito DWPI (AB/NOVELTY/USE); exportado pelo Web of Science"),
    "inpi": SourceSpec(
        "inpi", SOURCE_LABELS["inpi"], PARSERS["inpi"],
        exporta=("title", "ipc", "applicants", "inventors"),
        apelidos_arquivo=("inpi",),
        observacao="CONTRATO PROVISÓRIO: formato não validado com exportação real "
                   "(ver docs/formatos/inpi.md); sem resumo, citações ou situação jurídica"),
}


def spec(base: str) -> SourceSpec:
    return REGISTRY[base]


def bases_que_exportam(campo: str) -> tuple[str, ...]:
    return tuple(k for k, v in REGISTRY.items() if campo in v.exporta)


def campos_ausentes(base: str) -> tuple[str, ...]:
    return tuple(c for c in CAMPOS if c not in REGISTRY[base].exporta)


def matriz() -> dict[str, dict[str, bool]]:
    """Tabela base × campo: True quando a exportação traz o campo."""
    return {k: {c: c in s.exporta for c in CAMPOS} for k, s in REGISTRY.items()}


def validar_prevalencia(cfg: dict) -> list[str]:
    """Erro quando a configuração prefere, para um campo, uma base que não o exporta."""
    erros = []
    for campo, bases in (cfg.get("prevalence") or {}).items():
        for base in bases:
            if base in REGISTRY and campo in CAMPOS and campo not in REGISTRY[base].exporta:
                erros.append(f"prevalência de '{campo}' prefere {base}, que não exporta esse campo")
    return erros


def base_pelo_nome(nome: str) -> str | None:
    """Deduz a base pelo nome do arquivo ('lens_nucleo.csv', 'darwent_...', 'wos_...')."""
    low = (nome or "").lower()
    for key, s in REGISTRY.items():
        if any(a in low for a in (key, *s.apelidos_arquivo)):
            return key
    return None
