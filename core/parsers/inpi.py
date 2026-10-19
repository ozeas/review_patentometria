"""INPI (Brasil) — exportação de busca por classificação e/ou texto em português.

ATENÇÃO: o formato de exportação do INPI **não foi observado** nesta máquina
(verificado em 19/10/2026). O mapeamento abaixo usa sinônimos prováveis e o
parser **recusa explicitamente** o que não reconhece, citando
``docs/formatos/inpi.md``. Antes de usar em produção, atualize os sinônimos e a
documentação com uma exportação real.
"""
from __future__ import annotations

import csv
import io
import re
import unicodedata

from ..normalize import clean_name, dedupe, normalize_ipc, normalize_pub, parse_date
from ..records import Record

SINONIMOS = {
    "numero": ["pedido", "numero do pedido", "n do pedido", "nº do pedido", "processo", "numero", "número"],
    "titulo": ["titulo", "título", "title"],
    "ipc": ["classificacao", "classificação", "ipc", "cpc"],
    "depositante": ["depositante", "requerente", "titular", "applicant"],
    "inventor": ["inventor", "inventores"],
    "deposito": ["data de deposito", "data de depósito", "data do deposito", "data deposito"],
    "publicacao": ["data de publicacao", "data de publicação", "data da publicacao", "data publicacao"],
}

DOC = "docs/formatos/inpi.md"


def _norm(h: str) -> str:
    h = unicodedata.normalize("NFKD", str(h or "")).encode("ascii", "ignore").decode().lower()
    return re.sub(r"\s+", " ", h).strip()


def _colunas(header: list[str]) -> dict[str, str]:
    mapa, norm = {}, {_norm(h): h for h in header}
    for campo, apelidos in SINONIMOS.items():
        for a in apelidos:
            if _norm(a) in norm:
                mapa[campo] = norm[_norm(a)]
                break
    return mapa


def _lista(valor: str) -> list[str]:
    return [x.strip() for x in re.split(r"[;|]", valor or "") if x.strip()]


def parse(text: str, recorte: str) -> list[Record]:
    linhas = [l for l in (text or "").lstrip("\ufeff").splitlines() if l.strip()]
    if not linhas:
        raise ValueError(f"Arquivo vazio — ver {DOC}")
    delim = ";" if linhas[0].count(";") >= linhas[0].count(",") else ","
    leitor = list(csv.DictReader(io.StringIO("\n".join(linhas)), delimiter=delim))
    if not leitor:
        raise ValueError(f"Arquivo sem linhas de dados — ver {DOC}")
    mapa = _colunas(list(leitor[0].keys()))
    if "numero" not in mapa or "titulo" not in mapa:
        raise ValueError(
            "Formato INPI não reconhecido: preciso de coluna de número do pedido e de título. "
            f"Ver {DOC} e ajuste SINONIMOS em core/parsers/inpi.py")

    out: list[Record] = []
    for i, row in enumerate(leitor, start=1):
        pub = normalize_pub(row.get(mapa["numero"], ""),
                            parse_date(row.get(mapa.get("publicacao", ""), "")))
        if not pub:
            continue
        ipc = dedupe(normalize_ipc(x) for x in re.split(r"[;,|]", row.get(mapa.get("ipc", ""), "")) if x.strip())
        out.append(Record(
            source="inpi", recorte=recorte, row=i, pubs=[pub],
            earliest_priority=parse_date(row.get(mapa.get("deposito", ""), "")),
            earliest_publication=parse_date(row.get(mapa.get("publicacao", ""), "")),
            title=(row.get(mapa["titulo"], "") or "").strip(),
            applicants=dedupe(clean_name(a) for a in re.split(r"[;,|]", row.get(mapa.get("depositante", ""), "")) if a.strip()),
            inventors=dedupe(clean_name(a) for a in re.split(r"[;,|]", row.get(mapa.get("inventor", ""), "")) if a.strip()),
            ipc=ipc,
        ))
    return out
