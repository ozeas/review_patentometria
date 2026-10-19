# Formato de exportação — Google Patents

**Arquivo de exemplo:** `google_nucleo.csv`
**Parser:** `core/parsers/google.py` · **Encoding:** UTF-8 · **Separador:** `,`

## Primeira linha: a consulta

```
search URL:,https://patents.google.com/?q=...&country=WO%2CUS%2CEP%2CCN&type=PATENT
```

O parser ignora essa linha ao ler os registros. `manage.py extrair_consulta` grava a URL em
`query_no_arquivo` (evidência), **não** na consulta registrada. A URL carrega a equação e os
filtros (`country`, `type`) — é o melhor registro do que foi executado nessa base.

## Colunas usadas

| Coluna no arquivo | Campo interno | Observação |
|---|---|---|
| `id` | número de publicação | uma linha por publicação representativa |
| `title` | título | |
| `assignee` | depositantes | separados por vírgula, com cuidado para sufixos societários |
| `inventor/author` | inventores | idem |
| `publication date` | data de publicação | |
| `priority date` | data de prioridade | quando presente |

## Campos ausentes

- **Sem resumo**, **sem IPC/CPC**, **sem número de prioridade**, sem família DOCDB, sem situação
  jurídica e sem citações.

Consequência prática: famílias exclusivas do Google entram no corpus só com o título e ficam fora
das análises de IPC; e a prevalência nunca deve preferir `google` para `abstract`/`ipc` (a
validação de configuração recusa).

## Consulta

Extraível da URL da primeira linha. A comparação com a consulta declarada usa normalização
(URL decodificada) — declarar o texto legível fará a comparação acusar divergência, o que é
esperado.
