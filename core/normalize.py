"""Normalização de números de publicação, prioridade, IPC/CPC e nomes.

Regras (Material e Métodos, seção 2.1):
- remoção de hífens, espaços, barras e demais caracteres não alfanuméricos;
- conversão para maiúsculas;
- desconsideração do código de tipo (kind code) na comparação;
- conversão de formatos numéricos divergentes entre bases:
    WO 1999/058951 A1 (Lens)   ≡ WO9958951-A1 (Derwent)   → WO1999058951
    US 2010/0018287 A1 (Lens)  ≡ US2010018287A1 (Espacenet) → US2010018287
    EP92975-A (Derwent)        → EP0092975 (EP com 7 dígitos)
"""
from __future__ import annotations

import re
import unicodedata
from datetime import date, datetime

from .records import Priority, Pub

_NON_ALNUM = re.compile(r"[^0-9A-Za-z]")
_PUB_RE = re.compile(r"^([A-Z]{2})(\d+)([A-Z]\d?)?$")
_MONTHS = {m: i for i, m in enumerate(
    ["JAN", "FEB", "MAR", "APR", "MAY", "JUN", "JUL", "AUG", "SEP", "OCT", "NOV", "DEC"], start=1)}


def alnum_upper(value: str) -> str:
    return _NON_ALNUM.sub("", value or "").upper()


def split_kind(value: str) -> tuple[str, str, str]:
    """Separa país, dígitos e código de tipo. Retorna ('', valor, '') se não reconhecer."""
    s = alnum_upper(value)
    m = _PUB_RE.match(s)
    if not m:
        return "", s, ""
    return m.group(1), m.group(2), m.group(3) or ""


def canonical_number(country: str, digits: str) -> str:
    """Converte os dígitos ao formato canônico por escritório."""
    if country == "WO":
        if len(digits) == 7:  # yy + 5 dígitos (formato anterior a 2004)
            yy = int(digits[:2])
            year = 1900 + yy if yy >= 70 else 2000 + yy
            digits = f"{year}{digits[2:].zfill(6)}"
        elif len(digits) == 9 and digits[:2] in ("19", "20"):  # yyyy + 5
            digits = f"{digits[:4]}{digits[4:].zfill(6)}"
    elif country == "US":
        # Pedido pré-concessão: yyyy + 7 dígitos com zero inicial (Lens) → yyyy + 6
        if len(digits) == 11 and digits[:2] in ("19", "20") and digits[4] == "0":
            digits = digits[:4] + digits[5:]
    elif country == "EP":
        if len(digits) < 7:
            digits = digits.zfill(7)
    return f"{country}{digits}"


def normalize_pub(raw: str, pub_date: date | None = None) -> Pub | None:
    raw = (raw or "").strip()
    if not raw:
        return None
    country, digits, kind = split_kind(raw)
    if not country:
        return Pub(raw=raw, number=digits, kind="", country="", date=pub_date)
    return Pub(raw=raw, number=canonical_number(country, digits), kind=kind,
               country=country, date=pub_date)


def normalize_priority(raw: str, prio_date: date | None = None) -> Priority | None:
    raw = (raw or "").strip()
    if not raw:
        return None
    s = alnum_upper(raw)
    country, digits, kind = split_kind(s)
    if country:
        number = f"{country}{digits}"
    else:
        number = s
        country = s[:2]
    # Pedido internacional (PCT): escritório receptor
    # Lens: "CN 2025078734 W" (kind W) → CN ; Derwent: "WOUS044396" → US
    if s.startswith("WO") and len(s) > 4 and s[2:4].isalpha():
        country = s[2:4]
    return Priority(raw=raw, number=number, country=country, date=prio_date)


def priority_link_eligible(p: Priority, min_digits: int) -> bool:
    """Prioridades curtas (ex.: Derwent 'US184874', sem ano) não entram no
    encadeamento, para evitar colisão entre pedidos de anos distintos."""
    digits = re.sub(r"\D", "", p.number)
    return len(digits) >= min_digits


# ---------------------------------------------------------------- datas
def parse_date(value: str) -> date | None:
    value = (value or "").strip()
    if not value:
        return None
    for fmt in ("%Y-%m-%d", "%d/%m/%Y", "%Y/%m/%d", "%Y%m%d"):
        try:
            return datetime.strptime(value[:10], fmt).date()
        except ValueError:
            pass
    m = re.match(r"(\d{1,2})\s+([A-Za-z]{3})\s+(\d{4})", value)  # Derwent: 19 Jul 2010
    if m and m.group(2).upper() in _MONTHS:
        return date(int(m.group(3)), _MONTHS[m.group(2).upper()], int(m.group(1)))
    return None


# ---------------------------------------------------------------- IPC/CPC
_IPC_RE = re.compile(r"^([A-H]\d{2}[A-Z])\s*-?\s*0*(\d+)\s*/\s*(\d+)")


def normalize_ipc(raw: str) -> str | None:
    """'G01N30/64', 'G01N-030/64', 'G01N 30/64 (EP,US)' → 'G01N 30/64'."""
    s = (raw or "").strip().upper()
    if not s:
        return None
    s = s.split(",")[0]  # conjuntos de combinação do Espacenet: primeiro código
    s = re.sub(r"\(.*?\)", "", s).strip()
    m = _IPC_RE.match(s)
    if not m:
        m2 = re.match(r"^([A-H]\d{2}[A-Z])$", s)
        return m2.group(1) if m2 else None
    return f"{m.group(1)} {int(m.group(2))}/{m.group(3)}"


def ipc_subclass(code: str) -> str:
    return code[:4]


def ipc_main_group(code: str) -> str:
    """'G01N 30/64' → 'G01N 30'."""
    return code.split("/")[0]


def dedupe(seq):
    seen, out = set(), []
    for x in seq:
        if x and x not in seen:
            seen.add(x)
            out.append(x)
    return out


# ---------------------------------------------------------------- nomes
_COUNTRY_TAG = re.compile(r"\s*\[[A-Z]{2}\]\s*$")
_DERWENT_CODE = re.compile(r"\s*\([A-Z0-9]{3,5}(-[A-Za-z\- ]+)?\)\s*$")


def clean_name(raw: str) -> str:
    s = unicodedata.normalize("NFKC", raw or "").strip()
    s = _COUNTRY_TAG.sub("", s)
    s = _DERWENT_CODE.sub("", s)
    s = re.sub(r"\s+", " ", s)
    return s.strip(" ;,")


def name_key(raw: str) -> str:
    """Chave de comparação de nomes: maiúsculas, sem pontuação nem acentos."""
    s = clean_name(raw)
    s = unicodedata.normalize("NFKD", s)
    s = "".join(c for c in s if not unicodedata.combining(c))
    s = re.sub(r"[^\w\s&]", " ", s.upper())
    return re.sub(r"\s+", " ", s).strip()


def token_key(raw: str) -> frozenset:
    """Conjunto de tokens do nome — identifica 'ZHANG JUHE' e 'JUHE ZHANG'."""
    return frozenset(name_key(raw).split())


def has_cjk(s: str) -> bool:
    return any("一" <= c <= "鿿" or "㐀" <= c <= "䶿" for c in s or "")


def pinyin_name(chinese: str) -> str:
    """Transcrição pinyin na ordem sobrenome–prenome, em maiúsculas
    (padrão das demais bases: 'ZHANG JUHE')."""
    try:
        from pypinyin import lazy_pinyin
    except ImportError:  # pragma: no cover
        return chinese
    chars = [c for c in chinese.strip() if not c.isspace()]
    if not chars:
        return ""
    syl = lazy_pinyin(chars)
    # Sobrenomes compostos mais comuns (dois caracteres)
    compound = {"欧阳", "司马", "上官", "诸葛", "东方", "皇甫", "尉迟", "公孙", "慕容", "令狐", "夏侯", "端木"}
    n_surname = 2 if "".join(chars[:2]) in compound and len(chars) > 2 else 1
    surname = "".join(syl[:n_surname]).upper()
    given = "".join(syl[n_surname:]).upper()
    return f"{surname} {given}".strip()
