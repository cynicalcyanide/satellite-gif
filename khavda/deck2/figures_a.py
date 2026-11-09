#!/usr/bin/env python3
"""Five charts for the Khavda deck (deck2), set A.

    .venv/bin/python khavda/deck2/figures_a.py

Style follows khavda/make_figures.py: grey for everything, one accent for
the thing the title is about, values on the marks, a source line under
each chart, short sentences. Output: khavda/deck2/figures/fig*.png.
"""
import math
import os

import numpy as np
import matplotlib
matplotlib.use('Agg')
import matplotlib.pyplot as plt  # noqa: E402
from matplotlib import font_manager  # noqa: E402
from matplotlib.patches import Polygon, Patch, FancyArrowPatch  # noqa: E402

HERE = os.path.dirname(os.path.abspath(__file__))
OUT = os.path.join(HERE, 'figures')
os.makedirs(OUT, exist_ok=True)

# ---- palette: the theme's SpOrange, plus greys ------------------------------
ACCENT = '#F27A69'
INK = '#1C1C1C'
INK2 = '#5A5A5A'
MUTED = '#8A8A8A'
GREY = '#C9C9C9'
GREY2 = '#E6E6E6'
BLUE = '#4A6F8A'
BG = 'white'

for p in ('/usr/share/fonts/opentype/urw-base35/NimbusSans-Regular.otf',
          '/usr/share/fonts/opentype/urw-base35/NimbusSans-Bold.otf'):
    if os.path.exists(p):
        font_manager.fontManager.addfont(p)
plt.rcParams.update({
    'font.family': 'Nimbus Sans' if any(
        f.name == 'Nimbus Sans' for f in font_manager.fontManager.ttflist)
    else 'DejaVu Sans',
    'font.size': 11, 'axes.edgecolor': GREY, 'axes.linewidth': 0.8,
    'xtick.color': INK2, 'ytick.color': INK2, 'axes.labelcolor': INK2,
    'text.color': INK, 'figure.facecolor': BG, 'axes.facecolor': BG,
    'savefig.dpi': 300, 'savefig.bbox': 'tight', 'savefig.pad_inches': 0.15,
})


def frame(title, subtitle=None, source=None, size=(11, 5.4), ncols=1,
          title_size=16):
    """Figure with title (the finding), subtitle, source. Multi-line titles
    and subtitles are allowed; the subtitle moves down to make room."""
    fig, axes = plt.subplots(1, ncols, figsize=size)
    fig.text(0.01, 0.985, title, ha='left', va='top', fontsize=title_size,
             fontweight='bold', color=INK, linespacing=1.15)
    n_title = title.count('\n') + 1
    # line height in figure fraction
    th = n_title * title_size * 1.2 / 72 / size[1]
    if subtitle:
        fig.text(0.01, 0.985 - th - 0.012, subtitle, ha='left', va='top',
                 fontsize=11, color=INK2, linespacing=1.2)
    if source:
        fig.text(0.01, 0.005, source, ha='left', va='bottom', fontsize=8.5,
                 color=MUTED, linespacing=1.2)
    for ax in (axes if ncols > 1 else [axes]):
        for sp in ('top', 'right'):
            ax.spines[sp].set_visible(False)
    return fig, axes


def strip(ax, x=True, y=True):
    for sp in ('top', 'right', 'left', 'bottom'):
        ax.spines[sp].set_visible(False)
    if x:
        ax.set_xticks([])
    if y:
        ax.set_yticks([])


def save(fig, name):
    path = os.path.join(OUT, name)
    fig.savefig(path)
    plt.close(fig)
    print('wrote', os.path.relpath(path, HERE))


# ---- 1. rent: state lease vs private farmland ------------------------------
def fig04_rent():
    fig, ax = frame(
        'The state lease costs a fifth\nof private land nearby',
        'Annual rent, rupees per hectare.\n'
        'State rent escalates 10% every three years.',
        'Source: AGEL ESIA (lease terms); local lease accounts\n'
        'from Rapar taluka.', size=(5.6, 4.6), title_size=15)
    labels = ['Khavda state lease', 'Private arid farmland,\nRapar taluka']
    vals = [15000, 86400]
    ax.bar([0, 1], vals, color=[ACCENT, GREY], width=0.55)
    ax.errorbar(1, 86400, yerr=[[86400 - 74000], [98800 - 86400]],
                fmt='none', ecolor=INK2, elinewidth=1, capsize=6,
                capthick=1, zorder=3)
    ax.text(0, 15000 + 2000, 'Rs 15,000', ha='center', va='bottom',
            fontsize=11, color=INK, fontweight='bold')
    ax.text(1, 98800 + 2000, 'Rs 74,000 to 98,800', ha='center',
            va='bottom', fontsize=11, color=INK, fontweight='bold')
    ax.set_xticks([0, 1])
    ax.set_xticklabels(labels, fontsize=10.5)
    ax.set_xlim(-0.55, 1.55)
    ax.set_ylim(0, 112000)
    strip(ax, x=False, y=True)
    ax.tick_params(axis='x', length=0)
    fig.subplots_adjust(top=0.72, bottom=0.17, left=0.05, right=0.97)
    save(fig, 'fig04_rent.png')


# ---- 2. land share ---------------------------------------------------------
def fig06_land_share():
    data = [('Adani group', 44500), ('NTPC Renewable Energy', 9500),
            ('Sarjan Realities', 9500), ('GSECL and tenants', 6650),
            ('GIPCL and tenants', 4750)]
    data.sort(key=lambda d: -d[1])
    total = 74900
    fig, ax = frame(
        'Adani holds more land than everyone else combined',
        "Hectares allotted, after SECI's 23,000 ha parcel passed to Adani "
        'in 2023.',
        'Source: analysis note; Scroll (RTI records). AGEL reports 53,800 ha\n'
        'including 9,500 ha leased from third parties.',
        size=(6.2, 4.6), title_size=15)
    y = list(range(len(data)))
    ax.barh(y, [v for _, v in data], height=0.62,
            color=[ACCENT if 'Adani' in n else INK2 for n, _ in data])
    for i, (n, v) in enumerate(data):
        ax.text(v + 700, i, f'{v:,} ha, {v / total:.0%}', va='center',
                fontsize=10, color=INK,
                fontweight='bold' if 'Adani' in n else 'normal')
    ax.set_yticks(y)
    ax.set_yticklabels([n for n, _ in data], fontsize=10.5)
    ax.invert_yaxis()
    strip(ax, x=True, y=False)
    ax.tick_params(axis='y', length=0)
    ax.set_xlim(0, 58000)
    fig.subplots_adjust(top=0.80, bottom=0.12, left=0.33, right=0.97)
    save(fig, 'fig06_land_share.png')


# ---- 3. resource map -------------------------------------------------------
def fig09_resource_map():
    fig, ax = frame(
        'Sun by day, sea wind by night, flat state land in between',
        'Schematic; positions approximate.',
        'Source: AGEL project page; analysis note.', size=(11, 5.2))
    ax.set_aspect(1 / math.cos(math.radians(23.5)))
    SEA = '#DCE6EC'
    # Arabian Sea: south-west of the line (68.5,23.9)-(69.3,22.6)-(70.2,22.6)
    # -(71.0,21.0)
    sea = [(68.5, 23.9), (69.3, 22.6), (70.2, 22.6), (71.0, 21.0),
           (71.0, 19.5), (65.0, 19.5), (65.0, 23.9)]
    ax.add_patch(Polygon(sea, closed=True, facecolor=SEA, edgecolor='none',
                         zorder=0))
    ax.text(66.9, 23.45, 'Arabian Sea', fontsize=11, color=BLUE,
            style='italic', ha='left', va='center', zorder=1)
    # Great Rann: very light grey around Khavda
    rann = [(68.9, 23.9), (69.9, 23.9), (69.9, 24.3), (68.9, 24.3)]
    ax.add_patch(Polygon(rann, closed=True, facecolor='#F2F2F2',
                         edgecolor='none', zorder=0))
    ax.text(69.9, 23.86, 'Great Rann of Kutch, salt flats', fontsize=9,
            color=MUTED, style='italic', ha='right', va='top', zorder=1)
    # Pakistan border
    ax.plot([68.7, 69.6], [24.33, 24.33], color=INK, lw=1.2, ls=(0, (5, 3)),
            zorder=2)
    ax.text(68.68, 24.36, 'Pakistan border', fontsize=9, color=INK,
            ha='left', va='bottom', zorder=3)

    # points
    ax.plot(69.35, 24.12, 'o', ms=16, color=ACCENT, mec='white', mew=1.5,
            zorder=5)
    ax.text(69.47, 24.12, 'Khavda park, 24.12 N 69.35 E', fontsize=11,
            fontweight='bold', color=INK, ha='left', va='center', zorder=6)
    ax.plot(69.30, 24.30, 'o', ms=5, color=INK2, mec='white', mew=0.8,
            zorder=5)
    ax.text(69.26, 24.25, 'Vighakot', fontsize=8.5, color=INK2,
            ha='right', va='center', zorder=6)
    for lon, lat, lbl in ((69.67, 23.24, 'Bhuj, 125 km'),
                          (69.72, 22.84, 'Mundra: panels, turbines')):
        ax.plot(lon, lat, 'o', ms=8, color='white', mec=INK, mew=1.5,
                zorder=5)
        ax.text(lon + 0.1, lat, lbl, fontsize=10, color=INK, ha='left',
                va='center', zorder=6)

    # wind arrows from the south-west sea towards Khavda
    dx, dy = 0.62, 0.85            # direction, roughly NE
    px, py = 0.38, -0.28           # offset between arrows
    for k in range(0, 5):
        x0, y0 = 67.4 + k * px, 22.95 + k * py
        ax.add_patch(FancyArrowPatch(
            (x0, y0), (x0 + dx, y0 + dy), arrowstyle='-|>',
            mutation_scale=16, color=BLUE, lw=2.0, zorder=3, alpha=0.9))
    ax.text(66.85, 22.25, 'Marine wind, 8 m/s mean,\nstrongest 20:00 to 06:00',
            fontsize=10, color=BLUE, ha='left', va='top', zorder=4,
            fontweight='bold')
    ax.text(68.95, 23.58, 'about 150 km from the sea', fontsize=9,
            color=INK2, ha='left', va='center', zorder=4)

    # sun glyph, top right
    sx, sy = 71.55, 24.25
    ax.plot(sx, sy, 'o', ms=26, color=ACCENT, mec='none', zorder=4)
    for a in range(0, 360, 30):
        r = math.radians(a)
        ax.plot([sx + 0.17 * math.cos(r), sx + 0.28 * math.cos(r)],
                [sy + 0.185 * math.sin(r), sy + 0.30 * math.sin(r)],
                color=ACCENT, lw=2, solid_capstyle='round', zorder=4)
    ax.text(sx, sy - 0.40, '2,060 kWh/m²/yr, 300+ clear days,\nsecond only '
            'to Ladakh', fontsize=10, color=ACCENT, ha='center', va='top',
            fontweight='bold', zorder=4)

    ax.set_xlim(66.7, 72.5)
    ax.set_ylim(21.85, 24.6)
    strip(ax)
    fig.subplots_adjust(top=0.86, bottom=0.05, left=0.01, right=0.99)
    save(fig, 'fig09_resource_map.png')


# ---- 4. diurnal profile ----------------------------------------------------
def fig12_diurnal():
    t = np.linspace(0, 24, 721)

    # cosine ramps 06:30-10:00 and 16:00-18:30, gentle bump on the plateau
    solar = np.zeros_like(t)
    up = (t >= 6.5) & (t < 10)
    solar[up] = 93 * 0.5 * (1 - np.cos(np.pi * (t[up] - 6.5) / 3.5))
    top = (t >= 10) & (t <= 16)
    solar[top] = 96 - 3 * np.cos(2 * np.pi * (t[top] - 10) / 6)
    dn = (t > 16) & (t <= 18.5)
    solar[dn] = 93 * 0.5 * (1 + np.cos(np.pi * (t[dn] - 16) / 2.5))
    wind = 72 - 42 * np.exp(-((t - 14.2) / 3.4) ** 2) \
        + 4 * np.cos((t - 1) / 24 * 2 * np.pi)
    hybrid = solar + wind
    fig, ax = frame(
        'Solar carries the day, sea wind carries the night',
        'Stylised daily output profile, percent of installed capacity.',
        'Source: analysis note; AGEL CUF guidance (33% solar, 35%+ wind).',
        size=(11, 5.0))
    ax.fill_between(t, 0, wind, color=BLUE, alpha=0.85, lw=0, label='Wind')
    ax.fill_between(t, wind, hybrid, color=ACCENT, alpha=0.85, lw=0,
                    label='Solar')
    ax.plot(t, hybrid, color=INK, lw=2, label='Combined hybrid')
    ax.text(13, 85, 'Solar plateau,\ntrackers + 1.35x DC overload',
            ha='center', va='center', fontsize=10.5, color='white',
            fontweight='bold')
    ax.text(2.6, 33, 'Night wind,\n60 to 80%', ha='center', va='center',
            fontsize=10.5, color='white', fontweight='bold')
    ax.text(21.5, 33, 'Night wind,\n60 to 80%', ha='center', va='center',
            fontsize=10.5, color='white', fontweight='bold')
    # CUF annotation with a bracket over the day
    ax.annotate('', xy=(0.15, 158), xytext=(23.85, 158),
                arrowprops=dict(arrowstyle='|-|', color=INK2, lw=1,
                                mutation_scale=4))
    ax.text(12, 162, 'Combined hybrid CUF 38 to 42% against 33% solar alone',
            ha='center', va='bottom', fontsize=10.5, color=INK,
            fontweight='bold')
    ax.set_xlim(0, 24)
    ax.set_ylim(0, 180)
    ax.set_xticks(range(0, 25, 3))
    ax.set_xticklabels([f'{h:02d}:00' for h in range(0, 25, 3)],
                       fontsize=10)
    ax.set_yticks([0, 25, 50, 75, 100, 125])
    ax.set_yticklabels(['0', '25', '50', '75', '100', '125%'], fontsize=10)
    ax.spines['left'].set_visible(False)
    ax.tick_params(axis='y', length=0)
    ax.tick_params(axis='x', length=3, color=GREY)
    ax.legend([Patch(color=ACCENT, alpha=0.85), Patch(color=BLUE, alpha=0.85)],
              ['Solar', 'Wind'], loc='upper left', frameon=False,
              fontsize=10, bbox_to_anchor=(0.0, 0.84))
    fig.subplots_adjust(top=0.84, bottom=0.11, left=0.05, right=0.98)
    save(fig, 'fig12_diurnal.png')


# ---- 5. two clocks ---------------------------------------------------------
def fig16_two_clocks():
    periods = ['Before FY27', 'FY 2026-27', 'FY 2027-28',
               'FY 2028-29\nand later']
    mw = [16505, 7301, 3276, 5667]
    ckm = [0, 1303, 644, 4350]
    mva = ['0 MVA', '19,000 MVA', '4,500 MVA', '21,500 MVA']
    fig, (a, b) = frame(
        'The panels are scheduled years before the wires: the two clocks '
        "in CMIE's data",
        'Khavda generation versus Phase IV-V transmission by scheduled '
        'completion, from the CMIE CapEx extract.',
        'Source: CMIE CapEx, Nov 2026; 157 Khavda projects.',
        size=(11, 5.2), ncols=2, title_size=15)
    x = range(4)
    # panel A: generation
    a.bar(x, mw, color=ACCENT, width=0.62)
    for i, v in enumerate(mw):
        a.text(i, v + 300, f'{v:,}', ha='center', va='bottom', fontsize=11,
               color=INK, fontweight='bold')
    a.set_title('Generation, MW scheduled', fontsize=12, fontweight='bold',
                loc='left', color=INK, pad=10)
    a.set_ylim(0, 19500)
    # panel B: transmission
    b.bar(x, ckm, color=INK2, width=0.62)
    for i, v in enumerate(ckm):
        b.text(i, v + 80, f'{v:,}' + (' ckm' if v else ''), ha='center',
               va='bottom', fontsize=11, color=INK, fontweight='bold')
        b.text(i, v + 80 + 360, mva[i], ha='center', va='bottom',
               fontsize=9, color=INK2)
    b.set_title('Transmission, circuit-km scheduled', fontsize=12,
                fontweight='bold', loc='left', color=INK, pad=10)
    b.set_ylim(0, 5600)
    b.annotate('73% of all new lines\narrive after March 2028',
               xy=(2.69, 3200), xytext=(1.5, 3900), fontsize=10, color=INK,
               ha='center', va='center',
               arrowprops=dict(arrowstyle='-', color=INK2, lw=0.9,
                               shrinkA=4, shrinkB=2))
    for ax in (a, b):
        ax.set_xticks(list(x))
        ax.set_xticklabels(periods, fontsize=10)
        strip(ax, x=False, y=True)
        ax.tick_params(axis='x', length=0)
    fig.subplots_adjust(top=0.74, bottom=0.12, left=0.03, right=0.98,
                        wspace=0.12)
    save(fig, 'fig16_two_clocks.png')


if __name__ == '__main__':
    fig04_rent()
    fig06_land_share()
    fig09_resource_map()
    fig12_diurnal()
    fig16_two_clocks()
