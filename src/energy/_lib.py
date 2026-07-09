"""US energy trade + prices dashboard — fetch EIA bulk data, render SVG charts.

Pipeline (backend-aware via :mod:`energy.storage`):

1. ``download_series`` — fetch the EIA **bulk** zips (KEYLESS: PET.zip ~59 MB,
   NG.zip ~4 MB from ``www.eia.gov/opendata/bulk/``), each an NDJSON of one series
   per line, extract the US-total monthly series we need (crude/product imports &
   exports & net, natural-gas imports & exports, and gasoline / WTI / Henry-Hub
   prices), and cache the compact result.
2. ``build_dashboard`` — render a self-contained HTML page of inline-SVG
   time-series charts (no JS/CDN): the US net-importer → net-exporter flip and
   the price history through the 2008 / 2014 / 2020 / 2022 swings.

EIA is the gold standard for US energy data (series back to the 1990s or 1920s);
this focuses on ~2000-present. Global trade is patchier (EIA is US-centric).
"""

from __future__ import annotations

import io
import json
import logging
import zipfile
from dataclasses import dataclass
from html import escape

from . import storage as cstore

try:
    import requests
except ImportError:  # pragma: no cover
    requests = None

logger = logging.getLogger("energy")

BULK = "https://www.eia.gov/opendata/bulk"
USER_AGENT = "facetwork-energy/1.0 (+https://github.com/rlemke/facetwork)"
FFL_URL = "https://github.com/rlemke/fwh_energy/blob/main/src/energy/ffl/energy.ffl"
YEAR_FROM = 2000

# US-total monthly series → (EIA series_id, label). All verified in the bulk data.
PET_SERIES = {
    "crude_imports": ("PET.MCRIMUS2.M", "Crude oil imports"),
    "crude_exports": ("PET.MCREXUS2.M", "Crude oil exports"),
    "petro_imports": ("PET.MTTIMUS2.M", "Crude + products imports"),
    "petro_exports": ("PET.MTTEXUS2.M", "Crude + products exports"),
    "petro_net": ("PET.MTTNTUS2.M", "Net petroleum imports"),
    "gasoline": ("PET.EMM_EPMR_PTE_NUS_DPG.M", "Regular gasoline"),
    "wti": ("PET.RWTC.M", "WTI crude"),
}
NG_SERIES = {
    "ng_imports": ("NG.N9100US2.M", "Natural gas imports"),
    "ng_exports": ("NG.N9130US2.M", "Natural gas exports"),
    "henryhub": ("NG.RNGWHHD.M", "Henry Hub price"),
}


@dataclass
class DashboardResult:
    html_path: str
    json_path: str
    series_count: int
    month_min: str
    month_max: str


# ---------------------------------------------------------------------------
# Download + cache
# ---------------------------------------------------------------------------


def _extract(zip_bytes: bytes, wanted: dict[str, tuple[str, str]]) -> dict[str, dict]:
    """Pull the wanted series out of an EIA bulk NDJSON zip."""
    ids = {sid: key for key, (sid, _label) in wanted.items()}
    out: dict[str, dict] = {}
    with zipfile.ZipFile(io.BytesIO(zip_bytes)) as z:
        fn = next(n for n in z.namelist() if n.endswith(".txt"))
        for line in io.TextIOWrapper(z.open(fn), "utf-8"):
            try:
                d = json.loads(line)
            except Exception:  # noqa: BLE001
                continue
            key = ids.get(d.get("series_id"))
            if not key:
                continue
            pts = {}
            for row in d.get("data") or []:
                try:
                    ym, val = str(row[0]), row[1]
                except (IndexError, TypeError):
                    continue
                if len(ym) == 6 and val is not None and int(ym[:4]) >= YEAR_FROM:
                    pts[ym] = float(val)
            out[key] = {"label": wanted[key][1], "units": d.get("units", ""), "points": pts}
            if len(out) == len(wanted):
                break
    return out


def download_series(*, force: bool = False) -> dict[str, dict]:
    """Fetch + cache the EIA series we need. Returns {key: {label, units, points}}."""
    cache_key = cstore.join(cstore.cache_root(), "eia-series.json")
    if not force and cstore.exists(cache_key):
        with cstore.open_read(cache_key) as f:
            return json.load(f)
    if requests is None:
        raise RuntimeError("requests is required to fetch EIA bulk data")
    series: dict[str, dict] = {}
    for name, wanted in (("PET", PET_SERIES), ("NG", NG_SERIES)):
        logger.info("downloading EIA bulk %s.zip …", name)
        resp = requests.get(f"{BULK}/{name}.zip", headers={"User-Agent": USER_AGENT}, timeout=(30, 300))
        resp.raise_for_status()
        series.update(_extract(resp.content, wanted))
    missing = (set(PET_SERIES) | set(NG_SERIES)) - set(series)
    if missing:
        logger.warning("EIA series not found: %s", missing)
    with cstore.open_write(cache_key, "w") as f:
        json.dump(series, f, separators=(",", ":"))
    logger.info("cached %d EIA series", len(series))
    return series


# ---------------------------------------------------------------------------
# SVG chart primitives (self-contained, no JS)
# ---------------------------------------------------------------------------

W, H = 900, 300
PAD_L, PAD_R, PAD_T, PAD_B = 66, 16, 30, 34


def _ym_to_x(ym: str) -> float:
    return int(ym[:4]) + (int(ym[4:6]) - 1) / 12.0


def _nice(v: float) -> float:
    """A round-ish step for gridlines."""
    import math
    if v <= 0:
        return 1.0
    mag = 10 ** math.floor(math.log10(v))
    for m in (1, 2, 2.5, 5, 10):
        if v <= m * mag:
            return m * mag
    return 10 * mag


def _svg_chart(title: str, units: str, lines: list[tuple[str, str, dict]], *,
               zero_line: bool = False) -> str:
    """Render one time-series line chart as inline SVG. lines = [(label, colour, points)]."""
    allx = [_ym_to_x(ym) for _l, _c, pts in lines for ym in pts]
    ally = [v for _l, _c, pts in lines for v in pts.values()]
    if not allx or not ally:
        return f'<div class="chart"><h3>{escape(title)}</h3><p>no data</p></div>'
    x0, x1 = min(allx), max(allx)
    y0 = min(0.0, min(ally)) if zero_line or min(ally) < 0 else 0.0
    y1 = max(ally)
    y1 += (y1 - y0) * 0.06 or 1.0
    step = _nice((y1 - y0) / 5)
    import math
    y0g = math.floor(y0 / step) * step
    y1g = math.ceil(y1 / step) * step

    def px(x): return PAD_L + (x - x0) / (x1 - x0 or 1) * (W - PAD_L - PAD_R)
    def py(y): return H - PAD_B - (y - y0g) / (y1g - y0g or 1) * (H - PAD_T - PAD_B)

    parts = [f'<svg viewBox="0 0 {W} {H}" class="svgchart" role="img" '
             f'aria-label="{escape(title)}">']
    # y gridlines + labels
    yv = y0g
    while yv <= y1g + 1e-9:
        yy = py(yv)
        parts.append(f'<line x1="{PAD_L}" y1="{yy:.1f}" x2="{W-PAD_R}" y2="{yy:.1f}" '
                     f'class="grid"/>')
        lab = f"{yv:,.2f}" if abs(y1g) < 20 else f"{yv:,.0f}"
        parts.append(f'<text x="{PAD_L-6}" y="{yy+3:.1f}" class="ylab">{lab}</text>')
        yv += step
    # zero line emphasis
    if y0g < 0 < y1g:
        parts.append(f'<line x1="{PAD_L}" y1="{py(0):.1f}" x2="{W-PAD_R}" y2="{py(0):.1f}" class="zero"/>')
    # x year ticks
    yr0, yr1 = int(math.ceil(x0)), int(x1)
    tstep = max(1, (yr1 - yr0) // 8)
    for yr in range(yr0, yr1 + 1, tstep):
        xx = px(yr)
        parts.append(f'<text x="{xx:.1f}" y="{H-PAD_B+16:.1f}" class="xlab">{yr}</text>')
    # data polylines
    for label, colour, pts in lines:
        seq = sorted(pts.items())
        pl = " ".join(f"{px(_ym_to_x(ym)):.1f},{py(v):.1f}" for ym, v in seq)
        parts.append(f'<polyline points="{pl}" fill="none" stroke="{colour}" '
                     f'stroke-width="1.8"/>')
    parts.append("</svg>")
    # legend
    leg = " ".join(f'<span class="lg"><i style="background:{c}"></i>{escape(l)}</span>'
                   for l, c, _ in lines)
    return (f'<div class="chart"><h3>{escape(title)} '
            f'<span class="units">{escape(units)}</span></h3>'
            f'<div class="legend">{leg}</div>{"".join(parts)}</div>')


# ---------------------------------------------------------------------------
# Build the dashboard
# ---------------------------------------------------------------------------


def build_dashboard(*, force: bool = False) -> DashboardResult:
    s = download_series(force=force)

    def pts(k):
        return (s.get(k) or {}).get("points", {})

    months = sorted(ym for k in s for ym in pts(k))
    m_min, m_max = (months[0], months[-1]) if months else ("", "")

    petro = _svg_chart(
        "US petroleum trade — imports, exports & net", "million barrels/day",
        [("Imports (crude + products)", "#c0392b", {k: v/1000 for k, v in pts("petro_imports").items()}),
         ("Exports (crude + products)", "#27ae60", {k: v/1000 for k, v in pts("petro_exports").items()}),
         ("Net imports", "#2c3e50", {k: v/1000 for k, v in pts("petro_net").items()})],
        zero_line=True)
    crude = _svg_chart(
        "US crude oil trade", "million barrels/day",
        [("Crude imports", "#e67e22", {k: v/1000 for k, v in pts("crude_imports").items()}),
         ("Crude exports", "#16a085", {k: v/1000 for k, v in pts("crude_exports").items()})])
    gas = _svg_chart(
        "US natural gas trade", "billion cubic feet/month",
        [("Imports", "#8e44ad", {k: v/1000 for k, v in pts("ng_imports").items()}),
         ("Exports (incl. LNG)", "#2980b9", {k: v/1000 for k, v in pts("ng_exports").items()})])
    p_wti = _svg_chart("WTI crude oil price", "$ / barrel",
                       [("WTI", "#c0392b", pts("wti"))])
    p_gas = _svg_chart("Regular gasoline (retail)", "$ / gallon",
                       [("Gasoline", "#d35400", pts("gasoline"))])
    p_hh = _svg_chart("Henry Hub natural gas price", "$ / million BTU",
                      [("Henry Hub", "#2980b9", pts("henryhub"))])

    html = _render_html([petro, crude, gas], [p_wti, p_gas, p_hh], m_min, m_max)
    out = cstore.output_root()
    html_path = cstore.join(out, "index.html")
    json_path = cstore.join(out, "eia-series.json")
    with cstore.open_write(html_path, "w") as f:
        f.write(html)
    with cstore.open_write(json_path, "w") as f:
        json.dump(s, f, separators=(",", ":"))
    logger.info("energy dashboard: %d series, %s-%s -> %s", len(s), m_min, m_max, html_path)
    return DashboardResult(html_path, json_path, len(s), m_min, m_max)


def _render_html(trade_charts: list[str], price_charts: list[str], m0: str, m1: str) -> str:
    from datetime import UTC, datetime
    ts = datetime.now(UTC).strftime("%Y-%m-%d %H:%M UTC")

    def ymlab(ym):
        return f"{ym[:4]}-{ym[4:6]}" if len(ym) == 6 else ym
    repo = escape(FFL_URL.split("/blob/")[0])
    return f"""<!doctype html>
<html><head><meta charset="utf-8"><title>US energy trade &amp; prices (EIA)</title>
<meta name="viewport" content="width=device-width, initial-scale=1">
<style>
  body{{margin:0;font:15px/1.6 system-ui,-apple-system,Segoe UI,Roboto,sans-serif;color:#1a1a1a;background:#fafafa}}
  .wrap{{max-width:960px;margin:0 auto;padding:26px 18px 80px}}
  h1{{font-size:26px;margin:0 0 4px}} .sub{{color:#666;margin:0 0 14px}}
  h2{{font-size:19px;margin:30px 0 6px;border-bottom:2px solid #eee;padding-bottom:4px}}
  .thesis{{background:#eef6ff;border-left:4px solid #2166ac;padding:12px 16px;border-radius:6px;margin:14px 0}}
  .chart{{background:#fff;border:1px solid #e6e6e6;border-radius:8px;padding:10px 12px 6px;margin:14px 0}}
  .chart h3{{margin:2px 0 2px;font-size:15px}} .units{{color:#888;font-weight:400;font-size:12px}}
  .svgchart{{width:100%;height:auto;display:block}}
  .grid{{stroke:#eee;stroke-width:1}} .zero{{stroke:#999;stroke-width:1.2;stroke-dasharray:4 3}}
  .ylab{{fill:#666;font-size:11px;text-anchor:end}} .xlab{{fill:#666;font-size:11px;text-anchor:middle}}
  .legend{{margin:2px 0 4px;font-size:12px;color:#444}}
  .lg{{margin-right:14px;white-space:nowrap}} .lg i{{display:inline-block;width:11px;height:11px;border-radius:2px;vertical-align:middle;margin-right:4px}}
  .prices{{display:grid;grid-template-columns:repeat(auto-fit,minmax(280px,1fr));gap:12px}}
  .prices .chart{{margin:0}}
  footer{{margin-top:34px;padding-top:12px;border-top:1px solid #e6e6e6;color:#666;font-size:12px}}
  footer a{{color:#1565c0;text-decoration:none}} code{{background:#f0f0f0;padding:0 3px;border-radius:3px}}
</style></head>
<body><div class="wrap">
<h1>US energy trade &amp; prices</h1>
<p class="sub">Imports, exports and prices for oil, refined products and natural gas,
monthly {ymlab(m0)} to {ymlab(m1)}. Source: U.S. Energy Information Administration.</p>

<div class="thesis"><b>The big shift.</b> Driven by the shale boom, the United States went
from the world's largest net oil importer to a <b>net exporter around 2019-2020</b> — the net-imports
line below crosses zero. Natural-gas exports (LNG) took off over the same period. Prices tell the
parallel story: the 2008 spike, the 2014 collapse, the 2020 COVID crash (WTI briefly negative), and
the 2022 surge after Russia's invasion of Ukraine.</div>

<h2>Trade</h2>
{''.join(trade_charts)}

<h2>Prices</h2>
<div class="prices">{''.join(price_charts)}</div>

<footer>Generated by Facetwork workflow <code>energy.workflows.BuildEnergyDashboard</code> ·
data: <a href="https://www.eia.gov/opendata/" target="_blank" rel="noopener">U.S. Energy Information
Administration</a> (public domain) ·
<a href="{escape(FFL_URL)}" target="_blank" rel="noopener">view FFL</a> ·
<a href="{repo}" target="_blank" rel="noopener">source repo</a> · generated {ts}</footer>
</div></body></html>"""
