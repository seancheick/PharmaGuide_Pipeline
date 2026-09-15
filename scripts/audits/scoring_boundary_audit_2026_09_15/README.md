# Scoring and probiotic follow-up audit — 2026-09-15

Baseline: `515ef8c5` on main. Scope: Claude's strain expansion, prebiotic
unification, rubric-proxy removal, verification tiers, clinical dose references,
and their cleaner → enricher → scorer → catalog boundaries. This is a code and
source audit, not a new clinical approval or a catalog release.

The later completed probiotic calibration batch uses baseline `b2ff64d2`;
its separate results appear below. Do not combine the two replay denominators.

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
were changed in that audit. Its production config was `1.5.2-evidence-boundary-fixes` and
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

Subsequent owner confirmation: Dr. Pham read and approved the review. This is
not a request for another signature. Preserve the existing historical records;
do not invent a countersignature date or rewrite their attribution. Remaining
work is source accuracy, rubric verification and release validation.

## Calibration direction

Keep the proxy-removal work: gummy format alone, organic/Non-GMO marketing,
marine sustainability, and an arbitrary EPA:DHA ratio should not manufacture
clinical-quality points or duplicate an existing dose/sugar consequence.
The removed astaxanthin/CoQ10 display caps should stay removed. A high score is
allowed when the actual applicable pillars justify it; do not tune thresholds
to make a chosen number of market products reach 98–100.

The follow-up is **purpose-fit calibration**, not bulk approval. The active
implementation and remaining work are tracked in the existing
[calibration plan](../../../docs/superpowers/plans/2026-09-15-probiotic-completeness.md).
Its design was presented before implementation:

1. Exact identity quality is now `8 × exact source-owned identities / all
   eligible named microbial identities`, independent of clinical projections. One fully identified
   strain and five fully identified strains both earn 8. Formulation no longer
   rewards CFU size or strain diversity. Its positive ceiling/reference is 16:
   potency disclosure 4 + exact identity completeness 8 + delivery 3 + the
   existing prebiotic complement 1. Invalid source proof earns no exact credit;
   shared blend CFU is never allocated to its members.
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

## Completed probiotic calibration — frozen runtime `41a7699e`

Config: `1.6.0-probiotic-completeness`, fingerprint `ab9f5a61fd77e879`.
The existing six-pillar scorer, source resolver and measurement owner remain
the only implementation. The obsolete count-only Wave 1 numeric projection
was retired in favor of the existing production replay, not repaired into a
second scorer. Clinical registry records and approval attribution are unchanged.

Final independent reviews approved the implementation. The frozen-code fast
suite passed **15,492 tests, 66 skipped, zero failures** in 458.94 seconds.
Its one warning comes from the deliberate image-decompression-bomb test.
Skipped live/release fixtures are not counted as release validation.

Fixed arithmetic canaries passed: with potency disclosure 4 and delivery 3,
no penalties or optional complement, one exact strain and five exact strains
both earn identity 8/8 and public Formulation 18.8/20. Two exact of four earn
identity 4/8 and Formulation 13.8/20; species-only earns identity zero and
Formulation 8.8/20. Changing total CFU from 1 to 50 billion adds no Formulation
points. The existing full complement can reach Formulation 20/20; no final
score is capped or tuned upward to manufacture an excellent market product.

Source-bound regressions also cover missing clinical projections, structured
forms, aliases, malformed member lists, stale counts, dangling references,
nonlive ancestors, and flattened containers. Actual botanical/food categories
cannot be overridden merely by a derived probiotic name. The same source
predicate protects native clinical/CFU proof; diagnostic originals survive.

Frozen comparisons (read-only; no new cleaning/enrichment):

- Both packets: **111 + 79 products, zero unexpected movements**. Eighteen
  products move in packet 1 and two in packet 2, all in Formulation. Unrelated
  controls and all other pillars are unchanged. Group names such as
  `probiotic_multi_all_exact` are frozen historical strata, not a current
  finding that every label in that group is completely identified.
- All stored products: routing inspected across **15,418** inputs; all **553**
  routed probiotics replayed. Product IDs, every input-file hash and routing
  counts match baseline. Both checkouts are clean and commit-stamped.
- Public statuses: **548 scored, 5 safety-suppressed**, unchanged. Of the 548
  scored products, **162 increase, 383 decrease, 3 stay unchanged**. Mean delta
  is **−2.04**, range **−10.4 to +5.9**. This is removal of count/CFU proxies
  plus corrected source ownership, not a promise that more products score high.
- Pillar changes: Formulation 545; Dose 5; Transparency 2; **Evidence,
  Verification and Safety zero**. No new positive outcomes, tested-dose
  matches, clinical approvals, or AFU-to-CFU conversions were introduced.

Every non-Formulation movement was inspected against actual stored rows:

| Products | Source correction | Dose / Transparency effect |
|---|---|---|
| 182666, 210848 | Six actual microbes, not five; one individually measured. | Dose disclosure uses 1/6, not 1/5. Transparency's existing aggregate floor keeps its public score unchanged. |
| 232325 | Two actual microbial rows, only one exact and individually measured; the previously omitted source remains unresolved. | Disclosure becomes 1/2. Existing limited aggregate-disclosure handling changes; no CFU is allocated to the unresolved row. |
| 251169 | The flattened marketing parent is not an organism: 15 members, 14 exact, zero individually measured. | Removes the parent's falsely individual 10-billion-CFU disclosure. No child borrows its quantity. |
| 46802 | Bioflora is a container for one species-only child with its own explicit 2-billion-CFU quantity, not a second organism. | Corrects disclosure from 1/2 to 1/1. Exact identity and clinical adequacy remain zero; the redundant aggregate floor no longer applies. |

Other inspected controls: HSO 297698 has 12 exact microbial identities;
its grass ingredients are not microbes. FLORASSIST 182421/232334 has five
exact of six actual members: the ambiguous `B. bifidum/lactis BB-02` text
must not disappear merely because an older projection omitted it.

Private before/after receipts are retained under
`reports/private_scoring_calibration_20260915/` (gitignored), including
`probiotic-before-b2ff64d2.json`, `probiotic-after-41a7699e.json`, and both
packet pairs. Final artifact copies were hash-checked. No product-output
directory, shipped database or phone artifact was replaced.

Nonblocking performance observation from independent review: the additional
ancestor checks measured approximately 79ms for 30 synthetic rows, 216ms for
60, and 87ms for the actual 251169 summary. Any future optimization must reuse
this source owner and preserve its adversarial cases, not cache stale results.

**Still not complete:** the folate/B12 IQM source audit (the vitamin/prenatal
form-ownership code batch is recorded below), focused/broad fairness,
generic dose/evidence hierarchy, indication-aware omega, ingredient-specific
fiber/sports, review-coverage explanations, and the complete five-variant
canary matrix. The next vitamin batch is already specified in the same plan.
Do not run the operational commands below until the combined calibration is
stable and the owner is ready to regenerate.

## Vitamin/prenatal form ownership — scoring tree `b5e7499b` (Claude)

Config `1.7.0-vitamin-form-ownership`, fingerprint `32da1b7296417cad`.
IQM `bio_score` is now the only form-quality signal for multi/prenatal and
B-complex scoring. The batch made no IQM numeric edits, added no replacement
form table and changed no schema.

| Owner | Removed duplicate ranking | Retained | Cap/reference |
|---|---|---|---|
| Multi/prenatal Formulation | premium-form count (4), key-form name credit (5) | IQM panel form quality 12 + disclosure 2 | reference 21 → 14, raw cap 25 → 14 |
| B-complex Formulation | preferred-form name table (7) | panel 10 + IQM form 8 + focus 3 + disclosure 2 | 30 → 23 |
| Multi/prenatal Dose | `0.75 + bio_score/60` coverage multiplier | amounts, DFE/units, critical/targeted rules, DHA/choline, UL/B7 | 23 unchanged |

Every changed or removed component was covered by a regression that failed
before the change for the intended reason (17 red), then passed. Canaries:
prenatal IQM 12 gives raw 11.6 / public 16.6, and IQM 15 gives 14 / 20.
B-complex IQM 12 gives 21.4 / 18.6, and IQM 15 gives 23 / 20. At 100% RDA below
the UL, coverage credit is 1.0 for ratings 0, 6, 12, 15 and missing. Underdosing
and UL violations keep their responses. Form wording and panel size add
nothing at equal IQM.

Isolated variants run through `build_scored_artifact`:

- Weak verification moves only Verification.
- Underdosing moves Dose without touching Formulation, Transparency,
  Verification or Safety.
- Unnecessary complexity never adds Formulation. The focused B-complex rule
  still lowers it.
- Incomplete evidence review remains a strict xfail (known Evidence defect above).

An independent review found no scoring defects. Its two low test findings were
fixed before the full suite: a cap-saturated panel-size comparison and a stale
test name. **Full fast suite on frozen code: 15,519 passed, 66 skipped,
2 xfailed, zero failures** (374 s; tree unchanged during the run).

Frozen comparisons (read-only, no regeneration). Both checkouts were clean.
IDs, input-file hashes and routes matched, and the attribution script reported
zero problems:

- **Multi/prenatal, all 2,073 stored:** statuses unchanged (1,927 scored, 145
  not scored, 1 safety-suppressed). Of scored products, 773 go up, 1,120 down
  and 34 stay unchanged. Mean −0.78, median −0.6, range −7.6 to +5.5.
  Formulation moved for 1,879 (mean −1.92); Dose rose for all 1,927 (+0.2 to
  +2.1). Evidence, Transparency, Verification and Safety did not move.
  Retained components and all formulation/dose penalties are identical, and no
  nutrient's coverage decreased.
- **B-complex, all 146 stored:** 133 up, 12 down, 1 unchanged; mean +1.92,
  range −1.5 to +3.7; Formulation only.
- **Packets:** 23 of 111 and 12 of 79 moved. Every mover routes to multi/prenatal
  or B-complex and changes only Formulation/Dose. One tier changed: 4123
  B-complex, Needs improvement → Good.
- **Shipped-tier changes:** 301 of 1,927 multis (107 Good → Needs improvement,
  91 Very good → Good, 44 Needs improvement → Good) and 48 of 146 B-complex
  products (20 Good → Very good, 18 Needs improvement → Good, 8 Very good →
  Excellent, 1 Excellent → Exceptional).

Unexpected movements and their source-level causes:

- **Largest multi drops (−7.6):** meal shakes such as 802 carry unchanged
  formulation penalties of 6.5–9.5 (harmful additives 7 + sugar 2). Raw went from
  7.2 + 4 + 5 + 2 − 9 = 9.2 to 7.2 + 2 − 9 = 0.2.
- **Presence floor:** the multi/prenatal and generic floor (`pre_floor_score <= 0`)
  leaves products with a small positive remainder below floored ones.
  Scored multis in that band: 44 → 120. Floored: 45 → 178. Not changed here;
  owner decision.
- **Dose:** every scored multi's Dose pillar rises because nearly every rated
  form is below 15. Critical anchors without a threshold (for example vitamin A,
  vitamin C and zinc in core multis) inherit the unweighted coverage by the
  existing rule.
- **B-complex Formulation:** the reference drop lifts products without name
  credit. 209616 (average IQM 10) rises 93.6 → 96.6, Exceptional, because 15/23
  of Formulation is now structure. The failure fixture moves Poor → Needs
  improvement for the same reason.
- **266767 Prenatal Multi + DHA** (average IQM 9.69) loses 7.5 name/count
  points and moves 89.5 → 87.7, Excellent → Very good.

Private receipts (gitignored) are in `reports/private_scoring_calibration_20260915/`:
`multi-before-a7b676e4.json`, `multi-after-candidate.json`,
`bcomplex-before-a7b676e4.json`, `bcomplex-after-candidate.json`, both packet
pairs, and the rerunnable `compare_vitamin_replay.py`.

### Audit of the completed probiotic batch

- Vitamin products were untouched: 2,073 + 146 stored products are
  score-identical from `b2ff64d2` to `a7b676e4`. Every probiotic receipt number
  above was recomputed from the two receipts and matches exactly: 553 products;
  548 scored and 5 suppressed; 162 up, 383 down, 3 unchanged; mean −2.04; range
  −10.4 to +5.9; Formulation 545, Dose 5, Transparency 2, other pillars 0.
- **HIGH, reproduced and fixed by adversarial audit:** a resolved IQM identity
  outside the `probiotics` category now outranks broad or incorrect source
  categories. This covers Spirulina/Chlorella filed as bacteria and four Solgar
  Turmeric rows incorrectly typed by DSLD, without an algae-specific exception.
  A fresh two-product source re-enrichment proves 63308 Best Spirulina remains
  non-probiotic, while 31062 Super Foods 25 remains a multivitamin and retains
  exactly one typed Bacillus coagulans member plus its 12.5-billion-CFU
  disclosure. Plural `Probiotics`, scaled CFU units, and long-tail probiotic IQM
  identities are covered by regression tests; enrichment, taxonomy, and scoring
  consume the same predicate and dependency-free IQM reference owner.
- Seventeen slow real-catalog canaries fail identically at clean `a7b676e4`
  (omega p161 ×9, cross-module probiotic ×7, generic 184661). `fast` excludes
  them through `scripts/test_profiles.py`, so refresh them before release gates.
- Of the four low findings, Chlorella is fixed by the same shared resolved-IQM
  rule, including when it appears inside a probiotic blend container.
  Ref-less multi-strain totals remain deliberately ineligible for per-strain
  dose credit because their ownership cannot be proved. Existing source-owner
  tests cover nested/flattened representations. ProDentis/Shirota remains a
  separate registry-identity review, not a reason to loosen exact matching.

The same adversarial audit also fixed two cross-category boundaries found by
the vitamin canaries: the shared Formulation presence floor is monotonic across
the whole sub-floor interval, and unresolved generic effect direction now earns
zero Evidence rather than default-positive credit. The full fast tier passed
with 15,529 tests and 66 expected skips.

No Clean/Enrich/Score regeneration, catalog build, release, Supabase deployment
or phone build ran.

## One probiotic identity owner — follow-up to the adversarial audit (Claude)

**Codex audit verified.** The four commits `b289c3fd..fab83fc6` hold up on real
stored data:

- The 11 source-shaped regressions for Spirulina, the mislabeled Solgar Turmeric
  and the Chlorella container pass.
- The full-corpus taxonomy and route diff from `66bec377` to `fab83fc6` shows
  0 changes across 13,704 products.
- The monotonic presence floor lifts only 5 stored products that carry no
  penalty, by at most +0.25 raw.
- CFU unit scaling fixes a real miss: 31062 declares 12.5 Billion CFU.
- The creatine test follows production behavior that the earlier typed-UL
  commits had already introduced.

**Remaining duplicates removed.** Before this change there were three regex
copies, the contract's and the enricher's text-only probiotic checks, a
routing raw-category shortcut, and three copies of the fiber/prebiotic support
rule. They are now one regex, one row-identity predicate and one support
predicate in `probiotic_measurements`. Enrichment, taxonomy, routing and the
scoring contract all call them.

**Reference-identity guard extended.** A resolved `other_ingredients` record
now outranks category-only or derived-name organism evidence, like an IQM
identity outside `probiotics`. The ten reviewed microbe-, yeast- or
culture-named records are pinned in `test_probiotic_identity_single_owner.py`.
All are processing aids, label descriptors or derived/nonviable preparations.
This covers:

- Immuno-LP20 (`NHA_IMMUNO_LP20`), a nonviable heat-treated L. plantarum L-137
  preparation;
- 535 processing-aid `S. cerevisiae` carriers nested under minerals.

**Measured (read-only, identical stored inputs, `fab83fc6` vs candidate):**

- 0 taxonomy and 0 route changes.
- 79 score-time contract output changes: 70 non-probiotic panel counts and 9
  recovered nested strict rows.
- 1 public score change: 232325 "Oral Hygiene", 49.1 → 61.3.
  - Before, the nonviable Immuno-LP20 counted as a second, unidentified strain.
  - Now the single live strain, BLIS M18, is fully identified and measured.
  - Components: identity completeness 4 → 8, Dose per-strain disclosure 5 → 10,
    Transparency per-strain CFU 3.5 → 7.
- Evidence, Verification and Safety are unchanged.

Full fast tier on `cb678d43`: **15,549 passed, 70 skipped, zero failures** (398 s; tree unchanged).

**Open decisions surfaced, not changed here:**

1. **Mass-dosed brewer's yeast.** Printed `Saccharomyces cerevisiae` label
   names on mass-dosed `brewers_yeast` rows (IQM `functional_foods`) still
   count as organisms. That is 521 stored rows in 38 products, mostly
   multivitamins, all already stored as probiotic products. An existing test
   pins live S. cerevisiae with CFU as probiotic. Decide whether a resolved
   non-probiotic identity with a mass dose should outrank the printed name.
2. **Pomegranate in the prebiotic registry.** The registry lists "Pomegranate
   Polyphenol Extract", with aliases including "pomegranate extract". Every
   pomegranate extract therefore matches the prebiotic matcher: it earns the
   probiotic Formulation prebiotic complement and shows as prebiotic-present.
   Confirm that clinical policy before the rebuild.
3. **Corpus state after the stopped run.** The stopped
   `batch_run_all_datasets.sh` regenerated 9 brands and left GNC half-enriched.
   Earlier replay receipts no longer match the stored inputs. Rebuild from
   Clean only once calibration is stable.

## Next operational run — after the remaining calibration

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
