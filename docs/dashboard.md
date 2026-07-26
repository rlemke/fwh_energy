# Energy Dashboard (facet + workflow)

**Namespace(s):** `energy.data`, `energy.workflows` ·
**FFL:** `src/energy/ffl/energy.ffl` ·
**Handlers:** `src/energy/handlers/energy_handlers.py` ·
**Library:** `src/energy/_lib.py` (`build_dashboard`) ·
**Tests:** `tests/test_energy.py` (`test_build_dashboard`)

## Overview

This is the domain's **single capability and flagship**: build a self-contained
US energy trade & prices dashboard from EIA bulk data and write it to the cache /
published site. It answers one request — *"show me US oil, refined-product and
natural-gas imports/exports/net plus WTI, gasoline and Henry-Hub prices over
time"* — and the headline it renders is the shale-era flip from the world's
largest **net oil importer to a net exporter ~2019–2020**.

The feature is the orchestration seam: the `energy.data.BuildDashboard` event
facet (served by `energy_handlers.handle_build_dashboard`) and the
`energy.workflows.BuildEnergyDashboard` workflow that wraps it. The real work is
delegated — data acquisition to [eia-ingest](eia-ingest.md), rendering to
[svg-charts](svg-charts.md), and path resolution to [storage](storage.md). This
spec covers how those pieces are wired into a single runnable dashboard build.

## How it works

1. **Workflow entry.** `BuildEnergyDashboard(force)` (`energy.ffl`) has one step —
   `d = BuildDashboard(force = $.force)` — then `yield`s
   `(status = "completed", html_path = d.html_path, series_count = d.series_count)`.
   It is a thin single-step wrapper; all logic lives in the facet's handler.
2. **Handler.** `handle_build_dashboard(params)` calls `build_dashboard(force=bool(params.get("force")))`,
   emits a `_step_log` line at `success` (`"BuildEnergyDashboard: {n} series {min}-{max} -> {path}"`)
   or `error`, and returns the five return fields verbatim.
3. **Library.** `_lib.build_dashboard` → `download_series(force=force)` (EIA bulk
   fetch/cache; see [eia-ingest](eia-ingest.md)) → six `_svg_chart(...)` calls
   (see [svg-charts](svg-charts.md)) → `_render_html(...)` → writes `index.html`
   and a full `eia-series.json` under `storage.output_root()`. Returns a
   `DashboardResult(html_path, json_path, series_count, month_min, month_max)`.

Data shape end-to-end: `EIA bulk .zip → {key: {label, units, points{YYYYMM: float}}}
→ inline SVG strings → one HTML page`.

## Fan-out

**Single-task — no fan-out.** There is no `foreach` in the FFL; the workflow is
one `BuildDashboard` step. The input is two small keyless bulk files and the
output is one atomic HTML page, so there is nothing to shard across the fleet.
Task-list routing still applies: the facet's top-level namespace `energy` is the
queue, so an `energy` runner claims it (see the framework `task_list_routing`).

## Data & fields

The facet's return schema (from the FFL) is the contract this feature exposes:

| Return field | Type | Meaning |
|---|---|---|
| `html_path` | String | Path to the rendered `index.html` (local or `s3://…`) |
| `json_path` | String | Path to the accompanying full `eia-series.json` |
| `series_count` | Int | Number of EIA series rendered (10 when all resolve) |
| `month_min` / `month_max` | String | `YYYYMM` span of the data actually present |

`series_count` is `len(s)` — the count of series that survived extraction, so a
missing EIA series lowers it (the ingest logs a warning rather than failing; see
[eia-ingest](eia-ingest.md)). `month_min`/`month_max` are `min`/`max` over every
`YYYYMM` key across all series, or `("", "")` if empty.

## External libraries / binaries

This orchestration layer itself imports only stdlib (`os`, `typing`) plus the
in-repo `_lib`. Its transitive pip deps are `requests` (ingest) and
`facetwork.runtime.storage` / `facetwork.config` (storage). No binary
dependencies. See the delegated specs for details.

## Facets & workflows

| Facet / workflow | Kind | Effect / Cost / Timeout | Signature → purpose |
|---|---|---|---|
| `energy.data.BuildDashboard(force: Boolean = false)` | **event** | `Effect(kind="external")` · `Cost(tier="moderate")` · `Timeout(minutes=10)` | ⇒ `(html_path, json_path: String, series_count: Int, month_min, month_max: String)`. "Download the EIA bulk energy series (keyless) and render the trade+prices dashboard (inline-SVG charts, no JS/CDN)." |
| `energy.workflows.BuildEnergyDashboard(force: Boolean = false)` | workflow | — | ⇒ `(status: String, html_path: String, series_count: Int)`. "Build the US energy trade + prices dashboard (EIA)." Single `andThen` step over `BuildDashboard`. |

`BuildDashboard` is the only event facet in the domain. It is registered by
`register_handlers(runner)` (and `register_poller(poller)`) via the `_DISPATCH`
map `{"energy.data.BuildDashboard": handle_build_dashboard}`; the package's
`DomainPackage(register_handlers=register_all_registry_handlers)` wires it into
the RegistryRunner. `handle(payload)` dispatches on `payload["_facet_name"]` and
raises `ValueError("Unknown facet: …")` for anything else.

## Cache / output

- **Output** — `index.html` + `eia-series.json` written under
  `storage.output_root()`: `s3://…/cache/energy/output/` on the fleet (MinIO),
  or the local `energy-output/` dir off `FW_DATA_ROOT` in terminal use. On the
  fleet this HTML is what gets published to
  `rlemke.github.io/facetwork-maps/us/energy-trade/` (per the repo README).
- **Cache** — the compact intermediate `eia-series.json` lives separately under
  `storage.cache_root()`; see [storage](storage.md) and [eia-ingest](eia-ingest.md).
- The page is fully self-contained (inline `<style>` + inline SVG, no JS, no CDN),
  so it renders from any static host with no assets.

## Gotchas & notes

- **`force` re-downloads.** `force=true` bypasses the `eia-series.json` cache and
  re-fetches ~63 MB of bulk zips from EIA — use it only when the upstream data
  changed. The default `false` reuses the cache.
- **The workflow drops two return fields.** `BuildEnergyDashboard` surfaces only
  `status`, `html_path`, `series_count`; `json_path`, `month_min`, `month_max`
  are available on the facet return but not re-yielded by the workflow. Callers
  that need the month span should read the facet step, not the workflow yield.
- **10-minute timeout.** `Timeout(minutes=10)` bounds the whole build including
  the ~63 MB download; on a slow link a cold (`force`/empty-cache) run can press
  against it. Warm runs (cache hit) finish in well under a second.
- **One facet, one handler.** There is no additional handler surface here — do
  not expect per-series or per-chart facets; the dashboard is built atomically.

## Related specs

- [eia-ingest](eia-ingest.md) — where `download_series` gets the data.
- [svg-charts](svg-charts.md) — how the six charts + HTML page are rendered.
- [storage](storage.md) — how `html_path` / `json_path` are resolved on fleet vs
  local.
