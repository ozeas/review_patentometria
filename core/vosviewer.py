"""Pacote de entrada do VOSviewer e leitura dos arquivos de mapa e rede.

Saídas: corpus (um documento por linha), escores (ano de prioridade e
pertença à janela recente) e tesauro (unificações e exclusões).
Entradas: arquivos de mapa (``map``) e de rede (``network``) exportados
pelo VOSviewer, para os indicadores por cluster.
"""
from __future__ import annotations

import csv
import io
import re
from collections import defaultdict


def clean_line(s: str) -> str:
    return re.sub(r"\s+", " ", s or "").strip()


def build_corpus(fams: list[dict], text_fn) -> tuple[str, str, list[dict]]:
    """``text_fn(fields) -> (texto, modo)``. Retorna (corpus, escores, controle)."""
    corpus, scores, control = [], ["score<Ano de prioridade>\tscore<Janela recente>"], []
    for f in fams:
        text, mode = text_fn(f["fields"])
        corpus.append(clean_line(text))
        year = f["fields"].get("priority_year") or ""
        win = 1 if f["fields"].get("recent_window") else 0
        scores.append(f"{year}\t{win}")
        control.append({"linha": len(corpus), "familia": f["key"], "modo": mode,
                        "ano": year, "janela": win})
    return "\n".join(corpus) + "\n", "\n".join(scores) + "\n", control


def build_thesaurus(entries: list[dict]) -> str:
    """``entries`` = [{"label":..., "replace_by":...}] (replace_by vazio = exclusão).
    As exclusões vêm antes das unificações: o VOSviewer pode ignorar a
    última linha do arquivo quando ela é uma exclusão."""
    excl = [e for e in entries if not (e.get("replace_by") or "").strip()]
    unif = [e for e in entries if (e.get("replace_by") or "").strip()]
    lines = ["label\treplace by"]
    lines += [f"{e['label'].strip()}\t" for e in excl]
    lines += [f"{e['label'].strip()}\t{e['replace_by'].strip()}" for e in unif]
    return "\n".join(lines) + "\n"


def parse_thesaurus(text: str) -> list[dict]:
    out = []
    for i, line in enumerate(text.lstrip("﻿").splitlines()):
        if not line.strip():
            continue
        parts = line.split("\t")
        if i == 0 and parts[0].strip().lower() == "label":
            continue
        out.append({"label": parts[0].strip(), "replace_by": parts[1].strip() if len(parts) > 1 else ""})
    return out


def parse_map(text: str) -> list[dict]:
    text = text.lstrip("﻿")
    delim = "\t" if "\t" in text.splitlines()[0] else ","
    rows = list(csv.DictReader(io.StringIO(text), delimiter=delim))
    out = []
    for r in rows:
        occ_key = next((k for k in r if k and "Occurrences" in k), None)
        scores = {k: r[k] for k in r if k and k.startswith("score<")}
        out.append({
            "id": r.get("id"), "label": r.get("label"),
            "cluster": int(r["cluster"]) if r.get("cluster") not in (None, "") else None,
            "occurrences": float(r[occ_key]) if occ_key and r[occ_key] else 0.0,
            "scores": {k: float(v) for k, v in scores.items() if v not in ("", None)},
        })
    return out


def parse_network(text: str) -> list[tuple[str, str, float]]:
    out = []
    for line in text.lstrip("﻿").splitlines():
        parts = re.split(r"[\t,]", line.strip())
        if len(parts) >= 3:
            try:
                out.append((parts[0], parts[1], float(parts[2])))
            except ValueError:
                continue
    return out


def cluster_indicators(items: list[dict], links: list[tuple[str, str, float]]) -> dict:
    by_id = {it["id"]: it for it in items}
    clusters = defaultdict(list)
    for it in items:
        if it["cluster"] is not None:
            clusters[it["cluster"]].append(it)
    internal = defaultdict(float)
    involving = defaultdict(float)
    between = defaultdict(float)
    for a, b, s in links:
        ca = by_id.get(a, {}).get("cluster")
        cb = by_id.get(b, {}).get("cluster")
        if ca is None or cb is None:
            continue
        if ca == cb:
            internal[ca] += s
            involving[ca] += s
        else:
            involving[ca] += s
            involving[cb] += s
            between[tuple(sorted((ca, cb)))] += s
    score_keys = sorted({k for it in items for k in it["scores"]})
    rows = []
    for c in sorted(clusters):
        its = clusters[c]
        occ = sum(i["occurrences"] for i in its)
        row = {"cluster": c, "termos": len(its), "ocorrencias": occ,
               "termos_lista": ", ".join(i["label"] for i in sorted(its, key=lambda x: -x["occurrences"])),
               "coesao": round(internal[c] / involving[c], 3) if involving[c] else None}
        for k in score_keys:
            w = [(i["scores"][k], i["occurrences"]) for i in its if k in i["scores"]]
            tot = sum(o for _, o in w)
            row[k] = round(sum(v * o for v, o in w) / tot, 3) if tot else None
        rows.append(row)
    return {
        "clusters": rows,
        "entre_clusters": [{"cluster_a": a, "cluster_b": b, "forca": s} for (a, b), s in sorted(between.items())],
        "termos": len(items), "ligacoes": len(links),
        "forca_total": sum(s for _, _, s in links),
        "score_keys": score_keys,
    }
