#!/usr/bin/env python3
"""satgif — satellite timelapse GIFs and MP4s from Google Earth Engine.

Give it a location, a date range, and a satellite; get an annotated,
loopable timelapse with a legend panel, timeline indicator, and correct
imagery attribution. Frames are cloud-free median composites with a fixed
brightness stretch, so the series shows change on the ground, not weather.

Python:
    from satgif import make_timelapse
    make_timelapse(lat=23.4945, lon=72.0072, radius_km='3x1.2',
                   start='2016', end='2023', season='01-04',
                   title='HANSALPUR, GUJARAT', out='hansalpur.gif')

Command line:
    python satgif.py generate --lat 23.4945 --lon 72.0072 \
        --start 2016 --end 2023 --out hansalpur.gif
    python satgif.py sensors        # available satellites and coverage
    python satgif.py doctor         # diagnose install / auth / project setup

Setup (once): a Google account and an Earth Engine-registered Cloud project
(free for noncommercial use) are required — there is no plain API key.
    1. Register:      https://code.earthengine.google.com/register
    2. Authenticate:  python -c "import ee; ee.Authenticate()"
    3. Set project:   echo YOUR-PROJECT-ID > ~/.satgif
Full manual: README.md. Setup check: python satgif.py doctor.
"""
import argparse
import hashlib
import os
import shutil
import subprocess
import sys
from datetime import date

# ---------------------------------------------------------------- sensors

def _s2(region, t0, t1, season, max_cloud):
    import ee
    col = (ee.ImageCollection('COPERNICUS/S2_SR_HARMONIZED')
           .filterBounds(region).filterDate(t0, t1)
           .filter(ee.Filter.lt('CLOUDY_PIXEL_PERCENTAGE', max_cloud)))
    col = _season_filter(col, season)
    img = col.median().divide(10000)
    return col, img.visualize(bands=['B4', 'B3', 'B2'], min=0, max=0.3, gamma=1.2)


def _landsat(region, t0, t1, season, max_cloud):
    import ee
    def prep(bands):
        def f(img):
            return (img.select(bands, ['R', 'G', 'B'])
                    .multiply(0.0000275).add(-0.2)
                    .copyProperties(img, ['system:time_start']))
        return f
    tm = ['SR_B3', 'SR_B2', 'SR_B1']      # Landsat 5/7
    oli = ['SR_B4', 'SR_B3', 'SR_B2']     # Landsat 8/9
    col = None
    for cid, bands in [('LANDSAT/LT05/C02/T1_L2', tm),
                       ('LANDSAT/LE07/C02/T1_L2', tm),
                       ('LANDSAT/LC08/C02/T1_L2', oli),
                       ('LANDSAT/LC09/C02/T1_L2', oli)]:
        c = (ee.ImageCollection(cid)
             .filter(ee.Filter.lt('CLOUD_COVER', max_cloud))
             .map(prep(bands)))
        col = c if col is None else col.merge(c)
    col = _season_filter(col.filterBounds(region).filterDate(t0, t1), season)
    img = ee.ImageCollection(col).median()
    return col, img.visualize(bands=['R', 'G', 'B'], min=0, max=0.3, gamma=1.2)


def _viirs(region, t0, t1, season, max_cloud):
    import ee
    year = int(t0[:4])
    cid = 'NOAA/VIIRS/DNB/ANNUAL_V22' if year >= 2022 else 'NOAA/VIIRS/DNB/ANNUAL_V21'
    col = ee.ImageCollection(cid).filterDate(t0, t1).select('average_masked')
    img = col.first().add(1).log10()
    inferno = ['000004', '320a5a', '781c6d', 'bb3754',
               'ec6824', 'fbb41a', 'fcffa4']
    return col, img.visualize(min=0, max=2, palette=inferno)


def _season_filter(col, season):
    import ee
    if not season:
        return col
    m0, m1 = (int(m) for m in season.split('-'))
    return col.filter(ee.Filter.calendarRange(m0, m1, 'month'))


SENSORS = {
    'sentinel2': dict(
        fn=_s2, res='10 m', coverage='2015-07 to present', kind='optical',
        notes='Sharpest free optical imagery. Best default for 2015+.',
        attribution='Contains modified Copernicus Sentinel data',
        min_interval_months=1),
    'landsat': dict(
        fn=_landsat, res='30 m', coverage='1984 to present', kind='optical',
        notes='Landsat 5/7/8/9 merged. Coarser, but 40 years of history.',
        attribution='Imagery: USGS/NASA Landsat',
        min_interval_months=1),
    'viirs-ntl': dict(
        fn=_viirs, res='~500 m', coverage='2012 to present', kind='night lights',
        notes='VIIRS DNB annual nighttime-lights composites (log-scaled, '
              'inferno palette). Yearly interval only; season/cloud ignored.',
        attribution='Nighttime lights: NOAA VIIRS DNB',
        min_interval_months=12),
}

# ---------------------------------------------------------------- helpers

KM_PER_DEG_LAT = 110.574


def _parse_radius(radius_km):
    """A number means a square; 'WxH' or (W, H) means E-W by N-S half-widths."""
    if isinstance(radius_km, str):
        parts = radius_km.lower().split('x')
        return float(parts[0]), float(parts[-1])
    if isinstance(radius_km, (tuple, list)):
        return float(radius_km[0]), float(radius_km[1])
    return float(radius_km), float(radius_km)


def _region(lat, lon, radius_km):
    import ee
    import math
    rx, ry = _parse_radius(radius_km)
    d_lat = ry / KM_PER_DEG_LAT
    d_lon = rx / (111.320 * math.cos(math.radians(lat)))
    coords = [lon - d_lon, lat - d_lat, lon + d_lon, lat + d_lat]
    return ee.Geometry.Rectangle(coords)


def _parse_ym(s, default_month):
    s = str(s)
    if '-' in s:
        y, m = s.split('-')[:2]
        return int(y), int(m)
    return int(s), default_month


def _frames_spec(start, end, interval):
    """Yield (label, t0, t1) ISO date ranges, one per frame."""
    months = {'1y': 12, '6m': 6, '3m': 3, '1m': 1}[interval]
    y0, m0 = _parse_ym(start, 1)
    y1, m1 = _parse_ym(end, 1 if interval != '1y' else 12)
    cur = y0 * 12 + (m0 - 1)
    last = y1 * 12 + (m1 - 1)
    out = []
    while cur <= last:
        y, m = divmod(cur, 12)
        nxt = cur + months
        ny, nm = divmod(nxt, 12)
        t0 = f'{y:04d}-{m + 1:02d}-01'
        t1 = f'{ny:04d}-{nm + 1:02d}-01'
        if interval == '1y':
            label = str(y)
        elif interval == '3m':
            label = f'Q{m // 3 + 1} {y}'
        else:
            label = date(y, m + 1, 1).strftime('%b %Y')
        out.append((label, t0, t1))
        cur = nxt
    return out


def _fonts(scale):
    from PIL import ImageFont
    candidates = [
        ('/System/Library/Fonts/HelveticaNeue.ttc', {'medium': 10, 'bold': 1, 'regular': 0}),
        ('/System/Library/Fonts/Helvetica.ttc', {'medium': 0, 'bold': 1, 'regular': 0}),
        ('/usr/share/fonts/truetype/dejavu/DejaVuSans.ttf', None),
    ]
    for path, idx in candidates:
        if os.path.exists(path):
            def load(key, size):
                if idx is None:
                    return ImageFont.truetype(path, size)
                return ImageFont.truetype(path, size, index=idx[key])
            return (load('medium', max(12, int(26 * scale))),
                    load('bold', max(20, int(72 * scale))),
                    load('regular', max(11, int(22 * scale))))
    f = ImageFont.load_default()
    return f, f, f


def _draw_panel(img, label, i, n, title, subtitle, attribution):
    """Legend panel in the lower-right corner; sizes scale with frame width."""
    from PIL import Image, ImageDraw
    s = img.width / 2400
    f_label, f_date, f_small = _fonts(s)
    overlay = Image.new('RGBA', img.size, (0, 0, 0, 0))
    d = ImageDraw.Draw(overlay)
    PAD = int(28 * s)
    W = int(600 * s)
    H = int(296 * s)
    PX, PY = img.width - W - int(40 * s), img.height - H - int(40 * s)
    y = PY + PAD
    d.rounded_rectangle([PX, PY, PX + W, PY + H], radius=int(22 * s),
                        fill=(12, 14, 18, 190))
    x = PX + PAD
    for ch in title:
        d.text((x, y), ch, font=f_label, fill=(190, 196, 205, 255))
        x += d.textlength(ch, font=f_label) + int(5 * s)
    y += int(44 * s)
    d.text((PX + PAD, y), label, font=f_date, fill=(255, 255, 255, 255))
    y += int(104 * s)
    tx0, tx1 = PX + PAD, PX + W - PAD
    if n > 1:
        if n <= 16:
            d.line([tx0, y, tx1, y], fill=(255, 255, 255, 70),
                   width=max(2, int(3 * s)))
            for j in range(n):
                x = tx0 + (tx1 - tx0) * j / (n - 1)
                r = int((10 if j == i else 5) * s) or 2
                fill = (255, 196, 0, 255) if j == i else (255, 255, 255, 140)
                d.ellipse([x - r, y - r, x + r, y + r], fill=fill)
        else:
            d.line([tx0, y, tx1, y], fill=(255, 255, 255, 70),
                   width=max(2, int(4 * s)))
            x = tx0 + (tx1 - tx0) * i / (n - 1)
            d.line([tx0, y, x, y], fill=(255, 196, 0, 255),
                   width=max(2, int(4 * s)))
    y += int(30 * s)
    d.text((PX + PAD, y), subtitle, font=f_small, fill=(190, 196, 205, 255))
    y += int(34 * s)
    d.text((PX + PAD, y), attribution, font=f_small, fill=(140, 146, 155, 255))
    return Image.alpha_composite(img.convert('RGBA'), overlay).convert('RGB')


def _resolve_project(project):
    if project:
        return project
    if os.environ.get('SATGIF_PROJECT'):
        return os.environ['SATGIF_PROJECT']
    cfg = os.path.expanduser('~/.satgif')
    if os.path.exists(cfg):
        return open(cfg).read().strip()
    return None

# ---------------------------------------------------------------- main API

def make_timelapse(lat, lon, radius_km=2.0, start='2016', end=None,
                   interval='1y', season=None, sat='sentinel2',
                   width=1200, fps=2.0, hold=2.0, max_cloud=20,
                   title=None, out='timelapse.gif', mp4=True,
                   project=None, cache_dir='satgif_cache', verbose=True):
    """Build a satellite timelapse GIF (and, if ffmpeg is present, an MP4).

    Each frame is a cloud-free median composite of every usable scene in its
    interval, rendered with a fixed per-sensor brightness stretch and stamped
    with a legend panel (title, period label, timeline indicator, scene size,
    coordinates, attribution).

    Args:
        lat, lon: Scene center in decimal degrees (negative = south/west).
        radius_km: Scene half-width in km. A number gives a square scene;
            'WxH' (e.g. '3x1.2') or a (W, H) tuple gives W km east-west by
            H km north-south — a 2*W by 2*H km scene.
        start, end: Frame range, 'YYYY' or 'YYYY-MM'. `end` defaults to the
            last full calendar year.
        interval: One frame per '1y', '6m', '3m', or '1m'.
        season: 'MM-MM' (e.g. '01-04') — restrict every frame's imagery to
            the same months of its year. Fixes seasonal green/brown flicker.
        sat: Sensor key — 'sentinel2' (10 m, 2015+), 'landsat' (30 m, 1984+),
            or 'viirs-ntl' (nighttime lights, yearly only). See SENSORS.
        width: Frame width in pixels; height follows the scene's aspect.
        fps: Playback speed in frames per second.
        hold: Extra seconds the final frame stays on screen.
        max_cloud: Max per-scene cloud percentage admitted to composites.
            Raise it if frames come back empty; lower it if frames look hazy.
        title: Legend heading. Defaults to formatted coordinates.
        out: Output GIF path. The MP4 is written beside it (same stem).
        mp4: Set False to skip the MP4 even when ffmpeg is available.
        project: Earth Engine Cloud project id. Falls back to the
            SATGIF_PROJECT environment variable, then the ~/.satgif file.
        cache_dir: Downloaded frames are cached here by parameter hash, so
            reruns that only change styling or timing cost zero refetches.
        verbose: Print per-frame progress.

    Returns:
        The rendered frames as a list of PIL Images.

    Raises:
        ValueError: Unknown sensor, or an interval the sensor cannot serve.
        SystemExit: Earth Engine initialization failed (run `satgif.py
            doctor` for step-by-step fixes), or fewer than two frames could
            be built.

    Frames with no usable scenes are skipped with a printed warning naming
    the fix rather than raising.
    """
    import ee
    import requests
    from PIL import Image

    if sat not in SENSORS:
        raise ValueError(f'unknown sat {sat!r} — options: {", ".join(SENSORS)}')
    sensor = SENSORS[sat]
    if sensor['min_interval_months'] >= 12 and interval != '1y':
        raise ValueError(f'{sat} only supports --interval 1y')

    project = _resolve_project(project)
    try:
        ee.Initialize(project=project)
    except Exception as e:
        raise SystemExit(
            f'Earth Engine init failed ({e}).\nRun `python satgif.py doctor` '
            'for setup steps.') from e

    if end is None:
        end = str(date.today().year - 1)
    spec = _frames_spec(start, end, interval)
    region = _region(lat, lon, radius_km)
    if title is None:
        title = f'{abs(lat):.4f}° {"N" if lat >= 0 else "S"}, ' \
                f'{abs(lon):.4f}° {"E" if lon >= 0 else "W"}'
    rx, ry = _parse_radius(radius_km)
    rad_txt = f'{rx:g} km' if rx == ry else f'{2*rx:g}×{2*ry:g} km'
    subtitle = f'{rad_txt}  ·  {lat:.4f}°, {lon:.4f}°'
    os.makedirs(cache_dir, exist_ok=True)

    frames = []
    labels = []
    for label, t0, t1 in spec:
        key = hashlib.md5(f'{sat}|{lat}|{lon}|{radius_km}|{t0}|{t1}|'
                          f'{season}|{max_cloud}|{width}'.encode()).hexdigest()
        cached = os.path.join(cache_dir, key + '.png')
        if os.path.exists(cached):
            frames.append(Image.open(cached).convert('RGB'))
            labels.append(label)
            if verbose:
                print(f'  {label}: cached')
            continue
        col, vis = sensor['fn'](region, t0, t1, season, max_cloud)
        n_scenes = col.size().getInfo()
        if n_scenes == 0:
            print(f'  {label}: WARNING — no scenes '
                  f'(try higher --max-cloud or no --season); frame skipped')
            continue
        url = vis.getThumbURL({'region': region, 'dimensions': width,
                               'format': 'png'})
        r = requests.get(url, timeout=180)
        r.raise_for_status()
        with open(cached, 'wb') as fh:
            fh.write(r.content)
        frames.append(Image.open(cached).convert('RGB'))
        labels.append(label)
        if verbose:
            print(f'  {label}: {n_scenes} scenes')

    if len(frames) < 2:
        raise SystemExit('fewer than 2 frames produced — nothing to animate')

    n = len(frames)
    rendered = [_draw_panel(f, lbl, i, n, title, subtitle,
                            sensor['attribution'])
                for i, (f, lbl) in enumerate(zip(frames, labels))]

    pal = [f.convert('P', palette=Image.ADAPTIVE, colors=128)
           for f in rendered]
    durations = [int(1000 / fps)] * (n - 1) + [int(1000 / fps + hold * 1000)]
    pal[0].save(out, save_all=True, append_images=pal[1:],
                duration=durations, loop=0)
    if verbose:
        print(f'wrote {out} ({n} frames)')

    if mp4 and shutil.which('ffmpeg'):
        tmp = os.path.join(cache_dir, '_render')
        os.makedirs(tmp, exist_ok=True)
        for i, f in enumerate(rendered):
            if f.width % 2 or f.height % 2:
                f = f.crop((0, 0, f.width - f.width % 2,
                            f.height - f.height % 2))
            f.save(os.path.join(tmp, f'f_{i:03d}.png'))
        mp4_path = os.path.splitext(out)[0] + '.mp4'
        subprocess.run(
            ['ffmpeg', '-y', '-framerate', str(fps),
             '-i', os.path.join(tmp, 'f_%03d.png'),
             '-vf', f'tpad=stop_mode=clone:stop_duration={hold}',
             '-c:v', 'libx264', '-pix_fmt', 'yuv420p', '-crf', '18',
             mp4_path], check=True, capture_output=True)
        if verbose:
            print(f'wrote {mp4_path}')
    elif mp4 and verbose:
        print('ffmpeg not found — skipped MP4 (brew install ffmpeg)')
    return rendered

# ---------------------------------------------------------------- CLI

def _cmd_sensors(args):
    if args.name:
        s = SENSORS.get(args.name)
        if not s:
            sys.exit(f'unknown sensor {args.name!r}')
        print(f'{args.name}\n  resolution : {s["res"]}\n'
              f'  coverage   : {s["coverage"]}\n  type       : {s["kind"]}\n'
              f'  attribution: {s["attribution"]}\n  notes      : {s["notes"]}')
        return
    w = max(len(k) for k in SENSORS)
    print(f'{"NAME":{w}}  {"RES":6}  {"COVERAGE":22}  {"TYPE":12}  NOTES')
    for k, s in SENSORS.items():
        print(f'{k:{w}}  {s["res"]:6}  {s["coverage"]:22}  '
              f'{s["kind"]:12}  {s["notes"]}')


def _cmd_doctor(args):
    ok = True
    try:
        import ee  # noqa: F401
        print('[ok] earthengine-api installed')
    except ImportError:
        print('[FAIL] earthengine-api missing -> pip install earthengine-api')
        return
    creds = os.path.expanduser('~/.config/earthengine/credentials')
    if os.path.exists(creds):
        print('[ok] credentials found')
    else:
        ok = False
        print('[FAIL] no credentials -> python -c "import ee; ee.Authenticate()"')
    project = _resolve_project(args.project)
    if not project:
        ok = False
        print('[FAIL] no project configured -> pass --project, set '
              'SATGIF_PROJECT, or write the id to ~/.satgif\n'
              '       (register one free: '
              'https://code.earthengine.google.com/register)')
    elif os.path.exists(creds):
        import ee
        try:
            ee.Initialize(project=project)
            ee.Number(1).getInfo()
            print(f'[ok] Earth Engine works with project {project!r}')
        except Exception as e:
            ok = False
            print(f'[FAIL] init with project {project!r}: {str(e)[:160]}')
    if shutil.which('ffmpeg'):
        print('[ok] ffmpeg found (MP4 output enabled)')
    else:
        print('[warn] ffmpeg not found — GIF only (brew install ffmpeg)')
    print('all good' if ok else 'fix the FAIL lines above, then rerun doctor')


def _cmd_generate(args):
    make_timelapse(lat=args.lat, lon=args.lon, radius_km=args.radius_km,
                   start=args.start, end=args.end, interval=args.interval,
                   season=args.season, sat=args.sat, width=args.width,
                   fps=args.fps, hold=args.hold, max_cloud=args.max_cloud,
                   title=args.title, out=args.out, mp4=not args.no_mp4,
                   project=args.project, cache_dir=args.cache_dir)


def main(argv=None):
    p = argparse.ArgumentParser(
        prog='satgif', description=__doc__,
        formatter_class=argparse.RawDescriptionHelpFormatter)
    sub = p.add_subparsers(dest='cmd', required=True)

    g = sub.add_parser('generate', help='build a timelapse GIF/MP4')
    g.add_argument('--lat', type=float, required=True,
                   help='center latitude, decimal degrees')
    g.add_argument('--lon', type=float, required=True,
                   help='center longitude, decimal degrees')
    g.add_argument('--radius-km', default='2',
                   help="scene half-width in km: one number for a square "
                        "(default 2), or WxH for a rectangle, e.g. '3x1.5' "
                        '= 3 km east-west by 1.5 km north-south')
    g.add_argument('--start', default='2016',
                   help="first frame, 'YYYY' or 'YYYY-MM' (default 2016)")
    g.add_argument('--end', default=None,
                   help="last frame, 'YYYY' or 'YYYY-MM' "
                        '(default: last full year)')
    g.add_argument('--interval', choices=['1y', '6m', '3m', '1m'],
                   default='1y', help='one frame per this period (default 1y)')
    g.add_argument('--season', default=None, metavar='MM-MM',
                   help="limit every frame to the same months, e.g. '01-04' — "
                        'prevents seasonal green/brown flicker')
    g.add_argument('--sat', choices=list(SENSORS), default='sentinel2',
                   help="satellite (see 'satgif sensors'; default sentinel2)")
    g.add_argument('--width', type=int, default=1200,
                   help='frame width px; height follows bbox (default 1200)')
    g.add_argument('--fps', type=float, default=2.0,
                   help='frames per second (default 2)')
    g.add_argument('--hold', type=float, default=2.0,
                   help='extra seconds on the final frame (default 2)')
    g.add_argument('--max-cloud', type=float, default=20,
                   help='max scene cloud %% in composites (default 20)')
    g.add_argument('--title', default=None,
                   help='legend heading (default: the coordinates)')
    g.add_argument('--out', default='timelapse.gif',
                   help='output GIF path; MP4 lands beside it')
    g.add_argument('--no-mp4', action='store_true',
                   help='skip the MP4 even if ffmpeg is available')
    g.add_argument('--project', default=None,
                   help='GEE Cloud project id (or SATGIF_PROJECT / ~/.satgif)')
    g.add_argument('--cache-dir', default='satgif_cache',
                   help='downloaded-frame cache (default satgif_cache/)')
    g.set_defaults(func=_cmd_generate)

    s = sub.add_parser('sensors', help='list satellites and their coverage')
    s.add_argument('name', nargs='?', help='show one sensor in detail')
    s.set_defaults(func=_cmd_sensors)

    d = sub.add_parser('doctor', help='check install, auth, and project setup')
    d.add_argument('--project', default=None, help='project id to test')
    d.set_defaults(func=_cmd_doctor)

    args = p.parse_args(argv)
    args.func(args)


if __name__ == '__main__':
    main()
