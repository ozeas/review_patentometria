# Formato de exportação — Lens.org

**Arquivo de exemplo:** `lens_nucleo.csv` (export "CSV" da lista de resultados, salvo como UTF-8)
**Parser:** `core/parsers/lens.py` · **Encoding:** UTF-8 com BOM (`utf-8-sig`) · **Separador:** `,`

## Colunas usadas

| Coluna no arquivo | Campo interno | Observação |
|---|---|---|
| `Jurisdiction` | jurisdição da publicação | código de 2 letras |
| `Kind` | código de tipo | usado na exclusão de modelo de utilidade |
| `Display Key` | número de publicação | normalizado por `normalize_pub` |
| `Lens ID` | identificador | não entra no encadeamento |
| `Publication Date` / `Publication Year` | data de publicação | |
| `Priority Numbers` | prioridades | lista separada por `;` |
| `Earliest Priority Date` | data de prioridade | |
| `Title`, `Abstract` | título, resumo | resumo em redação original |
| `Applicants`, `Inventors`, `Owners` | depositantes, inventores | |
| `IPCR Classifications`, `CPC Classifications` | IPC, CPC | normalizados ao padrão OMPI |
| `Legal Status` | situação jurídica | `ACTIVE`, `PENDING`, `DISCONTINUED`… |
| `Cited by Patent Count` | citações recebidas | |
| `Document Type` | tipo de documento | |

## Famílias

O Lens exporta a **família simples** num campo próprio; o parser também aproveita a família
DOCDB quando presente. É a base que fornece o **resumo original**, e por isso é a preferencial
para `title` e `abstract`.

## Consulta

A exportação **não** traz a consulta no conteúdo. Registre-a com `manage.py registrar_consulta`
(colando o histórico da busca) — o texto do arquivo nunca é usado como consulta registrada.

## Limitações conhecidas

- Exportação grande pode vir truncada pela interface (conferir o número de linhas com o total
  declarado na tela do Lens).
- `Owners` não é lido: o depositante é `Applicants`.
