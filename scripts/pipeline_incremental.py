"""Product-level execution for PipelineRunner, using its existing stage entrypoints.

Unknown reference or code dependencies widen the plan. Reuse requires verified
stage ownership, raw lineage and a stored baseline, never merely a matching ID.
"""
from __future__ import annotations

import hashlib
import copy
import json
import os
import shutil
import tempfile
from datetime import date, datetime, timezone
from pathlib import Path

from pipeline_freshness import (
    DATA_FINGERPRINT_KEY, REFERENCE_FINGERPRINT_KEY,
    STAGES, _reference_data_files, _content_set_fingerprint, stage_data_files, stage_data_fingerprint,
    stage_input_fingerprints,
)
from stage_manifest import MANIFEST_NAME, StageManifestError, select_stage_input_files, write_stage_manifest_from_directory


def digest(value):
    return hashlib.sha256(json.dumps(value, sort_keys=True, ensure_ascii=False,
                                     separators=(",", ":")).encode()).hexdigest()


def product_id(product):
    value = product.get("id") or product.get("dsld_id")
    if value is None or not str(value).strip():
        raise StageManifestError("Product has no stable ID")
    return str(value)


def raw_products(directory, *, include_paths=False):
    rows = {}
    paths = {}
    for path in stage_data_files(directory):
        value = json.loads(path.read_text())
        if not isinstance(value, dict):
            raise StageManifestError(f"Expected one raw label object: {path}")
        identifier = product_id(value)
        if identifier in rows:
            raise StageManifestError(f"Duplicate raw ID: {identifier}")
        rows[identifier] = value
        paths[identifier] = path.name
    return (rows, paths) if include_paths else rows


def stage_products(directory, stage):
    rows = {}
    for path in select_stage_input_files(directory, stage, require_manifest=True,
                                        patterns=("*.json",)):
        payload = json.loads(path.read_text())
        if not isinstance(payload, list):
            raise StageManifestError(f"Expected product array: {path}")
        for product in payload:
            identifier = product_id(product)
            if identifier in rows:
                raise StageManifestError(f"Duplicate stage ID: {identifier}")
            rows[identifier] = product
    return rows


def reference_snapshot(repo, *, contents=None):
    """Record changed-entry hashes and lookup vocabularies for bounded invalidation."""
    repo = Path(repo).resolve()
    result = {}
    for path in _reference_data_files(repo):
        relative = path.relative_to(repo).as_posix()
        payload = json.loads(contents[path] if contents is not None else path.read_bytes())
        if path.name == "ingredient_quality_map.json":
            entries = {k: v for k, v in payload.items() if not k.startswith("_")}
            # Any lookup vocabulary change can alter a formerly different match.
            vocabulary = {k: lookup_vocabulary(v) for k, v in entries.items()}
            result[relative] = {"kind": "identity", "entries": {k: digest(v) for k, v in entries.items()},
                                "vocabulary": digest(vocabulary),
                                "metadata": digest({key: value for key, value in payload.get("_metadata", {}).items()
                                                    if key not in {"last_updated", "total_entries", "statistics"}})}
        elif relative.endswith("curated_overrides/product_label_corrections.json"):
            result[relative] = {"kind": "label", "entries": {
                k: digest(v) for k, v in payload["corrections"].items()}}
        elif path.name == "literature_evidence_records.json":
            entries = payload["literature_evidence_records"]
            keys = [str(v["canonical_id"]) for v in entries]
            if len(keys) != len(set(keys)):
                raise StageManifestError("Duplicate literature canonical IDs")
            from dose_assessment import _record_names
            result[relative] = {"kind": "research", "entries": {
                str(v["canonical_id"]): digest(v) for v in entries},
                "scopes": {str(v["canonical_id"]): {
                    "bounded": ((v.get("reference_semantics") or {}).get("scope") == "exact_preparation"
                                and (v.get("applicability") or {}).get("require_source_label_form") is True
                                and not v.get("qualifying_human_studies") and v.get("effect_direction") is None),
                    "names": sorted(_record_names(v)),
                } for v in entries}}
        else:
            result[relative] = {"kind": "global", "hash": digest(payload)}
    return result


def lookup_vocabulary(value):
    if isinstance(value, dict):
        return {key: (item if key in {"aliases", "source_form_aliases", "standard_name", "name"}
                      else lookup_vocabulary(item))
                for key, item in value.items()
                if key not in {"_metadata", "notes", "absorption", "absorption_structured",
                               "form_evidence", "bio_score", "consumer_note", "consumer_note_review"}}
    if isinstance(value, list):
        return [lookup_vocabulary(item) for item in value]
    return value


def dependencies(product):
    """Use all emitted identities and reference IDs, including excluded source rows."""
    from dose_assessment import _identity_text
    identifiers = set()
    names = set()
    unresolved = False
    clock_refresh_required = False
    enriched_at = str(product.get("enriched_date") or "")
    try:
        enriched_local_date = datetime.fromisoformat(enriched_at.replace("Z", "+00:00")).astimezone().date()
    except ValueError:
        enriched_local_date = None

    def visit(value):
        nonlocal unresolved, clock_refresh_required
        if isinstance(value, dict):
            if value.get("snapshot_date") and "snapshot_age_days" in value:
                from cert_resolver import _recency_status
                status, age = _recency_status(value["snapshot_date"])
                if (age != value["snapshot_age_days"]
                        or ("recency_status" in value and status != value["recency_status"])):
                    clock_refresh_required = True
            if value.get("date") and value.get("severity_level"):
                from scoring_v4.modules.generic_manufacturer import _count_class_i_in_3_years
                if (enriched_local_date is None
                        or _count_class_i_in_3_years([value], today=enriched_local_date)
                        != _count_class_i_in_3_years([value], today=date.today())):
                    clock_refresh_required = True
            for key, item in value.items():
                if key in {"canonical_id", "clinical_id", "source_id", "record_id"} and isinstance(item, str):
                    identifiers.add(item)
                if key == "raw_source_text" and isinstance(item, str):
                    names.add(_identity_text(item))
                if key == "mapped" and item is False:
                    unresolved = True
                visit(item)
        elif isinstance(value, list):
            for item in value:
                visit(item)

    visit(product)
    return {"identifiers": sorted(identifiers), "names": sorted(names), "unresolved": unresolved,
            "clock_refresh_required": clock_refresh_required}


def plan_changes(old, current, raw, dependency_rows):
    ids = set(raw)
    previous = set(old["raw"])
    selected = [set(), set(), set()]
    reasons = []
    identity_recheck = set()

    def widen(index, affected, reason):
        if not affected:
            return
        for downstream in range(index, 3):
            selected[downstream].update(affected)
        reasons.append(reason)

    clock_affected = {key for key in ids if dependency_rows.get(key, {}).get("clock_refresh_required")}
    if clock_affected:
        widen(1, clock_affected, "date-sensitive certification or manufacturer assessment needs refresh")
    changed_raw = {key for key in ids if old["raw"].get(key) != digest(raw[key])}
    widen(0, changed_raw, "new or changed raw labels")
    removed = previous - ids
    if removed:
        reasons.append("deleted raw labels removed from every stage")
    for index, stage in enumerate(STAGES):
        # Reference changes are classified below. Runtime/code changes use the
        # existing transitive stage fingerprints, not filename guesses.
        before = old["stages"][stage]
        after = current["stages"][stage]
        if any(before.get(key) != value for key, value in after.items()
               if key != REFERENCE_FINGERPRINT_KEY):
            widen(index, ids, f"{stage} code or runtime dependency changed")
    for path in set(old["references"]) | set(current["references"]):
        before = old["references"].get(path)
        after = current["references"].get(path)
        if before == after:
            continue
        if before is None or after is None or before["kind"] != after["kind"]:
            widen(0, ids, f"reference inventory changed: {path}")
            continue
        kind = after["kind"]
        if kind == "global" or (kind == "identity" and before.get("metadata") != after.get("metadata")):
            widen(0, ids, f"broad reference changed: {path}")
            continue
        changed = {key for key in set(before["entries"]) | set(after["entries"])
                   if before["entries"].get(key) != after["entries"].get(key)}
        if kind == "label":
            widen(0, ids & changed, f"exact label corrections changed: {path}")
        else:
            if kind == "research":
                scopes = [snapshot.get("scopes", {}).get(key)
                          for snapshot in (before, after) for key in changed
                          if key in snapshot["entries"]]
                if scopes and all(scope and scope["bounded"] for scope in scopes):
                    names = {name for scope in scopes for name in scope["names"]}
                    affected = {key for key in ids if key not in dependency_rows
                                or dependency_rows[key]["unresolved"]
                                or names.intersection(dependency_rows[key].get("names", []))
                                or changed.intersection(dependency_rows[key]["identifiers"])}
                    widen(1, affected, f"exact preparation Dose references changed: {path}")
                else:
                    widen(1, ids, f"broad research source dependencies changed: {path}")
            else:
                affected = {key for key in ids if key not in dependency_rows
                            or dependency_rows[key]["unresolved"]
                            or changed.intersection(dependency_rows[key]["identifiers"])}
                widen(0, affected, f"ingredient reference entries changed: {path}")
                if before["vocabulary"] != after["vocabulary"]:
                    # Recheck all identities cheaply through Clean. Only actual
                    # Clean changes and known users reach the expensive stages.
                    selected[0].update(ids)
                    identity_recheck.update(ids)
                    reasons.append("lookup vocabulary changed: recheck all Clean identities")
    return {"stages": {stage: sorted(selected[index]) for index, stage in enumerate(STAGES)},
            "deleted": sorted(removed), "reasons": reasons,
            "pending_identity_recheck": sorted(identity_recheck)}



def clean_semantics(product):
    value = copy.deepcopy(product)
    if isinstance(value, dict) and isinstance(value.get("metadata"), dict):
        value["metadata"].pop("lastCleaned", None)
    return value


def materialize_merged(original, candidate, stage, merged):
    """Preserve unchanged files byte for byte, replace only changed batches."""
    if not merged:
        (candidate / "incremental_empty.json").write_text("[]")
        return
    remaining = dict(merged)
    for path in select_stage_input_files(original, stage, require_manifest=True):
        prior = json.loads(path.read_text())
        kept = [remaining.pop(product_id(row)) for row in prior if product_id(row) in remaining]
        destination = candidate / path.name
        if kept == prior:
            shutil.copy2(path, destination)
        elif kept:
            destination.write_text(json.dumps(kept, ensure_ascii=False))
    if remaining:
        name = "incremental_new_products.json"
        destination = candidate / name
        inserted = json.loads(destination.read_text()) if destination.exists() else []
        inserted.extend(remaining.values())
        destination.write_text(json.dumps(inserted, ensure_ascii=False))


def stage_directories(prefix):
    return [prefix / "cleaned", Path(str(prefix) + "_enriched") / "enriched",
            Path(str(prefix) + "_scored") / "scored"]


def current_snapshot(repo):
    repo = Path(repo).resolve()
    stages = {stage: stage_input_fingerprints(repo, stage) for stage in STAGES}
    contents = {path: path.read_bytes() for path in _reference_data_files(repo)}
    binding = _content_set_fingerprint(
        contents, root=repo, file_digest=lambda path: hashlib.sha256(contents[path]).digest())
    if any(fields[REFERENCE_FINGERPRINT_KEY] != binding for fields in stages.values()):
        raise StageManifestError("Reference data changed while capturing dependencies")
    return {"stages": stages, "references": reference_snapshot(repo, contents=contents),
            "evaluation_date": datetime.now(timezone.utc).date().isoformat(),
            "evaluation_local_date": date.today().isoformat()}


def run_incremental(runner, raw_dir, prefix, *, plan_only=False, baseline_repo=None):
    """Build in isolation, verify unchanged inputs, then promote a complete dataset.

    The single state belongs to this dataset's stage manifests. A crash during
    promotion leaves a recovery marker and refuses further reuse until recovery.
    """
    import fcntl

    repo = runner.script_dir.parent
    prefix = Path(prefix).resolve()
    raw_dir = Path(raw_dir).resolve()
    prefix.parent.mkdir(parents=True, exist_ok=True)
    lock_path = prefix.parent / ("." + prefix.name + ".incremental.lock")
    with lock_path.open("a") as lock:
        fcntl.flock(lock, fcntl.LOCK_EX | fcntl.LOCK_NB)
        return _run_locked(runner, repo, raw_dir, prefix, plan_only, baseline_repo)



def recover_promotion(recovery, prefix):
    """Restore the previous complete generation before retrying a killed run."""
    entries = json.loads(recovery.read_text())
    expected = [prefix, Path(str(prefix) + "_enriched"), Path(str(prefix) + "_scored")]
    if not isinstance(entries, list) or len(entries) != 3:
        raise StageManifestError("Invalid incremental recovery journal")
    transaction = None
    for entry, live in zip(entries, expected):
        backup = Path(entry["backup"])
        candidate = Path(entry["candidate"])
        if (Path(entry["live"]) != live or backup.parent.parent != prefix.parent
                or not backup.parent.name.startswith("." + prefix.name + ".incremental-")
                or candidate.parent != backup.parent):
            raise StageManifestError("Recovery paths are outside the dataset transaction")
        if transaction is not None and backup.parent != transaction:
            raise StageManifestError("Recovery journal mixes transactions")
        transaction = backup.parent
    for entry in reversed(entries):
        live, backup = Path(entry["live"]), Path(entry["backup"])
        if backup.exists():
            if live.exists():
                shutil.rmtree(live)
            os.replace(backup, live)
        elif entry.get("existed") is False and not Path(entry["candidate"]).exists() and live.exists():
            shutil.rmtree(live)
    recovery.unlink()
    if transaction is not None:
        shutil.rmtree(transaction)





def copy_artifact(source, destination):
    """Retain generated evidence, including symlinks, without overwriting it."""
    destination.parent.mkdir(parents=True, exist_ok=True)
    if destination.exists() or destination.is_symlink():
        raise StageManifestError(f"Generated artifact archive collision: {destination}")
    if source.is_dir() and not source.is_symlink():
        shutil.copytree(source, destination, symlinks=True)
    else:
        shutil.copy2(source, destination, follow_symlinks=False)


def preserve_generation_artifacts(prefix, candidate_prefix):
    """Keep prior non-stage evidence explicitly historical, never as current."""
    for stage, live, candidate in zip(
            STAGES, (prefix, Path(str(prefix) + "_enriched"), Path(str(prefix) + "_scored")),
            (candidate_prefix, Path(str(candidate_prefix) + "_enriched"), Path(str(candidate_prefix) + "_scored"))):
        if not live.exists():
            continue
        current_history = candidate / ".incremental_artifacts"
        old_history = live / ".incremental_artifacts"
        if (old_history / "prior").exists():
            copy_artifact(old_history / "prior", current_history / "prior")
        stage_name = {"clean": "cleaned", "enrich": "enriched", "score": "scored"}[stage]
        manifest = json.loads((live / stage_name / MANIFEST_NAME).read_text())
        extras = [entry for entry in live.iterdir()
                  if entry.name not in {stage_name, ".incremental_artifacts"}]
        scoped = [entry for entry in old_history.iterdir() if entry.name != "prior"] if old_history.exists() else []
        if not extras and not scoped:
            continue
        generation = current_history / "prior" / digest(manifest)
        generation.mkdir(parents=True)
        (generation / "generation.json").write_text(json.dumps({
            "scope": "historical_generation", "original_root": str(live), "stage_manifest": manifest,
        }, indent=2))
        for entry in extras:
            copy_artifact(entry, generation / "artifacts" / entry.name)
        for entry in scoped:
            copy_artifact(entry, generation / "scoped_artifacts" / entry.name)


def promote_generation(prefix, candidate_prefix, transaction, recovery):
    """Promote all three owned roots, retaining the old generation on failure."""
    preserve_generation_artifacts(prefix, candidate_prefix)
    live_roots = [prefix, Path(str(prefix) + "_enriched"), Path(str(prefix) + "_scored")]
    candidate_roots = [candidate_prefix, Path(str(candidate_prefix) + "_enriched"),
                       Path(str(candidate_prefix) + "_scored")]
    # Keep a durable journal before any rename. On a normal exception all
    # completed renames are rolled back. A killed process fails closed.
    journal = [{"live": str(live), "candidate": str(candidate),
                "backup": str(transaction / ("backup-" + str(index))),
                "existed": live.exists()}
               for index, (live, candidate) in enumerate(zip(live_roots, candidate_roots))]
    with recovery.open("x") as handle:
        json.dump(journal, handle, indent=2)
        handle.flush()
        os.fsync(handle.fileno())
    promoted = []
    try:
        for entry in journal:
            live, candidate, backup = map(Path, (entry["live"], entry["candidate"], entry["backup"]))
            if live.exists():
                os.replace(live, backup)
            try:
                os.replace(candidate, live)
            except BaseException:
                if backup.exists():
                    os.replace(backup, live)
                raise
            promoted.append(entry)
    except BaseException:
        for entry in reversed(promoted):
            live, backup = Path(entry["live"]), Path(entry["backup"])
            shutil.rmtree(live)
            if backup.exists():
                os.replace(backup, live)
        recovery.unlink()
        raise
    recovery.unlink()



def verified_bootstrap_source(repo, baseline_repo, directories, raw_dir):
    """Prefer current verified outputs, then the supplied historical source."""
    from pipeline_freshness import reusable_stage_issue

    candidates = [Path(repo).resolve()]
    if baseline_repo is not None and Path(baseline_repo).resolve() not in candidates:
        candidates.append(Path(baseline_repo).resolve())
    last_issue = None
    for candidate in candidates:
        inputs = raw_dir
        for stage, directory in zip(STAGES, directories):
            last_issue = reusable_stage_issue(candidate, directory, stage, inputs)
            if last_issue:
                break
            inputs = directory
        else:
            return candidate
    raise StageManifestError(
        f"Cannot seed incremental reuse from unverified output: {last_issue}. "
        "Supply the exact --baseline-revision or complete one full build.")


def _run_locked(runner, repo, raw_dir, prefix, plan_only, baseline_repo):
    state_path = prefix / ".incremental_state.json"
    recovery = prefix.parent / ("." + prefix.name + ".incremental-recovery.json")
    if recovery.exists():
        if plan_only:
            raise StageManifestError("Interrupted promotion: run --incremental to recover before planning")
        recover_promotion(recovery, prefix)
    directories = stage_directories(prefix)
    raw_binding = stage_data_fingerprint(stage_data_files(raw_dir))
    raw, raw_names = raw_products(raw_dir, include_paths=True)
    raw_bytes = {key: (raw_dir / name).read_bytes() for key, name in raw_names.items()}
    if any(json.loads(raw_bytes[key]) != value for key, value in raw.items()):
        raise StageManifestError("Raw objects differ from their captured source bytes")
    captured_hashes = {raw_dir / raw_names[key]: hashlib.sha256(content).digest()
                       for key, content in raw_bytes.items()}
    if stage_data_fingerprint(captured_hashes, content_hashes=captured_hashes) != raw_binding:
        raise StageManifestError("Captured raw bytes differ from the planning source inventory")
    raw_files = {key: stage_data_fingerprint([raw_dir / name], content_hashes=captured_hashes)
                 for key, name in raw_names.items()}
    current = current_snapshot(repo)
    if stage_data_fingerprint(stage_data_files(raw_dir)) != raw_binding:
        raise StageManifestError("Raw inputs changed while reading the planning snapshot")
    if not all((directory / MANIFEST_NAME).is_file() for directory in directories):
        if state_path.exists():
            raise StageManifestError("Owned incremental stage is missing; restore or rebuild the dataset")
        plan = {"stages": {stage: sorted(raw) for stage in STAGES}, "deleted": [],
                "reasons": ["new dataset requires its initial full build"]}
        if plan_only:
            return plan
        live_roots = [prefix, Path(str(prefix) + "_enriched"), Path(str(prefix) + "_scored")]
        if any(root.exists() for root in live_roots):
            raise StageManifestError("Partial prior dataset has no complete ownership proof; run a full repair")
        transaction = Path(tempfile.mkdtemp(prefix="." + prefix.name + ".incremental-", dir=prefix.parent))
        candidate_prefix = transaction / prefix.name
        try:
            result = runner.run_pipeline(raw_dir=str(raw_dir), output_prefix=str(candidate_prefix),
                                         strict_release_gates=True)
            if not result["success"]:
                raise StageManifestError("Initial dataset build failed")
            _run_locked(runner, repo, raw_dir, candidate_prefix, False, None)
            if (digest(current_snapshot(repo)) != digest(current)
                    or stage_data_fingerprint(stage_data_files(raw_dir)) != raw_binding):
                raise StageManifestError("Inputs changed during initial incremental build")
            promote_generation(prefix, candidate_prefix, transaction, recovery)
            return plan
        finally:
            if not recovery.exists():
                shutil.rmtree(transaction)
    products = {stage: stage_products(directory, stage)
                for stage, directory in zip(STAGES, directories)}
    if state_path.exists():
        old = json.loads(state_path.read_text())
        for stage, directory in zip(STAGES, directories):
            manifest = json.loads((directory / MANIFEST_NAME).read_text())
            fingerprints = manifest["input_fingerprints"]
            if fingerprints.get("incremental_state_sha256") != digest(old):
                raise StageManifestError("Incremental state does not match the owned stage")
            expected = {**old["stages"][stage],
                        DATA_FINGERPRINT_KEY: old["inputs"][stage],
                        "incremental_state_sha256": digest(old)}
            if fingerprints != expected:
                raise StageManifestError(f"{stage} provenance differs from the verified generation")
            if old["outputs"][stage] != {key: digest(value) for key, value in products[stage].items()}:
                raise StageManifestError("Incremental cached products changed")
    else:
        baseline = verified_bootstrap_source(repo, baseline_repo, directories, raw_dir)
        old = current_snapshot(baseline)
        old["raw"] = {key: digest(value) for key, value in raw.items()}
        old["outputs"] = {stage: {key: digest(value) for key, value in rows.items()}
                          for stage, rows in products.items()}
        old["inputs"] = {
            stage: json.loads((directory / MANIFEST_NAME).read_text())["input_fingerprints"][DATA_FINGERPRINT_KEY]
            for stage, directory in zip(STAGES, directories)
        }
    dependency_rows = {key: dependencies(value) for key, value in products["enrich"].items()}
    plan = plan_changes(old, current, raw, dependency_rows)
    if state_path.exists() and raw_binding != old["inputs"]["clean"]:
        # Parsed equality cannot establish byte/path lineage. Re-run Clean
        # for changed source files, then let actual Clean changes select
        # downstream work. Older generations lack per-file proof: recheck
        # their dataset conservatively rather than inventing provenance.
        affected = {key for key in raw
                    if old.get("raw_files", {}).get(key) != raw_files[key]}
        if not affected and not plan["deleted"]:
            raise StageManifestError("Raw inventory changed without a matching per-file proof")
        plan["stages"]["clean"] = sorted(set(plan["stages"]["clean"]) | affected)
        plan["pending_identity_recheck"] = sorted(set(plan["pending_identity_recheck"]) | affected)
        plan["reasons"].append("raw file bytes or filenames changed: recheck Clean lineage")
    if plan_only:
        return plan
    if (state_path.exists() and not plan["deleted"]
            and not any(plan["stages"].values())
            and old["stages"] == current["stages"]
            and old["references"] == current["references"]
            and raw_binding == old["inputs"]["clean"]):
        return plan

    source_binding = digest(current)
    owned_binding = {stage: {key: digest(value) for key, value in rows.items()}
                     for stage, rows in products.items()}
    transaction = Path(tempfile.mkdtemp(prefix="." + prefix.name + ".incremental-", dir=prefix.parent))
    candidate_prefix = transaction / prefix.name
    candidate_dirs = stage_directories(candidate_prefix)
    try:
        for index, (stage, candidate_dir) in enumerate(zip(STAGES, candidate_dirs)):
            selected = set(plan["stages"][stage])
            merged = {key: value for key, value in products[stage].items()
                      if key not in plan["deleted"]}
            upstream = raw if index == 0 else products[list(STAGES)[index - 1]]
            if selected:
                stage_workspace = transaction / ("work-" + stage)
                stage_workspace.mkdir()
                input_dir = stage_workspace / "input"
                input_dir.mkdir()
                selected_rows = {key: upstream[key] for key in selected if key in upstream}
                if set(selected_rows) != selected:
                    raise StageManifestError(f"{stage}: selected upstream product missing")
                if stage == "clean":
                    for key, value in selected_rows.items():
                        # Execute the same parsed label snapshot that was planned.
                        (input_dir / raw_names[key]).write_bytes(raw_bytes[key])
                    output = stage_workspace / "result"
                    success = runner.run_clean(str(input_dir), str(output))
                    result_dir = output / "cleaned"
                else:
                    (input_dir / "batch.json").write_text(json.dumps(list(selected_rows.values()), ensure_ascii=False))
                    output = stage_workspace / "result"
                    if stage == "enrich":
                        success = runner.run_enrich(str(input_dir), str(output))
                        result_dir = output / "enriched"
                    else:
                        success = runner.run_score(str(input_dir), str(output))
                        result_dir = output / "scored"
                if not success:
                    raise StageManifestError(f"Incremental {stage} failed; prior outputs retained")
                # Run the same per-stage ownership boundary for the isolated result.
                write_stage_manifest_from_directory(result_dir, stage)
                replacement = stage_products(result_dir, stage)
                if set(replacement) != selected:
                    raise StageManifestError(f"{stage}: output ID inventory differs from selected inputs")
                if stage == "clean":
                    changed_clean = {key for key, value in replacement.items()
                                     if clean_semantics(value) != clean_semantics(merged.get(key))}
                    for downstream in ("enrich", "score"):
                        plan["stages"][downstream] = sorted(
                            set(plan["stages"][downstream]) | changed_clean)
                merged.update(replacement)
                candidate_root = (candidate_prefix if stage == "clean" else
                                  Path(str(candidate_prefix) + ("_enriched" if stage == "enrich" else "_scored")))
                artifact_root = candidate_root / ".incremental_artifacts" / "current" / stage
                # The worker's reports describe only selected products. Keep
                # that scope explicit beside the complete merged gate reports.
                artifact_root.mkdir(parents=True)
                (artifact_root / "scope.json").write_text(json.dumps({
                    "scope": "selected_products", "product_ids": sorted(selected),
                }, indent=2))
                for entry in output.iterdir():
                    if entry != result_dir:
                        copy_artifact(entry, artifact_root / entry.name)
            products[stage] = merged
            candidate_dir.mkdir(parents=True)
            materialize_merged(directories[index], candidate_dir, stage, merged)
        # The complete merged enrichment, not merely the changed slice, must pass.
        all_enriched = list(products["enrich"].values())
        valid, _ = runner.run_enrichment_contract_gate(
            all_enriched, strict_mode=True, report_dir=str(candidate_prefix) + "_enriched")
        if not valid:
            raise StageManifestError("Merged enrichment contract gate failed")
        valid, _ = runner.run_coverage_gate(
            str(candidate_dirs[1]), str(candidate_prefix) + "_enriched",
            products=all_enriched, strict_mode=True)
        if not valid:
            raise StageManifestError("Merged coverage gate failed")
        if (digest(current_snapshot(repo)) != source_binding
                or stage_data_fingerprint(stage_data_files(raw_dir)) != raw_binding):
            raise StageManifestError("Inputs changed during incremental execution")
        for stage, directory in zip(STAGES, directories):
            verified = stage_products(directory, stage)
            if {key: digest(value) for key, value in verified.items()} != owned_binding[stage]:
                raise StageManifestError("Prior stage outputs changed during incremental execution")
        state = {**current, "raw": {key: digest(value) for key, value in raw.items()},
                 "raw_files": raw_files,
                 "outputs": {stage: {key: digest(value) for key, value in rows.items()}
                             for stage, rows in products.items()},
                 "inputs": {
                     "clean": raw_binding,
                     "enrich": stage_data_fingerprint(stage_data_files(candidate_dirs[0])),
                     "score": stage_data_fingerprint(stage_data_files(candidate_dirs[1])),
                 }}
        state_hash = digest(state)
        for stage, directory in zip(STAGES, candidate_dirs):
            fingerprints = {**current["stages"][stage],
                            DATA_FINGERPRINT_KEY: state["inputs"][stage],
                            "incremental_state_sha256": state_hash}
            write_stage_manifest_from_directory(directory, stage, input_fingerprints=fingerprints)
        (candidate_prefix / ".incremental_state.json").write_text(json.dumps(state, sort_keys=True))
        promote_generation(prefix, candidate_prefix, transaction, recovery)
        return plan
    finally:
        if not recovery.exists():
            shutil.rmtree(transaction)
