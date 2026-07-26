# EIA Bulk Data Ingest (keyless)

**Namespace(s):** `energy.data` (data side) ·
**Library:** `src/energy/_lib.py` (`download_series`, `_extract`, `PET_SERIES`, `NG_SERIES`) ·
**Storage:** `src/energy/storage.py` ·
**Tests:** `tests/test_energy.py` (download mocked)

## Overview

This feature acquires the raw numbers behind the dashboard. It fetches the EIA
**bulk** data files — **keyless**, unlike the EIA API v2 which needs a free
key — extracts only the ~10 US-total monthly series the dashboard charts, and
caches a compact result so subsequent builds skip the multi-tens-of-megabytes
download.

The keyless bulk route is the whole point of the domain's data story: `PET.zip`
(~59 MB) and `NG.zip` (~4 MB) from `www.eia.gov/opendata/bulk/`, each an NDJSON
file with one series per line. This sits at the head of the pipeline —
everything downstream ([svg-charts](svg-charts.md), [dashboard](dashboard.md))
consumes its `{key: {label, units, points}}` output.

## How it works

`download_series(*, force=False)` (`_lib.py`):

1. **Cache check.** Computes `cache_key = storage.join(cache_root(), "eia-series.json")`.
   If not `force` and `storage.exists(cache_key)`, loads and returns the cached
   dict immediately (no network).
2. **Guard.** If `requests` failed to import, raises
   `RuntimeError("requests is required to fetch EIA bulk data")`.
3. **Fetch two zips.** For `("PET", PET_SERIES)` and `("NG", NG_SERIES)`: HTTP
   `GET {BULK}/{name}.zip` with a `User-Agent` header and `timeout=(30, 300)`
   (connect, read), `raise_for_status()`, then `series.update(_extract(resp.content, wanted))`.
4. **`_extract(zip_bytes, wanted)`.** Opens the zip in memory, finds the single
   `.txt` member, iterates it line-by-line as UTF-8, `json.loads` each line
   (skipping parse errors), and keeps only lines whose `series_id` is in the
   wanted set. For each kept series it walks `d["data"]` rows `[YYYYMM, value]`,
   keeping points where `len(ym) == 6`, `val is not None`, and
   `int(ym[:4]) >= YEAR_FROM` (2000). Breaks early once all wanted series are found.
5. **Missing warning.** Any wanted series not found is logged
   (`logger.warning("EIA series not found: %s", missing)`) — **not** an error.
6. **Cache write.** Dumps the compact result (`separators=(",", ":")`) to the
   cache key and returns it.

Output shape: `{key: {"label": str, "units": str, "points": {YYYYMM: float}}}`.

## Fan-out

**Single-task — no fan-out.** Two fixed URLs fetched sequentially in one process;
there is no per-region or per-series sharding. Extraction streams each NDJSON
line-by-line (`io.TextIOWrapper` over `z.open(fn)`) so the ~59 MB PET file is
never fully materialized as parsed JSON.

## Data & fields

The exact US-total monthly series pulled (all verified present in the bulk data,
per the code comment). Keys are internal; the tuple is `(EIA series_id, label)`:

**`PET_SERIES`** (petroleum, from `PET.zip`):

| Internal key | EIA series_id | Label |
|---|---|---|
| `crude_imports` | `PET.MCRIMUS2.M` | Crude oil imports |
| `crude_exports` | `PET.MCREXUS2.M` | Crude oil exports |
| `petro_imports` | `PET.MTTIMUS2.M` | Crude + products imports |
| `petro_exports` | `PET.MTTEXUS2.M` | Crude + products exports |
| `petro_net` | `PET.MTTNTUS2.M` | Net petroleum imports |
| `gasoline` | `PET.EMM_EPMR_PTE_NUS_DPG.M` | Regular gasoline (retail) |
| `wti` | `PET.RWTC.M` | WTI crude spot price |

**`NG_SERIES`** (natural gas, from `NG.zip`):

| Internal key | EIA series_id | Label |
|---|---|---|
| `ng_imports` | `NG.N9100US2.M` | Natural gas imports |
| `ng_exports` | `NG.N9130US2.M` | Natural gas exports (incl. LNG) |
| `henryhub` | `NG.RNGWHHD.M` | Henry Hub spot price |

Ten series total. `YEAR_FROM = 2000` clips history to ~2000-present (EIA carries
some of these back to the 1990s / 1920s, deliberately not used here). `units`
comes straight from the series' `units` field. Trade volumes are stored in the
EIA's native units (thousand barrels/day for petroleum, million cubic feet for
gas); the ÷1000 conversions to million bbl/day and billion cf/month happen later
at render time, not here.

## External libraries / binaries

- **`requests`** (pip, the domain's only declared dependency in `pyproject.toml`)
  — the two bulk HTTP GETs. Imported defensively (`except ImportError: requests = None`);
  a cache-hit path works without it, but a cold fetch raises `RuntimeError`.
- **`zipfile`, `io`, `json`** (stdlib) — in-memory unzip + streaming NDJSON parse.
- **`facetwork.runtime.storage`** (via `energy.storage`) — cache existence/read/write.
- No binary dependencies.

## Facets & workflows

No facet of its own — this is the data half of `energy.data.BuildDashboard`
(see [dashboard](dashboard.md)). It is exercised as a pure library function and
is the seam the tests mock (`monkeypatch.setattr(_lib, "download_series", …)`),
which is why the test suite runs fully offline.

## Cache / output

- Caches to `storage.cache_root()/eia-series.json` — the **compact** intermediate
  (`{key: {label, units, points}}`), distinct from the full `eia-series.json`
  that `build_dashboard` also writes under `output_root()` for provenance.
- On the fleet the cache lives at `s3://…/cache/energy/cache/eia-series.json`
  (MinIO); locally at `energy-cache/eia-series.json` off `FW_DATA_ROOT`. See
  [storage](storage.md).
- `force=True` ignores and overwrites the cache.

## Gotchas & notes

- **Bulk, not API.** Do not "modernize" this to the EIA API v2 — that requires a
  free API key and defeats the domain's keyless design. The bulk zips need no
  auth. (Repo memory note: "EIA gold standard, KEYLESS via bulk zips (NDJSON)".)
- **~63 MB per cold run.** A cache miss (or `force`) downloads both zips every
  time; keep the cache warm. The read timeout is 300 s.
- **Missing series degrade, not fail.** If EIA renames or drops a series_id, that
  series silently vanishes from the output and `series_count` drops — check the
  `"EIA series not found"` warning rather than assuming a crash.
- **First `.txt` member assumption.** `_extract` takes `next(n for n in z.namelist() if n.endswith(".txt"))` —
  it assumes exactly one `.txt` in each bulk zip (true today); a multi-`.txt`
  layout would need revisiting.
- **US-total only.** Every series here is a national aggregate (`…US…`); the
  domain deliberately does not attempt per-state or global trade (the repo README
  notes global data is patchier — UN Comtrade coarse, IEA paywalled).

## Related specs

- [dashboard](dashboard.md) — the facet/workflow that calls `download_series`.
- [svg-charts](svg-charts.md) — consumes the `points` dicts, applies unit scaling.
- [storage](storage.md) — the cache backend this reads/writes through.
