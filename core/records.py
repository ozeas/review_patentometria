"""Estruturas de dados do pipeline (independentes de Django).

Um ``Record`` é uma linha de exportação de uma base, já normalizada.
Uma ``Family`` é o resultado da consolidação de registros por
encadeamento de números compartilhados.
"""
from __future__ import annotations

from dataclasses import dataclass, field
from datetime import date

SOURCES = ("lens", "espacenet", "google", "derwent", "inpi")
SOURCE_LABELS = {
    "lens": "Lens.org",
    "espacenet": "Espacenet",
    "google": "Google Patents",
    "derwent": "Derwent (WoS)",
    "inpi": "INPI (Brasil)",
}


@dataclass
class Pub:
    """Número de publicação normalizado."""

    raw: str
    number: str  # forma canônica sem código de tipo (ex.: US2010018287)
    kind: str  # código de tipo (A1, B2, U...)
    country: str
    date: date | None = None


@dataclass
class Priority:
    raw: str
    number: str  # forma canônica (alfanumérica, sem código de tipo)
    country: str  # escritório (receptor, no caso de PCT)
    date: date | None = None


@dataclass
class Record:
    source: str
    recorte: str  # "nucleo" | "BR" (ou outro rótulo do estudo)
    row: int  # posição na exportação (1-based)
    pubs: list[Pub] = field(default_factory=list)
    priorities: list[Priority] = field(default_factory=list)
    earliest_priority: date | None = None
    earliest_publication: date | None = None  # data informada pela base para a família
    title: str = ""
    abstract: str = ""  # resumo em redação original
    dwpi_title: str = ""
    dwpi_abstract: str = ""  # resumo DWPI completo
    dwpi_novelty: str = ""
    dwpi_use: str = ""
    applicants: list[str] = field(default_factory=list)
    inventors: list[str] = field(default_factory=list)
    ipc: list[str] = field(default_factory=list)  # já no padrão OMPI
    cpc: list[str] = field(default_factory=list)
    family_ids: list[str] = field(default_factory=list)  # LENS:..., DOCDB:...
    legal_status: str = ""
    cited_by: int | None = None
    cited_patents: list[str] = field(default_factory=list)  # números normalizados
    doc_type: str = ""

    @property
    def record_id(self) -> str:
        return f"{self.source}:{self.recorte}:{self.row}"

    @property
    def pub_numbers(self) -> list[str]:
        return sorted({p.number for p in self.pubs})

    def is_utility_model_only(self, kinds: tuple[str, ...] = ("U",)) -> bool:
        """Verdadeiro se TODAS as publicações do registro são modelos de utilidade."""
        if not self.pubs:
            return False
        return all(any(p.kind.startswith(k) for k in kinds) for p in self.pubs)

    def to_dict(self) -> dict:
        return {
            "source": self.source,
            "recorte": self.recorte,
            "row": self.row,
            "pubs": [
                {"raw": p.raw, "number": p.number, "kind": p.kind, "country": p.country,
                 "date": p.date.isoformat() if p.date else None}
                for p in self.pubs
            ],
            "priorities": [
                {"raw": p.raw, "number": p.number, "country": p.country,
                 "date": p.date.isoformat() if p.date else None}
                for p in self.priorities
            ],
            "earliest_priority": self.earliest_priority.isoformat() if self.earliest_priority else None,
            "earliest_publication": self.earliest_publication.isoformat() if self.earliest_publication else None,
            "title": self.title,
            "abstract": self.abstract,
            "dwpi_title": self.dwpi_title,
            "dwpi_abstract": self.dwpi_abstract,
            "dwpi_novelty": self.dwpi_novelty,
            "dwpi_use": self.dwpi_use,
            "applicants": self.applicants,
            "inventors": self.inventors,
            "ipc": self.ipc,
            "cpc": self.cpc,
            "family_ids": self.family_ids,
            "legal_status": self.legal_status,
            "cited_by": self.cited_by,
            "cited_patents": self.cited_patents,
            "doc_type": self.doc_type,
        }

    @classmethod
    def from_dict(cls, d: dict) -> "Record":
        def _d(v):
            return date.fromisoformat(v) if v else None

        return cls(
            source=d["source"], recorte=d["recorte"], row=d["row"],
            pubs=[Pub(p["raw"], p["number"], p["kind"], p["country"], _d(p["date"])) for p in d["pubs"]],
            priorities=[Priority(p["raw"], p["number"], p["country"], _d(p["date"])) for p in d["priorities"]],
            earliest_priority=_d(d["earliest_priority"]),
            earliest_publication=_d(d.get("earliest_publication")),
            title=d["title"], abstract=d["abstract"], dwpi_title=d.get("dwpi_title", ""),
            dwpi_abstract=d.get("dwpi_abstract", ""), dwpi_novelty=d.get("dwpi_novelty", ""),
            dwpi_use=d.get("dwpi_use", ""), applicants=d["applicants"], inventors=d["inventors"],
            ipc=d["ipc"], cpc=d["cpc"], family_ids=d["family_ids"], legal_status=d["legal_status"],
            cited_by=d["cited_by"], cited_patents=d["cited_patents"], doc_type=d["doc_type"],
        )


@dataclass
class Family:
    """Família consolidada (unidade de contagem)."""

    key: str  # identificador sequencial da rodada (F001...)
    records: list[Record]
    manual_link_ids: list[int] = field(default_factory=list)
    # Campos consolidados pela regra de prevalência
    fields: dict = field(default_factory=dict)
    origin: dict = field(default_factory=dict)  # campo -> base de origem

    @property
    def sources(self) -> list[str]:
        return [s for s in SOURCES if any(r.source == s for r in self.records)]

    @property
    def numbers(self) -> list[str]:
        nums = set()
        for r in self.records:
            nums.update(r.pub_numbers)
        return sorted(nums)

    @property
    def anchor(self) -> str:
        nums = self.numbers
        return nums[0] if nums else self.records[0].record_id
