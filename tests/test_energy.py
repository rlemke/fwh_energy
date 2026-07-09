"""Offline tests for the energy dashboard — EIA download mocked, no network."""

from __future__ import annotations

import pytest


@pytest.fixture()
def local_storage(tmp_path, monkeypatch):
    monkeypatch.setenv("FW_STORAGE", "local")
    monkeypatch.setenv("FW_DATA_ROOT", str(tmp_path))
    yield tmp_path


def _fake_series():
    def ser(label, units, base):
        return {"label": label, "units": units,
                "points": {f"{y}{m:02d}": base + (y - 2010) + m * 0.1
                           for y in range(2010, 2018) for m in range(1, 13)}}
    from energy import _lib
    return {k: ser(lbl, "u", 100 + i * 10) for i, (k, (_id, lbl)) in
            enumerate({**_lib.PET_SERIES, **_lib.NG_SERIES}.items())}


def test_svg_chart_renders():
    from energy import _lib
    svg = _lib._svg_chart("Test", "unit",
                          [("A", "#c00", {"201001": 5.0, "201512": 8.0, "201706": 3.0})],
                          zero_line=True)
    assert "<svg" in svg and "polyline" in svg and "Test" in svg


def test_build_dashboard(local_storage, monkeypatch):
    from energy import _lib
    monkeypatch.setattr(_lib, "download_series", lambda force=False: _fake_series())
    res = _lib.build_dashboard(force=True)
    assert res.series_count == len(_lib.PET_SERIES) + len(_lib.NG_SERIES)
    html = open(_lib.cstore.localize(res.html_path)).read()
    assert "US energy trade" in html
    assert html.count("<svg") == 6           # 3 trade + 3 price charts
    assert "net exporter" in html.lower()    # the thesis
    assert "energy.workflows.BuildEnergyDashboard" in html  # provenance footer
