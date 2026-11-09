#!/usr/bin/env python3
"""Five more charts for the Khavda deck: developers, IEX + BESS,
IRR, transmission map, blackout telemetry.

Style follows khavda/make_figures.py: grey for everything, one accent for
the thing the title is about, values on the marks, a source line under
each chart. Output: khavda/deck/figures/fig*.png (300 dpi).

    .venv/bin/python khavda/deck/figures_b.py
"""
import math
import os

import matplotlib
matplotlib.use('Agg')
import matplotlib.pyplot as plt  # noqa: E402
import numpy as np  # noqa: E402
from matplotlib import font_manager  # noqa: E402
from matplotlib.lines import Line2D  # noqa: E402
from matplotlib.patches import Patch  # noqa: E402

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


def frame(title, subtitle=None, source=None, size=(11, 5.4), nax=1,
          ratios=None, left=0.07, right=0.97, bottom=0.12, hspace=0.12,
          gap=0.2):
    """Figure with title / subtitle / source and `nax` stacked axes.

    Title and subtitle may contain newlines; the axes block starts `gap`
    inches under the subtitle. Returns (fig, ax) or (fig, [axes]).
    """
    fig = plt.figure(figsize=size)
    w, h = size
    tsize = 16 if w >= 8 else 15
    y = 0.985
    fig.text(0.01, y, title, ha='left', va='top', fontsize=tsize,
             fontweight='bold', color=INK)
    y -= (title.count('\n') + 1) * tsize * 1.3 / 72 / h + 0.08 / h
    if subtitle:
        fig.text(0.01, y, subtitle, ha='left', va='top', fontsize=11,
                 color=INK2)
        y -= (subtitle.count('\n') + 1) * 11 * 1.3 / 72 / h
    if source:
        fig.text(0.01, 0.005, source, ha='left', va='bottom', fontsize=8.5,
                 color=MUTED)
    top = y - gap / h
    gs = fig.add_gridspec(nax, 1, height_ratios=ratios, top=top,
                          bottom=bottom, left=left, right=right,
                          hspace=hspace)
    axes = [fig.add_subplot(gs[i]) for i in range(nax)]
    for ax in axes:
        for sp in ('top', 'right'):
            ax.spines[sp].set_visible(False)
    return (fig, axes[0]) if nax == 1 else (fig, axes)


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


# ---- 17. capacity by developer group (CMIE) ---------------------------------
def fig17_developers():
    rows = [('Adani Green and group SPVs', 8193, 11068),
            ('NTPC Renewable Energy', 2455, 2679),
            ('GSECL sub-park tenants', 1000, 1900),
            ('GIPCL and sub-park tenants', 600, 1600)]
    fig, ax = frame(
        'Adani has built two-thirds of what is complete, and holds most of '
        'what is under way',
        'Generation capacity at Khavda, MW, from the CMIE CapEx extract '
        '(umbrella records removed).',
        'Source: CMIE CapEx, Nov 2026. GSECL tenants: SAEL 800, KPI Green '
        '200 done; NLC, SJVN, JSW, NHPC, Enren-II building. GIPCL: own 600 '
        'done; SJVN, SAEL, Coal India, NHPC building.',
        size=(11, 4.8), left=0.235, right=0.97, bottom=0.1, gap=0.3)
    cols = [('Completed', ACCENT), ('Under implementation', GREY)]
    for i, (dev, done, build) in enumerate(rows):
        left = 0
        for (st, c), v in zip(cols, (done, build)):
            ax.barh(i, v, left=left, color=c, height=0.62,
                    edgecolor='white', linewidth=1.5)
            if v >= 1000:
                ax.text(left + v / 2, i, f'{v:,}', ha='center', va='center',
                        fontsize=9.5 if v >= 1500 else 8.5,
                        color='white' if c == ACCENT else INK)
            left += v
        ax.text(left + 220, i, f'{left:,}', va='center', fontsize=10.5,
                color=INK, fontweight='bold')
    ax.set_yticks(range(len(rows)))
    ax.set_yticklabels([r[0] for r in rows], fontsize=11)
    ax.invert_yaxis()
    strip(ax, x=True, y=False)
    ax.tick_params(axis='y', length=0)
    ax.set_xlim(0, 21500)
    ax.legend([Patch(color=c) for _, c in cols], [s for s, _ in cols],
              loc='lower right', frameon=False, fontsize=9.5, ncol=2,
              bbox_to_anchor=(1, 1.0), borderaxespad=0)
    save(fig, 'fig17_developers.png')


# ---- 19. IEX day-ahead price and battery dispatch --------------------------
def fig19_iex_bess():
    fig, (ax1, ax2) = frame(
        'Charge at noon when the line is full, sell at 8 pm when the price '
        'hits the ceiling',
        'Stylised day-ahead exchange price and battery dispatch; 6.63 GWh '
        'operating at Khavda in October 2026.',
        'Source: IEX ceiling and AGEL BESS statements; curve shape is '
        'illustrative.',
        size=(11, 5.4), nax=2, ratios=[2.1, 1], left=0.075, right=0.98,
        bottom=0.11, hspace=0.1)
    # price curve: control points, dense linear interpolation, light smoothing
    kx = [0, 2, 4, 6, 8, 9.5, 10.5, 11.5, 13, 14.5, 15.5, 17, 18, 18.8,
          19.4, 22, 22.6, 23.3, 24]
    ky = [4.9, 4.4, 4.2, 4.6, 3.9, 3.0, 2.3, 2.02, 1.98, 2.05, 2.4, 3.9,
          6.5, 9.3, 10, 10, 8.4, 6.3, 5.0]
    x = np.linspace(0, 24, 961)
    y = np.interp(x, kx, ky)
    kern = np.ones(25) / 25
    ypad = np.concatenate([np.full(12, y[0]), y, np.full(12, y[-1])])
    y = np.convolve(ypad, kern, mode='valid')
    y = np.minimum(y, 10.0)
    ax1.plot(x, y, color=INK, lw=2, solid_capstyle='round', zorder=3)
    ax1.axhline(10, color=MUTED, lw=1, ls=(0, (4, 3)), zorder=1)
    ax1.text(0.25, 10.2, 'IEX price ceiling, Rs 10/kWh', fontsize=9.5,
             color=INK2, va='bottom')
    ax1.plot(12.6, 2.0, 'o', ms=7, color=INK, mec='white', mew=1.2, zorder=4)
    ax1.text(12.6, 1.55, 'Solar noon, Rs 2/kWh', fontsize=9.5, color=INK,
             ha='center', va='top', fontweight='bold')
    ax1.text(20.5, 9.55, 'Rs 10 plateau,\n19:00 to 22:00', fontsize=9,
             color=INK2, ha='center', va='top')
    ax1.text(0.25, 5.2, 'about Rs 4 to 5 overnight', fontsize=9,
             color=INK2, va='bottom')
    ax1.set_ylim(0, 11.6)
    ax1.set_yticks([0, 2, 4, 6, 8, 10])
    ax1.set_ylabel('Rs per kWh', fontsize=10)
    ax1.spines['left'].set_visible(False)
    ax1.tick_params(axis='y', length=0)
    ax1.tick_params(axis='x', labelbottom=False, length=0)
    ax1.grid(axis='y', color=GREY2, lw=0.6, zorder=0)
    # battery dispatch
    ch = [11, 12, 13, 14]
    dis = [19, 20, 21]
    ax2.bar(ch, [-250] * 4, width=1, align='edge', color=BLUE,
            edgecolor='white', linewidth=1.5, zorder=3)
    ax2.bar(dis, [330] * 3, width=1, align='edge', color=ACCENT,
            edgecolor='white', linewidth=1.5, zorder=3)
    ax2.axhline(0, color=GREY, lw=0.8, zorder=2)
    ax2.text(11.5, -235, '-250 MW', fontsize=8, color='white', ha='center',
             va='bottom', rotation=90)
    ax2.text(19.5, 315, '+330 MW', fontsize=8, color='white', ha='center',
             va='top', rotation=90)
    ax2.text(15.3, -140, 'Charging: otherwise-curtailed midday solar',
             fontsize=9.5, color=BLUE, ha='left', va='center')
    ax2.text(18.7, 180, 'Discharging into the evening peak', fontsize=9.5,
             color=ACCENT, ha='right', va='center')
    ax2.set_ylim(-330, 420)
    ax2.set_yticks([-250, 0, 330])
    ax2.set_yticklabels(['-250', '0', '330'])
    ax2.set_ylabel('BESS, MW\n(stylised)', fontsize=10)
    ax2.spines['left'].set_visible(False)
    ax2.spines['bottom'].set_visible(False)
    ax2.tick_params(axis='y', length=0)
    for ax in (ax1, ax2):
        ax.set_xlim(0, 24)
    ax2.set_xticks(range(0, 25, 3))
    ax2.set_xticklabels([f'{h:02d}:00' for h in range(0, 25, 3)])
    ax2.tick_params(axis='x', length=0)
    save(fig, 'fig19_iex_bess.png')


# ---- 20. equity IRR by structure -------------------------------------------
def fig20_irr():
    bars = [('Flat Rs 2.70 PPA,\nsolar + BESS', 10.1, GREY, '10.1%'),
            ('Pure solar,\nPPA only', 15.9, GREY, '15.9%'),
            ('Split PPA + IEX\nevening arbitrage', 15.4, INK2, '15.4%'),
            ('Conglomerate: EPC\nmargin + 50% farm-down', 21.5, ACCENT,
             '21.5%+')]
    fig, ax = frame(
        'The SPV alone earns 15%;\nthe group earns 21% or more',
        'Modelled equity IRR for a 1 GW AC solar + 500 MWh battery SPV,\n'
        'Rs 5,350 crore capex, 75:25 debt.',
        'Source: Analysis note project-finance model; illustrative.',
        size=(6.2, 4.8), left=0.04, right=0.99, bottom=0.17, gap=0.15)
    xs = range(len(bars))
    ax.bar(xs, [b[1] for b in bars], color=[b[2] for b in bars], width=0.62,
           zorder=3)
    for i, (_, v, c, lbl) in enumerate(bars):
        ax.text(i, v + 0.5, lbl, ha='center', va='bottom', fontsize=11,
                color=INK, fontweight='bold')
    ax.axhline(12, color=MUTED, lw=1, ls=(0, (4, 3)), zorder=2)
    ax.text(-0.55, 12.7, 'typical hurdle', fontsize=9, color=INK2, ha='left',
            va='bottom')
    ax.set_xticks(list(xs))
    ax.set_xticklabels([b[0] for b in bars], fontsize=9)
    strip(ax, x=False, y=True)
    ax.tick_params(axis='x', length=0)
    ax.set_xlim(-0.6, 3.55)
    ax.set_ylim(0, 25)
    save(fig, 'fig20_irr.png')


# ---- 22. evacuation network schematic --------------------------------------
def fig22_transmission_map():
    nodes = {   # lon, lat (approximate; schematic)
        'K': (69.35, 24.12), 'Bhuj': (69.67, 23.24), 'Lakadia': (70.80, 23.33),
        'Halvad': (71.18, 23.02), 'Ahmedabad': (72.58, 23.03),
        'Vadodara': (73.19, 22.31), 'Olpad': (72.75, 21.33),
        'Boisar': (72.75, 19.80), 'Pune': (73.86, 18.52),
        'Nagpur': (79.09, 21.15)}
    fig, ax = frame(
        'Two lines out today; a Rs 55,552 crore spine still to come',
        'Evacuation corridors from Khavda. Solid: in service (9,000 MW '
        'ceiling). Dashed: under construction.',
        'Source: CTUIL minutes; CMIE CapEx transmission projects; '
        'schematic, positions approximate.',
        size=(10.5, 6.2), left=0.02, right=0.98, bottom=0.05, gap=0.1)
    ax.set_aspect(1 / math.cos(math.radians(21.5)))

    def seg(a, b, bow=0.0, **kw):
        """Straight line, or a quadratic curve bowed `bow` degrees north."""
        (x0, y0), (x1, y1) = nodes[a], nodes[b]
        t = np.linspace(0, 1, 80)
        x = x0 + (x1 - x0) * t
        y = y0 + (y1 - y0) * t + 4 * bow * t * (1 - t)
        ax.plot(x, y, **kw)
    S_IN = dict(color=INK, lw=2.5, solid_capstyle='round', zorder=2)
    S_P3 = dict(color=INK2, lw=1.8, ls=(0, (4, 3)), zorder=2)
    S_P4 = dict(color=INK2, lw=1.8, ls=(0, (1.5, 2.5)), zorder=2)
    S_P5 = dict(color=ACCENT, lw=2.5, ls=(0, (5, 3)), zorder=2)
    seg('K', 'Bhuj', **S_IN)
    seg('K', 'Lakadia', **S_IN)
    seg('K', 'Halvad', bow=-0.17, **S_P3)
    seg('K', 'Lakadia', bow=0.13, **S_P4)
    seg('Ahmedabad', 'Olpad', **S_P4)
    seg('Vadodara', 'Olpad', **S_P4)
    seg('Olpad', 'Boisar', **S_P4)
    seg('Boisar', 'Pune', **S_P4)
    seg('K', 'Nagpur', bow=0.6, **S_P5)
    seg('K', 'Olpad', bow=-0.28, **S_P5)
    labels = {  # node: (text, dx, dy, ha, va)
        'K': ('Khavda\nKPS1, KPS2, KPS3', 0, 0.17, 'center', 'bottom'),
        'Bhuj': ('Bhuj', 0, -0.14, 'center', 'top'),
        'Lakadia': ('Lakadia', 0.12, 0.1, 'left', 'bottom'),
        'Halvad': ('Halvad', 0.2, -0.02, 'left', 'center'),
        'Ahmedabad': ('Ahmedabad', 0.2, 0.03, 'left', 'center'),
        'Vadodara': ('Vadodara', 0.2, 0, 'left', 'center'),
        'Olpad': ('South Olpad (Surat)', 0.2, 0, 'left', 'center'),
        'Boisar': ('Boisar-II (Mumbai)', 0.2, 0.02, 'left', 'center'),
        'Pune': ('Pune-III', 0.2, -0.05, 'left', 'center'),
        'Nagpur': ('Nagpur', 0.2, 0, 'left', 'center')}
    for n, (x, y) in nodes.items():
        ax.plot(x, y, 'o', ms=11 if n == 'K' else 7,
                color=ACCENT if n == 'K' else 'white',
                mec=ACCENT if n == 'K' else INK, mew=1.5, zorder=4)
        txt, dx, dy, ha, va = labels[n]
        ax.text(x + dx, y + dy, txt, fontsize=9.5, color=INK, ha=ha, va=va,
                fontweight='bold' if n == 'K' else 'normal', zorder=5)
    # line annotations
    ax.text(70.55, 24.95,
            'In service, 765 kV: KPS1 to Bhuj, 107 km; KPS2 to Lakadia, '
            '170 km. Together capped at 9,000 MW.\n'
            'Phase III, delayed: KPS2 to Halvad, 492 ckm; 229 of 690 '
            'towers blocked by land disputes.\n'
            'Phase IV, 765 kV AC: KPS3 to Lakadia, 404 ckm, plus the '
            'Ahmedabad and Vadodara to South Olpad, Boisar, Pune ring.',
            fontsize=8.5, color=INK2, ha='left', va='top', linespacing=1.45)
    ax.text(76.6, 21.6, 'Phase V: KPS2 to Nagpur\n'
            '±800 kV, 6,000 MW LCC HVDC\n2,409 ckm, Rs 24,819 crore',
            fontsize=8.5, color=ACCENT, ha='center', va='top',
            linespacing=1.4)
    ax.text(71.45, 21.75, 'Phase V: KPS3 to South Olpad\n'
            '±500 kV, 2,500 MW VSC HVDC\n1,157 ckm, Rs 12,000 crore',
            fontsize=8.5, color=ACCENT, ha='right', va='center',
            linespacing=1.4)
    handles = [Line2D([], [], **{k: v for k, v in s.items()
                                 if k not in ('zorder', 'solid_capstyle')})
               for s in (S_IN, S_P3, S_P4, S_P5)]
    ax.legend(handles, ['In service (Phase I and II)', 'Phase III, delayed',
                        'Phase IV, 765 kV AC', 'Phase V, HVDC'],
              loc='lower left', frameon=False, fontsize=9,
              bbox_to_anchor=(0.0, 0.0), handlelength=3.2)
    ax.set_xlim(68.6, 80.3)
    ax.set_ylim(17.9, 25.2)
    strip(ax)
    save(fig, 'fig22_transmission_map.png')


# ---- 23. the 13 May 2026 blackout, reconstructed traces --------------------
def fig23_telemetry():
    def secs(t):
        h, m, s = (int(v) for v in t.split(':'))
        return (h - 14) * 3600 + m * 60 + s
    ev = [('14:02:39', 'fault near\nIndore (LVRT)'),
          ('14:03:46', 'oscillation'), ('14:05:40', 'first dip'),
          ('14:09:31', 'sag'), ('14:09:51', 'peak'), ('14:10:02', 'blackout')]
    T = {t: secs(t) for t, _ in ev}
    t_osc, t_sag, t_peak, t_dark = (T['14:03:46'], T['14:09:31'],
                                    T['14:09:51'], T['14:10:02'])
    fig, (a1, a2, a3) = frame(
        'Dark in 17 seconds: reactive power overshoot in a weak grid',
        'Reconstructed from the WRPC event sequence of 13 May 2026; shapes '
        'between events are schematic.',
        'Source: WRPC grid disturbance report, Khavda, 13 May 2026.',
        size=(11, 5.6), nax=3, ratios=[1.5, 1, 1], left=0.1, right=0.98,
        bottom=0.145, hspace=0.18, gap=0.5)
    # -- voltage
    t = np.linspace(0, t_sag, 4000)
    v = np.full_like(t, 765.0)
    m = t >= t_osc
    v[m] += 10 * np.sin(2 * np.pi * 0.458 * (t[m] - t_osc))
    t2 = [t_sag, t_sag + 0.3, t_sag + 5, t_sag + 5.3, t_peak - 0.5, t_peak,
          t_peak + 2, t_dark, t_dark + 0.1, 630]
    v2 = [765, 680, 680, 760, 870, 894, 894, 894, 0, 0]
    a1.plot(np.concatenate([t, t2]), np.concatenate([v, v2]), color=ACCENT,
            lw=1.6, zorder=3)
    a1.plot([t_sag + 0.3, t_peak], [680, 894], 'o', ms=6, color=ACCENT,
            mec='white', mew=1, zorder=4)
    a1.text(t_sag - 6, 672, '680 kV', fontsize=9, color=INK, ha='right',
            va='center', fontweight='bold')
    a1.text(t_sag - 6, 900, '894 kV', fontsize=9, color=INK, ha='right',
            va='center', fontweight='bold')
    a1.text((t_osc + t_sag) / 2, 810,
            '0.458 Hz oscillation, 20 kV p-p on 400 kV bus', fontsize=9,
            color=INK2, ha='center', va='bottom')
    a1.text(8, 740, '765 kV nominal', fontsize=9, color=INK2, va='top')
    a1.set_ylim(0, 1000)
    a1.set_yticks([0, 250, 500, 750, 1000])
    a1.set_ylabel('765 kV bus\nvoltage, kV', fontsize=10)
    # -- reactive power
    tq = [0, t_sag, t_peak, t_dark, t_dark + 0.1, 630]
    q = [145, 145, 900, 900, 0, 0]
    a2.plot(tq, q, color=BLUE, lw=1.8, zorder=3)
    a2.text(t_sag - 6, 200, '145 MVAr', fontsize=9, color=INK, ha='right',
            va='bottom', fontweight='bold')
    a2.text(t_sag - 6, 900, '900 MVAr', fontsize=9, color=INK, ha='right',
            va='center', fontweight='bold')
    a2.set_ylim(0, 1150)
    a2.set_yticks([0, 500, 1000])
    a2.set_ylabel('Reactive\npower, MVAr', fontsize=10)
    # -- generation
    tg = [0, t_osc, t_osc + 4, t_osc + 18, t_osc + 22, t_peak, t_peak + 0.1,
          t_dark, t_dark + 0.1, 630]
    g = [8963, 8963, 9263, 9263, 8963, 8963, 6032, 6032, 0, 0]
    a3.plot(tg, g, color=INK, lw=1.8, zorder=3)
    a3.axhline(9000, color=MUTED, lw=1, ls=(0, (4, 3)), zorder=2)
    a3.text(8, 9150, '9,000 MW evacuation ceiling', fontsize=9, color=INK2,
            va='bottom')
    a3.text(t_osc + 26, 9700, '+300 MW', fontsize=8.5, color=INK2,
            va='bottom')
    a3.text(t_sag - 6, 6032, '2,931 MW trips on over-voltage',
            fontsize=9, color=INK, ha='right', va='center',
            fontweight='bold')
    a3.text(t_sag - 6, 1800, '17 lines trip; complex dark; 49.39 Hz',
            fontsize=9, color=INK, ha='right', va='center',
            fontweight='bold')
    a3.set_ylim(0, 11800)
    a3.set_yticks([0, 5000, 10000])
    a3.set_yticklabels(['0', '5,000', '10,000'])
    a3.set_ylabel('Generation,\nMW', fontsize=10)
    # -- shared x, event lines, event labels above panel 1
    ticks = [T[tt] for tt, _ in ev]
    for ax in (a1, a2, a3):
        ax.set_xlim(0, 630)
        for x in ticks:
            ax.axvline(x, color=GREY, lw=0.8, zorder=1)
        ax.spines['left'].set_visible(False)
        ax.tick_params(axis='y', length=0)
        ax.yaxis.set_label_coords(-0.072, 0.5)
    for ax in (a1, a2):
        ax.tick_params(axis='x', labelbottom=False, length=0)
        ax.spines['bottom'].set_visible(False)
    a3.set_xticks([0] + ticks)
    a3.set_xticklabels(['14:00:00'] + [tt for tt, _ in ev], rotation=90,
                       fontsize=8.5)
    a3.tick_params(axis='x', length=0)
    rows = {'14:09:31': 1.04, '14:09:51': 1.22, '14:10:02': 1.04}
    for tt, lbl in ev:
        x = T[tt]
        ha = 'center'
        if tt == '14:09:31':
            ha, x = 'right', x - 2
        elif tt == '14:10:02':
            ha, x = 'left', x + 2
        a1.text(x, rows.get(tt, 1.04), lbl, fontsize=8, color=INK2, ha=ha,
                va='bottom', transform=a1.get_xaxis_transform(),
                clip_on=False, linespacing=1.2)
    a1.plot([t_peak, t_peak], [1.0, 1.2], color=GREY, lw=0.8,
            transform=a1.get_xaxis_transform(), clip_on=False, zorder=1)
    save(fig, 'fig23_telemetry.png')


if __name__ == '__main__':
    fig17_developers()
    fig19_iex_bess()
    fig20_irr()
    fig22_transmission_map()
    fig23_telemetry()
