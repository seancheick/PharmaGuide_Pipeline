# Scoring and probiotic follow-up audit — 2026-09-15

Baseline: `515ef8c5` on main. Scope: Claude's strain expansion, prebiotic
unification, rubric-proxy removal, verification tiers, clinical dose references,
and their cleaner → enricher → scorer → catalog boundaries. This is a code and
source audit, not a new clinical approval or a catalog release.

## Confirmed defects corrected

| Boundary | Defect | Correction |
|---|---|---|
| Prebiotic enrichment and scoring | First prebiotic's name could receive another row's larger dose. Notes mentioning inulin could lend rice-flour mass; a mixed blend could lend its total to an individual substrate. | Both callers use `prebiotic_catalog.prebiotic_summary`: name and amount travel together; notes are not identity; mixed containers cannot supply a child's dose. Mass parsing uses the existing unit owner and rejects non-finite/negative values. |
| Cleaner and strain identity | Substring fallback could rename Lp-1150 to Lp-115 or extend/truncate NCIMB codes. | Cleaner lookup and downstream identity checks share the same exact registry key. All 578 current normalized names/aliases were checked: zero cross-identity collisions. |
| Probiotic formulation | Uppercase species typography could count as a strain designation; a caller-supplied ID could validate a different printed code; species-general entries could earn exact-code credit. | Identity resolution checks the label against the existing registry. Species-level research remains available but is not rewarded as disclosure of an exact strain code. |
| Trust modules and public verification pillar | Label GMP masked stronger facility evidence; omega's nested provenance was ignored; adding a label certification could lower an existing manufacturing tier. | Stronger recorded evidence wins. Public assembly recognizes existing archetype metadata without a second certification policy. |
| Verification and catalog copy | A label QR/COA mention could earn independently-verified product credit and become “Heavy metal tested.” | Only registry-backed product certification reaches that tier. COA/lookup mentions remain limited claims. Exported badges read the final pillar; GMP claims are not displayed as facility audits. |
| Dose references | Betaine HCl and acetylated/dipeptide glutamine could inherit another chemical preparation's clinical reference through their IQM parent; a glucosamine-HCl alias resolved to the sulfate anchor. | The shared RDA calculator receives the already-resolved form and abstains for incompatible bindings, including HCl/NAG against the [glucosamine sulfate reference](https://pubmed.ncbi.nlm.nih.gov/30566740/). Existing ingredient/form identities remain intact. |
| Citation audits | Loose normalization erased decimals/signs; a full-text fallback could read the wrong article or its references; the identity verifier could report failures but exit successfully. | Shared source-text checks preserve numerical operators, bind PMC front-matter PMID, include actual article tables but exclude the bibliography, and fail with a nonzero exit. |
| Calibration harness | Two equally empty/invalid snapshots could appear unchanged. Dirty code could be described only by its base commit. | Require real finite public scores and all six bounded pillars; preserve frozen IDs/input hashes; record dirty state, tracked-diff hash and canonical config provenance. |

No reference doses, ingredient identities, approval records or sign-off flags
were changed. Production config is versioned `1.5.2-evidence-boundary-fixes` and
its fingerprint is pinned in the existing ledger. No second scorer, registry,
approval path, or app schema was introduced.

## Evidence and limits

- Final frozen-code backstop: `scripts/test.sh fast` — **15,216 passed,
  66 skipped, zero failures** (373.83 seconds). Final focused audit regressions:
  95 passed. Earlier red runs are not counted as successful verification; they
  reproduced and then closed the numeric/table-boundary and form-scope defects.
- Live anchor audit: 30 reference entries, 51 PubMed records, 71 source quotes;
  10 quotes required full text. Zero failures with the stricter verifier.
- Live strain-identity audit: 75 PubMed records, 158 checks; 54 used full text.
  Zero failures with the stricter verifier.
- These verify the cited text and identities, **not** universal clinical
  effectiveness, lowest effective dose, or a clinician's credentials.
- Both frozen calibration packets scored successfully: 111 + 79 products.
  Their existing enriched inputs were not regenerated; this is not evidence
  that a partially completed earlier pipeline run has become fresh.
- Read-only verification replay held stored module inputs constant and called
  the actual baseline/candidate assembler across all 15,109 scored records
  found in the local scored batches. 619 pillars changed: 439 increases and
  180 decreases (range −5 to +2 verification points). Changes were
  claim→manufacturing (439), product→claim (122), product→manufacturing (58).
  This is a bounded comparison, not a full-score catalog delta. Old module
  inputs cannot measure the new GMP collector ordering; integration tests do.
- Full corpus regeneration, catalog release gates, and phone verification are
  deliberately left for the owner's next run. No operational batch, release,
  database deployment, or phone installation was started in this audit.

Reproduce the read-only verification replay:

```bash
source scripts/python_env.sh
"$PG_PYTHON" scripts/audits/scoring_boundary_audit_2026_09_15/replay.py \
  --baseline 515ef8c5 --out /tmp/pharmaguide-verification-replay.json
```

## Probiotic registry: what is actually present

Current data has **131 identities**, not the older 105. There are 125 contexts:
123 carry the existing `clinician_approved` status (113 scoring-eligible) and
2 are held as `adjudication_required`. Forty strain sign-off flags are true;
91 are false. Those are separate concepts and were not conflated or changed.

The 123 approval records attribute the research approval to the engineering
owner. The legacy status/policy names do **not** prove clinician sign-off. A
later countersignature would be a new, explicit review—not merely changing
the reviewer string. No consumer claim of clinician approval should be inferred
from those historical enum names.

## Calibration direction

Keep the proxy-removal work: gummy format alone, organic/Non-GMO marketing,
marine sustainability, and an arbitrary EPA:DHA ratio should not manufacture
clinical-quality points or duplicate an existing dose/sugar consequence.
The removed astaxanthin/CoQ10 display caps should stay removed. A high score is
allowed when the actual applicable pillars justify it; do not tune thresholds
to make a chosen number of market products reach 98–100.

The next rubric work is **purpose-fit probiotic calibration**, not bulk approval:

1. Compare a fully disclosed, well-supported single strain against fully
   disclosed combinations. The current exact-identity component still awards
   3 points for one identity and 8 for five; the CFU-size ladder also remains.
   These are known policy choices, not proof that more strains/CFU are better.
2. Keep label disclosure, condition-specific evidence, dose applicability and
   verification distinct. Species-only labels cannot be resolved into invented
   strains. A blend's total CFU cannot become every strain's CFU, and AFU is
   not automatically CFU. Null studies remain evidence, not positive benefit.
3. Freeze intended single/multi/low-disclosure contrasts before inspecting
   movements; use the existing config, scorer and packets. No new scoring brain.
4. Recheck generic clinical anchors by preparation, population and outcome.
   A studied dose is not an official RDA or a universal efficacy threshold.
   The restored [NMN 250 mg trial](https://pubmed.ncbi.nlm.nih.gov/38789831/)
   had a null primary endpoint and secondary signals. Preserve the correct
   dose and its uncertainty; do not raise it to 300 mg just because another
   trial used that amount. PQQ remains 20 mg under the current reviewed policy.
5. The prebiotic 3 g complement threshold is still a shared *rubric* threshold,
   not a clinical-equivalence claim across all 14 registered substrates. Any
   substrate-specific change needs its own evidence and the same matcher.

The broader reviewer roadmap is **not all implemented** by Claude's first
passes or by this audit. Single/focused/broad formula fairness, indication-aware
omega dosing, prenatal form appropriateness, ingredient-specific fiber dosing,
and a scored-versus-review-coverage explanation still require separate bounded
work in the existing modules. Preserve current safety gates while doing it;
removing an excess-dose penalty before its replacement exists is not cleanup.
The numeric 20/20/20/15/15/10 public contract is unchanged. Do not introduce a
parallel “v5” scorer or new field vocabulary just to reflect reviewer examples.

If the objective is **one final calibration release**, complete those agreed
rubric changes and benchmark them before paying for another full regeneration.
The commands below are also appropriate for inspecting the corrected current
model, but that rebuild alone would not finish the larger calibration plan.

## Next operational run

Start from **Clean**, not just Enrich: this audit changed the cleaner's strain
matching. Do not reuse the earlier mixed/partially interrupted outputs.

The separately stored Product Submissions source must also have current
cleaned/enriched/scored outputs: the batch runner's automatic auxiliary refresh
is reference-data-driven and may reuse earlier cleaning. Refresh it first
through the same runner, then run the brands (no submission-specific scorer):

```bash
source scripts/python_env.sh
"$PG_PYTHON" scripts/run_pipeline.py \
  --raw-dir "$REPO_ROOT/manual_labels/product_submissions" \
  --output-prefix scripts/products/output_Product_Submissions \
  --stages clean,enrich,score --strict-release-gates &&
PYTHON="$PG_PYTHON" bash batch_run_all_datasets.sh \
  --stages clean,enrich,score --skip-release
```

`--skip-release` still builds the local dashboard/catalog snapshot; it does not
publish the release. Run from the repository root. If either command fails,
resolve the reported gate rather than bypassing it or releasing partial output.

After regeneration, compare category/product deltas and check unresolved strain
coverage on the fresh artifacts, then run `scripts/test.sh release` before the
existing release train. The earlier stale-corpus coverage numbers are not a
forecast of how many products will improve.
