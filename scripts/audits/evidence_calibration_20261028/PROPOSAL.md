# Evidence calibration — measured proposal for Sean (October 28, 2026)

Branch `claude/serene-dubinsky-479574` on `e6885790d` (origin/main). Config `1.31.0-evidence-no-automatic-exceptional`, unreleased. Not merged; Sean's approval is required. Receipts: `~/pg_quality/evidence_calibration_20261028/`.

The requirement is Dr Pham's signed scientific framework (October 28, 2026), as relayed. The bands are PharmaGuide editorial ranges, not a GRADE conversion. I found no copy of the signed band table in the repository.

## 1. Policy, old and new (one owner: `generic_evidence._primary_mass_floor`, magnitudes in `quality_score.json`)

Generic, sports and fiber Evidence: public = raw / 18 × 20 (immune reference 17).

| Path | Old (raw → public) | New | Why |
|---|---|---|---|
| Brand marker (`branded-rct` or `BRAND_` id) or ingredient allowlist (vitamin D, folate, psyllium, creatine, EPA/DHA) + meta/multi-RCT, positive_strong | 18 → 20.0 | strong floor 14 → 15.6 | A name is not a certainty judgement; one or two small manufacturer trials reached 20 |
| Same, single RCT | 17 → 18.9 | moderate floor 11 → 12.2 | One trial is not near-full credit |
| Meta/multi-RCT, positive_strong, prominent row | 14 → 15.6 | unchanged | Strong band |
| Single RCT / clinical strain, positive_strong | 11 → 12.2 | unchanged | Moderate band |
| Essential-nutrient authority | 10 → 11.1 | unchanged | Nutrition band |
| positive_weak / mixed | 10.4 / 7.3 | unchanged | Limited band |
| Exceptional 19–20 via a floor | automatic | **no automatic floor** | See below; the additive multi-ingredient sum is unchanged (decision 6) |

**No automatic exceptional floor.** No registry records a reviewed certainty judgement for a whole evidence body (no certainty, grade, bias or independence fields; funding appears on 2 of 181 contexts). Any automatic 19–20 rule would therefore be a proxy. That includes the brand marker, the allowlist and a trial count: an earlier candidate on this branch used "three approved trial families", which Sean rejected. So no automatic floor exceeds the strong base. **Decision 1** below proposes how 19–20 can be earned.

Unchanged: Dose, the 11.4 Dose neutral, Transparency, Verification, safety, nutrition panels (multi/prenatal, B-complex) and probiotic/omega Evidence. Completed zeros and unfinished assessments keep their distinct `display_state`, and the app hides the number for unfinished states.

## 2. Measured impact (vs unchanged main)

- **Cohort** (205 raw labels: original 20, every driver of the old 18/17 floors, strong/moderate/weak/mixed/authority/pipeline/zero strata, contradictory-trial and exact-preparation cases, other-module controls; `replay.py` freeze-raw → snapshot → compare). 59 moved, all down, Evidence only. Every control was unchanged.
- **Whole corpus, scorer only** (15,149 scored). 803 moved down, 0 up. No change to other pillars, status, safety status or result state. 788 went from 19–20 to 15–18 and 15 from 18.9 to 12.2. 344 tier changes: Very good→Good 137, Excellent→Very good 110, Good→Needs improvement 50, Exceptional→Excellent 43, Needs improvement→Poor 4. By driver: vitamin D3 454, creatine 133, Sensoril 36, Suntheanine 34, KSM-66 28, Testofen 18, psyllium 18, Pycnogenol 13, Kaneka 12, 5-MTHF 11, UC-II 9, and 37 across 11 other brands.
- **Final code = measured code.** The run was at `37d74d5b1`. Later commits only narrowed or removed the 19–20 route. That route never fired on any record: across all 210 records, no condition has more than one approved positive RCT family, and 0 of 37,330 corpus matches are unregistered. The result is now trivially identical, because the route no longer exists. Receipt: `corpus/final_sha_equivalence.txt`, which also records my earlier mis-statement that the gate was "strictly narrower".

## 3. Verifications Sean asked for

**Strong ingredients keep strong credit.** Creatine (270330, 253769), psyllium (82099), vitamin D3 (26743, 261951), KSM-66 (318247, 253114), Sensoril (286869) and Suntheanine (25543) all sit at 15.6, in the strong band, with "driven by the primary ingredient" copy. Evidence and Dose stay independent. A label without a claim keeps its record's credit, while claims about other purposes are still blocked by the existing purpose check. Clinical-lane judgement calls:
- Creatine plausibly merits 19–20 once a body determination exists.
- The KSM-66 and Suntheanine bodies (two small trials) sit generously even at strong.
- INGR_VITAMIN_D3 is typed positive_strong, but its only reviewed context is mixed/null.

**5-MTHF.** The remaining 12.2 comes from INGR_FOLATE_MTHF (`rct_single`, positive_strong). That triggers the moderate *clinical* floor. But the record's support is pharmacokinetic and biomarker (folate status, unmetabolized folic acid, infant growth equivalence), as its own notes say, and its only context has surrogate outcomes. Proposed for the clinical lane's file: classify the record as reference/biomarker-only. Measured: all 11 products go 12.2 → **11.1** through the existing folate or B12 nutrition-authority floor (`evaluated_authority`), −1.1 each, no tier changes. No clinical outcome is claimed.

**Four products into Poor** (BSN Re-Built Mass XP 244288, 211339, 220208, 83268). Evidence went 20 → 15.7: the creatine allowlist floor is gone, and the existing additive pipeline now sets it ("not yet reviewed"; uncurated records remain). The Poor tier mainly reflects Dose 0. **Magnesium check (pre-existing, Dose/safety owner):** the label prints Magnesium 540 mg per 255 g serving with no form. No magnesium salt appears among the other ingredients (whey, casein, starches, grain blend, cocoa), so it is most likely food-matrix magnesium. `rda_optimal_uls.json` scopes the 350 mg magnesium UL as `supplemental_only` ("not food sources"), yet the Dose safety owner records `confirmed_over_threshold` at 154% and sets Dose to 0. The frequency also shows as defaulted although the directions say one serving daily. Census: 232 products with a confirmed magnesium exceedance; 17 declare no magnesium source (10 Re-Built Mass XP flavours plus e.g. 273823, 29043), listed in `magnesium_ul_census.txt`. Not changed here.

## 4. Decisions for Sean

1. **Approve 1.31.0** (no automatic floor above strong). For 19–20, propose a recorded clinician determination per record and purpose. It would be a new persisted field on the existing clinical-review object, which is Sean's decision. It would state certainty, directness, consistency, independent corroboration (including funding and independence), population and purpose, and could rest on a high-quality systematic review or on assessed independent trials, with no count rule. The scorer would read only that determination.
2. **5-MTHF record** → reference/biomarker-only (clinical lane), 12.2 → 11.1 on 11 products.
3. **Magnesium supplemental-UL scope** → Dose/safety owner review of the 17 undeclared-source products.
4. **Omega-3 (separate proposal; nothing implemented here).** Re-cite `omega_reviewed_weak` from the heart-outcome reviews to EFSA NDA (2010) *Dietary Reference Values for fats*, doi:10.2903/j.efsa.2010.1461. That is a dietary reference (AI 250 mg EPA+DHA/day for adults; +100–200 mg DHA in pregnancy and lactation), not a US RDA and not clinical-event evidence. The 10.4 itself is editorial policy in `quality_score.json`, not an EFSA number. Keeping 10.4 moves no scores. The disclosure rule (any trustworthy disclosed EPA and/or DHA amount) would lift 84 adult products from 0 to 10.4 (42 combined-only, 34 DHA-only, 8 EPA-only; no prenatal or child labels; 53 tier changes, all up). Each needs review for identity, population, quantity and nutritional-vs-clinical basis: `omega_84_review.csv`. Also review 82325 (phosphatidylserine + DHA). Triple Omega 179650/302769 disclose only a mixed 434 mg total omega-3 (including flaxseed ALA), so 0 stays correct.
6. **Additive multi-ingredient sum (open).** Removing the floors leaves the existing additive pipeline unchanged: four accepted Evidence owners at the 7-point per-ingredient cap sum to 17.5 raw (19.4/20), plus up to 0.5 depth bonus (20/20), with no body-level determination. No product reaches 19–20 this way in the measured corpus. Capping it would be a new scoring policy, so it is Sean's decision; this PR documents the scope rather than enforcing a cap (raised by CodeRabbit on PR #274).
5. **App Evidence badge** → app/integration owner (`lib/core/scoring/v4_pillars.dart::statusForPillar` shows "Strong" for nutrition-authority panels); note: `app_evidence_badge_handoff.md` in the shared notes folder.

## 5. Validation (final commit)

- Fail-first for every changed rule (`fail_first.log`). Focused floor, magnitude, config-registry, archetype and generic-evidence files pass. Raw contract canaries 33/33 (3 refreshed with cause in the manifest changelog).
- Owner/consumer slice and the slow canary files: see the CI and local results recorded in the PR.
- **Pre-existing, owner-assigned, not hidden:**
  - `test_v4_gate_canary_diversity[230149]`: a slow-profile raw-fixture pin stale since `49b61f37d` (bisected: passes at `35c306e85`). Repinned with cause.
  - 10 stored-corpus canary nodes (gate/cross-module files): registered preparation-artifact nodes (`test_profiles.PREPARATION_ARTIFACT_NODES`) reading pre-rebuild artifacts. They fail identically on main and are checked after the final rebuild.
  - 7 `test_e1_2_2_preflight_invariant` nodes: fresh raw rebuilds vs the dated October 18 baseline (`release_artifact_paths.canary_baseline_dir`). They fail identically on main, and the base and candidate rebuilds differ only in Evidence fields. Drifts: new low additive warnings (306237, 246324), changed CBD penalty text (246324), changed penalties (176872), and **a lost "Vitamin D / pregnancy" interaction warning on 176872, which needs the safety owner**. Refreshing that baseline is a reviewed capture for the final combined qualification.
  - Canaries 1002, 1036 and 35491 have no raw label in the staging dataset, so they wait for the final rebuild.
- Two fresh-context reviews of the earlier gate. All their findings were fixed, then the gate was removed.
