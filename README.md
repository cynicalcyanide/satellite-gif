# satgif

Satellite timelapse GIFs and MP4s from code. Give it a lat/long, a radius,
a date range, and a satellite — get an annotated, loopable timelapse with a
legend panel, timeline indicator, and correct imagery attribution.

Built on [Google Earth Engine](https://earthengine.google.com/) (free for
noncommercial use).

## Install

```bash
python3 -m venv .venv
.venv/bin/pip install earthengine-api pillow requests
brew install ffmpeg          # optional — enables MP4 output alongside the GIF
```

## One-time Earth Engine setup

Earth Engine has no plain API key. You need a Google account and a Cloud
project registered for Earth Engine (free, takes ~2 minutes):

1. Register a project at <https://code.earthengine.google.com/register>
   (choose *Unpaid usage* for research/noncommercial work).
2. Authenticate once — this opens a browser sign-in and caches a token:
   ```bash
   .venv/bin/python -c "import ee; ee.Authenticate()"
   ```
3. Tell satgif your project id, any of three ways:
   - `--project my-project-id` on the command line
   - `export SATGIF_PROJECT=my-project-id`
   - `echo my-project-id > ~/.satgif`

Check everything in one shot:

```bash
.venv/bin/python satgif.py doctor
```

`doctor` verifies the install, the credentials, the project, and ffmpeg, and
prints the exact fix for whichever piece is missing.

## Quick start

```bash
.venv/bin/python satgif.py generate \
    --lat 23.4945 --lon 72.0072 --radius-km 2 \
    --start 2015 --end 2023 \
    --title "HANSALPUR, GUJARAT" \
    --out hansalpur.gif
```

Or from Python / a notebook:

```python
from satgif import make_timelapse

make_timelapse(lat=23.4945, lon=72.0072, radius_km=2,
               start='2015', end='2023', sat='sentinel2',
               title='HANSALPUR, GUJARAT', out='hansalpur.gif')
```

Every CLI flag is a keyword argument with the same name (dashes become
underscores) and the same default.

## Satellites

```bash
.venv/bin/python satgif.py sensors            # the table below
.venv/bin/python satgif.py sensors sentinel2  # one sensor in detail
```

| name | resolution | coverage | type | notes |
|---|---|---|---|---|
| `sentinel2` | 10 m | 2015-07 → now | optical | sharpest free imagery; the default |
| `landsat` | 30 m | 1984 → now | optical | Landsat 5/7/8/9 merged; 40 years of history |
| `viirs-ntl` | ~500 m | 2012 → now | night lights | annual composites, log-scaled, inferno palette |

Pick one sensor per GIF — mixing resolutions mid-series looks like a glitch.
If your date range starts before 2015, use `landsat`.

## Flag manual

| flag | default | meaning |
|---|---|---|
| `--lat`, `--lon` | *required* | scene center, decimal degrees |
| `--radius-km` | `2` | half-width of the square scene |
| `--start`, `--end` | `2016`, last full year | `YYYY` or `YYYY-MM` |
| `--interval` | `1y` | one frame per `1y` / `6m` / `3m` / `1m` |
| `--season` | off | `MM-MM`, e.g. `01-04`: build every frame from the same months of its year. Use this whenever frames flicker green/brown — that's seasons, not change |
| `--sat` | `sentinel2` | see `sensors` |
| `--width` | `1200` | frame width px (height follows the bounding box) |
| `--fps` | `2` | playback speed |
| `--hold` | `2` | extra seconds the final frame stays on screen |
| `--max-cloud` | `20` | max per-scene cloud % admitted to composites. Raise it if frames come back empty; lower it if frames look hazy |
| `--title` | the coordinates | legend heading |
| `--out` | `timelapse.gif` | GIF path; the MP4 is written beside it |
| `--no-mp4` | off | skip MP4 even when ffmpeg is present |
| `--project` | env/`~/.satgif` | GEE Cloud project id |
| `--cache-dir` | `satgif_cache` | downloaded frames are cached by parameter hash — restyling or retiming reruns cost zero refetches |

## How frames are built

A frame is not a single photo. For each interval, satgif takes every scene
over your bounding box, drops scenes cloudier than `--max-cloud`, optionally
restricts to `--season` months, and takes the pixelwise **median** — a
cloud-free composite. Visualization stretch is fixed per sensor across all
frames, so brightness never flickers frame to frame. Frames with zero
usable scenes are skipped with a warning naming the fix.

## Recipes

```bash
# 40-year urban growth (Landsat, dry-season frames only)
satgif.py generate --lat 28.61 --lon 77.21 --radius-km 15 \
    --start 1990 --end 2023 --sat landsat --season 01-03 --fps 4

# Nighttime lights of an industrial corridor
satgif.py generate --lat 23.4945 --lon 72.0072 --radius-km 10 \
    --start 2014 --end 2023 --sat viirs-ntl

# Quarterly crop cycles on one farm belt
satgif.py generate --lat 30.9 --lon 75.8 --radius-km 5 \
    --start 2022 --end 2024 --interval 3m --fps 3
```

## Attribution

The legend stamps the correct credit automatically: Copernicus Sentinel data
for `sentinel2`, USGS/NASA for `landsat`, NOAA for `viirs-ntl`. Keep it
visible when you publish the output.
