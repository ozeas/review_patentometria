#!/bin/bash
# Instalador da Patentometria para macOS (duplo clique).
set -euo pipefail
cd "$(dirname "$0")"

VER="0.3.0"
WHEEL="$PWD/patentometria-$VER-py3-none-any.whl"
if [ ! -f "$WHEEL" ]; then
  echo "ERRO: wheel não encontrado em $WHEEL"
  read -r -p "Pressione Enter para fechar..." _
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

APP="$HOME/Applications/Patentometria.app"
mkdir -p "$APP/Contents/MacOS"
cat > "$APP/Contents/Info.plist" <<'PLIST'
<?xml version="1.0" encoding="UTF-8"?>
<!DOCTYPE plist PUBLIC "-//Apple//DTD PLIST 1.0//EN" "http://www.apple.com/DTDs/PropertyList-1.0.dtd">
<plist version="1.0">
<dict>
  <key>CFBundleName</key><string>Patentometria</string>
  <key>CFBundleDisplayName</key><string>Patentometria</string>
  <key>CFBundleIdentifier</key><string>br.ufes.ppgen.patentometria</string>
  <key>CFBundleVersion</key><string>0.3.0</string>
  <key>CFBundleShortVersionString</key><string>0.3.0</string>
  <key>CFBundlePackageType</key><string>APPL</string>
  <key>CFBundleExecutable</key><string>Patentometria</string>
  <key>LSMinimumSystemVersion</key><string>11.0</string>
</dict>
</plist>
PLIST

cat > "$APP/Contents/MacOS/Patentometria" <<LAUNCHER
#!/bin/bash
exec "$BIN" >>"\$HOME/Library/Logs/Patentometria.log" 2>&1
LAUNCHER
chmod +x "$APP/Contents/MacOS/Patentometria"

if [ -d "$HOME/Desktop" ]; then
  ln -sfn "$APP" "$HOME/Desktop/Patentometria.app"
fi

"$BIN" --check || { echo "ERRO: verificação falhou."; read -r -p "Enter..." _; exit 1; }
echo
echo "Pronto. Abra 'Patentometria' no Launchpad, em Aplicativos ou no Desktop."
echo "Pasta de dados: $("$BIN" where)"
read -r -p "Pressione Enter para fechar..." _
