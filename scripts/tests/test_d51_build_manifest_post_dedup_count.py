"""
Sprint D5.1 regression — build_final_db manifest must reflect POST-UPC-dedup
blob counts, not pre-dedup.

Bug surfaced during the D5.4 release-gate: the Supabase sync contract
check ``len(unique_blob_uploads) == manifest.detail_blob_unique_count``
failed because the manifest was emitting the pre-dedup unique-hash
count while the surviving detail_index (and disk blobs) reflected the
post-dedup set.

Concrete numbers from the D5.1 full-pipeline run:
  - Staged: 13,236 enriched products
  - After UPC dedup: 8,287 products (4,949 duplicates removed)
  - Pre-dedup ``unique_blob_hashes`` set size: 13,236
  - Actual disk blobs post-dedup: 8,287
  - Manifest MUST record the post-dedup count, not the pre-dedup count

Fix (build_final_db.py): recompute detail_blob_unique_count from
``detail_index.values()`` after dedup completes. This guarantees the
invariant that sync_to_supabase.py enforces:

    len(collect_unique_blob_uploads(build_dir, detail_index))
        == manifest["detail_blob_unique_count"]
"""

from __future__ import annotations

from pathlib import Path


def test_build_final_db_computes_unique_count_from_surviving_index() -> None:
    """The fix must recompute unique_count from detail_index (post-dedup),
    NOT from the pre-dedup unique_blob_hashes set."""
    source = Path("scripts/build_final_db.py").read_text()
    # Find the manifest_dict block
    start = source.find('"detail_blob_count": inserted')
    assert start > 0, "detail_blob_count manifest entry missing"
    block = source[start:start + 600]

    # The unique count must be derived from detail_index, not from the
    # pre-dedup set.
    assert "detail_index.values()" in block, (
        "D5.1 regression: detail_blob_unique_count must be computed from "
        "detail_index.values() so it reflects post-UPC-dedup state."
    )
    assert 'entry["blob_sha256"]' in block, (
        "D5.1 regression: unique-count derivation must key on "
        'entry["blob_sha256"] from the surviving detail_index.'
    )


def test_no_pre_dedup_unique_hashes_in_manifest() -> None:
    """Defensive: the old buggy line using ``len(unique_blob_hashes)``
    alone on the manifest assignment must not return."""
    source = Path("scripts/build_final_db.py").read_text()
    start = source.find('"detail_blob_count": inserted')
    block = source[start:start + 600]
    # The literal 'len(unique_blob_hashes)' should NOT appear as a value
    # on the detail_blob_unique_count line — it may still appear elsewhere
    # for staging-time logging, but the manifest must use the post-dedup
    # derivation.
    offending = '"detail_blob_unique_count": len(unique_blob_hashes)'
    assert offending not in block, (
        f"D5.1 regression: {offending!r} reintroduces the pre-dedup bug."
    )
