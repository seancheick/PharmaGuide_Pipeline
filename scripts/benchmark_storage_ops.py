#!/usr/bin/env python3
"""Benchmark Supabase storage copy/delete throughput on an isolated prefix.

Phase 3 of the storage-cleanup acceleration plan. Selects the copy concurrency
for the shard-window quarantine engine from MEASUREMENT, not guesswork — the
listing side already proved concurrency assumptions wrong once (8 workers
healthy, 24 slower AND incomplete).

Every write this tool makes is confined to ``shared/_bench/<run-id>/`` — a
throwaway prefix it creates and fully deletes. It never touches active blobs,
quarantine, or version directories. It still writes to the production bucket,
so it REFUSES to run without ``--i-have-approval``.

Usage (after explicit operator approval):
    scripts/benchmark_storage_ops.py --i-have-approval \
        --sample-bytes 4096,32768,262144,1048576 --objects-per-level 64

Output: per-worker-level p50/p95/throughput, the selected worker count per the
promotion rule (highest level with zero mismatches, zero unresolved transient
failures, p95 <= 1.2x the previous level), and a projected ETA for a given
``--project-count``.
"""

from __future__ import annotations

import argparse
import json
import os
import sys
import time
import uuid
from concurrent.futures import ThreadPoolExecutor

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import env_loader  # noqa: F401,E402

from release_safety.blob_inventory import list_storage_page  # noqa: E402
from release_safety.quarantine import remove_storage_batch  # noqa: E402
from release_safety.transient import retry_transient  # noqa: E402

BUCKET = "pharmaguide"
BENCH_ROOT = "shared/_bench"
WORKER_LEVELS = (1, 2, 4, 8)
P95_REGRESSION_LIMIT = 1.2


def _percentile(values, q):
    if not values:
        return 0.0
    ordered = sorted(values)
    idx = min(len(ordered) - 1, max(0, int(round(q * (len(ordered) - 1)))))
    return ordered[idx]


def _upload(client, path, payload):
    client.storage.from_(BUCKET).upload(
        path, payload, {"content-type": "application/json", "upsert": "true"},
    )


def _copy(client, src, dst):
    from release_safety.quarantine import _copy_storage_object

    ok, err = _copy_storage_object(client, BUCKET, src, dst)
    if not ok:
        raise RuntimeError(err or "copy failed")


def _list_names(client, prefix):
    names = []
    offset = 0
    while True:
        items = retry_transient(
            lambda offset=offset: list_storage_page(
                client.storage.from_(BUCKET), prefix, offset,
            ),
            max_attempts=5,
        )
        if not items:
            break
        names.extend(i["name"] for i in items if isinstance(i, dict) and i.get("name"))
        if len(items) < 1000:
            break
        offset += 1000
    return names


def run_benchmark(client_factory, *, sample_bytes, objects_per_level,
                  project_count=None, out_path=None):
    run_id = uuid.uuid4().hex[:12]
    root = f"{BENCH_ROOT}/{run_id}"
    base_client = client_factory()
    print(f"Benchmark prefix: {root}/ (throwaway; deleted at the end)")

    # Seed one source set per size quantile.
    sources = []
    for size in sample_bytes:
        payload = os.urandom(size)
        for i in range(objects_per_level):
            path = f"{root}/src/{size}/{i:04d}.bin"
            _upload(base_client, path, payload)
            sources.append(path)
    print(f"Seeded {len(sources)} source object(s).")

    results = []
    prev_p95 = None
    selected = None
    for workers in WORKER_LEVELS:
        import threading

        thread_local = threading.local()

        def worker_client():
            if not hasattr(thread_local, "client"):
                thread_local.client = client_factory()
            return thread_local.client

        latencies = []
        errors = []

        def one_copy(idx_path):
            idx, src = idx_path
            dst = f"{root}/dst/w{workers}/{idx:05d}.bin"
            t0 = time.monotonic()
            try:
                retry_transient(
                    lambda: _copy(worker_client(), src, dst), max_attempts=4,
                )
            except Exception as exc:  # noqa: BLE001
                errors.append(f"{type(exc).__name__}: {exc}")
                return
            latencies.append(time.monotonic() - t0)

        started = time.monotonic()
        with ThreadPoolExecutor(max_workers=workers) as pool:
            list(pool.map(one_copy, enumerate(sources)))
        elapsed = time.monotonic() - started

        expected = len(sources) - len(errors)
        landed = len(_list_names(base_client, f"{root}/dst/w{workers}"))
        mismatches = expected - landed
        p95 = _percentile(latencies, 0.95)
        throughput = len(latencies) / elapsed if elapsed else 0.0
        row = {
            "workers": workers,
            "copies": len(latencies),
            "errors": len(errors),
            "mismatches": mismatches,
            "p50_s": round(_percentile(latencies, 0.50), 4),
            "p95_s": round(p95, 4),
            "elapsed_s": round(elapsed, 2),
            "copies_per_s": round(throughput, 2),
        }
        results.append(row)
        print(
            f"  workers={workers}: {row['copies_per_s']:.1f} copies/s, "
            f"p95={row['p95_s']:.3f}s, errors={row['errors']}, "
            f"mismatches={mismatches}"
        )

        healthy = not errors and mismatches == 0 and (
            prev_p95 is None or p95 <= prev_p95 * P95_REGRESSION_LIMIT
        )
        if healthy:
            selected = row
        if not errors:
            prev_p95 = p95

    # Full cleanup, then prove the prefix empty.
    leftovers = []
    for sub in ("src", "dst"):
        for size_or_w in _list_names(base_client, f"{root}/{sub}"):
            prefix = f"{root}/{sub}/{size_or_w}"
            names = _list_names(base_client, prefix)
            paths = [f"{prefix}/{n}" for n in names]
            for start in range(0, len(paths), 500):
                remove_storage_batch(base_client, BUCKET, paths[start:start + 500])
            leftovers.extend(_list_names(base_client, prefix))
    print(f"Cleanup: {'prefix empty' if not leftovers else f'LEFTOVERS: {leftovers}'}")

    report = {
        "run_id": run_id,
        "levels": results,
        "selected": selected,
        "prefix_empty_after": not leftovers,
    }
    if selected and project_count:
        eta_s = project_count / selected["copies_per_s"]
        report["projected"] = {
            "count": project_count,
            "eta_seconds": round(eta_s),
            "eta_human": f"{eta_s / 3600:.1f} h" if eta_s > 5400 else f"{eta_s / 60:.1f} min",
        }
        print(
            f"Selected workers={selected['workers']}; projected "
            f"{project_count:,} copies ≈ {report['projected']['eta_human']}"
        )
    if out_path:
        with open(out_path, "w") as f:
            json.dump(report, f, indent=2, sort_keys=True)
        print(f"Report written to {out_path}")
    return report


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument(
        "--i-have-approval", action="store_true", default=False,
        help="Required. This tool WRITES to the production bucket (isolated "
             "shared/_bench/ prefix only). Run it only with explicit approval.",
    )
    parser.add_argument("--sample-bytes", default="4096,32768,262144,1048576")
    parser.add_argument("--objects-per-level", type=int, default=64)
    parser.add_argument("--project-count", type=int, default=None)
    parser.add_argument("--out", default=None)
    args = parser.parse_args(argv)

    if not args.i_have_approval:
        print(
            "[refused] Benchmarks write to the production bucket (isolated "
            "shared/_bench/ prefix). Re-run with --i-have-approval once the "
            "operator has explicitly approved benchmark writes."
        )
        return 2

    from supabase_client import get_supabase_client

    run_benchmark(
        get_supabase_client,
        sample_bytes=[int(x) for x in args.sample_bytes.split(",") if x],
        objects_per_level=args.objects_per_level,
        project_count=args.project_count,
        out_path=args.out,
    )
    return 0


if __name__ == "__main__":
    sys.exit(main())
