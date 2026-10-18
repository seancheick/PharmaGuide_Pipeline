"""
Fail-closed guard for the export's product-level banned/recalled bridge.

``build_final_db._resolver_status_in`` is the last product-level check for a
banned or recalled ingredient that the enricher's ``contaminant_data`` missed
(inactive ingredients, alias variants on actives). It used to wrap its two
loaders in ``except Exception: return False``. ``False`` is also the healthy
"no banned/recalled match" answer, so an unloadable safety index read as a
clean product at the one site that exists to catch what ``contaminant_data``
misses (architecture audit 2026-10-17: R9, C.3, D.5). Sean, 2026-10-18:
unavailable safety-reference infrastructure must never produce a false clean
result.

Each failure test makes one loader raise and asserts that the bridge raises
the same exception (so the per-product export loop quarantines the product
and a ``--strict`` build stops) and that an error-level log names the loader
that failed. The build-level test pins the integrated outcome.
"""

from __future__ import annotations

import json
import logging
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent))          # scripts/tests (helpers)
sys.path.insert(0, str(Path(__file__).parent.parent))   # scripts

import pytest

import build_final_db
from build_final_db import _resolver_status_in, has_banned_substance
from test_build_final_db import make_enriched, make_scored


class _SafetyIndexUnavailable(RuntimeError):
    """Synthetic loader failure; the type must reach the caller unchanged."""


def _raise_unavailable(*_args, **_kwargs):
    raise _SafetyIndexUnavailable("synthetic safety index failure")


def _error_messages(caplog) -> list[str]:
    return [
        rec.getMessage()
        for rec in caplog.records
        if rec.levelno >= logging.ERROR and rec.name == "build_final_db"
    ]


def test_bridge_raises_when_active_index_loader_fails(monkeypatch, caplog):
    monkeypatch.setattr(
        build_final_db, "_get_active_banned_recalled_index", _raise_unavailable
    )
    caplog.set_level(logging.ERROR, logger="build_final_db")

    with pytest.raises(_SafetyIndexUnavailable, match="synthetic safety index failure"):
        _resolver_status_in(make_enriched(), ("banned",))

    errors = _error_messages(caplog)
    assert errors, "an unloadable safety index must be logged at error level"
    assert any("_get_active_banned_recalled_index" in msg for msg in errors), errors


def test_bridge_raises_when_inactive_resolver_loader_fails(monkeypatch, caplog):
    # Let the first loader succeed from its cache so the failure is attributed
    # to the second loader, not to the index loader that wraps it.
    monkeypatch.setattr(build_final_db, "_ACTIVE_BANNED_RECALLED_INDEX", {})
    monkeypatch.setattr(
        build_final_db, "_get_shared_inactive_resolver", _raise_unavailable
    )
    caplog.set_level(logging.ERROR, logger="build_final_db")

    with pytest.raises(_SafetyIndexUnavailable, match="synthetic safety index failure"):
        _resolver_status_in(make_enriched(), ("recalled",))

    errors = _error_messages(caplog)
    assert errors, "an unloadable safety index must be logged at error level"
    assert any("_get_shared_inactive_resolver" in msg for msg in errors), errors


def test_bridge_is_quiet_and_clean_when_loaders_are_healthy(caplog):
    # Control: the clean fixture has no banned/recalled hit through either
    # contaminant_data or the resolver index, and nothing is logged.
    caplog.set_level(logging.ERROR, logger="build_final_db")

    assert _resolver_status_in(make_enriched(), ("banned", "recalled")) is False
    assert has_banned_substance(make_enriched()) is False
    assert _error_messages(caplog) == []


def test_strict_build_stops_when_safety_index_is_unavailable(tmp_path, monkeypatch):
    # Integrated outcome: a raising loader fails the product in the export
    # loop and a --strict build (the release chain's mode,
    # rebuild_dashboard_snapshot.sh) raises instead of shipping clean flags.
    enriched_dir = tmp_path / "enriched"
    scored_dir = tmp_path / "scored"
    output_dir = tmp_path / "out"
    enriched_dir.mkdir()
    scored_dir.mkdir()
    (enriched_dir / "batch.json").write_text(
        json.dumps([make_enriched()]), encoding="utf-8"
    )
    scored = make_scored()
    scored["dsld_id"] = "999"
    (scored_dir / "batch.json").write_text(json.dumps([scored]), encoding="utf-8")
    monkeypatch.setattr(
        build_final_db, "_get_shared_inactive_resolver", _raise_unavailable
    )

    with pytest.raises(ValueError, match="1 product export error"):
        build_final_db.build_final_db(
            [str(enriched_dir)],
            [str(scored_dir)],
            str(output_dir),
            str(Path(__file__).parent.parent),
            strict=True,
        )
