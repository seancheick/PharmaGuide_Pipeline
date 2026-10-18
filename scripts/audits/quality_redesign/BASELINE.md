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

## Full-artifact baseline — October 18, 2026 (architecture audit F.3, wave 1.5)

`snapshot --full --blob` keeps, per product, a sha256 of the whole cleaned, enriched and scored record and of
the detail blob (clock stamps removed through `replay.VOLATILE_FIELDS`), stores the records under
`<out>.records/<id>.json.gz`, and `compare` names the changed record and its first differing JSON path.
Score-only snapshots and their compare output are unchanged. Blob path: the same `build_scored_artifact` +
`build_detail_blob` calls as `scripts/reports/canary_rebuild.py::rebuild_one`; on frozen Hum labels 241665 and
276704 the harness blob hash equals `record_hash(rebuild_one(label), 'blob')`.

### Inputs

(The September receipts above under `/tmp/pg_quality` are historical; `/tmp` is wiped on reboot. Everything below lives under `~/pg_quality`.)

- Raw root: `~/Downloads/PharmaGuide_Datasets/staging/brands` (the batch runner's `DATASET_ROOT`): 37 brand
  directories, 15,414 raw DSLD labels, unique ids. The 38th stage manifest of a corpus run is
  `Product_Submissions`, whose inputs are submission JSONs keyed by submission id (`PG_SUB_*`), not DSLD labels;
  `freeze-raw` cannot freeze them and they are not in this baseline.
- Frozen root `/Users/seancheick/pg_quality/full_artifact_baseline_20261018/frozen_raw` (176 MB); manifest
  `/Users/seancheick/pg_quality/full_artifact_baseline_20261018/manifest.json`, sha256
  `fd4f3ca7d4b5963d578230cc13e8c75753c7993b9b33bf0315c625480174b02b`; ids list `ids.json` beside it.

### Volatile fields (the whole list; the harness's `VOLATILE_FIELDS` carries a reason per path)

Found, not assumed: DSLD 19067 (Nature Made) run twice more than a second apart through clean → enrich →
scored artifact → detail blob and every JSON path of all four records diffed; then the 22 frozen Hum labels run
twice through the harness and every stored record diffed with the stamps still in (`probe_hum/`). The only clock
stamps are `cleaned.metadata.lastCleaned`, `enriched.enriched_date`, `enriched.enrichment_metadata.generated_at`,
`enriched.match_ledger.generated_at` and `scored.scoring_metadata.scored_date`; the detail blob carries none.
`run_id` (named in AUDIT.md F.3) is stamped by the enricher's batch driver `process_all()` and never appears in a
per-product record. No path was added to make a comparison pass.

### Historical finding: one enriched field was ordered by the process hash seed (fixed by PR #156)

`scripts/enrich_supplements_v3.py:5574` writes `"scorable_ingredient_names_normalized": list(scorable_names_normalized)`,
a set rendered as a list. Two harness runs of the 22 Hum labels differ on that path for 16 of 22 products
(`probe_hum/run1_vs_run2.json`); with `PYTHONHASHSEED=0` both runs are byte-identical
(`probe_hum/seeded3.jsonl` and `seeded4.jsonl`, sha256 `c08936b3fe1d839ded148960d373d77a03d54603a982876b778a10621f7616c3`,
compare: 0 changed). Scores, the scored artifact and the detail blob do not move; nothing outside tests reads the
field (`rg scorable_ingredient_names_normalized scripts/ "/Users/seancheick/PharmaGuide ai/lib"`). So that the
harness compares code and inputs rather than seeds, the `--full` worker runs with `PYTHONHASHSEED=0`
(`replay.FULL_WORKER_ENV`, recorded in the receipt); the field itself stays in the hash. Sorting that list is a
Clean/Enrich behavioral change for its own fix task (see the memory gotcha on set iteration).

### Baseline run

- Production source: `5fb2be1ca` (main). The snapshot's `repository.head` is `5fb2be1ca` and `source_sha256`
  covers every production module, scoring config and data file at that commit (tests and `scripts/audits/` are
  outside the fingerprint, so the harness edit does not appear in it). Harness used: `replay.py` sha256
  `2d2a0612387d6c4bab2fc1c8e611e84742a30795d478eba0858ca8927db1ab71` (`full.harness_sha256` in the receipt), commit ce5694b88.
  The review fixes that followed change only the compare side (receipt guard on `volatile_fields` / `worker_env`;
  leaves compared by canonical JSON so `-0.0` vs `0.0` is reported like the hash sees it; `compare --all-paths`), never
  capture: `compare` of this baseline against itself under the PR head harness reports 15,414 products, 0 changed
  (`self_compare_guard_check.json`, rerun after each compare-side change).
- Command (from the worktree, `PG_PYTHON` = pinned 3.13.3):
  `replay.py snapshot --checkout <worktree at 5fb2be1ca> --products-root .../frozen_raw --manifest .../manifest.json --out .../baseline_5fb2be1ca.jsonl --workers 4 --full --blob`
- Output: `/Users/seancheick/pg_quality/full_artifact_baseline_20261018/baseline_5fb2be1ca.jsonl`
  (+ `.meta.json`, `.records/`, `.log`). 15,414/15,414 products, exit 0, `source_unchanged` true, 4 workers, about 32 minutes wall (03:04 to 03:36 local, 2026-10-18). Status: 15,109 scored, 236 not_scored, 69 suppressed_safety; routes: generic 10,674, multi_or_prenatal 2,071, sports 922, omega 714, probiotic 539, fiber_digestive 348, b_complex 146 (the September score-only section replayed stored enrichment of 38 manifests, so its counts are not comparable). Every product carries all four hashes; no two products share one. Snapshot sha256 `96d7ec7ac3762b7586965d6339b4a7f3f245e457cecaa34034065cd626e7c704` (355 MB); receipt sha256 `29263ce852f5f8f9d68de1ae353353bbc80573892bdbb5513a707954aab55438`; records 15,414 files, 1.1 GB.
- Not done: a second full run of all 15,414 labels. Determinism of the capture rests on the 22-label Hum
  receipt above (byte-identical twice under the pinned seed) and on the earlier 15,421-product score-only
  repeat recorded in the September section.

### Using it

```
replay.py snapshot --checkout <candidate worktree> --products-root .../frozen_raw --manifest .../manifest.json \
    --out .../candidate_<sha>.jsonl --workers 4 --full --blob
replay.py compare --baseline .../baseline_5fb2be1ca.jsonl --candidate .../candidate_<sha>.jsonl --out .../delta.json
```

`compare` writes one entry per product whose row differs, each with `changed` (cleaned / enriched / scored /
blob) and `first_difference` per changed record, and prints a one-line summary to stderr. `--all-paths` adds every
differing path of each changed record (`differences`) and, to the summary, the number of products carrying each
path with list indices generalized to `[*]`: the "only this path differs" receipt of a PR comes from that summary.
Every listed difference is justified in the PR that produced it; none is removed by widening `VOLATILE_FIELDS`.

### Unpinned recapture — October 18 follow-up

PR #156 sorted `scorable_ingredient_names_normalized` at its production owner and is integrated through PR #163. The current harness no longer overrides `PYTHONHASHSEED`. It records an explicitly inherited setting in `full.worker_env`; `{}` means the variable was unset and Python selected its normal randomized process seed. It does not claim to know Python's internal seed.

`compare` requires compatible recorded environments on the two captures, independently of the caller's current environment. Historical seed-0 captures still compare to each other. Pinned and unpinned captures deliberately do not compare directly; retain the historical receipts without editing/restamping them. Volatile-field declarations and all existing input/hash/count checks remain enforced.

For the authorized new baseline, explicitly unset any shell pin:

```bash
env -u PYTHONHASHSEED "$PG_PYTHON" scripts/audits/quality_redesign/replay.py snapshot \
  --checkout /Users/seancheick/Downloads/dsld_clean \
  --products-root <fresh-frozen-raw-root> --manifest <fresh-input-manifest> \
  --out <durable-baseline.jsonl> --workers 4 --full --blob
```

Validate independent unpinned repetitions and explicit cross-seed probes using whole-record hashes; do not expand the volatile-field list to hide ordering differences. The old baseline above excludes Product_Submissions by format; validate that source separately through its manifest-owned stages and a stored-enrichment snapshot. New capture and validation receipts will be recorded here after the pipeline completes. No release is implied.
