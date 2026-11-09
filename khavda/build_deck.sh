#!/bin/sh
# Build the Khavda deck: khavda/deck/khavda.pdf
#   ./khavda/build_deck.sh          slides only
#   ./khavda/build_deck.sh notes    slides with presenter notes on a second screen
set -e
DIR=$(cd "$(dirname "$0")/deck" && pwd)
cd "$DIR"
if [ "$1" = "notes" ]; then
    printf '\\PassOptionsToPackage{}{beamer}\\AtBeginDocument{}\n' > /dev/null
    sed 's/\\documentclass\[aspectratio=169,11pt,t\]{beamer}/\\documentclass[aspectratio=169,11pt,t]{beamer}\\setbeameroption{show notes on second screen=right}/' \
        khavda.tex > khavda_notes.tex
    SRC=khavda_notes.tex
else
    SRC=khavda.tex
fi
pdflatex -interaction=nonstopmode -halt-on-error "$SRC" > build.log 2>&1 || { grep -A3 '^!' build.log | head -40; exit 1; }
pdflatex -interaction=nonstopmode -halt-on-error "$SRC" > build.log 2>&1 || { grep -A3 '^!' build.log | head -40; exit 1; }
rm -f ./*.aux ./*.nav ./*.out ./*.snm ./*.toc ./*.vrb
echo "wrote $DIR/${SRC%.tex}.pdf"
