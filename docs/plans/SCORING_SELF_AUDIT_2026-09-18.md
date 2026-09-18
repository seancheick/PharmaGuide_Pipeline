# Self-audit of the scoring batch (2026-09-18)

## 0. The fresh batch does not contain my work

The run at 10:12–10:58 today was executed from the `claude/evidence-expansion` checkout, which
carries none of the omega batch. The artifacts say so themselves:

```
_v4_config_fingerprint = {"omega":         {"version": "1.2.0-label-stated-omega-amounts"},
                          "quality_score": {"version": "1.10.1-omega-printed-epa-dha"}}
```

Mine are `1.3.0-omega-semantics-2026-09` and `1.11.0-omega-semantics-2026-09`. Thorne Advanced DHA
reads **57.6** in that batch — the pre-fix number. `scripts/identity/omega_labels.py` is not even
present in that tree, so the clean stage ran without the cleaner fix too.

So I did not audit those scores. I scored the fresh **enriched** corpus with my tree instead: same
inputs, one variable. **15,109 products, 0 crashes.**

## 1. Bugs found in my own work

### A. A latent Safety bug — FIXED (`2883b9eb`)

`_low_severity_additive_magnitude` subtracted the **uncapped** `inactive_penalty_details` ledger from
a mirrored total carrying the **clamped** `B1_harmful_additives` charge. Once the ledger exceeds the
charge, the excess comes out of `B1_dietary_sugar` standing beside it in the same mirror group — a
sugary product silently stops losing Safety points, the opposite of the decision that left sweetener
and colour tiers untouched.

Proved by direct call: sugar −4.0, additive charge −1.0, ledger 10 × 0.5 → deduction **0.0** instead
of 4.0.

Not reachable today: the cap is 15.0 against 0.5 per low-severity entry, and **zero of 15,109**
products has a ledger larger than its charge. It fires the moment anyone calibrates that cap down,
which is a config knob. Clamped to the charge it explains; two regression tests.

### B. The oxidation explanation contradicted the score — FIXED (`4033fbe6`)

`_OMEGA_DISCLOSURE_ITEMS` still listed oxidation testing after the rubric set it to 0, so **every**
omega product was told oxidation testing was not disclosed by a pillar that no longer charges for it,
and the "everything is disclosed" sentence became unreachable — a retired component can never appear
in the credited list. Visible in a live probe.

**The two pins I wrote in the same batch asserted the contradictory sentence**, which is why the suite
stayed green. Both corrected with the reason recorded beside them.

### C. Oxidation is now owned by nobody — REPORTED, NOT FIXED

My checkpoint said "Verification keeps oxidation ownership". That is not true in code. The
Verification pillar's components are `cert`, `coa_batch`, `gmp`, `testing`, `brand_only_cert`,
`reputation`. Nothing on the verification side reads oxidation. Removing it from Transparency was
right — zero of 708 omega products could earn it — but it never got its new home. Creating a
Verification component is new scoring, so it waits for you.

## 2. Did the plan finish?

The older certification/POOR plan landed, steps 1–4, verified in code today:

| step | evidence |
|---|---|
| 1 claimed vs verified contract | `cert_evidence.claimed_programs / verified_programs / verified_quality_flags`; `verified_capabilities` in `cert_claim_rules.json` |
| 2 record-scoped rejection | `cert_resolver` collects rejected `record_id`s and notes "all registry candidates rejected by override" |
| 3 registry-backed GMP | `facility_registrations` present in `top_manufacturers_data.json` |
| 4 POOR owned by the tier | `score_supplements_v4`: "POOR is not decided here". Shipped verdicts are only `no_known_catalog_concern` / `caution`; quality tiers are clean non-overlapping score bands (Poor ≤ 54.4 … Exceptional ≥ 95) |

Steps 5–6 were the clean-corpus comparison and the fresh rebuild — still open, and they are exactly
what the next integration run should be.

The eleven decisions you approved are all implemented and verified against the merged tree, except as
noted in 1C.

## 3. Are we one system?

| fact | owner | verdict |
|---|---|---|
| "this row states EPA and DHA" | `identity/omega_labels.states_only_epa_and_dha` | one definition, two callers (cleaner + contract) |
| EPA+DHA dose curve | `omega_dose._band_score` | one owner; anchors exact, monotonic |
| molecular form quality | `omega_rubric.form_tier` | one table |
| source disclosure | detector in `omega_formulation`, **points only in Transparency** | correct after the batch |
| unrated ingredient form | imports `multi_prenatal_formulation.PANEL_FORM_NEUTRAL_FLOOR / BIO_SCORE_MAX` | no second number invented |
| GRAS excipient give-back | the additive ledger, now clamped to its own charge | correct after fix A |
| oxidation disclosure | **nobody** | finding 1C |

The omega transparency cap still lives in three config places (`omega_rubric.dimension_caps`,
`quality_score.category_magnitudes.omega.dimension_caps`,
`quality_score.transparency_magnitudes.omega.cap_transparency`). All three read 13 and each is pinned
by a test, so it is duplicated-but-guarded rather than drift-prone. The rubric's copy is read by no
production code.

## 4. Do the scores make sense?

Full-catalogue A/B on identical enriched inputs, 15,109 products:

| measure | value |
|---|---:|
| changed | 6,883 (45.6%) |
| up / down | 6,745 / 138 |
| mean over all products | +0.84 |
| tier changes | 944 |
| crashes | 0 |

**Attribution by pillar** — each matches an approved decision:

| pillar | products | mean | note |
|---|---:|---:|---|
| safety_hygiene | 6,183 | +1.16 | GRAS excipients; all up, none down |
| formulation | 899 | +5.20 | unrated-form neutral up, omega form-tier compression down |
| transparency | 690 | +1.26 | omega cap 15 → 13 |
| dose | 427 | +2.19 | Model C interpolation |
| evidence | 212 | −4.84 | the retired ≥1,000 mg bonus |
| verification | 0 | — | see §5 |

**Invariants you set, checked on the real corpus:**
- no product zeroed on Safety by a genuine driver recovers: **0**
- no product loses Safety points: **0**
- pillar values outside their max: **0**; scores outside 0–100: **0**
- every one of the 138 down-movers is an omega product — **no collateral damage** from the two
  catalogue-wide changes

**Route diff** (the standing rule I had skipped): **7 products** change module, all
`generic → omega`, all omega gummies, mean −14.7. A 300 mg fish-oil gummy declaring 50 mg EPA+DHA now
routes to omega and is judged as one: dose 0 (the reviewed floor is 100 mg/day), form undisclosed. The
old 62.3 was crediting carrier-oil mass as if it were EPA+DHA.

## 5. Two things that need your decision

**The first perfect scores in the catalogue.** Six products reach **100.0/100**, up from zero —
Thorne Curcumin Phytosome 1000 mg goes 98.5 → 100.0 with every pillar maxed. The only thing that
moved is Safety 8.5 → 10.0, because its additive flags were low-severity GRAS excipients. The
evidence says those carry no safety finding, so 10/10 on *safety* is defensible; whether a product
containing microcrystalline cellulose should publish as **100/100** is product policy.

Distribution: Poor −345, Good +228, Very good +128, below-40 370 → 296.

**Certification overrides need a re-enrich.** Only 7 of my 31 override entries are in the tree that
produced the fresh batch, so 24 score `cert = 0` there. This is not a defect: `discover_verified_programs`
is called from `enrich_supplements_v3.py`, and the scorer only reads what enrichment already stamped.
The 7 that are present score `cert = 9.0`, which is the end-to-end proof that the re-keying fix works.
An override is invisible until its products are re-enriched.

## 7. The canaries, run against the real corpus

My worktree has no `scripts/products`, so every catalogue-backed canary had been **skipping** in each
"15,639 passed" run I reported. I attached the real corpus to a separate worktree and ran them.

| file | result |
|---|---|
| `test_v4_omega_dose_p162` | 44 passed, 1 skipped — Model C values (16.4 / 16.64) hold on real labels |
| `test_v4_omega_evidence_p163` | 29 passed, 2 skipped |
| `test_v4_omega_transparency_p165` | 39 passed, 1 skipped |
| `test_v4_omega_formulation_p161` + `_skeleton_p160` | 107 passed |
| `test_scoring_snapshot_v1` (the 3 I froze) | 35 passed |
| `test_v4_omega_final_assembly_p166` | **5 failed**, 13 passed, 1 skipped |

**267 passed, 5 failed, 5 skipped.**

### The 5 failures are mine, and they are stale baselines rather than a regression

`test_canary_final_score_in_range` pins `score_omega(...).to_breakdown()["score_100"]` — the omega
module's RAW rubric score, not the public six-pillar score.

| product | expected | actual |
|---|---|---:|
| Sports Research 327776 / 326270 | 84.9–85.9 | 64.4 |
| Nordic Naturals 288740 | 63.6–64.6 | 56.6 |
| Garden of Life 273630 | 84.0–85.0 | 64.1 |
| CVS Health 239592 | 49.4–50.4 | 33.4 |

Decomposing Garden of Life 273630 (64.1):

```
formulation   12.0/25   form_tier 8 + epa_dha_concentration 4
                        (premium-form carry and source disclosure both gone)
dose         16.64/25   Model C interpolation — slightly UP
evidence      10.0/20   the retired >=1,000 mg bonus, -5
transparency   9.0/13   cap 15 -> 13
```

Every line is one of the four approved changes, and the caps now sum to 83 instead of 85. The public
six-pillar score for that same product is **82.0, Very good** — the raw module scale is where the
removals bite hardest.

**I have not re-baselined the ranges.** The test says "update the ranges deliberately — never widen
them silently", and the only corpus available today is mixed: enriched by the old cleaner, scored by
my tree. Re-pin them from the integration run's output, not from this.

### Two canary hygiene problems

- **182968 (Pure Encapsulations) is not in the corpus at all.** It skips in all four omega canary
  files, so it has been protecting nothing.
- Corpus-gated canaries skip silently wherever `scripts/products` is absent. A skipped canary reads
  as a pass in the summary line.

## 8. Full suite

**2 failed, 15,640 passed, 191 skipped.** Both failures are `test_submission_queue_contract.py`,
which reads `/Users/seancheick/PharmaGuide ai/supabase/migrations`. A new migration,
`20260918160000_admin_submission_notification_outbox.sql`, was written there at **11:59 today** —
between my two runs. It is someone else's in-flight app work reaching a cross-repo contract test, not
a scoring change.

## 6. What the next run has to be

A full **clean → enrich → score → export** from the merged tree. Clean, because the cleaner changed;
enrich, because the certification overrides live there. Nothing before that measures the batch as it
will ship.

Branch: `claude/scoring-into-evidence`. Nothing pushed, nothing released.

## 9. How to reproduce these numbers

Do not write a new harness — the owners already exist and this audit's scratch scripts were
duplicates of them:

| measurement | owner |
|---|---|
| full-corpus score/dimension/route delta against the shipped scored artifacts | `scripts/api_audit/v4_full_corpus_delta.py` (baseline = the shipped scored universe; emits `delta.csv`, `histogram.json`, `large_deltas.md`, `verdict_flips.csv`, `provenance.json`, and carries `v4_module` and per-dimension scores) |
| certification resolution and per-product scope/credit | `scripts/api_audit/cert_audit_report.py` |
| omega canaries against the real catalogue | `scripts/test.sh fast scripts/tests/test_v4_omega_*.py` from a checkout where `scripts/products` exists |

One gap worth closing deliberately rather than with another script: `v4_full_corpus_delta.py` reads
`score_100_equivalent` as its baseline, because it was written for the v3 -> v4 cutover question. A
v4-vs-v4 comparison needs that baseline key to be selectable. That is a one-field change inside the
existing owner, not a new file.
