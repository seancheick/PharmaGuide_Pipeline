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
