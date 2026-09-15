"""Read-only calibration must reject an empty or malformed success report."""

import hashlib
import importlib.util
import json
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[2]
SPEC = importlib.util.spec_from_file_location(
    "calibration_replay", ROOT / "scripts/audits/scoring_boundary_audit_2026_09_15/replay.py"
)
replay = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(replay)


@pytest.fixture
def corpus(tmp_path, monkeypatch):
    import score_supplements_v4
    import scoring_v4.router
    from scoring_v4.quality_score import _config

    path = tmp_path / "output_example_enriched/enriched/one.json"
    path.parent.mkdir(parents=True)
    path.write_text(json.dumps([{"dsld_id": "1", "route": "probiotic"},
                                {"dsld_id": "2", "route": "generic"}]))
    result = {
        "quality_score_status": "scored", "quality_score_v4_100": 100.0,
        "quality_pillars_v4": {k: {"score": v["weight"]} for k, v in _config()["pillars"].items()},
        "v4_breakdown": {"module": {"dimensions": {
            "formulation": {"score": 16}, "dose": {"score": 22},
            "transparency": {"score": 15},
        }}},
    }
    monkeypatch.setattr(scoring_v4.router, "class_for_product", lambda p: p["route"])
    calls = []

    def score(product):
        calls.append(product["dsld_id"])
        return result

    monkeypatch.setattr(score_supplements_v4, "score_product_v4", score)
    # snapshot imports a requested checkout; restore the test process's path.
    monkeypatch.setattr(replay.sys, "path", list(replay.sys.path))
    return tmp_path, path, result, calls


def test_snapshot_uses_scorer_only_for_requested_category_and_keeps_input(corpus):
    root, path, result, calls = corpus
    before = path.read_bytes()
    report = replay.snapshot_category(ROOT, root)
    assert calls == ["1"]
    assert report["_meta"]["routes"] == {"probiotic": 1, "generic": 1}
    assert report["_meta"]["count"] == 1
    assert report["_meta"]["input_files"][0]["sha256"] == hashlib.sha256(before).hexdigest()
    assert report["products"]["1"]["pillars"] == result["quality_pillars_v4"]
    assert report["products"]["1"]["dimensions"]["formulation"] == {"score": 16}
    assert path.read_bytes() == before


@pytest.mark.parametrize("defect", ["null", "bool", "nan", "infinity", "over", "missing_pillar", "over_pillar", "bad_status"])
def test_snapshot_refuses_invalid_public_score(corpus, defect):
    root, _, result, _ = corpus
    if defect == "missing_pillar":
        result["quality_pillars_v4"].pop("dose")
    elif defect == "over_pillar":
        result["quality_pillars_v4"]["dose"]["score"] = 21
    elif defect == "bad_status":
        result["quality_score_status"] = "ok"
    else:
        result["quality_score_v4_100"] = {
            "null": None, "bool": True, "nan": float("nan"),
            "infinity": float("inf"), "over": 101,
        }[defect]
    with pytest.raises(ValueError, match="Invalid status|Incomplete public score"):
        replay.snapshot_category(ROOT, root)


@pytest.mark.parametrize("contents, message", [
    ([], "No scored"),
    ({"error": "not a batch"}, "Unexpected batch shape"),
    ([None], "Malformed product"),
    ([{"dsld_id": "1", "route": "generic"}], "No scored"),
    ([{"route": "probiotic"}], "Missing/duplicate"),
    ([{"dsld_id": "1", "route": "probiotic"}] * 2, "Missing/duplicate"),
])
def test_snapshot_refuses_empty_invalid_and_duplicate_inputs(corpus, contents, message):
    root, path, _, _ = corpus
    path.write_text(json.dumps(contents))
    with pytest.raises(ValueError, match=message):
        replay.snapshot_category(ROOT, root)


def test_snapshot_keeps_unscored_products_without_inventing_a_number(corpus, monkeypatch):
    import score_supplements_v4

    root, path, scored, _ = corpus
    path.write_text(json.dumps([{"dsld_id": "1", "route": "probiotic"},
                                {"dsld_id": "2", "route": "probiotic"}]))
    unscored = {"quality_score_status": "not_scored", "quality_score_v4_100": None}
    monkeypatch.setattr(score_supplements_v4, "score_product_v4",
                        lambda p: scored if p["dsld_id"] == "1" else unscored)
    report = replay.snapshot_category(ROOT, root)
    assert report["products"]["2"]["score"] is None
    assert report["products"]["2"]["status"] == "not_scored"
    unscored["quality_score_v4_100"] = 0
    with pytest.raises(ValueError, match="Unexpected public number"):
        replay.snapshot_category(ROOT, root)


def test_snapshot_refuses_missing_module_breakdown(corpus):
    root, _, result, _ = corpus
    result.pop("v4_breakdown")
    with pytest.raises(ValueError, match="Missing module dimensions"):
        replay.snapshot_category(ROOT, root)


def test_category_selection_reuses_the_same_replay_and_scorer(corpus):
    root, path, _, calls = corpus
    before = path.read_bytes()
    report = replay.snapshot_category(ROOT, root, "generic")
    assert calls == ["2"]
    assert set(report["products"]) == {"2"}
    assert report["_meta"]["category"] == "generic"
    assert path.read_bytes() == before


def test_category_replay_rejects_a_changed_checkout(corpus, monkeypatch):
    root, _, _, _ = corpus
    original = replay.subprocess.run
    calls = 0

    def git_changed(args, **kwargs):
        nonlocal calls
        result = original(args, **kwargs)
        if args[-2:] == ["rev-parse", "HEAD"]:
            calls += 1
            if calls > 1:
                result.stdout = b"different-commit\n"
        return result

    monkeypatch.setattr(replay.subprocess, "run", git_changed)
    with pytest.raises(ValueError, match="Checkout changed"):
        replay.snapshot_category(ROOT, root, "generic")
