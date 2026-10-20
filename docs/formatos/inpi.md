# Formato de exportação — INPI (Brasil)

> **Status: contrato provisório — não validado com exportação real.**
> Em 19/10/2026 não havia nenhuma amostra de exportação do INPI nesta máquina. O que está abaixo é
> o contrato que o parser (`core/parsers/inpi.py`) espera: nomes de coluna aceitos, o que ele recusa
> e o que precisa ser coletado para fechar o formato. **Não invente colunas**: se a exportação real
> não casar, o parser levanta `ValueError` citando este documento.

## Onde buscar

`https://busca.inpi.gov.br` — a busca é por **classificação** (via principal) e por texto em
português (via de controle; documento INPI em PT não casa com palavra-chave em inglês). Ver
o documento de consultas do projeto.

## Colunas esperadas (sinônimos aceitos)

| Campo interno | Nomes de coluna aceitos |
|---|---|
| número do pedido | `Pedido`, `Número do pedido`, `Nº do pedido`, `Processo`, `Numero` |
| título | `Título`, `Title` |
| classificação | `Classificação`, `IPC`, `CPC` |
| depositante | `Depositante`, `Requerente`, `Titular`, `Applicant` |
| inventor | `Inventor`, `Inventores` |
| data de depósito | `Data de depósito`, `Data do depósito`, `Data depósito` |
| data de publicação | `Data de publicação`, `Data da publicação`, `Data publicação` |

- **Encoding:** UTF-8 (com BOM aceito); se vier em ISO-8859-1, converter antes.
- **Separador:** `;` ou `,` — detectado pela primeira linha.
- **Múltiplos valores** dentro de uma célula: separados por `;`, `,` ou `|`.

## Campos ausentes (esperados)

Sem resumo estruturado, sem citações, sem situação jurídica, sem família DOCDB. Consequência: o
INPI tende a ser base de **conferência de cobertura nacional**, não de prevalência de metadados.

## Como fechar este contrato

1. Exportar uma busca pequena (5–10 registros) de `busca.inpi.gov.br` em CSV ou XLSX.
2. Salvar como `tests/fixtures/inpi_sample.csv` **e** atualizar a tabela de sinônimos acima com os
   nomes reais.
3. Rodar `python manage.py test tests.test_inpi` — o teste de formato real (hoje sintético) deve
   passar com a fixture oficial.
4. Atualizar `exporta=` em `core/sources.py` (registro `inpi`) com o que a base realmente traz e
   remover a nota "contrato provisório".

## Consulta

O INPI provavelmente não imprime a consulta no arquivo exportado. Declare com
`manage.py registrar_consulta` (via principal: só-classificação, ex.: `(cl=G01N30 OR cl=E21B49) NOT
cl=C10G`).
