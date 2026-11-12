# Remaining interaction research — 2026-11-12

Research receipt, not clinical approval or a release attestation. Prepared by Codex research agents;
no recommendations below are attributed to Dr. Pham. Existing signed decisions remain in
`DR_PHAM_REVIEW_20261111.md` and `DR_PHAM_ANSWERS_20261112.md`; implementation status belongs in
`DISPOSITIONS_20261111.md`. Named holds are not silently closed by finding a source.

## Approval boundary

[PR #458](https://github.com/seancheick/PharmaGuide_Pipeline/pull/458) records Dr. Pham's
signed answers to the original seven questions and serious-warning decisions. Apply Part A
and track implementation in DISPOSITIONS. The research below records only narrower
questions outside that signed scope. Remaining decisions include the new CBD H1–H4
questions, explicitly held presentation choices and exposure policies. Routine source
corrections proceed under the existing review delegation.

## Decision register after reconciliation with Part A

| Signed decision | Implementation status |
|---|---|
| Q1 SAMe and MAOIs | #459 implements the class avoid fallback and exact tranylcypromine and phenelzine contraindications. Confirmed EMSAM still needs exact formulation matching and pair/profile parity. That is engineering work under the signed contraindication. |
| Q2 vitamin E | #465 carries the wording correction. Lower prominence for known ordinary exposure is already authorized within Q2. Implement and verify form, daily use and combined Stack amounts first. Any new numerical suppression threshold falls outside Q2. |
| Q3 and Q7 anticoagulants | #461 implements the glucosamine action, supported VKA distinctions and injected-anticoagulant exclusions. Ginseng species and any extension beyond warfarin remain separate questions. |
| Q4 and Q6 antimuscarinic scope | #462 implements the differentiated warning. Preserve qualified review for unknown route or dose. Presentation for an unidentified picker selection and accurate naming of the narrower class remain separate. |
| Q5 CBD | #464 implements the named split, qualified oral-digoxin caution and general seizure-medicine review message. Preserve that message for an otherwise unassessed medicine even when the same regimen includes stiripentol. #470 carries the sirolimus source correction against current main. Mycophenolate was signed for the review list. |
| Serious warnings | #459 implements SJW/SSRIs and the SSRI/SNRI 5-HTP harmonization, #461 implements SJW/anticoagulant distinctions, #462 implements huperzine scope, and #465/#466 carry senna/cascara/aloe with digoxin. Keep unknown aloe processing uncertain. |

### Questions for Dr. Pham

- CBD H1 clinical scope for oral cyclosporine, H2 grade and direction of the existing qualified seizure-medicine message, H3 adding liver and ammonia signals, and H4 a specific warning for prescription cannabidiol plus OTC CBD. Include whether the review-listed mycophenolate finding should publish.
- Any new severity or management outside signed scope: exact 5-HTP coverage for systemic TCAs, carbidopa or oral selegiline where the current rules or evidence leave a gap; ginseng species and anticoagulant extension; a fixed vitamin E surgery instruction; or a new aloe ferox gel exemption. An explicit topical/low-dose doxepin exemption would also change applicability.
- New policy for B6 and niacin exposure suppression, a published SINEMET depletion finding, nitrate/PDE5–arginine/citrulline guidance, or an activated-charcoal interval. These need clinical review if pursued. The cited IV-calcium statement does not supply an oral digoxin/calcium warning to approve.

### Decisions Sean can make

- Pick the placement and wording of a prompt to identify an unknown immunosuppressant or antimuscarinic. Engineering must distinguish a picker-only selection from a known medicine before enabling that prompt. Preserve signed actions and clinical prominence requirements.
- Choose whether and where to show uncertainty about aloe preparation, and whether to build a non-precise timing presentation for the held pairs. Any new clinical recommendation or exemption stays within its own review scope.
- Prioritize engineering and release order, choose presentation within the signed vitamin E policy, and select factual medication wording within the existing copy contract. H5 vocabulary currently has a clinician-copy gate, so existing signed wording can be reused within scope and any genuinely new text must clear that gate or a separately authorized change to the gate.

## Owner Check and scope

Owner: `scripts/data/ingredient_interaction_rules.json` (profile findings),
`scripts/data/curated_interactions/curated_interactions_v1.json` (pairs),
`scripts/data/drug_class_vocab.json` (medicine descriptions), and the existing clinical-review
DISPOSITIONS register. Evidence: searched the source-of-truth matrix and glossary for research,
interaction and held concepts; enumerated `scripts/audits/clinical_review_20261111/` and found no
existing research.md. This file is a bounded source receipt under that existing audit, not a registry.
Will NOT create: clinical statuses, severities, clinical policy, a new engine, or a second execution register.

Research date: 2026-11-12. CBD and Batch 8 facts below were checked by the CBD research agent against
live labels/NIH pages and NCBI EFetch abstracts. The earlier-held-items section consolidates the other
research agent's dated receipt and explicitly identifies that provenance. Integrator review is still
required before applying data. No data was edited by this research task.

## CBD held items and source corrections

Primary label: [EPIDIOLEX, effective 2026-05-29](https://dailymed.nlm.nih.gov/dailymed/drugInfo.cfm?setid=8bf27097-4870-43fb-94f0-f3d0871d1eec),
sections 5.1, 7.2, 7.3, 7.4 and 12.3, content read live.

| Item | Verified basis and recommendation | Remaining decision |
|---|---|---|
| H1 cyclosporine | [Neoral oral solution SmPC 4.5, updated 2026-03-11](https://www.medicines.org.uk/emc/product/5300/smpc) explicitly names cannabidiol, caution, adverse-effect surveillance and cyclosporine concentration monitoring. Recommend a named oral-cyclosporine caution. Label rationale partly extrapolates from another calcineurin inhibitor; do not promise a magnitude or inevitable direction. | Named clinical hold remains; recommend approving this precise scope, not the whole immunosuppressant class. |
| H1 picker only | Recommend a conditional request to identify the medicine, not a claim that all immunosuppressants interact. The handoff says the profile cannot distinguish a picker-only choice from entered biologics. | Applicability/presentation decision and consumer proof; research does not resolve the representation gap. |
| H2 other antiseizure medicines | Dr. Pham authorized a qualified review message. Recommend informational/neutral with insufficient evidence for the unassessed remainder. Keep named findings separate. Monitor is unsuitable unless the observation is specified. | Named severity/direction hold. Lack of assessment is not absence of an interaction. |
| H3 clobazam liver/ammonia | EPIDIOLEX 5.1 supports the smaller clobazam liver signal and postmarketing ammonia reports, mostly with valproate/clobazam. Recommend source-qualified detail in existing cards. | Named hold on adding findings; no universal ammonia testing or consumer dose adjustment. |
| H4 prescription cannabidiol | EPIDIOLEX 5.1 documents dose-related liver risk. Recommend a duplicate-exposure review message before adding OTC CBD, without an invented threshold. | New named finding remains held; this is inference, not an OTC-product interaction trial. |
| Digoxin | EPIDIOLEX 7.2 names oral digoxin, potential exposure increase and clinician monitoring. Caution is defensible under the existing review/management rubric; no effect size is established. | Closed within Q5: the qualified caution is implemented in #464. A stronger warning would be a new decision. |
| Mycophenolate | EPIDIOLEX 12.3 reports mycophenolic-acid AUC +35%; +58% is a prediction at a different CBD regimen. 7.2 supplies UGT1A9 management context. Recommend a named specialist-review caution. | Dr. Pham authorized the review list, not a published warning. Source review can finish while publication remains held. |

### Confirmed sirolimus factual defect in batch 4

Inspected `origin/claude/interaction-b4-cbd` rule `RULE_BANNED_CBD_INTERACTIONS` / `sirolimus`.
Its mechanism, alert body and informational note say the interaction was not measured directly.
[PMID 31924480](https://pubmed.ncbi.nlm.nih.gov/31924480/), content-verified via live NCBI EFetch,
describes a retrospective TSC series with seven sirolimus patients and a median trough increase
of 5.1 ng/mL after cannabidiol. This is observational, not a controlled sirolimus trial.
Recommendation: correct all three absolute statements, retain the distinction between label
precaution and observational evidence, and keep the existing caution action. This is a factual
correction within the accepted finding, not authority to invent a stronger severity.

Additional API/content checks:

- [PMID 38212169](https://pubmed.ncbi.nlm.nih.gov/38212169/): exact CBD/cyclosporine/mycophenolate case report.
  Available abstract gives neither direction, magnitude nor CBD dose. Do not import those details
  from secondary sites.
- [PMID 29579828](https://pubmed.ncbi.nlm.nih.gov/29579828/): seven kidney-transplant patients in a short series;
  cyclosporine levels were stable. This limits certainty without negating the regulatory precaution.
- [PMID 39601108](https://pubmed.ncbi.nlm.nih.gov/39601108/): 12 healthy participants, CBD 5 mg/kg twice daily;
  tacrolimus Cmax 4.2-fold and AUC 3.1-fold. Do not transfer these numbers to other drugs or arbitrary
  OTC/topical exposures.

### H5 vocabulary recommendations

These are agent drafts, still subject to the named vocabulary hold. Correcting inherited indications
does not authorize changing interaction scope.

| Medicine | Recommended draft or disposition | Source checked |
|---|---|---|
| Clobazam | Commonly used with other seizure medicines for Lennox-Gastaut syndrome. | [Clobazam label](https://dailymed.nlm.nih.gov/dailymed/drugInfo.cfm?setid=e827ced8-dc40-9bd3-e053-2a95a90ae795) |
| Stiripentol | Commonly used with clobazam for seizures in Dravet syndrome. | [DIACOMIT](https://dailymed.nlm.nih.gov/dailymed/drugInfo.cfm?setid=58304ba8-9779-4658-811e-94ffe08c3f16) |
| Sirolimus | Commonly used by mouth to prevent kidney transplant rejection and for a lung condition called LAM. | [Sirolimus](https://dailymed.nlm.nih.gov/dailymed/drugInfo.cfm?setid=09f24e7a-0bea-4e02-b557-c60eb842d41a) |
| Everolimus | Use the existing draft with depending-on-the-product qualification for transplant versus tumor indications. | [Transplant label](https://dailymed.nlm.nih.gov/dailymed/drugInfo.cfm?setid=59cb86d5-8706-4619-b074-af253d3e0b68), [oncology label](https://dailymed.nlm.nih.gov/dailymed/drugInfo.cfm?setid=ae8c881f-31dc-41e2-8acd-2c029a9f4925) |
| Tacrolimus | Preserve the oral-versus-skin distinction in the existing draft; eczema does not imply oral use. | [Ointment label](https://dailymed.nlm.nih.gov/dailymed/drugInfo.cfm?setid=c2d2e3a1-f346-4245-b445-6dd44e371180) supports the skin indication; oral/transplant wording should retain its existing verified source. |
| Valproate | Retain depending-on-the-product qualification for seizures, mania and migraine prevention. | [STAVZOR label](https://www.accessdata.fda.gov/drugsatfda_docs/label/2026/022152s010lbl.pdf) |

## Questions outside the signed scope: independent research receipt

The held-research agent reported live checks on 2026-11-12. These findings were consolidated here,
not independently re-fetched by this document's writer. They require integrator source review before data edits.

| Item | Source result and recommendation | Remaining boundary |
|---|---|---|
| 5-HTP and tricyclic antidepressants | [Health Canada oral 5-HTP monograph](https://webprod.hc-sc.gc.ca/nhpid-bdipsn/atReq?atid=5htp&lang=eng) contraindicates antidepressants. Supports systemic TCA scope, not automatic equivalence of topical/low-dose doxepin. | Named applicability hold. |
| 5-HTP and carbidopa | Same monograph separately cautions carbidopa. Recommend exact carbidopa coverage, including combination products, rather than ignoring the source. | Named hold remains; not an approval to classify every Parkinson medicine alike. |
| 5-HTP and oral selegiline | [ZELAPAR](https://dailymed.nlm.nih.gov/dailymed/drugInfo.cfm?setid=380d7717-2a79-42f3-a712-efe5e7696ba0), sections 4/5.2/7.6, does not name 5-HTP. Recommend avoid as a stated precaution; do not transfer EMSAM-specific conclusions. | Stronger contraindication needs owner interpretation. |
| Ginseng anticoagulant scope | [PMID 15238367](https://pubmed.ncbi.nlm.nih.gov/15238367/) American ginseng reduced warfarin effect; [PMID 15089812](https://pubmed.ncbi.nlm.nih.gov/15089812/) Asian-ginseng healthy-volunteer findings differ. Recommend warfarin-specific caution with species/preparation accuracy; any VKA extension explicit. | Whole DOAC/heparin warning not established; named scope decision. |
| Antimuscarinic vocabulary | Proposed factual wording: Commonly used for conditions such as overactive bladder, motion sickness, Parkinson symptoms and muscle spasms; uses depend on the medicine. Verify each subset member before adopting. | Vocabulary hold, no new severity. |
| Antimuscarinic routes | [GELNIQUE](https://www.rxabbvie.com/pdf/gelnique_pi.pdf), [scopolamine patch](https://dailymed.nlm.nih.gov/dailymed/drugInfo.cfm?setid=b877a694-a1d0-4280-937a-a06820b12a88), and [inhaled glycopyrrolate](https://medlineplus.gov/druginfo/meds/a618016.html) are intended antimuscarinics. Route alone is not proof of exemption. | Retain Q6 precaution with honest inference from donepezil; do not claim a direct huperzine trial or contraindication. |
| Picker-only antimuscarinic severity | Research does not decide how unknown medicine identity should affect a badge. | Presentation/applicability policy remains held. |
| Vitamin E ordinary exposure | [NIH ODS](https://ods.od.nih.gov/factsheets/VitaminE-HealthProfessional/) does not establish 400 IU as a safe/unsafe boundary. Preserve Q2 quantity/form/frequency/Stack requirements. | Numerical suppression and prominence remain held until handling and policy are qualified. |
| Vitamin E surgery | [Mayo Clinic](https://www.mayoclinic.org/drugs-supplements-vitamin-e/art-20364144) says two weeks, not an unsupported one-to-two-week range or a high-dose threshold. Recommend clinician-directed wording with an attributed interval only if adopted. | Named instruction hold; Mayo is clinical guidance, not a trial establishing a universal interval. |
| Aloe ferox gel | [NCCIH Aloe Vera](https://www.nccih.nih.gov/health/aloe-vera) concerns Aloe vera; EMA/HMPC/625788/2015 concerns dried leaf juice/anthranoid preparations, not verified ferox inner gel. | Do not transfer species/preparation equivalence. Keep latex handling and unresolved gel applicability explicit. |

## Batch 6 additions to the owner decision list

The following completes the earlier held-item list. Source passages and live identifier checks are in
`BATCH6_RESEARCH_20261112.md`; these recommendations are agent research, not clinician sign-off.

| Decision | Recommendation and implementation boundary |
|---|---|
| Isotretinoin / beta-carotene | Apply F1’s avoid precaution and no-automatic-exemption decision. Any proposed beta-carotene-only exemption needs its own review. Keep explicit that provitamin A is not as toxic as preformed retinol; no extrapolation to unrelated carotenoids. |
| Oral bisphosphonates / magnesium | F3 calls for reviewing magnesium alongside calcium. The implemented Major-to-Moderate change follows Sean’s batch-6 instruction, with drug-specific label timing and IV products excluded. No universal spacing interval. |
| SINEMET B6 depletion | Approve severity/copy and qualify exact combination hydration before activation. The source record is withheld. Do not add a blanket B6 warning to carbidopa/levodopa users. A true levodopa-without-inhibitor regimen is a separate question; INBRIJA's indication does not establish that regimen. |
| Digoxin / calcium | Accept no oral supplement warning from the cited rapid-IV-calcium statement. This does not establish that every calcium/digoxin situation is clear. |
| Nitrates or PDE5 medicines / arginine or citrulline | Consider a qualified, medicine-specific prescriber-review finding. Do not equate amino acids with organic nitrates or invent a formal contraindication, threshold or spacing rule. Selected combination trials do not establish universal safety. |
| Activated charcoal | Specify oral medicine/formulation scope if a finding is wanted. Poisoning-treatment evidence does not establish one universally protective separation interval. |
| G1 routine niacin and B6 quantities | Agree a source-supported exposure policy and qualify daily/Stack amounts before suppressing routine-quantity findings. The source/form corrections are implemented; no study dose was repurposed as a safety threshold. |

Product decisions: retain iron/calcium, iron/zinc and theanine/caffeine holds rather than creating a
new timing relation solely to clear records. Do not infer aloe latex from unknown processing;
an uncertainty display would require a defined consumer meaning. These are implementation
recommendations for Sean, not additional clinician approvals.

## Batch 8 G1: source review

The clinical severity decisions below are already in Dr. Pham's G1 review; the research verifies
their factual basis, not a new clinical policy. This receipt does not demonstrate consumer behavior,
deduplication, form matching, exposure aggregation or Stack grade parity.

| Entry | Source content checked 2026-11-12 | Recommended implementation and boundary |
|---|---|---|
| Magnesium / kidney disease | [NIH ODS Magnesium, excess-intake section](https://ods.od.nih.gov/factsheets/Magnesium-HealthProfessional/) explains increased toxicity risk with impaired renal removal. | Existing kidney flag can support caution and check-with-kidney-team guidance. Do not infer a CKD stage or erase the reduced-clearance risk. Update structured severity and all free text together. |
| Potassium / kidney disease | [NIH ODS Potassium](https://ods.od.nih.gov/factsheets/Potassium-HealthProfessional/) describes hyperkalemia with impaired renal excretion and advises individualized intake guidance; even intake below AI can matter. | Caution with kidney-team review is supported. No dose exemption, universal food restriction or implication that unknown kidney function is normal. |
| L-theanine / antihypertensives | Live EFetch [PMID 23107346](https://pubmed.ncbi.nlm.nih.gov/23107346/): 14 adults, stress response. [PMID 17891480](https://pubmed.ncbi.nlm.nih.gov/17891480/): 48 healthy adults, caffeine/theanine challenge. Neither studies coadministration with antihypertensive therapy. | Apply signed informational/theoretical, neutral treatment; describe study context instead of a proven drug interaction. No Stack penalty, subject to consumer test. Do not change its separate sedative row under this decision. |
| Zinc / levothyroxine | Live EFetch [PMID 23960398](https://pubmed.ncbi.nlm.nih.gov/23960398/) is a zinc-deficiency/hypothyroidism alopecia case, not levothyroxine chelation or spacing evidence. | Apply signed informational/theoretical handling; remove harmful-interaction implication. No newly invented interval. If a precautionary interval is retained anywhere, identify its policy basis, not this PMID. |
| B6 / lactation | [LactMed NBK593298](https://www.ncbi.nlm.nih.gov/books/NBK593298/) indexed source excerpts mention 600 mg/day suppression studies and routine maternal supplementation. Full direct HTML/XML/PDF requests hit CAPTCHA in this research session. | Signed G1 rejects the 50 mg boundary. Do not replace it with a 600 mg threshold or infer high-dose safety. Reuse an applicable complete earlier receipt or verify accessible primary studies before declaring this source review complete. Preserve separate B6 toxicity rules. |
| Niacin / diabetes | [NIH ODS Niacin, antidiabetes section](https://ods.od.nih.gov/factsheets/Niacin-HealthProfessional/) specifically discusses high-dose nicotinic acid and glucose effects; 1.5 g/day is described as most likely in some studies, not a universal onset. | Correct all generic niacin prose to the supported form/exposure. Verify ingredient-row form exclusion before removing warnings from nicotinamide, including mixed/unknown forms; no absolute 1 g/1.5 g gate. Conditional copy alone does not prove applicability is fixed. |
| Vitamin D / warfarin | Live EFetch [PMID 35718837](https://pubmed.ncbi.nlm.nih.gov/35718837/): 89-patient retrospective vitamin-D-status/warfarin-sensitivity association. [PMID 27225617](https://pubmed.ncbi.nlm.nih.gov/27225617/): 40 deficient DVT/PE patients, 50,000 IU weekly for 8 weeks then every two weeks for 4 weeks; lower warfarin doses controlled INR; P-selectin/hs-CRP did not significantly improve. | Remove all-anticoagulant and mild-antiplatelet claims; exact warfarin conditional information, with monitoring limited to starting/changing deficiency treatment. These studies establish no 10,000 IU interaction threshold and no universal effect of ordinary multivitamins. Do not treat unknown treatment context as confirmed deficiency. |
| Omega-3 / EPA / DHA bleeding | Live EFetch [PMID 38742535](https://pubmed.ncbi.nlm.nih.gov/38742535/): 11 RCTs/120,643 patients; overall bleeding RR 1.09 (95% CI 0.91–1.31), high-dose purified EPA subgroup modest absolute increase 0.6%. [VASCEPA label 5.3](https://www.dailymed.nlm.nih.gov/dailymed/drugInfo.cfm?setid=d245ddab-d81b-44bd-90d7-0e4d446d9bf5) separately documents bleeding. | Signed monitor-level ordinary omega-3 guidance is supportable. One finding requires parent/EPA/DHA and class/pair deduplication proof in consumers; do not merely lower three cards and call it consolidated. Preserve prescription-icosapent scope and no invented 3 g/5 g boundary. |

### Confirmed vitamin D citation defect

`RULE_INGREDIENT_VITAMIN_D` included PMID 8983860 in the baseline. Live EFetch resolves it to
*Warfarin withdrawal. Pharmacokinetic-pharmacodynamic considerations*, not vitamin-D supplementation.
The abstract's isolated vitamin-D-dependent wording occurs amid the vitamin-K mechanism and does not
support the claimed interaction. PR #468 removes the citation and retains the applicable
vitamin-D evidence. This source correction requires no new clinical decision.

### Bounded ready subset versus outstanding consumer work

Ready for focused implementation under signed G1, after fail-first tests: magnesium/kidney and
potassium/kidney caution; theanine/antihypertensive informational-neutral; zinc/thyroid
informational-neutral without a new interval; vitamin-D ghost-citation/copy correction and exact
warfarin conditional scope. Preserve source attribution and unrelated rows.

Do not mark the whole batch complete from that subset. B6 needs a full applicable source receipt and
proof of routine-versus-high-exposure behavior without inventing a threshold. Niacin needs tested
form/exposure applicability. Omega consolidation needs actual one-card/one-grade consumer proof,
including isolated EPA/DHA, parent plus child rows, multiple products and prescription icosapent.
Calcium/iron thyroid shared-management consolidation, chromium-picolinate form specificity,
nadolol-specific green-tea coverage and caffeine exposure handling remain separate G1 implementation
items not resolved by this receipt. All changed Stack outputs need reviewed examples; no algorithm change.

## Verification limits

- NCBI EFetch content checks in this task: 38212169, 29579828, 39601108, 31924480, 23107346,
  17891480, 23960398, 35718837, 8983860, 27225617 and 38742535.
- No new RxCUI/CUI identity was authored or verified by this task.
- This receipt is documentation only. No pipeline, release, broad test suite or data mutation was run.
- Recommendations still need integrator double-check; named holds still need their actual owner.

## Batch 8 implementation receipt — 2026-11-12

Owner: `scripts/data/ingredient_interaction_rules.json::interaction_rules` and
`curated_interactions/curated_interactions_v1.json::interactions`; evidence:
`rg interaction_rules scripts/contracts/source_of_truth_matrix.json scripts/GLOSSARY.md`.
Exact medication membership remains `drug_classes.json::classes`; gate vocabulary
remains `clinical_risk_taxonomy.json` and `drug_class_vocab.json`. Will NOT create:
a new dose field, a new severity, a parallel interaction registry, or a made-up threshold.
`apply_batch8_remaining.py` is a bounded one-shot audit procedure, following the
existing batch apply scripts. This is behavioral clinical-data correction, not display-only.

Per-entry implementation (Codex source/application work; G1 is the prior named decision):

- `RULE_INGREDIENT_OMEGA_3`, `RULE_INGREDIENT_FISH_OIL`,
  `RULE_IQM_DHA_BLEEDING`, `RULE_IQM_EPA_BLEEDING`: anticoagulant and antiplatelet
  subrows now monitor with identical copy, sources and profile gates per class.
  Direction/materiality and dose-floor state also agree. Sources are ODS and
  PMID 38742535 (11 randomized trials, 120,643 participants; no overall bleeding
  increase; high-dose purified EPA subgroup differs). These are four separate
  canonical identities with one consistent ordinary-supplement finding, not an
  assertion that all preparations have identical trial evidence. Prescription purified
  EPA remains explicitly separate. `DSI_WAR_OMEGA3` is Minor, the curated monitor
  counterpart; no new amount boundary. INR advice applies only if taking warfarin.
- `RULE_IQM_CALCIUM` and `RULE_IQM_IRON_HYPERTENSION`, thyroid subrows only:
  identical shared caution copy and sources, oral levothyroxine at least four hours
  apart. Current SYNTHROID SPL setid `1e11ad30-1041-4520-10b0-8f9d30d30fcc`
  was read through DailyMed XML on 2026-11-12: administration §2.1, §7.1 calcium
  carbonate/ferrous sulfate binding, and patient counseling explicitly support four
  hours. Removed calcium study-dose and absorption/metabolism generalization.
- `RULE_IQM_CHROMIUM_GLUCOSE`, thyroid subrow only: direct evidence identifies
  chromium picolinate, not every form; PMID 17725434 reports seven volunteers,
  acute levothyroxine absorption, and recommends several hours separation. Removed
  invented exact four-hour interval. Actual subrow form applicability remains unresolved.
- `RULE_IQM_NIACIN_DIABETES`, diabetes condition and three hypoglycemic classes
  only: pharmacologic nicotinic-acid glucose concern, known niacinamide exclusion
  through the existing gate; mixed/unknown forms retain caution. Current ODS content
  and niacin-ER setid `249e27ac-e1e7-42dc-84f6-cd32fd1d9dee` distinguish treatment
  exposure and do not establish a universal 1-g onset. Daily amount gating is not
  completed. Liver-disease and high-cholesterol subrows are parsed-identical to HEAD;
  statin subrow unchanged. Independent parent review caught and corrected an initial
  overly broad loop before handoff; regression protects the unrelated findings.
- `RULE_IQM_VITAMIN_B6_LACTATION`: corrected false claim that the current gate
  already excludes normal multivitamin quantities, universal prenatal suitability,
  and mechanistic certainty. Live PubMed EFetch PMID 28425124: seven studies,
  450–600 mg/day for 5–7 days, inconsistent suppression and prolactin results.
  PMID 569255 is a historical recommendation whose abstract calls the mechanism
  conjecture. The historical source does not override the later synthesis. No 50-mg
  boundary introduced. Existing caution remains while quantitative implementation
  is unresolved; this is NOT completion of the requested routine-dose suppression.
- `RULE_IQM_GREEN_TEA_HYPERTENSION`: replaced broad antihypertensive/beta-blocker
  drug rows with one exact nadolol row, preserving existing avoid severity from the
  beta-blocker row. Hypertension alone now supplies conditional informational text.
  Primary PMID 24419562 supports approximately 85% lower nadolol exposure and
  OATP1A2 uptake inhibition; no universal spacing or extract threshold. Exact class
  membership RxNorm API content verified on 2026-11-12: 7226, nadolol, IN, suppress N.
  Added existing-shape class, taxonomy and nonselectable vocabulary entry. Vocab
  group label and commonly-used-for strings are copied unchanged from the approved
  beta-blocker entry. No extra clinical copy signoff is invented.

Focused validation: six defect classes failed first. After fixes, new B8 tests plus
vocabulary contract: **24 passed**. Profile-gate, taxonomy, reachability and new B8
slice: **36 passed** before the vocabulary-only addition. Drug schema initial failure
was the explicit newly added class allowlist, addressed by the parent; taxonomy
count fixed at its owner. `git diff --check` passes. Consumer gate probes prove known
niacinamide suppresses, mixed/unknown forms retain, and broad beta-blocker membership
cannot fire the nadolol gate. No broad/local/release or CI run is claimed here; the
parent owns the combined checkpoint and real-product replay.

Remaining delivery limits:

1. Product-detail composition was verified with eight canonical omega rows: after
   eligibility checks, the existing presentation owner merges both medicine classes
   into one concern. Single-class controls also pass; 33 focused consumer tests passed.
   Exact curated Stack rows retain their existing ID-based dedupe.
2. Niacin excludes known niacinamide, but routine nicotinic-acid nutrient amounts
   still receive the presence-based conditional caution. No agreed source-supported
   treatment boundary with validated daily/Stack exposure has been implemented.
3. B6 routine-quantity lactation suppression remains unimplemented. Existing rule and
   pregnancy/lactation fallback both lack a validated exposure gate. Do not label it
   completed or infer a source threshold from a study dose.
4. Chromium thyroid applicability now uses a separate entry under the existing
   form-scope owner. Confirmed non-picolinate forms are excluded; mixed picolinate,
   unspecified and unresolved forms retain the qualified warning. Glucose findings
   remain unchanged. Rebuilt product references and rule sources must ship together.
5. Taxonomy/class/vocabulary source changes require fresh app assets and the parent's
   candidate validation. Old catalog artifacts do not contain these changes.

Final focused update: combined owner/consumer slice had 454 passes and two new-class
required-field failures. RxClass live API returned nadolol 7226 in C07AA
(nonselective beta blockers); adding rxclass_id/atc_codes using that verified
classification fixed both targeted nodes (2 passed). Curated class membership
remains only nadolol, not the whole ATC class. Parent owns the final integrated
validation. No broad suite was repeated for this metadata fix.
