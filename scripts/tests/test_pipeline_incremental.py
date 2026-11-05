"""Selective execution must match full output and fail closed on invalid reuse."""
from copy import deepcopy
import json

import pytest

from pipeline_incremental import digest, plan_changes


def baseline():
    return {
        "raw": {"1": digest({"id": "1"}), "2": digest({"id": "2"})},
        "stages": {stage: {"stage_code_sha256_v1": "code", "reference_data_sha256_v1": "old"}
                   for stage in ("clean", "enrich", "score")},
        "references": {
            "labels": {"kind": "label", "entries": {"1": "old"}},
            "iqm": {"kind": "identity", "entries": {"ginseng": "old", "creatine": "same"},
                    "vocabulary": "same"},
        },
    }


def plan(old, current, raw=None, deps=None):
    return plan_changes(old, current, raw or {"1": {"id": "1"}, "2": {"id": "2"}},
                        deps or {"1": {"identifiers": ["ginseng"], "unresolved": False},
                                 "2": {"identifiers": ["creatine"], "unresolved": False}})


def test_exact_label_correction_selects_only_its_label():
    old = baseline()
    new = deepcopy(old)
    new["references"]["labels"]["entries"]["1"] = "new"
    assert plan(old, new)["stages"] == {stage: ["1"] for stage in old["stages"]}


def test_grade_change_selects_all_users_of_the_changed_ingredient():
    old = baseline()
    new = deepcopy(old)
    new["references"]["iqm"]["entries"]["ginseng"] = "new"
    assert plan(old, new)["stages"]["clean"] == ["1"]


def test_added_alias_cannot_hide_a_formerly_different_match():
    old = baseline()
    new = deepcopy(old)
    new["references"]["iqm"]["vocabulary"] = "new"
    assert plan(old, new)["stages"]["clean"] == ["1", "2"]


def test_unresolved_rows_are_included_in_reference_reassessment():
    old = baseline()
    new = deepcopy(old)
    new["references"]["iqm"]["entries"]["ginseng"] = "new"
    deps = {key: {"identifiers": [], "unresolved": True} for key in old["raw"]}
    assert plan(old, new, deps=deps)["stages"]["clean"] == ["1", "2"]


def test_score_code_change_reuses_clean_and_enrich():
    old = baseline()
    new = deepcopy(old)
    new["stages"]["score"]["stage_code_sha256_v1"] = "new"
    assert plan(old, new)["stages"] == {"clean": [], "enrich": [], "score": ["1", "2"]}


def test_deleted_and_new_raw_labels_are_not_lost():
    old = baseline()
    new = deepcopy(old)
    result = plan(old, new, raw={"2": {"id": "2"}, "3": {"id": "3"}})
    assert result["deleted"] == ["1"]
    assert result["stages"]["clean"] == ["3"]


def test_unknown_reference_change_rebuilds_conservatively():
    old = baseline()
    new = deepcopy(old)
    new["references"]["safety"] = {"kind": "global", "hash": "new"}
    assert plan(old, new)["stages"]["clean"] == ["1", "2"]


def test_materialization_preserves_unchanged_file_bytes_and_deletes_rows(tmp_path):
    from pipeline_incremental import materialize_merged
    from stage_manifest import write_stage_manifest

    original, candidate = tmp_path / "old", tmp_path / "new"
    original.mkdir()
    candidate.mkdir()
    one = original / "one.json"
    one.write_text('[ { "id": "1", "x": 2 } ]\n')
    two = original / "two.json"
    two.write_text('[{"id":"2"},{"id":"3"}]')
    write_stage_manifest(original, "clean", [one, two])
    materialize_merged(original, candidate, "clean", {"1": {"id": "1", "x": 2}, "3": {"id": "3"}})
    assert (candidate / "one.json").read_bytes() == one.read_bytes()
    assert json.loads((candidate / "two.json").read_text()) == [{"id": "3"}]


def test_recovery_restores_previous_generation(tmp_path):
    from pipeline_incremental import recover_promotion

    prefix = tmp_path / "output"
    transaction = tmp_path / ".output.incremental-test"
    transaction.mkdir()
    entries = []
    for index, suffix in enumerate(("", "_enriched", "_scored")):
        live = tmp_path / ("output" + suffix)
        live.mkdir()
        (live / "value").write_text("old")
        candidate = transaction / live.name
        candidate.mkdir()
        (candidate / "value").write_text("new")
        backup = transaction / ("backup-" + str(index))
        entries.append({"live": str(live), "candidate": str(candidate), "backup": str(backup)})
    # Simulate death after the first promotion.
    from pathlib import Path
    Path(entries[0]["live"]).rename(entries[0]["backup"])
    Path(entries[0]["candidate"]).rename(entries[0]["live"])
    journal = tmp_path / ".output.incremental-recovery.json"
    journal.write_text(json.dumps(entries))
    recover_promotion(journal, prefix)
    assert all((tmp_path / ("output" + suffix) / "value").read_text() == "old"
               for suffix in ("", "_enriched", "_scored"))
    assert not journal.exists()


def test_real_incremental_raw_edit_matches_full_rebuild(tmp_path):
    """Normal runner entrypoints, same real labels, full stage-record comparison."""
    from pathlib import Path
    from run_pipeline import PipelineRunner
    from pipeline_incremental import run_incremental, stage_directories, stage_products
    from audits.quality_redesign.replay import without_volatile

    repo = Path(__file__).resolve().parents[2]
    raw_dir = tmp_path / "raw"
    raw_dir.mkdir()
    # These are existing frozen repository fixtures, not local product builds.
    fixtures = repo / "scripts/tests/fixtures"
    candidates = {}
    for filename in ("incremental_creatine_336362_raw.json", "evidence_truth_231852_raw.json"):
        value = json.loads((fixtures / filename).read_text())
        candidates[str(value["id"])] = value
    assert len(candidates) == 2, "real comparison fixtures must remain available"
    for key, value in candidates.items():
        (raw_dir / (key + ".json")).write_text(json.dumps(value))
    runner = PipelineRunner()
    prefix = tmp_path / "incremental"
    created = run_incremental(runner, raw_dir, prefix)
    assert created["stages"] == {stage: ["231852", "336362"] for stage in ("clean", "enrich", "score")}
    seeded = run_incremental(runner, raw_dir, prefix)
    assert all(not ids for ids in seeded["stages"].values())
    before = {stage: stage_products(directory, stage)
              for stage, directory in zip(("clean", "enrich", "score"), stage_directories(prefix))}
    changed = candidates["336362"]
    changed["ingredientRows"][0]["quantity"][0]["quantity"] *= 2
    (raw_dir / "336362.json").write_text(json.dumps(changed))
    result = run_incremental(runner, raw_dir, prefix)
    assert result["stages"] == {stage: ["336362"] for stage in before}
    full = tmp_path / "full"
    assert runner.run_pipeline(raw_dir=str(raw_dir), output_prefix=str(full),
                               strict_release_gates=True)["success"]
    names = {"clean": "cleaned", "enrich": "enriched", "score": "scored"}
    for stage, incremental_dir, full_dir in zip(before, stage_directories(prefix), stage_directories(full)):
        got = stage_products(incremental_dir, stage)
        expected = stage_products(full_dir, stage)
        assert got["231852"] == before[stage]["231852"]
        assert {key: without_volatile(value, names[stage]) for key, value in got.items()} == {
            key: without_volatile(value, names[stage]) for key, value in expected.items()}


def _synthetic_dataset(tmp_path, monkeypatch):
    """A deterministic stage harness for transaction and reuse failure tests."""
    from pathlib import Path
    from types import SimpleNamespace
    import pipeline_incremental as incremental
    from stage_manifest import write_stage_manifest

    raw = tmp_path / "raw"
    raw.mkdir()
    prefix = tmp_path / "output"
    labels = {"1": {"id": "1", "dose": 10}, "2": {"id": "2", "dose": 20}}
    for key, value in labels.items():
        (raw / (key + ".json")).write_text(json.dumps(value))
    snapshot = baseline()
    snapshot.pop("raw")
    for fingerprints in snapshot["stages"].values():
        for key, value in list(fingerprints.items()):
            fingerprints[key] = digest(value)
    for stage, directory in zip(("clean", "enrich", "score"), incremental.stage_directories(prefix)):
        directory.mkdir(parents=True)
        path = directory / "batch.json"
        path.write_text(json.dumps(list(labels.values())))
        write_stage_manifest(directory, stage, [path],
                             input_fingerprints={**snapshot["stages"][stage],
                                                 "stage_data_sha256_v1": "1" * 64})
    monkeypatch.setattr(incremental, "current_snapshot", lambda *_: deepcopy(snapshot))
    monkeypatch.setattr("pipeline_freshness.reusable_stage_issue", lambda *_: None)
    calls = []

    def execute(stage, source, output, **kwargs):
        calls.append(stage)
        target = Path(output) / {"clean": "cleaned", "enrich": "enriched", "score": "scored"}[stage]
        target.mkdir(parents=True)
        rows = []
        for path in Path(source).glob("*.json"):
            payload = json.loads(path.read_text())
            rows.extend(payload if isinstance(payload, list) else [payload])
        (target / "batch.json").write_text(json.dumps(rows))
        return True

    runner = SimpleNamespace(
        script_dir=tmp_path / "scripts",
        run_clean=lambda source, output: execute("clean", source, output),
        run_enrich=lambda source, output: execute("enrich", source, output),
        run_score=lambda source, output: execute("score", source, output),
        run_enrichment_contract_gate=lambda *a, **kw: (True, {}),
        run_coverage_gate=lambda *a, **kw: (True, {}),
    )
    incremental.run_incremental(runner, raw, prefix)
    assert not calls
    return incremental, runner, raw, prefix, calls, snapshot


def test_unchanged_run_calls_no_stage_and_preserves_products(tmp_path, monkeypatch):
    mod, runner, raw, prefix, calls, _ = _synthetic_dataset(tmp_path, monkeypatch)
    before = {path: path.read_bytes() for directory in mod.stage_directories(prefix)
              for path in directory.glob("*.json")}
    result = mod.run_incremental(runner, raw, prefix)
    assert not calls
    assert all(not selected for selected in result["stages"].values())
    assert all(path.read_bytes() == content for path, content in before.items())


@pytest.mark.parametrize("failure", ["stage", "gate", "input_change", "output_change"])
def test_failure_keeps_previous_complete_generation(tmp_path, monkeypatch, failure):
    mod, runner, raw, prefix, calls, _ = _synthetic_dataset(tmp_path, monkeypatch)
    before = {path: path.read_bytes() for directory in mod.stage_directories(prefix)
              for path in directory.iterdir() if path.is_file()}
    (raw / "1.json").write_text('{"id":"1","dose":30}')
    original = runner.run_enrich

    def fail_or_mutate(source, output):
        if failure == "stage":
            return False
        if failure == "input_change":
            (raw / "2.json").write_text('{"id":"2","dose":99}')
        if failure == "output_change":
            existing = mod.stage_directories(prefix)[0] / "batch.json"
            existing.write_text("[]")
        return original(source, output)

    runner.run_enrich = fail_or_mutate
    if failure == "gate":
        runner.run_coverage_gate = lambda *a, **kw: (False, {})
    with pytest.raises((mod.StageManifestError, KeyError)):
        mod.run_incremental(runner, raw, prefix)
    for path, content in before.items():
        if failure == "output_change" and path.name == "batch.json" and path.parent == mod.stage_directories(prefix)[0]:
            continue  # The simulated external writer, not the incremental run.
        assert path.read_bytes() == content


def test_corrupt_output_and_state_cannot_be_reused(tmp_path, monkeypatch):
    mod, runner, raw, prefix, calls, _ = _synthetic_dataset(tmp_path, monkeypatch)
    state = prefix / ".incremental_state.json"
    state.write_text("{}")
    with pytest.raises(mod.StageManifestError, match="state"):
        mod.run_incremental(runner, raw, prefix)
    assert not calls


def test_insert_delete_and_retry_match_full_generation(tmp_path, monkeypatch):
    mod, runner, raw, prefix, calls, _ = _synthetic_dataset(tmp_path, monkeypatch)
    (raw / "1.json").unlink()
    (raw / "3.json").write_text('{"id":"3","dose":30}')
    result = mod.run_incremental(runner, raw, prefix)
    assert result["deleted"] == ["1"]
    assert calls == ["clean", "enrich", "score"]
    for stage, directory in zip(mod.STAGES, mod.stage_directories(prefix)):
        assert mod.stage_products(directory, stage) == {
            "2": {"id": "2", "dose": 20}, "3": {"id": "3", "dose": 30}}
    calls.clear()
    mod.run_incremental(runner, raw, prefix)
    assert not calls


def test_exact_preparation_dose_change_includes_matching_and_unresolved_labels():
    old = baseline()
    old["references"]["research"] = {
        "kind": "research", "entries": {"gs15": "old"},
        "scopes": {"gs15": {"bounded": True, "names": ["gs15 4"]}},
    }
    new = deepcopy(old)
    new["references"]["research"]["entries"]["gs15"] = "new"
    deps = {
        "1": {"identifiers": ["ginseng"], "names": ["gs15 4"], "unresolved": False},
        "2": {"identifiers": ["creatine"], "names": ["creatine"], "unresolved": False},
    }
    assert plan(old, new, deps=deps)["stages"] == {"clean": [], "enrich": ["1"], "score": ["1"]}
    deps["2"]["unresolved"] = True
    assert plan(old, new, deps=deps)["stages"]["enrich"] == ["1", "2"]


def test_mixed_stage_fingerprints_cannot_be_reused(tmp_path, monkeypatch):
    mod, runner, raw, prefix, calls, _ = _synthetic_dataset(tmp_path, monkeypatch)
    from stage_manifest import MANIFEST_NAME
    manifest_path = mod.stage_directories(prefix)[1] / MANIFEST_NAME
    manifest = json.loads(manifest_path.read_text())
    manifest["input_fingerprints"]["stage_code_sha256_v1"] = "0" * 64
    manifest_path.write_text(json.dumps(manifest))
    with pytest.raises(mod.StageManifestError, match="provenance"):
        mod.run_incremental(runner, raw, prefix)


def test_raw_change_between_read_and_binding_is_rejected(tmp_path, monkeypatch):
    mod, runner, raw, prefix, calls, snapshot = _synthetic_dataset(tmp_path, monkeypatch)
    (raw / "1.json").write_text('{"id":"1","dose":30}')

    def mutate_after_raw_read(*args):
        (raw / "2.json").write_text('{"id":"2","dose":99}')
        return deepcopy(snapshot)

    monkeypatch.setattr(mod, "current_snapshot", mutate_after_raw_read)
    with pytest.raises(mod.StageManifestError, match="changed"):
        mod.run_incremental(runner, raw, prefix)
    assert not calls


def test_successive_insertions_extend_the_existing_owned_batch(tmp_path, monkeypatch):
    mod, runner, raw, prefix, calls, _ = _synthetic_dataset(tmp_path, monkeypatch)
    for identifier in ("3", "4", "5"):
        (raw / (identifier + ".json")).write_text(json.dumps({"id": identifier, "dose": 30}))
        mod.run_incremental(runner, raw, prefix)
    for stage, directory in zip(mod.STAGES, mod.stage_directories(prefix)):
        assert set(mod.stage_products(directory, stage)) == {"1", "2", "3", "4", "5"}


def test_second_root_promotion_failure_rolls_back_and_retry_succeeds(tmp_path, monkeypatch):
    mod, runner, raw, prefix, calls, _ = _synthetic_dataset(tmp_path, monkeypatch)
    before = {path: path.read_bytes() for directory in mod.stage_directories(prefix)
              for path in directory.iterdir() if path.is_file()}
    (raw / "1.json").write_text('{"id":"1","dose":30}')
    replace = mod.os.replace
    failed = False

    def injected(source, destination):
        nonlocal failed
        from pathlib import Path
        if (not failed and Path(source).name == prefix.name + "_enriched"
                and Path(destination) == tmp_path / (prefix.name + "_enriched")):
            failed = True
            raise OSError("simulated second root failure")
        return replace(source, destination)

    monkeypatch.setattr(mod.os, "replace", injected)
    with pytest.raises(OSError, match="second root"):
        mod.run_incremental(runner, raw, prefix)
    assert all(path.read_bytes() == content for path, content in before.items())
    mod.run_incremental(runner, raw, prefix)
    assert mod.stage_products(mod.stage_directories(prefix)[2], "score")["1"]["dose"] == 30


def test_plan_only_does_not_seed_or_change_manifests(tmp_path, monkeypatch):
    mod, runner, raw, prefix, calls, _ = _synthetic_dataset(tmp_path, monkeypatch)
    before = {path: path.read_bytes() for directory in mod.stage_directories(prefix)
              for path in directory.iterdir() if path.is_file()}
    (raw / "1.json").write_text('{"id":"1","dose":30}')
    assert mod.run_incremental(runner, raw, prefix, plan_only=True)["stages"]["score"] == ["1"]
    assert not calls
    assert all(path.read_bytes() == content for path, content in before.items())


@pytest.mark.parametrize("options,message", [
    (["--baseline-revision", "HEAD", "--pipeline-only"], "requires --incremental"),
    (["--incremental-plan", "--release"], "cannot publish or release"),
])
def test_batch_parser_rejects_unsafe_or_ambiguous_modes_before_work(options, message):
    import subprocess
    from pathlib import Path

    repo = Path(__file__).resolve().parents[2]
    result = subprocess.run(["bash", str(repo / "batch_run_all_datasets.sh"), *options],
                            cwd=repo, text=True, capture_output=True)
    assert result.returncode == 2
    assert message in result.stderr


def test_identity_recheck_promotes_a_newly_changed_clean_match_downstream(tmp_path, monkeypatch):
    mod, runner, raw, prefix, calls, snapshot = _synthetic_dataset(tmp_path, monkeypatch)
    before = {stage: mod.stage_products(directory, stage)["1"]
              for stage, directory in zip(mod.STAGES, mod.stage_directories(prefix))}
    snapshot["references"]["iqm"]["vocabulary"] = "new alias"
    original = runner.run_clean

    def resolve_new_match(source, output):
        from pathlib import Path
        assert original(source, output)
        path = Path(output) / "cleaned/batch.json"
        rows = json.loads(path.read_text())
        for row in rows:
            if row["id"] == "2":
                row["newly_mapped"] = True
        path.write_text(json.dumps(rows))
        return True

    runner.run_clean = resolve_new_match
    result = mod.run_incremental(runner, raw, prefix)
    assert result["stages"] == {"clean": ["1", "2"], "enrich": ["2"], "score": ["2"]}
    for stage, directory in zip(mod.STAGES, mod.stage_directories(prefix)):
        rows = mod.stage_products(directory, stage)
        assert rows["1"] == before[stage]
        assert rows["2"]["newly_mapped"] is True


def test_date_sensitive_verification_is_refreshed_without_recleaning_other_labels():
    old = baseline()
    new = deepcopy(old)
    new["evaluation_date"] = "2026-11-05"
    deps = {
        "1": {"identifiers": ["ginseng"], "unresolved": False,
              "clock_refresh_required": True},
        "2": {"identifiers": ["creatine"], "unresolved": False,
              "clock_refresh_required": False},
    }
    assert plan(old, new, deps=deps)["stages"] == {"clean": [], "enrich": ["1"], "score": ["1"]}



def test_certification_clock_uses_existing_recency_owner_at_exact_time(monkeypatch):
    from pipeline_incremental import dependencies

    monkeypatch.setattr("cert_resolver._recency_status", lambda _: ("warn", 91))
    product = {"certification_data": {"verified_cert_programs": [{
        "snapshot_date": "2026-08-01T13:00:00Z",
        "snapshot_age_days": 90, "recency_status": "fresh",
    }]}}
    assert dependencies(product)["clock_refresh_required"] is True
    product["certification_data"]["verified_cert_programs"][0].update(
        snapshot_age_days=91, recency_status="warn")
    assert dependencies(product)["clock_refresh_required"] is False


def test_manufacturer_lookback_reuses_existing_case_normalization_and_threshold():
    from datetime import date, datetime, time, timedelta, timezone
    from pipeline_incremental import dependencies
    from scoring_v4.modules.generic_manufacturer import CLASS_I_LOOKBACK_DAYS

    today = date.today()
    yesterday = today - timedelta(days=1)
    product = {
        "enriched_date": datetime.combine(yesterday, time(12), tzinfo=timezone.utc).isoformat(),
        "manufacturer_violations": [{
            "severity_level": " CRITICAL ",
            "date": (today - timedelta(days=CLASS_I_LOOKBACK_DAYS + 1)).isoformat(),
        }],
    }
    assert dependencies(product)["clock_refresh_required"] is True
    product["manufacturer_violations"][0]["date"] = today.isoformat()
    assert dependencies(product)["clock_refresh_required"] is False


@pytest.mark.parametrize("mode", ["--incremental", "--incremental-plan"])
def test_incremental_cli_requires_an_explicit_output_prefix(tmp_path, monkeypatch, mode):
    import sys
    import run_pipeline

    def must_not_run(*args, **kwargs):
        raise AssertionError("missing output prefix reached execution")

    monkeypatch.setattr("pipeline_incremental.run_incremental", must_not_run)
    monkeypatch.setattr(sys, "argv", ["run_pipeline.py", mode, "--raw-dir", str(tmp_path)])
    with pytest.raises(SystemExit) as error:
        run_pipeline.main()
    assert error.value.code == 2


def test_generated_sidecars_survive_in_an_explicit_historical_scope(tmp_path, monkeypatch):
    mod, runner, raw, prefix, calls, _ = _synthetic_dataset(tmp_path, monkeypatch)
    sidecar = prefix / "needs_review" / "unique_review.json"
    sidecar.parent.mkdir()
    sidecar.write_text('{"id":"2","reason":"original reviewed source"}')
    prior = sidecar.read_bytes()
    (raw / "1.json").write_text('{"id":"1","dose":30}')
    mod.run_incremental(runner, raw, prefix)
    retained = list(prefix.rglob("unique_review.json"))
    assert len(retained) == 1
    assert retained[0].read_bytes() == prior
    assert ".incremental_artifacts" in retained[0].parts
    assert "prior" in retained[0].parts
    (raw / "1.json").write_text('{"id":"1","dose":40}')
    mod.run_incremental(runner, raw, prefix)
    retained = list(prefix.rglob("unique_review.json"))
    assert len(retained) == 1
    assert retained[0].read_bytes() == prior


def test_partial_ordinary_run_invalidates_state_before_writing(tmp_path, monkeypatch):
    from run_pipeline import PipelineRunner

    prefix = tmp_path / "ordinary"
    prefix.mkdir()
    state = prefix / ".incremental_state.json"
    state.write_text("{}")
    runner = PipelineRunner()
    monkeypatch.setattr(runner, "_validate_data_dir", lambda: True)
    monkeypatch.setattr(runner, "_validate_input_dir", lambda *a: True)
    monkeypatch.setattr(runner, "_load_products_for_gates", lambda *a, **kw: ([{"id": "1"}], None))
    monkeypatch.setattr(runner, "run_enrichment_contract_gate", lambda *a, **kw: (True, {}))
    monkeypatch.setattr(runner, "_stage_inputs", lambda *a: {})
    monkeypatch.setattr("run_pipeline.quarantine_stage_outputs", lambda *a: [])

    def failed_score(*args, **kwargs):
        assert not state.exists()
        return False

    monkeypatch.setattr(runner, "run_score", failed_score)
    assert not runner.run_pipeline(stages=["score"], raw_dir=str(tmp_path),
                                   output_prefix=str(prefix), skip_coverage_gate=True)["success"]
    assert not state.exists()


@pytest.mark.parametrize("change", ["format", "rename"])
def test_raw_bytes_or_inventory_change_cannot_reuse_stale_provenance(tmp_path, monkeypatch, change):
    from pipeline_freshness import DATA_FINGERPRINT_KEY, stage_data_files, stage_data_fingerprint
    from stage_manifest import MANIFEST_NAME

    mod, runner, raw, prefix, calls, _ = _synthetic_dataset(tmp_path, monkeypatch)
    before = {stage: mod.stage_products(directory, stage)["2"]
              for stage, directory in zip(mod.STAGES, mod.stage_directories(prefix))}
    original = raw / "1.json"
    if change == "format":
        original.write_text(json.dumps(json.loads(original.read_text()), indent=4) + "\n")
    else:
        original.rename(raw / "renamed.json")
    selected_source = raw / ("1.json" if change == "format" else "renamed.json")
    expected_bytes = selected_source.read_bytes()
    original_clean = runner.run_clean

    def verify_exact_source_bytes(source, output):
        from pathlib import Path
        files = list(Path(source).glob("*.json"))
        assert [path.name for path in files] == [selected_source.name]
        assert files[0].read_bytes() == expected_bytes
        return original_clean(source, output)

    runner.run_clean = verify_exact_source_bytes
    planned = mod.run_incremental(runner, raw, prefix, plan_only=True)
    assert planned["stages"]["clean"] == ["1"]
    assert not calls
    result = mod.run_incremental(runner, raw, prefix)
    assert result["stages"] == {"clean": ["1"], "enrich": [], "score": []}
    assert calls == ["clean"]
    manifest = json.loads((mod.stage_directories(prefix)[0] / MANIFEST_NAME).read_text())
    assert manifest["input_fingerprints"][DATA_FINGERPRINT_KEY] == stage_data_fingerprint(stage_data_files(raw))
    for stage, directory in zip(mod.STAGES, mod.stage_directories(prefix)):
        assert mod.stage_products(directory, stage)["2"] == before[stage]
    calls.clear()
    assert not any(mod.run_incremental(runner, raw, prefix)["stages"].values())
    assert not calls


def test_older_reuse_state_without_per_file_proof_rechecks_clean_on_raw_byte_change(tmp_path, monkeypatch):
    from stage_manifest import MANIFEST_NAME, write_stage_manifest_from_directory

    mod, runner, raw, prefix, calls, _ = _synthetic_dataset(tmp_path, monkeypatch)
    state_path = prefix / ".incremental_state.json"
    old = json.loads(state_path.read_text())
    old.pop("raw_files")
    state_path.write_text(json.dumps(old))
    for stage, directory in zip(mod.STAGES, mod.stage_directories(prefix)):
        fingerprints = json.loads((directory / MANIFEST_NAME).read_text())["input_fingerprints"]
        fingerprints["incremental_state_sha256"] = mod.digest(old)
        write_stage_manifest_from_directory(directory, stage, input_fingerprints=fingerprints)
    original = raw / "1.json"
    original.write_text(json.dumps(json.loads(original.read_text()), indent=4))
    result = mod.run_incremental(runner, raw, prefix)
    assert result["stages"] == {"clean": ["1", "2"], "enrich": [], "score": []}
    assert calls == ["clean"]
    assert set(json.loads(state_path.read_text())["raw_files"]) == {"1", "2"}


def test_raw_capture_rejects_a_transient_edit_restored_before_live_recheck(tmp_path, monkeypatch):
    mod, runner, raw, prefix, calls, snapshot = _synthetic_dataset(tmp_path, monkeypatch)
    original_read = mod.raw_products
    path = raw / "1.json"
    planned_bytes = path.read_bytes()

    def transient_read(directory, **kwargs):
        path.write_text('{"id":"1","dose":99}')
        return original_read(directory, **kwargs)

    def restore_before_live_check(*args):
        path.write_bytes(planned_bytes)
        return deepcopy(snapshot)

    monkeypatch.setattr(mod, "raw_products", transient_read)
    monkeypatch.setattr(mod, "current_snapshot", restore_before_live_check)
    with pytest.raises(mod.StageManifestError, match="Captured raw"):
        mod.run_incremental(runner, raw, prefix)
    assert not calls


def test_unchanged_plan_does_not_claim_raw_labels_changed():
    result = plan(baseline(), baseline())
    assert result["stages"] == {"clean": [], "enrich": [], "score": []}
    assert result["reasons"] == []


def _clinical_reference(tmp_path, monkeypatch, filename="clinically_relevant_strains"):
    import pipeline_incremental as incremental
    path = tmp_path / "scripts" / "data" / (filename + ".json")
    path.parent.mkdir(parents=True)
    payload = {"_metadata": {"schema_version": "1", "last_updated": "old", "total_entries": 1},
               filename: [{"id": "RECORD_A", "standard_name": "Test strain", "aliases": ["A"],
                           "study_contexts": [{"context_id": "CONTEXT_A", "review_status": "pending"}]}]}
    if filename == "clinically_relevant_strains":
        payload["prebiotics"] = {"description": "Opaque existing prebiotic catalog", "ingredients": [
            {"standard_name": "Inulin", "aliases": ["chicory inulin"]}]}
    path.write_text(json.dumps(payload))
    monkeypatch.setattr(incremental, "_reference_data_files", lambda repo: [repo / path.relative_to(tmp_path)])
    return incremental, path, payload


@pytest.mark.parametrize("filename", ["clinically_relevant_strains", "backed_clinical_studies"])
def test_clinical_context_change_selects_emitted_rejected_and_unresolved_active_users(tmp_path, monkeypatch, filename):
    mod, path, payload = _clinical_reference(tmp_path, monkeypatch, filename)
    old = baseline()
    old["references"] = mod.reference_snapshot(tmp_path)
    payload[filename][0]["study_contexts"].append({"context_id": "NEW_CONTEXT", "review_status": "approved"})
    path.write_text(json.dumps(payload))
    new = deepcopy(old)
    new["references"] = mod.reference_snapshot(tmp_path)
    raw = {key: {"id": key} for key in ("1", "2", "3")}
    old["raw"] = {key: digest(value) for key, value in raw.items()}
    deps = {"1": {"identifiers": ["CONTEXT_A"], "unresolved": True, "clinical_unresolved": False},
            "2": {"identifiers": ["unrelated"], "unresolved": True, "clinical_unresolved": False},
            "3": {"identifiers": [], "unresolved": False, "clinical_unresolved": True}}
    selected = plan_changes(old, new, raw, deps)["stages"]
    assert selected == {"clean": [], "enrich": ["1", "3"], "score": ["1", "3"]}
    deps["2"].pop("clinical_unresolved")
    assert plan_changes(old, new, raw, deps)["stages"]["enrich"] == ["1", "2", "3"]
    deps["2"]["clinical_unresolved"] = False
    deps["2"].pop("identifiers")
    assert plan_changes(old, new, raw, deps)["stages"]["enrich"] == ["1", "2", "3"]


@pytest.mark.parametrize("change", ["alias", "added", "removed", "schema", "unknown_field"])
def test_clinical_lookup_or_unknown_structure_change_widens_conservatively(tmp_path, monkeypatch, change):
    mod, path, payload = _clinical_reference(tmp_path, monkeypatch)
    old = baseline(); old["references"] = mod.reference_snapshot(tmp_path)
    if change == "alias": payload["clinically_relevant_strains"][0]["aliases"].append("new")
    elif change == "added": payload["clinically_relevant_strains"].append({"id": "NEW", "standard_name": "new"})
    elif change == "removed": payload["clinically_relevant_strains"] = []
    elif change == "schema": payload["_metadata"]["schema_version"] = "2"
    else: payload["clinically_relevant_strains"][0]["new_identity_rule"] = {"x": True}
    path.write_text(json.dumps(payload))
    new = deepcopy(old); new["references"] = mod.reference_snapshot(tmp_path)
    assert plan(old, new)["stages"] == {stage: ["1", "2"] for stage in old["stages"]}


def test_runtime_dependencies_include_rejected_ids_and_isolate_active_unknowns():
    from pipeline_incremental import dependencies
    row = {"name": "Magnesium", "canonical_id": "magnesium", "mapped": True,
           "mapped_identity": True, "scoreable_identity": True, "identity_disposition": "clean",
           "source_section": "active", "cleaner_row_role": "active_scorable", "score_eligible_by_cleaner": True,
           "quantity": 100, "unit": "mg", "raw_source_path": "ingredientRows[0]"}
    product = {"dsld_id": "1", "ingredient_quality_data": {"ingredients_scorable": [row], "ingredients": [row]},
               "evidence_data": {"rejected_matches": [{"id": "RECORD_A", "context_id": "CONTEXT_A"}],
                                 "rejected_record_ids": ["RECORD_B"]},
               "inactiveIngredients": [{"name": "Unmatched inactive", "mapped": False}]}
    result = dependencies(product)
    assert {"RECORD_A", "CONTEXT_A", "RECORD_B"} <= set(result["identifiers"])
    assert result["unresolved"] is True  # Existing IQM conservative guard remains.
    assert result["clinical_unresolved"] is False
    # Dose/scoring exclusion is not an unresolved clinical source identity.
    row.update(mapped=False, mapped_identity=False, scoreable_identity=False)
    assert dependencies(product)["clinical_unresolved"] is False
    row["canonical_id"] = None
    assert dependencies(product)["clinical_unresolved"] is True
    product.pop("ingredient_quality_data")
    assert dependencies(product)["clinical_unresolved"] is True


def test_legacy_clinical_map_requires_exact_historical_payload_proof(tmp_path, monkeypatch):
    mod, path, payload = _clinical_reference(tmp_path, monkeypatch)
    current = baseline(); current["references"] = mod.reference_snapshot(tmp_path)
    relative = next(iter(current["references"]))
    old = deepcopy(current); old["references"][relative] = {"kind": "global", "hash": digest(payload)}
    untouched = deepcopy(old)
    derived = mod.planning_snapshot(old, current)
    assert derived["references"] == current["references"]
    assert all(not rows for rows in plan(derived, current)["stages"].values())
    assert old == untouched
    payload["clinically_relevant_strains"][0]["study_contexts"][0]["review_status"] = "approved"
    path.write_text(json.dumps(payload))
    changed = deepcopy(current); changed["references"] = mod.reference_snapshot(tmp_path)
    assert mod.planning_snapshot(old, changed)["references"] == old["references"]
    assert plan(mod.planning_snapshot(old, changed), changed)["stages"]["clean"] == ["1", "2"]
    historical = tmp_path / "history"
    historical_file = historical / path.relative_to(tmp_path); historical_file.parent.mkdir(parents=True)
    original_payload = deepcopy(payload); original_payload["clinically_relevant_strains"][0]["study_contexts"][0]["review_status"] = "pending"
    historical_file.write_text(json.dumps(original_payload))
    verified = mod.planning_snapshot(old, changed, baseline_repo=historical)
    assert verified["references"] == current["references"]
    historical_file.write_text(json.dumps(payload))
    assert mod.planning_snapshot(old, changed, baseline_repo=historical)["references"] == old["references"]
    assert old == untouched


def test_original_owned_state_is_validated_before_legacy_planning(tmp_path, monkeypatch):
    mod, runner, raw, prefix, calls, _ = _synthetic_dataset(tmp_path, monkeypatch)
    state_path = prefix / ".incremental_state.json"
    state = json.loads(state_path.read_text())
    state["raw"]["1"] = "unproven"
    state_path.write_text(json.dumps(state))
    monkeypatch.setattr(mod, "planning_snapshot", lambda *a, **kw: pytest.fail("unvalidated state reached migration"))
    with pytest.raises(mod.StageManifestError, match="state does not match"):
        mod.run_incremental(runner, raw, prefix)
    assert not calls


def test_clinical_bookkeeping_only_does_not_reselect_unresolved_products(tmp_path, monkeypatch):
    mod, path, payload = _clinical_reference(tmp_path, monkeypatch)
    old = baseline(); old["references"] = mod.reference_snapshot(tmp_path)
    payload["_metadata"]["last_updated"] = "new"
    path.write_text(json.dumps(payload))
    current = deepcopy(old); current["references"] = mod.reference_snapshot(tmp_path)
    assert all(not rows for rows in plan(old, current)["stages"].values())


@pytest.mark.parametrize("change", ["prebiotic_alias", "record_order"])
def test_clinical_auxiliary_catalog_and_order_changes_remain_broad(tmp_path, monkeypatch, change):
    mod, path, payload = _clinical_reference(tmp_path, monkeypatch)
    payload["clinically_relevant_strains"].append({"id": "RECORD_B", "standard_name": "Other strain"})
    path.write_text(json.dumps(payload))
    old = baseline(); old["references"] = mod.reference_snapshot(tmp_path)
    if change == "prebiotic_alias": payload["prebiotics"]["ingredients"][0]["aliases"].append("new")
    else: payload["clinically_relevant_strains"].reverse()
    path.write_text(json.dumps(payload))
    current = deepcopy(old); current["references"] = mod.reference_snapshot(tmp_path)
    assert plan(old, current)["stages"] == {stage: ["1", "2"] for stage in old["stages"]}


def test_clinical_selection_uses_runtime_reference_only_rejected_record_ids(tmp_path, monkeypatch):
    mod, path, payload = _clinical_reference(tmp_path, monkeypatch, "backed_clinical_studies")
    old = baseline(); old["references"] = mod.reference_snapshot(tmp_path)
    payload["backed_clinical_studies"][0]["study_contexts"][0]["review_status"] = "approved"
    path.write_text(json.dumps(payload))
    current = deepcopy(old); current["references"] = mod.reference_snapshot(tmp_path)
    products = {}
    for identifier in ("1", "2"):
        row = {"name": "Magnesium", "canonical_id": "magnesium", "mapped_identity": True,
               "scoreable_identity": True, "identity_disposition": "clean", "source_section": "active",
               "cleaner_row_role": "active_scorable", "score_eligible_by_cleaner": True,
               "quantity": 100, "unit": "mg", "raw_source_path": "ingredientRows[0]"}
        products[identifier] = {"id": identifier,
            "ingredient_quality_data": {"ingredients_scorable": [row], "ingredients": [row]},
            "evidence_data": {"rejected_clinical_matches": [{"id": "RECORD_A"}] if identifier == "1" else []},
            "inactiveIngredients": [{"name": "Unmapped excipient", "mapped": False}]}
    deps = {key: mod.dependencies(product) for key, product in products.items()}
    assert deps["1"]["clinical_unresolved"] is False
    assert deps["2"]["unresolved"] is True  # General IQM policy still sees the inactive.
    assert plan(old, current, deps=deps)["stages"] == {"clean": [], "enrich": ["1"], "score": ["1"]}


@pytest.mark.parametrize('canonical', ['l_histidine', 'l_isoleucine', 'l_leucine', 'l_lysine', 'methionine', 'l_phenylalanine', 'l_threonine', 'l_tryptophan', 'l_valine'])
@pytest.mark.parametrize('status', ['mapped', 'unspecified'])
def test_all_eaa_users_depend_on_group_reference_even_when_form_rejected(canonical, status):
    from pipeline_incremental import dependencies
    row = {'canonical_id': canonical, 'form_match_status': status, 'mapped': False}
    product = {'ingredient_quality_data': {'ingredients_scorable': [row]}, 'evidence_data': {}}
    assert 'essential_amino_acids' in dependencies(product)['identifiers']
