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
