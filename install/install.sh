#!/usr/bin/env bash
# Instalador da Patentometria para Linux (sem sudo).
set -euo pipefail

VER="0.3.0"
AQUI="$(cd "$(dirname "$0")" && pwd)"
WHEEL="$AQUI/patentometria-$VER-py3-none-any.whl"

if [ ! -f "$WHEEL" ]; then
  echo "ERRO: wheel não encontrado em $WHEEL" >&2
  exit 1
fi

if ! command -v uv >/dev/null 2>&1; then
  echo "Instalando uv (gerenciador de Python)..."
  curl -LsSf https://astral.sh/uv/install.sh | sh
  export PATH="$HOME/.local/bin:$PATH"
fi

echo "Instalando Patentometria $VER..."
uv tool install --force "$WHEEL"

BIN="$HOME/.local/bin/patentometria"
if [ ! -x "$BIN" ]; then
  BIN="$(command -v patentometria || true)"
fi
if [ -z "$BIN" ] || [ ! -x "$BIN" ]; then
  echo "ERRO: o comando patentometria não foi encontrado após a instalação." >&2
  echo "Abra um novo terminal e rode: uv tool install --force \"$WHEEL\"" >&2
  exit 1
fi

MENU="$HOME/.local/share/applications/patentometria.desktop"
mkdir -p "$(dirname "$MENU")"
cat > "$MENU" <<EOF
[Desktop Entry]
Type=Application
Name=Patentometria
Comment=Análise patentométrica (PGEN1075/UFES)
Exec=$BIN
Icon=applications-science
Terminal=false
Categories=Education;Science;
EOF

ATALHO="$HOME/Desktop/Patentometria.desktop"
if [ -d "$HOME/Desktop" ]; then
  cp "$MENU" "$ATALHO"
  chmod +x "$ATALHO"
  gio set "$ATALHO" metadata::trusted true 2>/dev/null || true
fi

"$BIN" --check || { echo "ERRO: verificação falhou." >&2; exit 1; }
echo
echo "Pronto. Abra 'Patentometria' no menu de aplicativos ou no Desktop."
echo "Pasta de dados: $("$BIN" where)"
