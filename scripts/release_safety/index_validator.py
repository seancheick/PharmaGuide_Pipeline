"""detail_index.json validator — gating precondition for orphan-cleanup.

Implements ADR-0001 HR-11: cleanup may only execute against a validated
detail_index.json. Orphan computation against a corrupted or partial
index silently deletes blobs that are still referenced.

What this validator checks
==========================
1. The file exists and parses as JSON.
2. The top-level is a JSON object (dict) — `{dsld_id: entry, ...}`,
   optionally with a reserved `_meta` key carrying release metadata.
3. Each non-meta entry is a dict that yields a usable blob hash from
   either ``blob_sha256`` directly or by parsing ``storage_path``.
4. Each blob hash is well-formed: lowercase hex, length 64.
5. (Optional) If the caller provides ``expected_db_checksum`` and/or
   ``expected_db_version``, the index's ``_meta`` block must match.

What this validator does NOT do
================================
- It does NOT reject duplicate blob hashes. Detail blobs are content-
  addressed; two products with identical rendered JSON legitimately
  share a hash. Duplicates are surfaced via ``duplicate_hash_groups``
  for audit/logging but are not a validation failure.
- It does NOT verify that each blob actually exists in Supabase storage —
  that is P4's job (verify-bundle), running in the consumer.
- It does NOT compute the DB checksum itself — the caller passes the
  expected checksum (typically extracted from ``export_manifest.json``).

Detail-index file shapes accepted
==================================
Either of these is valid (the validator handles both):

    Shape A — flat (current pipeline output):
        {
          "1001": {"blob_sha256": "...", "storage_path": "...", "blob_version": 1},
          "1002": {...},
          ...
        }

    Shape B — flat with optional metadata block:
        {
          "_meta": {"db_version": "2026.05.12.203133", "db_checksum_sha256": "..."},
          "1001": {...},
          ...
        }

The ``_meta`` key (if present) is consumed by the validator and reported
in the result. All other top-level keys are treated as ``dsld_id`` entries.
"""

from __future__ import annotations

import json
import re
from dataclasses import dataclass, field
from pathlib import Path
from typing import Optional, Union

# A valid blob hash is exactly 64 lowercase hex characters.
_VALID_BLOB_HASH_RE = re.compile(r"^[0-9a-f]{64}$")

# Reserved top-level key for release metadata (Shape B).
_META_KEY = "_meta"

# Storage-path format used by the pipeline:
#   shared/details/sha256/{2-char-shard}/{64-hex-hash}.json
_STORAGE_PATH_HASH_RE = re.compile(
    r"shared/details/sha256/[0-9a-f]{2}/([0-9a-f]{64})\.json$"
)


# ---------------------------------------------------------------------------
# Exception hierarchy
# ---------------------------------------------------------------------------


class IndexValidationError(Exception):
    """Base for all detail_index.json validation failures.

    Catch this for a generic "cleanup precondition failed" handler;
    catch a specific subclass when behavior should differ by reason.
    """


class MalformedJSONError(IndexValidationError):
    """The file does not exist, is unreadable, or does not parse as JSON."""


class MalformedStructureError(IndexValidationError):
    """The JSON parses but the structure is not a valid index shape.

    Examples: top-level is not a dict; an entry is not a dict; the
    optional ``_meta`` block is not a dict.
    """


class MissingFieldError(IndexValidationError):
    """An entry has no usable blob hash (neither blob_sha256 nor
    a parseable storage_path)."""


class MalformedHashError(IndexValidationError):
    """A blob hash is not in canonical form: lowercase hex, length 64."""


class ChecksumMismatchError(IndexValidationError):
    """The caller provided an expected DB checksum (or version) that does
    not match the index's ``_meta`` block — or the index has no ``_meta``
    block to compare against."""


# ---------------------------------------------------------------------------
# Result dataclass
# ---------------------------------------------------------------------------


@dataclass(frozen=True)
class ValidatedIndex:
    """Result of a successful validation.

    Attributes:
        index_path: path the validator was given (after normalization).
        count: total number of dsld_id entries (excluding ``_meta``).
        blob_hashes: frozenset of all unique blob hashes referenced.
            ``len(blob_hashes) <= count`` — equality means no dedup.
        unique_hash_count: ``len(blob_hashes)``, exposed for convenience.
        duplicate_hash_groups: mapping from hash -> list of dsld_ids that
            share it. Only includes hashes appearing in 2+ entries.
            Empty dict when every entry has a unique hash.
        db_version: from index's ``_meta.db_version`` if present, else None.
        db_checksum: from index's ``_meta.db_checksum_sha256`` if present,
            else None.
    """

    index_path: Path
    count: int
    blob_hashes: frozenset
    unique_hash_count: int
    duplicate_hash_groups: dict = field(default_factory=dict)
    db_version: Optional[str] = None
    db_checksum: Optional[str] = None


# ---------------------------------------------------------------------------
# Public API
# ---------------------------------------------------------------------------


def validate_detail_index(
    index_path: Union[Path, str],
    *,
    expected_db_checksum: Optional[str] = None,
    expected_db_version: Optional[str] = None,
) -> ValidatedIndex:
    """Validate a ``detail_index.json`` file end-to-end and return its
    structured contents.

    Args:
        index_path: filesystem path to ``detail_index.json``.
        expected_db_checksum: if provided, the index's
            ``_meta.db_checksum_sha256`` must equal this value (raises
            ``ChecksumMismatchError`` on mismatch or missing metadata).
        expected_db_version: if provided, the index's ``_meta.db_version``
            must equal this value (same error semantics).

    Returns:
        ``ValidatedIndex`` with the index's contents and audit metadata
        (including ``duplicate_hash_groups`` for any shared hashes).

    Raises:
        MalformedJSONError: file missing/unreadable/invalid JSON.
        MalformedStructureError: top-level or entry is not the expected shape.
        MissingFieldError: an entry yields no usable blob hash.
        MalformedHashError: a blob hash is not lowercase hex length 64.
        ChecksumMismatchError: optional checksum/version check failed.
    """
    path = Path(index_path)

    # --- Step 1: load and parse JSON ---------------------------------------
    try:
        with open(path) as f:
            data = json.load(f)
    except FileNotFoundError as e:
        raise MalformedJSONError(
            f"detail_index file not found: {path}"
        ) from e
    except OSError as e:
        raise MalformedJSONError(
            f"detail_index file unreadable: {path}: {e}"
        ) from e
    except (json.JSONDecodeError, ValueError) as e:
        raise MalformedJSONError(
            f"detail_index is not valid JSON: {path}: {e}"
        ) from e

    if not isinstance(data, dict):
        raise MalformedStructureError(
            f"detail_index top-level must be a JSON object, got "
            f"{type(data).__name__}: {path}"
        )

    # --- Step 2: extract optional _meta block ------------------------------
    meta = data.pop(_META_KEY, None)
    db_version: Optional[str] = None
    db_checksum: Optional[str] = None
    if meta is not None:
        if not isinstance(meta, dict):
            raise MalformedStructureError(
                f"detail_index '{_META_KEY}' must be a JSON object, got "
                f"{type(meta).__name__}: {path}"
            )
        db_version = meta.get("db_version")
        db_checksum = meta.get("db_checksum_sha256")

    # --- Step 3: walk entries, collect hashes ------------------------------
    # hash_to_dsld_ids is built in input order so duplicate_hash_groups is
    # deterministic across runs (helps idempotency tests in P1.5).
    hash_to_dsld_ids: dict = {}
    for dsld_id, entry in data.items():
        if not isinstance(entry, dict):
            raise MalformedStructureError(
                f"detail_index entry for dsld_id={dsld_id!r} must be a JSON "
                f"object, got {type(entry).__name__}: {path}"
            )

        blob_hash = _extract_blob_hash(entry)
        if blob_hash is None:
            raise MissingFieldError(
                f"detail_index entry for dsld_id={dsld_id!r} has no usable "
                f"blob hash (neither 'blob_sha256' nor parseable "
                f"'storage_path'): {path}"
            )

        if not _VALID_BLOB_HASH_RE.match(blob_hash):
            raise MalformedHashError(
                f"detail_index entry for dsld_id={dsld_id!r} has malformed "
                f"blob hash {blob_hash!r}: must be lowercase hex, length 64. "
                f"({path})"
            )

        hash_to_dsld_ids.setdefault(blob_hash, []).append(str(dsld_id))

    # --- Step 4: build result ---------------------------------------------
    blob_hashes = frozenset(hash_to_dsld_ids.keys())
    duplicate_hash_groups = {
        h: ids for h, ids in hash_to_dsld_ids.items() if len(ids) > 1
    }
    count = sum(len(ids) for ids in hash_to_dsld_ids.values())

    # --- Step 5: optional checksum / version cross-check -------------------
    if expected_db_checksum is not None and expected_db_checksum != db_checksum:
        raise ChecksumMismatchError(
            f"detail_index db_checksum_sha256 mismatch: "
            f"expected {expected_db_checksum!r}, "
            f"index has {db_checksum!r}: {path}"
        )

    if expected_db_version is not None and expected_db_version != db_version:
        raise ChecksumMismatchError(
            f"detail_index db_version mismatch: "
            f"expected {expected_db_version!r}, "
            f"index has {db_version!r}: {path}"
        )

    return ValidatedIndex(
        index_path=path,
        count=count,
        blob_hashes=blob_hashes,
        unique_hash_count=len(blob_hashes),
        duplicate_hash_groups=duplicate_hash_groups,
        db_version=db_version,
        db_checksum=db_checksum,
    )


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _extract_blob_hash(entry: dict) -> Optional[str]:
    """Pull a blob hash from an entry, preferring ``blob_sha256`` and
    falling back to parsing it out of ``storage_path``.

    Returns the raw hash string (un-validated) or None if neither source
    yields anything. Format validation is the caller's job.
    """
    raw = entry.get("blob_sha256")
    if isinstance(raw, str) and raw:
        return raw

    storage_path = entry.get("storage_path")
    if isinstance(storage_path, str):
        match = _STORAGE_PATH_HASH_RE.search(storage_path)
        if match:
            return match.group(1)

    return None
