# satgif

Make satellite timelapse GIFs and MP4s from code. You give it a location,
a date range, and a satellite; it gives you an annotated, loopable timelapse
with a legend panel, a timeline indicator, and correct imagery attribution.

Built on [Google Earth Engine](https://earthengine.google.com/) — free for
research and noncommercial use.

Working on this repo with an AI coding agent? Point it at
[`AGENTS.md`](AGENTS.md) — operating notes, verification steps, and
extension conventions written for agents.

---

## Setup (once, ~5 minutes)

You need: Python 3.10+, a Google account, and a browser.

**Step 1 — install the tool's dependencies**

```bash
cd satellite-gif-tool
python3 -m venv .venv
.venv/bin/pip install -r requirements.txt
```

The repo ships a `satgif` launcher that always runs with this venv, so you
never type interpreter paths — every command below is just `./satgif ...`.
To make it a global `satgif` command (runs from any directory), symlink it
onto your PATH:

```bash
ln -s "$PWD/satgif" ~/.local/bin/satgif    # or /usr/local/bin
```

Optional but recommended — ffmpeg, which enables MP4 output next to every GIF:

```bash
brew install ffmpeg          # macOS;  apt install ffmpeg on Debian/Ubuntu
```

**Step 2 — register a Google Earth Engine project**

Earth Engine has no simple API key. Access works through a Google *Cloud
project* that is registered for Earth Engine. Registration is free:

1. Open <https://code.earthengine.google.com/register> in your browser.
2. Sign in with your Google account.
3. Choose **Unpaid usage** (research / noncommercial).
4. Create a new project (or pick an existing one) and finish.
5. Note the **project id** — e.g. `satellite-imagery-magic`. You need the id,
   not the project *number*.

**Step 3 — sign in from the terminal (once)**

```bash
.venv/bin/python -c "import ee; ee.Authenticate()"
```

A browser window opens; approve access with the same Google account. The
token is cached on disk — you will not be asked again on this machine.

**Step 4 — tell satgif your project id**

```bash
echo YOUR-PROJECT-ID > ~/.satgif
```

(Alternatives: `export SATGIF_PROJECT=...`, or pass `--project ...` per run.)

**Step 5 — verify everything**

```bash
./satgif doctor
```

Expected output:

```
[ok] earthengine-api installed
[ok] credentials found
[ok] Earth Engine works with project 'YOUR-PROJECT-ID'
[ok] ffmpeg found (MP4 output enabled)
all good
```

Any `[FAIL]` line prints the exact command that fixes it. Setup is done.

---

## Your first GIF (worked example)

The Maruti Suzuki plant at Hansalpur, Gujarat — farmland in 2016, major
industrial complex by 2023:

```bash
./satgif generate \
    --lat 23.4945 --lon 72.0072 \
    --radius-km 3x1.2 \
    --start 2016 --end 2023 \
    --season 01-04 \
    --title "HANSALPUR, GUJARAT" \
    --out hansalpur.gif
```

What you'll see — one line per frame as each year's cloud-free composite is
built, then the outputs:

```
  2016: 12 scenes
  2017: 42 scenes
  ...
  2023: 152 scenes
wrote hansalpur.gif (8 frames)
wrote hansalpur.mp4
```

Open `hansalpur.gif`. The legend sits in the lower-right: title, the year
(changing per frame), a timeline dot marking progress, scene size,
coordinates, and the imagery credit.

The same call from Python or a notebook — every flag is a keyword argument
with the same name (dashes become underscores):

```python
from satgif import make_timelapse

make_timelapse(lat=23.4945, lon=72.0072, radius_km='3x1.2',
               start='2016', end='2023', season='01-04',
               title='HANSALPUR, GUJARAT', out='hansalpur.gif')
```

---

## Choosing a satellite

```bash
./satgif sensors            # summary table
./satgif sensors landsat    # one sensor in detail
```

| name | resolution | coverage | best for |
|---|---|---|---|
| `sentinel2` *(default)* | 10 m | mid-2015 → now | sharpest imagery of anything after 2015 |
| `landsat` | 30 m | 1984 → now | history — 40-year timelapses (Landsat 5/7/8/9 merged) |
| `viirs-ntl` | ~500 m | 2012 → now | nighttime lights as an economic-activity proxy |

Rules of thumb:

- **One sensor per GIF.** Mixing resolutions mid-series looks like a glitch.
- Date range starts before 2015 → use `landsat`.
- `viirs-ntl` is yearly-only; `--season` and `--max-cloud` don't apply to it.

---

## Flag reference

Full help: `./satgif generate --help`

| flag | default | meaning |
|---|---|---|
| `--lat`, `--lon` | *required* | scene center, decimal degrees (negative = S / W) |
| `--radius-km` | `2` | scene half-width in km. One number = square scene; `WxH` = rectangle: `3x1.2` is 3 km east-west by 1.2 km north-south (a 6 × 2.4 km scene) |
| `--start`, `--end` | `2016`, last full year | `YYYY` or `YYYY-MM` |
| `--interval` | `1y` | one frame per `1y`, `6m`, `3m`, or `1m` |
| `--season` | off | `MM-MM`, e.g. `01-04`: build every frame only from those months of its year. **Use this whenever the GIF flickers green/brown** — that is seasons changing, not the ground |
| `--sat` | `sentinel2` | satellite — see table above |
| `--width` | `1200` | frame width in pixels; height follows the scene's shape |
| `--fps` | `2` | playback speed, frames per second |
| `--hold` | `2` | extra seconds the final frame stays on screen |
| `--max-cloud` | `20` | max per-scene cloud % allowed into a composite. Frames empty → raise it. Frames hazy → lower it |
| `--title` | the coordinates | legend heading |
| `--scale-bar` | off | draw a distance scale bar (0 / mid / end labels, round 1-2-5 length ≈ ⅕ of the scene width) in the lower-left corner |
| `--out` | `timelapse.gif` | output GIF path; the MP4 is written beside it |
| `--no-mp4` | off | skip the MP4 even when ffmpeg is installed |
| `--project` | `~/.satgif` / env | GEE project id override |
| `--cache-dir` | `satgif_cache` | where downloaded frames are cached |

**Iterating is cheap.** Downloaded frames are cached by parameter hash, so
rerunning with different `--fps`, `--hold`, `--title`, or `--scale-bar` is instant. Changing
location, dates, sensor, season, or width re-fetches, because those change
the imagery itself.

---

## How a frame is made (what the tool does for you)

A frame is not a single photo. For each interval, satgif collects every
scene crossing your bounding box, drops scenes cloudier than `--max-cloud`,
optionally keeps only `--season` months, and takes the pixelwise **median**:
a cloud-free composite. The brightness stretch is fixed per sensor across
all frames, so the series never flickers from exposure differences. A frame
with zero usable scenes is skipped with a warning that names the fix.

---

## Recipes

```bash
# 40 years of urban growth (Landsat, dry-season frames, brisk playback)
./satgif generate --lat 28.61 --lon 77.21 --radius-km 15 \
    --start 1990 --end 2023 --sat landsat --season 01-03 --fps 4 \
    --title "DELHI NCR" --out delhi.gif

# Nighttime lights of an industrial corridor
./satgif generate --lat 23.4945 --lon 72.0072 --radius-km 10 \
    --start 2014 --end 2023 --sat viirs-ntl \
    --title "HANSALPUR NTL" --out hansalpur_ntl.gif

# Quarterly crop cycles on a farm belt
./satgif generate --lat 30.9 --lon 75.8 --radius-km 5 \
    --start 2022 --end 2024 --interval 3m --fps 3 --out punjab_crops.gif
```

---

## Troubleshooting

| symptom | cause → fix |
|---|---|
| `Earth Engine init failed (... not registered ...)` | the project isn't registered for Earth Engine → register it at <https://code.earthengine.google.com/register> |
| `Caller does not have required permission to use project X` | the project id isn't yours (or a typo) → check the id on <https://console.cloud.google.com> and update `~/.satgif` |
| `no credentials` in `doctor` | you haven't signed in on this machine → `.venv/bin/python -c "import ee; ee.Authenticate()"` |
| `WARNING — no scenes ... frame skipped` | nothing cloud-free in that window → raise `--max-cloud`, widen `--season`, or use `--interval 1y` |
| GIF flickers green/brown between frames | frames sample different seasons → add `--season`, e.g. `01-04` |
| `ffmpeg not found — skipped MP4` | GIF still works → `brew install ffmpeg` to get MP4s |
| imagery looks blurry | that's the sensor's real resolution (10 m Sentinel / 30 m Landsat). Sub-meter imagery (Google Earth's Maxar layer) is not programmatically available — this is the physics, not a bug |

Still stuck? `./satgif doctor` diagnoses the setup chain
step by step.

---

## Attribution

The legend automatically stamps the legally required credit: *"Contains
modified Copernicus Sentinel data"* for `sentinel2`, *"Imagery: USGS/NASA
Landsat"* for `landsat`, *"Nighttime lights: NOAA VIIRS DNB"* for
`viirs-ntl`. Keep it visible when you publish the output.
