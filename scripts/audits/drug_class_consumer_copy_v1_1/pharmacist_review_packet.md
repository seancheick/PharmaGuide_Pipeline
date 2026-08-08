# Drug-class consumer-copy review packet (vocab v1.1.0)

Revision: **3 — round-2 correction applied (immunosuppressants), signed**

Status: **approved** — Dr Pham approved this revised copy on 2026-08-08. The strings below are cleared to render verbatim in the app. Any later edit to `group_label` or `commonly_used_for` invalidates the sign-off: reset the status and regenerate this packet before repinning the Flutter asset.

Scope: **two sheet-facing fields on all 30 drug-class entries: `group_label` + `commonly_used_for`.** Existing `name`/`notes`/`examples` copy is NOT part of this review (unchanged, previously approved for the profile checklist).

Artifact: `scripts/data/drug_class_vocab.json`, schema `1.1.0`, content hash `sha256:17fae67704ca37a91d7cad76212b1a0b4d725e4a193b9673faac022310208a36`. Regenerate this packet (`regenerate_packet.py`) if the file hash changes again before signing.

Review history: **round 1 — 16 approved as authored, 14 approved_with_wording_change (all applied). Round 2 — 29 approved at current wording, 1 approved_with_wording_change (applied). 0 requires_revision.**

## Why these fields exist

The Flutter medication details sheet (`lib/features/stack/v2/widgets/medication_details_sheet.dart`) renders no medication education today, because `name`/`notes` were authored for the onboarding checklist ("Metformin, Ozempic, etc. (rarely cause low blood sugar)") and read wrong as a classification shown back to the user. `group_label` is the clean classification noun; `commonly_used_for` is one sentence of consumer education. Both render **verbatim** in the app; content is bundled on-device (no runtime lookups, by privacy design).

## Review contract

- Phrasing is deliberately **"Commonly used …", never "treats"** — off-label reality (amitriptyline for migraine, propranolol for anxiety). A contract test enforces this.

- Sentences must not box the user into a diagnosis; class-level purpose only.

- `group_label` is deliberately not unique — related classes share a consumer bucket (all four anticoagulant-family classes read "Blood thinners", retained at review).

- The entry marked **REVISED round 2** carries the round-2 wording change; entries reworded in round 1 keep their round-1 rationale inline for provenance.

## Entries

### 1. `anticoagulants` — user-selectable

- Checklist name (existing, unchanged): Blood thinners
- **group_label:** Blood thinners
- **commonly_used_for:** Commonly used to help prevent harmful blood clots, such as with atrial fibrillation or after a previous clot.
- Example drugs (for source lookup): warfarin (Coumadin), apixaban (Eliquis), rivaroxaban (Xarelto)
- Disposition: approved at current wording (round 2)

### 2. `antiplatelets` — user-selectable

- Checklist name (existing, unchanged): Antiplatelet medication
- **group_label:** Blood thinners
- **commonly_used_for:** Commonly used to help prevent heart attack and stroke by keeping platelets from clumping into clots.
- Example drugs (for source lookup): aspirin (low-dose daily), clopidogrel (Plavix), prasugrel (Effient)
- Disposition: approved at current wording (round 2)

### 3. `nsaids` — user-selectable

- Checklist name (existing, unchanged): NSAIDs (Ibuprofen, Aspirin regularly)
- **group_label:** Pain and inflammation relievers
- **commonly_used_for:** Commonly used to help relieve pain, fever, and inflammation.
- Example drugs (for source lookup): ibuprofen (Advil, Motrin), naproxen (Aleve), celecoxib (Celebrex)
- Disposition: approved at current wording (round 2)

### 4. `antihypertensives` — user-selectable

- Checklist name (existing, unchanged): Blood pressure medication
- **group_label:** Blood pressure medications
- **commonly_used_for:** Commonly used to help lower high blood pressure and reduce strain on the heart and blood vessels.
- Example drugs (for source lookup): lisinopril, amlodipine, losartan
- Disposition: approved at current wording (round 2)

### 5. `hypoglycemics_high_risk` — user-selectable

- Checklist name (existing, unchanged): Insulin or sulfonylureas (can cause low blood sugar)
- **group_label:** Diabetes medications
- **commonly_used_for:** Commonly used to help manage blood sugar in diabetes; insulin is used in type 1 and type 2 diabetes, while sulfonylureas are used in type 2 diabetes.
- Example drugs (for source lookup): insulin (all types), glipizide (Glucotrol), glyburide (Micronase)
- Disposition: approved at current wording (round 2; wording set in round 1 — insulin spans type 1 + type 2; sulfonylureas are type 2 drugs)

### 6. `hypoglycemics_lower_risk` — user-selectable

- Checklist name (existing, unchanged): Metformin, Ozempic, etc. (rarely cause low blood sugar)
- **group_label:** Diabetes medications
- **commonly_used_for:** Commonly used to help manage blood sugar in type 2 diabetes; some are also used for weight management.
- Example drugs (for source lookup): metformin (Glucophage), semaglutide (Ozempic, Wegovy), liraglutide (Victoza)
- Disposition: approved at current wording (round 2; wording set in round 1 — GLP-1 agents are also used for weight management, not merely 'support')

### 7. `hypoglycemics_unknown` — user-selectable

- Checklist name (existing, unchanged): Not sure / other diabetes medication
- **group_label:** Diabetes medications
- **commonly_used_for:** Commonly used to help manage blood sugar in diabetes.
- Example drugs (for source lookup): Please select Insulin/Sulfonylureas or Metformin/GLP-1 RAs above
- Disposition: approved at current wording (round 2)

### 8. `thyroid_medications` — user-selectable

- Checklist name (existing, unchanged): Thyroid medication
- **group_label:** Thyroid hormone medications
- **commonly_used_for:** Commonly used to replace thyroid hormone when the body does not make enough.
- Example drugs (for source lookup): levothyroxine (Synthroid, Levoxyl), liothyronine (Cytomel), armour thyroid
- Disposition: approved at current wording (round 2; wording set in round 1 — examples are replacement hormones, not agents that 'balance' thyroid function)

### 9. `sedatives` — user-selectable

- Checklist name (existing, unchanged): Sedatives / Sleep medication
- **group_label:** Sleep and anxiety medications
- **commonly_used_for:** Commonly used to help with sleep or to ease anxiety.
- Example drugs (for source lookup): zolpidem (Ambien), alprazolam (Xanax), diazepam (Valium)
- Disposition: approved at current wording (round 2)

### 10. `immunosuppressants` — user-selectable

- Checklist name (existing, unchanged): Immunosuppressants
- **group_label:** Immune-suppressing medications
- **commonly_used_for:** Commonly used to reduce immune-system activity, such as to prevent organ transplant rejection or manage autoimmune conditions.
- Example drugs (for source lookup): tacrolimus, cyclosporine, mycophenolate
- Disposition: **approved_with_wording_change — REVISED round 2, applied.** Rationale: transplant use prevents rejection of the transplanted organ (MedlinePlus framing); 'overactive immune system' fit only the autoimmune half.

### 11. `statins` — user-selectable

- Checklist name (existing, unchanged): Statins / Cholesterol medication
- **group_label:** Cholesterol medications
- **commonly_used_for:** Commonly used to help lower cholesterol and reduce the risk of heart attack and stroke.
- Example drugs (for source lookup): atorvastatin (Lipitor), simvastatin (Zocor), rosuvastatin (Crestor)
- Disposition: approved at current wording (round 2)

### 12. `antidepressants_ssri_snri` — user-selectable

- Checklist name (existing, unchanged): Antidepressants (SSRIs/SNRIs)
- **group_label:** Antidepressants
- **commonly_used_for:** Commonly used to help manage depression and anxiety; some are also used for nerve pain or other conditions.
- Example drugs (for source lookup): sertraline (Zoloft), escitalopram (Lexapro), fluoxetine (Prozac)
- Disposition: approved at current wording (round 2; wording set in round 1 — separates the additional uses from the primary indication)

### 13. `maois` — user-selectable

- Checklist name (existing, unchanged): MAOIs
- **group_label:** Antidepressants
- **commonly_used_for:** Commonly used for depression in selected situations; some MAO inhibitors are also used for Parkinson's disease.
- Example drugs (for source lookup): phenelzine (Nardil), tranylcypromine (Parnate), selegiline (Eldepryl)
- Disposition: approved at current wording (round 2; wording set in round 1 — oral selegiline is a Parkinson's drug; transdermal is the antidepressant form)

### 14. `serotonergic_medications` — user-selectable

- Checklist name (existing, unchanged): Other serotonergic medication
- **group_label:** Serotonin-affecting medications
- **commonly_used_for:** Commonly used for different purposes, including depression, pain, migraine, and certain infections; these medicines share clinically relevant effects on serotonin.
- Example drugs (for source lookup): linezolid (Zyvox), amitriptyline, tramadol
- Disposition: approved at current wording (round 2; wording set in round 1 — interaction grouping, not a therapeutic class -- separates purpose from the shared serotonin property)

### 15. `cardiac_glycosides` — user-selectable

- Checklist name (existing, unchanged): Digoxin / Heart rhythm medication
- **group_label:** Heart medications
- **commonly_used_for:** Commonly used to help control heart rate in atrial fibrillation and to improve symptoms in some people with heart failure.
- Example drugs (for source lookup): digoxin (Lanoxin), digitoxin
- Disposition: approved at current wording (round 2; wording set in round 1 — rate control in AF + symptom improvement in HF; not 'a steady rhythm')

### 16. `anticholinergics` — user-selectable

- Checklist name (existing, unchanged): Anticholinergic medication
- **group_label:** Anticholinergic medications
- **commonly_used_for:** Commonly used for conditions such as allergies, overactive bladder, motion sickness, or sleep problems; these medicines share anticholinergic effects.
- Example drugs (for source lookup): diphenhydramine (Benadryl), oxybutynin, amitriptyline
- Disposition: approved at current wording (round 2; wording set in round 1 — names the shared anticholinergic property rather than implying one indication)

### 17. `anticonvulsants` — rule-only (assigned by classification, not picked by user)

- Checklist name (existing, unchanged): Anti-seizure medication
- **group_label:** Seizure medications
- **commonly_used_for:** Commonly used to help prevent seizures, and also for nerve pain, migraine prevention, or mood stabilization.
- Example drugs (for source lookup): levetiracetam (Keppra), lamotrigine, valproate
- Disposition: approved at current wording (round 2)

### 18. `antiarrhythmics` — rule-only (assigned by classification, not picked by user)

- Checklist name (existing, unchanged): Antiarrhythmic medication
- **group_label:** Heart rhythm medications
- **commonly_used_for:** Commonly used to help keep the heart in a steady rhythm.
- Example drugs (for source lookup): amiodarone, flecainide, sotalol
- Disposition: approved at current wording (round 2)

### 19. `calcium_channel_blockers` — rule-only (assigned by classification, not picked by user)

- Checklist name (existing, unchanged): Calcium channel blockers
- **group_label:** Blood pressure medications
- **commonly_used_for:** Commonly used to help lower blood pressure or relieve chest pain (angina); some also help control heart rate.
- Example drugs (for source lookup): amlodipine, nifedipine, diltiazem
- Disposition: approved at current wording (round 2; wording set in round 1 — class also includes rate/rhythm-control agents)

### 20. `thiazide_diuretics` — rule-only (assigned by classification, not picked by user)

- Checklist name (existing, unchanged): Thiazide diuretics
- **group_label:** Blood pressure medications
- **commonly_used_for:** Commonly used to help lower blood pressure by moving extra salt and water out of the body.
- Example drugs (for source lookup): hydrochlorothiazide (HCTZ), chlorthalidone, indapamide
- Disposition: approved at current wording (round 2)

### 21. `lithium` — rule-only (assigned by classification, not picked by user)

- Checklist name (existing, unchanged): Lithium
- **group_label:** Mood stabilizers
- **commonly_used_for:** Commonly used to help stabilize mood in bipolar disorder.
- Example drugs (for source lookup): lithium carbonate (Lithobid, Eskalith)
- Disposition: approved at current wording (round 2)

### 22. `oral_contraceptives` — rule-only (assigned by classification, not picked by user)

- Checklist name (existing, unchanged): Oral contraceptives
- **group_label:** Birth control pills
- **commonly_used_for:** Commonly used to prevent pregnancy, and sometimes to help with acne or irregular periods.
- Example drugs (for source lookup): estradiol-containing combo pills, norethindrone, drospirenone-containing pills
- Disposition: approved at current wording (round 2)

### 23. `cyp2d6_substrates` — rule-only (assigned by classification, not picked by user)

- Checklist name (existing, unchanged): CYP2D6-substrate drugs
- **group_label:** Medications processed by the CYP2D6 enzyme
- **commonly_used_for:** Commonly used for many different conditions, from pain to blood pressure to mood; these medicines are all affected by how the CYP2D6 enzyme processes them.
- Example drugs (for source lookup): codeine, tramadol, metoprolol
- Disposition: approved at current wording (round 2; wording set in round 1 — 'broken down by' is wrong: CYP2D6 can bioactivate (codeine); substrate exposure is the concept)

### 24. `cyp3a4_substrates` — rule-only (assigned by classification, not picked by user)

- Checklist name (existing, unchanged): CYP3A4-substrate drugs
- **group_label:** Medications processed by the CYP3A4 enzyme
- **commonly_used_for:** Commonly used for many different conditions, from cholesterol to blood pressure to sleep; these medicines are all affected by CYP3A4 metabolism.
- Example drugs (for source lookup): statins (most), many calcium channel blockers, tacrolimus
- Disposition: approved at current wording (round 2; wording set in round 1 — same substrate-vs-'broken down by' correction as CYP2D6)

### 25. `doacs` — rule-only (assigned by classification, not picked by user)

- Checklist name (existing, unchanged): DOAC blood thinners
- **group_label:** Blood thinners
- **commonly_used_for:** Commonly used to help prevent stroke and blood clots, such as with atrial fibrillation or after a previous clot.
- Example drugs (for source lookup): Eliquis, Xarelto, Pradaxa
- Disposition: approved at current wording (round 2)

### 26. `potassium_sparing_diuretics` — rule-only (assigned by classification, not picked by user)

- Checklist name (existing, unchanged): Potassium-sparing diuretics
- **group_label:** Potassium-sparing medications
- **commonly_used_for:** Commonly used for conditions such as high blood pressure, heart failure, kidney disease, or certain hormone-related conditions; these medicines tend to preserve or raise potassium.
- Example drugs (for source lookup): spironolactone, eplerenone, finerenone
- Disposition: approved at current wording (round 2; wording set in round 1 — finerenone is an MRA for CKD in type 2 diabetes -- 'water pills' misleads)

### 27. `tetracycline_antibiotics` — rule-only (assigned by classification, not picked by user)

- Checklist name (existing, unchanged): Tetracycline antibiotics
- **group_label:** Antibiotics
- **commonly_used_for:** Commonly used for certain bacterial infections, including tick-borne infections, and for conditions such as acne.
- Example drugs (for source lookup): doxycycline, tetracycline, minocycline
- Disposition: approved at current wording (round 2; wording set in round 1 — avoids implying these clear any bacterial infection)

### 28. `beta_blockers` — rule-only (assigned by classification, not picked by user)

- Checklist name (existing, unchanged): Beta blockers
- **group_label:** Heart and blood pressure medications
- **commonly_used_for:** Commonly used to help slow the heart rate and lower blood pressure, and sometimes for migraine prevention or anxiety.
- Example drugs (for source lookup): nadolol, metoprolol, atenolol
- Disposition: approved at current wording (round 2)

### 29. `fluoroquinolones` — rule-only (assigned by classification, not picked by user)

- Checklist name (existing, unchanged): Fluoroquinolone antibiotics
- **group_label:** Antibiotics
- **commonly_used_for:** Commonly used for certain bacterial infections, including some urinary and respiratory infections.
- Example drugs (for source lookup): ciprofloxacin, levofloxacin, moxifloxacin
- Disposition: approved at current wording (round 2; wording set in round 1 — drops sinusitis, which implied first-line status)

### 30. `vitamin_k_antagonists` — rule-only (assigned by classification, not picked by user)

- Checklist name (existing, unchanged): Warfarin-type blood thinners
- **group_label:** Blood thinners
- **commonly_used_for:** Commonly used to help prevent blood clots, such as with atrial fibrillation, mechanical heart valves, or after a previous clot.
- Example drugs (for source lookup): warfarin (Coumadin), acenocoumarol, phenprocoumon
- Disposition: approved at current wording (round 2)

---

## Sign-off

Reviewer: **Dr Pham**  Date: **2026-08-08**

The `group_label` + `commonly_used_for` layer at the content hash above is approved to render verbatim in the app. Recorded in `_metadata.consumer_copy_review` (`status: approved`).

Downstream: the Flutter asset `assets/data/drug_class_vocab.json` is repinned from this artifact, the app drift-test metadata lock moves with it in the same commit, and the medication details sheet renders `group_label` + `commonly_used_for` from the bundled asset only.
