# Backend-aware Cache & Output Storage

**Namespace(s):** infrastructure (all `energy.*`) ·
**Module:** `src/energy/storage.py` ·
**Consumers:** `src/energy/_lib.py` (`download_series`, `build_dashboard`) ·
**Tests:** `tests/test_energy.py` (`local_storage` fixture, `cstore.localize`)

## Overview

A thin path/IO shim so the same code writes to a local directory in terminal use
and to the shared MinIO/S3 object store on the fleet — with no conditionals in
the ingest or render code. It is the same shape census-us / save-earth use, and
it wraps `facetwork.runtime.storage` so terminal runs and fleet runs share **one**
cache rooted at `$FW_DATA_ROOT/cache/energy/`.

Every path the domain produces (`html_path`, `json_path`, the cache key) is
resolved through this module. It is invisible to the FFL but load-bearing for the
"works locally and on the fleet unchanged" property.

## How it works

- **Root selection.** `_data_root()` = `FW_DATA_ROOT` or `get_output_base()`.
  `is_remote(path)` is just `"://" in path`.
- **`cache_root()`** — `FW_ENERGY_CACHE_DIR` override, else for a remote root
  `join(root, "cache", "energy", "cache")`, else local `join(root, "energy-cache")`.
- **`output_root()`** — `FW_ENERGY_OUTPUT_DIR` override, else remote
  `join(root, "cache", "energy", "output")`, else local `join(root, "energy-output")`.
- **`join(*parts)`** — URL/path-safe join (rstrip/strip slashes), works for both
  `s3://…` and POSIX paths.
- **`exists(path)`** — delegates to `_fws.get_storage_backend(path).exists(path)`.
- **`localize(path)`** — returns the path unchanged if local, else
  `_fws.localize(path)` (pulls the object to a local temp file for reading).
- **`open_read(path, mode="r")`** — `open(localize(path), mode)`.
- **`open_write(path, mode="w")`** (contextmanager) — **local:** `os.makedirs`
  the parent, open directly. **Remote:** write to a `tempfile.mkstemp` scratch
  file, then on close stream it into `get_storage_backend(path).open(path, "wb")`.
  This is the object-store "stage-local, finalize-on-close" pattern (object stores
  do not do partial writes), and the temp file is always unlinked in `finally`.

## Fan-out

Not applicable — a stateless path/IO helper. It is what *lets* any runner on any
host resolve the same `s3://` cache, but it does no orchestration itself. (Section
kept per template; genuinely N/A.)

## Data & fields

No domain data of its own. It handles opaque byte/text streams for two artifacts:
the compact cache `eia-series.json` (under `cache_root()`) and the published
`index.html` + full `eia-series.json` (under `output_root()`). See
[eia-ingest](eia-ingest.md) and [dashboard](dashboard.md) for those contents.

## External libraries / binaries

- **`facetwork.runtime.storage`** (`_fws`) — the backend registry
  (`get_storage_backend`, `localize`); this is where `local` / `s3://` / `hdfs://`
  selection actually lives.
- **`facetwork.config.get_output_base`** — the default root when `FW_DATA_ROOT`
  is unset.
- **stdlib** — `os`, `tempfile`, `contextlib`. No binary deps.

## Facets & workflows

None — infrastructure module, no FFL surface. Not registered as a handler.

## Cache / output

This *is* the cache/output layer. Resolved layout:

| Env | Cache | Output |
|---|---|---|
| Fleet (`FW_DATA_ROOT=s3://afl-cache`) | `s3://afl-cache/cache/energy/cache/eia-series.json` | `s3://afl-cache/cache/energy/output/{index.html, eia-series.json}` |
| Local (e.g. `FW_DATA_ROOT=/tmp/x`) | `/tmp/x/energy-cache/eia-series.json` | `/tmp/x/energy-output/{index.html, eia-series.json}` |
| Override | `FW_ENERGY_CACHE_DIR` | `FW_ENERGY_OUTPUT_DIR` |

The test `local_storage` fixture sets `FW_STORAGE=local` + `FW_DATA_ROOT=tmp_path`
and reads the result back through `cstore.localize`.

## Gotchas & notes

- **Stale module docstring.** `storage.py`'s docstring still describes "the cached
  UCDP aggregate + world geometry + the rendered map HTML" — copy-pasted from the
  `conflict` domain. The *code* is correct and generic; the prose is wrong. (Docs
  only — noted here rather than edited; a maintainer should fix the docstring.)
- **`eia-series.json` appears twice, intentionally.** The one under `cache_root()`
  is the compact download cache; the one under `output_root()` is written next to
  `index.html` for provenance. Different roots, same filename — do not assume one.
- **Keep scratch local.** The remote `open_write` stages through a local temp file
  because object stores can't do partial writes; this relies on a writable local
  temp dir (`tempfile.mkstemp`).
- **`is_remote` is purely string-based** (`"://" in path`) — a local path
  containing `"://"` would misroute, but that does not occur in practice.

## Related specs

- [eia-ingest](eia-ingest.md) — reads/writes the cache through this module.
- [dashboard](dashboard.md) — writes the published outputs through `output_root()`.
- [svg-charts](svg-charts.md) — produces the HTML this module persists.
