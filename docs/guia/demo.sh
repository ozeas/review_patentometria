#!/usr/bin/env bash
# Cria um ambiente de demonstração isolado para as capturas do guia.
# Uso: docs/guia/demo.sh [pasta]
set -euo pipefail

RAIZ="$(cd "$(dirname "$0")/../.." && pwd)"
DESTINO="${1:-/tmp/patentometria-guia}"

rm -rf "$DESTINO"
mkdir -p "$DESTINO/dados"

cp "$RAIZ/tests/fixtures/lens_sample.csv"      "$DESTINO/dados/lens_nucleo.csv"
cp "$RAIZ/tests/fixtures/espacenet_sample.csv" "$DESTINO/dados/espacenet_nucleo.csv"
cp "$RAIZ/tests/fixtures/google_sample.csv"    "$DESTINO/dados/google_nucleo.csv"
cp "$RAIZ/tests/fixtures/derwent_sample.txt"   "$DESTINO/dados/darwent_nucleo.txt"

export PATENTOMETRIA_DATA_DIR="$DESTINO"
cd "$RAIZ"

.venv/bin/python manage.py migrate --verbosity 0
.venv/bin/python manage.py novo_estudo --nome "Estudo de exemplo" \
    --preset docs/guia/demo/preset.json \
    --descricao "Demonstração usada nas capturas do guia."
.venv/bin/python manage.py importar_rodada --estudo "Estudo de exemplo" \
    --rodada "15/10/2026" --data 2026-10-15 --pasta "$DESTINO/dados" \
    --execucao "15/10/2026 16h"
.venv/bin/python manage.py executar_rodada 1

echo
echo "Ambiente de demonstração pronto em $DESTINO"
echo "Para abrir: PATENTOMETRIA_DATA_DIR=$DESTINO .venv/bin/python manage.py runserver 127.0.0.1:8090"
