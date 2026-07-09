"""Event facet handlers for the energy domain — thin layers over ``_lib``."""

from __future__ import annotations

import os
from typing import Any

from .._lib import build_dashboard

DATA = "energy.data"


def handle_build_dashboard(params: dict[str, Any]) -> dict[str, Any]:
    step_log = params.get("_step_log")
    try:
        res = build_dashboard(force=bool(params.get("force")))
        if step_log:
            step_log(f"BuildEnergyDashboard: {res.series_count} series {res.month_min}-"
                     f"{res.month_max} -> {res.html_path}", level="success")
        return {"html_path": res.html_path, "json_path": res.json_path,
                "series_count": res.series_count,
                "month_min": res.month_min, "month_max": res.month_max}
    except Exception as exc:
        if step_log:
            step_log(f"BuildEnergyDashboard: {exc}", level="error")
        raise


_DISPATCH: dict[str, Any] = {f"{DATA}.BuildDashboard": handle_build_dashboard}


def handle(payload: dict) -> dict:
    facet = payload["_facet_name"]
    handler = _DISPATCH.get(facet)
    if handler is None:
        raise ValueError(f"Unknown facet: {facet}")
    return handler(payload)


def register_handlers(runner) -> None:
    for facet_name in _DISPATCH:
        runner.register_handler(facet_name=facet_name,
            module_uri=f"file://{os.path.abspath(__file__)}", entrypoint="handle")


def register_poller(poller) -> None:
    for facet_name, handler in _DISPATCH.items():
        poller.register(facet_name, handler)
