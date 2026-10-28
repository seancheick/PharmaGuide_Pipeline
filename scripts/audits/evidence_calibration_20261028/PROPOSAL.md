# Evidence calibration — measured proposal for Sean (October 28, 2026)

Branch `claude/serene-dubinsky-479574`, candidate `5d02482d5` (rule `37d74d5b1`, review fix `67119326f`, pins `5d02482d5`) on `e6885790d` (origin/main). Not merged. Config `1.31.0-evidence-replicated-body`, pending Sean's decision.

Source of the requirement: Dr Pham's signed scientific framework (October 28, 2026), as relayed by the requesting session. The band text below is from that relay. I found no copy of the signed band table in the repository or the state folders; please confirm the bands against the signed original.

## 1. Bands → current generic floors

Generic, sports and fiber Evidence: public = raw / 18 × 20 (immune reference 17). Bands are PharmaGuide editorial ranges, not a GRADE conversion.

| Band (/20) | Current path (raw → public) | Fits? | Proposal |
|---|---|---|---|
| Exceptional 19–20 | branded (`branded-rct` level or `BRAND_` id) or ingredient allowlist (vitamin D, folate, psyllium, creatine, EPA/DHA) + meta/multi-RCT + positive_strong: 18 → 20.0 | No: brand/name, not evidence body | Require a replicated reviewed body (section 2), else the strong floor |
| Strong 15–18 | meta/multi-RCT, positive_strong, prominent row: 14 → 15.6 | Yes | Keep |
| Strong (top) | branded/allowlist single RCT: 17 → 18.9 | No: one trial near-full | Retire; one trial is the moderate floor |
| Moderate 11–14 | single RCT/clinical strain, positive_strong: 11 → 12.2 | Yes | Keep |
| Essential nutrient 10–12 | nutrition authority: 10 → 11.1 | Yes | Unchanged |
| Limited 6–10 | positive_weak: min(base×0.85, 11×0.85) = 9.35 → 10.4; mixed: 6.6 → 7.3 | Yes (10.4 sits at the limited/moderate edge) | Keep |
| Preliminary 1–5 | pipeline only (non-prominent rows; single ingredient tops at 7.5 raw = 8.3) | Yes | Keep |
| Completed zero | evaluated_null / no_qualifying / no_assessable: 0 with `display_state` assessed/not_applicable | Yes | Unchanged |
| Unfinished | gap states keep `display_state` `not_yet_reviewed` / `applicability_unestablished`; the app branches on it (`lib/core/scoring/v4_pillars.dart`) | Yes, as a display state | Unchanged; returning a null number would be a public-contract change for Sean |

Corpus census (stored scored outputs, discovery only): the additive pipeline never reaches 19+; every exceptional score came from the 18-raw floor.

## 2. Branded automatic floor: reachable from one small trial — confirmed

`_primary_mass_floor` elevated on study type + brand marker only; enrollment, funding and replication were never read. Examples from `backed_clinical_studies.json`:

- BRAND_ASTAREAL: `rct_multiple` with one PMID (36 men RCT + 30-woman open-label; both contexts mixed) → 20.0/20.
- BRAND_KSM66: two Ixoreal-supplied trials, 124 participants → 20.0/20.
- BRAND_COGNIZIN, BRAND_CYNATINE_HNS, BRAND_MEGASPORE_BIOTIC, BRAND_RELORA: single trials (n 40–112) → 18.9/20.
- INGR_VITAMIN_D3 (allowlist): its only context is a respiratory-infection meta-analysis with mixed/null results, pending clinical review → 20.0/20 on 459 products.

No record carries structured funding or independence fields (2 of 181 contexts mention funding).

Implemented rule: the 18-raw tier needs the record's clinician-approved contexts (`context_accepted_for_scoring`) with primary patient-important outcomes to show three consistent independent RCT families for one condition and no contradictory or unlinked pooled family, decided by the existing probiotic owner `_consistency_from_contexts`. Brand markers and the allowlist are gone. Today 0 of 210 records pass, so the exceptional tier is empty until the clinical lane records linked trial families.

## 3. Measured impact

Two measurements. Both compare unchanged main `e6885790d` with the candidate. Receipts are in `~/pg_quality/evidence_calibration_20261028/`.

**A. Category-balanced frozen cohort (`replay.py freeze-raw` → `snapshot` → `compare`).** 205 raw labels: the original 20; up to 3 products for every record that drove the 18 or 17 floor; strong, moderate, weak, mixed, authority, pipeline and zero-state strata for generic, sports and fiber; contradictory-trial records (BCM95, Magtein, Sunfiber, Sytrinol, MediHerb silymarin, OptiMSM, Niagen, Ester-C, Theracurmin, peppermint, echinacea); exact-preparation cases (generic ashwagandha vs KSM-66, curcumin forms); and controls for multi/prenatal, omega, probiotic, B-complex and not-scored products. Clean → enrich → score ran with each checkout's own modules.

- 59 of 205 moved, all down, Evidence pillar only. No other pillar or status changed. The final commit reproduces the first candidate exactly (empty compare).
- 52 went exceptional → strong (20.0 → 15.6). The exceptions are UC-II No. 7 (20 → 17.1, where the additive pipeline already exceeds the floor) and an immune elderberry/vitamin D gummy (20 → 16.5, reference 17).
- 7 went strong → moderate (18.9 → 12.2): Relora ×2, PureWay-C ×2, 5-MTHF ×3.
- Unchanged: all contradictory-trial, exact-preparation (generic ashwagandha, curcumin), nutrition-authority, moderate/weak/mixed floor, pipeline, zero-state and other-module controls.
- Original 20: three moved. Creatine 270330 went 93.0 → 88.6 (Excellent → Very good); this was the "creatine 20/20 control" and it moves by design (section 4, decision 1). Vitamin D3 261951 went 82.1 → 77.7 (Very good → Good). The other 17, including the completed zeros (CLA, glutamine) and the incomplete zeros, are unchanged.

**B. Whole corpus, scorer only.** Every stored enriched product (15,437; 15,149 scored) went through each checkout's `build_scored_artifact`. These inputs predate PR271's enrich changes, which is the same for both sides; this is a delta measurement, not a release artifact.

- 803 moved, 0 up, 0 changes to other pillars, status, safety status or Evidence result state.
- Band transitions: 788 exceptional → strong, 15 strong → moderate. Evidence deltas: −4.4 (728), −3.5 (42, immune reference), −6.7 (15), −1.8 to −4.3 (18; capped or pipeline-supported products).
- Tiers: 344 changes. Very good → Good 137; Excellent → Very good 110; Good → Needs improvement 50; Exceptional → Excellent 43; Needs improvement → Poor 4.
- By driving record: INGR_VITAMIN_D3 454 (197 tier changes), INGR_CREATINE_MONOHYDRATE 133 (52), BRAND_SENSORIL 36, BRAND_SUNTHEANINE 34, BRAND_KSM66 28, BRAND_TESTOFEN 18, INGR_PSYLLIUM_HUSK 18, BRAND_PYCNOGENOL 13, BRAND_KANEKA_UBIQUINOL 12, INGR_FOLATE_MTHF 11 (−6.7), BRAND_UCII 9, then 37 more across 11 BRAND_ records (Lutemax, BioCell, TamaFlex, Affron, Shoden, AstaReal, PureWay-C, Relora, Mitopure, Zynamite, LJ100).
- Evidence band census of scored products. Before: exceptional 2,245, strong 2,588, moderate 1,695, limited 2,355, preliminary 102, zero 6,164. After: exceptional 1,457, strong 3,361, moderate 1,710, other bands unchanged. Every remaining 19–20 is a multi/prenatal (1,332) or B-complex (125) nutrition-authority panel; no generic, sports or fiber product reaches 19–20 (section 4, decision 3).

**Tests.** Fail-first: 7 changed-rule tests failed on main, plus 2 more from the review fix (`fail_first.log`). Focused: the floor, magnitude and config-registry files pass. Owner/consumer slice: 85 files, 3,525 passed. The one failure, `test_v4_gate_canary_diversity[230149]` (68.5 → 65.5), fails identically on the untouched base checkout while main CI is green on that SHA, so it is pre-existing and local. Raw canaries: 33/33 after refreshing 245156, 298102 and 306237 (exactly −4.4 Evidence each; main passes 33/33). Fresh-context review: three gate gaps found. Two are fixed in `67119326f` (registry-only contexts, direct identity scopes); one is decision 4.

## 4. Decisions for Sean

1. **Approve the rule (config 1.31.0)?** Brand markers and the allowlist no longer lift Evidence; one trial is a moderate floor; 19–20 needs a replicated reviewed body. Consequence: 0 records qualify today, so 788 products lose 4.4 points (creatine and vitamin D included) until the clinical lane records three clinician-approved, independent, consistent trial families for one condition on a record. Creatine's evidence body is plausibly exceptional. Our registry holds one approved pooled meta-analysis context for it, and by the existing probiotic owner rule a pooled record earns no replication credit until its trials are linked. Alternative for Dr Pham: let a clinician-approved meta-analysis of ≥3 RCTs with consistent direction count as replicated. That is a policy change to the shared consistency owner and would also affect probiotics.
2. **Enrollment in the floors (measured, not implemented).** The strong/moderate floors ignore enrollment. Applying the existing bands (×0.8 for n < 200, ×0.6 for n < 50) would move about 420 more products, for example INGR_TURMERIC (n = 90, 119 products at 15.6) and BRAND_KSM66 (n = 124), and needs a fail-closed rule for the 384 floor products whose record has no enrollment. That is a policy owner decision.
3. **Nutrition panels at 19–20.** Multi/prenatal and B-complex complete panels earn a native 20 from nutrition authority (1,457 products), while the framework puts essential-nutrient nutritional credit at about 10–12. This was out of scope (kept unchanged as instructed) but conflicts with the bands.
4. **Purpose-scoped replication (Dr Pham).** The gate accepts replication for any condition in the record's approved contexts, while the record match itself is purpose-checked. Should replication also have to match the label's claimed purpose, as the probiotic path does? No product is affected today.
5. **Record follow-ups for the clinical lane, not changed here:** INGR_VITAMIN_D3 is labelled positive_strong systematic_review_meta, but its only context (respiratory infection) is mixed/null and pending review; it still floors 454 products at 15.6. BRAND_ASTAREAL is `rct_multiple` with one PMID. Bands at the edges: positive_weak strong-design floors land at 10.4 (between limited and moderate).

Not done: no merge, no corpus rebuild, no export or app check. Rebase and remeasure after `claude/held-source-closure` merges.
