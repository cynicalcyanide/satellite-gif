#!/bin/sh
# Fetch the Khavda quarterly satellite series and render everything the deck
# needs. Needs Earth Engine credentials and a project id: `./satgif doctor`.
#
#   ./khavda/make_frames.sh                 fetch (or reuse cache) and render
#   ./khavda/make_frames.sh --no-mp4 ...    extra flags are passed to satgif
#
# Outputs, all in khavda/deck/frames/:
#   khavda_plain.gif / .mp4         unannotated: imagery, legend, scale bar
#   khavda.gif / .mp4               annotated: built-up outline + hectares,
#                                   and the polygons in khavda/parcels.geojson
#   khavda_NN.png                   one annotated PNG per frame, for the deck
#   khavda_frames.csv               index, label, dates per frame
#   khavda_built_area.csv           measured built-up hectares per quarter
#   frames_meta.tex                 \satLast and the six grid frames
#
# The second run re-renders from the cache, so the two GIFs cost one fetch.
#
# Then: .venv/bin/python khavda/make_figures.py && ./khavda/build_deck.sh
#
# Scene: 48 x 27 km (16:9) centred on 24.117 N, 69.350 E, the centre the
# analysis note gives. CHECK FRAME 00: if the park is cut off, move --lat/--lon
# or widen --radius-km here (one refetch) and rerun.
set -e
ROOT=$(cd "$(dirname "$0")/.." && pwd)
OUT="$ROOT/khavda/deck/frames"
mkdir -p "$OUT"

POLY=""
if [ -s "$ROOT/khavda/parcels.geojson" ]; then
    POLY="--polygons $ROOT/khavda/parcels.geojson"
fi

COMMON="--lat 24.117 --lon 69.350 --radius-km 24x13.5 \
    --start 2020-01 --end 2026-10 --interval 3m \
    --sat sentinel2 --max-cloud 30 --width 1600 \
    --fps 1 --hold 3 \
    --scale-bar --contrast 1.2 --sharpen 0.6 \
    --cache-dir $ROOT/satgif_cache"

echo "== 1/2 unannotated GIF (fetches frames; later runs use the cache)"
"$ROOT/satgif" generate $COMMON \
    --title "KHAVDA RENEWABLE ENERGY PARK, KUTCH" \
    --out "$OUT/khavda_plain.gif" "$@"

echo "== 2/2 annotated GIF: built-up area outline and hectares, parcels"
"$ROOT/satgif" generate $COMMON \
    --title "KHAVDA RENEWABLE ENERGY PARK, KUTCH" \
    --built-area $POLY \
    --frames-dir "$OUT" \
    --out "$OUT/khavda.gif" "$@"

# frames_meta.tex: last frame index and the six stills for the grid slide,
# picked by label so skipped frames do not shift them.
"$ROOT/.venv/bin/python" - "$OUT" <<'EOF'
import csv, sys, os
out = sys.argv[1]
rows = list(csv.DictReader(open(os.path.join(out, 'khavda_frames.csv'))))
by = {r['label']: r['file'] for r in rows}
def pick(*labels):
    for l in labels:
        if l in by:
            return 'frames/' + by[l]
    return 'frames/' + rows[-1]['file']
meta = {
    'satLast': f"{len(rows) - 1:02d}",
    'satFirstFile': 'frames/' + rows[0]['file'],
    'satLastFile': 'frames/' + rows[-1]['file'],
    'satGridA': pick('Q1 2020', 'Q2 2020'),
    'satGridB': pick('Q4 2021', 'Q1 2022'),
    'satGridC': pick('Q1 2024', 'Q2 2024'),
    'satGridD': pick('Q3 2025', 'Q4 2025'),
    'satGridE': pick('Q1 2026', 'Q2 2026'),
    'satGridF': rows[-1]['label'] and 'frames/' + rows[-1]['file'],
}
with open(os.path.join(out, 'frames_meta.tex'), 'w') as fh:
    fh.write('% written by khavda/make_frames.sh\n')
    for k, v in meta.items():
        fh.write(f'\\renewcommand{{\\{k}}}{{{v}}}\n')
print('wrote', os.path.join(out, 'frames_meta.tex'), meta)
EOF

echo
echo "Next: .venv/bin/python khavda/make_figures.py && ./khavda/build_deck.sh"
echo "Check $OUT/khavda_00.png (is the park centred?) and the last frame"
echo "(is the orange built-up outline sensible? tune --built-threshold)."
