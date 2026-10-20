# Patentometria

Pipeline de análise patentométrica: importa exportações de bases de patentes, consolida famílias,
aplica triagem em duas etapas, calcula indicadores, prepara o VOSviewer e gera a planilha base.

```
Exportações (CSV/TXT) ──► Adaptadores por base ──► Normalização de números ──► Exclusão de modelos de utilidade
                                                                                         │
            ┌────────────────────────────────────────────────────────────────────────────┘
            ▼
 Encadeamento (union-find) por publicação, prioridade e família da base  +  ligações manuais
            │
            ▼
 Base unificada (famílias) ── regra de prevalência por campo (origem registrada)
            │                 IPC (padrão OMPI) · jurisdição de origem · datas · situação · citações
            │                 dicionários: depositantes → grupo econômico; inventores (pinyin)
            ▼
 Triagem etapa 1 (tema × contexto) ──► etapa 2 (segmento) ──► estratos S1/S2
            │
            ├─► Indicadores (períodos, jurisdição, CR4/CR8/HHI/Gini, IPC, janela 36 m, situação, citações)
            ├─► Pacote VOSviewer (corpus, escores, tesauro) ◄── importação de map/network → clusters
            └─► Planilha base .xlsx (PRISMA e estratos em fórmulas)
```

## Instalação

**Usuários (Windows, macOS, Linux).** Baixe o zip do seu sistema na página de releases, extraia e
execute o instalador (`install.ps1`, `install.command` ou `install.sh`). Não pede administrador e cria
atalhos no Desktop e no menu do sistema. Passo a passo e solução de problemas em
[`docs/INSTALACAO.md`](docs/INSTALACAO.md).

Com o pacote publicado no PyPI:

```bash
uv tool install patentometria
patentometria            # abre em http://127.0.0.1:8080
```

Os dados (banco, uploads, logs) ficam na pasta do usuário — `patentometria where` mostra o caminho.
O padrão é **somente local** (`127.0.0.1`); para abrir na rede, use `patentometria serve --host 0.0.0.0`
e libere a porta no firewall.

Publicação no PyPI: metadados e workflow em [`docs/PYPI.md`](docs/PYPI.md).

### Desenvolvimento

Requer Python 3.11 ou superior. As versões das dependências estão fixadas
(`requirements.txt` e `uv.lock`) — é o que permite dizer que duas execuções
rodaram o mesmo código.

```bash
uv venv --python 3.12 .venv && source .venv/bin/activate     # ou: python -m venv .venv
uv pip install -r requirements.txt                          # pip só se existir no sistema
python manage.py migrate
python manage.py runserver                                  # http://127.0.0.1:8000
```

> Em Arch/Omarchy com PEP 668 o `pip` do sistema não existe: use `uv` (é o que
> este projeto usa para travar as versões). `uv sync` também funciona, porque as
> dependências estão declaradas no `pyproject.toml`.

Opcional: `python manage.py createsuperuser` dá acesso a `/admin/`, onde todos os modelos podem ser
editados.

## Uso pela interface

1. **Estudo.** Crie um estudo com o padrão genérico (blocos, classificação, períodos, etapas e estratos
   a preencher; a regra de prevalência já vem pronta) ou carregue um preset JSON. A configuração é
   editável na tela e em JSON.
2. **Rodada.** Crie uma rodada com a data da coleta e envie os arquivos.
   - Base e recorte são detectados pelo conteúdo e pelo nome (`lens_nucleo.csv`, `espacenet_BR.csv`,
     `darwent_nucleo.txt`).
   - Os `*_query.txt` enviados juntos ficam registrados como a consulta do arquivo correspondente.
   - Os `*_concepts.csv` são ignorados.
3. **Consolidar.** O fluxo PRISMA aparece na página da rodada.
4. **Ligações.** Revise as sugestões: famílias sem número em comum, com mesma prioridade, mesmo
   depositante e título semelhante. Aceite as procedentes e reexecute a consolidação.
5. **Nomes.** Harmonize depositantes e grupos econômicos e traduza grafias em chinês. Confira o pinyin
   dos inventores. Reexecute a consolidação.
6. **Triagem.** "Triar etapa 1" percorre as famílias pendentes. Para cada uma, a página mostra:
   - título e resumo com os termos dos blocos destacados;
   - presença dos termos no título e no título + resumo;
   - campos com a base de origem.

   Repita na etapa 2 e na atribuição de estratos.
7. **Indicadores.** Escolha o conjunto (unificada, após etapa 1, base final), opcionalmente por estrato.
   A página traz o recálculo por estrato.
8. **VOSviewer.** Baixe o pacote, gere o mapa no VOSviewer e importe os arquivos `map` e `network`. A
   aplicação calcula, por cluster: ocorrências, ano médio, fração na janela recente, coesão e força
   entre clusters.
9. **Planilha base.** Baixe a planilha. As abas PRISMA e S6_Estratos usam fórmulas sobre as abas de
   dados; a coluna de conferência traz o valor calculado pela aplicação.

O trabalho manual pertence ao **estudo**, não à rodada: decisões de elegibilidade, ligações manuais,
dicionários e tesauro. Decisões e ligações são ancoradas em números de publicação normalizados, de modo
que uma nova coleta herda o que já foi decidido para as mesmas famílias. Só as famílias novas aparecem
como pendentes.

## Configuração do estudo

Seis partes, todas editáveis na tela do estudo:

- **Blocos lexicais** — dois grupos de termos: o tema e o contexto de aplicação. A triagem lexical mede
  a presença dos dois.
- **Bloco de classificação** — códigos IPC/CPC que delimitam a busca (vazio = não filtra).
- **Períodos e janela recente** — faixas de prioridade e a janela, em meses, contada da data da coleta.
- **Etapa 1 e etapa 2** — rótulos, segmentos de inclusão e motivos de exclusão.
- **Estratos** — códigos, nomes e definições (por padrão S1 núcleo e S2 aplicado).
- **Prevalência** — de qual base vem cada campo quando mais de uma o possui.

O preset `studies/presets/vazio.json` reproduz o padrão genérico. Presets próprios podem ser salvos em
JSON e carregados na criação de um estudo:

```bash
python manage.py exportar_preset 1 -o studies/presets/meu-desenho.json
```

## Uso pela linha de comando

```bash
python manage.py importar_rodada --estudo "Meu estudo" --rodada "01/01/2026" --data 2026-01-01 \
       --pasta ./dados/2026-01-01 --execucao "01/01/2026 16h"
python manage.py executar_rodada 1                       # imprime o fluxo PRISMA (--json para máquina)
python manage.py executar_rodada 1 --exigir-consulta     # falha (código 1) se faltar consulta registrada
python manage.py importar_trabalho 1 decisoes decisoes.csv
python manage.py importar_trabalho 1 depositantes depositantes.xlsx
python manage.py importar_trabalho 1 tesauro thesaurus.txt --substituir
python manage.py exportar_planilha 1 -o base.xlsx --vos vosviewer.zip
python manage.py exportar_estudo 1 -o estudo_1.json       # backup do trabalho manual (JSON)
python manage.py importar_estudo estudo_1.json --estudo 2  # restaura em outro estudo
python manage.py conferir_regressao 1 referencia.json --exigir-procedencia
```

### Procedência da rodada

Cada exportação guarda, além do arquivo: **sha256 do conteúdo**, consulta registrada, data/hora da
busca e número de registros. `executar_rodada --json` e `exportar_estudo` emitem esse bloco
(`procedencia`) com o que está faltando (`sem_consulta`, `sem_hash`, `sem_data_execucao`), e
`conferir_regressao --exigir-procedencia` transforma qualquer falta em falha.

### Consulta declarada × consulta lida do arquivo

- `query_text` — **consulta registrada**, declarada pelo analista (tela do arquivo ou
  `manage.py registrar_consulta`). É o que os porteiros exigem.
- `query_no_arquivo` — texto que a própria exportação imprime no cabeçalho
  (`manage.py extrair_consulta <rodada>`). É **evidência** do que foi executado, nunca substitui a
  declarada.
- Divergência entre as duas é sinalizada na tela e no relatório; com `--exigir-consulta` ela falha
  (código 1).
- `ingest()` não lê consulta de arquivo — há teste garantindo isso.
- Só Espacenet e Google imprimem a consulta no arquivo (Lens e Derwent não).

### Aderência da configuração ao corpus

Se a configuração não casar com o corpus (bloco sem casamento, famílias sem termo no título/resumo,
registros sem IPC/CPC), `executar_rodada` avisa e `--exigir-aderencia` falha com código 1. É a proteção
contra rodar um corpus novo com a configuração de outro tema e achar que o resultado pequeno é achado.

### Matriz de campos por base

O que cada exportação traz (a tela de configuração mostra a mesma tabela e a validação recusa
prevalência que prefira uma base sem o campo):

| campo | Lens.org | Espacenet | Google Patents | Derwent (WoS) | INPI |
|---|---|---|---|---|---|
| título | ✓ | ✓ | ✓ | ✓ | ✓ |
| resumo | ✓ | — | — | ✓ (DWPI) | — |
| IPC/CPC | ✓ | ✓ | — | ✓ (IPC) | ✓ |
| prioridade (número) | ✓ | — (só data) | — | ✓ | — |
| família | ✓ (simples/DOCDB) | ✓ (DOCDB) | — | ✓ (DWPI) | — |
| situação jurídica | ✓ | — | — | — | — |
| citações | ✓ | — | — | — (CP/CR são do documento) | — |
| consulta no arquivo | — | ✓ | ✓ | — | — |
| contrato de formato | `docs/formatos/lens.md` | `espacenet.md` | `google.md` | `derwent.md` | `inpi.md` |

> **INPI é contrato provisório.** Não havia exportação real do INPI quando o parser foi escrito: ele
> reconhece o cabeçalho por sinônimos e **recusa** o que não casa, citando `docs/formatos/inpi.md`.
> Antes de usar em produção, exporte 5–10 registros, ajuste os sinônimos e atualize o registro em
> `core/sources.py`.

### Cache

`Round.cache` guarda PRISMA, BR, sugestões de ligação, diagnóstico e procedência. O cache é refeito
quando muda qualquer insumo (config, arquivos, decisões, ligações, dicionários ou tesauro), por hash —
não por evento. Indicadores são calculados sobre as famílias gravadas, sem rodar o pipeline.

## Regras implementadas

| Etapa | Regra | Onde |
|---|---|---|
| Normalização | remoção de não alfanuméricos; maiúsculas; código de tipo desconsiderado; WO aa+5 → aaaa+6; US pré-concessão aaaa+7 → aaaa+6; EP com 7 dígitos | `core/normalize.py` |
| Modelos de utilidade | registro excluído quando **todas** as suas publicações têm código de tipo U; famílias Derwent mistas são mantidas | `core/records.py` |
| Encadeamento | união transitiva por publicação, prioridade, família simples (Lens) e família DOCDB (Espacenet) | `core/consolidate.py` |
| Prioridades no encadeamento | só números com ≥ 8 dígitos (configurável: `prio_link_min_digits`). Números Derwent sem ano não ligam famílias, para evitar colisões | `core/normalize.py` |
| Prevalência | publicações ← Derwent; título/resumo ← Lens; IPC ← Espacenet; depositantes/inventores ← Lens; ordens de reserva configuráveis | `core/prevalence.py` |
| Jurisdição de origem | prioridade mais antiga (Derwent, depois Lens). PCT: escritório receptor. Sem número: publicação nacional/regional mais antiga, sem WO | `core/prevalence.py` |
| Situação jurídica | Lens; vigente (active/patented) > em exame (pending) > inativa; situação mais favorável da família | `core/prevalence.py` |
| Citações | Lens, maior valor entre as publicações; rede interna pelo campo CP do Derwent | `core/indicators.py` |
| Janela recente | 1ª publicação nos N meses anteriores à coleta | `core/prevalence.py` |
| Corpus VOSviewer | título + resumo original; sem ele, título + NOVELTY + USE do DWPI; senão, título | `core/prevalence.py` |
| Tesauro | exclusões antes das unificações (o VOSviewer ignora exclusão na última linha) | `core/vosviewer.py` |
| Procedência | sha256 do arquivo, consulta registrada e data/hora por exportação; falta vira falha com `--exigir-consulta` / `--exigir-procedencia` | `studies/services.py` |
| Porteiro de regressão | `conferir_regressao` sai com **código 1** na divergência (serve a script, não só a relatório) | `studies/management/commands/` |
| Backup do trabalho manual | `exportar_estudo` / `importar_estudo` em JSON, ancorado por número de publicação; reimportar não duplica | `studies/management/commands/` |

## Estrutura

```
core/            pipeline em Python puro (sem Django) — testável e reutilizável em scripts
  parsers/       um adaptador por base (lens, espacenet, google, derwent, inpi)
  normalize.py   números, datas, IPC/CPC, nomes, pinyin
  consolidate.py union-find, ligações manuais, sugestões, recortes
  prevalence.py  campos consolidados com origem
  lexical.py     ocorrência dos blocos no título e no título + resumo
  indicators.py  distribuições, concentração, citações
  vosviewer.py   corpus, escores, tesauro, leitura de mapa/rede
  pipeline.py    orquestração, decisões, PRISMA
  config.py      esquema, validação e padrão genérico
studies/         aplicação Django (modelos, telas, exportação, comandos)
  presets/       preset genérico (vazio.json)
tests/           núcleo e aplicação; fixtures sintéticas de cada base
scripts/         smoke do wheel e porteiro de metadados do PyPI
install/         instaladores por sistema e montagem do release
docs/            instalação, PyPI e formatos de exportação
```

Para acrescentar uma base, implemente `parse(text, recorte) -> list[Record]` em `core/parsers/` e
registre-a em `PARSERS`.

## Limitações conhecidas

- A ordem sobrenome–prenome de inventores latinos não é inferida automaticamente; use o dicionário de
  inventores. A transcrição pinyin é aplicada aos nomes em chinês.
- Nomes de depositantes em chinês dependem do dicionário para a tradução ao inglês.
- O Google Patents não exporta resumo, IPC nem números de prioridade. Famílias exclusivas dessa base
  entram no corpus só com o título e ficam fora das análises de IPC.
- A aplicação não executa o VOSviewer. Ela prepara a entrada e lê os arquivos de mapa e de rede
  exportados pelo programa.

## Licença

MIT — ver [`LICENSE`](LICENSE).
