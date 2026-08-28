"""RPC-backed inventory fast path: strict validation, walker always the net.

The SQL side (migrations/*_storage_inventory_rpc.sql) is applied only with its
own approval; these tests pin the CLIENT contract so the fast path can never
weaken the inventory:

  * a page shorter than the limit is NORMAL termination — never a fault;
  * real faults — RPC error, malformed row, duplicate or non-monotonic
    cursor, summary count/byte mismatch — raise ``RpcInventoryError``, and the
    flagged wrapper falls back to the shard walker;
  * the RPC result feeds the SAME aggregation as the walker (fingerprints,
    categories, integrity checks), so parity is structural, not incidental.
"""

from __future__ import annotations

import os
import sys
import time

import pytest

_scripts_dir = os.path.join(os.path.dirname(__file__), "..")
if _scripts_dir not in sys.path:
    sys.path.insert(0, os.path.abspath(_scripts_dir))

PREFIX = "shared/details/sha256"


@pytest.fixture(autouse=True)
def _no_real_backoff_sleeps(monkeypatch):
    monkeypatch.setattr(time, "sleep", lambda _s: None)


def _h(shard, n):
    return shard + f"{n:062x}"


def _path(h):
    return f"{PREFIX}/{h[:2]}/{h}.json"


class _RpcResult:
    def __init__(self, data):
        self.data = data

    def execute(self):
        return self


class _FakeRpcClient:
    """Serves both the RPC surface and (for fallback) the listing surface."""

    def __init__(self, objects, *, page_limit_served=1000):
        self.objects = dict(objects)  # full path -> bytes
        self.page_limit_served = page_limit_served
        self.rpc_calls = []
        self.list_calls = []
        self.fail_rpc = False
        self.tamper_rows = None      # callable(rows) -> rows
        self.tamper_summary = None   # callable(summary) -> summary
        self.storage = self

    # --- storage side (walker fallback) --------------------------------
    def from_(self, _name):
        return self

    def list(self, path="", options=None):
        self.list_calls.append(path)
        opts = options or {}
        limit = int(opts.get("limit", 1000))
        offset = int(opts.get("offset", 0))
        base = path.rstrip("/") + "/" if path else ""
        names = sorted(
            full[len(base):]
            for full in self.objects
            if full.startswith(base) and "/" not in full[len(base):]
        )
        return [
            {"name": n, "metadata": {
                "size": len(self.objects[base + n]),
                "eTag": f'"et-{n[:12]}"',
            }}
            for n in names[offset:offset + limit]
        ]

    # --- rpc side --------------------------------------------------------
    def rpc(self, fn, params=None):
        self.rpc_calls.append((fn, dict(params or {})))
        if self.fail_rpc:
            raise RuntimeError("rpc exploded")
        params = params or {}
        prefix = params["p_prefix"]
        rows = sorted(
            (full, data) for full, data in self.objects.items()
            if full.startswith(prefix.rstrip("/") + "/")
        )
        if fn.endswith("summary"):
            summary = [{
                "object_count": len(rows),
                "total_bytes": sum(len(d) for _p, d in rows),
            }]
            if self.tamper_summary:
                summary = self.tamper_summary(summary)
            return _RpcResult(summary)
        after = params.get("p_after")
        limit = min(int(params.get("p_limit", 1000)), self.page_limit_served)
        page = [
            {
                "name": full,
                "size": len(data),
                "etag": f'"et-{full.rsplit("/", 1)[-1][:12]}"',
                "updated_at": "2026-08-28T00:00:00Z",
            }
            for full, data in rows
            if after is None or full > after
        ][:limit]
        if self.tamper_rows:
            page = self.tamper_rows(page)
        return _RpcResult(page)


def _seed(hashes):
    return _FakeRpcClient({_path(h): b"data-" + h[:10].encode() for h in hashes})


# ---------------------------------------------------------------------------
# Happy path
# ---------------------------------------------------------------------------


def test_rpc_inventory_matches_walker_output_structurally():
    from release_safety.blob_inventory import (
        inventory_detail_blobs,
        inventory_detail_blobs_via_rpc,
    )

    hashes = [_h("aa", i) for i in range(3)] + [_h("bb", 1)]
    client = _seed(hashes)

    via_rpc = inventory_detail_blobs_via_rpc(client, prefix=PREFIX)
    via_walker = inventory_detail_blobs(client, shards=("aa", "bb"))

    assert via_rpc.complete is True
    assert via_rpc.sizes == via_walker.sizes
    assert via_rpc.etags == via_walker.etags
    assert via_rpc.categories == via_walker.categories


def test_short_page_is_normal_termination_not_a_fault():
    from release_safety.blob_inventory import inventory_detail_blobs_via_rpc

    hashes = [_h("aa", i) for i in range(5)]
    client = _seed(hashes)

    inv = inventory_detail_blobs_via_rpc(client, prefix=PREFIX, page_limit=1000)

    # One summary + ONE page (5 rows < 1000) — no extra probe call needed.
    page_calls = [c for c in client.rpc_calls if c[0].endswith("page")]
    assert len(page_calls) == 1
    assert inv.complete is True
    assert len(inv.hashes) == 5


def test_keyset_pagination_passes_the_last_name_as_cursor():
    from release_safety.blob_inventory import inventory_detail_blobs_via_rpc

    hashes = [_h("aa", i) for i in range(7)]
    client = _seed(hashes)

    inv = inventory_detail_blobs_via_rpc(client, prefix=PREFIX, page_limit=3)

    page_calls = [c for c in client.rpc_calls if c[0].endswith("page")]
    assert len(page_calls) == 3
    cursors = [c[1].get("p_after") for c in page_calls]
    assert cursors[0] is None
    assert cursors[1] and cursors[2] and cursors[1] < cursors[2]
    assert len(inv.hashes) == 7


# ---------------------------------------------------------------------------
# Fault triggers — each raises, and the flagged wrapper falls back
# ---------------------------------------------------------------------------


def _expect_rpc_error(client, match):
    from release_safety.blob_inventory import (
        RpcInventoryError,
        inventory_detail_blobs_via_rpc,
    )

    with pytest.raises(RpcInventoryError, match=match):
        inventory_detail_blobs_via_rpc(client, prefix=PREFIX, page_limit=3)


def test_malformed_row_is_a_fault():
    client = _seed([_h("aa", 1)])
    client.tamper_rows = lambda rows: [{"name": None, "bogus": True}]
    _expect_rpc_error(client, "malformed")


def test_duplicate_cursor_row_is_a_fault():
    client = _seed([_h("aa", i) for i in range(4)])

    def duplicate_first(rows):
        return [rows[0], rows[0]] + rows[1:] if rows else rows

    client.tamper_rows = duplicate_first
    _expect_rpc_error(client, "monotonic")


def test_summary_count_mismatch_is_a_fault():
    client = _seed([_h("aa", i) for i in range(4)])
    client.tamper_summary = lambda s: [{**s[0], "object_count": 999}]
    _expect_rpc_error(client, "summary")


def test_summary_bytes_mismatch_is_a_fault():
    client = _seed([_h("aa", i) for i in range(4)])
    client.tamper_summary = lambda s: [{**s[0], "total_bytes": 1}]
    _expect_rpc_error(client, "summary")


def test_flagged_wrapper_falls_back_to_the_walker_on_rpc_fault(monkeypatch):
    """The walker is the permanent net: any RPC fault must yield a walker
    inventory, not a failure and not a partial."""
    import release_safety.blob_inventory as bi

    hashes = [_h("aa", 1), _h("bb", 1)]
    client = _seed(hashes)
    client.fail_rpc = True
    monkeypatch.setenv("PG_STORAGE_INVENTORY_RPC", "1")

    inv = bi.inventory_detail_blobs(client, shards=("aa", "bb"))

    assert inv.complete is True
    assert len(inv.hashes) == 2
    assert client.list_calls, "fallback must actually use the walker"


def test_rpc_is_off_by_default(monkeypatch):
    import release_safety.blob_inventory as bi

    monkeypatch.delenv("PG_STORAGE_INVENTORY_RPC", raising=False)
    client = _seed([_h("aa", 1)])

    bi.inventory_detail_blobs(client, shards=("aa",))

    assert client.rpc_calls == [], "no RPC calls unless the flag is on"


def test_flag_on_and_healthy_rpc_skips_the_walker(monkeypatch):
    import release_safety.blob_inventory as bi

    monkeypatch.setenv("PG_STORAGE_INVENTORY_RPC", "1")
    client = _seed([_h("aa", 1), _h("bb", 1)])

    inv = bi.inventory_detail_blobs(client, shards=("aa", "bb"))

    assert inv.complete is True
    assert len(inv.hashes) == 2
    assert client.rpc_calls, "flag on + healthy RPC must use the fast path"
    assert client.list_calls == []


# ---------------------------------------------------------------------------
# CLI dual-read: --verify-inventory proves walker/RPC parity
# ---------------------------------------------------------------------------


def _world_for_cli(tmp_path, hashes):
    """A dual-surface client embedded in the CLI's expected world shape."""
    client = _seed(hashes)

    def table(name):
        class _T:
            def select(self, *_a, **_k):
                return self

            def order(self, *_a, **_k):
                return self

            def execute(self):
                return type("_R", (), {"data": []})()

        return _T()

    client.table = table
    return client


def test_cli_verify_inventory_reports_parity_ok(tmp_path, capsys, monkeypatch):
    import reconcile_orphan_blobs as cli

    hashes = [_h("aa", 1), _h("bb", 1)]
    client = _world_for_cli(tmp_path, hashes)

    exit_code = cli.main(
        ["--flutter-repo", str(tmp_path), "--dist-dir", str(tmp_path),
         "--retained-version", "x",
         "--shards", "aa,bb", "--verify-inventory"],
        client=client,
    )

    out = capsys.readouterr().out
    assert exit_code == 0
    assert "PARITY OK" in out
    assert client.rpc_calls and client.list_calls, "both paths must run"


def test_cli_verify_inventory_holds_release_lock_for_the_snapshot(
    tmp_path, monkeypatch,
):
    import reconcile_orphan_blobs as cli

    lock_path = tmp_path / "release.lock"
    observed = []

    def verify(_client, _shards):
        observed.append(lock_path.exists())
        return cli.EXIT_OK

    monkeypatch.setattr(cli, "_verify_inventory_parity", verify)

    exit_code = cli.main(
        [
            "--flutter-repo", str(tmp_path),
            "--dist-dir", str(tmp_path),
            "--verify-inventory",
            "--lock-path", str(lock_path),
        ],
        client=object(),
    )

    assert exit_code == cli.EXIT_OK
    assert observed == [True]
    assert not lock_path.exists()


def test_cli_verify_inventory_fails_on_divergence(tmp_path, capsys):
    import reconcile_orphan_blobs as cli

    hashes = [_h("aa", 1), _h("bb", 1)]
    client = _world_for_cli(tmp_path, hashes)
    # RPC serves a self-consistent but WRONG view: drop one object entirely
    # (rows and summary agree with each other, disagree with the walker).
    dropped = _path(hashes[1])
    hidden = dict(client.objects)

    real_rpc = client.rpc

    def rpc_without_one(fn, params=None):
        client.objects = {k: v for k, v in hidden.items() if k != dropped}
        try:
            return real_rpc(fn, params)
        finally:
            client.objects = hidden

    client.rpc = rpc_without_one

    exit_code = cli.main(
        ["--flutter-repo", str(tmp_path), "--dist-dir", str(tmp_path),
         "--retained-version", "x",
         "--shards", "aa,bb", "--verify-inventory"],
        client=client,
    )

    out = capsys.readouterr().out
    assert exit_code != 0
    assert "PARITY" in out and "OK" not in out.split("PARITY", 1)[1][:20]
