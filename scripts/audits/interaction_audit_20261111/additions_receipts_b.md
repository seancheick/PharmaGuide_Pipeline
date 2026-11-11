# Interaction additions, batch B (proposal for PharmD review)

Prepared 2026-11-11 by an agent (agent research, not clinician review). Read-only against
`/Users/seancheick/worktrees/dsld-interaction-baseline`. No repo file was edited.
Raw source captures were kept locally during research and are not committed.

RxCUIs checked with `rxnav.nlm.nih.gov/REST/rxcui/ID/historystatus.json` (all Active, TTY IN):
4124 ethinyl estradiol, 4083 estradiol, 28439 lamotrigine, 21241 clobazam, 10582 levothyroxine,
3407 digoxin, 4917 nitroglycerin, 197 acetylcysteine, 32624 oxcarbazepine, 38404 topiramate,
8691 primidone, 6835 methimazole, 8794 propylthiouracil.

Source failures (one attempt each): MedlinePlus herb monographs `natural/866.html` (psyllium),
`natural/953.html` (ashwagandha) and `natural/1018.html` (NAC) all redirect to the herb landing page,
which says the Natural Medicines Comprehensive Database is unavailable. The MedlinePlus wording for
psyllium and digoxin (3 hours) therefore could not be checked.

---

## 1. CBD + clobazam, CBD + valproate

### Existing coverage
- `scripts/data/ingredient_interaction_rules.json` → `RULE_BANNED_CBD_INTERACTIONS` (subject
  `banned_recalled_ingredients::BANNED_CBD_US`), `drug_class_rules[drug_class_id=anticonvulsants]`,
  severity `caution`, evidence `established`, gate `drug_classes_any: [anticonvulsants, clobazam, valproate]`.
- Its condition rule `liver_disease` already names the valproate risk.
- No curated pair links CBD (`agent2_canonical_id: cbd`, C4704022) to clobazam or valproate. The CBD
  curated pairs cover only anticoagulants, antihypertensives and statins.
- Class membership: `class:clobazam` = [21241]; `class:valproate` = [266856, 9919, 40254, 11118].
  `class:anticonvulsants` contains neither clobazam nor valproic acid, so the gate needs the two
  extra classes, and it now has them.

### Sources (Epidiolex, DailyMed setid 8bf27097-4870-43fb-94f0-f3d0871d1eec)
- §7.2 Clobazam: "Concomitant use of EPIDIOLEX with clobazam increases plasma concentrations of
  N‑desmethylclobazam, the active metabolite of clobazam … which may increase the risk of
  clobazam-related adverse reactions" … "Consider a reduction in dosage of clobazam if adverse
  reactions known to occur with clobazam are experienced".
- §12.3: N-desmethylclobazam "C max and AUC by approximately 3-fold, with no effect on clobazam levels".
- §7.3: "Concomitant use of EPIDIOLEX and valproate increases the incidence of liver enzyme elevations"
  … "consider discontinuation or reduction of EPIDIOLEX and/or concomitant valproate."
- §5.1: "Concomitant use of clobazam also increased the incidence of transaminase elevations, although
  to a lesser extent than valproate".

### Is the existing text accurate and complete?
- **Mechanism: accurate.** It names both distinct mechanisms (the N-desmethylclobazam increase and
  the higher liver-enzyme risk with valproate) and says they come from the prescription preparation.
- **Gaps:**
  (a) `alert_headline` and `alert_body` are generic ("CBD can influence how seizure medications work"),
  so the user-facing text names neither mechanism.
  (b) Under §5.1, clobazam also raises the transaminase-elevation rate (to a lesser extent), and the
  text omits this.
  (c) One sub-rule serves three gates, so a levetiracetam user gets the same rule as a clobazam user.
  The mechanism text does hedge this ("does not establish identical effects").
- **Recommendation:** keep the `anticonvulsants` sub-rule as the general one, and add two
  class-specific sub-rules whose user text is accurate. Then remove `clobazam` and `valproate` from
  the general gate so each user gets the specific text only. Engine behaviour when one profile
  matches two sub-rules of the same rule is unverified, so check the dedup in the engine.

### Proposed JSON (two `drug_class_rules` entries appended to RULE_BANNED_CBD_INTERACTIONS)
```json
{
  "drug_class_id": "clobazam",
  "severity": "caution",
  "evidence_level": "established",
  "mechanism": "The EPIDIOLEX label reports that cannabidiol raises N-desmethylclobazam, the active metabolite of clobazam (Cmax and AUC about 3-fold), with no change in clobazam itself, which may increase clobazam-related adverse reactions such as somnolence. Concomitant clobazam also increased transaminase elevations, to a lesser extent than valproate. Data are from the prescription cannabidiol preparation.",
  "action": "Talk to the prescriber before adding CBD. The label advises considering a lower clobazam dose if clobazam-related adverse reactions appear; that decision belongs to the prescriber.",
  "sources": ["https://dailymed.nlm.nih.gov/dailymed/fda/fdaDrugXsl.cfm?setid=8bf27097-4870-43fb-94f0-f3d0871d1eec&type=display"],
  "alert_headline": "CBD can raise clobazam's active metabolite",
  "alert_body": "CBD can increase the level of clobazam's active form, which may add to sleepiness and other clobazam side effects. Talk to your prescriber before adding CBD.",
  "informational_note": "CBD affects clobazam levels, which matters for people taking clobazam.",
  "profile_gate": {"gate_type": "drug_class", "requires": {"conditions_any": [], "drug_classes_any": ["clobazam"], "profile_flags_any": []}, "excludes": {"conditions_any": [], "drug_classes_any": [], "profile_flags_any": [], "product_forms_any": [], "nutrient_forms_any": []}, "dose": null},
  "direction": "harmful",
  "materiality": "presence"
}
```
```json
{
  "drug_class_id": "valproate",
  "severity": "caution",
  "evidence_level": "established",
  "mechanism": "The EPIDIOLEX label reports that concomitant valproate increases the incidence of liver-enzyme (transaminase) elevations, and most ALT elevations in its controlled studies occurred in patients taking valproate. Cannabidiol did not change valproate exposure in healthy subjects. Data are from the prescription cannabidiol preparation.",
  "action": "Talk to the prescriber before adding CBD. With prescription cannabidiol the label calls for liver monitoring and advises considering a reduction or discontinuation of cannabidiol and/or valproate if elevations occur; the prescriber manages this.",
  "sources": ["https://dailymed.nlm.nih.gov/dailymed/fda/fdaDrugXsl.cfm?setid=8bf27097-4870-43fb-94f0-f3d0871d1eec&type=display"],
  "alert_headline": "CBD with valproate: liver-enzyme risk",
  "alert_body": "Taking CBD with valproate (Depakote) has been linked to higher liver-enzyme levels. Talk to your prescriber before adding CBD; they may want to check your liver tests.",
  "informational_note": "CBD and valproate together raise liver-enzyme risk, which matters for people taking valproate.",
  "profile_gate": {"gate_type": "drug_class", "requires": {"conditions_any": [], "drug_classes_any": ["valproate"], "profile_flags_any": []}, "excludes": {"conditions_any": [], "drug_classes_any": [], "profile_flags_any": [], "product_forms_any": [], "nutrient_forms_any": []}, "dose": null},
  "direction": "harmful",
  "materiality": "presence"
}
```
Judgment calls:
- Severity stays `caution`, matching the existing sub-rule.
- The "liver tests" wording in the valproate `alert_body` comes from the label's monitoring advice for
  the prescription product. It is not a label requirement for OTC CBD.

### Open questions
- Should the general `anticonvulsants` gate drop `clobazam` and `valproate` after the split? I
  recommend yes, after checking engine dedup.
- How far do label findings carry from prescription cannabidiol (Epidiolex, about 10-20 mg/kg/day) to
  low-dose OTC CBD? The existing text already flags this.
- §7.2 also names stiripentol and CYP2C19/UGT1A9 substrates. These are not proposed here.

### Confidence
High for the source passages. Medium for the structure, because engine dedup is unverified.

---

## 2. Ashwagandha + thyroid hormone replacement

### Existing coverage
- `RULE_IQM_ASHWAGANDHA` (subject `ingredient_quality_map::ashwagandha`) has a **condition** rule,
  `thyroid_disorder` (caution, `probable`, PMIDs 38003702 and 31203475, both review or rat data). Its
  `alert_body` mentions "take thyroid medication", but the gate is condition-only. Its only
  `drug_class_rules` entry is `sedatives`.
- There is no curated pair for ashwagandha and levothyroxine. The ashwagandha curated pairs are
  DSI_DM_, DSI_ANTIHYP_ and DSI_SEDATIVES_ASHWAGANDHA.
- So a user who records levothyroxine but no thyroid condition gets no ashwagandha warning.
- `class:thyroid_medications` = levothyroxine 10582, liothyronine 10814, thyroid USP 10572 and
  tiratricol 13982. Antithyroid drugs are deliberately excluded (its notes say "open for PharmD
  review"), and no antithyroid class exists. Nine other rules already use `thyroid_medications`
  (calcium, iron, magnesium, zinc, genistein and others).
- Side finding: the existing condition rule's action reads "Contraindicated in hyperthyroidism without
  physician oversight". No source read here says "contraindicated". NCCIH says ashwagandha is "not
  recommended" for people with thyroid disorders. Flagged as a possible overstatement for the
  reviewer.

### Sources
- NCCIH, https://www.nccih.nih.gov/health/ashwagandha: "ashwagandha might interact with some
  medications, including … anti-seizure medications (anticonvulsants), and thyroid hormone
  medications." Also: "not recommended … for those who have autoimmune or thyroid disorders."
- PMID 28829155 (RCT, subclinical hypothyroidism, n=50, 600 mg/day for 8 weeks, patients **not** on
  levothyroxine): "improved serum TSH (p < 0.001), T3 (p = 0.0031), and T4 (p = 0.0096)".
- PMID 25624699 (bipolar RCT, safety labs): "suggest that ASW may increase thyroxine levels, and
  therefore vigilance regarding hyperthyroidism may be warranted." Only 3 people on ashwagandha were
  in the analysed subset.
- PMID 35475098 (case report): thyrotoxicosis with SVT "after two years of using ARE as a
  self-administered treatment for hypothyroidism"; it resolved on stopping. The abstract does not say
  whether she also took levothyroxine.
- PMID 16355578 (case report, Dutch): thyrotoxicosis in a woman "not taking any other remedies or
  medications"; it resolved on stopping.
- **What the sources do not show:** no study read here measured ashwagandha together with
  levothyroxine. The interaction is inferred from an additive pharmacodynamic effect (raised T3/T4)
  plus NCCIH's general statement. There is no product label for ashwagandha.

### Antithyroid drugs (methimazole, PTU)
No source read here addresses ashwagandha with antithyroid drugs. A person on those drugs is
hyperthyroid, so the existing `thyroid_disorder` condition rule is the right owner if the profile
records the condition. Do not add antithyroid drugs to `class:thyroid_medications`: the mechanism
text below is about added thyroid-hormone effect, which is wrong for antithyroid therapy. No new
class is proposed.

### Proposed JSON (one `drug_class_rules` entry appended to RULE_IQM_ASHWAGANDHA)
```json
{
  "drug_class_id": "thyroid_medications",
  "severity": "monitor",
  "evidence_level": "limited",
  "mechanism": "In a placebo-controlled trial in adults with subclinical hypothyroidism who were not taking thyroid medicine, ashwagandha root extract raised T3 and T4 and lowered TSH. Case reports describe thyrotoxicosis that resolved after stopping ashwagandha. No study has measured the combination with levothyroxine; NCCIH lists thyroid hormone medications among possible interactions. An additive effect on thyroid hormone levels is therefore possible but unquantified.",
  "action": "Tell the clinician who manages your thyroid medicine if you take ashwagandha, so thyroid tests can be interpreted and checked as they see fit. Report symptoms such as a racing heart, tremor or heat intolerance.",
  "sources": [
    "https://www.nccih.nih.gov/health/ashwagandha",
    "https://pubmed.ncbi.nlm.nih.gov/28829155/",
    "https://pubmed.ncbi.nlm.nih.gov/25624699/",
    "https://pubmed.ncbi.nlm.nih.gov/35475098/"
  ],
  "alert_headline": "May add to thyroid hormone effects",
  "alert_body": "Ashwagandha has raised thyroid hormone levels in studies, and rare cases of overactive thyroid have been reported. If you take thyroid hormone (such as levothyroxine), let your clinician know you use ashwagandha.",
  "informational_note": "Ashwagandha can affect thyroid hormone levels, which matters for people taking thyroid hormone.",
  "profile_gate": {"gate_type": "drug_class", "requires": {"conditions_any": [], "drug_classes_any": ["thyroid_medications"], "profile_flags_any": []}, "excludes": {"conditions_any": [], "drug_classes_any": [], "profile_flags_any": [], "product_forms_any": [], "nutrient_forms_any": []}, "dose": null},
  "direction": "harmful",
  "materiality": "presence"
}
```
Judgment calls:
- `monitor` rather than `caution`, and `limited` rather than `probable`: there is no combination
  study, only an indirect pharmacodynamic signal and an NCCIH "might interact".
- The symptom list in `action` is general hyperthyroid symptom guidance taken from the case reports'
  presentations, not a sourced instruction.

### Open questions
- Is `limited` with `monitor` right, or does PharmD want `caution` to match the condition rule?
- Should the condition rule's "Contraindicated in hyperthyroidism" wording be softened to match NCCIH
  ("not recommended")?
- The vocabulary-versus-class mismatch for methimazole is already noted in `drug_classes.json`.

### Confidence
Medium-high that the sources are represented accurately. The interaction itself has low-quality
evidence.

---

## 3. NAC + nitroglycerin

### Existing coverage
- None. NAC has only `RULE_IQM_NAC_BLEEDING` (anticoagulants, monitor). No curated record names
  nitroglycerin, nitrates or NAC.
- There is no nitrate class in `drug_classes.json`.
- IQM `nac` has no `cui` (only UNII WYQ7N0BPYC). The proposed `agent2_id` C0001047 (acetylcysteine)
  is from memory and **is not verified**. No UMLS call was made. Run `verify_cui` before use.

### Sources (PubMed abstracts, efetch)
- PMID 9120179, Ardissino 1997, JACC (RCT, n=200, unstable angina, **transdermal NTG + oral NAC**,
  4 months): "The combination of nitroglycerin and N-acetylcysteine was associated with a high
  incidence of side effects (35%), mainly intolerable headache, which was almost twice as frequent as
  in patients receiving nitroglycerin alone."
  The abstract does not state the oral NAC dose. Outcome events were lower with the combination (13%
  vs 39% placebo).
- PMID 1505148, Iversen 1992 (n=11 healthy, **IV NTG**, NAC 100 mg/kg; route not stated in the
  abstract): "N-Acetylcysteine potentiated the headache response".
- PMID 9024731, Pizzulli 1997 (**IV NAC** 2,000 mg bolus plus infusion, with IV NTG): NAC
  "attenuates tolerance development". This is a pharmacological effect, not a harm finding.

### What is supported for oral supplement NAC
- One RCT used oral NAC with transdermal NTG and found intolerable headache in 35%, about twice the
  rate with NTG alone. The oral dose is not in the abstract; the full text would be needed to compare
  it with supplement doses (typically 600-1,200 mg/day).
- Hypotension is **not** stated in any abstract read here. It is described in the IV literature from
  memory only, so it is omitted.
- No evidence was read for isosorbide mononitrate or dinitrate, so scope is nitroglycerin only.

### Proposed JSON (curated pair, `curated_interactions_v1.json`)
```json
{
  "id": "DSI_NITROGLYCERIN_NAC",
  "type": "Med-Sup",
  "agent1_name": "Nitroglycerin",
  "agent1_id": "4917",
  "agent2_name": "N-Acetylcysteine (NAC)",
  "agent2_id": "C0001047",
  "agent2_canonical_id": "nac",
  "agent1_canonical_id": null,
  "severity": "Minor",
  "interaction_effect_type": "Enhancer",
  "mechanism": "NAC is a sulfhydryl donor that can potentiate nitroglycerin's vasodilating effect. In a randomized trial in unstable angina, oral NAC combined with transdermal nitroglycerin caused side effects in 35% of patients, mainly intolerable headache, about twice as often as nitroglycerin alone. Most other studies used intravenous NAC; the effect at typical supplement doses has not been measured.",
  "management": "If you use nitroglycerin, tell your prescriber before starting NAC. Report new or worse headaches, or dizziness, to your clinician.",
  "source_urls": ["https://pubmed.ncbi.nlm.nih.gov/9120179/", "https://pubmed.ncbi.nlm.nih.gov/1505148/"],
  "source_pmids": ["9120179", "1505148"],
  "evidence_basis": "clinical_literature",
  "clinical_confidence": "low",
  "applies_to": "specific_drug",
  "direction": "harmful",
  "materiality": "presence",
  "evidence_notes": "Oral-NAC evidence is one RCT abstract (PMID 9120179; dose not stated in the abstract). PMID 1505148 used IV nitroglycerin. Scope limited to nitroglycerin; other nitrates not studied in sources read."
}
```
Judgment calls:
- `Minor`: the documented harm is headache, which is bothersome and can limit therapy but is not
  dangerous in the sources read. PharmD may prefer `Moderate` if potentiated hypotension is judged
  relevant. That would need a source stating it.
- "dizziness" in `management` is general vasodilator counselling, not a finding from these abstracts.
  Remove it if PharmD wants strict source wording.
- The `verification` block is omitted; it should be filled by the verifier run.

### Open questions
- Should the full text of Ardissino 1997 be fetched to confirm the oral NAC dose before choosing the
  severity?
- Is this record worth adding at all? Evidence is thin and the effect is headache. I lean towards
  adding it as Minor because the oral-route RCT exists.
- Should the pair extend to isosorbide nitrates? Not proposed without a source.
- C0001047 needs UMLS content verification.

### Confidence
Medium for the source reading. Low for clinical materiality at supplement doses.

---

## 4. Lamotrigine + estrogen-containing hormonal contraceptives

### Existing coverage
- `med_med_pairs_v1.json` → `DDI_ANTICONV_OCP`: `class:anticonvulsants` × `class:oral_contraceptives`,
  Moderate. Its mechanism names "carbamazepine, phenytoin, phenobarbital, oxcarbazepine, topiramate"
  as enzyme inducers. Its source is the Tegretol label (setid 8d409411-…).
- No lamotrigine-specific pair exists.
- `class:anticonvulsants` includes lamotrigine 28439, cannabidiol 2045371, levetiracetam and
  others. The current pair therefore fires for lamotrigine with the wrong mechanism (the reverse
  direction: contraceptive harmed instead of lamotrigine lowered), and also for non-inducers such as
  levetiracetam and Epidiolex.

### Class fit: `class:enzyme_inducing_antiseizure_medications`
- **Members:** carbamazepine 2002, phenobarbital 8134, phenytoin 8183, primidone 8691. It excludes
  oxcarbazepine ("weaker, dose-dependent inducer … evaluate separately") and valproate.
- **The DDI text names:** CBZ, PHT, PB, **oxcarbazepine, topiramate**, and **omits primidone**.
- **What labels say about the two drugs the class lacks:**
  - Trileptal (setid 4c5c86c8-ab7f-4fcf-bc1b-5a0b1fd0691b) §7.3: "Concurrent use of TRILEPTAL with
    hormonal contraceptives may render these contraceptives less effective". This is a label-level
    contraceptive warning, so narrowing to the class alone **drops a valid oxcarbazepine warning**.
  - Topamax (setid 21628112-0c47-11df-95b3-498d55d89593) §12.3: at 50-200 mg/day alone, "not
    associated with statistically significant changes"; as adjunct, EE "decreased at doses of 200, 400,
    and 800 mg/day (18%, 21%, and 30%)". This is dose-dependent, so topiramate does not belong in an
    unconditional inducer list.
- **Verdict:** the class fits pharmacologically for CBZ, PHT, PB and primidone. The class was built for
  vitamin D catabolism, but its notes say it carries "every induction-driven depletion", and
  contraceptive failure follows from the same CYP3A4 induction, so reuse is defensible.
- **Required with the narrowing:**
  (a) Rewrite the mechanism to name the four class members (drop oxcarbazepine and topiramate, add
  primidone).
  (b) Add a separate oxcarbazepine (32624) × `class:oral_contraceptives` pair from the Trileptal label,
  so oxcarbazepine users keep a warning.
  (c) Treat topiramate as a separate dose-dependent decision, or omit it.
- **Side notes:**
  - `interaction_effect_type: "Inhibitor"` on an inducer pair looks inconsistent. The enum has no
    "Inducer"; check the field's meaning.
  - Other ASM labels with contraceptive interactions (eslicarbazepine, cenobamate, felbamate,
    rufinamide, perampanel) were **not checked**. That is a coverage-gap question, not a claim.

### Lamotrigine sources (Lamictal, DailyMed setid d7e3572d-56fe-4727-2bb4-013ccca22678)
- Highlights: "Adjustments to maintenance doses will be necessary in most patients starting or stopping
  estrogen-containing products, including oral contraceptives."
- §2.1: the maintenance dose "will in most cases need to be increased by as much as 2-fold over the
  recommended target maintenance dose".
- Table 13: "Decreased lamotrigine concentrations approximately 50%" (30 mcg EE / 150 mcg
  levonorgestrel).
- §12.3: "ethinylestradiol, not progestogens, increased the clearance of lamotrigine up to 2-fold, and
  the progestin-only pills had no effect on lamotrigine plasma levels."
- §2.1 pill-free week: "Gradual transient increases in lamotrigine plasma levels may occur during the
  week of inactive hormonal preparation".
- The label says no OC adjustment is needed for women also taking CBZ, PHT, PB, primidone, rifampin
  or lopinavir/ritonavir, because those drugs already induce lamotrigine glucuronidation.

### Class / RxCUI status (important)
- `class:oral_contraceptives` holds **progestins only** (desogestrel, drospirenone, etonogestrel,
  levonorgestrel, lynestrenol, medroxyprogesterone, norethindrone, norgestrienone, ulipristal).
  **Ethinyl estradiol is not a member.**
- Targeting that class would wrongly warn progestin-only, implant and DMPA users, which the label says
  are unaffected. It would also miss nothing that EE covers, because combined products contain EE.
- Proposed `agent2_id`: **4124 (ethinyl estradiol, Active IN)**. This covers combined pills, patch and
  ring, which all contain EE.
- Estradiol (4083) is not proposed: the label says other hormonal or HRT preparations have "not been
  systematically evaluated".

### Proposed JSON (`med_med_pairs_v1.json`)
```json
{
  "id": "DDI_LAMOTRIGINE_ETHINYL_ESTRADIOL",
  "type": "Med-Med",
  "agent1_name": "Lamotrigine",
  "agent1_id": "28439",
  "agent2_name": "Ethinyl estradiol (estrogen-containing contraceptives)",
  "agent2_id": "4124",
  "agent1_canonical_id": null,
  "agent2_canonical_id": null,
  "severity": "Moderate",
  "interaction_effect_type": "Inhibitor",
  "mechanism": "Ethinyl estradiol increases lamotrigine clearance (up to 2-fold), lowering lamotrigine levels by about 50% with a 30 mcg ethinyl estradiol pill. Levels can rise again during the hormone-free week. Progestin-only pills had no effect on lamotrigine levels. Patients also taking carbamazepine, phenytoin, phenobarbital, primidone or other glucuronidation inducers are not expected to need this adjustment.",
  "management": "Tell the lamotrigine prescriber when starting or stopping an estrogen-containing contraceptive. The label states that the lamotrigine maintenance dose will need adjustment in most patients; the prescriber decides the change.",
  "source_urls": ["https://dailymed.nlm.nih.gov/dailymed/drugInfo.cfm?setid=d7e3572d-56fe-4727-2bb4-013ccca22678"],
  "source_pmids": [],
  "evidence_basis": "label_regulatory",
  "clinical_confidence": "high",
  "applies_to": "specific_drug",
  "direction": "harmful",
  "materiality": "presence"
}
```
Judgment calls:
- `Moderate`: the label requires dose adjustment, with loss of seizure or mood control on one side and
  adverse effects in the pill-free week on the other. There is no contraindication language.
- `interaction_effect_type: "Inhibitor"` mirrors DDI_ANTICONV_OCP's use for "reduces the other drug's
  effect". Confirm the enum's meaning.

### Open questions
- Does the medication matcher decompose a combined-pill entry into ingredient 4124? Check this before
  relying on the ingredient-level `agent2_id`.
- Should estradiol-valerate combined pills (estradiol 4083) be included? There is no label support.
- Should the oxcarbazepine pair and the topiramate decision ship in the same batch as the narrowing?
  I recommend yes, otherwise oxcarbazepine users lose their warning.

### Confidence
High for the label passages and the class contents. Medium for matcher behaviour.

---

## 5. Psyllium + digoxin

### Existing coverage
- None. `RULE_IQM_PSYLLIUM_DIABETES` (subject `psyllium`) has sub-rules only for
  hypoglycemics_high_risk, hypoglycemics_lower_risk, hypoglycemics_unknown and lithium.
- No curated record pairs psyllium with digoxin. Digoxin pairs: DDI_DIGOXIN_AMIODARONE,
  DDI_DIGOXIN_DIURETICS, DSI_DIGOXIN_SJW.
- `class:cardiac_glycosides` exists (digoxin 3407 and others) and is already used by the senna,
  cascara, aloe ferox and ginseng rules.
- IQM psyllium CUI: C0033979.

### Sources
- MedlinePlus psyllium monograph: **fetch failed.** The page redirects; Natural Medicines content is
  unavailable. The "3 hours" statement is unverified.
- Lanoxin (DailyMed setid d91e3646-4c63-4512-ab22-db39c085c4dc) §12.3: "When taken with meals high in
  bran fiber, however, the amount absorbed from an oral dose may be reduced." §7 table, "Digoxin
  concentrations decreased", lists "meals high in bran" and kaolin-pectin. **Psyllium is not named.**
- Metamucil Drug Facts (DailyMed setid a9824f73-5ea2-4a65-a926-3a57561441b8): "Take this product 2
  or more hours before or after other drugs. Laxatives may affect how other drugs work." This is
  generic and not digoxin-specific.
- PMID 3038494, Nordström 1987 (randomized, 30 geriatric inpatients on digoxin, ispaghula = psyllium,
  4 weeks): "Ispaghula had no influence at any time." It concluded neither fibre had "any clinically
  relevant influence on therapeutic digoxin levels".
- PMID 6963097, Reissell 1982: "The effect of fibre alone is small but an interactive effect on
  absorption may occur if fibre and digoxin are ingested simultaneously."

### Assessment
The only psyllium-specific digoxin study found no effect on steady-state levels. The remaining
support is general:
- simultaneous fibre intake may reduce absorption (a small study);
- the Lanoxin label mentions bran meals, not psyllium;
- Metamucil's Drug Facts gives a 2-hour separation from all drugs.

A digoxin-specific Moderate warning is not supported. Under the "flag only real, sourced concerns"
rule, I recommend **not adding a digoxin-specific pair**, or at most the Minor spacing record below.
PharmD decides.

### Proposed JSON (optional; `curated_interactions_v1.json`)
```json
{
  "id": "DSI_DIGOXIN_PSYLLIUM",
  "type": "Med-Sup",
  "agent1_name": "Digoxin",
  "agent1_id": "3407",
  "agent2_name": "Psyllium",
  "agent2_id": "C0033979",
  "agent1_canonical_id": null,
  "agent2_canonical_id": "psyllium",
  "severity": "Minor",
  "interaction_effect_type": "Inhibitor",
  "mechanism": "Dietary fiber taken at the same time as digoxin may slightly reduce digoxin absorption; the digoxin label notes reduced absorption with meals high in bran fiber. In a randomized study of older patients on steady digoxin, psyllium (ispaghula) did not change digoxin levels.",
  "management": "Psyllium product labeling advises taking it 2 or more hours before or after other medicines. Following that spacing with digoxin is a reasonable precaution; no digoxin-specific dose change is indicated.",
  "source_urls": [
    "https://dailymed.nlm.nih.gov/dailymed/drugInfo.cfm?setid=d91e3646-4c63-4512-ab22-db39c085c4dc",
    "https://dailymed.nlm.nih.gov/dailymed/drugInfo.cfm?setid=a9824f73-5ea2-4a65-a926-3a57561441b8",
    "https://pubmed.ncbi.nlm.nih.gov/3038494/",
    "https://pubmed.ncbi.nlm.nih.gov/6963097/"
  ],
  "source_pmids": ["3038494", "6963097"],
  "evidence_basis": "label_regulatory",
  "clinical_confidence": "low",
  "applies_to": "specific_drug",
  "direction": "harmful",
  "materiality": "presence",
  "evidence_notes": "Psyllium-specific digoxin RCT (PMID 3038494) found no effect; spacing comes from the generic psyllium Drug Facts statement, not a digoxin-specific source. MedlinePlus 3-hour statement could not be retrieved (Natural Medicines content unavailable, 2026-11-11)."
}
```
Judgment calls:
- `Minor` and `clinical_confidence: low`.
- The 2-hour interval is stated by the Metamucil Drug Facts, so it meets the "interval only if the
  source states it" rule. The 3-hour MedlinePlus figure is not used because it is unverified.
- `evidence_basis: label_regulatory` reflects the Drug Facts and Lanoxin labels. `clinical_literature`
  would also be defensible.

### Open questions
- Add this record or not? I lean towards not adding a digoxin-specific pair, given PMID 3038494.
- If a generic spacing message for all medicines is wanted, it may belong in a psyllium product-level
  note rather than a digoxin pair. That needs an owner check.

### Confidence
High that a strong interaction is not supported by the sources read. Low on whether any record adds
value.
