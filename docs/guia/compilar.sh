#!/usr/bin/env bash
# Compila o guia (duas passadas para sumário e referências).
set -euo pipefail
cd "$(dirname "$0")"
pdflatex -interaction=nonstopmode -halt-on-error guia.tex > /tmp/guia-build.log 2>&1 || { tail -30 /tmp/guia-build.log; exit 1; }
pdflatex -interaction=nonstopmode -halt-on-error guia.tex > /tmp/guia-build.log 2>&1 || { tail -30 /tmp/guia-build.log; exit 1; }
echo "PDF: $(pwd)/guia.pdf ($(pdfinfo guia.pdf | awk '/Pages/{print $2}') páginas)"
