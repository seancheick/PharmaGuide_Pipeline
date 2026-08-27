"""Scalable, honest inventory of the shared detail-blob store.

Measured against the live ``pharmaguide`` bucket on 2026-08-26 (~134,283
blobs):

  * ``POST object/list`` on the shard ROOT ``shared/details/sha256`` returns
    HTTP 544 ``DatabaseTimeout`` deterministically (~30s in). The inventory
    must therefore address the 256 hex shards directly and never the root.
  * A single shard listing costs ~1.5s warm and ~19s cold, and each shard
    holds ~500 objects — i.e. one page. Serially that is 256 round trips and
    the 6+ minute stall that made catalog releases wait on maintenance.
  * ``metadata.size`` is present on every listed object, so byte totals cost
    no extra requests.

Design rules
------------
1. **Partial is always labelled partial.** ``BlobInventory.complete`` is False
   whenever any shard failed, and ``require_complete()`` raises. The previous
   inventory helpers returned "whatever I got so far" on error, which is how a
   truncated listing can quietly become a deletion decision.
2. **Bounded parallelism, one client per thread.** Mirrors
   ``cleanup_old_versions.quarantine_orphan_blob_batch``: without a
   ``client_factory`` the walk stays serial, because a Supabase client's HTTP
   transport is not safe to share across threads.
3. **Resumable.** A checkpoint records only shards that fully succeeded, keyed
   by prefix + shard set so a stale checkpoint cannot be mistaken for this one.
4. **Reproducible.** Every collection that reaches a report is sorted; nothing
   ships out of set-iteration order.
"""

from __future__ import annotations

import json
import hashlib
import os
import re
import threading
import time
from concurrent.futures import ThreadPoolExecutor, as_completed
from dataclasses import dataclass, field
from pathlib import Path
from typing import Callable, Dict, Iterable, Optional, Sequence, Tuple

from .transient import is_transient_error, retry_transient

BLOB_STORAGE_PREFIX = "shared/details/sha256"
HEX_BLOB_SHARDS: Tuple[str, ...] = tuple(f"{i:02x}" for i in range(256))
DEFAULT_BUCKET = "pharmaguide"

_HASH_RE = re.compile(r"^[0-9a-f]{64}$")

#: Wall-clock bound for a single page request. Supabase-py's public ``list()``
#: exposes no per-call timeout; the bucket proxy's private request path does.
PAGE_TIMEOUT_SECONDS = int(os.environ.get("PG_STORAGE_LIST_PAGE_TIMEOUT_SECONDS", "45"))
PAGE_LIMIT = int(os.environ.get("PG_STORAGE_LIST_PAGE_LIMIT", "1000"))
MAX_ATTEMPTS = int(os.environ.get("PG_STORAGE_LIST_MAX_RETRIES", "5"))

#: Concurrency does NOT scale linearly here — past ~8 it goes backwards.
#: Measured 2026-08-26 against the live bucket, 32-shard slice, no checkpoint:
#:
#:     workers= 8   41.2s   16,351 objects   complete=True    0 retries
#:     workers=24   98.9s   15,808 objects   complete=False  29 retries
#:
#: Supabase serialises these listings server-side, so extra workers buy
#: contention and 544s rather than throughput — and a partial inventory, which
#: correctly refuses to be usable. Full 256-shard pass at 8 workers is ~5 min.
#: Raise this only with a fresh measurement showing it helps.
MAX_WORKERS = int(os.environ.get("PG_STORAGE_LIST_MAX_WORKERS", "8"))

CHECKPOINT_VERSION = 2


class IncompleteInventoryError(RuntimeError):
    """Raised when a caller requires a complete inventory and cannot have one."""


@dataclass(frozen=True)
class ShardFailure:
    shard: str
    error: str
    attempts: int

    def to_dict(self) -> dict:
        return {"shard": self.shard, "error": self.error, "attempts": self.attempts}


@dataclass
class BlobInventory:
    """The result of one inventory pass. Treat ``complete=False`` as unusable
    for any destructive decision."""

    prefix: str = BLOB_STORAGE_PREFIX
    sizes: Dict[str, int] = field(default_factory=dict)
    categories: Dict[str, int] = field(default_factory=dict)
    failures: Tuple[ShardFailure, ...] = ()
    shards_total: int = 0
    shards_completed: int = 0
    retries: int = 0
    elapsed_seconds: float = 0.0
    resumed_shards: int = 0

    @property
    def hashes(self) -> frozenset:
        return frozenset(self.sizes)

    @property
    def total_objects(self) -> int:
        return sum(self.categories.values())

    @property
    def total_bytes(self) -> int:
        return sum(self.sizes.values())

    @property
    def complete(self) -> bool:
        return not self.failures and self.shards_completed == self.shards_total

    def bytes_for(self, blob_hash: str) -> int:
        return self.sizes.get(blob_hash, 0)

    def require_complete(self) -> "BlobInventory":
        """Return self, or raise if any shard could not be read."""
        if self.complete:
            return self
        detail = ", ".join(f"{f.shard} ({f.error})" for f in self.failures[:5])
        more = "" if len(self.failures) <= 5 else f" (+{len(self.failures) - 5} more)"
        raise IncompleteInventoryError(
            f"Inventory covered {self.shards_completed}/{self.shards_total} "
            f"shard(s); {len(self.failures)} failed: {detail}{more}. "
            "Refusing to treat a partial inventory as authoritative."
        )

    def to_dict(self) -> dict:
        return {
            "prefix": self.prefix,
            "complete": self.complete,
            "shards_total": self.shards_total,
            "shards_completed": self.shards_completed,
            "resumed_shards": self.resumed_shards,
            "total_objects": self.total_objects,
            "unique_blobs": len(self.sizes),
            "total_bytes": self.total_bytes,
            "categories": dict(sorted(self.categories.items())),
            "retries": self.retries,
            "failures": [f.to_dict() for f in self.failures],
            "elapsed_seconds": round(self.elapsed_seconds, 3),
        }


# ---------------------------------------------------------------------------
# Page listing
# ---------------------------------------------------------------------------


def list_storage_page(bucket, prefix, offset, *, limit=None, timeout_seconds=None):
    """List one storage page with a bounded wall-clock timeout.

    Production clients go through the bucket proxy's private request path
    because the public ``list()`` exposes no per-call timeout. Test doubles
    that only implement ``list()`` take the public fallback.
    """
    limit = PAGE_LIMIT if limit is None else limit
    if timeout_seconds is None:
        timeout_seconds = PAGE_TIMEOUT_SECONDS

    if not hasattr(bucket, "_request") or not hasattr(bucket, "id"):
        return bucket.list(path=prefix, options={"limit": limit, "offset": offset})

    response = bucket._request(
        "POST",
        ["object", "list", bucket.id],
        json={
            "limit": limit,
            "offset": offset,
            "sortBy": {"column": "name", "order": "asc"},
            "prefix": prefix,
        },
        headers={"Content-Type": "application/json"},
        timeout=timeout_seconds,
    )
    return response.json()


def _classify(name: str) -> Tuple[str, Optional[str]]:
    """Return ``(category, blob_hash|None)`` for one listed leaf name."""
    if name.endswith(".json"):
        stem = name[:-5]
        if _HASH_RE.match(stem):
            return "detail_blob", stem
    return "unrecognized", None


# ---------------------------------------------------------------------------
# Checkpointing
# ---------------------------------------------------------------------------


def _checkpoint_key(prefix: str, shards: Sequence[str]) -> str:
    """Fingerprint the exact prefix and ordered shard set.

    The previous ``count + endpoints`` key collided for different middle
    shards. That let a resume silently reuse work from a different inventory.
    """
    payload = json.dumps(
        {"prefix": prefix, "shards": list(shards)},
        separators=(",", ":"),
        sort_keys=True,
    ).encode("utf-8")
    return hashlib.sha256(payload).hexdigest()


def _load_checkpoint(path: Optional[Path], prefix: str, shards: Sequence[str]) -> dict:
    if path is None or not Path(path).exists():
        return {}
    try:
        data = json.loads(Path(path).read_text())
    except (OSError, ValueError):
        return {}
    if not isinstance(data, dict):
        return {}
    if data.get("version") != CHECKPOINT_VERSION:
        return {}
    # Validate BOTH recorded identity fields. ``key`` embeds the prefix, but a
    # checkpoint is a plain JSON file an operator may copy or hand-edit; a
    # resume that silently trusts a checkpoint from a different prefix would
    # skip shards it never actually read.
    if data.get("prefix") != prefix:
        return {}
    if data.get("key") != _checkpoint_key(prefix, shards):
        return {}
    shard_map = data.get("shards")
    return shard_map if isinstance(shard_map, dict) else {}


def _save_checkpoint(path: Optional[Path], prefix: str, shards: Sequence[str],
                     shard_map: dict) -> None:
    if path is None:
        return
    payload = {
        "version": CHECKPOINT_VERSION,
        "prefix": prefix,
        "key": _checkpoint_key(prefix, shards),
        "shards": {k: shard_map[k] for k in sorted(shard_map)},
    }
    path = Path(path)
    path.parent.mkdir(parents=True, exist_ok=True)
    tmp = path.with_suffix(path.suffix + ".tmp")
    tmp.write_text(json.dumps(payload, sort_keys=True))
    tmp.replace(path)


# ---------------------------------------------------------------------------
# Inventory
# ---------------------------------------------------------------------------


def inventory_detail_blobs(
    client,
    *,
    bucket: str = DEFAULT_BUCKET,
    prefix: str = BLOB_STORAGE_PREFIX,
    shards: Iterable[str] = HEX_BLOB_SHARDS,
    max_workers: Optional[int] = None,
    max_attempts: Optional[int] = None,
    page_limit: Optional[int] = None,
    timeout_seconds: Optional[int] = None,
    client_factory: Optional[Callable[[], object]] = None,
    checkpoint_path: Optional[Path] = None,
    progress: Optional[Callable[[int, int, int], None]] = None,
) -> BlobInventory:
    """Walk every shard under ``prefix`` and return a labelled inventory.

    Never raises for storage failures — a failed shard is recorded in
    ``failures`` and the inventory reports ``complete=False``. Callers that
    will act destructively must call ``require_complete()``.
    """
    shards = tuple(shards)
    max_attempts = MAX_ATTEMPTS if max_attempts is None else max_attempts
    page_limit = PAGE_LIMIT if page_limit is None else page_limit
    workers = MAX_WORKERS if max_workers is None else int(max_workers)
    if client_factory is None:
        # No factory: stay serial. Sharing one client's HTTP transport across
        # threads is exactly the failure mode quarantine_orphan_blob_batch
        # already avoids.
        workers = 1
    workers = max(1, min(workers, len(shards) or 1))

    started = time.monotonic()
    checkpoint = _load_checkpoint(checkpoint_path, prefix, shards)

    thread_local = threading.local()
    lock = threading.Lock()
    retry_count = {"n": 0}

    def _worker_client():
        if client_factory is None:
            return client
        if not hasattr(thread_local, "client"):
            thread_local.client = client_factory()
        return thread_local.client

    def _count_retry(_attempt, _exc):
        with lock:
            retry_count["n"] += 1

    def _list_shard(shard: str):
        """Return ``(shard, names)``; raises on unrecoverable failure."""
        shard_prefix = f"{prefix}/{shard}"
        proxy = _worker_client().storage.from_(bucket)
        names = []
        offset = 0
        while True:
            items = retry_transient(
                lambda: list_storage_page(
                    proxy, shard_prefix, offset,
                    limit=page_limit, timeout_seconds=timeout_seconds,
                ),
                max_attempts=max_attempts,
                on_retry=_count_retry,
            )
            if not items:
                break
            for item in items:
                name = item.get("name") if isinstance(item, dict) else None
                if not name:
                    continue
                size = None
                metadata = item.get("metadata")
                if isinstance(metadata, dict) and isinstance(metadata.get("size"), int):
                    size = metadata["size"]
                elif isinstance(item.get("size"), int):
                    size = item["size"]
                names.append((name, size))
            if len(items) < page_limit:
                break
            offset += page_limit
        return shard, names

    results: Dict[str, list] = {}
    failures: list = []

    pending = [s for s in shards if s not in checkpoint]
    resumed = len(shards) - len(pending)
    for shard in shards:
        if shard in checkpoint:
            results[shard] = [tuple(entry) for entry in checkpoint[shard]]

    done_count = resumed

    def _record_progress():
        if progress is not None:
            objects = sum(len(v) for v in results.values())
            progress(done_count, len(shards), objects)

    if pending:
        if workers == 1:
            for shard in pending:
                try:
                    _, names = _list_shard(shard)
                    results[shard] = names
                except Exception as exc:  # noqa: BLE001 — recorded, not raised.
                    failures.append(ShardFailure(
                        shard=shard,
                        error=f"{type(exc).__name__}: {exc}",
                        attempts=1 if not is_transient_error(exc) else max_attempts,
                    ))
                done_count += 1
                _record_progress()
        else:
            with ThreadPoolExecutor(max_workers=workers) as pool:
                futures = {pool.submit(_list_shard, s): s for s in pending}
                for future in as_completed(futures):
                    shard = futures[future]
                    try:
                        _, names = future.result()
                        results[shard] = names
                    except Exception as exc:  # noqa: BLE001
                        failures.append(ShardFailure(
                            shard=shard,
                            error=f"{type(exc).__name__}: {exc}",
                            attempts=1 if not is_transient_error(exc) else max_attempts,
                        ))
                    done_count += 1
                    _record_progress()
    else:
        _record_progress()

    # Checkpoint only fully-successful shards.
    if checkpoint_path is not None:
        _save_checkpoint(
            checkpoint_path, prefix, shards,
            {s: [list(entry) for entry in names] for s, names in results.items()},
        )

    sizes: Dict[str, int] = {}
    categories: Dict[str, int] = {}
    for shard in sorted(results):
        for name, size in results[shard]:
            category, blob_hash = _classify(name)
            categories[category] = categories.get(category, 0) + 1
            if blob_hash is not None:
                sizes[blob_hash] = size if isinstance(size, int) else 0

    return BlobInventory(
        prefix=prefix,
        sizes=sizes,
        categories=categories,
        failures=tuple(sorted(failures, key=lambda f: f.shard)),
        shards_total=len(shards),
        shards_completed=len(results),
        retries=retry_count["n"],
        elapsed_seconds=time.monotonic() - started,
        resumed_shards=resumed,
    )
