# AGENTS.md — operating satgif as an AI agent

Instructions for AI coding agents (Claude Code, Cursor, Copilot, etc.)
working in this repository or using the tool on a user's behalf. The
human-oriented manual is `README.md`; read that first for concepts. This
file covers what an agent must know that a human guide glosses over.

## What this tool is

`satgif.py` is a single-module tool that renders satellite timelapse GIFs
and MP4s from Google Earth Engine (GEE). One module, no package install.
It has two equivalent interfaces:

- **CLI**: `./satgif generate|sensors|doctor [flags]` — `satgif` is a
  POSIX-sh launcher that resolves its own repo directory (through
  symlinks too) and execs `.venv/bin/python satgif.py`. Prefer it over
  spelling out interpreter paths; it may also be on the user's PATH as
  plain `satgif`.
- **Python**: `from satgif import make_timelapse` — every CLI flag is a
  keyword argument of the same name (dashes → underscores, same defaults).

Repo layout: `satgif.py` (everything), `satgif` (launcher), `README.md`
(manual), `requirements.txt` (`earthengine-api`, `pillow`, `requests`),
`satgif_cache/` (gitignored frame cache), outputs `*.gif`/`*.mp4`
(gitignored).

## Setup, as an agent

1. **Interpreter**: the `satgif` launcher expects the repo's own venv at
   `.venv/`. Detect it first (`.venv/bin/python -c "import ee, PIL,
   requests"`); create it only if missing:
   `python3 -m venv .venv && .venv/bin/pip install -r requirements.txt`
   (the launcher prints exactly this fix if the venv is absent).
2. **Diagnose before running**: always start with
   `./satgif doctor`. It checks, in dependency order: the
   `earthengine-api` import → cached credentials → resolvable project id →
   a live EE round-trip → ffmpeg. Each failing line prints its fix.
3. **The step you cannot do yourself**: `ee.Authenticate()` opens a browser
   OAuth flow. **Never attempt to run it headlessly, script it, or handle
   the user's Google credentials.** If `doctor` reports missing
   credentials, stop and ask the human to run:
   `python -c "import ee; ee.Authenticate()"`
   then re-run `doctor`. Credentials cache at
   `~/.config/earthengine/credentials` and persist across sessions.
4. **Project id resolution order**: `--project` flag / `project=` kwarg →
   `SATGIF_PROJECT` env var → `~/.satgif` file (first line). If none
   resolves, ask the human for their GEE project id rather than guessing;
   if they don't have one, point them to
   https://code.earthengine.google.com/register (free, "Unpaid usage").
   A "Caller does not have required permission" error means the id exists
   but belongs to someone else — ask for the right id; do not retry.

## Running jobs

Canonical invocation (the repo's worked example):

```bash
./satgif generate \
    --lat 23.4945 --lon 72.0072 --radius-km 3x1.2 \
    --start 2016 --end 2023 --season 01-04 \
    --title "HANSALPUR, GUJARAT" --out hansalpur.gif
```

Semantics an agent gets wrong if it only skims the flag table:

- `--radius-km` is a **half**-width. `3x1.2` → a 6 km × 2.4 km scene
  (W km east-west, H km north-south). A single number → square.
- `--season MM-MM` restricts every frame to the same months of its year.
  Recommend it by default for optical sensors in monsoon climates
  (e.g. `01-04` for western India); it is the fix for green/brown flicker.
- Sensor date floors: `sentinel2` mid-2015, `landsat` 1984, `viirs-ntl`
  2012 (and `viirs-ntl` accepts only `--interval 1y`; it ignores
  `--season`/`--max-cloud`). A `--start` before the floor yields empty
  early frames, which are skipped with warnings — prefer switching sensor.
- Do not mix sensors across one GIF; make two GIFs instead.
- `--width` is pixels; frame height follows the scene's km aspect ratio.
- `--scale-bar` is a pure overlay (lower-left, length auto-picked from
  1/2/5 × 10^k near ⅕ of the scene width, in m below 1 km). It is not in
  the cache hash — toggling it re-renders from cache. The legend's size
  text is always the full scene, `2W×2H km`.
- `--contrast` / `--sharpen` are post-download, per-pixel and fixed
  across frames (contrast pivots on grey 128, never the frame mean —
  keep it that way or you reintroduce flicker). Not in the cache hash.
  They touch only the imagery; legend and scale bar are drawn after.

**Cost model / cache.** Each frame is one GEE query plus one image
download, cached in `--cache-dir` keyed on a hash of
`(sat, lat, lon, radius, dates, season, max_cloud, width)`. Changing only
`--fps`, `--hold`, `--title`, `--scale-bar`, `--contrast`,
`--sharpen`, or `--out` re-renders from cache (seconds);
changing anything in the hash refetches those frames (tens of seconds to
minutes). Batch your parameter decisions before fetching; iterate styling
freely afterwards. Never commit the cache.

**Long runs**: a many-frame job (`--interval 1m` over years) is dozens of
sequential network calls — run it in the background and poll, rather than
blocking on a foreground timeout.

## Reading the output

- Progress goes to stdout: one `  <label>: <N> scenes` line per frame.
  `N` is the number of scenes admitted to that frame's composite; `N` of
  one or two for an optical sensor means a fragile composite (expect haze
  or gaps) — consider widening the window or raising `--max-cloud`.
- `<label>: WARNING — no scenes ... frame skipped` is non-fatal; the GIF
  is still written without that frame. Treat >1 skip as a parameter
  problem to fix, not noise to ignore.
- Exit is nonzero (SystemExit) when: EE init fails, or fewer than 2 frames
  could be built. Both messages name the remedy.
- `make_timelapse(...)` returns the rendered frames as PIL Images — in
  notebooks, display them directly instead of re-opening the GIF.

**Verify before reporting success.** Check the GIF exists and is sane:

```bash
python -c "from PIL import Image; g = Image.open('out.gif'); \
print(g.n_frames, 'frames', g.size)"
```

Expected: frame count = number of non-skipped intervals; size ≈
`width × width·(H_km/W_km)`. To eyeball content, `seek()` to a frame and
save it as PNG. A plausible failure that still "succeeds" is an all-black
or all-haze frame — if the user will present the output, inspect at least
the first and last frames visually.

## Modifying the code

- **Style**: plain Python, stdlib + the three deps only. Heavy imports
  (`ee`, `PIL`, `requests`) stay *inside* functions so `--help`, `sensors`,
  and `doctor` work without network or full deps. Keep it one module.
- **Adding a sensor** is the designed extension point: write a builder
  `def _mysensor(region, t0, t1, season, max_cloud) -> (collection,
  visualized_image)` and register it in `SENSORS` with `res`, `coverage`,
  `kind`, `notes`, `attribution`, `min_interval_months`. Fix the
  visualization stretch (constants, never per-frame autoscale — that
  reintroduces flicker). Set `attribution` to the provider's required
  credit line; it is stamped on every frame. Update the README sensor
  table in the same change.
- **Cache compatibility**: the frame-cache key hashes the parameter tuple.
  If you change what a parameter *means* (not just add one), old cache
  entries become silently wrong — add the changed parameter to the hash
  string in `make_timelapse` so stale entries miss.
- **Testing**: there is no test suite; verification is live. Cheapest
  real check: 2–3 frames, small width, one sensor, `--no-mp4`:
  `generate --lat 23.4945 --lon 72.0072 --start 2021 --end 2023 --width 600 --no-mp4 --out /tmp/t.gif`
  then verify frame count/size as above. Test every sensor you touched.
  `doctor` and `generate --help` must both run clean without credentials.
- **Commit hygiene**: never commit `satgif_cache/`, GIFs, or MP4s (the
  `.gitignore` covers them — don't weaken it). Keep `README.md`,
  `AGENTS.md`, docstrings, and `--help` text in agreement: the flag table
  exists in three places (README, argparse help, this file's semantics
  notes); a flag change updates all three.

## Attribution and use

The legend auto-stamps the legally required imagery credit per sensor
(Copernicus for Sentinel, USGS/NASA for Landsat, NOAA for VIIRS). Do not
remove it or add output modes that omit it. When asked for higher
resolution than 10 m: sub-meter basemap imagery (Google Earth / Maxar) has
no programmatic export — say so rather than attempting workarounds.
