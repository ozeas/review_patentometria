"""Aderência entre a configuração do estudo e o corpus realmente exportado.

Existe porque a falha mais cara desta ferramenta é silenciosa: rodar um corpus
novo com a configuração de outro projeto produz famílias sem casamento lexical e
contagens "pequenas" que parecem resultado.
"""
from __future__ import annotations

CAMPOS = ("abstract", "ipc", "cpc", "priorities", "legal_status", "cited_by", "dwpi_abstract")
LIMITE_LEXICAL = 50.0      # % de famílias sem casamento que dispara aviso
LIMITE_SEM_CLASSIFICACAO = 50.0


def diagnosticar(result) -> dict:
    """Recebe o ``PipelineResult`` de ``core.pipeline.run`` e devolve contagens + avisos."""
    fams = result.families
    n = len(fams) or 1
    ausente = sum(1 for f in fams if (f.get("lexical") or {}).get("level") in (None, "", "ausente"))
    lexical_ausente_pct = round(100 * ausente / n, 1)

    nomes = [b.get("name", "") for b in result.config.get("blocks", [])]
    por_bloco = {nome: 0 for nome in nomes}
    for f in fams:
        hits = (f.get("lexical") or {}).get("title_abstract_hits") or {}
        for nome, termos in hits.items():
            if nome in por_bloco and termos:
                por_bloco[nome] += 1

    identificados = result.consolidation.identified
    por_base: dict[str, dict] = {}
    for rec in identificados:
        linha = por_base.setdefault(rec.source, {"n": 0, **{c: 0 for c in CAMPOS}})
        linha["n"] += 1
        for c in CAMPOS:
            if getattr(rec, c, None):
                linha[c] += 1

    avisos: list[str] = []
    informativos: list[str] = []
    if lexical_ausente_pct > LIMITE_LEXICAL:
        avisos.append(f"{lexical_ausente_pct}% das famílias sem casamento lexical — "
                      "a configuração do estudo pode ser de outro tema")
    for nome, qtd in por_bloco.items():
        if qtd == 0:
            avisos.append(f"bloco '{nome}' não casou em nenhuma família")
    total = len(identificados) or 1
    sem_ipc = sum(1 for rec in identificados if not (rec.ipc or rec.cpc))
    if identificados and 100 * sem_ipc / total > LIMITE_SEM_CLASSIFICACAO:
        avisos.append(f"{round(100 * sem_ipc / total, 1)}% dos registros sem IPC/CPC — "
                      "o bloco de classificação não filtra nada")
    for base, linha in sorted(por_base.items()):
        for c in CAMPOS:
            if linha["n"] and not linha[c]:
                informativos.append(f"{base} não exporta '{c}' nesta rodada")

    return {"lexical_ausente_pct": lexical_ausente_pct, "por_bloco": por_bloco,
            "por_base": por_base, "avisos": avisos, "informativos": informativos}
