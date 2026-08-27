"""The benchmark tool: approval-gated, bench-prefix-confined, self-cleaning."""

from __future__ import annotations

import os
import sys

_scripts_dir = os.path.join(os.path.dirname(__file__), "..")
if _scripts_dir not in sys.path:
    sys.path.insert(0, os.path.abspath(_scripts_dir))


def test_refuses_without_explicit_approval(capsys):
    import benchmark_storage_ops as bench

    exit_code = bench.main([])

    assert exit_code == 2
    assert "--i-have-approval" in capsys.readouterr().out


def test_every_write_stays_under_the_bench_prefix_and_is_cleaned_up():
    import benchmark_storage_ops as bench

    class _Bucket:
        def __init__(self):
            self.objects = {}
            self.writes = []

        def upload(self, path, payload, _opts=None):
            self.writes.append(path)
            self.objects[path] = payload

        def copy(self, src, dst):
            self.writes.append(dst)
            self.objects[dst] = self.objects[src]
            return {"ok": True}

        def list(self, path="", options=None):
            opts = options or {}
            limit = int(opts.get("limit", 1000))
            offset = int(opts.get("offset", 0))
            base = path.rstrip("/") + "/" if path else ""
            names, seen = [], set()
            for full in sorted(self.objects):
                if not full.startswith(base):
                    continue
                head = full[len(base):].split("/", 1)[0]
                if head not in seen:
                    seen.add(head)
                    names.append(head)
            return [{"name": n} for n in names[offset:offset + limit]]

        def remove(self, paths):
            for p in paths:
                self.objects.pop(p, None)
            return [{"name": p} for p in paths]

    bucket = _Bucket()

    class _Client:
        storage = property(lambda self: self)

        def from_(self, _name):
            return bucket

    report = bench.run_benchmark(
        _Client, sample_bytes=[16], objects_per_level=3, project_count=1000,
    )

    assert all(p.startswith("shared/_bench/") for p in bucket.writes), (
        "the benchmark must never write outside its throwaway prefix"
    )
    assert report["prefix_empty_after"] is True
    assert not bucket.objects, "cleanup must remove everything it created"
    assert report["selected"] is not None
    assert report["projected"]["count"] == 1000
