#!/bin/sh
# Compile one diagram standalone and print its size in cm.
#   ./test_tikz.sh d02_two_clocks.tex
set -e
DIR=$(cd "$(dirname "$0")" && pwd)
F="$1"; B=$(basename "$F" .tex)
T=$(mktemp -d)
cat > "$T/$B.tex" <<HEAD
\documentclass[border=1pt]{standalone}
\usepackage[T1]{fontenc}\usepackage[scaled=0.95]{helvet}\renewcommand{\familydefault}{\sfdefault}
\input{$DIR/../preamble_common.tex}
\begin{document}\footnotesize
\input{$DIR/$B.tex}
\end{document}
HEAD
(cd "$T" && pdflatex -interaction=nonstopmode -halt-on-error "$B.tex" > build.log 2>&1) || { grep -A4 '^!' "$T/build.log" | head -20; exit 1; }
pdfinfo "$T/$B.pdf" | grep "Page size" | awk -v b="$B" '{printf "%s: %.1f x %.1f cm\n", b, $3/28.35, $5/28.35}'
pdftoppm -r 90 -png -singlefile "$T/$B.pdf" "$DIR/preview_$B" >/dev/null 2>&1 && echo "preview: $DIR/preview_$B.png"
