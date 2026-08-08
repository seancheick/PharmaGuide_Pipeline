# Drug-class consumer-copy review packet (vocab v1.1.0)

Status: **drafted, pending clinician (Dr Pham) sign-off — nothing ships to the app until approval**

Scope: **two NEW sheet-facing fields on all 30 drug-class entries: `group_label` + `commonly_used_for`.** Existing `name`/`notes`/`examples` copy is NOT part of this review (unchanged, previously approved for the profile checklist).

Artifact: `scripts/data/drug_class_vocab.json`, schema `1.1.0`, authored `2026-08-08`, content hash `sha256:b0a62a68763f89d956875d8efc443aef39687f544d387d1ed11f614fb2b31f78`. If the file hash changes after edits, regenerate this packet before signing.

## Why these fields exist

The Flutter medication details sheet (`lib/features/stack/v2/widgets/medication_details_sheet.dart`) renders no medication education today, because `name`/`notes` were authored for the onboarding checklist ("Metformin, Ozempic, etc. (rarely cause low blood sugar)") and read wrong as a classification shown back to the user. `group_label` is the clean classification noun; `commonly_used_for` is one sentence of consumer education. Both render **verbatim** in the app; content is bundled on-device (no runtime lookups, by privacy design).

## Review contract

- Phrasing is deliberately **"Commonly used …", never "treats"** — off-label reality (amitriptyline for migraine, propranolol for anxiety). A contract test enforces this; if a sentence needs "treat", flag it instead so we adjust the contract consciously.

- Sentences must not box the user into a diagnosis; class-level purpose only.

- Suggested sources: **MedlinePlus consumer monographs** for the example drugs listed under each entry, and the **FDA Established Pharmacologic Class** on those drugs' labels.

- Dispositions per entry: `approved` | `approved_with_wording_change` (write the wording) | `requires_revision`.

- `group_label` is deliberately not unique — related classes share a consumer bucket (all four anticoagulant-family classes read "Blood thinners").

## Entries

### 1. `anticoagulants` — user-selectable

- Checklist name (existing, unchanged): Blood thinners
- **group_label (NEW):** Blood thinners
- **commonly_used_for (NEW):** Commonly used to help prevent harmful blood clots, such as with atrial fibrillation or after a previous clot.
- Example drugs (for source lookup): warfarin (Coumadin), apixaban (Eliquis), rivaroxaban (Xarelto)
- Disposition: ______

### 2. `antiplatelets` — user-selectable

- Checklist name (existing, unchanged): Antiplatelet medication
- **group_label (NEW):** Blood thinners
- **commonly_used_for (NEW):** Commonly used to help prevent heart attack and stroke by keeping platelets from clumping into clots.
- Example drugs (for source lookup): aspirin (low-dose daily), clopidogrel (Plavix), prasugrel (Effient)
- Disposition: ______

### 3. `nsaids` — user-selectable

- Checklist name (existing, unchanged): NSAIDs (Ibuprofen, Aspirin regularly)
- **group_label (NEW):** Pain and inflammation relievers
- **commonly_used_for (NEW):** Commonly used to help relieve pain, fever, and inflammation.
- Example drugs (for source lookup): ibuprofen (Advil, Motrin), naproxen (Aleve), celecoxib (Celebrex)
- Disposition: ______

### 4. `antihypertensives` — user-selectable

- Checklist name (existing, unchanged): Blood pressure medication
- **group_label (NEW):** Blood pressure medications
- **commonly_used_for (NEW):** Commonly used to help lower high blood pressure and reduce strain on the heart and blood vessels.
- Example drugs (for source lookup): lisinopril, amlodipine, losartan
- Disposition: ______

### 5. `hypoglycemics_high_risk` — user-selectable

- Checklist name (existing, unchanged): Insulin or sulfonylureas (can cause low blood sugar)
- **group_label (NEW):** Diabetes medications
- **commonly_used_for (NEW):** Commonly used to help manage blood sugar in diabetes; insulin is used in type 1 and type 2 diabetes, while sulfonylureas are used in type 2 diabetes.
- Example drugs (for source lookup): insulin (all types), glipizide (Glucotrol), glyburide (Micronase)
- Disposition: ______

### 6. `hypoglycemics_lower_risk` — user-selectable

- Checklist name (existing, unchanged): Metformin, Ozempic, etc. (rarely cause low blood sugar)
- **group_label (NEW):** Diabetes medications
- **commonly_used_for (NEW):** Commonly used to help manage blood sugar in type 2 diabetes; some are also used for weight management.
- Example drugs (for source lookup): metformin (Glucophage), semaglutide (Ozempic, Wegovy), liraglutide (Victoza)
- Disposition: ______

### 7. `hypoglycemics_unknown` — user-selectable

- Checklist name (existing, unchanged): Not sure / other diabetes medication
- **group_label (NEW):** Diabetes medications
- **commonly_used_for (NEW):** Commonly used to help manage blood sugar in diabetes.
- Example drugs (for source lookup): Please select Insulin/Sulfonylureas or Metformin/GLP-1 RAs above
- Disposition: ______

### 8. `thyroid_medications` — user-selectable

- Checklist name (existing, unchanged): Thyroid medication
- **group_label (NEW):** Thyroid hormone medications
- **commonly_used_for (NEW):** Commonly used to replace thyroid hormone when the body does not make enough.
- Example drugs (for source lookup): levothyroxine (Synthroid, Levoxyl), liothyronine (Cytomel), armour thyroid
- Disposition: ______

### 9. `sedatives` — user-selectable

- Checklist name (existing, unchanged): Sedatives / Sleep medication
- **group_label (NEW):** Sleep and anxiety medications
- **commonly_used_for (NEW):** Commonly used to help with sleep or to ease anxiety.
- Example drugs (for source lookup): zolpidem (Ambien), alprazolam (Xanax), diazepam (Valium)
- Disposition: ______

### 10. `immunosuppressants` — user-selectable

- Checklist name (existing, unchanged): Immunosuppressants
- **group_label (NEW):** Immune-suppressing medications
- **commonly_used_for (NEW):** Commonly used to help calm an overactive immune system, such as after an organ transplant or in autoimmune conditions.
- Example drugs (for source lookup): tacrolimus, cyclosporine, mycophenolate
- Disposition: ______

### 11. `statins` — user-selectable

- Checklist name (existing, unchanged): Statins / Cholesterol medication
- **group_label (NEW):** Cholesterol medications
- **commonly_used_for (NEW):** Commonly used to help lower cholesterol and reduce the risk of heart attack and stroke.
- Example drugs (for source lookup): atorvastatin (Lipitor), simvastatin (Zocor), rosuvastatin (Crestor)
- Disposition: ______

### 12. `antidepressants_ssri_snri` — user-selectable

- Checklist name (existing, unchanged): Antidepressants (SSRIs/SNRIs)
- **group_label (NEW):** Antidepressants
- **commonly_used_for (NEW):** Commonly used to help manage depression and anxiety; some are also used for nerve pain or other conditions.
- Example drugs (for source lookup): sertraline (Zoloft), escitalopram (Lexapro), fluoxetine (Prozac)
- Disposition: ______

### 13. `maois` — user-selectable

- Checklist name (existing, unchanged): MAOIs
- **group_label (NEW):** Antidepressants
- **commonly_used_for (NEW):** Commonly used for depression in selected situations; some MAO inhibitors are also used for Parkinson's disease.
- Example drugs (for source lookup): phenelzine (Nardil), tranylcypromine (Parnate), selegiline (Eldepryl)
- Disposition: ______

### 14. `serotonergic_medications` — user-selectable

- Checklist name (existing, unchanged): Other serotonergic medication
- **group_label (NEW):** Serotonin-affecting medications
- **commonly_used_for (NEW):** Commonly used for different purposes, including depression, pain, migraine, and certain infections; these medicines share clinically relevant effects on serotonin.
- Example drugs (for source lookup): linezolid (Zyvox), amitriptyline, tramadol
- Disposition: ______

### 15. `cardiac_glycosides` — user-selectable

- Checklist name (existing, unchanged): Digoxin / Heart rhythm medication
- **group_label (NEW):** Heart medications
- **commonly_used_for (NEW):** Commonly used to help control heart rate in atrial fibrillation and to improve symptoms in some people with heart failure.
- Example drugs (for source lookup): digoxin (Lanoxin), digitoxin
- Disposition: ______

### 16. `anticholinergics` — user-selectable

- Checklist name (existing, unchanged): Anticholinergic medication
- **group_label (NEW):** Anticholinergic medications
- **commonly_used_for (NEW):** Commonly used for conditions such as allergies, overactive bladder, motion sickness, or sleep problems; these medicines share anticholinergic effects.
- Example drugs (for source lookup): diphenhydramine (Benadryl), oxybutynin, amitriptyline
- Disposition: ______

### 17. `anticonvulsants` — rule-only (assigned by classification, not picked by user)

- Checklist name (existing, unchanged): Anti-seizure medication
- **group_label (NEW):** Seizure medications
- **commonly_used_for (NEW):** Commonly used to help prevent seizures, and also for nerve pain, migraine prevention, or mood stabilization.
- Example drugs (for source lookup): levetiracetam (Keppra), lamotrigine, valproate
- Disposition: ______

### 18. `antiarrhythmics` — rule-only (assigned by classification, not picked by user)

- Checklist name (existing, unchanged): Antiarrhythmic medication
- **group_label (NEW):** Heart rhythm medications
- **commonly_used_for (NEW):** Commonly used to help keep the heart in a steady rhythm.
- Example drugs (for source lookup): amiodarone, flecainide, sotalol
- Disposition: ______

### 19. `calcium_channel_blockers` — rule-only (assigned by classification, not picked by user)

- Checklist name (existing, unchanged): Calcium channel blockers
- **group_label (NEW):** Blood pressure medications
- **commonly_used_for (NEW):** Commonly used to help lower blood pressure or relieve chest pain (angina); some also help control heart rate.
- Example drugs (for source lookup): amlodipine, nifedipine, diltiazem
- Disposition: ______

### 20. `thiazide_diuretics` — rule-only (assigned by classification, not picked by user)

- Checklist name (existing, unchanged): Thiazide diuretics
- **group_label (NEW):** Blood pressure medications
- **commonly_used_for (NEW):** Commonly used to help lower blood pressure by moving extra salt and water out of the body.
- Example drugs (for source lookup): hydrochlorothiazide (HCTZ), chlorthalidone, indapamide
- Disposition: ______

### 21. `lithium` — rule-only (assigned by classification, not picked by user)

- Checklist name (existing, unchanged): Lithium
- **group_label (NEW):** Mood stabilizers
- **commonly_used_for (NEW):** Commonly used to help stabilize mood in bipolar disorder.
- Example drugs (for source lookup): lithium carbonate (Lithobid, Eskalith)
- Disposition: ______

### 22. `oral_contraceptives` — rule-only (assigned by classification, not picked by user)

- Checklist name (existing, unchanged): Oral contraceptives
- **group_label (NEW):** Birth control pills
- **commonly_used_for (NEW):** Commonly used to prevent pregnancy, and sometimes to help with acne or irregular periods.
- Example drugs (for source lookup): estradiol-containing combo pills, norethindrone, drospirenone-containing pills
- Disposition: ______

### 23. `cyp2d6_substrates` — rule-only (assigned by classification, not picked by user)

- Checklist name (existing, unchanged): CYP2D6-substrate drugs
- **group_label (NEW):** Medications processed by the CYP2D6 enzyme
- **commonly_used_for (NEW):** Commonly used for many different conditions, from pain to blood pressure to mood; these medicines are all affected by how the CYP2D6 enzyme processes them.
- Example drugs (for source lookup): codeine, tramadol, metoprolol
- Disposition: ______

### 24. `cyp3a4_substrates` — rule-only (assigned by classification, not picked by user)

- Checklist name (existing, unchanged): CYP3A4-substrate drugs
- **group_label (NEW):** Medications processed by the CYP3A4 enzyme
- **commonly_used_for (NEW):** Commonly used for many different conditions, from cholesterol to blood pressure to sleep; these medicines are all affected by CYP3A4 metabolism.
- Example drugs (for source lookup): statins (most), many calcium channel blockers, tacrolimus
- Disposition: ______

### 25. `doacs` — rule-only (assigned by classification, not picked by user)

- Checklist name (existing, unchanged): DOAC blood thinners
- **group_label (NEW):** Blood thinners
- **commonly_used_for (NEW):** Commonly used to help prevent stroke and blood clots, such as with atrial fibrillation or after a previous clot.
- Example drugs (for source lookup): Eliquis, Xarelto, Pradaxa
- Disposition: ______

### 26. `potassium_sparing_diuretics` — rule-only (assigned by classification, not picked by user)

- Checklist name (existing, unchanged): Potassium-sparing diuretics
- **group_label (NEW):** Potassium-sparing medications
- **commonly_used_for (NEW):** Commonly used for conditions such as high blood pressure, heart failure, kidney disease, or certain hormone-related conditions; these medicines tend to preserve or raise potassium.
- Example drugs (for source lookup): spironolactone, eplerenone, finerenone
- Disposition: ______

### 27. `tetracycline_antibiotics` — rule-only (assigned by classification, not picked by user)

- Checklist name (existing, unchanged): Tetracycline antibiotics
- **group_label (NEW):** Antibiotics
- **commonly_used_for (NEW):** Commonly used for certain bacterial infections, including tick-borne infections, and for conditions such as acne.
- Example drugs (for source lookup): doxycycline, tetracycline, minocycline
- Disposition: ______

### 28. `beta_blockers` — rule-only (assigned by classification, not picked by user)

- Checklist name (existing, unchanged): Beta blockers
- **group_label (NEW):** Heart and blood pressure medications
- **commonly_used_for (NEW):** Commonly used to help slow the heart rate and lower blood pressure, and sometimes for migraine prevention or anxiety.
- Example drugs (for source lookup): nadolol, metoprolol, atenolol
- Disposition: ______

### 29. `fluoroquinolones` — rule-only (assigned by classification, not picked by user)

- Checklist name (existing, unchanged): Fluoroquinolone antibiotics
- **group_label (NEW):** Antibiotics
- **commonly_used_for (NEW):** Commonly used for certain bacterial infections, including some urinary and respiratory infections.
- Example drugs (for source lookup): ciprofloxacin, levofloxacin, moxifloxacin
- Disposition: ______

### 30. `vitamin_k_antagonists` — rule-only (assigned by classification, not picked by user)

- Checklist name (existing, unchanged): Warfarin-type blood thinners
- **group_label (NEW):** Blood thinners
- **commonly_used_for (NEW):** Commonly used to help prevent blood clots, such as with atrial fibrillation, mechanical heart valves, or after a previous clot.
- Example drugs (for source lookup): warfarin (Coumadin), acenocoumarol, phenprocoumon
- Disposition: ______

---

After sign-off: set `_metadata.consumer_copy_review.status` to `approved` in `scripts/data/drug_class_vocab.json`, then repin the Flutter asset (`assets/data/drug_class_vocab.json`) and update the app drift-test metadata lock in the same commit. The app parser already tolerates the fields' absence, so the app render slot stays dormant until the repin.
