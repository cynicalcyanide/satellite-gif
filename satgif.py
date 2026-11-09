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


def _bounds(lat, lon, radius_km):
    """Scene bounding box as (lon_min, lat_min, lon_max, lat_max)."""
    import math
    rx, ry = _parse_radius(radius_km)
    d_lat = ry / KM_PER_DEG_LAT
    d_lon = rx / (111.320 * math.cos(math.radians(lat)))
    return lon - d_lon, lat - d_lat, lon + d_lon, lat + d_lat


def _region(lat, lon, radius_km):
    import ee
    return ee.Geometry.Rectangle(list(_bounds(lat, lon, radius_km)))


# Frames are rendered in Web Mercator (EPSG:3857), which is conformal: a
# square kilometre is a square on screen, so the frame's pixel aspect equals
# the scene's km aspect and one scale bar is right in both axes. (The default
# EPSG:4326 thumbnail squashes the north-south axis by cos(latitude).)
RENDER_CRS = 'EPSG:3857'


def _merc_y(lat_deg):
    import math
    return math.log(math.tan(math.pi / 4 + math.radians(lat_deg) / 2))


def _lonlat_to_px(lon, lat, bounds, size):
    """Map a lon/lat to pixel coordinates in a frame rendered in RENDER_CRS."""
    lon0, lat0, lon1, lat1 = bounds
    w, h = size
    x = (lon - lon0) / (lon1 - lon0) * w
    y0, y1 = _merc_y(lat0), _merc_y(lat1)
    y = (y1 - _merc_y(lat)) / (y1 - y0) * h
    return x, y


def _ring_area_km2(ring, lat_ref):
    """Planar shoelace area of a lon/lat ring on a local metric grid (good to
    well under 0.1% for scenes a few tens of km across)."""
    import math
    kx = 111.320 * math.cos(math.radians(lat_ref))
    ky = KM_PER_DEG_LAT
    pts = [(lon * kx, lat * ky) for lon, lat in ring]
    a = 0.0
    for (x0, y0), (x1, y1) in zip(pts, pts[1:] + pts[:1]):
        a += x0 * y1 - x1 * y0
    return abs(a) / 2


def _fmt_area(km2):
    ha = km2 * 100
    if ha < 1:
        return f'{ha * 10000:,.0f} m²'
    if ha < 10000:
        return f'{ha:,.0f} ha'
    return f'{ha:,.0f} ha  ({km2:,.0f} km²)'


def _load_polygons(path):
    """Read a GeoJSON file into [(label, outer_ring, area_km2, color)].

    Accepts a FeatureCollection, a Feature, or a bare Polygon/MultiPolygon.
    Feature properties used: `name` (or `label`) for the caption and an
    optional `color` ('#rrggbb'). Holes are subtracted from the area but not
    drawn. Each part of a MultiPolygon is drawn and labelled separately.
    """
    import json
    with open(path) as fh:
        gj = json.load(fh)
    feats = (gj['features'] if gj.get('type') == 'FeatureCollection'
             else [gj] if gj.get('type') == 'Feature'
             else [{'type': 'Feature', 'geometry': gj, 'properties': {}}])
    out = []
    for f in feats:
        geom = f.get('geometry') or {}
        props = f.get('properties') or {}
        label = props.get('name') or props.get('label') or ''
        color = props.get('color')
        polys = ([geom['coordinates']] if geom.get('type') == 'Polygon'
                 else geom['coordinates'] if geom.get('type') == 'MultiPolygon'
                 else [])
        for rings in polys:
            if not rings:
                continue
            outer = [tuple(p[:2]) for p in rings[0]]
            lat_ref = sum(p[1] for p in outer) / len(outer)
            area = _ring_area_km2(outer, lat_ref)
            for hole in rings[1:]:
                area -= _ring_area_km2([tuple(p[:2]) for p in hole], lat_ref)
            out.append((label, outer, area, color))
    return out


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


ACCENT = (242, 122, 105)   # outline/label colour for polygons and built area


def _draw_panel(img, label, i, n, title, subtitle, attribution, extra=None):
    """Legend panel in the lower-right corner; sizes scale with frame width.

    `extra`, if given, is one more line (e.g. the built-up area) drawn in the
    accent colour under the scene-size line.
    """
    from PIL import Image, ImageDraw
    s = img.width / 2400
    f_label, f_date, f_small = _fonts(s)
    overlay = Image.new('RGBA', img.size, (0, 0, 0, 0))
    d = ImageDraw.Draw(overlay)
    PAD = int(28 * s)
    W = int(600 * s)
    H = int(296 * s) + (int(34 * s) if extra else 0)
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
    if extra:
        d.text((PX + PAD, y), extra, font=f_small, fill=ACCENT + (255,))
        y += int(34 * s)
    d.text((PX + PAD, y), attribution, font=f_small, fill=(140, 146, 155, 255))
    return Image.alpha_composite(img.convert('RGBA'), overlay).convert('RGB')


def _dark_mask(img, threshold):
    """Mode-'L' mask (255 = dark) of pixels whose luminance is below
    `threshold`, opened with a 3x3 min/max filter to drop single-pixel
    noise. Computed on the raw frame, before contrast/sharpen."""
    from PIL import ImageFilter
    m = img.convert('L').point(lambda v: 255 if v < threshold else 0)
    return m.filter(ImageFilter.MinFilter(3)).filter(ImageFilter.MaxFilter(3))


def _built_masks(frames, threshold):
    """Built-up mask per frame: dark now, still dark in the next frame and in
    the final frame, and not dark in the first frame.

    Panels and turbine pads are dark against bright ground, and construction
    is permanent, so a built pixel stays dark in every later frame. Requiring
    darkness in the next frame and the last one drops transient darkness
    that lasts one frame (monsoon flooding, cloud shadow). Dropping anything
    dark in the first frame removes permanent water, roads and rock that
    were there before building started, so start the series on a dry frame.
    The first frame's own built area is zero by construction, and the last
    frame's mask is the envelope everything else is measured within.
    """
    from PIL import ImageChops
    dark = [_dark_mask(f, threshold) for f in frames]
    base_inv = ImageChops.invert(dark[0])
    final = dark[-1]
    out = []
    for i, m in enumerate(dark):
        nxt = dark[min(i + 1, len(dark) - 1)]
        m = ImageChops.multiply(ImageChops.multiply(m, nxt), final)
        out.append(ImageChops.multiply(m, base_inv))
    return out


def _mask_area_km2(mask, km_per_px):
    hist = mask.histogram()
    return hist[255] * km_per_px * km_per_px


def _draw_mask_outline(img, mask, color=ACCENT):
    """Trace the boundary of a mask onto the frame in `color`, with a thin
    dark halo so the line reads on white salt and on dark panels alike."""
    from PIL import Image, ImageChops, ImageFilter
    s = img.width / 2400
    k = max(3, int(7 * s) | 1)      # odd kernel; ~5 px at 1600 px wide
    edge = ImageChops.subtract(mask, mask.filter(ImageFilter.MinFilter(k)))
    halo = edge.filter(ImageFilter.MaxFilter(3))
    out = img.convert('RGBA')
    out.paste(Image.new('RGBA', img.size, (0, 0, 0, 160)), mask=halo)
    out.paste(Image.new('RGBA', img.size, color + (255,)), mask=edge)
    return out.convert('RGB')


def _draw_polygons(img, polys, bounds):
    """Outline each (label, ring, area_km2, color) polygon and caption it with
    its name and area at the ring's centroid."""
    from PIL import Image, ImageDraw
    s = img.width / 2400
    f_txt, _, f_small = _fonts(s)
    overlay = Image.new('RGBA', img.size, (0, 0, 0, 0))
    d = ImageDraw.Draw(overlay)
    lw = max(2, int(5 * s))
    for label, ring, area, color in polys:
        if color:
            c = tuple(int(color.lstrip('#')[i:i + 2], 16) for i in (0, 2, 4))
        else:
            c = ACCENT
        pts = [_lonlat_to_px(lon, lat, bounds, img.size) for lon, lat in ring]
        d.line(pts + pts[:1], fill=(0, 0, 0, 150), width=lw + 2)
        d.line(pts + pts[:1], fill=c + (255,), width=lw)
        cx = sum(p[0] for p in pts) / len(pts)
        cy = sum(p[1] for p in pts) / len(pts)
        lines = [t for t in (label, _fmt_area(area)) if t]
        tw = max(d.textlength(t, font=f_txt) for t in lines)
        th = int(32 * s) * len(lines)
        pad = int(12 * s)
        box = [cx - tw / 2 - pad, cy - th / 2 - pad,
               cx + tw / 2 + pad, cy + th / 2 + pad]
        d.rounded_rectangle(box, radius=int(10 * s), fill=(12, 14, 18, 190))
        y = cy - th / 2
        for j, t in enumerate(lines):
            fill = (255, 255, 255, 255) if j == 0 else c + (255,)
            d.text((cx - d.textlength(t, font=f_txt) / 2, y), t,
                   font=f_txt, fill=fill)
            y += int(32 * s)
    return Image.alpha_composite(img.convert('RGBA'), overlay).convert('RGB')


def _enhance(img, contrast=1.0, sharpen=0.0):
    """Fixed, per-pixel contrast and sharpening applied identically to every
    frame. Contrast pivots on mid-grey (128), not the frame's own mean, so
    frames with different content can't drift apart (no flicker)."""
    from PIL import ImageFilter
    if contrast != 1.0:
        lut = [max(0, min(255, round((v - 128) * contrast + 128)))
               for v in range(256)]
        img = img.point(lut * 3)
    if sharpen > 0:
        img = img.filter(ImageFilter.UnsharpMask(
            radius=1.5, percent=int(sharpen * 100), threshold=2))
    return img


def _nice_length(km):
    """Largest 1/2/5 x 10^k km value not exceeding `km`."""
    import math
    k = 10 ** math.floor(math.log10(km))
    for m in (5, 2, 1):
        if m * k <= km:
            return m * k
    return k


def _draw_scale_bar(img, scene_w_km):
    """Scale bar in the lower-left corner, matching the legend panel style.

    Length is a round 1/2/5 value near a fifth of the scene width; the bar
    is split into black/white segments with 0 / mid / end labels.
    """
    from PIL import Image, ImageDraw
    s = img.width / 2400
    f_txt, _, _ = _fonts(s)
    px_per_km = img.width / scene_w_km
    length_km = _nice_length(scene_w_km / 5)
    bar_w = int(round(length_km * px_per_km))
    unit = 'km' if length_km >= 1 else 'm'
    fmt = (lambda v: f'{v:g}') if unit == 'km' else (lambda v: f'{v * 1000:g}')

    overlay = Image.new('RGBA', img.size, (0, 0, 0, 0))
    d = ImageDraw.Draw(overlay)
    PAD = int(28 * s)
    BAR_H = max(8, int(24 * s))
    txt_h = int(34 * s)
    gap = int(10 * s)
    end_txt = f'{fmt(length_km)} {unit}'
    end_w = d.textlength(end_txt, font=f_txt)
    W = bar_w + 2 * PAD + int(end_w / 2)
    H = 2 * PAD + txt_h + gap + BAR_H
    PX = int(40 * s)
    PY = img.height - H - int(40 * s)
    d.rounded_rectangle([PX, PY, PX + W, PY + H], radius=int(22 * s),
                        fill=(12, 14, 18, 190))
    bx0 = PX + PAD
    by0 = PY + PAD + txt_h + gap
    nseg = 4
    for j in range(nseg):
        x0 = bx0 + bar_w * j / nseg
        x1 = bx0 + bar_w * (j + 1) / nseg
        fill = (255, 255, 255, 255) if j % 2 == 0 else (20, 22, 26, 255)
        d.rectangle([x0, by0, x1, by0 + BAR_H], fill=fill)
    d.rectangle([bx0, by0, bx0 + bar_w, by0 + BAR_H],
                outline=(255, 255, 255, 255), width=max(1, int(2 * s)))
    for v, x in ((0, bx0), (length_km / 2, bx0 + bar_w / 2),
                 (length_km, bx0 + bar_w)):
        t = end_txt if v == length_km else fmt(v)
        tw = d.textlength(t, font=f_txt)
        d.text((x - tw / 2, PY + PAD), t, font=f_txt,
               fill=(230, 233, 238, 255))
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

def _write_mp4(rendered, mp4_path, fps, hold):
    """Encode frames to MP4 via ffmpeg.

    Frames go to a fresh per-run temp dir: ffmpeg's f_%03d.png pattern reads
    every consecutive file present, so a shared, reused dir would append
    leftover frames from an earlier, longer run to this video.
    """
    import tempfile
    with tempfile.TemporaryDirectory(prefix='satgif_render_') as tmp:
        for i, f in enumerate(rendered):
            if f.width % 2 or f.height % 2:
                f = f.crop((0, 0, f.width - f.width % 2,
                            f.height - f.height % 2))
            f.save(os.path.join(tmp, f'f_{i:03d}.png'))
        subprocess.run(
            ['ffmpeg', '-y', '-framerate', str(fps),
             '-i', os.path.join(tmp, 'f_%03d.png'),
             '-vf', f'tpad=stop_mode=clone:stop_duration={hold}',
             '-c:v', 'libx264', '-pix_fmt', 'yuv420p', '-crf', '18',
             mp4_path], check=True, capture_output=True)


def make_timelapse(lat, lon, radius_km=2.0, start='2016', end=None,
                   interval='1y', season=None, sat='sentinel2',
                   width=1200, fps=2.0, hold=2.0, max_cloud=20,
                   title=None, scale_bar=False, contrast=1.0, sharpen=0.0,
                   built_area=False, built_threshold=110, polygons=None,
                   frames_dir=None, out='timelapse.gif', mp4=True,
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
        scale_bar: Draw a distance scale bar in the lower-left corner
            (a round 1/2/5 length near a fifth of the scene width).
        contrast: Contrast multiplier around mid-grey; 1.0 = unchanged,
            1.2-1.4 = punchier, <1 = flatter. Imagery only, not the legend.
        sharpen: Unsharp-mask strength; 0 = off, 0.5-1.5 typical. Above
            ~1.5, halos appear around sharp edges such as panel rows.
        built_area: Measure and outline the built-up area in every frame
            (pixels darker than `built_threshold` that are also dark in the
            last frame and were not dark in the first). The hectares go in
            the legend and in `<out stem>_built_area.csv`. Meant for dark
            structures on bright ground (solar parks on sand or salt).
        built_threshold: Luminance (0-255) below which a pixel counts as
            dark for `built_area`. Raise it if panels are missed; lower it
            if bare ground is caught.
        polygons: Path to a GeoJSON file. Every polygon in it is outlined on
            every frame and captioned with its `name` property and its area
            computed from the coordinates (hectares, or km² when large).
        frames_dir: If given, every rendered frame is also saved there as
            `<out stem>_NN.png`, with a `<out stem>_frames.csv` index — for
            slide decks (LaTeX `animate`) or further analysis.
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
    if contrast <= 0:
        raise ValueError('contrast must be > 0 (1.0 = unchanged)')
    if sharpen < 0:
        raise ValueError('sharpen must be >= 0 (0 = off)')

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
    bounds = _bounds(lat, lon, radius_km)
    polys = _load_polygons(polygons) if polygons else []
    if title is None:
        title = f'{abs(lat):.4f}° {"N" if lat >= 0 else "S"}, ' \
                f'{abs(lon):.4f}° {"E" if lon >= 0 else "W"}'
    rx, ry = _parse_radius(radius_km)
    rad_txt = f'{2*rx:g}×{2*ry:g} km'
    subtitle = f'{rad_txt}  ·  {lat:.4f}°, {lon:.4f}°'
    os.makedirs(cache_dir, exist_ok=True)

    frames = []
    labels = []
    spans = []
    for label, t0, t1 in spec:
        key = hashlib.md5(f'{sat}|{lat}|{lon}|{radius_km}|{t0}|{t1}|'
                          f'{season}|{max_cloud}|{width}|{RENDER_CRS}'
                          .encode()).hexdigest()
        cached = os.path.join(cache_dir, key + '.png')
        if os.path.exists(cached):
            frames.append(Image.open(cached).convert('RGB'))
            labels.append(label)
            spans.append((t0, t1))
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
                               'crs': RENDER_CRS, 'format': 'png'})
        r = requests.get(url, timeout=180)
        r.raise_for_status()
        with open(cached, 'wb') as fh:
            fh.write(r.content)
        frames.append(Image.open(cached).convert('RGB'))
        labels.append(label)
        spans.append((t0, t1))
        if verbose:
            print(f'  {label}: {n_scenes} scenes')

    if len(frames) < 2:
        raise SystemExit('fewer than 2 frames produced — nothing to animate')

    n = len(frames)
    stem = os.path.splitext(out)[0]
    km_per_px = 2 * rx / frames[0].width

    masks = extras = None
    if built_area:
        masks = _built_masks(frames, built_threshold)
        areas = [_mask_area_km2(m, km_per_px) for m in masks]
        extras = [f'Built-up: {_fmt_area(a)}' for a in areas]
        csv_path = stem + '_built_area.csv'
        with open(csv_path, 'w') as fh:
            fh.write('label,start,end,hectares,km2,est_mw_at_2ha_per_mw\n')
            for lbl, (t0, t1), a in zip(labels, spans, areas):
                fh.write(f'{lbl},{t0},{t1},{a * 100:.0f},{a:.2f},'
                         f'{a * 100 / 2:.0f}\n')
        if verbose:
            print(f'wrote {csv_path}')

    if contrast != 1.0 or sharpen > 0:
        frames = [_enhance(f, contrast, sharpen) for f in frames]
    if masks:
        frames = [_draw_mask_outline(f, m) for f, m in zip(frames, masks)]
    if polys:
        frames = [_draw_polygons(f, polys, bounds) for f in frames]
    rendered = [_draw_panel(f, lbl, i, n, title, subtitle,
                            sensor['attribution'],
                            extras[i] if extras else None)
                for i, (f, lbl) in enumerate(zip(frames, labels))]
    if scale_bar:
        rendered = [_draw_scale_bar(f, 2 * rx) for f in rendered]

    pal = [f.convert('P', palette=Image.ADAPTIVE, colors=128)
           for f in rendered]
    durations = [int(1000 / fps)] * (n - 1) + [int(1000 / fps + hold * 1000)]
    pal[0].save(out, save_all=True, append_images=pal[1:],
                duration=durations, loop=0)
    if verbose:
        print(f'wrote {out} ({n} frames)')

    if frames_dir:
        os.makedirs(frames_dir, exist_ok=True)
        base = os.path.basename(stem)
        with open(os.path.join(frames_dir, base + '_frames.csv'), 'w') as fh:
            fh.write('index,file,label,start,end\n')
            for i, (f, lbl, (t0, t1)) in enumerate(zip(rendered, labels,
                                                       spans)):
                name = f'{base}_{i:02d}.png'
                f.save(os.path.join(frames_dir, name))
                fh.write(f'{i},{name},{lbl},{t0},{t1}\n')
        if verbose:
            print(f'wrote {n} frames to {frames_dir}/')

    if mp4 and shutil.which('ffmpeg'):
        mp4_path = os.path.splitext(out)[0] + '.mp4'
        _write_mp4(rendered, mp4_path, fps, hold)
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
                   title=args.title, scale_bar=args.scale_bar,
                   contrast=args.contrast, sharpen=args.sharpen,
                   built_area=args.built_area,
                   built_threshold=args.built_threshold,
                   polygons=args.polygons, frames_dir=args.frames_dir,
                   out=args.out, mp4=not args.no_mp4,
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
    g.add_argument('--scale-bar', action='store_true',
                   help='draw a distance scale bar in the lower-left corner')
    g.add_argument('--contrast', type=float, default=1.0,
                   help='contrast multiplier for the imagery; 1.0 = unchanged, '
                        '1.2-1.4 = punchier (default: 1.0)')
    g.add_argument('--sharpen', type=float, default=0.0,
                   help='unsharp-mask strength; 0 = off, 0.5-1.5 typical '
                        '(default: 0)')
    g.add_argument('--built-area', action='store_true',
                   help='outline the built-up area in each frame and put its '
                        'hectares in the legend and <out>_built_area.csv '
                        '(dark structures on bright ground, e.g. solar parks)')
    g.add_argument('--built-threshold', type=int, default=110,
                   metavar='0-255',
                   help='luminance below which a pixel counts as built for '
                        '--built-area (default 110)')
    g.add_argument('--polygons', default=None, metavar='FILE.geojson',
                   help='outline every polygon in this GeoJSON on each frame, '
                        "captioned with its 'name' and its area")
    g.add_argument('--frames-dir', default=None, metavar='DIR',
                   help='also save every rendered frame as a PNG here')
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
