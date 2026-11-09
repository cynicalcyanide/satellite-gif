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
#                                   if that file exists (it ships only as
#                                   parcels.geojson.template: the placeholder
#                                   rectangle is NOT a surveyed boundary, so
#                                   copy it to parcels.geojson and replace the
#                                   coordinates with traced ones before it is
#                                   drawn)
#   khavda_NN.png                   one annotated PNG per frame, for the deck
#   khavda_frames.csv               index, label, dates per frame
#   khavda_built_area.csv           measured built-up hectares per quarter
#   frames_meta.tex                 \satLast and the six grid frames
#
# The second run re-renders from the cache, so the two GIFs cost one fetch.
#
# Series starts at Q1 2022, not Q1 2020: on this scene the first eight quarters
# are bare salt with no visible construction, so they read as a dead opening.
# The 2020-21 frames are still in the cache -- set --start 2020-01 to get them
# back without refetching.
#
# Then: .venv/bin/python khavda/make_figures.py && ./khavda/build_deck.sh
#
# Scene: 54 x 30.4 km (16:9) centred on 24.100 N, 69.465 E. The analysis note's
# centre (24.117 N, 69.350 E) with a 48 x 27 km scene was measured against the
# imagery and clipped the park: the eastern arrays near 69.60-69.67 E ran off
# the right edge while ~15 km of empty salt flat sat unused in the west. The
# built arrays span about 69.26-69.67 E by 23.99-24.21 N (42 x 24 km), so this
# scene holds them with ~6 km of margin east-west and ~3 km north-south.
# CHECK FRAME 00: if the park is cut off, move --lat/--lon or widen
# --radius-km here (one refetch) and rerun; keep the 16:9 ratio.
set -e
ROOT=$(cd "$(dirname "$0")/.." && pwd)
OUT="$ROOT/khavda/deck/frames"
mkdir -p "$OUT"

# Luminance cut for --built-area, measured against this scene rather than left
# at the tool's default of 110. On these frames the arrays read about 165 in raw
# luminance, bare ground about 228 and white salt about 195, so 110 sat below
# the panels entirely and traced only dark rock (2,768 ha of specks). Sweeping
# 140/150/155/160/165/175/190 over the cached frames: 140 leaves whole array
# blocks untraced, 175 and above floods the salt flat and the rocky ground, and
# 160 covers the arrays with the least bleed. It is a threshold, not a
# classification: some wet salt flat in the west and dark rock in the north-east
# are still caught, so treat the hectares as an upper bound. Override per run
# with: BUILT_THRESHOLD=165 ./khavda/make_frames.sh
BUILT_THRESHOLD="${BUILT_THRESHOLD:-160}"

# Drawn only if real parcel boundaries have been traced into
# khavda/parcels.geojson. Absent (the default), the annotated GIF carries only
# the measured built-up polygons, nothing hand-drawn.
POLY=""
if [ -s "$ROOT/khavda/parcels.geojson" ]; then
    POLY="--polygons $ROOT/khavda/parcels.geojson"
fi

COMMON="--lat 24.100 --lon 69.465 --radius-km 27x15.1875 \
    --start 2022-01 --end 2026-10 --interval 3m \
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
    --built-area --built-threshold "$BUILT_THRESHOLD" $POLY \
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
