#!/usr/bin/env python3
"""Full frozen-corpus clean→enrich→score A/B driver — Phase-3 integration gate.

Runs the **production entry points** (clean_dsld_data.py → enrich_supplements_v3.py
→ score_products_v4.py) with an entire arm's ``scripts/`` tree, over the frozen
raw DSLD ingest corpus, and collects a compact per-product scored record as
JSONL. Two arms are then diffed by ``full_corpus_replay.py --compare`` (same
signature comparison) or by a scored-specific comparator.

Only the arm's own ``scripts/`` tree is used, so every module, data file and
config resolves to that arm — the arms differ only by the accepted commits.

The enrich stage is single-process and dominates runtime, so its input is
sharded and run concurrently. Everything is written under ``--out-root`` (never
into the repo's ``scripts/products``).

Usage:
    drive_pipeline_ab.py --arm integrated \
        --scripts-dir /path/to/integration/scripts \
        --raw-root "$HOME/Downloads/PharmaGuide_Datasets/staging/brands" \
        --out-root /tmp/pipelineB --enrich-workers 2 [--ids-file /tmp/ids.txt]
"""
from __future__ import annotations

import argparse
import json
import subprocess
import sys
import time
from pathlib import Path

REPO_SCRIPTS = Path(__file__).resolve()


def log(message: str) -> None:
    print(f"[{time.strftime('%H:%M:%S')}] {message}", flush=True)


def run_stage(label: str, script: Path, args: list, cwd: Path) -> None:
    cmd = [sys.executable, str(script), *args]
    log(f"{label}: {' '.join(cmd)}")
    started = time.time()
    result = subprocess.run(cmd, cwd=str(cwd))
    if result.returncode != 0:
        raise SystemExit(f"{label} failed rc={result.returncode}")
    log(f"{label}: done in {time.time() - started:.1f}s")


def discover_raw(raw_root: Path, ids: set) -> list:
    files = sorted(raw_root.glob("*/*.json"))
    files = [f for f in files if not f.name.startswith(".")]
    if ids:
        files = [f for f in files if f.stem in ids]
    return files


def shard_batches(batches: list, shards: int, shard_root: Path) -> list:
    """Split cleaned/enriched batch lists into `shards` input directories."""
    shard_root.mkdir(parents=True, exist_ok=True)
    buckets: list = [[] for _ in range(shards)]
    for index, path in enumerate(batches):
        buckets[index % shards].append(path)
    dirs = []
    for index, bucket in enumerate(buckets):
        target = shard_root / f"shard_{index}"
        target.mkdir(parents=True, exist_ok=True)
        for path in bucket:
            rows = json.loads(path.read_bytes())
            if not isinstance(rows, list):
                rows = [rows]
            (target / path.name).write_text(json.dumps(rows), encoding="utf-8")
        if bucket:
            dirs.append(target)
    return dirs


def run_concurrent(label: str, script: Path, cwd: Path, jobs: list, workers: int) -> None:
    """Run one subprocess per shard, `workers` at a time."""
    pending = list(jobs)
    running: list = []
    while pending or running:
        while pending and len(running) < workers:
            input_dir, output_dir = pending.pop(0)
            cmd = [
                sys.executable,
                str(script),
                "--input-dir",
                str(input_dir),
                "--output-dir",
                str(output_dir),
            ]
            running.append((subprocess.Popen(cmd, cwd=str(cwd)), input_dir, output_dir))
        time.sleep(2)
        still = []
        for proc, input_dir, output_dir in running:
            if proc.poll() is None:
                still.append((proc, input_dir, output_dir))
            elif proc.returncode != 0:
                raise SystemExit(f"{label} failed for {input_dir} rc={proc.returncode}")
        running = still
        log(f"{label}: {len(pending)} pending, {len(running)} running")


SCORE_FIELDS = (
    "dsld_id",
    "product_name",
    "brand_name",
    "scoring_status",
    "score_unavailable_reason",
    "blocking_reason",
    "not_scorable_reason",
    "quality_score_v4_100",
    "raw_score_v4_100",
    "display_100",
    "quality_tier",
    "grade",
    "verdict",
    "quality_score_status",
    "quality_score_suppressed_reason",
    "_v4_quality_status",
    "_v4_quality_score_cap",
    "_v4_score_unavailable_reason",
    "_v4_route_decision",
    "_v4_safety_gate",
    "_v4_safety_decision",
    "safety_verdict",
    "product_safety_status",
    "safety_signal_reason",
    "safety_decision",
    "_v4_safety_signal_reason",
    "_v4_assessment_readiness",
    "assessment_readiness",
    "_v4_completeness_gate",
    "strict_scoring_contract",
    "scoring_ingredients_source",
    "unmapped_actives_total",
)


def collect(paths: list, out_path: Path) -> None:
    written = 0
    with out_path.open("w", encoding="utf-8") as handle:
        for path in paths:
            rows = json.loads(path.read_bytes())
            if not isinstance(rows, list):
                rows = [rows]
            for row in rows:
                if not isinstance(row, dict):
                    continue
                record = {field: row.get(field) for field in SCORE_FIELDS}
                record["_safety_review_records"] = row.get("safety_review_records")
                record["_dose_safety"] = row.get("dose_safety_evaluation")
                record["_module_breakdown"] = row.get("_v4_module_breakdown")
                record["_pillars"] = row.get("_v4_pillars")
                record["_flags"] = row.get("flags")
                record["_badges"] = row.get("badges")
                for key in (
                    "quality_pillars_v4",
                    "iqd_contract_diagnostics",
                    "scoring_metadata",
                ):
                    record[key] = row.get(key)
                handle.write(json.dumps(record, sort_keys=True) + "\n")
                written += 1
    log(f"collected {written} scored records -> {out_path}")


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--arm", required=True)
    parser.add_argument("--scripts-dir", required=True)
    parser.add_argument("--raw-root", required=True)
    parser.add_argument("--out-root", required=True)
    parser.add_argument("--enrich-workers", type=int, default=2)
    parser.add_argument("--ids-file")
    parser.add_argument("--skip-clean", action="store_true")
    parser.add_argument("--skip-enrich", action="store_true")
    parser.add_argument(
        "--collect-stored",
        help="collect the frozen corpus's own scored artifacts instead of running the pipeline",
    )
    args = parser.parse_args()

    if args.collect_stored:
        root = Path(args.collect_stored).expanduser()
        batches = sorted(root.glob("output_*_scored/scored/scored_*.json"))
        log(f"[stored] {len(batches)} scored batches under {root}")
        collect(batches, Path(args.out_root) / "scored_records.jsonl")
        return 0

    scripts_dir = Path(args.scripts_dir).resolve()
    raw_root = Path(args.raw_root).expanduser().resolve()
    out_root = Path(args.out_root).resolve()
    out_root.mkdir(parents=True, exist_ok=True)

    ids = set()
    if args.ids_file:
        ids = {
            line.strip()
            for line in Path(args.ids_file).read_text().splitlines()
            if line.strip()
        }
    files = discover_raw(raw_root, ids)
    log(f"{args.arm}: {len(files)} raw records (ids filter={len(ids) or 'none'})")
    if not files:
        raise SystemExit("no raw records selected")

    raw_stage = out_root / "raw"
    raw_stage.mkdir(exist_ok=True)
    for path in files:
        link = raw_stage / path.name
        if not link.exists():
            link.symlink_to(path)

    cleaned_root = out_root / "cleaned"
    enriched_root = out_root / "enriched"
    scored_root = out_root / "scored"

    if not args.skip_clean:
        run_stage(
            f"{args.arm}/clean",
            scripts_dir / "clean_dsld_data.py",
            ["--input-dir", str(raw_stage), "--output-dir", str(cleaned_root)],
            scripts_dir,
        )

    cleaned_batches = sorted((cleaned_root / "cleaned").glob("cleaned_batch_*.json"))
    if not cleaned_batches:
        raise SystemExit(f"no cleaned batches under {cleaned_root}")
    log(f"{args.arm}: {len(cleaned_batches)} cleaned batches")

    shard_root = out_root / "_shards"
    if not args.skip_enrich:
        dirs = shard_batches(cleaned_batches, args.enrich_workers * 2, shard_root / "enrich")
        run_concurrent(
            f"{args.arm}/enrich",
            scripts_dir / "enrich_supplements_v3.py",
            scripts_dir,
            [(d, out_root / "enrich_out" / d.name) for d in dirs],
            args.enrich_workers,
        )

    enriched_batches = sorted((out_root / "enrich_out").glob("*/enriched/*.json"))
    if not enriched_batches:
        raise SystemExit("no enriched batches produced")
    log(f"{args.arm}: {len(enriched_batches)} enriched batches")

    dirs = shard_batches(enriched_batches, args.enrich_workers * 2, shard_root / "score")
    run_concurrent(
        f"{args.arm}/score",
        scripts_dir / "score_products_v4.py",
        scripts_dir,
        [(d, out_root / "score_out" / d.name) for d in dirs],
        args.enrich_workers,
    )

    scored = sorted((out_root / "score_out").glob("*/scored/*.json"))
    log(f"{args.arm}: {len(scored)} scored batches")
    collect(scored, out_root / "scored_records.jsonl")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
