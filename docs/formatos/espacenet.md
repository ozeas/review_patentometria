# Formato de exportação — Espacenet

**Arquivo de exemplo:** `espacenet_nucleo.csv`
**Parser:** `core/parsers/espacenet.py` · **Encoding:** UTF-8 · **Separador:** `;` (ponto e vírgula)

## Cabeçalho da consulta (3 primeiras linhas)

```
"Espacenet"; ...
"Patent search"; ...
"156 results found for (ta = "gas chromatography" OR ...) AND (ipc =/low "G01N" OR ...)"; ...
```

O parser localiza o cabeçalho das colunas pela linha que começa com `No`. A linha
`N results found for ...` é **evidência** do que foi executado: `manage.py extrair_consulta`
grava esse texto em `query_no_arquivo` (campo separado) e ele **não** substitui a consulta
registrada.

## Colunas usadas

| Coluna no arquivo | Campo interno | Observação |
|---|---|---|
| `No` | (marcador de cabeçalho) | |
| `Title` | título | |
| `Publication number` | número de publicação | multivalorado, uma linha por número |
| `Publication date` | data de publicação | idem |
| `Earliest priority` | data da prioridade mais antiga | **sem número de prioridade** |
| `Earliest publication` | data da publicação mais antiga | |
| `Applicants`, `Inventors` | depositantes, inventores | |
| `IPC`, `CPC` | IPC, CPC | normalizados ao padrão OMPI |
| `Family number` | família DOCDB | `DOCDB:<n>` |

## Campos ausentes

- **Sem resumo** (original ou reescrito).
- **Sem número de prioridade** — só a data. Consequência: o encadeamento por prioridade não conta
  com o Espacenet; a jurisdição de origem cai no critério secundário (publicação mais antiga
  nacional/regional, ignorando WO).
- Sem situação jurídica, sem citações.

## Consulta

Extraível do cabeçalho por `manage.py extrair_consulta <rodada>` (grava em `query_no_arquivo`).
