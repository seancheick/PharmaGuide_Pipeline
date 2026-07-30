# B1 clinical-copy delta review packet

Status: **clinical-team evidence QA returned; requested changes implemented; two records and presentation remain pending exact-current review**

Scope: **11 corrected active records: 7 approved as written, 2 exact wording changes implemented as directed, and 2 evidence revisions implemented pending exact-current re-review. App unavailable/partial states and clinician PDF remain unreviewed.**

Artifact: schema `5.4.0`, content version `2026.07.30-b1-delta.2`, content hash `sha256:ec003d3082bedfcf133a266c101960e6b2892fb6cbc9013e1b55b66556e6423f`.

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
| `DEP_ANTACIDS_IRON` | Acid reducers (PPIs and H2 blockers) (`class:acid_suppressants`) | Iron | `depletion` | `requires_evidence_revision` | yes |
| `DEP_CHOLESTYRAMINE_VITAMINA` | Cholestyramine (bile-acid sequestrant) (`2447`) | Vitamin A | `depletion` | `approved` | yes |
| `DEP_CHOLESTYRAMINE_VITAMIND` | Cholestyramine (bile-acid sequestrant) (`2447`) | Vitamin D | `depletion` | `approved` | yes |
| `DEP_CHOLESTYRAMINE_VITAMINE` | Cholestyramine (bile-acid sequestrant) (`2447`) | Vitamin E | `depletion` | `approved` | yes |
| `DEP_CHOLESTYRAMINE_VITAMINK` | Cholestyramine (bile-acid sequestrant) (`2447`) | Vitamin K | `depletion` | `approved` | yes |
| `DEP_DIURETICS_THIAMINE` | Furosemide (Lasix) (`4603`) | Thiamin | `depletion` | `approved` | yes |
| `DEP_LEVOTHYROXINE_CALCIUM` | Levothyroxine (thyroid hormone replacement) (`10582`) | Calcium | `supplement_interaction` | `approved_with_wording_change` | yes |
| `DEP_LEVOTHYROXINE_IRON` | Levothyroxine (thyroid hormone replacement) (`10582`) | Iron | `supplement_interaction` | `approved` | yes |
| `DEP_ORLISTAT_VITAMINA` | Orlistat (fat-blocking weight-loss medication) (`37925`) | Vitamin A | `depletion` | `approved_with_wording_change` | yes |
| `DEP_SSRIS_SODIUM` | SSRIs (antidepressants) (`class:ssris`) | Sodium | `monitoring_stability` | `requires_evidence_revision` | yes |
| `DEP_ANTICOAGULANTS_VITAMINK` | Warfarin (anticoagulant / blood thinner) (`11289`) | Vitamin K | `functional_antagonism` | `approved` | yes |

## Record details

### 1. `DEP_ANTACIDS_IRON`

- Medication / class: Acid reducers (PPIs and H2 blockers) (`class:acid_suppressants`)
- Nutrient: Iron (`iron`)
- Relationship: `depletion`; severity `moderate`; onset `years`

Consumer-visible card copy (every line below is shown to the user — approval covers all of it):

- Headline (`alert_headline`): Long-term acid suppression can affect iron status
- Body (`alert_body`): PPI or H2-blocker use for two years or longer is associated with a higher chance of iron deficiency, especially at higher doses.
- Monitoring tip (`monitoring_tip_short`): Discuss ferritin and blood-count testing if long-term use coincides with symptoms or other iron-deficiency risks.
- What can happen (`clinical_impact`): Use for two years or longer is associated with a higher risk of iron deficiency, with greater risk at higher doses and longer duration. Other causes of iron deficiency still need clinical evaluation.
- From food (`food_sources_short`): Food sources of iron include red meat, poultry, seafood, beans, lentils, tofu, spinach, and fortified cereals.
- Why (`mechanism`): Gastric acid helps release non-heme iron from food and supports its absorption. PPIs and H2 blockers suppress acid, so long-term use can lower non-heme iron absorption. In the observational study, the association with iron deficiency became weaker after acid-suppressing treatment was discontinued. This does not mean that an existing deficiency will always reverse after stopping treatment.
- Clinical guidance (`recommendation`): If you use a PPI or H2 blocker long term and have iron-deficiency symptoms or risk factors, ask your clinician whether ferritin and blood-count testing is appropriate. Do not start iron without confirming the cause and a suitable treatment plan, and do not stop the acid reducer on your own.

- Evidence: [Lam JR et al. Proton pump inhibitor and histamine-2 receptor antagonist use and iron deficiency. Gastroenterology. 2017](https://pubmed.ncbi.nlm.nih.gov/27890768/); [Hutchinson C et al. Proton pump inhibitors suppress absorption of dietary non-haem iron in hereditary haemochromatosis. Gut. 2007](https://pubmed.ncbi.nlm.nih.gov/17344278/); [Snook J et al. British Society of Gastroenterology guidelines for the management of iron deficiency anaemia in adults. Gut. 2021](https://gut.bmj.com/content/70/11/2030)

Reviewer disposition: **`requires_evidence_revision`**
Review note: Added the BSG adult IDA diagnostic guideline, the supplied attenuation caveat, and an explicit instruction not to stop the acid reducer independently.
Consumer-visible after review: **yes**

Reviewer comment (Approved / Approved with wording change / Requires evidence revision / Remove from release, plus any required change): _______________________________________

### 2. `DEP_CHOLESTYRAMINE_VITAMINA`

- Medication / class: Cholestyramine (bile-acid sequestrant) (`drug:2447`)
- Nutrient: Vitamin A (`vitamin_a`)
- Relationship: `depletion`; severity `moderate`; onset `months`

Consumer-visible card copy (every line below is shown to the user — approval covers all of it):

- Headline (`alert_headline`): May lower vitamin A absorption
- Body (`alert_body`): With prolonged use, cholestyramine can reduce Vitamin A absorption because bile supports uptake of fat-soluble vitamins.
- Monitoring tip (`monitoring_tip_short`): Ask about a water-miscible vitamin A form; pregnancy requires review of the form and total dose.
- What can happen (`clinical_impact`): Long-term cholestyramine use can lower vitamin A absorption. Excess preformed vitamin A can cause birth defects, so pregnancy or possible pregnancy requires clinician review of the vitamin A form and total dose.
- From food (`food_sources_short`): _(not set)_
- Why (`mechanism`): Cholestyramine binds bile acids in the gut and can interfere with fat digestion and absorption. Because Vitamin A is fat-soluble, long-term bile-acid binding can reduce absorption unless vitamin timing is managed.
- Clinical guidance (`recommendation`): For long-term use, ask whether a water-miscible vitamin A form is appropriate. The label directs other medicines at least 1 hour before or 4–6 hours after cholestyramine; confirm how to time the vitamin. If you are pregnant or could become pregnant, have the vitamin A form and total dose reviewed rather than adding extra preformed vitamin A.

- Evidence: [DailyMed — CHOLESTYRAMINE prescribing information](https://dailymed.nlm.nih.gov/dailymed/drugInfo.cfm?setid=09420793-7357-4194-8172-0b1cddb167fe); [NIH ODS — Vitamin A Fact Sheet for Health Professionals](https://ods.od.nih.gov/factsheets/VitaminA-HealthProfessional/)

Reviewer disposition: **`approved`**
Review note: Approved as written: water-miscible-form, timing, and preformed-vitamin-A pregnancy guidance align.
Consumer-visible after review: **yes**

Reviewer comment (Approved / Approved with wording change / Requires evidence revision / Remove from release, plus any required change): _______________________________________

### 3. `DEP_CHOLESTYRAMINE_VITAMIND`

- Medication / class: Cholestyramine (bile-acid sequestrant) (`drug:2447`)
- Nutrient: Vitamin D (`vitamin_d`)
- Relationship: `depletion`; severity `moderate`; onset `months`

Consumer-visible card copy (every line below is shown to the user — approval covers all of it):

- Headline (`alert_headline`): May lower vitamin D absorption
- Body (`alert_body`): With prolonged use, cholestyramine can reduce Vitamin D absorption because bile supports uptake of fat-soluble vitamins.
- Monitoring tip (`monitoring_tip_short`): Ask whether a water-miscible vitamin D form and laboratory monitoring fit prolonged treatment.
- What can happen (`clinical_impact`): Lower Vitamin D absorption can matter during long-term cholestyramine use, especially when dietary intake is limited or another condition already impairs fat absorption.
- From food (`food_sources_short`): _(not set)_
- Why (`mechanism`): Cholestyramine binds bile acids in the gut and can interfere with fat digestion and absorption. Because Vitamin D is fat-soluble, long-term bile-acid binding can reduce absorption unless vitamin timing is managed.
- Clinical guidance (`recommendation`): For long-term use, ask whether a water-miscible vitamin D form is appropriate. The label directs other medicines at least 1 hour before or 4–6 hours after cholestyramine; confirm how to time the vitamin.

- Evidence: [DailyMed — CHOLESTYRAMINE prescribing information](https://dailymed.nlm.nih.gov/dailymed/drugInfo.cfm?setid=09420793-7357-4194-8172-0b1cddb167fe)

Reviewer disposition: **`approved`**
Review note: Approved as written: label-specific formulation, timing, and individualized monitoring align.
Consumer-visible after review: **yes**

Reviewer comment (Approved / Approved with wording change / Requires evidence revision / Remove from release, plus any required change): _______________________________________

### 4. `DEP_CHOLESTYRAMINE_VITAMINE`

- Medication / class: Cholestyramine (bile-acid sequestrant) (`drug:2447`)
- Nutrient: Vitamin E (`vitamin_e`)
- Relationship: `depletion`; severity `moderate`; onset `months`

Consumer-visible card copy (every line below is shown to the user — approval covers all of it):

- Headline (`alert_headline`): May lower vitamin E absorption
- Body (`alert_body`): With prolonged use, cholestyramine can reduce Vitamin E absorption because bile supports uptake of fat-soluble vitamins.
- Monitoring tip (`monitoring_tip_short`): Ask whether a water-miscible vitamin E form and clinical monitoring fit prolonged treatment.
- What can happen (`clinical_impact`): Lower Vitamin E absorption can matter during long-term cholestyramine use, especially when dietary intake is limited or another condition already impairs fat absorption.
- From food (`food_sources_short`): _(not set)_
- Why (`mechanism`): Cholestyramine binds bile acids in the gut and can interfere with fat digestion and absorption. Because Vitamin E is fat-soluble, long-term bile-acid binding can reduce absorption unless vitamin timing is managed.
- Clinical guidance (`recommendation`): For long-term use, ask whether a water-miscible vitamin E form is appropriate. The label directs other medicines at least 1 hour before or 4–6 hours after cholestyramine; confirm how to time the vitamin.

- Evidence: [DailyMed — CHOLESTYRAMINE prescribing information](https://dailymed.nlm.nih.gov/dailymed/drugInfo.cfm?setid=09420793-7357-4194-8172-0b1cddb167fe)

Reviewer disposition: **`approved`**
Review note: Approved as written: label-specific formulation, timing, and individualized monitoring align.
Consumer-visible after review: **yes**

Reviewer comment (Approved / Approved with wording change / Requires evidence revision / Remove from release, plus any required change): _______________________________________

### 5. `DEP_CHOLESTYRAMINE_VITAMINK`

- Medication / class: Cholestyramine (bile-acid sequestrant) (`drug:2447`)
- Nutrient: Vitamin K (`vitamin_k`)
- Relationship: `depletion`; severity `moderate`; onset `months`

Consumer-visible card copy (every line below is shown to the user — approval covers all of it):

- Headline (`alert_headline`): May lower vitamin K absorption
- Body (`alert_body`): With prolonged use, cholestyramine can reduce Vitamin K absorption because bile supports uptake of fat-soluble vitamins.
- Monitoring tip (`monitoring_tip_short`): Ask whether a water-miscible vitamin K form and clotting assessment fit prolonged treatment.
- What can happen (`clinical_impact`): Lower Vitamin K absorption can impair clotting. The label reports increased bleeding tendency related to low prothrombin in some long-term users, which requires clinician assessment.
- From food (`food_sources_short`): _(not set)_
- Why (`mechanism`): Cholestyramine binds bile acids in the gut and can interfere with fat digestion and absorption. Because Vitamin K is fat-soluble, long-term bile-acid binding can reduce absorption unless vitamin timing is managed.
- Clinical guidance (`recommendation`): For long-term use, ask whether a water-miscible vitamin K form is appropriate. The label directs other medicines at least 1 hour before or 4–6 hours after cholestyramine; confirm how to time the vitamin.

- Evidence: [DailyMed — CHOLESTYRAMINE prescribing information](https://dailymed.nlm.nih.gov/dailymed/drugInfo.cfm?setid=09420793-7357-4194-8172-0b1cddb167fe)

Reviewer disposition: **`approved`**
Review note: Approved as written: formulation, timing, and label-supported hypoprothrombinemia/bleeding framing align.
Consumer-visible after review: **yes**

Reviewer comment (Approved / Approved with wording change / Requires evidence revision / Remove from release, plus any required change): _______________________________________

### 6. `DEP_DIURETICS_THIAMINE`

- Medication / class: Furosemide (Lasix) (`drug:4603`)
- Nutrient: Thiamin (`thiamin`)
- Relationship: `depletion`; severity `significant`; onset `months`

Consumer-visible card copy (every line below is shown to the user — approval covers all of it):

- Headline (`alert_headline`): Furosemide may lower thiamine over time
- Body (`alert_body`): Furosemide increases urinary thiamine loss. Clinical relevance is greatest with long-term higher doses and other deficiency risks.
- Monitoring tip (`monitoring_tip_short`): With long-term higher-dose furosemide, ask your treating clinician whether thiamine assessment fits your care.
- What can happen (`clinical_impact`): Lower thiamine status is most plausible with chronic, higher-dose furosemide and additional risks such as heart failure or poor intake. The evidence does not establish deficiency in every person taking furosemide.
- From food (`food_sources_short`): Food sources of thiamine include pork, fish, whole grains, fortified cereals, beans, lentils, and seeds.
- Why (`mechanism`): Furosemide increases urinary thiamine loss largely by increasing urine flow. Studies in heart failure also report low thiamine status, although illness severity and dietary intake can contribute.
- Clinical guidance (`recommendation`): With chronic higher-dose furosemide, poor intake, or symptoms compatible with deficiency, ask the treating clinician whether thiamine assessment or supplementation is appropriate. Do not change the diuretic on your own.

- Evidence: [Seligmann H et al. Thiamine deficiency in patients with congestive heart failure receiving long-term furosemide therapy: a pilot study. Am J Med. 1991](https://pubmed.ncbi.nlm.nih.gov/1867241/); [Zenuk C et al. Thiamine deficiency in congestive heart failure patients receiving long term furosemide therapy. Can J Clin Pharmacol. 2003](https://pubmed.ncbi.nlm.nih.gov/14712323/); [Hanninen SA et al. The prevalence of thiamin deficiency in hospitalized patients with congestive heart failure. J Am Coll Cardiol. 2006](https://pubmed.ncbi.nlm.nih.gov/16412860/); [Rieck J et al. Urinary loss of thiamine is increased by low doses of furosemide in healthy volunteers. J Lab Clin Med. 1999](https://pubmed.ncbi.nlm.nih.gov/10482308/)

Reviewer disposition: **`approved`**
Review note: Approved as written: confounding-aware scope and treating-clinician assessment avoid routine supplementation.
Consumer-visible after review: **yes**

Reviewer comment (Approved / Approved with wording change / Requires evidence revision / Remove from release, plus any required change): _______________________________________

### 7. `DEP_LEVOTHYROXINE_CALCIUM`

- Medication / class: Levothyroxine (thyroid hormone replacement) (`drug:10582`)
- Nutrient: Calcium (`calcium`)
- Relationship: `supplement_interaction`; severity `moderate`; onset `weeks`

Consumer-visible card copy (every line below is shown to the user — approval covers all of it):

- Headline (`alert_headline`): Calcium can reduce thyroid-med absorption
- Body (`alert_body`): Over time, calcium supplements taken close to levothyroxine can reduce thyroid-medicine absorption.
- Monitoring tip (`monitoring_tip_short`): Consider taking levothyroxine at least 4 hours apart from calcium supplements or calcium-containing medicines.
- What can happen (`clinical_impact`): In 20 patients with hypothyroidism, taking 1,200 mg/day of elemental calcium as calcium carbonate with levothyroxine for three months increased mean TSH from 1.6 to 2.7 mIU/L; 20% had TSH above the normal range. Calcium can therefore reduce thyroid-drug absorption and lead to inadequate control in some patients.
- From food (`food_sources_short`): Food sources of calcium include dairy, fortified plant milks, leafy greens, almonds, and canned sardines or salmon with bones.
- Why (`mechanism`): Calcium supplements and calcium-containing medicines can bind levothyroxine in the gastrointestinal tract and reduce its absorption. This affects thyroid-drug bioavailability rather than depleting body calcium stores.
- Clinical guidance (`recommendation`): Take calcium supplements and calcium-containing medicines at least 4 hours before or after levothyroxine. Continue taking levothyroxine on an empty stomach as directed. The 4-hour separation here applies to calcium supplements and medicines; ordinary foods still follow your usual levothyroxine meal-timing instructions.

- Evidence: [Singh N et al. Effect of calcium carbonate on the absorption of levothyroxine. JAMA. 2000;283(21):2822-5](https://pubmed.ncbi.nlm.nih.gov/10838651/); [Singh N et al. The acute effect of calcium carbonate on the intestinal absorption of levothyroxine. Thyroid. 2001;11(10):967-71](https://pubmed.ncbi.nlm.nih.gov/11716045/); [DailyMed — Levothyroxine Sodium prescribing information (calcium and iron separation)](https://dailymed.nlm.nih.gov/dailymed/lookup.cfm?setid=a8db0f7d-8863-9309-e053-2995a90a284a)

Reviewer disposition: **`approved_with_wording_change`**
Review note: Applied the exact supplied action copy separating calcium products by four hours while preserving empty-stomach meal-timing instructions.
Consumer-visible after review: **yes**

Reviewer comment (Approved / Approved with wording change / Requires evidence revision / Remove from release, plus any required change): _______________________________________

### 8. `DEP_LEVOTHYROXINE_IRON`

- Medication / class: Levothyroxine (thyroid hormone replacement) (`drug:10582`)
- Nutrient: Iron (`iron`)
- Relationship: `supplement_interaction`; severity `moderate`; onset `weeks`

Consumer-visible card copy (every line below is shown to the user — approval covers all of it):

- Headline (`alert_headline`): Iron can reduce thyroid-med absorption
- Body (`alert_body`): Iron taken near your thyroid medication can gradually reduce absorption of the dose over weeks. Separating them by several hours usually solves it.
- Monitoring tip (`monitoring_tip_short`): Consider taking iron at least 4 hours apart from your levothyroxine dose.
- What can happen (`clinical_impact`): Co-administration can lead to inadequate thyroid hormone levels and a return of hypothyroid symptoms; the effect is variable but clinically significant in some patients.
- From food (`food_sources_short`): Food sources of iron include red meat, poultry, seafood, beans, lentils, tofu, spinach, and fortified cereals.
- Why (`mechanism`): Iron supplements can bind levothyroxine in the gut and reduce its absorption. In a small uncontrolled 12-week study of 14 patients with hypothyroidism, taking ferrous sulfate with levothyroxine raised mean TSH from 1.6 to 5.4 mU/L.
- Clinical guidance (`recommendation`): Take iron supplements at least 4 hours before or after levothyroxine. If you start or stop iron, ask your clinician about rechecking your thyroid levels.

- Evidence: [Campbell NR et al. Ferrous sulfate reduces thyroxine efficacy in patients with hypothyroidism. Ann Intern Med. 1992;117(12):1010-3](https://pubmed.ncbi.nlm.nih.gov/1443969/); [DailyMed — Levothyroxine Sodium prescribing information (calcium and iron separation)](https://www.dailymed.nlm.nih.gov/dailymed/fda/fdaDrugXsl.cfm?setid=a0dbd009-0a3e-4314-812f-dd372c255bb1&type=display)

Reviewer disposition: **`approved`**
Review note: Approved as written: Campbell 1992 is accurately described as an uncontrolled 14-patient study.
Consumer-visible after review: **yes**

Reviewer comment (Approved / Approved with wording change / Requires evidence revision / Remove from release, plus any required change): _______________________________________

### 9. `DEP_ORLISTAT_VITAMINA`

- Medication / class: Orlistat (fat-blocking weight-loss medication) (`drug:37925`)
- Nutrient: Vitamin A (`vitamin_a`)
- Relationship: `depletion`; severity `moderate`; onset `months`

Consumer-visible card copy (every line below is shown to the user — approval covers all of it):

- Headline (`alert_headline`): May lower vitamin A absorption
- Body (`alert_body`): Orlistat can gradually reduce absorption of Vitamin A over months because this vitamin depends on dietary fat for uptake. Timing a multivitamin away from the dose helps.
- Monitoring tip (`monitoring_tip_short`): Take the multivitamin 2 hours apart; ask your prescriber promptly if pregnant because orlistat is contraindicated.
- What can happen (`clinical_impact`): Orlistat can lower absorption of fat-soluble vitamins. Its label recommends a daily multivitamin; excess preformed vitamin A can cause birth defects, so pregnancy or possible pregnancy requires clinician review of the vitamin A form and total dose.
- From food (`food_sources_short`): _(not set)_
- Why (`mechanism`): Orlistat inhibits gastrointestinal lipases and reduces absorption of dietary fat. Because Vitamin A is fat-soluble, lower fat absorption can reduce uptake unless vitamin intake is separated from the orlistat dose.
- Clinical guidance (`recommendation`): Take the daily multivitamin recommended in the orlistat label—containing vitamins A, D, E, and K plus beta-carotene—at least 2 hours before or after orlistat, such as at bedtime. Do not add extra vitamin A unless your clinician recommends it. Orlistat is contraindicated during pregnancy; if you are pregnant or may be pregnant, contact the prescriber promptly and review the vitamin A form and total dose.

- Evidence: [DailyMed — XENICAL (orlistat) prescribing information](https://dailymed.nlm.nih.gov/dailymed/lookup.cfm?setid=6240792b-9224-2d10-e053-2a91aa0a2c3e); [NIH ODS — Vitamin A Fact Sheet for Health Professionals](https://ods.od.nih.gov/factsheets/VitaminA-HealthProfessional/)

Reviewer disposition: **`approved_with_wording_change`**
Review note: Applied the exact supplied daily-multivitamin, bedtime, no-extra-vitamin-A, and pregnancy-contraindication action copy.
Consumer-visible after review: **yes**

Reviewer comment (Approved / Approved with wording change / Requires evidence revision / Remove from release, plus any required change): _______________________________________

### 10. `DEP_SSRIS_SODIUM`

- Medication / class: SSRIs (antidepressants) (`class:ssris`)
- Nutrient: Sodium (`sodium`)
- Relationship: `monitoring_stability`; severity `significant`; onset `weeks`

Consumer-visible card copy (every line below is shown to the user — approval covers all of it):

- Headline (`alert_headline`): SSRIs can rarely lower blood sodium
- Body (`alert_body`): During the first weeks after starting an SSRI, low-sodium risk is higher with older age, thiazide use, or prior hyponatremia.
- Monitoring tip (`monitoring_tip_short`): Ask whether early sodium monitoring fits your risk factors; report new symptoms promptly.
- What can happen (`clinical_impact`): Risk is highest soon after starting an SSRI and in older adults, people taking thiazide diuretics, and those with prior hyponatremia. Severe hyponatremia can cause marked confusion, seizures, or reduced consciousness.
- From food (`food_sources_short`): _(not set)_
- Why (`mechanism`): SSRIs are associated with SIADH and dilutional hyponatremia, in which excess water lowers blood sodium. Serotonergic effects on antidiuretic hormone are proposed, but the exact mechanism is not fully established.
- Clinical guidance (`recommendation`): If you have hyponatremia risk factors, your prescriber may check sodium at baseline and during early treatment. Report new nausea, headache, unsteadiness, or confusion promptly; seizures or reduced consciousness require urgent care. This is not treated by self-supplementing sodium.

- Evidence: [De Picker L et al. Antidepressants and the risk of hyponatremia: a class-by-class review of literature. Psychosomatics. 2014;55(6):536-47](https://pubmed.ncbi.nlm.nih.gov/25262043/); [DailyMed — Sertraline prescribing information (hyponatremia symptoms and risk groups)](https://dailymed.nlm.nih.gov/dailymed/drugInfo.cfm?audience=consumer&setid=4883ccdf-0e02-579d-e054-00144ff88e88); [Leth-Møller KB et al. Antidepressants and the risk of hyponatremia: a Danish register-based population study. BMJ Open. 2016](https://pubmed.ncbi.nlm.nih.gov/27194321/)

Reviewer disposition: **`requires_evidence_revision`**
Review note: Added the sertraline label and Leth-Møller 2016; narrowed all onset copy to treatment initiation rather than unsupported class-wide dose increases.
Consumer-visible after review: **yes**

Reviewer comment (Approved / Approved with wording change / Requires evidence revision / Remove from release, plus any required change): _______________________________________

### 11. `DEP_ANTICOAGULANTS_VITAMINK`

- Medication / class: Warfarin (anticoagulant / blood thinner) (`drug:11289`)
- Nutrient: Vitamin K (`vitamin_k`)
- Relationship: `functional_antagonism`; severity `significant`; onset `days`

Consumer-visible card copy (every line below is shown to the user — approval covers all of it):

- Headline (`alert_headline`): Warfarin is sensitive to vitamin K changes
- Body (`alert_body`): Warfarin blocks vitamin K recycling as part of its intended action; sudden diet or supplement changes can shift the INR within days.
- Monitoring tip (`monitoring_tip_short`): Consider keeping your vitamin K intake steady day to day; discuss changes with your prescriber.
- What can happen (`clinical_impact`): Large or sudden changes in vitamin K intake can change the INR and make warfarin less or more anticoagulant, increasing clotting or bleeding risk. Consistency matters more than avoiding vitamin K-rich foods.
- From food (`food_sources_short`): _(not set)_
- Why (`mechanism`): Warfarin inhibits vitamin K epoxide reductase (VKORC1), reducing the recycling of vitamin K needed to activate clotting factors II, VII, IX, and X and proteins C and S. This is warfarin's intended drug action, not dietary vitamin K deficiency.
- Clinical guidance (`recommendation`): Keep vitamin K intake reasonably consistent. Contact the warfarin prescriber or anticoagulation service before starting or stopping vitamin K supplements or making a major dietary change; do not change warfarin on your own.

- Evidence: [Hirsh J et al. Oral anticoagulants: mechanism of action, clinical effectiveness, and optimal therapeutic range. Chest. 2001](https://pubmed.ncbi.nlm.nih.gov/11157640/); [DailyMed — Warfarin Sodium prescribing information (consistent vitamin K intake)](https://dailymed.nlm.nih.gov/dailymed/fda/fdaDrugXsl.cfm?setid=801e4da1-5459-47d2-b67b-009f0a3247cc&type=display)

Reviewer disposition: **`approved`**
Review note: Approved as written: functional antagonism, days-scale onset, and consistent-intake guidance align.
Consumer-visible after review: **yes**

Reviewer comment (Approved / Approved with wording change / Requires evidence revision / Remove from release, plus any required change): _______________________________________

## Sign-off

- Reviewer: `PharmaGuide Clinical Team` (Clinical evidence-QA delta review; final licensed pharmacist sign-off pending)
- Review date: `2026-07-30`
- Release disposition: `hold_pending_2_record_rereview_and_presentation_review`
- Evidence auditor: `b1_delta_pharmacist_response_evidence_reconciliation` (AI clinical-content audit)
- Licensed clinical approver organization: `PharmaGuide Clinical Team`
- Licensed pharmacist sign-off: **not represented by this packet**
- Scope statement: This packet requests licensed-pharmacist review of the documented evidence audit; it does not record release approval or claim professional licensure.
