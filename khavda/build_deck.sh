#!/bin/sh
# Build the Khavda deck: khavda/deck2/khavda.pdf
#   ./khavda/build_deck.sh
set -e
DIR=$(cd "$(dirname "$0")/deck2" && pwd)
cd "$DIR"
pdflatex -interaction=nonstopmode -halt-on-error khavda.tex > build.log 2>&1 || { grep -A3 '^!' build.log | head -40; exit 1; }
pdflatex -interaction=nonstopmode -halt-on-error khavda.tex > build.log 2>&1 || { grep -A3 '^!' build.log | head -40; exit 1; }
rm -f ./*.aux ./*.nav ./*.out ./*.snm ./*.toc ./*.vrb
echo "wrote $DIR/khavda.pdf"
