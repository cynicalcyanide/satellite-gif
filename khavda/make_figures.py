#!/usr/bin/env python3
"""Regenerate every chart in the Khavda deck from khavda/data/*.csv.

Style: grey for everything, one accent (the XKDR theme orange) for the thing
the title is about, values on the marks, a source line under each chart,
short sentences. Output: khavda/deck/figures/fig_*.png (300 dpi, 16:9-ish).

    .venv/bin/python khavda/make_figures.py
"""
import csv
import os
from datetime import date

import matplotlib
matplotlib.use('Agg')
import matplotlib.pyplot as plt  # noqa: E402
from matplotlib import font_manager  # noqa: E402

HERE = os.path.dirname(os.path.abspath(__file__))
DATA = os.path.join(HERE, 'data')
OUT = os.path.join(HERE, 'deck', 'figures')
os.makedirs(OUT, exist_ok=True)

# ---- palette: the theme's SpOrange, plus greys ------------------------------
ACCENT = '#F27A69'
INK = '#1C1C1C'
INK2 = '#5A5A5A'
MUTED = '#8A8A8A'
GREY = '#C9C9C9'
GREY2 = '#E6E6E6'
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


def rows(name):
    with open(os.path.join(DATA, name)) as fh:
        return list(csv.DictReader(fh))


def frame(title, subtitle=None, source=None, size=(11, 5.4)):
    fig, ax = plt.subplots(figsize=size)
    fig.text(0.01, 0.985, title, ha='left', va='top', fontsize=16,
             fontweight='bold', color=INK)
    if subtitle:
        fig.text(0.01, 0.925, subtitle, ha='left', va='top', fontsize=11,
                 color=INK2)
    if source:
        fig.text(0.01, 0.005, source, ha='left', va='bottom', fontsize=8.5,
                 color=MUTED)
    for sp in ('top', 'right'):
        ax.spines[sp].set_visible(False)
    return fig, ax


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


# ---- 1. land by developer, 2020 vs 2026 ------------------------------------
def fig_land():
    r = rows('land_allotment_ha.csv')
    names = {'Adani Green Energy and group': 'Adani group',
             'NTPC Renewable Energy': 'NTPC',
             'Sarjan Realities': 'Sarjan Realities',
             'GSECL and tenants': 'GSECL and tenants',
             'GIPCL and tenants': 'GIPCL and tenants',
             'SECI (surrendered 2023)': 'SECI (surrendered 2023)'}
    r = sorted(r, key=lambda d: -int(d['hectares_2026']))
    fig, ax = frame(
        'Adani holds three-quarters of the park, more than everyone else '
        'combined',
        'Land held at Khavda, hectares. Grey: the 2020 allotment. '
        'Orange: late 2026, after SECI\'s parcel passed to Adani.',
        'Source: analysis note; AGEL FY25 financial statements (53,800 ha '
        'includes 9,500 ha leased from third parties); Scroll on the SECI '
        'parcel.')
    y = range(len(r))
    h = 0.36
    ax.barh([i + h / 2 for i in y], [int(d['hectares_2020']) for d in r],
            height=h, color=GREY, label='2020 allotment')
    ax.barh([i - h / 2 for i in y], [int(d['hectares_2026']) for d in r],
            height=h, color=[ACCENT if 'Adani' in d['developer'] else INK2
                             for d in r], label='Late 2026')
    for i, d in enumerate(r):
        a, b = int(d['hectares_2020']), int(d['hectares_2026'])
        ax.text(a + 600, i + h / 2, f'{a:,}', va='center', fontsize=9.5,
                color=INK2)
        ax.text(b + 600, i - h / 2, f'{b:,}' if b else 'returned',
                va='center', fontsize=9.5, color=INK, fontweight='bold')
    ax.set_yticks(list(y))
    ax.set_yticklabels([names[d['developer']] for d in r], fontsize=11)
    ax.invert_yaxis()
    strip(ax, x=True, y=False)
    ax.tick_params(axis='y', length=0)
    ax.set_xlim(0, 62000)
    ax.legend(loc='lower right', frameon=False, fontsize=9.5)
    fig.subplots_adjust(top=0.84, bottom=0.08, left=0.2, right=0.97)
    save(fig, 'fig_land_by_developer.png')


# ---- 2. milestone timeline --------------------------------------------------
def fig_timeline():
    r = rows('timeline_milestones.csv')
    short = {
        '2019-01-25': 'Wasteland policy',
        '2020-09-09': 'Land allotted to six developers',
        '2020-12-15': 'Foundation stone, 30 GW',
        '2021-12-31': 'Approach road done; clock starts',
        '2023-08-24': "SECI's parcel passes to Adani",
        '2024-02-01': 'First power: 551 MW',
        '2024-03-01': '1 GW running',
        '2024-07-01': 'First 250 MW of wind',
        '2025-08-01': 'Third grid station, KPS3',
        '2025-12-25': "GIPCL's 600 MW complete",
        '2026-03-31': '5.1 GW built in one year',
        '2026-05-13': 'Grid trip; 9 GW ceiling',
        '2026-10-01': '6.6 GWh of batteries',
    }
    pts = [(date.fromisoformat(d['date']), short[d['date']], d['act'])
           for d in r if d['date'] in short]
    fig, ax = frame(
        'Five years to prepare the land, then 10 GW in under three',
        'Milestones at Khavda, 2019 to 2026. Orange: building. '
        'The dashed line marks the first power.',
        'Source: company statements, the WRPC report, Scroll\'s RTI records. '
        'Data: timeline_milestones.csv', size=(11, 5.8))
    for i, (d, lbl, act) in enumerate(pts):
        c = ACCENT if act == 'Build' else GREY
        ax.plot([d], [i], marker='D', ms=9, color=c, mec='white', mew=0.8,
                zorder=3)
        ax.text(d, i, '   ' + d.strftime('%b %Y'), va='center', fontsize=9,
                color=INK2)
        ax.text(date(2018, 9, 1), i, lbl, va='center', ha='right',
                fontsize=10.5, color=INK,
                fontweight='bold' if 'First power' in lbl else 'normal')
    ax.axvline(date(2024, 2, 1), color=ACCENT, ls=(0, (3, 3)), lw=1)
    for yr in range(2019, 2028):
        ax.axvline(date(yr, 1, 1), color=GREY2, lw=0.8, zorder=0)
        ax.text(date(yr, 1, 1), -1.1, str(yr), ha='center', fontsize=9.5,
                color=INK2)
    ax.set_xlim(date(2018, 11, 1), date(2027, 6, 1))
    ax.set_ylim(len(pts) - 0.3, -1.6)
    strip(ax)
    fig.subplots_adjust(top=0.85, bottom=0.07, left=0.3, right=0.98)
    save(fig, 'fig_timeline.png')


# ---- 3. capacity by developer and status (CMIE) -----------------------------
def fig_capacity():
    r = rows('chart_capacity_by_developer.csv')
    devs = []
    data = {}
    for d in r:
        if d['developer'] not in devs:
            devs.append(d['developer'])
        data.setdefault(d['developer'], {})[d['status']] = int(d['mw'])
    fig, ax = frame(
        'Adani has built two-thirds of what is complete at Khavda, and holds '
        'most of the pipeline',
        'Generation capacity in MW from the CMIE CapEx extract: 12,248 '
        'completed, 19,357 under implementation.',
        'Source: CMIE CapEx, Nov 2026; 157 projects, 8 park-level umbrella '
        'records removed; generation only. Excludes 16,000 MW of multi-site '
        'announcements by Tata Power and Serentica.')
    cols = [('Completed', ACCENT), ('Under implementation', GREY),
            ('Announced', GREY2)]
    for i, dev in enumerate(devs):
        left = 0
        for st, c in cols:
            v = data[dev].get(st, 0)
            if v:
                ax.barh(i, v, left=left, color=c, height=0.6,
                        edgecolor='white', linewidth=1.5)
                if v >= 1500:
                    ax.text(left + v / 2, i, f'{v:,}', ha='center',
                            va='center', fontsize=9.5,
                            color='white' if c == ACCENT else INK)
                left += v
        ax.text(left + 250, i, f'{left:,}', va='center', fontsize=10,
                color=INK2)
    ax.set_yticks(range(len(devs)))
    ax.set_yticklabels(devs, fontsize=11)
    ax.invert_yaxis()
    strip(ax, x=True, y=False)
    ax.tick_params(axis='y', length=0)
    ax.set_xlim(0, 23500)
    from matplotlib.patches import Patch
    ax.legend([Patch(color=c) for _, c in cols], [s for s, _ in cols],
              loc='lower right', frameon=False, fontsize=9.5, ncol=3,
              bbox_to_anchor=(1, 1.0))
    fig.subplots_adjust(top=0.80, bottom=0.1, left=0.25, right=0.97)
    save(fig, 'fig_capacity_by_developer.png')


# ---- 4. corridor schematic -------------------------------------------------
def fig_corridors():
    nodes = {   # lon, lat (approximate; schematic)
        'Khavda\nKPS1-3': (69.35, 24.12), 'Bhuj': (69.67, 23.24),
        'Lakadia': (70.80, 23.33), 'Halvad': (71.18, 23.02),
        'Ahmedabad': (72.58, 23.03), 'Vadodara': (73.19, 22.31),
        'South Olpad\n(Surat)': (72.75, 21.33), 'Boisar\n(Mumbai)': (72.75, 19.80),
        'Pune': (73.86, 18.52), 'Nagpur': (79.09, 21.15)}
    K = 'Khavda\nKPS1-3'
    in_service = [(K, 'Bhuj', '765 kV, KPS1'), (K, 'Lakadia', '765 kV, KPS2')]
    building = [
        (K, 'Halvad', '765 kV; 229 of 690 towers blocked'),
        ('Ahmedabad', 'South Olpad\n(Surat)', '765 kV'),
        ('Vadodara', 'South Olpad\n(Surat)', '765 kV'),
        ('South Olpad\n(Surat)', 'Boisar\n(Mumbai)', '765 kV'),
        ('Boisar\n(Mumbai)', 'Pune', '765 kV'),
    ]
    hvdc = [(K, 'Nagpur', '6 GW HVDC, Power Grid, Rs 24,800 cr'),
            (K, 'South Olpad\n(Surat)', '2.5 GW HVDC, Adani, Rs 12,000 cr')]
    fig, ax = frame(
        'Two lines leave the park today; Rs 60,000 crore of lines are '
        'still being built',
        'Corridors out of Kutch. Solid: in service. Dashed: under '
        'construction. Orange: the two direct-current links.',
        'Schematic; positions approximate. Source: CTUIL minutes, CMIE '
        'transmission projects (transmission_projects_cmie.csv).',
        size=(11, 5.8))
    import math
    ax.set_aspect(1 / math.cos(math.radians(21.5)))

    def seg(a, b, **kw):
        (x0, y0), (x1, y1) = nodes[a], nodes[b]
        ax.plot([x0, x1], [y0, y1], **kw)
    for a, b, _ in in_service:
        seg(a, b, color=INK, lw=2.5, solid_capstyle='round', zorder=2)
    for a, b, _ in building:
        seg(a, b, color=INK2, lw=1.8, ls=(0, (4, 3)), zorder=2)
    for a, b, _ in hvdc:
        seg(a, b, color=ACCENT, lw=2.5, ls=(0, (5, 3)), zorder=2)
    for n, (x, y) in nodes.items():
        ax.plot(x, y, 'o', ms=9 if n == K else 7,
                color=ACCENT if n == K else 'white',
                mec=ACCENT if n == K else INK, mew=1.5, zorder=4)
        dx, dy = (0.25, 0.15)
        if n in ('Bhuj',):
            dx, dy = (-0.25, -0.35)
        if n == 'Pune':
            dx, dy = (0.25, -0.15)
        ax.text(x + dx, y + dy, n, fontsize=9.5, color=INK,
                ha='left' if dx > 0 else 'right', va='center',
                fontweight='bold' if n == K else 'normal', zorder=5)
    ax.text(76.2, 20.75, '6,000 MW HVDC to Nagpur\nRs 24,800 crore, four years',
            fontsize=8.5, color=ACCENT, ha='center', va='top')
    ax.text(70.9, 20.9, '2,500 MW HVDC to South Olpad\nRs 12,000 crore',
            fontsize=8.5, color=ACCENT, ha='center', va='top')
    ax.text(70.6, 24.3, 'KPS1 to Bhuj and KPS2 to Lakadia: the only two '
            'lines out, 9,000 MW cap', fontsize=8.5, color=INK, ha='left')
    ax.text(71.25, 22.75, 'to Halvad: late', fontsize=8.5, color=INK2,
            ha='left', va='top')
    ax.set_xlim(68.6, 80.2)
    ax.set_ylim(17.9, 24.9)
    strip(ax)
    fig.subplots_adjust(top=0.85, bottom=0.05, left=0.02, right=0.98)
    save(fig, 'fig_corridors.png')


# ---- 5. the 17 seconds of 13 May 2026 --------------------------------------
def fig_blackout():
    # The four key times are hand-placed below; the full event list is in
    # data/blackout_13may2026.csv.
    def secs(t):
        h, m, s = (int(x) for x in t.split(':'))
        return h * 3600 + m * 60 + s
    t0 = secs('14:09:20')
    fig, ax = frame(
        'Dark in 17 seconds: the voltage overshot and seventeen lines '
        'tripped',
        'The 765 kV system around Khavda on 13 May 2026. Orange: the '
        'recorded voltage. The park had been at its 8,963 MW ceiling '
        'since 14:00.',
        'Source: WRPC grid disturbance report on the Khavda event; the '
        'four earlier steps (fault near Indore 14:02:39, oscillation '
        '14:03:46, voltage dips from 14:05:40) are in the note. '
        'Data: blackout_13may2026.csv')
    ax.axhline(765, color=GREY, lw=1, ls=(0, (3, 3)))
    ax.text(secs('14:09:20') - t0, 768, '765 kV nominal', fontsize=9,
            color=INK2, va='bottom')
    volt = [(secs('14:09:31') - t0, 680, 'sags to 680 kV'),
            (secs('14:09:51') - t0, 894, 'peaks at 894 kV')]
    ax.plot([v[0] for v in volt], [v[1] for v in volt], color=ACCENT, lw=2,
            marker='o', ms=9, mec='white', zorder=3)
    for x, y, lbl in volt:
        ax.text(x, y + (14 if y > 765 else -14), lbl, ha='center',
                va='bottom' if y > 765 else 'top', fontsize=10, color=INK,
                fontweight='bold')
    events = [(11, 'Voltage sags for five seconds;\ninverters push reactive '
                   'power\n145 to 900 MVAr', 'right'),
              (26, 'First 765 kV line trips', 'center'),
              (31, 'About 2,931 MW trips\non over-voltage protection', 'left'),
              (42, '17 lines tripped;\nthe park is dark;\n'
                   'frequency 49.39 Hz', 'left')]
    for x, e, ha in events:
        ax.plot([x, x], [600, 640], color=INK2, lw=1)
        ax.text(x + (0.4 if ha == 'left' else -0.4 if ha == 'right' else 0),
                590, e, fontsize=8.5, color=INK2, ha=ha, va='top')
    ax.set_ylim(480, 940)
    ax.set_xlim(0, 50)
    ax.set_yticks([600, 700, 800, 900])
    ax.set_yticklabels(['600 kV', '700', '800', '900'])
    ticks = [11, 26, 31, 42]
    ax.set_xticks(ticks)
    ax.set_xticklabels(['14:09:31', '14:09:46', '14:09:51', '14:10:02'])
    ax.spines['left'].set_visible(False)
    ax.tick_params(axis='y', length=0)
    fig.subplots_adjust(top=0.82, bottom=0.12, left=0.07, right=0.98)
    save(fig, 'fig_blackout.png')


# ---- 6. batteries ----------------------------------------------------------
def fig_battery():
    r = [d for d in rows('battery_gwh.csv') if float(d['gwh_operational'])]
    labels = []
    for d in r:
        dt = date.fromisoformat(d['date'])
        labels.append('FY27 target' if dt.year == 2027
                      else dt.strftime('%b %Y'))
    vals = [float(d['gwh_operational']) for d in r]
    fig, ax = frame(
        'Adani doubled its batteries at Khavda in four months, to half of '
        "India's total",
        'Battery storage operating at Khavda, GWh. Light grey: the FY27 '
        'target of more than 10 GWh, Rs 15,000 crore.',
        'Source: WRPC report (May 2026), AGEL statements (Jun, Jul, Oct '
        '2026), AGEL FY27 guidance. Data: battery_gwh.csv')
    cols = [GREY2 if 'target' in l else ACCENT for l in labels]
    ax.bar(range(len(vals)), vals, color=cols, width=0.62)
    for i, v in enumerate(vals):
        ax.text(i, v + 0.15, f'{v:g}' if 'target' not in labels[i]
                else '>10', ha='center', fontsize=11, color=INK,
                fontweight='bold')
    ax.set_xticks(range(len(vals)))
    ax.set_xticklabels(labels, fontsize=10.5)
    strip(ax, x=False, y=True)
    ax.tick_params(axis='x', length=0)
    ax.set_ylim(0, 11.5)
    fig.subplots_adjust(top=0.82, bottom=0.1, left=0.04, right=0.98)
    save(fig, 'fig_battery.png')


# ---- 7. cost stack vs tariff ----------------------------------------------
def fig_cost():
    capex_per_mw = 6.5e7          # Rs
    cuf, rate, years = 0.33, 0.09, 25
    units = cuf * 8760 * 1000      # kWh per MW per year
    crf = rate / (1 - (1 + rate) ** -years)
    capital = capex_per_mw * crf / units
    om = 0.25
    land = 30000 / units
    tariff = 2.92
    fig, ax = frame(
        'A unit costs about Rs 2.5 to make and sells for Rs 2.92',
        'Rupees per kWh. Capital: Rs 6.5 crore per MW at 33% capacity '
        'factor, 9% over 25 years. Land rent: Rs 30,000 per MW a year.',
        'Source: CMIE cost convention; AGEL SECI manufacturing-linked '
        'tariff; analysis note. The Rs 6.5 crore is a filed convention, not '
        'an outturn.', size=(11, 4.6))
    parts = [('Capital', capital, ACCENT), ('Running costs', om, GREY),
             ('Land rent', land, INK2)]
    left = 0
    for lbl, v, c in parts:
        ax.barh(1, v, left=left, color=c, height=0.5, edgecolor='white',
                linewidth=1.5)
        if v > 1:
            ax.text(left + v / 2, 1, f'{lbl}\nRs {v:.2f}', ha='center',
                    va='center', fontsize=10, color='white')
        elif v > 0.1:
            ax.text(left + v / 2, 1.3, f'{lbl}\nRs {v:.2f}', ha='center',
                    va='bottom', fontsize=9.5, color=INK2)
        left += v
    ax.text(left + 0.04, 1, f'Rs {left:.2f} to make', va='center',
            fontsize=11, color=INK, fontweight='bold')
    ax.text(left + 0.04, 0.72, f'(land: under a paisa, Rs {land:.3f})',
            va='center', fontsize=8.5, color=INK2)
    ax.barh(0, tariff, color=INK, height=0.5)
    ax.text(tariff + 0.04, 0, f'Rs {tariff:.2f} tariff, SECI contract',
            va='center', fontsize=11, color=INK, fontweight='bold')
    ax.set_yticks([1, 0])
    ax.set_yticklabels(['Cost to make', 'Sale price'], fontsize=11)
    strip(ax, x=True, y=False)
    ax.tick_params(axis='y', length=0)
    ax.set_xlim(0, 4.2)
    ax.set_ylim(-0.6, 1.6)
    fig.subplots_adjust(top=0.78, bottom=0.1, left=0.12, right=0.98)
    save(fig, 'fig_cost_stack.png')


# ---- 8. build-out curve from the satellite frames (after make_frames.sh) --
def fig_buildout():
    path = os.path.join(HERE, 'deck', 'frames', 'khavda_built_area.csv')
    if not os.path.exists(path):
        print('skip fig_buildout: no', os.path.relpath(path, HERE),
              '(run khavda/make_frames.sh first)')
        return
    r = rows(os.path.relpath(path, DATA))
    ha = [int(d['hectares']) for d in r]
    lbl = [d['label'] for d in r]
    fig, ax = frame(
        'Built-up area measured from orbit, quarter by quarter',
        'Hectares of dark panel and turbine ground inside the scene, from '
        'Sentinel-2 composites. The MW figure assumes 2 ha per MW.',
        'Source: satgif --built-area on COPERNICUS/S2_SR_HARMONIZED. '
        'Monsoon quarters can under- or over-read; the threshold is a '
        'luminance cut, not a land-cover classification.')
    ax.plot(range(len(ha)), ha, color=ACCENT, lw=2.2, marker='o', ms=5,
            mec='white')
    for i in (len(ha) - 1,):
        ax.text(i, ha[i], f'  {ha[i]:,} ha\n  ≈ {ha[i] / 2:,.0f} MW',
                va='center', fontsize=10, color=INK, fontweight='bold')
    for x, text in ((lbl.index('Q1 2024'), 'First power\nFeb 2024'),
                    (lbl.index('Q3 2025'), 'KPS3 opens\nAug 2025')):
        ax.axvline(x, color=GREY, lw=1, ls=(0, (3, 3)))
        ax.text(x + 0.2, max(ha) * 0.95, text, fontsize=8.5, color=INK2,
                va='top')
    ax.set_xticks([i for i, l in enumerate(lbl) if l.startswith('Q1')])
    ax.set_xticklabels([l[-4:] for l in lbl if l.startswith('Q1')])
    ax.spines['left'].set_visible(False)
    ax.tick_params(axis='y', length=0)
    ax.yaxis.set_major_formatter(lambda v, _: f'{v:,.0f}')
    fig.subplots_adjust(top=0.82, bottom=0.1, left=0.08, right=0.95)
    save(fig, 'fig_buildout_curve.png')


if __name__ == '__main__':
    fig_land()
    fig_timeline()
    fig_capacity()
    fig_corridors()
    fig_blackout()
    fig_battery()
    fig_cost()
    fig_buildout()
