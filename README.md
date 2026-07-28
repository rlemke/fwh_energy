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

## FFL at a glance

The domain is driven from [FFL](https://github.com/rlemke/facetwork/blob/main/docs/reference/language/grammar.md),
Facetwork's workflow language. A step is `name = Facet(args)`, and later steps
reference earlier ones as `step.field`:

```ffl
namespace my.energy {

    use energy.data

    /** Rebuild the dashboard, optionally re-downloading the EIA bulk files. */
    workflow RefreshDashboard(force: Boolean = false) => (status: String, html_path: String, coverage: String) andThen {

        d = energy.data.BuildDashboard(force = $.force)

        yield RefreshDashboard(
            status = "completed",
            html_path = d.html_path,
            coverage = d.month_min ++ " to " ++ d.month_max)
    }
}
```

```bash
fw ffl run --primary my.ffl --library src/energy/ffl/energy.ffl \
  --workflow my.energy.RefreshDashboard --inputs '{"force": true}'
```

📖 **[docs/ffl-examples.md](docs/ffl-examples.md)** — the full example gallery:
call-time mixins (timeout/retry for the 59 MB bulk download), `catch`, `when`
guards on series coverage, wrapping the shipped workflow, and cross-domain
composition (publishing). Every snippet there is compile-checked; this domain's
single facet makes it a good place to learn the language.

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
