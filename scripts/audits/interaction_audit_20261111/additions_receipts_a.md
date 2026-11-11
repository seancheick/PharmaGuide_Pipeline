# Proposed interaction additions (batch A) — for PharmD review

Prepared 2026-11-11, read-only research against worktree `/Users/seancheick/worktrees/dsld-interaction-baseline`.
Nothing was edited or committed. Agent research, not clinician review. Every JSON field marked
`[J]` in the notes under each record is a judgment call for the reviewer.

Identity checks run once for the batch (RxNav `historystatus.json`, all `Active`, tty `IN`):
isotretinoin 6064, levodopa 6375, carbidopa 2019, digoxin 3407, alendronate 46041, risedronate 73056,
ibandronate 115264, zoledronic acid 77655.
Agent2 CUIs taken from the existing repo owners (`ingredient_quality_map.json` and existing curated
records), not re-verified against UMLS in this pass: licorice C0086555, vitamin_a C0042839,
iron C0302583, calcium C0006675, psyllium C0033979.

---

## 1. Digoxin + glycyrrhizin-containing licorice (DGL excluded)

### Existing coverage
- No curated Med-Sup pair. Digoxin appears only in `DSI_DIGOXIN_SJW` (batch_critical_2026_05.json) and Med-Med pairs.
- Licorice curated pairs: `DSI_ANTIHYP_LICORICE` (class:antihypertensives, Major), `DSI_CORTICO_LICORICE` (class:corticosteroids, Moderate).
- Profile rule `RULE_IQM_LICORICE_HYPERTENSION`: drug_class_rules only `antihypertensives`. Its `heart_disease` condition sub-rule mentions digoxin in the action text ("especially if combined with digoxin..."), but that fires only for the heart_disease condition, not for a digoxin user without that condition. Its sources (PMID 28981338, a case-report table that excluded drug-herb interactions; PMID 21954510, no abstract) do not support a digoxin claim.
- `class:cardiac_glycosides` exists in drug_classes.json (8 RxCUIs incl. digoxin 3407, digitoxin 3403; ATC C01AA). Its rule class is used by senna, cascara, aloe ferox, ginseng — not licorice.
- DGL: separate entry `dgl_deglycyrrhizinated_licorice` (botanical_ingredients.json, CUI C0697105, `canonical_id: null`), so it should not resolve to canonical `licorice`. Its own notes say residual glycyrrhizin <3% "does not establish elimination of mineralocorticoid effects".

Verdict: gap. Not a duplicate.

### Sources
- LANOXIN tablet label, setid `d91e3646-4c63-4512-ab22-db39c085c4dc` (ADVANZ, Jan 2025), section 5.3: "hypokalemia, hypercalcemia, or hypomagnesemia may predispose to digoxin toxicity. ... Assess serum electrolytes and renal function periodically." The label does not mention licorice.
- Penninkilampi 2017 meta-analysis, PMID 28660884 (already cited in repo): "chronic licorice ingestion is associated with an increase in blood pressure and a drop in plasma potassium, even at modest doses." Inclusion: products with at least 100 mg glycyrrhizic acid daily.
- Harada 2002 case report, PMID 12566654 (Cardiology 98:218): title only, no abstract: "Congestive heart failure caused by digitalis toxicity in an elderly man taking a licorice-containing chinese herbal laxative." Full text not read; the hypokalemia mechanism is not confirmed from the abstract layer.
- Miller 1998 review, PMID 9818800: "Kyushin, licorice, plantain, uzara root, hawthorn, and ginseng may interfere with either digoxin pharmacodynamically or with digoxin monitoring." Narrative review, low weight.
- NCCIH licorice root page (fetched): glycyrrhizin "can cause serious adverse effects, such as irregular heartbeat and cardiac arrest"; no digoxin mention.

### Class / RxCUI
Use existing `class:cardiac_glycosides` (covers digoxin and digitoxin). No new class needed.

### Proposed record
```json
{
  "id": "DSI_CARDIAC_GLYCOSIDE_LICORICE",
  "type": "Med-Sup",
  "agent1_name": "Cardiac glycosides (digoxin, digitoxin)",
  "agent1_id": "class:cardiac_glycosides",
  "agent1_canonical_id": null,
  "agent2_name": "Licorice root (glycyrrhizin)",
  "agent2_id": "C0086555",
  "agent2_canonical_id": "licorice",
  "severity": "Major",
  "interaction_effect_type": "Additive",
  "mechanism": "Glycyrrhizin in licorice root can lower blood potassium with regular use. The digoxin label states that low potassium can make digoxin toxicity more likely. A published case describes digitalis toxicity in a man taking a licorice-containing herbal laxative.",
  "management": "If you take digoxin, avoid licorice root products that contain glycyrrhizin unless your prescriber has reviewed them. Your care team may want to check your potassium and digoxin level. Deglycyrrhizinated licorice (DGL) is a different preparation and is not covered by this alert.",
  "source_urls": [
    "https://dailymed.nlm.nih.gov/dailymed/lookup.cfm?setid=d91e3646-4c63-4512-ab22-db39c085c4dc",
    "https://pubmed.ncbi.nlm.nih.gov/28660884/",
    "https://pubmed.ncbi.nlm.nih.gov/12566654/"
  ],
  "source_pmids": ["28660884", "12566654"],
  "evidence_basis": "mechanistic_label_plus_case_report",
  "clinical_confidence": "moderate",
  "applies_to": "whole_class",
  "direction": "harmful",
  "materiality": "presence",
  "evidence_notes": "Chain: label (hypokalemia predisposes to digoxin toxicity) + meta-analysis (glycyrrhizic acid >=100 mg/day lowers potassium) + one case report read at title level only. No controlled interaction study. DGL resolves to a separate botanical id (dgl_deglycyrrhizinated_licorice, canonical_id null), so canonical licorice excludes it by identity."
}
```
Judgment calls `[J]`: `severity` Major (narrow therapeutic index and explicit label electrolyte warning; matches `DSI_ANTIHYP_LICORICE` Major; Moderate is defensible given indirect evidence). `evidence_basis` value — confirm it is an allowed enum (existing values seen: `systematic_review`, `label_regulatory`); if not, use the nearest existing value. `materiality` presence vs dose_dependent (the meta-analysis floor is 100 mg glycyrrhizic acid/day, but labels rarely state glycyrrhizin content). `interaction_effect_type` "Additive". `applies_to` whole_class (digitoxin included by the same potassium mechanism; its own label not read).

### Open questions
- Should the 100 mg/day glycyrrhizic acid floor be a `dose_threshold`, or stay presence-based because content is usually undeclared?
- Should the `heart_disease` sub-rule action text drop the digoxin mention once this pair exists (one owner)?
- Full text of PMID 12566654 not read; reviewer may want it before citing.

### Confidence
Moderate. Mechanism chain is well sourced; direct interaction evidence is one case report.

---

## 2. Oral isotretinoin + vitamin A supplements

### Existing coverage
None. No `isotretinoin` in curated files, rules or drug_classes.json. `vitamin_a` has no curated pair; profile rules `RULE_IQM_VITAMIN_A_PREGNANCY_DOSE` and `RULE_IQM_VITAMIN_A_BETA_CAROTENE_LUNG_CANCER` have no drug_class_rules. Two "retinoid" mentions in ingredient_interaction_rules.json (lines ~7413, ~7736) are unrelated free text.

### Sources
- ABSORICA / ABSORICA LD label, setid `3ef0cff8-19c1-4441-b780-fca6c7ee1615` (Sun, Aug 2026), section 7.1: "Avoid concomitant use of ABSORICA/ABSORICA LD with supplements containing vitamin A. ABSORICA/ABSORICA LD is closely related to vitamin A." and "concomitant use ... with vitamin A may lead to ABSORICA/ABSORICA LD-associated adverse reactions."
- Same label, section 4: contraindicated in patients with hypersensitivity "to isotretinoin (or Vitamin A, given the chemical similarity to isotretinoin)". This is a hypersensitivity contraindication, not a co-use contraindication.
- Absorica is the brand chosen (original Accutane RLD not searched; one label read).

### Class / RxCUI
No class. Use RxCUI `6064` (isotretinoin, IN, Active). Route limitation: an IN-level RxCUI cannot distinguish oral from topical isotretinoin (topical isotretinoin gels exist outside the US). The label passage is from an oral capsule label only.

### Proposed record
```json
{
  "id": "DSI_ISOTRETINOIN_VITAMIN_A",
  "type": "Med-Sup",
  "agent1_name": "Isotretinoin (oral)",
  "agent1_id": "6064",
  "agent1_canonical_id": null,
  "agent2_name": "Vitamin A",
  "agent2_id": "C0042839",
  "agent2_canonical_id": "vitamin_a",
  "severity": "Major",
  "interaction_effect_type": "Additive",
  "mechanism": "Oral isotretinoin is closely related to vitamin A. Its prescribing information says taking it with vitamin A supplements may lead to isotretinoin side effects. This applies to isotretinoin taken by mouth, not to retinoid creams or gels used on the skin.",
  "management": "The isotretinoin label says to avoid supplements that contain vitamin A while taking oral isotretinoin. Check multivitamins too, and ask your prescriber or pharmacist before taking any product that lists vitamin A.",
  "source_urls": [
    "https://dailymed.nlm.nih.gov/dailymed/lookup.cfm?setid=3ef0cff8-19c1-4441-b780-fca6c7ee1615"
  ],
  "source_pmids": [],
  "evidence_basis": "label_regulatory",
  "clinical_confidence": "high",
  "applies_to": "specific_drug",
  "direction": "harmful",
  "materiality": "presence",
  "evidence_notes": "Absorica section 7.1 'Avoid concomitant use ... with supplements containing vitamin A'. Oral capsule label only; topical retinoids are out of scope. RxCUI 6064 is ingredient-level and does not encode route."
}
```
Judgment calls `[J]`: `severity` Major (label verb "Avoid"; not Contraindicated because the label lists co-use under Drug Interactions, not Contraindications). `applies_to` value "specific_drug" — confirm allowed enum. `materiality` presence (label gives no dose). Form scope: the label says "supplements containing vitamin A" and gives no exception for provitamin carotenoids; the record above applies to every `vitamin_a` form, including beta-carotene. Excluding carotenoid-only forms (via `profile_gate.excludes.nutrient_forms_any`) would be a new clinical determination.

### Open questions
- Route gating: how does the matcher keep a user on topical isotretinoin (or tretinoin/adapalene, which have other RxCUIs and are already outside this record) from getting this alert? A profile gate or route field may be needed; the bisphosphonate record shows the same unresolved gap.
- Beta-carotene / alpha-carotene / beta-cryptoxanthin: include or exclude? (IQM vitamin_a forms include all three.)
- Acitretin (oral retinoid) has similar label language in some regions; not researched here.

### Confidence
High for the label claim and oral scope. Medium for how it will fire until route gating and carotenoid scope are settled.

---

## 3. Carbidopa/levodopa + iron

### Existing coverage
None. No `levodopa`, `carbidopa`, or antiparkinson class in curated files, rules or drug_classes.json. `RULE_IQM_IRON_HYPERTENSION` drug_class_rules: antihypertensives, thyroid_medications, fluoroquinolones only.

### Sources
- SINEMET label, setid `9b17b028-964a-473c-823d-81423535bd66` (Organon, Aug 2026), Drug Interactions: "SINEMET and iron salts or multivitamins containing iron salts should be coadministered with caution. Iron salts can form chelates with levodopa and carbidopa and consequently reduce the bioavailability of carbidopa and levodopa."
- Same label, patient information: "Iron salts (such as in multivitamin tablets) may also reduce the amount of levodopa available to the body."
- **Interval: the label states none.** No separation interval was found in the Sinemet text. No other source was fetched for an interval; none is supplied.

### Class / RxCUI
No class. Use RxCUI `6375` (levodopa, IN, Active). Carbidopa `2019` is verified but carbidopa alone is not dosed for Parkinson's; levodopa is the affected drug. Other levodopa products (extended-release capsules, enteral suspension, inhaled levodopa) carry levodopa too; their labels were not read.

### Proposed record
```json
{
  "id": "DSI_LEVODOPA_IRON",
  "type": "Med-Sup",
  "agent1_name": "Levodopa (carbidopa/levodopa)",
  "agent1_id": "6375",
  "agent1_canonical_id": null,
  "agent2_name": "Iron",
  "agent2_id": "C0302583",
  "agent2_canonical_id": "iron",
  "severity": "Moderate",
  "interaction_effect_type": "Inhibitor",
  "mechanism": "Iron can bind levodopa and carbidopa in the gut and lower how much is absorbed. The carbidopa/levodopa label says iron salts, including iron in multivitamins, may reduce the amount of levodopa available to the body.",
  "management": "If you take carbidopa/levodopa, talk to your prescriber or pharmacist before starting an iron supplement or a multivitamin with iron. They can help you plan the timing and watch for any change in how well your Parkinson's medicine works.",
  "source_urls": [
    "https://dailymed.nlm.nih.gov/dailymed/lookup.cfm?setid=9b17b028-964a-473c-823d-81423535bd66"
  ],
  "source_pmids": [],
  "evidence_basis": "label_regulatory",
  "clinical_confidence": "high",
  "applies_to": "specific_drug",
  "direction": "harmful",
  "materiality": "presence",
  "evidence_notes": "Sinemet label: 'coadministered with caution'; chelation reduces carbidopa and levodopa bioavailability. The label gives no separation interval, so none is stated. Route: oral levodopa; enteral/inhaled levodopa labels not reviewed."
}
```
Judgment calls `[J]`: `severity` Moderate (label verb "with caution", effect is reduced efficacy rather than toxicity). Agent1 = levodopa IN rather than a new class (no class owner exists; creating `class:levodopa_products` would be a new owner for Sean). Whether inhaled levodopa (bypasses gut) should be excluded.

### Open questions
- Does the medication matcher map the combination product (carbidopa/levodopa SCD/SBD) to levodopa IN 6375? If not, the record will not fire for the common product.
- Timing advice: no source-stated interval; reviewer may want a PubMed PK study (e.g., Campbell 1990 ferrous sulfate–levodopa) before any timing language. Not fetched.

### Confidence
High for the label claim. Medium for matcher coverage.

---

## 4. Oral bisphosphonates + calcium / minerals / antacids

### Existing coverage
- `class:bisphosphonates` exists (drug_classes.json): alendronate 46041, ibandronate 115264, risedronate 73056, **zoledronic acid 77655 (IV only)**; ATC M05BA.
- Curated `DSI_MAGNESIUM_BISPHOSPHONATE` (class:bisphosphonates + magnesium, Major) exists and is adequate for magnesium; its own evidence_notes say "Existing broad class still lacks route/formulation gating". Its source setid `c89430be-...` is a generic risedronate sodium delayed-release label (not Atelvia brand).
- **No calcium + bisphosphonate pair.** `RULE_IQM_CALCIUM` drug_class_rules: thyroid_medications, fluoroquinolones only. No iron + bisphosphonate pair either (risedronate labels name iron; noted below, not proposed).
- Antacids: not a separate canonical; calcium carbonate antacids resolve through `calcium`, magnesium antacids through the existing magnesium record. Aluminum not researched.

Verdict: calcium is a gap; magnesium already covered.

### Sources (exact label dosing passages)
- FOSAMAX (alendronate), setid `14e931fd-2c5f-4d90-b7db-5980706f4a56` (Organon, Mar 2026), 7.1: "Co-administration of FOSAMAX and calcium, antacids, or oral medications containing multivalent cations will interfere with absorption of FOSAMAX. Therefore, instruct patients to wait at least one-half hour after taking FOSAMAX before taking any other oral medications."
- ACTONEL (risedronate IR), setid `24ed00e0-25e2-49a8-97fc-66c1b417dc0b` (Allergan, May 2026), 2.x: take "at least 30 minutes before the first food or drink of the day other than water, and before taking any oral medication or supplementation, including calcium, antacids, or vitamins". 2.7: take "calcium supplements, antacids, magnesium-based supplements or laxatives, and iron preparations at a different time of the day as they interfere with the absorption of ACTONEL."
- Risedronate sodium delayed-release, setid `c89430be-15f1-4b8b-ab7e-738de716ee7d`, 7.1: taken after breakfast, "co-administration of a tablet containing 600 mg of elemental calcium and 400 international units vitamin D reduced risedronate bioavailability by approximately 38%". Patients take calcium, antacids, magnesium and iron "at a different time of the day".
- Ibandronate sodium tablets (generic; Boniva brand only available as a 2010 repackager label), setid `6ca94cce-a2bb-421f-bd8f-6b14bc2bd985` (Bionpharma, Aug 2026), 2.3: "Avoid the use of calcium supplements within 60 minutes of Ibandronate Sodium Tablet administration because co-administration ... and calcium may interfere with the absorption of ibandronate sodium."

Intervals stated by labels: alendronate 30 min after the dose; risedronate IR at least 30 min before, and calcium at a different time of day; risedronate DR different time of day; ibandronate 60 min. They differ, so a single universal interval is not supported.

### Class / RxCUI
Existing `class:bisphosphonates`. It includes IV zoledronic acid, to which this oral-absorption interaction does not apply.

### Proposed record
```json
{
  "id": "DSI_CALCIUM_BISPHOSPHONATE",
  "type": "Med-Sup",
  "agent1_name": "Bisphosphonates (class)",
  "agent1_id": "class:bisphosphonates",
  "agent1_canonical_id": null,
  "agent2_name": "Calcium",
  "agent2_id": "C0006675",
  "agent2_canonical_id": "calcium",
  "severity": "Major",
  "interaction_effect_type": "Inhibitor",
  "mechanism": "Calcium, including calcium-based antacids, binds oral bisphosphonates in the gut and reduces how much of the medicine is absorbed. The labels for alendronate, risedronate and ibandronate tablets all describe this. It does not apply to bisphosphonates given by IV infusion, such as zoledronic acid.",
  "management": "Calcium is often recommended alongside these medicines, so the goal is timing, not stopping it. Each label gives its own instructions: alendronate, wait at least 30 minutes after the dose; ibandronate tablets, avoid calcium within 60 minutes; risedronate, take calcium at a different time of day. Ask your pharmacist to set a schedule for your specific product.",
  "source_urls": [
    "https://dailymed.nlm.nih.gov/dailymed/lookup.cfm?setid=14e931fd-2c5f-4d90-b7db-5980706f4a56",
    "https://dailymed.nlm.nih.gov/dailymed/lookup.cfm?setid=24ed00e0-25e2-49a8-97fc-66c1b417dc0b",
    "https://dailymed.nlm.nih.gov/dailymed/lookup.cfm?setid=c89430be-15f1-4b8b-ab7e-738de716ee7d",
    "https://dailymed.nlm.nih.gov/dailymed/lookup.cfm?setid=6ca94cce-a2bb-421f-bd8f-6b14bc2bd985"
  ],
  "source_pmids": [],
  "evidence_basis": "label_regulatory",
  "clinical_confidence": "high",
  "applies_to": "whole_class",
  "direction": "harmful",
  "materiality": "presence",
  "evidence_notes": "All oral bisphosphonate labels read state calcium/antacids interfere with absorption; intervals differ by product and are quoted per label. Risedronate DR: 600 mg calcium + vitamin D reduced bioavailability ~38%. Class includes IV zoledronic acid; same unresolved route gating as DSI_MAGNESIUM_BISPHOSPHONATE."
}
```
Judgment calls `[J]`: `severity` Major (matches existing magnesium sibling for consistency; the effect is loss of efficacy, so Moderate is arguable — if changed, change both). Including label-specific intervals in management (they are label-stated, so allowed, but long). `applies_to` whole_class despite zoledronic acid membership.

### Open questions
- Route gating for IV zoledronic acid (and IV ibandronate) — shared defect with the magnesium record; fix once in the class or matcher, not per record.
- Iron: Actonel and risedronate DR labels name iron preparations; a `DSI_IRON_BISPHOSPHONATE` pair would follow the same pattern. Not proposed (out of the requested scope).
- Fosamax Plus D (alendronate + cholecalciferol) — matcher behavior for the combination not checked.

### Confidence
High.

---

## 5. Source for RULE_IQM_PSYLLIUM_DIABETES

### Existing coverage / current problem
`RULE_IQM_PSYLLIUM_DIABETES` (ingredient_interaction_rules.json): condition `diabetes` (monitor) plus drug_class_rules `hypoglycemics_high_risk`, `hypoglycemics_lower_risk`, `hypoglycemics_unknown` (monitor) and `lithium`. Every diabetes sub-rule cites only `https://www.nccih.nih.gov/health/diabetes-and-dietary-supplements-what-you-need-to-know`. Fetched that page: 0 occurrences of "psyllium" (confirmed). The hypoglycemic drug_class_rules mechanism says "Fiber delays absorption of co-administered oral medications including metformin and sulfonylureas", and the condition alert_body says psyllium "may delay absorption of oral diabetes medications". (Lithium sub-rule not reviewed.)

### Sources for glucose lowering (content-verified abstracts)
- Gholami 2024, PMID 38844885, BMC Endocr Disord, GRADE-assessed systematic review and meta-analysis of 19 RCTs (962 participants): "psyllium could significantly decrease FBS, HbA1c, and HOMA IR levels, but not insulin levels, as compared to placebo." No competing interests declared. **Preferred primary.**
- Gibb 2015, PMID 26561625, Am J Clin Nutr, meta-analysis of 35 RCTs: in T2DM, "multiweek studies (psyllium dosed before meals) showed significant improvement in both the fasting blood glucose (FBG) concentration (-37.0 mg/dL; P < 0.001) and glycated hemoglobin". Also: "no significant glucose lowering was observed in euglycemic subjects". Authors include Procter & Gamble employees (Metamucil maker); use as supporting, note the conflict. It also says further studies are needed on use "with concomitant hypoglycemic medications", which supports a monitor-level alert rather than a stronger one.

### "Fiber delays absorption of metformin/sulfonylureas" — evidence found
- No human study of psyllium with metformin or a sulfonylurea was found (PubMed: psyllium AND metformin/glibenclamide/glyburide/sulfonylurea returned only rabbit, formulation and adulterant papers).
- Gin 1989, PMID 2722133: **guar gum**, not psyllium, 6 healthy volunteers: with guar "there was a reduction in the absorption rate over the first 6 hours" of metformin.
- Díez 2017, PMID 28592281: **diabetic rabbits**, Plantago ovata husk "increased the amount of absorbed metformin when included in the diet ... and delayed its absorption when administered at the same time". Animal data; direction is mixed (more absorbed overall).
- Conclusion: the metformin/sulfonylurea absorption claim is not supported for psyllium in humans. Recommend removing it from the mechanism and the condition alert_body, keeping the additive glucose-lowering mechanism, which the meta-analyses support.

### Proposed correction (edit of existing rule, not a new record)
Replace `sources` on the `diabetes` condition rule and the three hypoglycemic drug_class_rules with:
```json
[
  "https://pubmed.ncbi.nlm.nih.gov/38844885/",
  "https://pubmed.ncbi.nlm.nih.gov/26561625/"
]
```
Replace the hypoglycemic drug_class_rules `mechanism` with:
```json
"Meta-analyses of randomized trials found that psyllium lowers fasting blood glucose and HbA1c in people with type 2 diabetes. Added to a glucose-lowering medicine, this may increase the overall effect on blood sugar."
```
Replace the condition `alert_body` phrase "and may delay absorption of oral diabetes medications" by removing it, giving:
```json
"Psyllium can lower blood sugar after meals and over time. If you have diabetes, talk to your clinician and monitor glucose, especially in the first weeks."
```
Judgment calls `[J]`: keep severity `monitor` (unchanged; the sources show modest-to-moderate lowering and no hypoglycemia events in the abstracts). The condition-rule mechanism ("delays gastric emptying and slows carbohydrate absorption") is plausible but not stated in either abstract read; reviewer can keep it with Gibb's background sentence on viscous fibers attenuating "postprandial glucose excursions", or reword to the outcome only. `evidence_level` "established" is consistent with two meta-analyses.

### Open questions
- Per "changing a structured value means fixing every free-text field": the informational_note and alert_headline do not contain the absorption claim; the condition alert_body and three drug_class mechanisms do. A test should assert the phrase "delay absorption" / "delays absorption" is gone from this rule.
- Lithium sub-rule source and claim were not reviewed in this batch.

### Confidence
High that the NCCIH citation is a ghost source for psyllium and that the two PMIDs support glucose lowering. High that no human source supports psyllium delaying metformin/sulfonylurea absorption (one search; absence of evidence, not evidence of absence).

---

## Fetch log
All fetches succeeded on the first attempt: DailyMed searches (lanoxin, absorica, sinemet, fosamax, actonel, boniva, ibandronate), SPL XML for Lanoxin, Absorica, Sinemet, Fosamax, Actonel, ibandronate (Bionpharma), risedronate DR (c89430be); PubMed esearch/esummary/efetch; NCCIH licorice and diabetes pages; RxNav history status x8. Not fetched: Accutane/other isotretinoin labels, Rytary/Duopa/Inbrija levodopa labels, full text of PMID 12566654, UMLS re-verification of agent2 CUIs.
