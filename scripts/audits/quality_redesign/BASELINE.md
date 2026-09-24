# Quality redesign baseline

This audit replays the real `score_product_v4` on frozen, manifest-owned stored enrichment. It does not regenerate enrichment, approve clinical comparisons, or release a catalog.

## Inventory and source relationship

- 15,421 unique products in 58 enriched payload files owned by 38 successful enrichment stage manifests.
- Frozen root: `/tmp/pg_quality/frozen-products`; input receipt: `/tmp/pg_quality/frozen-inputs.json`.
- Every payload hash matches the original `scoring_diagnosis_20260922/inputs.json`: no added, removed, or changed inputs.
- Every scorer/config file fingerprint in the original diagnosis provenance matches the baseline checkout. Repository HEAD differs because plan/research work was committed; the exact relationship is recorded in `baseline_provenance.json`.
- The freeze operation uses `stage_manifest.select_stage_input_files(..., require_manifest=True)` as the ownership authority. It rejects duplicate product IDs and verifies copied bytes.

## Reproduction

Use the pinned Python 3.13.3 interpreter. `replay.py` exposes:

- `freeze --products-root SOURCE --frozen-root NEW_DESTINATION --manifest RECEIPT`
- `snapshot --checkout CHECKOUT --products-root FROZEN_ROOT --manifest RECEIPT --out SNAPSHOT --workers 4`
- `compare --baseline BASELINE --candidate CANDIDATE --out DIFF`
- `check --candidate CANDIDATE --reference-cases scripts/audits/quality_redesign/reference_cases.json`

Worker count is bounded to 1–4. Each worker imports the selected checkout's real scorer. The harness preserves failed product records and fails the run; it never drops failures or treats empty output as success. Snapshot receipts require a successful run, source stability, output hash, expected product count, and unique IDs. Compare additionally requires matching frozen-input receipts and per-product input hashes.

Snapshot metadata fingerprints production Python packages recursively plus scoring configuration and reference JSON data. No scoring formula is copied into this harness. Diagnostic subtype/profile fields are projections of the captured scorer breakdown.

## Reference queue and acceptance

The reference queue contains 30 actual products, expanded beyond the initial 10–20 to cover all observed sports subtypes, generic profiles, prenatal, digestive enzymes, single/multiple probiotic strains, and incomplete review. Every case records its frozen source/label path. The six original diagnosis cases are included.

Clinical comparisons remain explicitly pending. `check` must therefore return nonzero: neither an empty reference set nor unresolved required comparisons can approve a candidate. The Ipriflavone label receipt establishes label identity, the `<1 g` fiber comparator, and directions only; it does not establish effectiveness or quality ordering. Proposed synthetic invariants are listed separately and remain assigned to later scoring tasks.

## Verification receipt

- Harness regression tests: 23 passed using `scripts/test.sh fast scripts/tests/test_quality_redesign_replay.py`.
- Spec review and independent quality review approved the revised harness.
- Two successful full replays: 15,421 products each, zero scorer failures; 15,244 scored, 107 not scored, and 70 safety-suppressed.
- Complete per-product records are identical across the independent runs: zero differences. Both projected JSONL files have SHA-256 `047478177666a3992e72ec3f2230487e7396ff1dab22b2c0a039d37e3e2dcf2a`.
- All 30 queue products and coverage observations matched the fresh baseline. The reference check correctly exits 1 for six unresolved required comparisons.
- Final replay results, raw-capture preservation, and hashes: see `baseline_provenance.json`.

The first replay began before expanded receipt/profile projection safeguards were added. Its original capture is retained, and any post-run receipt/projection is explicitly labeled as such. Newly covered dependency hashes are compared with the initial committed baseline; they are not presented as observed pre-run hashes. The independent repeated replay uses the complete revised provenance boundary. An interrupted earlier repeat attempt is retained only as failed-run metadata and is not counted as a successful replay.
