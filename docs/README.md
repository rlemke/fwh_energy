# Energy (fwh_energy) — Feature Specifications

This directory holds one **spec per feature** of the `energy` domain — the
Facetwork pipeline that builds a US energy trade & prices dashboard from EIA
keyless bulk data. Each document follows a common shape
([`SPEC_TEMPLATE.md`](SPEC_TEMPLATE.md)) and states, for that feature: how it
works, whether it **fans out** (this domain is single-task), what **data/fields**
it touches (real EIA series IDs), the **external libraries** it relies on, its
**facets & workflows**, and its **cache/output**. Claims are grounded in the FFL
`/** … */` docstrings, `_lib.py`, `storage.py`, and the tests — the source of
truth for the facet remains its FFL docstring; these specs are the feature-level
narrative over them.

**Start here:** [**Energy Dashboard**](dashboard.md) — the flagship (and only)
capability: the `energy.data.BuildDashboard` event facet + the
`energy.workflows.BuildEnergyDashboard` workflow that produce the published page.

## The pipeline

| Spec | What it covers |
|------|----------------|
| [dashboard.md](dashboard.md) | **Flagship.** The `BuildDashboard` event facet + `BuildEnergyDashboard` workflow; return schema, `Effect`/`Cost`/`Timeout` mixins, handler wiring, and how the ingest/render/storage pieces are composed into one atomic build. |
| [eia-ingest.md](eia-ingest.md) | Keyless EIA **bulk** acquisition: `PET.zip`/`NG.zip` NDJSON → the 10 US-total monthly series (real series IDs), `YEAR_FROM=2000` clipping, `requests` fetch, compact caching. |
| [svg-charts.md](svg-charts.md) | The self-contained inline-SVG renderer (no JS/CDN): `_svg_chart` primitives, the six trade+price charts, unit scaling, and the HTML page with thesis callout + provenance footer. |
| [storage.md](storage.md) | Backend-aware cache/output shim: local dir vs MinIO/S3, `cache_root`/`output_root` layout, the stage-local-finalize-on-close write pattern. |
| [ffl-examples.md](ffl-examples.md) | **Usage patterns.** A gallery of complete, compile-checked FFL examples over this domain's facet — minimal workflow, `$`-scoping, call-time mixins, `catch`, `when`, wrapping the shipped workflow, cross-domain publish. |

---

*See also the repo [`README.md`](../README.md) (intro, data provenance, run
instructions) and the FFL source [`src/energy/ffl/energy.ffl`](../src/energy/ffl/energy.ffl)
(the authoritative facet/workflow docstrings). The live/queryable interface is
the MCP `fw_capabilities` / `fw_describe_handler` tools.*
