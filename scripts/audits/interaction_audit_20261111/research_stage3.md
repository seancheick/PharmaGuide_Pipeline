# Stage 3 receipts (2026-11-11)

Agent review; no clinician has reviewed these entries yet. Every row goes in the PharmD packet.

## Batch 1: intervals no source supports (`apply_stage3_held_intervals.py`)

Gate: `test_timing_rules.py::TestHeldIntervalsStayUnpublished`. No curated pair or interaction-rule text may
restate an interval that `timing_rules.json` holds (not `verified`). The control proves it reports a restated
interval and ignores other pairs and number-free wording.

| Entry | Before | After | Source read 2026-11-11 |
|---|---|---|---|
| `SSI_IRON_CALCIUM` management | "at least 2 hours apart" | "at different times of the day" | ODS Iron HP fact sheet: experts suggest "individual calcium and iron supplements at different times of the day"; ODS Calcium HP sheet gives no iron interval. Held: `timing_iron_calcium_separate` (Hallberg 1991/1992 test no interval) |
| `DSI_LEVOTHYROXINE_SOY` management | "by at least 4 hours" | different time; ask how far apart | Messina & Redmond 2006 (PMID 16571087) supports the interaction and states no interval. Held: `timing_thyroid_med_soy_separate` |
| `DSI_LEVOTHYROXINE_SOY` source_urls | ODS Soy HP URL | removed | The page returns 404 "File Not Found" (browser, 2026-11-11). PMID 16571087 remains |
| `RULE_IQM_PSYLLIUM_DIABETES` diabetes condition + three hypoglycemic sub-rules, action | "Separate … by at least 2 hours" | talk to prescriber/clinician; monitor glucose | No source states a psyllium–diabetes-medicine interval. MedlinePlus psyllium gives 3 h only for digoxin, salicylates and nitrofurantoin, and otherwise says the doctor may change doses or monitor. Severity (`monitor`) unchanged |

Kept by owner decision: magnesium + levothyroxine "at least 4 hours" in `DSI_LEVOTHYROXINE_MAGNESIUM` and the
`RULE_IQM_MAGNESIUM_HYPERTENSION` thyroid sub-rule. Sean approved "one interval everywhere: at least 4 hours" on
2026-10-01 (D27, `scripts/audits/levo_grapefruit_severity_20261001/research.md`), extrapolating the label's interval
for magnesium-containing antacids; `test_levothyroxine_grapefruit_reconciliation.py` locks it. The gate lists it in
`APPROVED_HELD_INTERVALS`. Open for Sean: the timing card `timing_thyroid_med_magnesium_separate` still says it waits
for "an interval source or a clinician decision", although D27 is that decision for the pair text. Publish the card
with the D27 basis, or keep it held?

Kept, sourced: the levothyroxine 4 h instruction for calcium carbonate and iron (ODS Calcium and Iron sheets cite
the FDA label), so the app's timing tests that pin "Keep calcium at least 4 hours away from levothyroxine" are correct.

Verifiers on the final changed set: `verify_all_citations_content.py --changed-since HEAD` 1 match, 0 mismatch;
`verify_interaction_rules_citations.py --strict --changed-since HEAD` PASS, 1 on-topic. (An earlier run that also
covered the magnesium rule flagged PMID 25864370 on its heart_disease sub-rule; read: that claim is magnesium
accumulation with renal impairment, which the dialysis paper covers. On topic.)

Found, not fixed in this batch (research step):
- `RULE_IQM_PSYLLIUM_DIABETES` cites only the NCCIH "Diabetes and Dietary Supplements" page, which never mentions
  psyllium (searched the full page text). Its glucose-lowering claim and "fiber delays absorption of … metformin and
  sulfonylureas" mechanism need a real source; until then the rule's `evidence_level: established` overstates it.
- MedlinePlus psyllium names digoxin (3 h). No curated psyllium–digoxin pair exists.

## Batch 2: label citations that do not exist (`apply_stage3_label_citations.py`)

A scan of all 72 DailyMed setids cited in `scripts/data` against the v2 SPL service (2026-11-11; a known label returned 200
in the same run) found 11 that return 404. Six follow a sequential-hex pattern (`a6b7c8d9-e0f1-4a2b-…`, `b7c8d9e0-…`,
`c2d3e4f5-…`, `d3e4f5a6-…`, `e4f5a6b7-…`, `f5a6b7c8-…`) and look fabricated; the rest look like retired labels. Only the
citations change. Each replacement label was read and its passage quoted:

| Entries | New label | Passage (label text) |
|---|---|---|
| `DDI_DIGOXIN_AMIODARONE` | LANOXIN tablets d91e3646 (ADVANZ, 2025-01-09) | interaction table: "Amiodarone 70% … Measure serum digoxin concentrations before initiating concomitant drugs" |
| `DDI_DIGOXIN_DIURETICS` | LANOXIN tablets d91e3646 | "hypokalemia, hypercalcemia, or hypomagnesemia may predispose to digoxin toxicity" |
| `DDI_THEOPHYLLINE_CIPRO` | CIPRO 888dc7f9 (Bayer, 2026-03-04) | "Serious and fatal reactions have been reported in patients receiving concurrent administration of CIPRO and theophylline" |
| `DSI_FLUOROQUINOLONES_IRON`, `_MAGNESIUM`; `RULE_IQM_IRON_HYPERTENSION`, `RULE_IQM_MAGNESIUM_HYPERTENSION`, `RULE_IQM_CALCIUM`, `RULE_IQM_ZINC` fluoroquinolone sub-rules | CIPRO 888dc7f9 | "2 hours before or 6 hours after … magnesium, calcium, aluminum, iron, or zinc" |
| `DDI_ANTICONV_OCP` | TEGRETOL 8d409411 (2026-08-21) | "may render the contraceptives less effective … Alternative or back-up methods of contraception should be considered" |
| `DDI_PHENYTOIN_VALPROATE` | DEPAKOTE 08a65cf4 (AbbVie, 2026-04-14) | "Valproate displaces phenytoin from its plasma albumin binding sites and inhibits its hepatic metabolism" |
| `DDI_BETABLOCKER_VERAPAMIL` | verapamil ER af1249b0 (repackager; no brand label on DailyMed) | "additive negative effects on heart rate, atrioventricular conduction and/or cardiac contractility" |
| `DDI_STATIN_GEMFIBROZIL` | gemfibrozil cf32b795 (repackager; no brand label on DailyMed) | "The concomitant administration of gemfibrozil with simvastatin is contraindicated" |

Verifiers on the changed set: content 2 match, 0 mismatch; rules strict PASS. Its two suspects were read and are on topic
(PMID 21452290 is the AASLD hemochromatosis guideline on the iron liver_disease sub-rule; PMID 25864370 as above).

Label-backed severity questions for the PharmD (not changed here):
- `DDI_STATIN_GEMFIBROZIL` is Moderate (caution). The gemfibrozil label contraindicates simvastatin and says combined
  therapy with any HMG-CoA reductase inhibitor "DOES NOT OUTWEIGH THE RISKS OF SEVERE MYOPATHY, RHABDOMYOLYSIS, AND
  ACUTE RENAL FAILURE". Possible under-warning.
- `DDI_THEOPHYLLINE_CIPRO` is Moderate. The CIPRO label reports serious and fatal reactions and says to monitor levels
  "if concomitant use cannot be avoided". Possible under-warning.

Verifier gap: neither citation verifier resolves DailyMed setids, which is how fabricated label links reached the data.
