# Scoring Integrity Candidate — Corrected Audit — 2026-08-22

Status: **technically verified preproduction candidate; not approved or published**

This report supersedes the earlier 2026-08-22 readiness report. The earlier report mixed
aggregate projections with label rows and treated an environment-dependent Red Yeast Rice
failure as an open defect. Those statements are corrected here from a fresh corpus rebuild and
direct candidate queries.

The product, quarantine, and route-change counts in that earlier report were **not** measurement
errors and are not corrected here. 14,380 live / 1,032 quarantined / 52 reviewed route changes
were accurate for the code state they were measured against — the candidate database built at
that commit contains exactly 14,380 rows. The counts moved because the code moved: row-level
protein routing and the route readiness dimension landed afterwards. Superseded, not corrected.

No Supabase upload, Flutter bundle import, app asset commit, push, cleanup, or production
promotion was performed.

## Audit verdict

Claude's implementation was directionally strong, but it was not fully correct or ready to
approve as delivered. The follow-up audit found and fixed pipeline, report, and Flutter consumer
defects. The corrected code is green at the technical gates. Publication still requires operator
sign-off for 12 US safety-policy holds and a separately authorized production release.

## Corrected candidate

| Measure | Shipped baseline | Corrected candidate |
|---|---:|---:|
| Export schema | 2.3.0 | **2.4.0** |
| Scoring version | 4.2.0 | **4.3.0** |
| Live app products | 13,271 | **14,409** |
| Quarantined products | 14 | **1,003** |
| Scored | 13,164 | **14,355** |
| Safety-suppressed | 107 | **54** |
| NOT_SCORED in live catalog | 0 | **0** |

Candidate database SHA-256:
`855684b0585cde7c20dce83e4ef438eeda03393ccb46b8f234d2bed45d035a82`

The candidate contains 14,409 detail blobs and a 56,573,952-byte core database. It adds 1,853
live products and removes 715 prior live products; 12,556 are shared with the shipped baseline.
On those shared products the columns that exist in both the 2.3 and 2.4 schemas changed as
follows: 565 verdicts, 274 blocking reasons, 44 score statuses. Mapping coverage changed on zero
shared products. Route, score, and tier columns were renamed between schemas and are not
directly comparable.

This supersedes the earlier candidate hash
`2cb086d318dc4b68897a8bc29bc989750115686b54219f28be617fc5103d2ea6`, which predates the
compound-excipient safety fix below.

## What the audit corrected

1. **Evidence applicability now follows row provenance.** Only rows explicitly marked
   `scoring_input_kind=product_level_evidence` are synthetic aggregates. Protein, fiber, enzyme,
   and blend identities are not globally exempted merely because their canonical name resembles
   an aggregate. This fixes the structural root cause without a hand-maintained canonical denylist.
2. **The real evidence backlog is 4,939 products / 8,935 material label rows**, not
   7,722 / 17,636. Product-level aggregate projections no longer inflate it. Evidence remains a
   measured shadow dimension under the approved category-aware policy; identity, dose, route,
   and verification remain enforced.
3. **Routing was corrected and reviewed against the enriched corpus.** The final gold set contains
   173 reviewed changes and zero unreviewed changes: 45 fiber-to-generic, 10 fiber-to-sports,
   57 generic-to-sports, and 61 multi/prenatal-to-sports. Seven unresolved title-claim protein
   products are quarantined rather than guessed into a route.
4. **Readiness audits now fail closed** if a producer and consumer disagree about which dimensions
   gate catalog eligibility.
5. **Red Yeast Rice is not an open regression.** The prior failure came from stale test state.
   Generic Red Yeast Rice remains CAUTION; explicit monacolin/lovastatin matches block. Targeted,
   release, and full suites all pass in the rebuilt environment.
6. **Candidate manifests no longer claim gates that were not run.** Interaction-database parity
   and Flutter-bundle parity are identified as post-candidate gates, not stamped as passed.
7. **Quarantine records are actionable.** They identify the unavailable reason and incomplete
   enforced dimensions instead of reporting every case as a generic mapping/dosage failure.
8. **Supabase dry-run reporting now prints the actual export schema** instead of a hard-coded
   legacy value.
9. **Schema-3 warning reconstruction in Flutter is now faithful.** It verifies reviewed-copy
   fingerprints, resolves pregnancy/lactation aggregate copy, preserves evidence/source
   provenance, and fails closed on copy drift. Resolved compact warnings now reach product-fit
   and stack dose calculations, not only product detail display.
10. **The Flutter importer now binds schema 2.4 to the generated Drift projection**, supports only
    valid interaction schema/user-version pairs, and verifies the schema-2 warning registry across
    manifest, embedded metadata, and physical table. Legacy safety gate state is migrated out of
    score-confidence vocabulary.

## Mapping, readiness, and quarantine

- Mapping: **84,492 / 84,492** score-eligible rows mapped; zero products below 1.0; zero strict
  mapping-contract failures.
- Readiness corpus: 15,412 products; 14,419 live-ready; 993 incomplete on enforced dimensions.
- Enforced incomplete dimensions: dose 893, identity 93, route 7, verification 0.
- Evidence shadow: 4,939 products / 8,935 material label rows not yet evaluated.
- Verification: 1,412 verified present; 14,000 verified absent; zero not-evaluated defaults.

The 1,003 exported quarantines are mutually exclusive records:

- 891 completeness/dose
- 93 completeness/identity
- 7 completeness/route
- 10 safety-policy review only
- 2 safety-policy review plus dose

The 12 policy holds are nine vinpocetine products (`204468`, `232923`, `294063`, `295535`,
`328399`, `44121`, `59786`, `60562`, `77114`) and three confirmed synthetic-steroid-class
products (`33358`, `33360`, `33361`). Their matches are confirmed; their final US consumer
verdict remains an operator clinical-policy decision.

## Safety verdict transitions

Quarantine is the conservative direction and it is the direction this report asked the operator
to sign off on. The permissive direction was not itemised anywhere, so it is recorded here.

Against the shipped baseline, **46 products lost a BLOCKED verdict and stayed live**. Two of
those were a defect, now fixed, leaving **44 deliberate policy transitions**:

| Cause | New verdict | Products | Status |
|---|---|---:|---|
| Red Yeast Rice, no monacolin/lovastatin declaration | CAUTION | 27 | needs sign-off |
| Sodium tetraborate as a declared boron source | SAFE | 16 | needs sign-off |
| Sodium tetraborate as a declared boron source | CAUTION | 1 (`312980`) | needs sign-off |
| Partially hydrogenated soybean oil | was SAFE | 2 | defect — blocked again |

A further 12 baseline-BLOCKED products left the live catalog into the policy-hold quarantine.

**The 44 Red Yeast Rice and tetraborate transitions are defensible and need sign-off.** NIH ODS
lists sodium tetraborate as a supplemental boron form, so a declared source salt is not the
retired food-additive block. NCCIH records monacolin K in red yeast rice ranging from none to
substantial, and the FDA prohibition addresses products with enhanced or added lovastatin, so
generic RYR is a high-risk review rather than an automatic unapproved-drug block. Both are
clinical-policy calls, not defects — and both move a consumer-facing verdict, so both belong in
the sign-off queue beside the 12 holds.

**The 2 PHO transitions were a defect and are fixed.** `33212` and `33230` declare Partially
Hydrogenated Soybean Oil inside a `Creamer` row whose `forms[]` is a sub-ingredient list. Because
a sibling child (Dipotassium Phosphate) duplicated the declared Potassium active, the active-form
duplicate rule suppressed the whole row and took the banned child with it, in all three callers.
The resolver identified `BANNED_PHO` correctly; the callers discarded it. FDA removed PHOs from
GRAS and the compliance period has closed, so this is not a sign-off choice.

Suppression is now scoped to the terms that earned it. Measured over the enriched corpus: 10,344
of 83,353 inactive rows are suppressed by this rule and exactly 4 carry an independent banned or
concern identity — the two PHO milkshakes, `178791` (Talc and Titanium Dioxide inside a Film
Coating row, beside a duplicated Riboflavin active) and `223441` (Carob color inside a Soft Gel
Capsule row). A full-corpus before/after diff over 15,412 products changes 4 safety-hit sets, all
gaining a signal, none losing one.

The corpus test that should have caught this repeated the same shortcut in its own oracle, while
its failure message named `33212` as the canary it expected to cover. The oracle no longer shares
the suppression rule, and both products are named canaries with an independent label-text check.

## Verification

- Full corpus enrich + score: **37 / 37 datasets, zero failures**.
- Pipeline release suite: **111 passed, 1 expected interaction skip, zero failures**, followed by
  live RxCUI, direct-drug, PMID existence, and reviewed-content gates with zero unresolved IDs.
- Pipeline full suite: **14,311 passed, 163 skipped, 2 documented xfailed, zero failures**.
- Candidate build: 14,409 live products, 1,003 quarantines, zero export-contract failures, and no
  red contract-sync findings.
- Flutter analysis: **no issues**.
- Flutter full suite: **3,235 passed, zero failures**.
- Candidate catalog + interaction importer dry-run: **passed; no app files written**.
- Supabase sync dry-run: **passed; no upload performed**.
- Warning equivalence for prepared schema 3: **181,471 checked, zero failures**.

The structural interaction artifact is schema 2.0.0/user-version 2 with 134 interactions,
31,690 research pairs, and 145 profile warning rules. Its SHA-256 is
`c1670111a4c09bc6262e35586a75f5f48d60c1b011077c21eebe531899c9ba67`.
The build environment did not contain `UMLS_API_KEY`, so this temporary artifact proves the app
bridge and structural gates, not final production identity verification. The pipeline release
suite independently passed its live identity gates; the production interaction build must still
run with the configured key.

## Prepared schema 3

Against the 14,409 candidate blobs, the prepared schema-3 projection reduces payload from
2,278,680,140 to 1,354,118,116 bytes: **924,562,024 bytes / 40.5745% saved**. This is a measured
future cleanup, not authorization to ship schema 3 before one compatible 2.4 app release.

## What is next

1. Operator signs off or retains quarantine for the 12 US safety-policy cases, including whether
   confirmed Schedule III synthetic-steroid-class matches may remain CAUTION or must be
   BLOCKED/UNSAFE.
2. Operator signs off on the 44 permissive transitions in **Safety verdict transitions**: 27 red
   yeast rice products moving BLOCKED → CAUTION, and 17 sodium tetraborate products losing the
   blanket ban (16 to SAFE, one to CAUTION). Both are supported by the cited authorities; both
   change a consumer-facing verdict and neither has been approved. The 2 PHO products are not on
   this list — they are a fixed defect and stay blocked.
3. Remediate the enforced review queues: 893 dose, 93 identity, and 7 route products. Keep the
   4,939-product evidence queue visible and curate it one verified ingredient at a time.
3. Rebuild the production interaction artifact with the configured UMLS credential, then run the
   real interaction-parity gate.
4. After explicit release approval, import and ship the compatible Flutter 2.4 bridge, run bundle
   parity, then perform the separately authorized Supabase/app publication. None of those actions
   are included in this candidate audit.
5. After one compatible app release, execute schema-3 cleanup. Keep score calibration as a later,
   separately versioned release.

## Open questions this candidate does not answer

1. **Probiotic `formula_only` badges bypass clinician review.** The producer sets
   `formula_only` before it checks `dr_pham_signoff`, so 148 of the candidate's 1,190 research
   rows render "Research applies to the formula, not necessarily each strain" without a
   sign-off. `exact_strain` (242) and `species_level` (787) sum exactly to the 1,029
   clinician-verified rows, so this is the only affirmative badge that can appear unreviewed.
   Display policy decision, not a defect.
2. **The clean-label lane never reads `forms[]`.** `_iter_resolver_clean_label_hits` collects
   only `name` / `standardName`, so a clean-label additive declared as a sub-ingredient of a
   compound excipient is invisible to it. `178791` reaches the safety lane through the fix above
   but its Titanium Dioxide still does not reach the clean-label flag. Pre-existing and
   independent of the duplicate rule; not changed here.
3. **`Organic Red Yeast Rice` resolves to no rule at all.** The bare and `Powder` forms resolve
   to `RISK_RED_YEAST_RICE`; the `Organic` prefix does not. An alias gap, unrelated to the
   policy question above.

The machine-readable companion report contains the artifact hashes, exact counts, verification
results, and a canonical-JSON self-integrity hash. That hash detects report changes; it is not an
identity signature.
