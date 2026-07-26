# Inline-SVG Charts & HTML Page

**Namespace(s):** `energy.data` (render side) ·
**Library:** `src/energy/_lib.py` (`_svg_chart`, `build_dashboard`, `_render_html`, `_ym_to_x`, `_nice`) ·
**Tests:** `tests/test_energy.py` (`test_svg_chart_renders`, `test_build_dashboard`)

## Overview

This feature turns the extracted EIA series into the visible artifact: a single,
**self-contained HTML page of inline-SVG time-series charts — no JavaScript, no
CDN, no external assets**. Everything (styles + six hand-rolled SVG line charts)
is embedded so the page renders from any static host, which is what makes it
publishable to GitHub Pages as a plain file.

It is the render half of `energy.data.BuildDashboard`. Input is the
`{key: {label, units, points}}` dict from [eia-ingest](eia-ingest.md); output is
the `index.html` string written by [dashboard](dashboard.md)/[storage](storage.md).

## How it works

`build_dashboard(*, force=False)` composes six charts then the page:

1. **Gather.** `s = download_series(force)`; a local `pts(k)` helper reads
   `s[k]["points"]`. Computes `months = sorted(...)` across all series →
   `m_min, m_max`.
2. **Six `_svg_chart(...)` calls** — three trade, three price:
   - *US petroleum trade* — imports / exports / net (crude + products), each
     scaled `v/1000` (thousand bbl/day → **million barrels/day**), `zero_line=True`.
   - *US crude oil trade* — crude imports / exports, `v/1000`.
   - *US natural gas trade* — imports / exports (incl. LNG), `v/1000`
     (million cf → **billion cubic feet/month**).
   - *WTI crude oil price* — `$ / barrel` (no scaling).
   - *Regular gasoline (retail)* — `$ / gallon`.
   - *Henry Hub natural gas price* — `$ / million BTU`.
3. **`_render_html([petro, crude, gas], [wti, gas, hh], m_min, m_max)`** wraps the
   chart fragments in a styled page: an `<h1>`, a "big shift" thesis callout, a
   **Trade** section (three stacked charts), a **Prices** grid
   (`grid-template-columns: repeat(auto-fit, minmax(280px,1fr))`), and a footer
   with provenance (workflow name, EIA link, "view FFL" link, source repo, UTC
   timestamp).

### `_svg_chart(title, units, lines, *, zero_line=False)`

`lines = [(label, colour, points)]`. Builds one `viewBox="0 0 900 300"` SVG
(`W, H = 900, 300`; margins `PAD_L/R/T/B = 66/16/30/34`):

- **Domain/range.** X from `_ym_to_x(ym) = year + (month-1)/12`. Y from
  `min(0, min(ally))` when `zero_line` or any negative, else `0`, up to
  `max(ally)` + 6 % headroom.
- **Gridlines.** `_nice((y1-y0)/5)` picks a round step (1/2/2.5/5/10 × power of
  ten); horizontal `.grid` lines + `.ylab` labels (2-decimal when `|y1g| < 20`,
  else integer). Emphasised dashed `.zero` line drawn when the range straddles 0
  (the net-imports crossing).
- **X ticks.** Year labels every `max(1, (yr1-yr0)//8)` years.
- **Series.** Each `(label, colour, pts)` → one `<polyline stroke-width="1.8">`
  over sorted points; a legend of `<span class="lg"><i style="background:…"></i>label</span>`.
- Empty input → a `<div class="chart"><h3>…</h3><p>no data</p></div>` fallback.

All text is `html.escape`d.

## Fan-out

**Single-task — no fan-out.** Pure string building in one process; the six charts
are rendered sequentially into one page. No fleet parallelism and none needed.

## Data & fields

- **Input:** the `points` dict `{YYYYMM: float}` per series (see
  [eia-ingest](eia-ingest.md)); `label` and `units` supply chart legends/headings.
- **Unit scaling happens here, not at ingest.** Trade series are divided by 1000
  at render time; price series are drawn raw.
- **Colours** are hard-coded per line (e.g. imports `#c0392b`, exports `#27ae60`,
  net `#2c3e50`, WTI `#c0392b`, gasoline `#d35400`, Henry Hub `#2980b9`).
- **Fixed geometry constants:** `W=900, H=300`, margins `66/16/30/34`.

## External libraries / binaries

- **stdlib only** — `math` (log/floor/ceil for nice steps), `html.escape`,
  `datetime` (UTC timestamp in the footer). No plotting library (no matplotlib /
  plotly / d3), no templating engine — SVG and HTML are built with f-strings by
  design, keeping the domain's only pip dep `requests`.

## Facets & workflows

No facet of its own — the render side of `energy.data.BuildDashboard`. Directly
unit-tested: `test_svg_chart_renders` asserts a chart contains `<svg`,
`polyline`, and the title; `test_build_dashboard` asserts the page has exactly
**6** `<svg` blocks (`html.count("<svg") == 6`), contains `"net exporter"` (the
thesis), and the provenance footer string `energy.workflows.BuildEnergyDashboard`.

## Cache / output

- Produces the `index.html` string that `build_dashboard` writes to
  `storage.output_root()/index.html` (local dir or MinIO on the fleet; published
  to GitHub Pages). Self-contained — no sidecar CSS/JS/image files.
- Does not itself touch the cache; that is [eia-ingest](eia-ingest.md).

## Gotchas & notes

- **No-JS is a hard constraint.** The page is inline SVG + inline `<style>` on
  purpose (static-host publishable). Do not add a chart library or external
  `<script>`/`<link>` — the `test_build_dashboard` SVG-count and the "no JS/CDN"
  promise in the FFL docstring would both break.
- **The dashed zero line is the story.** `zero_line=True` on the petroleum-trade
  chart is what makes the ~2019–2020 net-importer→net-exporter crossing legible;
  keep it.
- **Scaling lives at render time.** If you reuse a `points` dict elsewhere,
  remember trade values are in EIA native units until divided by 1000 here — the
  cached `eia-series.json` is unscaled.
- **`_nice` / label precision are heuristic.** Y labels switch to 2 decimals only
  when `|y1g| < 20` (price charts); large trade axes show integers. A series with
  an unusual magnitude could produce awkward ticks.

## Related specs

- [eia-ingest](eia-ingest.md) — supplies the `points` dicts and `units`.
- [dashboard](dashboard.md) — the facet/workflow that invokes rendering and
  persists the HTML.
- [storage](storage.md) — where `index.html` lands.
