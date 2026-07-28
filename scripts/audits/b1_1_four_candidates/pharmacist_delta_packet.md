# B1.1 pharmacist delta review packet

Status: **evidence revision complete; licensed pharmacist sign-off requested**

Scope: **4 suppressed B1.1 candidates; none are consumer-visible until separately approved. They are separate from the reopened B1 active-copy delta.**

Artifact: schema `5.4.0`, content version `2026.07.27-b1-closure.1`, content hash `sha256:c3f95f1d5ea4cbf05a6d26e81f3623e3834dd577d3b70c9f1bbc551a8dd89dee`.

## Review focus

**Approval covers the full card copy shown to the user — all seven consumer-visible fields reproduced under each record below, not only mechanism, clinical impact, and recommendation.** Every line printed under "Consumer-visible card copy" is text a user can read in the app.

- Confirm the medication scope and nutrient relationship are clinically accurate.
- Confirm the mechanism and clinical impact are supported by the linked evidence.
- Confirm recommendations are calm, actionable, and do not imply universal supplementation.
- Confirm monitoring and supplement-interaction records are not presented as measured deficiency.
- Dispositions are limited to `approved`, `approved_with_wording_change`, `requires_evidence_revision`, or `remove_from_release`.

## App presentation

**These images are layout-regression artifacts, not clinical-review evidence.** They are Flutter golden files: text renders as filled boxes because no font is registered in the test binding, and the verified card is captured in its collapsed state, so the expanded detail copy does not appear. Review the card copy from the per-record text below, which is the authoritative source. Do not base an approval on these screenshots.

Verified records (layout only):

![Verified medication-nutrient layout](../../../../../PharmaGuide%20ai/test/release_gate/goldens/med_nutrient_verified.png)

Unavailable analysis, explicitly not an all-clear (layout only):

![Unavailable medication-nutrient layout](../../../../../PharmaGuide%20ai/test/release_gate/goldens/med_nutrient_unavailable.png)

### Exact unavailable and partial-state copy

App unavailable card:

- Title: Check unavailable
- Body: We couldn't load the medication & nutrient checks right now. This is not an all-clear — please try again later.

Clinician report unavailable state:

- Status: Unavailable
- Body: Medication-nutrient analysis was unavailable when this report was generated. This is not evidence that no interactions exist - the check could not run.

Clinician report partial state:

- Status: Partial - fallback artifact
- Body: Partial medication-nutrient analysis: a fallback reference artifact was used. Review these notes in that context.

## Review disposition index

| Record | Medication / class | Nutrient | Relationship | Disposition | Consumer-visible |
|---|---|---|---|---|---|
| `DEP_DIURETICS_MAGNESIUM` | Loop and thiazide diuretics (water pills) (`class:loop_and_thiazide_diuretics`) | Magnesium | `depletion` | `pending_licensed_pharmacist_review` | no |
| `DEP_DIURETICS_POTASSIUM` | Loop and thiazide diuretics (water pills) (`class:loop_and_thiazide_diuretics`) | Potassium | `depletion` | `pending_licensed_pharmacist_review` | no |
| `DEP_ANTACIDS_MAGNESIUM` | Proton pump inhibitors (PPIs) (`class:proton_pump_inhibitors`) | Magnesium | `depletion` | `pending_licensed_pharmacist_review` | no |
| `DEP_ANTACIDS_VITAMINB12` | Proton pump inhibitors (PPIs) (`class:proton_pump_inhibitors`) | Vitamin B12 | `depletion` | `pending_licensed_pharmacist_review` | no |

## Record details

### 1. `DEP_DIURETICS_MAGNESIUM`

- Medication / class: Loop and thiazide diuretics (water pills) (`class:loop_and_thiazide_diuretics`)
- Nutrient: Magnesium (`magnesium`)
- Relationship: `depletion`; severity `moderate`; onset `variable`

Consumer-visible card copy (every line below is shown to the user — approval covers all of it):

- Headline (`alert_headline`): Loop and thiazide diuretics may lower magnesium
- Body (`alert_body`): With regular use, loop and thiazide diuretics can increase urinary magnesium loss. The likelihood varies by medicine, dose, and individual factors.
- Monitoring tip (`monitoring_tip_short`): Ask whether magnesium should be checked with other electrolytes, especially if potassium is low.
- What can happen (`clinical_impact`): Low magnesium can contribute to weakness, cramps, tremor, or arrhythmias and can coexist with low potassium. The finding requires clinical interpretation because symptoms and risk also depend on kidney function and other medicines.
- From food (`food_sources_short`): Food sources of magnesium include leafy greens, nuts, seeds, whole grains, and beans.
- Why (`mechanism`): Loop and thiazide diuretics can increase urinary magnesium losses through their effects on renal electrolyte handling. The magnitude and mechanism differ by diuretic subclass and by individual clinical factors.
- Clinical guidance (`recommendation`): Do not start a routine magnesium dose solely because you take a diuretic. Ask whether magnesium should be included with electrolyte monitoring, especially if potassium is low, symptoms appear, the dose is high, or intake is limited; correction should be clinician-directed.

- Evidence: [DailyMed — Furosemide tablets prescribing information](https://dailymed.nlm.nih.gov/dailymed/drugInfo.cfm?setid=f3173c0d-2b62-7c7b-e053-2995a90ada05); [DailyMed — Hydrochlorothiazide tablets prescribing information](https://dailymed.nlm.nih.gov/dailymed/drugInfo.cfm?setid=8a1de4e2-3aca-a4d3-e053-2995a90a1a41); [Ellison DH. Divalent cation transport by the distal nephron: insights from Bartter's and Gitelman's syndromes. Am J Physiol Renal Physiol. 2000;279(4):F616-25](https://pubmed.ncbi.nlm.nih.gov/10997911/)

Reviewer disposition: **`pending_licensed_pharmacist_review`**
Review note: Confirm the subclass-aware mechanism, variable timing, and clinician-directed monitoring/correction language.
Consumer-visible after review: **no**

Reviewer comment (Approved / Approved with wording change / Requires evidence revision / Remove from release, plus any required change): _______________________________________

### 2. `DEP_DIURETICS_POTASSIUM`

- Medication / class: Loop and thiazide diuretics (water pills) (`class:loop_and_thiazide_diuretics`)
- Nutrient: Potassium (`potassium`)
- Relationship: `depletion`; severity `significant`; onset `variable`

Consumer-visible card copy (every line below is shown to the user — approval covers all of it):

- Headline (`alert_headline`): Loop and thiazide diuretics may lower potassium
- Body (`alert_body`): With regular use or after dose changes, loop and thiazide diuretics can lower potassium. The effect varies and laboratory monitoring guides management.
- Monitoring tip (`monitoring_tip_short`): Ask how often potassium should be checked based on the diuretic, dose, kidneys, and other medicines.
- What can happen (`clinical_impact`): Low potassium can cause muscle weakness or cramps and increase arrhythmia risk; it can also increase digoxin toxicity. Some patients do not develop low potassium, and kidney disease or other medicines can instead raise it.
- From food (`food_sources_short`): Potassium is found in potatoes, beans, fruit, dairy, and vegetables; whether to change intake depends on labs and kidney function.
- Why (`mechanism`): Loop and thiazide diuretics increase renal sodium delivery and urinary electrolyte losses. This can lower potassium; the likelihood depends on the agent, dose, intake, kidney function, and concurrent medications.
- Clinical guidance (`recommendation`): Do not start potassium or deliberately increase dietary potassium without checking with your prescriber. Serum potassium should be monitored; any food, supplement, or prescription replacement plan must account for kidney function and other medications.

- Evidence: [DailyMed — Furosemide tablets prescribing information](https://dailymed.nlm.nih.gov/dailymed/drugInfo.cfm?setid=f3173c0d-2b62-7c7b-e053-2995a90ada05); [DailyMed — Hydrochlorothiazide tablets prescribing information](https://dailymed.nlm.nih.gov/dailymed/drugInfo.cfm?setid=8a1de4e2-3aca-a4d3-e053-2995a90a1a41)

Reviewer disposition: **`pending_licensed_pharmacist_review`**
Review note: Confirm the loop/thiazide-only scope, variable timing, and the explicit no-self-supplementation safety language.
Consumer-visible after review: **no**

Reviewer comment (Approved / Approved with wording change / Requires evidence revision / Remove from release, plus any required change): _______________________________________

### 3. `DEP_ANTACIDS_MAGNESIUM`

- Medication / class: Proton pump inhibitors (PPIs) (`class:proton_pump_inhibitors`)
- Nutrient: Magnesium (`magnesium`)
- Relationship: `depletion`; severity `significant`; onset `variable`

Consumer-visible card copy (every line below is shown to the user — approval covers all of it):

- Headline (`alert_headline`): Rarely, long-term PPIs may lower magnesium
- Body (`alert_body`): With prolonged use, PPIs can rarely lower magnesium. Most reports follow a year or more of use, but cases have occurred earlier.
- Monitoring tip (`monitoring_tip_short`): Ask whether magnesium monitoring fits prolonged PPI use, especially with digoxin or a diuretic.
- What can happen (`clinical_impact`): Low magnesium may be asymptomatic or can contribute to tetany, seizures, or arrhythmias and may accompany low calcium or potassium. FDA labeling notes that some cases required magnesium replacement and stopping the PPI.
- From food (`food_sources_short`): Food sources of magnesium include leafy greens, nuts, seeds, whole grains, and beans.
- Why (`mechanism`): Rare PPI-associated hypomagnesemia appears to involve reduced intestinal magnesium absorption, but the precise molecular mechanism is not established. Dechallenge and rechallenge reports support a PPI class effect.
- Clinical guidance (`recommendation`): Do not start a routine magnesium dose solely because you take a PPI. For prolonged therapy—especially with digoxin, a diuretic, or other risk factors—ask whether baseline and periodic magnesium testing is appropriate. Management of a low result should be clinician-directed.

- Evidence: [Hess MW et al. Systematic review: hypomagnesaemia induced by proton pump inhibition. Aliment Pharmacol Ther. 2012;36(5):405-13](https://pubmed.ncbi.nlm.nih.gov/22762246/); [DailyMed — PRILOSEC (omeprazole) prescribing information, section 5.9](https://dailymed.nlm.nih.gov/dailymed/drugInfo.cfm?setid=b6761f84-53ac-4745-a8c8-1e5427d7e179)

Reviewer disposition: **`pending_licensed_pharmacist_review`**
Review note: Confirm the rare but potentially clinically important signal, variable onset, and risk-based monitoring language.
Consumer-visible after review: **no**

Reviewer comment (Approved / Approved with wording change / Requires evidence revision / Remove from release, plus any required change): _______________________________________

### 4. `DEP_ANTACIDS_VITAMINB12`

- Medication / class: Proton pump inhibitors (PPIs) (`class:proton_pump_inhibitors`)
- Nutrient: Vitamin B12 (`vitamin_b12`)
- Relationship: `depletion`; severity `moderate`; onset `years`

Consumer-visible card copy (every line below is shown to the user — approval covers all of it):

- Headline (`alert_headline`): Long-term PPI use may affect vitamin B12
- Body (`alert_body`): With long-term PPI use, reduced stomach acid may lower absorption of vitamin B12 from food. Not everyone develops low levels.
- Monitoring tip (`monitoring_tip_short`): Ask whether B12 testing fits if use is prolonged or anemia, nerve symptoms, or other factors appear.
- What can happen (`clinical_impact`): Long-term PPI use is associated with a modestly higher likelihood of vitamin B12 deficiency, but the literature is heterogeneous and association does not prove causation. Confirmed deficiency can contribute to anemia or neurologic symptoms.
- From food (`food_sources_short`): Vitamin B12 is found in animal foods and fortified foods; laboratory assessment helps evaluate absorption and intake.
- Why (`mechanism`): PPIs reduce gastric acid. With prolonged use, this can impair absorption of food-bound vitamin B12; the degree of effect varies, and observational studies do not show that every user becomes deficient.
- Clinical guidance (`recommendation`): Do not start high-dose B12 solely because you take a PPI. If use is prolonged or you have anemia, neurologic symptoms, a restricted diet, or other B12 risk factors, ask your clinician whether B12 testing is appropriate; treat confirmed deficiency with an individualized plan.

- Evidence: [NIH ODS — Vitamin B12 Fact Sheet for Health Professionals](https://ods.od.nih.gov/factsheets/VitaminB12-HealthProfessional/); [Lam JR et al. Proton pump inhibitor and histamine 2 receptor antagonist use and vitamin B12 deficiency. JAMA. 2013;310(22):2435-42](https://pubmed.ncbi.nlm.nih.gov/24327038/); [Choudhury A et al. Vitamin B12 deficiency and use of proton pump inhibitors: a systematic review and meta-analysis. Expert Rev Gastroenterol Hepatol. 2023;17(5):479-487](https://pubmed.ncbi.nlm.nih.gov/37060552/); [DailyMed — PRILOSEC (omeprazole) prescribing information, sections 5.8 and 5.9](https://dailymed.nlm.nih.gov/dailymed/drugInfo.cfm?setid=b6761f84-53ac-4745-a8c8-1e5427d7e179)

Reviewer disposition: **`pending_licensed_pharmacist_review`**
Review note: Confirm the PPI-only scope, probable evidence tier, and symptom/risk-based testing language.
Consumer-visible after review: **no**

Reviewer comment (Approved / Approved with wording change / Requires evidence revision / Remove from release, plus any required change): _______________________________________

## Sign-off

- Reviewer: `` (Licensed pharmacist clinical review requested)
- Review date: `2026-07-27`
- Release disposition: `pending_licensed_pharmacist_delta_review`
- Evidence auditor: `b1_1_evidence_audit` (AI clinical-content audit)
- Licensed clinical approver organization: `PharmaGuide Clinical Team`
- Licensed pharmacist sign-off: **not represented by this packet**
- Scope statement: This packet requests licensed-pharmacist review of the documented evidence audit; it does not record release approval or claim professional licensure.
