# Instalação da Patentometria

Aplicação local. Não precisa de servidor, conta ou internet depois de instalada. Requer cerca de
300 MB livres e um navegador atualizado.

## Windows

1. Baixe `patentometria-0.3.0-windows.zip` e extraia em uma pasta (ex.: `Downloads\patentometria`).
2. Clique com o botão direito em `install.ps1` → **Executar com PowerShell**.
   Se o Windows bloquear:
   ```powershell
   powershell -ExecutionPolicy Bypass -File .\install.ps1
   ```
3. Ao final, aparecem atalhos **no Desktop e no Menu Iniciar**.
4. Abra *Patentometria*. O navegador abre em `http://127.0.0.1:8080`.

Dados: `%LOCALAPPDATA%\UFES\Patentometria`

## macOS

1. Baixe `patentometria-0.3.0-macos.zip` e extraia.
2. Duplo clique em `install.command`. Se o macOS bloquear: clique com o botão direito → **Abrir**.
   Alternativa:
   ```bash
   xattr -dr com.apple.quarantine install.command
   ```
3. O instalador cria `Patentometria.app` em `~/Applications` e um atalho no Desktop.
4. Abra pelo Launchpad, por Aplicativos ou pelo Desktop.

Dados: `~/Library/Application Support/Patentometria`

## Linux

```bash
unzip patentometria-0.3.0-linux.zip -d patentometria
cd patentometria
chmod +x install.sh
./install.sh
```

Cria entrada no menu de aplicativos e atalho no Desktop. Se o Desktop não marcar o atalho como
confiável:

```bash
gio set ~/Desktop/Patentometria.desktop metadata::trusted true
```

Dados: `~/.local/share/Patentometria`

## O que acontece na primeira execução

- A pasta de dados é criada (banco SQLite, `media/`, `logs/`, `secret.key`).
- As migrações rodam automaticamente.
- O servidor sobe em `127.0.0.1`, na primeira porta livre a partir de 8080.
- O navegador abre sozinho.

Para conferir sem abrir o navegador:

```bash
patentometria --check      # OK: banco migrado em <pasta>
patentometria where        # mostra a pasta de dados
```

## Backup e restauração

O backup do trabalho manual (decisões, ligações, dicionários, tesauro e configuração) é feito pelo
próprio aplicativo:

```bash
patentometria manage exportar_estudo 1 -o estudo.json
patentometria manage importar_estudo estudo.json --estudo 2
```

Para backup completo, feche o aplicativo e copie a pasta de dados inteira.

## Migrar dados de uma instalação antiga (manual)

A instalação **não** importa o banco da máquina de origem. Para levar um corpus existente:

1. Feche o aplicativo nas duas máquinas.
2. Copie `db.sqlite3` e a pasta `media/` da instalação antiga para a pasta de dados nova
   (`patentometria where` mostra o destino).
3. Abra o aplicativo — as migrações completam o que faltar.

## Desinstalar

```bash
uv tool uninstall patentometria
```

Windows/macOS: apague os atalhos e, se quiser, `%LOCALAPPDATA%\UFES\Patentometria` ou
`~/Library/Application Support/Patentometria`. A pasta de dados **não** é removida pelo desinstalador.

## Problemas comuns

| Sintoma | Causa | Solução |
|---|---|---|
| `patentometria` não é reconhecido | PATH atualizado só em terminal novo | feche e abra o terminal; no Windows, reinicie a sessão |
| Navegador não abre | porta ocupada ou bloqueio local | rode `patentometria serve --no-browser` e abra a URL impressa |
| "aplicativo danificado" no macOS | quarentena do download | `xattr -dr com.apple.quarantine /caminho/Patentometria.app` |
| Antivírus bloqueia o atalho | executável do `uv tool` | adicione exceção para `%USERPROFILE%\.local\bin\patentometria.exe` |
| Erro de banco bloqueado | pasta sincronizada (OneDrive/Dropbox) | rode com `--data-dir` em pasta local |
| Quero acessar de outro aparelho | padrão é só local | `patentometria serve --host 0.0.0.0` + liberar a porta no firewall |

## Para quem mantém o pacote

```bash
uv build                              # wheel + sdist em dist/
uv run python install/build_release.py  # três zips (windows/macos/linux)
uv run python scripts/smoke_wheel.py    # instala o wheel em ambiente limpo
```

Publicação no PyPI (requer token em `UV_PUBLISH_TOKEN`):

```bash
uv publish dist/patentometria-0.3.0-py3-none-any.whl dist/patentometria-0.3.0.tar.gz
```

O nome `patentometria` precisa estar livre no PyPI e o pacote deve ter licença definida antes da
primeira publicação.
