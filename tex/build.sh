#!/usr/bin/env bash
# One-shot build for the DASIP 2027 manuscript: pdflatex -> bibtex ->
# pdflatex -> pdflatex, producing tex/main.pdf.
#
# Usage:
#   ./build.sh          build main.pdf
#   ./build.sh clean    remove build artifacts (never touches .tex or main.pdf)
set -euo pipefail
cd "$(dirname "${BASH_SOURCE[0]}")"

ARTIFACTS=(main.aux main.log main.bbl main.blg main.out main.synctex.gz
           main.bcf main.run.xml main.fls main.fdb_latexmk sections/*.aux)

clean() {
  rm -f "${ARTIFACTS[@]}" 2>/dev/null || true
  echo "Cleaned build artifacts."
}

if [[ "${1:-}" == "clean" ]]; then
  clean
  exit 0
fi

pdflatex -interaction=nonstopmode -halt-on-error main.tex
bibtex main
pdflatex -interaction=nonstopmode -halt-on-error main.tex
pdflatex -interaction=nonstopmode -halt-on-error main.tex

echo "Build complete: tex/main.pdf"
