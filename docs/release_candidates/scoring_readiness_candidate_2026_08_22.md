# Scoring Integrity Candidate — Corrected Audit — 2026-08-22

Status: **technically verified preproduction candidate; not approved or published**

This report supersedes the earlier 2026-08-22 readiness report. The earlier report mixed
aggregate projections with label rows, understated the reviewed route diff, reported stale
candidate counts, and treated an environment-dependent Red Yeast Rice failure as an open defect.
Those statements are corrected here from a fresh corpus rebuild and direct candidate queries.

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
| Scored | 13,164 | **14,357** |
| Safety-suppressed | 107 | **52** |
| NOT_SCORED in live catalog | 0 | **0** |

Candidate database SHA-256:
`2cb086d318dc4b68897a8bc29bc989750115686b54219f28be617fc5103d2ea6`

The candidate contains 14,409 detail blobs and a 56,569,856-byte core database. On the 12,556
products shared with the shipped baseline, 568 routes, 1,493 scores, 615 tiers, 568 verdicts,
46 score statuses, and 276 blocking reasons changed. Mapping coverage changed on zero shared
products. The candidate adds 1,853 live products and removes 715 prior live products.

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
2. Remediate the enforced review queues: 893 dose, 93 identity, and 7 route products. Keep the
   4,939-product evidence queue visible and curate it one verified ingredient at a time.
3. Rebuild the production interaction artifact with the configured UMLS credential, then run the
   real interaction-parity gate.
4. After explicit release approval, import and ship the compatible Flutter 2.4 bridge, run bundle
   parity, then perform the separately authorized Supabase/app publication. None of those actions
   are included in this candidate audit.
5. After one compatible app release, execute schema-3 cleanup. Keep score calibration as a later,
   separately versioned release.

The machine-readable companion report contains the artifact hashes, exact counts, verification
results, and a canonical-JSON self-integrity hash. That hash detects report changes; it is not an
identity signature.
