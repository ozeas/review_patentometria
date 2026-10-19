# Formato de exportação — Derwent (Web of Science)

**Arquivo de exemplo:** `darwent_nucleo.txt` (também aceito como `derwent_*.txt`, `wos_*.txt`)
**Parser:** `core/parsers/derwent.py` · **Encoding:** UTF-8 com BOM · **Separador:** TAB (`\t`)

## Cabeçalho

```
PN 	TI 	AU 	AE 	GA 	AB 	TF 	EA 	DC 	MC 	IP 	PD 	AD 	FD 	PI 	DS 	FS 	CP 	CR 	DN 	MN 	RI 	CI 	RG
```

A primeira linha define as colunas; as linhas seguintes são registros. Campos multivalorados usam
`;` como separador interno.

## Colunas usadas

| Coluna | Campo interno | Observação |
|---|---|---|
| `PN` | publicações | família completa do DWPI |
| `TI` | título | |
| `AB` | resumo DWPI | reescrito pela Clarivate |
| `TF` | título DWPI | |
| `EA` / `DC` / `MC` | usados como reforço de contexto | |
| `IP` | IPC | formato `G01N-030/64`, normalizado |
| `PD` / `AD` / `FD` | datas de publicação/prioridade | |
| `PI` | prioridades | **número + data** (fonte preferencial de prioridade) |
| `CP` | citações | rede interna de citações |
| `CR` | referências citadas | |
| `AE` | depositantes (patentee) | |
| `AU` | inventores | |
| `DN` / `MN` | identificadores Derwent | |

## Campos ausentes

- Sem situação jurídica e sem contagem de citações *forward* (o `CP`/`CR` são citações do documento,
  não quantas vezes ele foi citado).
- Sem família DOCDB explícita: a família é a do próprio DWPI, agrupada pelo `PN`.

## Consulta

O arquivo **não** traz a consulta (o Web of Science a registra separadamente). Declare com
`manage.py registrar_consulta`.

## Observação de origem

O acesso ao Derwent Innovations Index depende de licença institucional (via Web of Science). O
nome do arquivo pode vir com o erro de digitação `darwent` — o registro de fontes aceita os dois.
