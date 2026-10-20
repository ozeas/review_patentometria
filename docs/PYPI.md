# Publicação no PyPI

Pacote configurado (`pyproject.toml`, `LICENSE` MIT e `.github/workflows/publish.yml`), versão
**0.3.1**. Falta apenas o cadastro do *pending publisher* na conta do PyPI — depois disso a publicação
é automática a cada tag `v*`.

## 1. Licença (definida)

`license = "MIT"` em `pyproject.toml` e `LICENSE` na raiz. O porteiro confere:

```bash
uv run python scripts/check_pypi.py
# esperado: PyPI OK: patentometria 0.3.1
```

## 2. Publicar com Trusted Publishing (recomendado, sem token)

O workflow `.github/workflows/publish.yml` publica em qualquer tag `v*`.

1. No PyPI, crie o *pending publisher* em
   <https://pypi.org/manage/account/publishing/> com:
   - **PyPI Project Name:** `patentometria`
   - **Owner:** `ozeas`
   - **Repository name:** `review_patentometria`
   - **Workflow name:** `publish.yml`
   - **Environment name:** `pypi`
2. No GitHub, crie o environment `pypi` em
   *Settings → Environments → New environment* (sem segredos; o OIDC faz o resto).
3. Publique:

```bash
git tag -a v0.3.1 -m "Patentometria 0.3.1"
git push origin v0.3.1
```

Acompanhar:

```bash
gh run watch "$(gh run list --workflow=publish.yml --limit=1 --json databaseId --jq '.[0].databaseId')"
```

Se o passo `uv publish` falhar com `invalid-publisher`, confira os quatro campos do pending
publisher — eles precisam bater exatamente (nome do repositório, workflow e environment).

## 2b. Alternativa com token (manual)

Se preferir publicar da máquina local:

```bash
export UV_PUBLISH_TOKEN=pypi-...      # token de escopo "upload" criado em pypi.org/manage/account/token/
uv build
uv publish dist/patentometria-0.3.1-py3-none-any.whl dist/patentometria-0.3.1.tar.gz
```

O token não deve ser colado em chat nem versionado. Para guardar sem variável de ambiente:

```bash
uv publish --token "$(cat ~/.config/pypi/patentometria.token)" dist/*
```

## 3. Checklist antes de cada versão

1. `uv run python manage.py test tests` → `OK` (skipped=1 esperado).
2. `uv run python scripts/check_pypi.py` → `PyPI OK`.
3. Versão nova em `pyproject.toml`, `install/install.sh`, `install/install.command`,
   `install/install.ps1`, `install/build_release.py` e `docs/INSTALACAO.md`.
4. `uv lock` e `uv build`; conferir o conteúdo do wheel:

   ```bash
   unzip -l dist/patentometria-<versao>-py3-none-any.whl | grep -E \
     'studies/(presets|templates|static)|studies/migrations|config/cli'
   ```

5. Tag `v<versao>` e push — o workflow publica.
6. Conferir a página <https://pypi.org/project/patentometria/> e testar a instalação limpa:

   ```bash
   uv tool install patentometria
   patentometria --check
   ```

## 4. Se precisar corrigir

- **Versão já publicada não pode ser reutilizada.** Corrija e suba a versão (ex.: `0.3.1`).
- **Yank** (não apaga) em *Manage → Releases → Yank*; útil quando a versão está quebrada.
- O `dist/` é ignorado pelo git (`dist/.gitignore` do próprio `uv`); os artefatos vivem no GitHub
  Releases e no PyPI, não no repositório.

## 5. Estado em 19/10/2026

- Nome `patentometria` consultado no PyPI: **livre** (HTTP 404).
- Licença **MIT** definida; `check_pypi.py` passa.
- Versão **0.3.1** (o release 0.3.0 no GitHub fica como pré-release histórico).
- Pendente: cadastrar o *pending publisher* no PyPI e criar o environment `pypi` no GitHub.
- Sem token configurado nesta máquina; a publicação deve sair pelo workflow (OIDC).
