"""Orphan reconciliation — build a reviewable report; propose, never act.

This module answers exactly one question: *which shared detail blobs are
provably unreferenced right now, and how big are they?* It never mutates
storage. Quarantining is a separate, explicitly-authorised step.

Fail-closed rule
----------------
"Provably" is load-bearing. An orphan is ``storage − protected``, so a gap on
either side is dangerous in a different way:

  * a gap in **protected** (an index we could not read) invents orphans that
    are actually live blobs — the 2026-05-12 incident;
  * a gap in **storage** (a shard we could not list) makes the report an
    undercount an operator might approve as if it were exact.

Either gap sets ``blocked_reason`` and forces ``proposed_quarantine`` to 0.
A partial answer is never presented as an exact one.
"""

from __future__ import annotations

import hashlib
import time
from dataclasses import dataclass, field
from pathlib import Path
from typing import Callable, Dict, Iterable, Optional, Sequence, Tuple

from .blob_inventory import (
    BLOB_STORAGE_PREFIX,
    DEFAULT_BUCKET,
    HEX_BLOB_SHARDS,
    BlobInventory,
    ObjectFingerprint,
    inventory_detail_blobs,
)


def hash_set_digest(hashes) -> str:
    """sha256 over newline-joined sorted hashes.

    Same construction as the quarantine checkpoint's candidate fingerprint in
    ``cleanup_old_versions.quarantine_orphan_blob_batch`` so the two artifacts
    can be cross-checked byte-for-byte.
    """
    return hashlib.sha256("\n".join(sorted(hashes)).encode("ascii")).hexdigest()
from .protected_blobs import compute_protected_blob_set


def _fmt_bytes(n: int) -> str:
    step = 1024.0
    value = float(n)
    for unit in ("B", "KiB", "MiB", "GiB", "TiB"):
        if abs(value) < step:
            return f"{value:,.1f} {unit}" if unit != "B" else f"{int(value):,} B"
        value /= step
    return f"{value:,.1f} PiB"


@dataclass
class OrphanReport:
    """Everything an operator needs to approve (or refuse) a quarantine."""

    inventory: BlobInventory
    protected_total: int = 0
    protected_by_version: Dict[str, int] = field(default_factory=dict)
    orphan_hashes: Tuple[str, ...] = ()
    orphan_bytes: int = 0
    blocked_reason: Optional[str] = None
    retained_versions: Tuple[str, ...] = ()
    elapsed_seconds: float = 0.0
    #: Frozen contract an operator approves against. All None/empty when the
    #: report is blocked — a blocked report pins nothing approvable.
    candidate_digest: Optional[str] = None
    protected_digest: Optional[str] = None
    candidate_fingerprints: Dict[str, ObjectFingerprint] = field(default_factory=dict)
    #: The quarantine date this approval is FOR. Execution uses this value, so
    #: a run resumed after midnight still lands under the same date directory.
    quarantine_run_date: Optional[str] = None

    @property
    def orphan_count(self) -> int:
        return len(self.orphan_hashes)

    @property
    def proposed_quarantine(self) -> int:
        """Zero whenever anything about the answer is unproven."""
        return 0 if self.blocked_reason else len(self.orphan_hashes)

    @property
    def total_objects_examined(self) -> int:
        return self.inventory.total_objects

    def to_dict(self) -> dict:
        return {
            "blocked_reason": self.blocked_reason,
            "candidate_digest": self.candidate_digest,
            "protected_digest": self.protected_digest,
            "quarantine_run_date": self.quarantine_run_date,
            "candidate_fingerprints": {
                h: {"size": fp.size, "etag": fp.etag}
                for h, fp in sorted(self.candidate_fingerprints.items())
            },
            "retained_versions": list(self.retained_versions),
            "protected_total": self.protected_total,
            "protected_by_version": dict(sorted(self.protected_by_version.items())),
            "orphan_count": self.orphan_count,
            "orphan_bytes": self.orphan_bytes,
            "proposed_quarantine": self.proposed_quarantine,
            "orphan_sample": list(self.orphan_hashes[:20]),
            "inventory": self.inventory.to_dict(),
            "elapsed_seconds": round(self.elapsed_seconds, 3),
        }

    def text_report(self) -> str:
        inv = self.inventory
        lines = [
            "=" * 68,
            "Orphan reconciliation — DRY RUN (no storage was modified)",
            "=" * 68,
            f"  Total objects examined:        {inv.total_objects:,}",
            f"  Unique detail blobs:           {len(inv.sizes):,}",
            f"  Storage bytes (all blobs):     {_fmt_bytes(inv.total_bytes)}",
            f"  Shards read:                   "
            f"{inv.shards_completed}/{inv.shards_total}"
            + (f" ({inv.resumed_shards} resumed from checkpoint)"
               if inv.resumed_shards else ""),
            "",
            "  Protected blobs by retained version:",
        ]
        if self.protected_by_version:
            for version, count in sorted(self.protected_by_version.items()):
                lines.append(f"    v{version:<24} {count:,}")
        else:
            lines.append("    (none resolved)")
        lines += [
            f"  Protected blobs (union):       {self.protected_total:,}",
            "",
            "  Object categories:",
        ]
        for category, count in sorted(inv.categories.items()):
            lines.append(f"    {category:<28} {count:,}")
        lines += [
            "",
            f"  Orphan blobs:                  {self.orphan_count:,}",
            f"  Estimated bytes reclaimable:   {_fmt_bytes(self.orphan_bytes)}",
            f"  Proposed quarantine:           {self.proposed_quarantine:,}",
            f"  Candidate digest:              {self.candidate_digest or '(none — blocked)'}",
            f"  Protected digest:              {self.protected_digest or '(none — blocked)'}",
            "",
            f"  Listing failures:              {len(inv.failures)}",
            f"  Retries:                       {inv.retries}",
            f"  Elapsed:                       {self.elapsed_seconds:.1f}s",
        ]
        if inv.failures:
            lines.append("")
            lines.append("  Failed shards:")
            for failure in inv.failures[:10]:
                lines.append(f"    {failure.shard}: {failure.error}")
            if len(inv.failures) > 10:
                lines.append(f"    ... and {len(inv.failures) - 10} more")
        if self.blocked_reason:
            lines += [
                "",
                "  *** BLOCKED — nothing may be quarantined from this run ***",
                f"  {self.blocked_reason}",
            ]
        elif self.orphan_hashes:
            lines += ["", "  Sample orphans (first 10):"]
            for blob_hash in self.orphan_hashes[:10]:
                lines.append(
                    f"    {BLOB_STORAGE_PREFIX}/{blob_hash[:2]}/{blob_hash}.json"
                )
        lines.append("=" * 68)
        return "\n".join(lines)


def build_orphan_report(
    client,
    *,
    flutter_repo_path,
    dist_dir,
    retained_versions: Sequence[str] = (),
    branch: str = "main",
    bucket: str = DEFAULT_BUCKET,
    shards: Iterable[str] = HEX_BLOB_SHARDS,
    max_workers: Optional[int] = None,
    max_attempts: Optional[int] = None,
    client_factory: Optional[Callable[[], object]] = None,
    checkpoint_path: Optional[Path] = None,
    progress: Optional[Callable[[int, int, int], None]] = None,
    run_date: Optional[str] = None,
) -> OrphanReport:
    """Inventory storage, compute the protected union, and diff them.

    Read-only. Returns a report whose ``proposed_quarantine`` is 0 unless both
    sides were fully proven.
    """
    started = time.monotonic()
    retained_versions = tuple(v for v in retained_versions if v)

    inventory = inventory_detail_blobs(
        client,
        bucket=bucket,
        shards=shards,
        max_workers=max_workers,
        max_attempts=max_attempts,
        client_factory=client_factory,
        checkpoint_path=checkpoint_path,
        progress=progress,
    )

    blocked: Optional[str] = None
    if not inventory.complete:
        blocked = (
            f"Storage inventory is incomplete: read "
            f"{inventory.shards_completed}/{inventory.shards_total} shard(s), "
            f"{len(inventory.failures)} failed. An undercounted storage side "
            "cannot produce an exact orphan count."
        )

    protected_total = 0
    protected_by_version: Dict[str, int] = {}
    orphan_hashes: Tuple[str, ...] = ()
    orphan_bytes = 0

    try:
        protected = compute_protected_blob_set(
            flutter_repo_path,
            dist_dir,
            branch=branch,
            supabase_client=client,
            registry_bucket=bucket,
            retained_versions=retained_versions,
        )
    except Exception as exc:  # noqa: BLE001 — reported, never raised.
        blocked = (
            f"Protected-set computation failed ({type(exc).__name__}: {exc}). "
            "Without a proven protected set every blob would look like an "
            "orphan, so nothing is proposed."
        )
    else:
        protected_total = len(protected.protected)
        protected_by_version = dict(protected.protected_by_version)
        if protected.degenerate:
            blocked = blocked or (
                "Protected set is degenerate: "
                f"{protected.degenerate_reason}. The bundled catalog is a "
                "required protection source for any destructive action."
            )
        if blocked is None:
            candidates = sorted(inventory.hashes - protected.protected)
            orphan_hashes = tuple(candidates)
            orphan_bytes = sum(inventory.bytes_for(h) for h in candidates)

    # An unproven fingerprint (no positive size or no eTag from the listing)
    # blocks HERE, at
    # report time — never later as an apparently actionable count that
    # execution then refuses.
    if blocked is None:
        unproven = [
            h for h in orphan_hashes
            if (
                (fp := inventory.fingerprint_for(h)) is None
                or fp.size <= 0
                or not fp.etag
            )
        ]
        if unproven:
            blocked = (
                f"{len(unproven)} candidate(s) lack a proven source "
                f"fingerprint (positive size and eTag required), e.g. "
                f"{unproven[0]}. Nothing may be proposed from an unproven "
                "identity."
            )
            orphan_hashes = ()
            orphan_bytes = 0

    candidate_digest = None
    protected_digest = None
    candidate_fingerprints: Dict[str, ObjectFingerprint] = {}
    if blocked is None:
        candidate_digest = hash_set_digest(orphan_hashes)
        protected_digest = hash_set_digest(protected.protected)
        candidate_fingerprints = {
            h: inventory.fingerprint_for(h) for h in orphan_hashes
        }

    return OrphanReport(
        inventory=inventory,
        protected_total=protected_total,
        protected_by_version=protected_by_version,
        orphan_hashes=orphan_hashes,
        orphan_bytes=orphan_bytes,
        blocked_reason=blocked,
        retained_versions=retained_versions,
        elapsed_seconds=time.monotonic() - started,
        candidate_digest=candidate_digest,
        protected_digest=protected_digest,
        candidate_fingerprints=candidate_fingerprints,
        quarantine_run_date=run_date if blocked is None else None,
    )
