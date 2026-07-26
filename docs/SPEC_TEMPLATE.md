<!-- SPEC TEMPLATE — every docs/<feature>.md follows this shape so the set reads
consistently. Delete this comment in real specs. Keep sections in this order;
omit a section only if it genuinely does not apply (say so in one line rather
than dropping the heading silently). Ground every claim in the actual FFL
docstrings / handler code / storage helpers — do not invent behaviour. For this
domain the concrete vocabulary is EIA bulk series (e.g. `PET.MCRIMUS2.M`,
`NG.RNGWHHD.M`), inline-SVG charts, and the `energy/` cache namespace — swap in
real IDs, not placeholders. -->

# <Feature Name>

**Namespace(s):** `energy.<ns>` · **FFL:** `src/energy/ffl/energy.ffl` ·
**Handlers:** `src/energy/handlers/energy_handlers.py` · **Library:** `src/energy/_lib.py` · **Storage:** `src/energy/storage.py`

## Overview
One or two paragraphs: what this feature is for, the request it answers, and where
it sits in the pipeline (bulk download → series extract → SVG render → publish).

## How it works
The algorithm / data flow, step by step. Name the concrete functions and the shape
of the data at each (bulk `.zip` → NDJSON lines → `{key: {label, units, points}}`
→ inline SVG → HTML page). If there is a source/render split, say so.

## Fan-out
Does it fan out across the fleet? If yes: what is the fan-out unit and which facet
drives it. This domain is single-task (one dashboard build) — if so, say
"single-task — no fan-out" and why (small keyless input, one atomic page).

## Data & fields
What data it reads and the concrete fields/series involved — be specific (real EIA
series IDs like `PET.MTTNTUS2.M`, the `{label, units, points}` cache shape, the
`YEAR_FROM` cutoff, units conversions). Name the mechanism (bulk NDJSON extract,
`_svg_chart` polylines, etc.). If the feature does no data selection, say so.

## External libraries / binaries
Every non-stdlib dependency this feature relies on and what for — e.g. `requests`
(EIA bulk HTTP GET), `facetwork.runtime.storage` (backend I/O). Distinguish a
**binary** dependency from a **pip** one. Note where the code degrades gracefully
if a dep is absent (`requests is None`).

## Facets & workflows
The key event facets and workflows, with signatures and a one-line purpose taken
from the FFL docstrings. Mark event facets (need a handler) vs pure facets, and
note `Effect` / `Cost` / `Timeout` mixins where present.

## Cache / output
The cache namespace under `$FW_DATA_ROOT/cache/energy/` (or the local
`energy-cache` / `energy-output` dirs) and the artifact(s) + format (compact
`eia-series.json`, self-contained `index.html`). Note whether outputs go to local
disk, MinIO/S3, or the published site.

## Gotchas & notes
Known pitfalls, rate limits, sensitivity caveats, or non-obvious constraints
(worth capturing anything a future maintainer would trip on).

## Related specs
Links to the specs this feature composes with or depends on.
