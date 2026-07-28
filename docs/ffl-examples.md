# FFL Examples — `energy`

Every numbered scenario is a **complete, compilable FFL file**. Copy one into
`my.ffl` and run it:

```bash
fw ffl run --primary my.ffl \
  --library ~/fw_handlers/fwh_energy/src/energy/ffl/energy.ffl \
  --workflow my.energy.<WorkflowName>
```

A runner serving the `energy` namespace must be up
(`fw runner start --domain energy`). Every block below is compile-checked against
`src/energy/ffl/energy.ffl`.

New to the language? Start with the
[FFL grammar](https://github.com/rlemke/facetwork/blob/main/docs/reference/language/grammar.md)
and the [canonical examples](https://github.com/rlemke/facetwork/tree/main/examples/canonical).

---

## The facets at a glance

This domain is deliberately small — one event facet and the workflow that wraps
it — which makes it a good place to learn the language without a 20-facet pipeline
in the way.

| Declaration | Signature | Does |
|---|---|---|
| `energy.data.BuildDashboard` | `(force: Boolean = false) => (html_path, json_path, series_count, month_min, month_max)` | Download EIA bulk series (keyless) → render the inline-SVG dashboard |
| `energy.workflows.BuildEnergyDashboard` | `(force: Boolean = false) => (status, html_path, series_count)` | The shipped entry point |

`BuildDashboard` is an `event facet`: it runs in a handler on a runner, not in the
compiler. Its `with Effect(kind = "external")` / `with Cost(tier = "moderate")`
mixins are what `fw_capabilities(effect=…, max_cost=…)` filters on.

---

## 1. Run what ships — no FFL to write

```bash
fw ffl seed --include energy

fw ffl run --primary ~/fw_handlers/fwh_energy/src/energy/ffl/energy.ffl \
  --workflow energy.workflows.BuildEnergyDashboard \
  --inputs '{"force": false}'
```

`force = true` re-downloads the EIA bulk zips (~63 MB) instead of using the cache.
Write FFL when you want a different shape of run — your own error handling, a
freshness guard, or composition with another domain.

## 2. The smallest workflow you can write

Every FFL workflow needs a `namespace`, a `use` per namespace it calls into, and a
`yield` back to itself.

```ffl
namespace my.energy {

    use energy.data

    /** Build the EIA trade + prices dashboard. */
    workflow MyDashboard() => (html_path: String, series: Int) andThen {

        d = energy.data.BuildDashboard(force = false)

        yield MyDashboard(html_path = d.html_path, series = d.series_count)
    }
}
```

Three rules visible above: `=>` sits on the **same line** as the closing `)` of the
parameter list; references are always `step.field` (never a bare step name); and a
workflow ends by yielding to itself.

## 3. Parameters and `$`

`$` means "my immediate container" — inside a workflow body that's the workflow, so
`$.force` is its parameter. `$$` walks one level out (into an enclosing block).

```ffl
namespace my.energy {

    use energy.data

    /** Rebuild, optionally re-downloading the EIA bulk files. */
    workflow RefreshDashboard(force: Boolean = false) => (status: String, html_path: String, coverage: String) andThen {

        d = energy.data.BuildDashboard(force = $.force)

        yield RefreshDashboard(
            status = "completed",
            html_path = d.html_path,
            coverage = d.month_min ++ " to " ++ d.month_max)
    }
}
```

Run with `--inputs '{"force": true}'`. Note `++` — string concatenation, used here
to build a coverage string out of two step results.

## 4. Call-time mixins — timeouts and retries

The facet declares its own defaults (`with Timeout(minutes = 10)`); the **call
site** can add or override mixins for one particular use without forking it. `PET.zip`
is ~59 MB, so a slow link wants more room.

```ffl
namespace my.energy {

    use energy.data

    /** Give the bulk download more time, and retry transient EIA failures. */
    workflow ResilientDashboard() => (html_path: String) andThen {

        d = energy.data.BuildDashboard(force = true) with Timeout(minutes = 40) with Retry(maxAttempts = 3, backoffSeconds = 60)

        yield ResilientDashboard(html_path = d.html_path)
    }
}
```

## 5. Survive a failed download — `catch`

`catch` runs when its step errors after retries are exhausted. Yielding from the
catch block ends the run with a partial result instead of a hard failure.

```ffl
namespace my.energy {

    use energy.data

    /** Report a partial result rather than failing the run. */
    workflow BestEffortDashboard() => (status: String, html_path: String) andThen {

        d = energy.data.BuildDashboard(force = true) catch {
            yield BestEffortDashboard(status = "eia_download_failed", html_path = "")
        }

        yield BestEffortDashboard(status = "completed", html_path = d.html_path)
    }
}
```

## 6. Branch on a result — `when`

A `when` block hangs off the step it inspects: inside a case `$` is that step, and
`$$` reaches the workflow's parameters. Every `when` needs a default case, and it
must come last. There is no truthy coercion — the condition must be a real
`Boolean`.

```ffl
namespace my.energy {

    use energy.data

    /** Only call it good if every expected series came through. */
    workflow VerifiedDashboard(expected_series: Int = 10) => (status: String, html_path: String) andThen {

        d = energy.data.BuildDashboard() andThen when {
            case $.series_count >= $$.expected_series => {
                yield VerifiedDashboard(status = "complete", html_path = $.html_path)
            }
            case _ => {
                yield VerifiedDashboard(status = "partial_series", html_path = $.html_path)
            }
        }
    }
}
```

## 7. Reuse the shipped workflow

Workflows compose like facets — wrap `BuildEnergyDashboard` rather than forking it.

```ffl
namespace my.energy {

    use energy.workflows

    /** Wrap the shipped workflow and reshape its result. */
    workflow DashboardWithHeadline() => (headline: String) andThen {

        built = energy.workflows.BuildEnergyDashboard(force = false)

        yield DashboardWithHeadline(headline = "energy dashboard: " ++ built.status)
    }
}
```

## 8. Compose across domains — publish the dashboard

Facets from different domains compose in one workflow as long as some runner in
the fleet serves each namespace. `census.Publish` is the generic publisher the
map/dashboard domains share.

```ffl
namespace my.energy {

    use energy.data
    use census.Publish

    /** Build, then push to the public site. */
    workflow DashboardPublish(repo: String = "rlemke/facetwork-maps") => (pages_url: String) andThen {

        d = energy.data.BuildDashboard()

        published = census.Publish.PublishWebBundle(
            repo = $.repo,
            prefixes = ["energy/output"],
            dests = ["us/energy-trade"],
            labels = ["US energy trade & prices"],
            landing_title = "Facetwork maps")

        yield DashboardPublish(pages_url = published.pages_url)
    }
}
```

Compile that one with `--library ~/fw_handlers/fwh_census_us/src/census_us/ffl/census.ffl`
as well.

---

## Cheat sheet

| You want to… | Write |
|---|---|
| Read a workflow/step parameter | `$.name` (`$$.name` one level out) |
| Read a previous step's result | `stepname.field` |
| Order two independent steps | reference a field of the first from the second |
| More time / retries for one call | `… with Timeout(minutes = 40) with Retry(maxAttempts = 3, backoffSeconds = 60)` |
| Handle a step failure | `step = Facet(…) catch { yield … }` |
| Branch | `step = Facet(…) andThen when { case <bool> => { … } case _ => { … } }` |
| Fan out over a list | `workflow W(items: Json) … andThen foreach i in $.items { … }` |
| Concatenate strings | `a ++ b` |

**Validate before you run:** `afl my.ffl --check` or MCP `fw_validate`. Every error
carries a `rule_id` — fetch `fw://docs/rules/{rule_id}` for a wrong/right pair.

## See also

- [`docs/README.md`](README.md) — per-feature specs for this domain
- [`docs/dashboard.md`](dashboard.md) — what the single facet actually does
- [FFL grammar](https://github.com/rlemke/facetwork/blob/main/docs/reference/language/grammar.md) ·
  [canonical examples](https://github.com/rlemke/facetwork/tree/main/examples/canonical) ·
  [relative `$`-scoping](https://github.com/rlemke/facetwork/blob/main/docs/architecture/ffl-relative-scoping.md)
- `src/energy/ffl/energy.ffl` — the source of truth for every signature above
