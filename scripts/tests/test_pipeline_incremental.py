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


def _pin_comparison_dates(monkeypatch):
    """Keep equivalence comparisons on their start date; retain live source hashes."""
    from datetime import date, datetime, timezone
    import pipeline_incremental as incremental
    original = incremental.current_snapshot
    dates = {"evaluation_date": datetime.now(timezone.utc).date().isoformat(),
             "evaluation_local_date": date.today().isoformat()}

    def snapshot(repo):
        return {**original(repo), **dates}

    monkeypatch.setattr(incremental, "current_snapshot", snapshot)


def test_real_incremental_raw_edit_matches_full_rebuild(tmp_path, monkeypatch):
    """Normal runner entrypoints, same real labels, full stage-record comparison."""
    _pin_comparison_dates(monkeypatch)
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
        run_clean=lambda source, output, **kwargs: execute("clean", source, output),
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

    def resolve_new_match(source, output, **kwargs):
        from pathlib import Path
        assert original(source, output, **kwargs)
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

    def verify_exact_source_bytes(source, output, **kwargs):
        from pathlib import Path
        files = list(Path(source).glob("*.json"))
        assert [path.name for path in files] == [selected_source.name]
        assert files[0].read_bytes() == expected_bytes
        return original_clean(source, output, **kwargs)

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


@pytest.mark.parametrize('context_edit', ['population', 'additional_context'])
def test_newly_applicable_context_matches_full_rebuild_and_reuses_unrelated_mapped_product(
    tmp_path, monkeypatch, context_edit,
):
    """Identity discovery retains rejected record IDs before context eligibility.

    Exercise the actual collector, applicability and Evidence scorer in both the
    selective and full arms. An unrelated mapped/no-reference control must stay
    reusable; inventing missing references on the related row would hide the
    production collector's retention contract instead of testing it.
    """
    import clinical_applicability as clinical
    import evidence_resolver as evidence
    import pipeline_incremental as incremental
    from enrich_supplements_v3 import SupplementEnricherV3
    from scoring_v4.modules.generic_evidence import score_evidence
    from test_evidence_resolver import _approved_test_source

    source = _approved_test_source({
        'id': 'TEST_CONTEXT_PROMOTION', 'study_type': 'rct_single',
        'effect_direction': 'positive_strong', 'evidence_level': 'ingredient-human',
        'score_contribution': 'tier_3',
    }, name='Ginger')
    source['study_contexts'][0]['population'] = {
        'age_group': 'child', 'description': 'Synthetic child mechanics population'}
    payload = {'_metadata': {'schema_version': 'synthetic'}, 'backed_clinical_studies': [source]}
    path = tmp_path / 'scripts/data/backed_clinical_studies.json'
    path.parent.mkdir(parents=True)
    path.write_text(json.dumps(payload))
    monkeypatch.setattr(incremental, '_reference_data_files', lambda repo: [path])
    monkeypatch.setattr(clinical, 'reviewed_entries', lambda: {source['id']: source})
    monkeypatch.setattr(evidence, '_backed_studies_index', lambda: {'ginger': [source]})
    monkeypatch.setattr(evidence, '_load_literature_evidence', lambda: {})
    enricher = SupplementEnricherV3()
    enricher.databases['backed_clinical_studies'] = payload

    products = {}
    for pid, canonical, name in [('1', 'ginger', 'Ginger'), ('2', 'magnesium', 'Magnesium')]:
        row = {'name': name, 'standard_name': name, 'canonical_id': canonical,
               'mapped': True, 'mapped_identity': True, 'scoreable_identity': True,
               'identity_disposition': 'clean', 'source_section': 'active',
               'cleaner_row_role': 'active_scorable', 'score_eligible_by_cleaner': True,
               'role_classification': 'active_scorable', 'dose_class': 'therapeutic_mass',
               'quantity': 500, 'unit': 'mg', 'raw_source_path': 'ingredientRows[0]'}
        products[pid] = {'dsld_id': pid, 'product_name': name, 'form_factor': 'capsule',
                         'activeIngredients': [row], 'evidence_data': {},
                         'ingredient_quality_data': {'ingredients': [row],
                             'ingredients_scorable': [row], 'total_active': 1}}
    untouched = deepcopy(products)

    def rebuild(pid):
        product = deepcopy(products[pid])
        product['evidence_data'] = enricher._collect_evidence_data(
            product, product['ingredient_quality_data'])
        # Persisted artifacts cannot borrow mutable context objects from a loader.
        product = json.loads(json.dumps(product))
        return deepcopy({'enriched': product, 'evidence': score_evidence(
            product, apply_primary_floor=True, owner_scoped=True)})

    prior_outputs = {pid: rebuild(pid) for pid in products}
    prior_evidence = prior_outputs['1']['enriched']['evidence_data']
    assert prior_evidence['clinical_matches'] == []
    assert [row['id'] for row in prior_evidence['rejected_clinical_matches']] == [source['id']]
    assert prior_outputs['2']['enriched']['evidence_data']['clinical_matches'] == []
    assert prior_outputs['2']['enriched']['evidence_data']['rejected_clinical_matches'] == []
    deps = {pid: incremental.dependencies(value['enriched']) for pid, value in prior_outputs.items()}
    assert all(row['clinical_unresolved'] is False and row['unresolved'] is False for row in deps.values())
    assert source['id'] in deps['1']['identifiers']
    assert not set(deps['2']['identifiers']) & set(incremental.reference_identifiers(source))
    old = baseline()
    old['raw'] = {pid: digest(product) for pid, product in products.items()}
    old['references'] = incremental.reference_snapshot(tmp_path)

    if context_edit == 'additional_context':
        source['study_contexts'].append(deepcopy(source['study_contexts'][0]))
        source['study_contexts'][-1]['context_id'] += '_new'
    source['study_contexts'][-1]['population'] = {
        'age_group': 'adult', 'description': 'Synthetic adult mechanics population'}
    path.write_text(json.dumps(payload))
    current = deepcopy(old)
    current['references'] = incremental.reference_snapshot(tmp_path)
    reference_path = next(iter(old['references']))
    assert old['references'][reference_path]['vocabulary'] == current['references'][reference_path]['vocabulary']
    selected = incremental.plan_changes(old, current, products, deps)['stages']
    assert selected == {'clean': [], 'enrich': ['1'], 'score': ['1']}

    full_outputs = {pid: rebuild(pid) for pid in products}
    selective_outputs = deepcopy(prior_outputs)
    for pid in selected['enrich']:
        selective_outputs[pid] = rebuild(pid)
    assert selective_outputs == full_outputs
    assert full_outputs['1']['evidence']['score'] > prior_outputs['1']['evidence']['score']
    assert [row['id'] for row in full_outputs['1']['enriched']['evidence_data']['clinical_matches']] == [source['id']]
    assert full_outputs['2'] == prior_outputs['2']
    assert products == untouched


def _partitioned_clean_dataset(tmp_path, monkeypatch, *, good_count=1):
    """Canonical output shapes; only execution is deterministic for failure tests."""
    from pathlib import Path
    from stage_manifest import write_stage_manifest
    mod, runner, raw, prefix, calls, snapshot = _synthetic_dataset(tmp_path, monkeypatch)
    if good_count > 1:
        for identifier in range(3, good_count + 2):
            (raw / (str(identifier) + '.json')).write_text(json.dumps({'id': str(identifier), 'dose': 20}))
        mod.run_incremental(runner, raw, prefix)
        calls.clear()
    clean_inputs = []

    def clean(source, output, *, incremental_worker=False):
        calls.append('clean')
        paths = sorted(Path(source).glob('*.json'))
        values = [json.loads(path.read_text()) for path in paths]
        clean_inputs.append([value['id'] for value in values])
        output = Path(output)
        cleaned = output / 'cleaned'
        cleaned.mkdir(parents=True)
        successes = []
        holds = {'incomplete': [], 'needs_review': []}
        for path, value in zip(paths, values):
            disposition = value.get('test_clean_outcome')
            if disposition in holds:
                value['metadata'] = {'completeness': {'missingFields': ['fullName'],
                                                       'criticalFieldsComplete': False}}
                holds[disposition].append(value)
            elif disposition == 'errors' and not getattr(runner, 'test_recover_errors', False):
                target = output / 'errors'
                target.mkdir(exist_ok=True)
                (target / (path.stem + '_error.json')).write_text(json.dumps({
                    'original_file': str(path), 'error_type': 'SyntheticItemError',
                    'error_message': 'Synthetic item failure', 'processing_stage': 'normalize',
                    'timestamp': '2026-11-05T00:00:00Z', 'traceback': None}))
            elif disposition == 'overlap':
                holds['incomplete'].append(value)
                successes.append(value)
            elif disposition == 'hold_extra':
                holds['incomplete'].append({**value, 'id': 'unexpected'})
            elif disposition == 'extra':
                successes.extend([value, {**value, 'id': 'unexpected'}])
            elif disposition == 'duplicate':
                successes.extend([value, value])
            elif disposition != 'missing':
                successes.append(value)
        owned = []
        if successes:
            batch = cleaned / 'batch.json'
            batch.write_text(json.dumps(successes))
            owned.append(batch)
        for name, rows in holds.items():
            if rows:
                target = output / name
                target.mkdir()
                (target / (name + '_batch_1.json')).write_text(json.dumps(rows))
        write_stage_manifest(cleaned, 'clean', owned)
        reports = output / 'reports'
        reports.mkdir()
        (reports / 'processing_summary.txt').write_text('Synthetic complete per-item disposition report')
        if getattr(runner, 'test_enforce_rate', False) and not incremental_worker:
            return len(successes) + sum(map(len, holds.values())) >= 0.95 * len(values)
        return True

    runner.run_clean = clean
    return mod, runner, raw, prefix, calls, clean_inputs


@pytest.mark.parametrize('disposition', ['incomplete', 'needs_review'])
def test_clean_hold_eviction_recovery_and_unchanged_resume(tmp_path, monkeypatch, disposition):
    mod, runner, raw, prefix, calls, clean_inputs = _partitioned_clean_dataset(tmp_path, monkeypatch)
    value = json.loads((raw / '1.json').read_text())
    value['test_clean_outcome'] = disposition
    (raw / '1.json').write_text(json.dumps(value))
    result = mod.run_incremental(runner, raw, prefix)
    assert result['stages'] == {'clean': ['1'], 'enrich': [], 'score': []}
    assert clean_inputs == [['1']]
    for stage, directory in zip(mod.STAGES, mod.stage_directories(prefix)):
        assert set(mod.stage_products(directory, stage)) == {'2'}
    held = mod.stage_products(prefix / disposition, 'clean')
    assert set(held) == {'1'}
    assert held['1']['metadata']['completeness']['missingFields'] == ['fullName']
    calls.clear()
    stable = {path: path.read_bytes() for path in prefix.rglob('*.json')}
    assert all(not ids for ids in mod.run_incremental(runner, raw, prefix)['stages'].values())
    assert not calls
    assert all(path.read_bytes() == data for path, data in stable.items())
    value.pop('test_clean_outcome')
    (raw / '1.json').write_text(json.dumps(value))
    restored = mod.run_incremental(runner, raw, prefix)
    assert restored['stages'] == {stage: ['1'] for stage in mod.STAGES}
    for stage, directory in zip(mod.STAGES, mod.stage_directories(prefix)):
        assert set(mod.stage_products(directory, stage)) == {'1', '2'}
    calls.clear()
    assert all(not ids for ids in mod.run_incremental(runner, raw, prefix)['stages'].values())
    assert not calls


def test_clean_error_partial_commit_and_retry_only_failed_item(tmp_path, monkeypatch):
    from pathlib import Path
    mod, runner, raw, prefix, calls, clean_inputs = _partitioned_clean_dataset(tmp_path, monkeypatch, good_count=20)
    value = json.loads((raw / '1.json').read_text())
    value['test_clean_outcome'] = 'errors'
    (raw / '1.json').write_text(json.dumps(value))
    mod.run_incremental(runner, raw, prefix)
    assert set(mod.stage_products(mod.stage_directories(prefix)[2], 'score')) == {str(i) for i in range(2, 22)}
    assert list((prefix / 'errors').glob('*_error.json'))
    before = {path: path.read_bytes() for root in (prefix, Path(str(prefix) + '_enriched'), Path(str(prefix) + '_scored'))
              for path in root.rglob('*') if path.is_file()}
    def failed_retry(source, output, **kwargs):
        selected = [json.loads(path.read_text())['id'] for path in Path(source).glob('*.json')]
        assert selected == ['1']
        return False
    with monkeypatch.context() as failed:
        failed.setattr(runner, 'run_clean', failed_retry)
        with pytest.raises(mod.StageManifestError, match='Incremental clean failed'):
            mod.run_incremental(runner, raw, prefix)
    assert all(path.read_bytes() == data for path, data in before.items())
    runner.test_recover_errors = True
    result = mod.run_incremental(runner, raw, prefix)
    assert result['stages'] == {stage: ['1'] for stage in mod.STAGES}
    assert clean_inputs == [['1'], ['1']]
    assert set(mod.stage_products(mod.stage_directories(prefix)[2], 'score')) == {str(i) for i in range(1, 22)}
    calls.clear()
    assert all(not ids for ids in mod.run_incremental(runner, raw, prefix)['stages'].values())
    assert not calls


def test_clean_unexplained_missing_output_stays_fatal(tmp_path, monkeypatch):
    mod, runner, raw, prefix, calls, _ = _partitioned_clean_dataset(tmp_path, monkeypatch)
    value = json.loads((raw / '1.json').read_text())
    value['test_clean_outcome'] = 'missing'
    (raw / '1.json').write_text(json.dumps(value))
    with pytest.raises(mod.StageManifestError, match='output ID inventory'):
        mod.run_incremental(runner, raw, prefix)


@pytest.mark.parametrize('defect', ['extra', 'duplicate', 'overlap', 'hold_extra'])
def test_clean_disposition_partition_rejects_unknown_extra_or_duplicate_ids(tmp_path, monkeypatch, defect):
    mod, runner, raw, prefix, _, _ = _partitioned_clean_dataset(tmp_path, monkeypatch)
    value = json.loads((raw / '1.json').read_text())
    value['test_clean_outcome'] = defect
    (raw / '1.json').write_text(json.dumps(value))
    before = (prefix / '.incremental_state.json').read_bytes()
    with pytest.raises(mod.StageManifestError, match='inventory|[Dd]uplicate'):
        mod.run_incremental(runner, raw, prefix)
    assert (prefix / '.incremental_state.json').read_bytes() == before


@pytest.mark.parametrize('manifest_defect', ['missing', 'incomplete'])
def test_clean_holds_cannot_override_missing_or_failed_producer_proof(tmp_path, monkeypatch, manifest_defect):
    mod, runner, raw, prefix, _, _ = _partitioned_clean_dataset(tmp_path, monkeypatch)
    value = json.loads((raw / '1.json').read_text())
    value['test_clean_outcome'] = 'incomplete'
    (raw / '1.json').write_text(json.dumps(value))
    clean = runner.run_clean
    def broken(source, output, **kwargs):
        from pathlib import Path
        from stage_manifest import MANIFEST_NAME
        clean(source, output)
        manifest = Path(output) / 'cleaned' / MANIFEST_NAME
        if manifest_defect == 'missing':
            manifest.unlink()
        else:
            payload = json.loads(manifest.read_text())
            payload['processing_complete'] = False
            manifest.write_text(json.dumps(payload))
        return True
    monkeypatch.setattr(runner, 'run_clean', broken)
    with pytest.raises(mod.StageManifestError, match='producer manifest|incomplete'):
        mod.run_incremental(runner, raw, prefix)


def test_owned_clean_hold_tampering_is_fatal_before_reuse(tmp_path, monkeypatch):
    mod, runner, raw, prefix, _, _ = _partitioned_clean_dataset(tmp_path, monkeypatch)
    value = json.loads((raw / '1.json').read_text())
    value['test_clean_outcome'] = 'incomplete'
    (raw / '1.json').write_text(json.dumps(value))
    mod.run_incremental(runner, raw, prefix)
    held_file = next(path for path in (prefix / 'incomplete').glob('*.json') if not path.name.startswith('.'))
    held_file.write_text('[]')
    with pytest.raises(mod.StageManifestError, match='checksum mismatch'):
        mod.run_incremental(runner, raw, prefix)


def test_clean_jsonl_materialization_preserves_controls_and_removes_only_held_id(tmp_path):
    from stage_manifest import write_stage_manifest
    from pipeline_incremental import stage_products, materialize_merged
    old, new = tmp_path / 'old', tmp_path / 'new'
    old.mkdir()
    new.mkdir()
    path = old / 'cleaned_batch_1.jsonl'
    path.write_text('{"id":"1"}\n{"id":"2"}\n')
    write_stage_manifest(old, 'clean', [path])
    assert set(stage_products(old, 'clean')) == {'1', '2'}
    materialize_merged(old, new, 'clean', {'2': {'id': '2'}})
    write_stage_manifest(new, 'clean', list(new.glob('*.jsonl')))
    assert stage_products(new, 'clean') == {'2': {'id': '2'}}


def test_incremental_cli_reports_unchanged_held_inputs(monkeypatch, capsys, tmp_path):
    import sys
    from types import SimpleNamespace
    from pathlib import Path
    import run_pipeline
    import pipeline_incremental
    result = {'stages': {stage: [] for stage in ('clean', 'enrich', 'score')},
              'deleted': [], 'reasons': [],
              'held_clean_inputs': {'incomplete': ['312659'], 'needs_review': [], 'errors': ['failed-id']}}
    monkeypatch.setattr(pipeline_incremental, 'run_incremental', lambda *args, **kwargs: result)
    monkeypatch.setattr(run_pipeline, 'PipelineRunner', lambda *_: SimpleNamespace(
        script_dir=tmp_path / 'scripts', _resolve_path=lambda path: Path(path)))
    monkeypatch.setattr(sys, 'argv', ['run_pipeline.py', '--incremental', '--raw-dir', str(tmp_path),
                                    '--output-prefix', str(tmp_path / 'output')])
    with pytest.raises(SystemExit) as stopped:
        run_pipeline.main()
    assert stopped.value.code == 0
    output = json.loads(capsys.readouterr().out)
    assert output['held_clean_counts'] == {'incomplete': 1, 'needs_review': 0, 'errors': 1}
    assert output['held_clean_inputs']['incomplete'] == ['312659']


def test_real_null_ingredients_hold_transitions_match_full_rebuild(tmp_path, monkeypatch):
    _pin_comparison_dates(monkeypatch)
    from pathlib import Path
    from run_pipeline import PipelineRunner
    from pipeline_incremental import run_incremental, stage_directories, stage_products
    from audits.quality_redesign.replay import without_volatile
    repo = Path(__file__).resolve().parents[2]
    raw = tmp_path / 'raw'
    raw.mkdir()
    fixtures = repo / 'scripts/tests/fixtures'
    labels = {}
    for name in ('incremental_creatine_336362_raw.json', 'evidence_truth_231852_raw.json'):
        value = json.loads((fixtures / name).read_text())
        labels[str(value['id'])] = value
        (raw / (str(value['id']) + '.json')).write_text(json.dumps(value))
    runner = PipelineRunner()
    prefix = tmp_path / 'incremental'
    run_incremental(runner, raw, prefix)
    original_control = {stage: stage_products(directory, stage)['231852']
        for stage, directory in zip(('clean', 'enrich', 'score'), stage_directories(prefix))}
    for held in (True, False):
        changed = deepcopy(labels['336362'])
        if held:
            changed['ingredientRows'] = None  # Actual Bulk312659/Emergen_C250356 defect shape.
        (raw / '336362.json').write_text(json.dumps(changed))
        result = run_incremental(runner, raw, prefix)
        assert result['stages']['clean'] == ['336362']
        assert result['stages']['enrich'] == ([] if held else ['336362'])
        assert result['stages']['score'] == ([] if held else ['336362'])
        full = tmp_path / ('full_held' if held else 'full_valid')
        assert runner.run_pipeline(raw_dir=str(raw), output_prefix=str(full), strict_release_gates=True)['success']
        for stage, left, right in zip(('clean', 'enrich', 'score'), stage_directories(prefix), stage_directories(full)):
            got, expected = stage_products(left, stage), stage_products(right, stage)
            assert got['231852'] == original_control[stage]
            assert {pid: without_volatile(row, {'clean': 'cleaned', 'enrich': 'enriched', 'score': 'scored'}[stage])
                    for pid, row in got.items()} == {
                pid: without_volatile(row, {'clean': 'cleaned', 'enrich': 'enriched', 'score': 'scored'}[stage])
                for pid, row in expected.items()}
        resumed = run_incremental(runner, raw, prefix)
        assert all(not ids for ids in resumed['stages'].values())


def test_clean_jsonl_executor_promotes_and_reuses_owned_generation(tmp_path, monkeypatch):
    mod, runner, raw, prefix, calls, _ = _synthetic_dataset(tmp_path, monkeypatch)
    from stage_manifest import MANIFEST_NAME, write_stage_manifest_from_directory
    clean = mod.stage_directories(prefix)[0]
    fingerprints = json.loads((clean / MANIFEST_NAME).read_text())['input_fingerprints']
    original = clean / 'batch.json'
    rows = json.loads(original.read_text())
    original.unlink()
    lines = clean / 'batch.jsonl'
    lines.write_text(''.join(json.dumps(row) + '\n' for row in rows))
    write_stage_manifest_from_directory(clean, 'clean', patterns=('*.json', '*.jsonl'),
                                        input_fingerprints=fingerprints)
    mod.run_incremental(runner, raw, prefix)
    assert set(mod.stage_products(clean, 'clean')) == {'1', '2'}
    assert 'batch.jsonl' in (clean / MANIFEST_NAME).read_text()
    (raw / '1.json').write_text(json.dumps({'id': '1', 'dose': 30}))
    result = mod.run_incremental(runner, raw, prefix)
    assert result['stages'] == {stage: ['1'] for stage in mod.STAGES}
    assert mod.stage_products(clean, 'clean') == {'1': {'id': '1', 'dose': 30}, '2': rows[1]}
    calls.clear()
    resumed = mod.run_incremental(runner, raw, prefix)
    assert not calls
    assert all(not ids for ids in resumed['stages'].values())


def test_expected_clean_hold_without_manifest_is_fatal(tmp_path, monkeypatch):
    mod, runner, raw, prefix, _, _ = _partitioned_clean_dataset(tmp_path, monkeypatch)
    from stage_manifest import MANIFEST_NAME
    value = json.loads((raw / '1.json').read_text())
    value['test_clean_outcome'] = 'incomplete'
    (raw / '1.json').write_text(json.dumps(value))
    mod.run_incremental(runner, raw, prefix)
    (prefix / 'incomplete' / MANIFEST_NAME).unlink()
    with pytest.raises(mod.StageManifestError, match='manifest'):
        mod.run_incremental(runner, raw, prefix)


def test_initial_incremental_result_reports_clean_holds(tmp_path, monkeypatch):
    from pathlib import Path
    import shutil
    mod, runner, raw, seeded, _, _ = _partitioned_clean_dataset(tmp_path, monkeypatch)
    value = json.loads((raw / '1.json').read_text())
    value['test_clean_outcome'] = 'incomplete'
    (raw / '1.json').write_text(json.dumps(value))
    mod.run_incremental(runner, raw, seeded)
    def full_build(**kwargs):
        for source, target in zip(mod.stage_directories(seeded), mod.stage_directories(Path(kwargs['output_prefix']))):
            shutil.copytree(source, target)
        for name in ('incomplete', 'needs_review', 'errors'):
            if (seeded / name).exists():
                shutil.copytree(seeded / name, Path(kwargs['output_prefix']) / name)
        return {'success': True}
    runner.run_pipeline = full_build
    fresh = tmp_path / 'fresh'
    result = mod.run_incremental(runner, raw, fresh)
    assert result['held_clean_inputs']['incomplete'] == ['1']
    assert result['stages'] == {'clean': ['1', '2'], 'enrich': ['2'], 'score': ['2']}
    assert any('incomplete' in reason for reason in result['reasons'])
    resumed = mod.run_incremental(runner, raw, fresh)
    assert resumed['held_clean_inputs']['incomplete'] == ['1']
    assert all(not ids for ids in resumed['stages'].values())


def test_initial_partial_clean_error_is_committed_before_next_retry(tmp_path, monkeypatch):
    from pathlib import Path
    mod, runner, raw, _, calls, clean_inputs = _partitioned_clean_dataset(tmp_path, monkeypatch, good_count=20)
    value = json.loads((raw / '1.json').read_text())
    value['test_clean_outcome'] = 'errors'
    (raw / '1.json').write_text(json.dumps(value))
    def full_build(**kwargs):
        root = Path(kwargs['output_prefix'])
        runner.run_clean(kwargs['raw_dir'], root)
        successful = json.loads((root / 'cleaned' / 'batch.json').read_text())
        for directory in mod.stage_directories(root)[1:]:
            directory.mkdir(parents=True)
            (directory / 'batch.json').write_text(json.dumps(successful))
        from stage_manifest import write_stage_manifest_from_directory
        for stage, directory in zip(mod.STAGES, mod.stage_directories(root)):
            write_stage_manifest_from_directory(directory, stage, input_fingerprints={
                **mod.current_snapshot(tmp_path)['stages'][stage], 'stage_data_sha256_v1': '1' * 64})
        return {'success': True}
    runner.run_pipeline = full_build
    initial_clean = runner.run_clean
    def clean_once(source, output, **kwargs):
        if len(list(Path(source).glob('*.json'))) == 1:
            return False  # Retrying the only failed item must retain the prior generation.
        return initial_clean(source, output, **kwargs)
    runner.run_clean = clean_once
    fresh = tmp_path / 'fresh_error'
    result = mod.run_incremental(runner, raw, fresh)
    assert result['held_clean_inputs']['errors'] == ['1']
    assert set(result['stages']['score']) == {str(i) for i in range(2, 22)}
    assert clean_inputs == [sorted(str(i) for i in range(1, 22))]
    before = {path: path.read_bytes() for root in (fresh, Path(str(fresh) + '_enriched'), Path(str(fresh) + '_scored'))
              for path in root.rglob('*') if path.is_file()}
    with pytest.raises(mod.StageManifestError, match='prior outputs retained'):
        mod.run_incremental(runner, raw, fresh)
    assert all(path.read_bytes() == contents for path, contents in before.items())


@pytest.mark.parametrize('separator', ['\u0085', '\u2028', '\u2029'])
def test_clean_jsonl_keeps_unicode_line_separators_inside_strings(tmp_path, separator):
    from stage_manifest import write_stage_manifest
    from pipeline_incremental import stage_products, materialize_merged
    old, new = tmp_path / 'old', tmp_path / 'new'
    old.mkdir()
    new.mkdir()
    path = old / 'cleaned_batch_1.jsonl'
    row = {'id': '1', 'name': 'before' + separator + 'after'}
    path.write_text(json.dumps(row, ensure_ascii=False) + '\n', encoding='utf-8')
    write_stage_manifest(old, 'clean', [path])
    assert stage_products(old, 'clean') == {'1': row}
    materialize_merged(old, new, 'clean', {'1': row})
    assert (new / path.name).read_bytes() == path.read_bytes()


def test_deleted_clean_hold_is_absent_from_plan_and_execution(tmp_path, monkeypatch):
    mod, runner, raw, prefix, _, _ = _partitioned_clean_dataset(tmp_path, monkeypatch)
    value = json.loads((raw / '1.json').read_text())
    value['test_clean_outcome'] = 'incomplete'
    (raw / '1.json').write_text(json.dumps(value))
    mod.run_incremental(runner, raw, prefix)
    (raw / '1.json').unlink()
    for plan_only in (True, False):
        result = mod.run_incremental(runner, raw, prefix, plan_only=plan_only)
        assert result['deleted'] == ['1']
        assert all('1' not in ids for ids in result['held_clean_inputs'].values())


def test_incremental_clean_rate_uses_whole_verified_dataset(tmp_path, monkeypatch):
    mod, runner, raw, prefix, calls, clean_inputs = _partitioned_clean_dataset(tmp_path, monkeypatch, good_count=102)
    for identifier in ('1', '2', '3'):
        path = raw / (identifier + '.json')
        row = json.loads(path.read_text())
        row['test_clean_outcome'] = 'errors'
        path.write_text(json.dumps(row))
    mod.run_incremental(runner, raw, prefix)
    runner.test_enforce_rate = True
    clean_inputs.clear()
    calls.clear()
    path = raw / '4.json'
    row = json.loads(path.read_text())
    row['dose'] = 40
    path.write_text(json.dumps(row))
    result = mod.run_incremental(runner, raw, prefix)
    assert result['stages'] == {'clean': ['1', '2', '3', '4'], 'enrich': ['4'], 'score': ['4']}
    assert clean_inputs == [['1', '2', '3', '4']]
    assert result['held_clean_inputs']['errors'] == ['1', '2', '3']
    clean_inputs.clear()
    resumed = mod.run_incremental(runner, raw, prefix)
    assert resumed['stages'] == {'clean': ['1', '2', '3'], 'enrich': [], 'score': []}
    assert clean_inputs == [['1', '2', '3']]


@pytest.mark.parametrize('minimum', [None, 99.0])
def test_incremental_clean_global_below_threshold_retains_generation(tmp_path, monkeypatch, minimum):
    mod, runner, raw, prefix, _, _ = _partitioned_clean_dataset(tmp_path, monkeypatch,
        good_count=20 if minimum is not None else 1)
    if minimum is not None:
        runner.script_dir.mkdir(parents=True)
        (runner.script_dir / 'strict_clean.json').write_text(json.dumps({'validation': {'min_success_rate': minimum}}))
        runner.config = {'configs': {'clean': 'strict_clean.json'}}
    row = json.loads((raw / '1.json').read_text())
    row['test_clean_outcome'] = 'errors'
    (raw / '1.json').write_text(json.dumps(row))
    before = {path: path.read_bytes() for root in mod.stage_directories(prefix)
              for path in root.rglob('*') if path.is_file()}
    with pytest.raises(mod.StageManifestError, match='success rate|Success rate|95'):
        mod.run_incremental(runner, raw, prefix)
    assert all(path.read_bytes() == data for path, data in before.items())


@pytest.mark.parametrize('clock_field', ['evaluation_date', 'evaluation_local_date'])
def test_clock_rollover_during_execution_refuses_promotion(tmp_path, monkeypatch, clock_field):
    mod, runner, raw, prefix, _, snapshot = _synthetic_dataset(tmp_path, monkeypatch)
    snapshot[clock_field] = '2026-11-05'
    # Bind the baseline to the start date before attempting changed input work.
    mod.run_incremental(runner, raw, prefix)
    before = {path: path.read_bytes() for directory in (prefix, *mod.stage_directories(prefix)[1:])
              for path in directory.rglob('*') if path.is_file()}
    original = runner.run_enrich
    def rollover(*args, **kwargs):
        snapshot[clock_field] = '2026-11-06'
        return original(*args, **kwargs)
    monkeypatch.setattr(runner, 'run_enrich', rollover)
    (raw / '1.json').write_text(json.dumps({'id': '1', 'dose': 30}))
    with pytest.raises(mod.StageManifestError, match='Inputs changed during incremental execution'):
        mod.run_incremental(runner, raw, prefix)
    assert all(path.read_bytes() == contents for path, contents in before.items())


def test_comparison_date_pin_preserves_live_source_changes(monkeypatch):
    import pipeline_incremental as incremental
    source = {'stages': {'clean': {'code': 'before'}}, 'references': {'entry': 'before'},
              'evaluation_date': '2026-11-05', 'evaluation_local_date': '2026-11-05'}
    calls = []
    def real_snapshot(repo):
        calls.append(repo)
        return deepcopy(source)
    monkeypatch.setattr(incremental, 'current_snapshot', real_snapshot)
    _pin_comparison_dates(monkeypatch)
    first = incremental.current_snapshot('repo')
    source['stages']['clean']['code'] = 'after'
    source['references']['entry'] = 'after'
    source['evaluation_date'] = source['evaluation_local_date'] = '2026-11-06'
    second = incremental.current_snapshot('repo')
    assert calls == ['repo', 'repo']
    assert first['stages'] != second['stages']
    assert first['references'] != second['references']
    for field in ('evaluation_date', 'evaluation_local_date'):
        assert first[field] == second[field]


@pytest.mark.parametrize('stage', ['clean', 'enrich'])
@pytest.mark.parametrize('changed', [False, True])
def test_code_recheck_propagates_only_changed_stage_products(tmp_path, monkeypatch, stage, changed):
    mod, runner, raw, prefix, calls, snapshot = _synthetic_dataset(tmp_path, monkeypatch)
    snapshot['stages'][stage]['stage_code_sha256_v1'] = digest('new code')
    original = getattr(runner, 'run_' + stage)
    def execute(source, output, **kwargs):
        success = original(source, output, **kwargs)
        from pathlib import Path
        path = Path(output) / {'clean': 'cleaned', 'enrich': 'enriched'}[stage] / 'batch.json'
        rows = json.loads(path.read_text())
        if changed:
            changed_row = next(row for row in rows if row['id'] == '1')
            changed_row['quality_score_status'] = 'suppressed_safety'
            changed_row['assessment'] = {'is_complete': False}
        path.write_text(json.dumps(rows))
        return success
    monkeypatch.setattr(runner, 'run_' + stage, execute)
    result = mod.run_incremental(runner, raw, prefix)
    expected = {'clean': [], 'enrich': [], 'score': []}
    expected[stage] = ['1', '2']
    if changed:
        for downstream in (['enrich', 'score'] if stage == 'clean' else ['score']):
            expected[downstream] = ['1']
    assert result['stages'] == expected


def test_independent_score_invalidation_survives_unchanged_upstream_recheck(tmp_path, monkeypatch):
    mod, runner, raw, prefix, calls, snapshot = _synthetic_dataset(tmp_path, monkeypatch)
    for stage in ('clean', 'score'):
        snapshot['stages'][stage]['stage_code_sha256_v1'] = digest('new ' + stage)
    assert mod.run_incremental(runner, raw, prefix)['stages'] == {
        'clean': ['1', '2'], 'enrich': [], 'score': ['1', '2']}


def test_enrich_semantics_ignores_clock_only_and_preserves_contract_fields():
    from pipeline_incremental import stage_semantics
    row = {'id': '1', 'enriched_date': '2026-11-05T12:00:00Z',
           'enrichment_metadata': {'generated_at': 'old', 'ready_for_scoring': True},
           'match_ledger': {'generated_at': 'old', 'unmatched': []},
           'product_safety_status': 'no_known_catalog_concern',
           'quality_score_status': 'scored', 'assessment': {'is_complete': True}}
    later = deepcopy(row)
    later['enriched_date'] = '2026-11-05T13:00:00Z'
    later['enrichment_metadata']['generated_at'] = 'new'
    later['match_ledger']['generated_at'] = 'new'
    assert stage_semantics(row, stage='enrich') == stage_semantics(later, stage='enrich')
    for key, value in [('enriched_date', '2026-11-06T12:00:00Z'),
                       ('product_safety_status', 'blocked'), ('quality_score_status', 'not_scored'),
                       ('assessment', {'is_complete': False})]:
        altered = deepcopy(row)
        altered[key] = value
        assert stage_semantics(row, stage='enrich') != stage_semantics(altered, stage='enrich')
    assert row['enrichment_metadata']['generated_at'] == 'old'


@pytest.mark.parametrize('stage', ['clean', 'enrich'])
def test_runtime_recheck_selects_only_own_stage(tmp_path, monkeypatch, stage):
    mod, runner, raw, prefix, calls, snapshot = _synthetic_dataset(tmp_path, monkeypatch)
    snapshot['stages'][stage]['stage_runtime_sha256_v1'] = digest('new runtime')
    result = mod.run_incremental(runner, raw, prefix)
    assert result['stages'] == {name: (['1', '2'] if name == stage else []) for name in mod.STAGES}


def test_changed_clean_stops_at_unchanged_enrich(tmp_path, monkeypatch):
    from pathlib import Path
    mod, runner, raw, prefix, calls, snapshot = _synthetic_dataset(tmp_path, monkeypatch)
    snapshot['stages']['clean']['stage_code_sha256_v1'] = digest('new clean')
    original = runner.run_clean
    def clean(source, output, **kwargs):
        success = original(source, output, **kwargs)
        path = Path(output) / 'cleaned' / 'batch.json'
        rows = json.loads(path.read_text())
        next(row for row in rows if row['id'] == '1')['new_clean_fact'] = True
        path.write_text(json.dumps(rows))
        return success
    original_enrich = runner.run_enrich
    def enrich(source, output):
        success = original_enrich(source, output)
        path = Path(output) / 'enriched' / 'batch.json'
        rows = json.loads(path.read_text())
        for row in rows:
            row.pop('new_clean_fact', None)
        path.write_text(json.dumps(rows))
        return success
    monkeypatch.setattr(runner, 'run_clean', clean)
    monkeypatch.setattr(runner, 'run_enrich', enrich)
    assert mod.run_incremental(runner, raw, prefix)['stages'] == {
        'clean': ['1', '2'], 'enrich': ['1'], 'score': []}


def test_current_snapshot_shares_reference_capture_and_rechecks_bytes(tmp_path, monkeypatch):
    import pipeline_incremental as mod
    import pipeline_freshness as freshness
    from pathlib import Path

    data = tmp_path / 'scripts' / 'data'
    data.mkdir(parents=True)
    reference = data / 'sample.json'
    reference.write_text('{"value": 1}')
    for stage in freshness.STAGES.values():
        entry = tmp_path / 'scripts' / stage['entry']
        entry.parent.mkdir(parents=True, exist_ok=True)
        entry.write_text('pass\n')
    counts = {'reads': 0}
    original_read = Path.read_bytes
    original_open = Path.open

    def read_bytes(path):
        if path == reference:
            counts['reads'] += 1
        return original_read(path)

    def open_file(path, *args, **kwargs):
        if path == reference and args and args[0] == 'rb':
            counts['reads'] += 1
        return original_open(path, *args, **kwargs)

    # read_bytes uses io.open directly; count its call and the independent
    # streaming verification, not implementation details of code hashing.
    monkeypatch.setattr(Path, 'read_bytes', read_bytes)
    monkeypatch.setattr(Path, 'open', open_file)
    result = mod.current_snapshot(tmp_path)
    assert counts['reads'] == 2
    assert len({v[freshness.REFERENCE_FINGERPRINT_KEY] for v in result['stages'].values()}) == 1
    assert result['references'] == mod.reference_snapshot(tmp_path)


@pytest.mark.parametrize('mutation', ['edit', 'add', 'delete'])
def test_current_snapshot_refuses_reference_changes_during_capture(tmp_path, monkeypatch, mutation):
    import pipeline_incremental as mod
    import pipeline_freshness as freshness
    data = tmp_path / 'scripts' / 'data'
    data.mkdir(parents=True)
    reference = data / 'sample.json'
    reference.write_text('{"value": 1}')
    for stage in freshness.STAGES.values():
        entry = tmp_path / 'scripts' / stage['entry']
        entry.parent.mkdir(parents=True, exist_ok=True)
        entry.write_text('pass\n')
    original = mod.reference_snapshot

    def snapshot(*args, **kwargs):
        value = original(*args, **kwargs)
        if mutation == 'edit':
            reference.write_text('{"value": 2}')
        elif mutation == 'add':
            (data / 'added.json').write_text('{}')
        else:
            reference.unlink()
        return value

    monkeypatch.setattr(mod, 'reference_snapshot', snapshot)
    with pytest.raises(mod.StageManifestError, match='Reference data changed'):
        mod.current_snapshot(tmp_path)
