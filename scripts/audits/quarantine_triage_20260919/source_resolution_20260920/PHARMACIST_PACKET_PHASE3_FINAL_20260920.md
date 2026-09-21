# PharmaGuide — Phase-3 final clinical decision record

Date: **2026-09-21**
Phase: **Phase 3 — quarantine remediation / clinical sign-off**
Supersedes: `PHARMACIST_PACKET_PHASE3_SOURCE_RESOLVED_20260920.md` (source-resolution draft)
Status: **DECISIONS RECORDED — CLOSED**

> This is the archived clinical decision record. It is no longer a request for a
> decision: every clinical policy question raised by the Phase-3 review has been
> decided by PharmaGuide's clinical authority and implemented in the pipeline.
> The four sections below state the decided policy, its implementation, and its
> measured effect. No question boxes remain.

---

## Clinical authority

| | |
|---|---|
| **Clinical reviewer** | **Dr. Pham** |
| **Team** | **PharmaGuide Clinical Team** |
| **Decision date** | **2026-09-21** |
| **Phase** | Phase 3 |
| **Policy decisions** | Approved as documented below |
| **Overall** | **APPROVED WITH SPECIFIED PRODUCTS HELD** |

Per PharmaGuide owner governance, Dr. Pham / PharmaGuide Clinical Team is
sufficient clinical sign-off authority for Phase 3. No licence number, state
licence, credential verification, external attestation, or other pharmacist
paperwork is required by that governance and none is recorded here.

The clinical team's supplied decision response is the supporting review
artifact for this record.

---

## Status

| Domain | Status |
|---|---|
| Source verification | **COMPLETE** |
| Source corrections | **APPLIED** — 10 products carrying a correction receipt are implemented and replay-verified (9 source rewrites plus the structural folate declared-total closure of `201420`, zero data rows changed) |
| Engineering validation | **COMPLETE** — static source-of-truth audit 0 findings; fast tier 0 failures |
| Frozen-corpus replay | **COMPLETE** — see §5 |
| EDTA product policy | **DECIDED — implemented** (`BLOCKED_SAFETY_CARD_NO_SCORE`) |
| Botanical standardization constituents | **DECIDED — implemented** (`CONTAINED_CONSTITUENT_MODEL_APPROVED`) |
| Discrete-enzyme formulation | **DECIDED — implemented** (`NOT_INDIVIDUALLY_RATED_APPROVED`) |
| Beta-carotene / Vitamin-A UL | **DECIDED — verified intact** (`PREFORMED_VITAMIN_A_ONLY`) |
| Release authority | **SIGNED — Dr. Pham / PharmaGuide Clinical Team** |

**Clinical policy unresolved: 0** · Source/data unresolved: **0** ·
Engineering unresolved: **0** · Products with an undefined disposition: **0**

The durable policy ledger is
`scripts/audits/quarantine_triage_20260919/PHASE3_CLINICAL_POLICY_20260921.md`.

### Resolved — do not research these

| Item | Resolution |
|---|---|
| E2 vitamin-unit defects (223563, 223572, 328644) | `mg RAE` → `mcg RAE`, unit only. `mg RAE` occurs on no other vitamin-A row in the 15,414-record corpus, and each row's own printed %DV resolves on the microgram basis. |
| E2 rows 231334 / 231335 / 263865 | Printed denomination is DFE-shaped but cannot be separated from RAE at audit grade. **Explicitly withheld** — no plausibility rewrite. |
| B12 raw-material tubs (254396, 254413) | Printed panel carries no Supplement Facts dose and states "not intended for individual use … qualified professionals only"; classified `intentional_non_scoreable` (`professional_formulation_material`). |
| 12300 Fem-Mend proprietary blend | The label declares only an 860 mg blend total with zero component doses. Withheld on source insufficiency — no dose may be invented. |
| Vitamin-A form on Bulk 1340 (228823, 243799, 243808, 243812, 243815) | The printed vitamin/mineral blend names `Natural beta-Carotene` as the only vitamin A source. Form provenance is **recorded**; the row is not defaulted to retinol. |
| Vitamin-A UL applicability for provitamin A | **Not a clinical judgement.** NIH ODS states the Vitamin A UL applies to preformed vitamin A only, and beta-carotene and other provitamin-A carotenoids have no established UL. Implemented and test-pinned. See §4. |
| Folate source duplication (243808, 246430, 201420) | Source structure established; the declared-total contract identifies the dose owner **structurally** rather than from a parent-name vocabulary. `201420` is closed (zero data rows changed; its independent niacin exceedance and `CAUTION` verdict preserved). |
| Serrapeptase 269360 | The printed Supplement Facts panel declares `Serrapeptase Enzyme 40,000 SPU`; the amount is restored from the panel, never from the product name. |
| DSLD nesting / label-version questions | Resolved against sibling label records and archived label images. |

---

## 1. Standalone oral EDTA — DECIDED

**Policy:** `BLOCKED_SAFETY_CARD_NO_SCORE` — **BLOCKED**, consumer-visible
through a **Safety card**, **no quality score**. Reason semantics
`NON_ROUTINE_CHELATOR` / `CLINICIAN_REVIEW_REQUIRED`.

**Clinical basis.** Independent of the other sourcing policies in this record,
EDTA is included here as a *single-source-position* entry: every claim below
comes from the same one authority (FDA), and FDA is the authority that owns the
question. No PubMed, Springer, Frontiers, or PMC source was used anywhere in
the policy basis, so there is no multi-source bibliography to verify against
and no competing position to weigh.

FDA, *Questions and Answers on Unapproved Chelation Products*: **"FDA has never
approved any chelation product for OTC use for any health condition. All
FDA-approved chelation products require a prescription."**
FDA, *FDA warns consumers about potential health risks from using Thorne
Research's Captomer products*: **"FDA advises consumers to avoid all products
offered over the counter (OTC) for chelation. There are no FDA-approved OTC
chelation products."**

The approved disposition therefore represents **non-routine chelation requiring
clinical review**. It is explicitly **not** a claim that the labelled oral dose
is proven acutely toxic, and the reason semantics must not assert one.

**Binding invariants (tested):**

1. disodium edetate and calcium disodium edetate remain **distinct
   identities**, resolved by separate rules and never collapsed into a generic
   "EDTA" safety identity;
2. the generic token `EDTA` is **not** an alias of either identity;
3. both rules are authored for the **declared-active label role only** — EDTA
   declared as a formulation excipient is out of scope and is unaffected;
4. no toxicity assertion appears in the consumer copy;
5. the policy basis carries authoritative FDA sources and US jurisdiction.

### Final disposition table — 16 products

| DSLD | Product | Identity | Daily labeled dose | Previous state | Final state | Safety card | Quality score | Reason |
|---|---|---|---|---|---|---|---|---|
| 252358 | EDTA Disodium | disodium edetate | 500 mg | NOT_SCORED / blocked_by_completeness_gate | **BLOCKED** | visible | none (`display_100 = N/A`) | `NON_ROUTINE_CHELATOR` |
| 253339 | EDTA Disodium | disodium edetate | 500 mg | NOT_SCORED / blocked_by_completeness_gate | **BLOCKED** | visible | none | `NON_ROUTINE_CHELATOR` |
| 253350 | EDTA Disodium | disodium edetate | 500 mg | NOT_SCORED / blocked_by_completeness_gate | **BLOCKED** | visible | none | `NON_ROUTINE_CHELATOR` |
| 253357 | EDTA Disodium | disodium edetate | 500 mg | NOT_SCORED / blocked_by_completeness_gate | **BLOCKED** | visible | none | `NON_ROUTINE_CHELATOR` |
| 312449 | EDTA Disodium | disodium edetate | 500 mg | NOT_SCORED / blocked_by_completeness_gate | **BLOCKED** | visible | none | `NON_ROUTINE_CHELATOR` |
| 312450 | EDTA Disodium | disodium edetate | 500 mg | NOT_SCORED / blocked_by_completeness_gate | **BLOCKED** | visible | none | `NON_ROUTINE_CHELATOR` |
| 312451 | EDTA Disodium | disodium edetate | 500 mg | NOT_SCORED / blocked_by_completeness_gate | **BLOCKED** | visible | none | `NON_ROUTINE_CHELATOR` |
| 312452 | EDTA Disodium | disodium edetate | 500 mg | NOT_SCORED / blocked_by_completeness_gate | **BLOCKED** | visible | none | `NON_ROUTINE_CHELATOR` |
| 252426 | Calcium Disodium EDTA | calcium disodium edetate | 500 mg | NOT_SCORED / blocked_by_completeness_gate | **BLOCKED** | visible | none | `NON_ROUTINE_CHELATOR` |
| 253331 | Calcium Disodium EDTA | calcium disodium edetate | 500 mg | NOT_SCORED / blocked_by_completeness_gate | **BLOCKED** | visible | none | `NON_ROUTINE_CHELATOR` |
| 253335 | Calcium Disodium EDTA | calcium disodium edetate | 500 mg | NOT_SCORED / blocked_by_completeness_gate | **BLOCKED** | visible | none | `NON_ROUTINE_CHELATOR` |
| 253336 | Calcium Disodium EDTA | calcium disodium edetate | 500 mg | NOT_SCORED / blocked_by_completeness_gate | **BLOCKED** | visible | none | `NON_ROUTINE_CHELATOR` |
| 311259 | Calcium Disodium EDTA | calcium disodium edetate | 500 mg | NOT_SCORED / blocked_by_completeness_gate | **BLOCKED** | visible | none | `NON_ROUTINE_CHELATOR` |
| 311260 | Calcium Disodium EDTA | calcium disodium edetate | 500 mg | NOT_SCORED / blocked_by_completeness_gate | **BLOCKED** | visible | none | `NON_ROUTINE_CHELATOR` |
| 311261 | Calcium Disodium EDTA | calcium disodium edetate | 500 mg | NOT_SCORED / blocked_by_completeness_gate | **BLOCKED** | visible | none | `NON_ROUTINE_CHELATOR` |
| 311262 | Calcium Disodium EDTA | calcium disodium edetate | 500 mg | NOT_SCORED / blocked_by_completeness_gate | **BLOCKED** | visible | none | `NON_ROUTINE_CHELATOR` |

**Consumer-facing meaning (rendered from the sanctioned Safety-card copy layer):**

> **Chelating agent — not scored as a routine supplement.**
> Chelating agent (EDTA). FDA has not approved any over-the-counter chelation
> treatment; medically used chelation agents require clinical supervision. EDTA
> forms differ in their risks.

**Implementation.** Two policy entries in
`scripts/data/banned_recalled_ingredients.json`
(`BANNED_NON_ROUTINE_CHELATOR_EDETATE_DISODIUM`,
`BANNED_NON_ROUTINE_CHELATOR_CALCIUM_DISODIUM_EDETATE`), applied by the
idempotent
`scripts/audits/quarantine_triage_20260919/apply_edta_non_routine_chelator_policy.py`.

Two general, opt-in gate capabilities were added so this is a policy rather than
a product-id special case:

* `verdict_reason_code` — a rule may name its own machine reason code, so the
  exported `blocking_reason` states the policy instead of the registry tier;
* `role_scope_out_of_scope: "not_applicable"` — a rule authored for specific
  label roles treats another role as out of scope instead of an unresolved
  policy question. An out-of-scope occurrence leaves the product payload
  byte-identical to a label that never named the substance.

---

## 2. Botanical standardization constituents — DECIDED

**Policy:** `CONTAINED_CONSTITUENT_MODEL_APPROVED`.

The parent standardized botanical extract is the dose-bearing formulation
identity. A quantified constituent declared beneath it **remains visible**,
**retains its declared quantity and parent/source provenance**, is **not counted
as additional additive mass**, and **remains available to Safety matching** and
to evidence matching where appropriate.

Approved conceptual role: `contained_standardization_constituent`.

| DSLD | Product | Parent (dose-bearing) | Constituents |
|---|---|---|---|
| 216948 | PM Phytogen Complex | standardized Pueraria mirifica root extract 80 mg | Miroestrol 16 mcg, Isoflavonoids 16 mcg |
| 232718 | Longevity A.I. | Ashwagandha extract (std. 3% withaferin A) | Withaferin A 12 mg |
| 216776 | Herbal Complex | six `standardized <botanical> extract` parents @ 100 mg | Triterpene Glycosides 0.5 mg, Alkaloids 3 mg, Polyphenols 15/30 mg, Echinacosides 4 mg, Glycyrrhizin 1 mg, Oleuropein 6 mg |
| 44423 | Deglycyrrhized Licorice Root Extract | standardized Deglycyrrhized Licorice extract 250 mg | Glycyrrhizin 3 mg (<1%) |
| 77254 | Male Multiple | standardized American Ginseng 25 mg + standardized Korean Ginseng 25 mg | Ginsenosides 2.5 mg (10%), 2 mg (8%) |

**Structural criterion, not arithmetic equality.** Each child amount happens to
equal the parent's own stated percentage, but the rule does **not** depend on
exact arithmetic — labels legitimately carry rounding, `<`, `>`, ranges and
approximate standardization. The predicate keys on a clear parent/child
relationship plus a *standardized* botanical extract parent plus a compatible
constituent declaration, with an explicit negative control (a nested constituent
under a non-standardized extract stays scoreable). No product-ID allowlist.

**Safety preserved.** All five products keep their safety classifications: 232718
keeps `B0_WATCHLIST_SUBSTANCE`, 216948 keeps `B0_HIGH_RISK_SUBSTANCE`. Identity
remediation does not bypass Safety.

**Terminology decision (recorded).** The runtime name for this role is
`standardization_marker`. The preferred clinical wording is
`contained_standardization_constituent`; the literal enum rename is recorded as
a **non-blocking technical-debt item** rather than performed here, because it
reaches the cleaner's row-role enum, the form-fallback audit data, the replay
classifier and six test modules. For this release, `standardization_marker`
means a **contained quantified constituent** of a dosed parent extract — not an
inert analytical marker.

---

## 3. Discrete-enzyme formulation — DECIDED

**Policy:** `NOT_INDIVIDUALLY_RATED_APPROVED`.

Removal of generic collapsed `digestive_enzymes` evidence inheritance is
approved. There is no generic evidence transfer from a multi-enzyme formulation
to unrelated discrete identities (protease, lipase, amylase, lactase,
serrapeptase, alpha-galactosidase, and other individually modelled enzymes).

Approved clinical meaning: **no qualifying enzyme-specific formulation evidence
has been applied.**

Approved consumer presentation: **"Not individually rated"** — *we don't
currently apply enzyme-specific formulation evidence to this ingredient.*

Internal semantics: `formulation_evidence_state = NOT_INDIVIDUALLY_RATED`,
`formulation_credit = none`, `formulation_penalty = none`.

**No new scoring mechanism was invented.** The Formulation pillar already owns
this state: an unrated form (`iqm_form_quality_assessed_count == 0`) receives
the multi/prenatal panel's own neutral floor
(`_unrated_form_neutral_ratio`) together with the reason *"Ingredient-form
quality is not rated in PharmaGuide's current data."* — i.e. **not evaluated**,
not "average", and not zero. No new denominator or normalisation method was
introduced. Once qualifying direct evidence exists for a discrete enzyme, the
row becomes rateable through the normal rules; this is **not** a permanent
exemption class.

**Measured effect (frozen-corpus A/B, at the remediation tip).** 28 score
changes, all inside the discrete-enzyme / probiotic-evidence family and all
traced to that single evidence-transfer removal; 0 Safety-field changes;
0 quarantine exits; 1 new quarantine (`269360` Serrapeptase, whose printed panel
declares 40,000 SPU — restored by the source-resolution phase; its residual
quarantine is an identity-scoring condition, not a missing dose). The changes
come from **preventing unsupported evidence transfer**, not from losing
legitimate evidence.

---

## 4. Beta-carotene / Vitamin-A UL — DECIDED (closed)

**Policy:** `PREFORMED_VITAMIN_A_ONLY`.

Only **preformed** vitamin A (retinol, retinyl esters, and other applicable
preformed forms) participates in the preformed Vitamin-A UL. Beta-carotene and
other provitamin-A carotenoids contribute **0** to that UL.

The resolved Bulk 1340 products supplying approximately 6.0–6.834 mg
supplemental beta-carotene receive **no retinol-UL penalty** and **no high-dose
beta-carotene Safety warning** at those resolved doses.

Verified intact: `rda_optimal_uls.json` declares *"UL applies to preformed
vitamin A only, not beta-carotene"*; the dose lane resolves a provitamin-A row
to `beta_carotene_no_established_ul` /
`provitamin_a_carotenoid_no_established_ul` in `_NO_UL_REASONS`; the vitamin-A
pregnancy interaction gate excludes `beta_carotene` / `mixed_carotenoids`.
Regression coverage: `test_ul_gate_eligibility.py`,
`test_phase3_clinical_policy_20260921.py`.

### Future stack-aware rule — recorded, not a Phase-3 blocker

Dr. Pham additionally recommended a future **stack-aware, personalized**
beta-carotene rule: `< 15 mg/day` → no high-dose beta-carotene penalty;
`>= 15 mg/day` + current/former smoker or significant asbestos exposure →
personalized CAUTION; `>= 20 mg/day` + those risk factors → stronger CAUTION;
`>= 20 mg/day` with risk status unknown → contextual high-dose card.

**15 mg/day is a PharmaGuide operational threshold, not an official UL** — there
is no established beta-carotene UL. This is **not** a Phase-3 release blocker
(the Phase-3 products are ~6–6.8 mg/day); it is recorded as the durable
clinical/Safety specification for a future stack-Safety phase.

---

## 5. Validation and replay

* **Static source-of-truth audit:** `scoring-static` → **OK, 0 findings**.
* **Registry policy audit:** `audit_banned_recalled_accuracy.py` →
  **Status: pass**, 0 errors, 0 warnings, `missing_cui_annotations=0`.
* **Targeted suites:** 519 passed / 7 skipped over the Phase-3 clinical policy,
  banned/recalled schema, active-role gate, strict match, class recognition,
  collision corpus, alias coverage, identifier integrity, active-parity,
  vocabulary contracts, safety-policy readiness, safety copy, digestive-enzyme
  identity repair, standardization-marker generalization, the 2026-09-19
  clinical sign-off fixes, UL gate eligibility, and the Phase-3 source
  correction/count-basis suites.
* **Fast tier:** **15,928 passed / 0 failed / 196 skipped / 0 errors**
  (4:12). See `FAST_TIER_CLINICAL_POLICY_20260921.md`.
* **Frozen-corpus replay** (base `b4ae13f6` = `origin/main` at session start):
  15,414 row-level records per arm with **0 representation changes** and
  0 crashes; 15,412 scored records per arm with **0 score changes**, 16
  conclusion changes, 16 Safety changes, **0 quarantine exits, 0 quarantine
  entries** and **0 changes outside the approved policy family**. The 16
  changed ids are exactly the standalone oral EDTA set. Evidence:
  `PHASE3_CLINICAL_ROWLEVEL_REPLAY_b4ae13f6_20260921.json`,
  `PHASE3_CLINICAL_SCORED_REPLAY_b4ae13f6_20260921.json`.
* **Per-product policy proof:** `EDTA_POLICY_SHIPPING_PROOF_20260921.json`
  (24 products, 0 failing) runs the real `validate_export_contract` ship gate
  and the real Safety-card content layer.

---

## 6. Release sign-off

| | |
|---|---|
| **Clinical reviewer** | **Dr. Pham** |
| **Team** | **PharmaGuide Clinical Team** |
| **Decision date** | **2026-09-21** |
| **Phase** | **Phase 3** |
| **Policy decisions** | **Approved as documented (§1–§4)** |
| **Overall** | **APPROVED WITH SPECIFIED PRODUCTS HELD** |

**APPROVE WITH SPECIFIED PRODUCTS HELD is permitted**, and is what this record
uses. Approval does not require every product to receive a score: an explicit
conservative hold is a complete disposition. `231334` / `231335` / `263865` have
no authorable printed denomination and remain explicitly withheld; the
intentional non-scoreable and Safety-card/no-score products remain in their
decided states. No product was reopened to increase catalog coverage.
