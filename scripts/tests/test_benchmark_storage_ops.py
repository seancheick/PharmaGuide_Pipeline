"""The benchmark tool: approval-gated, bench-prefix-confined, self-cleaning."""

from __future__ import annotations

import os
import sys

import pytest

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


def _make_bucket_and_client(bench_module=None):
    class _Bucket:
        def __init__(self):
            self.objects = {}
            self.writes = []
            self.fail_upload_after = None

        def upload(self, path, payload, _opts=None):
            if (
                self.fail_upload_after is not None
                and len(self.writes) >= self.fail_upload_after
            ):
                raise RuntimeError("upload exploded mid-benchmark")
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

    return bucket, _Client


def test_cleanup_runs_even_when_the_benchmark_body_crashes(monkeypatch):
    """A crash mid-benchmark must not strand _bench objects in production."""
    import benchmark_storage_ops as bench

    bucket, _Client = _make_bucket_and_client()
    bucket.fail_upload_after = 2  # explode partway through seeding

    with pytest.raises(Exception):
        bench.run_benchmark(
            _Client, sample_bytes=[16], objects_per_level=4,
        )

    assert not bucket.objects, (
        "the throwaway prefix must be emptied even on a crash"
    )


def test_no_healthy_worker_level_is_a_nonzero_exit(monkeypatch, tmp_path):
    import benchmark_storage_ops as bench

    bucket, _Client = _make_bucket_and_client()

    def broken_run(client_factory, **kw):
        return {"selected": None, "prefix_empty_after": True, "levels": []}

    monkeypatch.setattr(bench, "run_benchmark", broken_run)
    monkeypatch.setattr(
        "supabase_client.get_supabase_client", lambda: _Client(), raising=False,
    )

    exit_code = bench.main(["--i-have-approval"])

    assert exit_code != 0, "an unusable benchmark must not exit 0"


def test_leftover_bench_objects_are_a_nonzero_exit(monkeypatch):
    import benchmark_storage_ops as bench

    def leaky_run(client_factory, **kw):
        return {
            "selected": {"workers": 4, "copies_per_s": 10.0},
            "prefix_empty_after": False,
            "levels": [],
        }

    monkeypatch.setattr(bench, "run_benchmark", leaky_run)
    monkeypatch.setattr(
        "supabase_client.get_supabase_client", lambda: object(), raising=False,
    )

    exit_code = bench.main(["--i-have-approval"])

    assert exit_code != 0, "unverified cleanup must not exit 0"
