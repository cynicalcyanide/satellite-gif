# Khavda deck: plan

Prepared 9 November 2026. The package (`khavda_package.zip`) was read in full:
the briefing note, the 17-slide skeleton, the five built charts, the eight CSVs,
the CMIE extract and its working notes, and the 57-citation analysis note.
This plan maps all of it onto one Beamer deck in the XKDR colour theme, with
the satellite work done by `satgif`.

## 1. Satellite imagery (the part only `satgif` can do)

**One GIF, quarterly frames, one second each.**

| Parameter | Value | Why |
| --- | --- | --- |
| Centre | 24.117° N, 69.350° E | From the analysis note (section "What the satellite imagery can show") |
| Scene | 48 km east-west × 27 km north-south (`--radius-km 24x13.5`) | Covers the 726 km² park with margin; 16:9, so it fills a slide with no letterbox. **Check the first frame and shift the centre if the park is cut off.** |
| Sensor | Sentinel-2, 10 m | Panels and turbine shadows read clearly against white salt |
| Interval | `3m` (quarterly) | 2020 Q1 to 2026 Q4: 28 frames |
| Speed | `--fps 1`, `--hold 3` | One second per frame, 28 s loop, last frame held |
| Season | none | Quarterly frames cannot be season-filtered; monsoon quarters (Q3) show which plots flood, which the note says is useful |
| Cloud | `--max-cloud 30` | Looser than default; the Rann is dry most of the year so composites stay clean |
| Width | 1600 px | 30 m per pixel; sharp enough for a projector, small enough to animate |
| Scale bar | `--scale-bar` | 10 km bar, lower-left |
| Rendering | `--contrast 1.2 --sharpen 0.6` | Styling only; re-renders from cache |

**Two things added to `satgif` for this deck:**

1. **Built-up area per frame** (`--built-area`). Panels are dark, salt is white.
   For every frame the tool classifies dark pixels, removes anything that was
   already dark in the first frame (permanent water, the BSF road) and anything
   not dark in the last frame (floods recede, panels stay), traces the outline
   of what is left in orange, and writes the hectares into the legend. A CSV
   of hectares per quarter is written beside the GIF: that is the independent
   build-out curve the note asks for, convertible to MW at ~2 ha/MW.
2. **Hand-drawn polygons** (`--polygons file.geojson`). Any polygon you draw
   (in geojson.io or QGIS) is outlined on every frame, labelled with its name
   and its area in hectares or km², computed from the coordinates. This is how
   the developer parcels (Adani, NTPC, Sarjan, GSECL, GIPCL, ex-SECI) go on
   slide 5 once their boundaries are traced. `khavda/parcels.geojson` is a
   template with the park outline to replace.

Both are overlays: they do not touch the cache, so you can iterate on them in
seconds once the frames are downloaded.

**What you have to run.** This session has no Earth Engine credentials and
cannot fetch imagery. Everything is wired so that one command does it:

```bash
./khavda/make_frames.sh
```

It writes two GIFs (with MP4s beside them) into `khavda/deck/frames/`:
`khavda_plain.gif`, unannotated (imagery, legend, scale bar only), and
`khavda.gif`, annotated (built-up outline with hectares, plus any polygons in
`parcels.geojson`). It also writes one PNG per annotated frame and
`khavda_built_area.csv`; the deck picks them up on the next build. The second
GIF renders from the cache, so both cost one fetch.

## 2. The deck

Beamer, 16:9, `beamercolorthemeXKDR` (your `.sty`, renamed so
`\usecolortheme{XKDR}` finds it), `{X}KDR` logos on the title slide and the
footer. Source: `khavda/deck/khavda.tex`. Build: `./khavda/build_deck.sh`
(runs `pdflatex` twice).

The GIF cannot play inside a PDF. The deck uses the `animate` package on the
frame PNGs (plays in Acrobat and most desktop viewers at 1 fps, autoplay,
loop) and a 2 × 3 grid of key quarters as the fallback on the next slide. The
GIF and MP4 sit beside the PDF for presenting from a browser or Keynote.

Slide by slide (numbers follow the skeleton):

| # | Slide | Visual | Status |
| --- | --- | --- | --- |
| 1 | Title | Latest satellite frame, full bleed | satellite |
| 2 | Six years in 28 seconds | The animation; three numbers | satellite |
| 2b | The same, six stills | 2 × 3 grid of key quarters | satellite |
| 3 | Why here | Four facts; first frame (bare salt) | satellite |
| 4 | The lease | Four-number callout | **built**, native LaTeX |
| 5 | Who holds the land | Land by developer, 2020 vs 2026 bars; annotated frame | **built** chart; satellite with parcels once traced |
| 6 | What the plant is made of | Anatomy chain | rebuilt in LaTeX, orange accent |
| 7 | Building on salt | Five hazards and their fixes | text; photo strip is a placeholder until photos arrive |
| 8 | The timeline | Milestone chart, rebuilt in theme colours; frame thumbnails | **built** chart; satellite |
| 9 | CMIE capex | Stacked bar by developer, rebuilt | **built** |
| 10 | How Adani builds | Subsidiaries diagram | rebuilt in LaTeX |
| 11 | Everyone else | Tenant table | **built** |
| 12 | Getting the power out | Evacuation chain, rebuilt; corridor schematic | **built** |
| 13 | 13 May 2026 | Seconds timeline with the voltage values | **built** |
| 14 | Batteries | GWh by date bars | **built**; battery-yard circle on the frame needs your eye |
| 15 | Economics | Cost stack vs tariff | **built** |
| 16 | Adani in four points | Text | **built** |
| 17 | The plant in one page | Three columns; annotated frame | **built**; satellite |
| 18 | Build-out curve | Built hectares per quarter vs milestones | generated from the built-area CSV after frames exist |
| 19 | Sources | | **built** |

Presenter notes from the skeleton go in `\note{}` on each frame; build with
`notes=show` in the class options to get them beside the slides.

Charts follow the package style note (short sentences, one finding per chart
stated in the title, values on the marks, source line under each) with the
palette swapped to the theme: grey for everything, `SpOrange` (#F27A69) for
the thing the title is about.

## 3. Order of work

1. `satgif`: `--built-area`, `--polygons`, `--frames-dir`, and render in a
   metric projection so the scene has its true shape and the scale bar is
   right in both axes. Verified on synthetic frames, since no imagery can be
   fetched here.
2. `khavda/make_frames.sh`: the one command above.
3. Charts: `khavda/make_figures.py` regenerates every chart from the CSVs.
4. `khavda.tex`: all 19 slides; compiles with or without the frames present.
5. After you run `make_frames.sh`: check frame 1 (is the park centred?), the
   latest frame (is the built outline sensible, or does the threshold need
   `--built-threshold` adjusted?), rebuild the deck.

## 4. Things to confirm on your side

- The scene centre and size. If the park spills off an edge, change
  `--lat/--lon/--radius-km` in `make_frames.sh` (one refetch).
- Parcel boundaries. There is no public GeoJSON of the six parcels; the
  template holds a placeholder park outline. Trace the parcels once in
  geojson.io and drop the file in; the labels and hectares follow.
- Frame for slide 14. Battery yards are "dense rectangles beside the
  switchyards"; pick the quarter and circle them with a polygon in the same
  GeoJSON (a second file, `--polygons batteries.geojson`, for that one still).
- Ground photographs for slide 7 (none in the package).
