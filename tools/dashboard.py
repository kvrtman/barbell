#!/usr/bin/env python3
"""Generate dashboard.html — the barbell's visual state, projections included.

Stdlib only, so it runs on any machine with Python 3. Reads holdings from
ledger.csv (BASELINE/BUY/SELL rows), takes current prices as flags, and emits
a self-contained theme-aware HTML file with inline SVG charts:

  1. Stat tiles        — portfolio value, both legs, the dividend loop
  2. Target progress   — shares held vs target, both legs
  3. Scenario P/L      — diverging bars at audited exit prices (today vs 500k plan)
  4. Accumulation race — months to 500k at three funding paces vs the re-rate window
  5. Fee curve         — effective fee % by clip size (the P8,000 rule, priced)

Usage:
  python3 tools/dashboard.py --alter-price 0.78 --rcr-price 7.30 --asof 2026-07-03
"""

import argparse
import csv
import html
from datetime import date
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parent.parent

# Audited exit scenarios: (price, label, audit tag)
EXITS = [
    (0.64, "Bear", "COD slip"),
    (0.91, "Book", "first leg"),
    (1.15, "52wk high", "ceiling zone"),
    (1.28, "IPO price", "ceiling top"),
    (1.55, "Bull", "tail case"),
]
STT = 0.006          # stock transaction tax on sale
BUY_FEE = 0.00295    # all-in buy drag at/above the P8,000 clip
FEE_MIN = 20.0       # broker minimum commission
FEE_RATE = 0.0025
LOT = 1000


def buy_fee(gross):
    return max(FEE_RATE * gross, FEE_MIN) * 1.12 + 0.00015 * gross


def read_holdings(ledger_path):
    holdings = {}
    with open(ledger_path, newline="", encoding="utf-8") as f:
        for row in csv.DictReader(f):
            action = (row.get("action") or "").strip().upper()
            ticker = (row.get("ticker") or "").strip().upper()
            shares = (row.get("shares") or "").strip()
            if not ticker or not shares or action == "DIVIDEND":
                continue
            qty = float(shares)
            if action == "SELL":
                qty = -abs(qty)
            holdings[ticker] = holdings.get(ticker, 0) + qty
    return {k: int(v) for k, v in holdings.items()}


def php(x, dec=0):
    return f"₱{x:,.{dec}f}"


def esc(s):
    return html.escape(str(s), quote=True)


# ---------------------------------------------------------------- SVG helpers

def svg_open(w, h, label):
    return (f'<svg viewBox="0 0 {w} {h}" role="img" aria-label="{esc(label)}" '
            f'style="width:100%;height:auto;display:block">')


def scale(lo, hi, out_lo, out_hi):
    span = (hi - lo) or 1.0
    return lambda v: out_lo + (v - lo) / span * (out_hi - out_lo)


def tip(text):
    return f'data-tip="{esc(text)}"'


# ---------------------------------------------------------------- components

def stat_tiles(tiles):
    cells = "".join(
        f'<div class="tile"><div class="tile-label">{esc(lb)}</div>'
        f'<div class="tile-value">{esc(v)}</div>'
        f'<div class="tile-sub">{esc(sub)}</div></div>'
        for lb, v, sub in tiles)
    return f'<div class="tiles">{cells}</div>'


def progress_bars(rows):
    out = []
    for label, held, target in rows:
        pct = min(held / target, 1.0)
        out.append(
            f'<div class="prog"><div class="prog-head"><span>{esc(label)}</span>'
            f'<span class="prog-num">{held:,} / {target:,} '
            f'<strong>({pct * 100:.1f}%)</strong></span></div>'
            f'<div class="prog-track"><div class="prog-fill" style="width:{pct * 100:.2f}%"></div></div></div>')
    return "".join(out)


def scenario_panel(title, ref_note, rows, vmin, vmax, w=680):
    """Diverging horizontal bars around a zero baseline. rows: (label, tag, pnl)."""
    left, right, row_h, top = 118, 14, 44, 30
    h = top + row_h * len(rows) + 26
    x = scale(vmin, vmax, left, w - right)
    x0 = x(0)
    parts = [svg_open(w, h, title)]
    # zero baseline
    parts.append(f'<line x1="{x0:.1f}" y1="{top - 8}" x2="{x0:.1f}" y2="{h - 22}" class="axisline"/>')
    for i, (label, tag, pnl) in enumerate(rows):
        y = top + i * row_h
        bx = x(min(pnl, 0)) if pnl < 0 else x0
        bw = abs(x(pnl) - x0)
        cls = "bar-pos" if pnl >= 0 else "bar-neg"
        rx = 4 if bw >= 8 else 2
        t = tip(f"Exit {label}: {php(pnl)} net of 0.6% sale tax")
        parts.append(f'<text x="{left - 10}" y="{y + 15}" class="lbl" text-anchor="end">{esc(label)}</text>')
        parts.append(f'<text x="{left - 10}" y="{y + 30}" class="lbl-sub" text-anchor="end">{esc(tag)}</text>')
        parts.append(f'<rect x="{bx:.1f}" y="{y + 4}" width="{max(bw, 2):.1f}" height="22" rx="{rx}" class="{cls}" {t}/>')
        sign = "−" if pnl < 0 else "+"
        vtxt = f"{sign}₱{abs(pnl) / 1000:,.1f}k"
        tx = x(pnl) + (7 if pnl >= 0 else -7)
        anch, vcls = ("start", "val") if pnl >= 0 else ("end", "val")
        # keep the label out of the row-label gutter / right edge: move it inside the bar
        if pnl < 0 and tx - 60 < left - 6:
            tx, anch, vcls = bx + 7, "start", "val val-in"
        elif pnl >= 0 and tx + 60 > w - right:
            tx, anch, vcls = x(pnl) - 7, "end", "val val-in"
        parts.append(f'<text x="{tx:.1f}" y="{y + 19}" class="{vcls}" text-anchor="{anch}">{esc(vtxt)}</text>')
    parts.append(f'<text x="{x0:.1f}" y="{h - 8}" class="lbl-sub" text-anchor="middle">₱0 (break even)</text>')
    parts.append("</svg>")
    return (f'<div class="panel"><div class="panel-title">{esc(title)}</div>'
            f'<div class="panel-sub">{esc(ref_note)}</div>{"".join(parts)}</div>')


def race_chart(series, target, window, months_axis, w=720, h=330):
    """series: [(name, cssvar, [(month_idx, shares)...], cross_label)]"""
    left, right, top, bottom = 64, 120, 22, 40
    xmax = months_axis[-1][0]
    ymax = target * 1.12
    xs = scale(0, xmax, left, w - right)
    ys = scale(0, ymax, h - bottom, top)
    parts = [svg_open(w, h, "Accumulation race: months to 500,000 shares by funding pace")]
    # re-rate window band
    wx1, wx2 = xs(window[0]), xs(window[1])
    parts.append(f'<rect x="{wx1:.1f}" y="{top}" width="{wx2 - wx1:.1f}" height="{h - bottom - top}" class="window"/>')
    parts.append(f'<text x="{(wx1 + wx2) / 2:.1f}" y="{h - bottom - 10}" class="lbl-sub" text-anchor="middle">re-rate window (COD → 2028)</text>')
    # gridlines + y ticks
    for gv in (100_000, 200_000, 300_000, 400_000, 500_000):
        gy = ys(gv)
        cls = "target" if gv == target else "grid"
        parts.append(f'<line x1="{left}" y1="{gy:.1f}" x2="{w - right}" y2="{gy:.1f}" class="{cls}"/>')
        parts.append(f'<text x="{left - 8}" y="{gy + 4:.1f}" class="tick" text-anchor="end">{gv // 1000}k</text>')
    parts.append(f'<text x="{left + 6}" y="{ys(target) - 7:.1f}" class="lbl-sub" text-anchor="start">target 500k</text>')
    # x ticks: Jan of each year
    for m, label in months_axis:
        parts.append(f'<text x="{xs(m):.1f}" y="{h - 14}" class="tick" text-anchor="middle">{esc(label)}</text>')
    # series lines + end labels + hover dots
    for name, var, pts, cross in series:
        d = " ".join(f"{'M' if i == 0 else 'L'}{xs(m):.1f},{ys(s):.1f}" for i, (m, s) in enumerate(pts))
        parts.append(f'<path d="{d}" fill="none" style="stroke:var({var})" class="line"/>')
        em, es_ = pts[-1]
        parts.append(f'<circle cx="{xs(em):.1f}" cy="{ys(es_):.1f}" r="4" style="fill:var({var})" class="dot" '
                     f'{tip(f"{name}: reaches target {cross}")}/>')
        parts.append(f'<text x="{xs(em) + 8:.1f}" y="{ys(es_) - 9:.1f}" class="lbl" style="fill:var({var})">{esc(name)}</text>')
        for m, s in pts[::6]:
            parts.append(f'<circle cx="{xs(m):.1f}" cy="{ys(s):.1f}" r="8" class="hit" '
                         f'{tip(f"{name} · month {m}: {int(s):,} shares")}/>')
    parts.append("</svg>")
    legend = "".join(
        f'<span class="key"><span class="swatch" style="background:var({var})"></span>{esc(name)} — {esc(cross)}</span>'
        for name, var, _, cross in series)
    return "".join(parts) + f'<div class="legend">{legend}</div>'


def fee_chart(w=720, h=280):
    left, right, top, bottom = 64, 20, 18, 42
    gmin, gmax = 500, 16000
    pmax = 5.0
    xs = scale(gmin, gmax, left, w - right)
    ys = scale(0, pmax, h - bottom, top)
    pts = []
    g = gmin
    while g <= gmax:
        pts.append((g, buy_fee(g) / g * 100))
        g += 100
    parts = [svg_open(w, h, "Effective buy fee percentage by clip size")]
    for gv in (1, 2, 3, 4, 5):
        gy = ys(gv)
        parts.append(f'<line x1="{left}" y1="{gy:.1f}" x2="{w - right}" y2="{gy:.1f}" class="grid"/>')
        parts.append(f'<text x="{left - 8}" y="{gy + 4:.1f}" class="tick" text-anchor="end">{gv}%</text>')
    for gv in (2000, 4000, 6000, 8000, 10000, 12000, 14000, 16000):
        parts.append(f'<text x="{xs(gv):.1f}" y="{h - 20}" class="tick" text-anchor="middle">{gv // 1000}k</text>')
    parts.append(f'<text x="{(left + w - right) / 2:.1f}" y="{h - 4}" class="lbl-sub" text-anchor="middle">clip size (₱)</text>')
    d = " ".join(f"{'M' if i == 0 else 'L'}{xs(g):.1f},{ys(p):.1f}" for i, (g, p) in enumerate(pts))
    parts.append(f'<path d="{d}" fill="none" class="line fee-line"/>')
    marks = [(780, "1 board lot · 2.9%"), (2500, "sanity floor · 0.9%"), (8000, "full clip · 0.30%")]
    for gv, lab in marks:
        p = buy_fee(gv) / gv * 100
        parts.append(f'<circle cx="{xs(gv):.1f}" cy="{ys(p):.1f}" r="5" class="dot fee-dot" '
                     f'{tip(f"{php(gv)}: {p:.2f}% — {php(buy_fee(gv), 2)} fee")}/>')
        parts.append(f'<text x="{xs(gv) + 9:.1f}" y="{ys(p) - 9:.1f}" class="lbl">{esc(lab)}</text>')
    parts.append("</svg>")
    return "".join(parts)


def table_view(headers, rows):
    th = "".join(f"<th>{esc(x)}</th>" for x in headers)
    trs = "".join("<tr>" + "".join(f"<td>{esc(c)}</td>" for c in r) + "</tr>" for r in rows)
    return (f'<details class="tbl"><summary>table view</summary>'
            f'<div class="tbl-scroll"><table><thead><tr>{th}</tr></thead><tbody>{trs}</tbody></table></div></details>')


# ---------------------------------------------------------------- main

def build(args):
    holdings = read_holdings(REPO_ROOT / "ledger.csv")
    alter, rcr = holdings.get("ALTER", 0), holdings.get("RCR", 0)
    ap, rp = args.alter_price, args.rcr_price
    alter_val, rcr_val = alter * ap, rcr * rp
    total = alter_val + rcr_val
    div_q = rcr * args.rcr_dps
    div_q_net = div_q * 0.90
    loop_shares_yr = int(div_q_net * 4 / ap)

    # scenario P/L
    cur_rows, plan_rows = [], []
    plan_basis = alter * 0.85 + (args.target_alter - alter) * args.plan_fill * (1 + BUY_FEE)
    for p, label, tag in EXITS:
        cur_rows.append((f"₱{p:.2f} {label}", tag, alter * p * (1 - STT) - alter_val))
        plan_rows.append((f"₱{p:.2f} {label}", tag, args.target_alter * p * (1 - STT) - plan_basis))
    allv = [r[2] for r in cur_rows + plan_rows]
    vmin, vmax = min(allv) * 1.15, max(allv) * 1.15

    # accumulation race (monthly buys at race_fill + quarterly dividend reinvest)
    def race(monthly):
        pts, sh, m = [(0, alter)], float(alter), 0
        cross = None
        while m < 54 and sh < args.target_alter:
            m += 1
            sh += monthly * (1 - BUY_FEE) / args.race_fill
            if m % 3 == 0:
                sh += div_q_net / args.race_fill
            if sh >= args.target_alter and cross is None:
                cross = m
                sh = args.target_alter
            pts.append((m, min(sh, args.target_alter)))
        return pts, cross

    start_y, start_m = (int(x) for x in args.asof.split("-")[:2])

    def month_name(m):
        y, mo = divmod(start_m - 1 + m, 12)
        return f"{date(start_y + y, mo + 1, 1):%b %Y}"

    series = []
    for amt, var in ((8000, "--s1"), (16000, "--s2"), (24000, "--s3")):
        pts, cross = race(amt)
        label = month_name(cross) if cross else "beyond chart"
        series.append((f"₱{amt // 1000}k/mo", var, pts, label))
    months_axis = [(m, month_name(m)) for m in range(0, 55, 12)]
    window = (4, 29)  # ~Nov 2026 (first COD) to ~Dec 2028

    tiles = stat_tiles([
        ("Portfolio value", php(total), f"as of {args.asof} close"),
        ("Engine · ALTER", php(alter_val), f"{alter:,} sh @ {php(ap, 2)} · P/B {ap / 0.91:.2f}"),
        ("Anchor · RCR", php(rcr_val), f"{rcr:,} sh @ {php(rp, 2)} · yield {args.rcr_dps * 4 / rp * 100:.1f}%"),
        ("The Loop", f"{php(div_q_net)}/qtr", f"net dividend → ~{loop_shares_yr:,} ALTER sh/yr"),
    ])
    progress = progress_bars([
        ("ALTER — engine target", alter, args.target_alter),
        ("RCR — anchor target", rcr, args.target_rcr),
    ])
    scen_tbl = table_view(
        ["Exit", "Audit tag", f"P/L today ({alter:,} sh)", f"P/L at 500k (basis {php(plan_basis)})"],
        [(c[0], c[1], php(c[2]), php(p[2])) for c, p in zip(cur_rows, plan_rows)])
    race_tbl = table_view(
        ["Pace", "Reaches 500k", "Inside re-rate window?"],
        [(n, c, "yes" if c != "beyond chart" and c <= month_name(30) else "at risk") for n, _, _, c in series])

    css_svg = """
.viz-root{--surface-1:#fcfcfb;--plane:#f9f9f7;--ink:#0b0b0b;--ink-2:#52514e;--muted:#898781;
 --grid:#e1e0d9;--axis:#c3c2b7;--border:rgba(11,11,11,.10);
 --s1:#2a78d6;--s2:#1baf7a;--s3:#eda100;--pos:#2a78d6;--neg:#e34948;--accent:#256abf}
@media (prefers-color-scheme:dark){.viz-root{--surface-1:#1a1a19;--plane:#0d0d0d;--ink:#ffffff;
 --ink-2:#c3c2b7;--muted:#898781;--grid:#2c2c2a;--axis:#383835;--border:rgba(255,255,255,.10);
 --s1:#3987e5;--s2:#199e70;--s3:#c98500;--pos:#3987e5;--neg:#e66767;--accent:#3987e5}}
:root[data-theme="dark"] .viz-root{--surface-1:#1a1a19;--plane:#0d0d0d;--ink:#ffffff;--ink-2:#c3c2b7;
 --muted:#898781;--grid:#2c2c2a;--axis:#383835;--border:rgba(255,255,255,.10);
 --s1:#3987e5;--s2:#199e70;--s3:#c98500;--pos:#3987e5;--neg:#e66767;--accent:#3987e5}
:root[data-theme="light"] .viz-root{--surface-1:#fcfcfb;--plane:#f9f9f7;--ink:#0b0b0b;--ink-2:#52514e;
 --muted:#898781;--grid:#e1e0d9;--axis:#c3c2b7;--border:rgba(11,11,11,.10);
 --s1:#2a78d6;--s2:#1baf7a;--s3:#eda100;--pos:#2a78d6;--neg:#e34948;--accent:#256abf}
.viz-root{font-family:system-ui,-apple-system,"Segoe UI",sans-serif;background:var(--plane);color:var(--ink);
 margin:0 auto;max-width:900px;padding:20px 16px 40px;box-sizing:border-box}
.viz-root *,.viz-root *::before,.viz-root *::after{box-sizing:inherit}
h1{font-size:22px;margin:0 0 2px}
.asof{color:var(--ink-2);font-size:13px;margin:0 0 18px}
section{background:var(--surface-1);border:1px solid var(--border);border-radius:10px;
 padding:16px 18px;margin:14px 0}
h2{font-size:15px;margin:0 0 4px}
.note{color:var(--ink-2);font-size:12.5px;margin:0 0 12px;line-height:1.5}
.tiles{display:grid;grid-template-columns:repeat(auto-fit,minmax(180px,1fr));gap:10px}
.tile{background:var(--surface-1);border:1px solid var(--border);border-radius:10px;padding:12px 14px}
.tile-label{font-size:12px;color:var(--ink-2)}
.tile-value{font-size:24px;font-weight:650;margin:2px 0}
.tile-sub{font-size:11.5px;color:var(--muted)}
.prog{margin:12px 0}
.prog-head{display:flex;justify-content:space-between;font-size:13px;margin-bottom:5px}
.prog-num{color:var(--ink-2)}.prog-num strong{color:var(--ink)}
.prog-track{height:10px;border-radius:5px;background:var(--grid)}
.prog-fill{height:10px;border-radius:5px;background:var(--accent)}
.panel{margin:10px 0}.panel-title{font-size:13px;font-weight:600}
.panel-sub{font-size:11.5px;color:var(--muted);margin-bottom:4px}
.lbl{font-size:11.5px;fill:var(--ink)}
.lbl-sub{font-size:10.5px;fill:var(--muted)}
.val{font-size:11px;font-weight:600;fill:var(--ink)}
.val-in{fill:var(--surface-1)}
.tick{font-size:10.5px;fill:var(--muted);font-variant-numeric:tabular-nums}
.grid{stroke:var(--grid);stroke-width:1}
.axisline{stroke:var(--axis);stroke-width:1.5}
.target{stroke:var(--ink-2);stroke-width:1;stroke-dasharray:5 4}
.window{fill:var(--grid);opacity:.45}
.line{stroke-width:2;stroke-linejoin:round;stroke-linecap:round}
.fee-line{stroke:var(--s1)}.fee-dot{fill:var(--s1);stroke:var(--surface-1);stroke-width:2}
.dot{stroke:var(--surface-1);stroke-width:2}
.hit{fill:transparent;pointer-events:all}
.bar-pos{fill:var(--pos)}.bar-neg{fill:var(--neg)}
.bar-pos:hover,.bar-neg:hover,.dot:hover{opacity:.85}
.legend{display:flex;flex-wrap:wrap;gap:14px;font-size:12px;color:var(--ink-2);margin-top:8px}
.key{display:inline-flex;align-items:center;gap:6px}
.swatch{width:10px;height:10px;border-radius:3px;display:inline-block}
.tbl{margin-top:8px;font-size:12.5px}.tbl summary{cursor:pointer;color:var(--ink-2)}
.tbl-scroll{overflow-x:auto}
.tbl table{border-collapse:collapse;margin-top:8px;min-width:480px}
.tbl th,.tbl td{text-align:left;padding:4px 12px 4px 0;border-bottom:1px solid var(--grid);
 font-variant-numeric:tabular-nums}
.tbl th{color:var(--ink-2);font-weight:600}
footer{color:var(--muted);font-size:11.5px;line-height:1.6;margin-top:18px}
#tt{position:fixed;pointer-events:none;background:var(--ink);color:var(--plane);font-size:12px;
 padding:5px 9px;border-radius:6px;opacity:0;transition:opacity .08s;z-index:10;max-width:260px}
"""
    js = """
(function(){var tt=document.getElementById('tt');
document.querySelectorAll('[data-tip]').forEach(function(el){
 el.addEventListener('mousemove',function(e){tt.textContent=el.getAttribute('data-tip');
  tt.style.opacity=1;tt.style.left=Math.min(e.clientX+12,window.innerWidth-270)+'px';
  tt.style.top=(e.clientY+14)+'px';});
 el.addEventListener('mouseleave',function(){tt.style.opacity=0;});});})();
"""

    gap = args.target_alter - alter
    doc = f"""<!-- generated by tools/dashboard.py — regenerate, do not hand-edit -->
<title>Barbell Dashboard</title>
<style>{css_svg}</style>
<div class="viz-root">
<h1>The Barbell — Dashboard</h1>
<p class="asof">Prices as of {esc(args.asof)} (PSE close) · generated {date.today().isoformat()} · holdings from ledger.csv</p>
{tiles}
<section><h2>Progress to targets</h2>
<p class="note">Engine gap: {gap:,} shares ≈ {php(gap * ap)} at {php(ap, 2)}. Anchor gap: {args.target_rcr - rcr:,} shares ≈ {php((args.target_rcr - rcr) * rp)}.</p>
{progress}</section>
<section><h2>Exit scenarios — audited (red-team, 2026-07-04)</h2>
<p class="note">Net of 0.6% sale tax. Audit verdict: ₱1.15–1.28 is the honest ceiling for the two-project story; ₱1.55 is a tail case; ₱1.80 was struck as fantasy and is not charted. Left panel measures against today's market value (fill your true cost basis into ledger.csv for exact P/L); right panel against the 500k plan basis of {php(plan_basis)} ({args.plan_fill:.2f} blended fill).</p>
{scenario_panel(f"At today's {alter:,} shares", f"reference: today's market value {php(alter_val)}", cur_rows, vmin, vmax)}
{scenario_panel(f"At the 500,000-share target", f"reference: plan cost basis {php(plan_basis)}", plan_rows, vmin, vmax)}
{scen_tbl}</section>
<section><h2>The accumulation race — pace vs the re-rate window</h2>
<p class="note">Shares held by month at three funding paces ({php(args.race_fill, 2)} average fill, dividends reinvested quarterly). The shaded band is when the audit says the re-rate must land (COD → 2028) for the trade to earn its risk. A line crossing 500k after the band means the target is reached only if the thesis stalls — the accumulation paradox.</p>
{race_chart(series, args.target_alter, window, months_axis)}
{race_tbl}</section>
<section><h2>The ₱8,000 rule, priced honestly</h2>
<p class="note">Effective all-in buy fee by clip size (0.25% commission with ₱20 minimum, +VAT +PSE +SCCP). ₱8,000 is where the minimum stops binding (0.30%). Below it the flat ₱≈23 dominates — acceptable leakage above the ₱2,500 sanity floor, real bleed below it. Long-horizon verdict: clips under ₱8k are allowed; clips under ₱2.5k are not.</p>
{fee_chart()}</section>
<footer>Assumptions: book value ₱0.91/sh; plan basis = existing at ₱0.85 + gap at {args.plan_fill:.2f} incl. fees; race at {php(args.race_fill, 2)} fill; RCR DPS {php(args.rcr_dps, 2)}/qtr, 10% WHT. Scenario prices and tags from the red-team audit in playbook.md §9. Personal working document — not investment advice.</footer>
<div id="tt"></div>
</div>
<script>{js}</script>
"""
    out = Path(args.out) if args.out else REPO_ROOT / "dashboard.html"
    out.write_text(doc, encoding="utf-8")
    print(f"wrote {out} — ALTER {alter:,} sh @ {php(ap, 2)}, RCR {rcr:,} sh @ {php(rp, 2)}, total {php(total)}")


def main():
    p = argparse.ArgumentParser(description="Generate the barbell dashboard")
    p.add_argument("--alter-price", type=float, required=True)
    p.add_argument("--rcr-price", type=float, required=True)
    p.add_argument("--asof", default=date.today().isoformat(), help="price date YYYY-MM-DD")
    p.add_argument("--rcr-dps", type=float, default=0.11)
    p.add_argument("--target-alter", type=int, default=500_000)
    p.add_argument("--target-rcr", type=int, default=10_000)
    p.add_argument("--plan-fill", type=float, default=0.85)
    p.add_argument("--race-fill", type=float, default=0.82)
    p.add_argument("--out", default=None)
    build(p.parse_args())


if __name__ == "__main__":
    main()
