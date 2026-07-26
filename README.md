# fwh_energy

A Facetwork domain that builds a **US energy trade & prices dashboard** — a
self-contained page of inline-SVG time-series charts (no JS, no CDN) from the
[EIA](https://www.eia.gov/opendata/) bulk data:

- **Trade** — imports, exports & net for crude oil, refined products, and natural
  gas, monthly ~2000–present (showing the US flip from the world's biggest net
  oil importer to a **net exporter ~2019–2020**, the shale story).
- **Prices** — WTI crude ($/bbl), regular gasoline ($/gal), Henry Hub gas ($/MMBtu),
  through the 2008 spike, 2014 collapse, 2020 COVID crash, and 2022 Ukraine surge.

**Live:** [rlemke.github.io/facetwork-maps/us/energy-trade](https://rlemke.github.io/facetwork-maps/us/energy-trade/)

## Feature specifications

Per-feature specs live under [`docs/`](docs/README.md) — how each part works, what
data it touches, its facets, and its cache/output:

| Spec | What it covers |
|------|----------------|
| [docs/dashboard.md](docs/dashboard.md) | **Flagship** — the `BuildDashboard` facet + `BuildEnergyDashboard` workflow (the runnable dashboard build). |
| [docs/eia-ingest.md](docs/eia-ingest.md) | Keyless EIA bulk acquisition (`PET.zip`/`NG.zip` NDJSON → the 10 US-total series). |
| [docs/svg-charts.md](docs/svg-charts.md) | The self-contained inline-SVG chart renderer (no JS/CDN). |
| [docs/storage.md](docs/storage.md) | Backend-aware cache/output (local dir vs MinIO/S3). |

See [`docs/README.md`](docs/README.md) for the full index.

## Data

- **EIA bulk files — keyless** (`www.eia.gov/opendata/bulk/`): `PET.zip` (~59 MB)
  + `NG.zip` (~4 MB), each an NDJSON of one series per line. Downloaded once,
  target US-total monthly series extracted + cached. (The EIA API v2 needs a free
  key; the bulk route does not.) US Government public domain.
- Global energy trade is patchier (UN Comtrade coarse; IEA mostly paywalled) — so
  this is US-focused, where EIA is comprehensive and clean.

## Workflow

```
energy.workflows.BuildEnergyDashboard
  └─ energy.data.BuildDashboard   # fetch EIA bulk → extract series → SVG dashboard
```

## Run

```bash
pip install -e .            # requests only
python -m pytest tests/ -q  # offline (EIA download mocked)
```
