# Interaction packet: one disposition per row (2026-11-11)

Prepared by an agent from Dr. Pham's review and response (`DR_PHAM_REVIEW_20261111.md`, verbatim). The decisions are
hers; this file only maps each to a packet row and an implementation batch. Rows marked **ask** need her answer
before they change. Packet: `../interaction_audit_20261111/PHARMD_PACKET.md`.

Batches follow her sequence: 2 = label-backed corrections (this PR), 3 = scope, membership, F additions and timing,
4 = noise reductions after the quantity checks pass, 5 = one combined comparison on a frozen data version.

## Policies adopted (apply to every batch)

- **Terminology.** Contraindicated: an applicable authoritative source explicitly contraindicates the combination
  (a class-level contraindication counts when the source covers the class and membership is verified). Avoid: strong
  recommendation against, including an approved precaution. Caution: needs professional review or a plan. Monitor: a
  named observation. A timing instruction is management, not severity. Absence from a contraindication list is not
  evidence of safety; existing contraindicated rows are reviewed one by one, never bulk-renamed.
- **No automatic downgrade** from "theoretical", "might", a dead citation or one small negative trial.
- **Content contract** on every changed record, using existing fields: consequence (mechanism/body), action,
  evidence basis kept separate from certainty, applicability (drug, route, preparation, quantity, missing data). The
  evidence for an interaction and the evidence for its management interval are recorded separately.
- **All text fields agree**: headline, body, mechanism, action, informational note, timing text, chatbot.
- **Scoring**: the Stack grading algorithm stays as it is; grade changes caused by corrected rules are explained in
  the comparison, never overridden. The product-only score is not changed by personal interactions.
- **Dose gates**: none activates until per-unit, per-serving and per-day amounts, elemental vs salt, EPA/DHA vs fish-oil
  mass, missing amounts and Stack totals are proven for that rule.

## Batch 2: label-backed corrections (this PR)

| Row | Decision | Implemented as |
|---|---|---|
| A3 SAMe + MAOIs | Decided: reject the downgrade; contraindicated for tranylcypromine (PARNATE §4.1 and §7 list SAM-e). Pending (**ask 1**): the other MAOIs, whose labels do not name SAMe | Pair `DSI_MAOI_SAME` stays Contraindicated with the label added; profile rule `RULE_IQM_SAME` maois raised avoid → contraindicated so both agree. For the other MAOIs this keeps the pair's existing class-wide contraindication as a documented class inference, the option her A3 decision allows, so no warning is lowered while she answers ask 1 |
| B1 statin + gemfibrozil | Split by statin; simvastatin contraindicated; others per own label | New exact pair `DDI_SIMVASTATIN_GEMFIBROZIL` Contraindicated; class pair Moderate → Major (every marketed statin label says avoid or not recommended); the advice to switch to pravastatin or fenofibrate is removed. App: an exact medicine pair now replaces the class pair for the same two medicines |
| B2 ciprofloxacin + theophylline | Avoid for systemic ciprofloxacin | Moderate → Major; label management only (avoid; if unavoidable, theophylline levels monitored and dose adjusted by the prescriber); unsourced "30–50%" and the azithromycin suggestion removed; text says it is for tablets, liquid or IV, and asks drop users to check with a pharmacist. Medicines carry no route, so drops are not silently excluded |
| F9 NAC + nitroglycerin | Caution, hypotension-focused | New pair `DSI_NITROGLYCERIN_NAC` (RxCUI 4917 + acetylcysteine C0001047, canonical `nac`) Moderate, from the UK acetylcysteine SmPC §4.5 and PMID 9120179. Nitroglycerin only; no other nitrate is claimed. Management follows §4.5: if both are used, ask the prescriber how blood pressure should be checked. NAC's ingredient-map entry gets its exact CUI back (C0001047, acetylcysteine; RXNORM atom 197 is the entry's RxCUI) so the verifier keeps the pair's canonical id `nac` |

Consistency check for the exact-over-class rule: an exact pair that replaces a class pair for the same two agents
must never be the weaker warning (`test_an_exact_pair_that_hides_a_class_pair_is_never_the_weaker_warning`). Today two
overlaps exist: simvastatin + gemfibrozil (Contraindicated over Major) and warfarin + turmeric (Moderate over Moderate).

## Batch 3: scope, membership, additions, timing

| Row | Decision |
|---|---|
| A1 SJW + hormonal contraception | Avoid, scoped to affected hormonal methods (MHRA); not intrauterine methods automatically |
| A2 SJW + warfarin | Keep avoid; UK warfarin label; starting and stopping both need attention; other VKAs verified separately |
| A4 CoQ10 + warfarin | Monitor, warfarin only; anticoagulation-team review at start/stop/change; drop all-anticoagulant scope |
| A5 ginkgo + warfarin | Caution; remove the 120 mg threshold; wording matches the action |
| A6 garlic + warfarin | Caution for supplements and concentrates; remove the 600 mg floor; not culinary exposure |
| A7 glucosamine + warfarin | Caution, warfarin only; remove "2–4 weeks" |
| A8 cranberry + warfarin | Caution for supplements, concentrates and unknown preparations; contact the anticoagulation team at start/stop/change; mixed evidence and preparation limits stated; UK avoid instruction recorded; no dose gate; not contraindicated (response) |
| A9 ginger + warfarin | Caution for supplemental or concentrated ginger; cite the cohort and crossover study with their limits |
| A10 fish oil + NSAIDs | Monitor; omega-3 labeling with the extrapolation stated; prescription EPA kept separate; drop "take NSAIDs with food" |
| A11 ashwagandha + sedatives | No class-wide downgrade; caution for prescription sedatives or several sedating medicines |
| A12 zinc + fluoroquinolones | Caution with drug-specific spacing: ciprofloxacin 2 h before or 6 h after; levofloxacin 2 h before or after; moxifloxacin 4 h before or 8 h after; not injected forms |
| A13 calcium + ciprofloxacin | Caution with label spacing; supplements and dairy/fortified juice alone differ from calcium in a meal |
| A14 licorice + antihypertensives | Avoid for glycyrrhizin licorice; verified DGL excluded in matching; unknown preparation is not DGL |
| A15 astragalus + immunosuppressants | Caution; stronger pre-use review for tacrolimus/transplant; replace the ghost citation with the case report |
| A16 cat's claw + immunosuppressants | Caution, precautionary; specialist review in transplant; NCCIH herb–drug page as source |
| A17 green tea + nadolol | Keep avoid for nadolol; no invented interval; narrow the broad antihypertensive rule |
| C iron + calcium | Keep "different times of day"; do not say no source gives 2 h (MedlinePlus does) |
| C levothyroxine + soy | Keep removal of the 4 h claim; separate soy food/protein from isoflavone extracts |
| C psyllium + diabetes medicines | Keep glucose monitoring; product-label 2 h spacing may be used as a product instruction |
| C levothyroxine + magnesium | Publish on the D27 precautionary basis; ThyroMag supports the interaction, not the 4 h interval |
| D1 thyroid examples | Correct the vocabulary example; methimazole stays out of the replacement class |
| D2 anticholinergics | Add oral diphenhydramine (and combination sleep/cold products in matching tests); review tricyclics individually |
| D3 tirzepatide, pramlintide | Tirzepatide lower risk alone, higher with insulin or a secretagogue; pramlintide without insulin entered = incomplete regimen |
| E sources | Psyllium–diabetes PMID 38844885 (glucose outcomes only); ginger cohort + crossover; omega-3 labeling; cranberry current labeling |
| F1 isotretinoin + vitamin A | Avoid, oral isotretinoin; beta-carotene not auto-exempt; a reviewed exception is needed to suppress for beta-carotene-only products |
| F2 levodopa + iron | Caution; carbidopa/levodopa products must resolve; no interval |
| F3 calcium + bisphosphonates | Caution with formulation-specific timing (alendronate 30 min, ibandronate 60 min, Atelvia after breakfast); IV excluded; review the magnesium row too |
| F4 cardiac glycosides + licorice | Avoid, glycyrrhizin licorice; EMA monograph; DGL excluded; no safe floor |
| F5 lamotrigine + ethinyl estradiol | Caution; direction explained (estrogen lowers lamotrigine; stopping raises it) |
| F6 anticonvulsant–contraceptive narrowing | Only with replacement coverage in the same change: inducers kept, oxcarbazepine added, topiramate own context with no ≤200 mg suppression |
| F7 CBD split | Separate caution rules: clobazam (active metabolite, sedation), valproate (liver enzymes); prescription oral-CBD context preserved |
| F8 ashwagandha + thyroid medication | Narrow caution, limited evidence, clinician review; revise "contraindicated in hyperthyroidism" to the NIH wording |
| F10 psyllium + digoxin | Precautionary timing record: MedlinePlus says not within 3 h; keep the negative study in the evidence record |
| F11 psyllium–diabetes source | Approve; remove the metformin/sulfonylurea absorption claim |
| G2 SJW + MAOIs | Keep the strong warning; ZELAPAR lists it; improve evidence metadata and scope |
| G2 L-tyrosine + MAOIs | Keep the phenelzine (NARDIL) hard warning; not every MAOI or dietary protein; fix the tyramine wording in its note |
| G2 PEA, hordenine + MAOIs | Strong precaution kept; record the class inference; hordenine evidence is preclinical; scoped decision, no automatic change |
| G2 citrus bergamot + immunosuppressants | Avoid unsupervised use with the relevant transplant medicines, precautionary; not "strictly contraindicated with all" |
| G2 remaining rows | Individual disposition each (keep with better source, narrow, lower on evidence, or hold with a named question); severe first, then high volume |
| G3 iron–calcium | Publish the "different times" version |
| G3 iron–zinc | Publish narrower non-precise advice (ODS: ≥25 mg elemental iron taken together) |
| G3 levothyroxine–magnesium | Publish on D27 with the evidence split recorded |
| G3 levothyroxine–soy | Narrow and revise before publishing; generic 4 h stays held |
| G3 calcium–vitamin D together | Reject as a timing rule; optional adequacy education, no bonus |
| G3 psyllium water/medication spacing | Publish after splitting: liquid guidance; label spacing; 3 h for digoxin, salicylates, nitrofurantoin only |
| G3 quercetin–vitamin C together | Reject; no Stack bonus |
| G3 L-theanine–caffeine together | Optional combination information only |
| G3 melatonin before bed | Split by formulation and purpose before publishing |
| G3 bromelain by purpose | Keep held or remove |
| G3 probiotics by formulation | No universal timing penalty; follow verified product/strain instructions |
| G3 calcium carbonate with food | Approve once form matching works (citrate distinct) |
| G3 EGCG/tea–iron | Keep the capsule/extract rule held |

## Batch 4: noise reductions (after quantity checks)

| Row | Decision |
|---|---|
| G1 vitamin E + anticoagulants | Correct wording and evidence now. Numerical suppression **held**: below 400 IU is not automatically "ordinary"; missing amount, frequency, form or Stack total blocks a dose-derived downgrade; other bleeding findings are kept. **ask 2** |
| G1 DHA/EPA | One monitor-level omega-3 finding; prescription icosapent ethyl separate; no 3 g/5 g cutoff |
| G1 vitamin D + anticoagulants | Remove the 10,000 IU cutoff and the all-anticoagulant scope; keep the warfarin evidence record; conditional, non-interruptive note for ordinary products; monitoring wording only for starting/changing deficiency treatment |
| G1 magnesium / potassium + kidney disease | Caution with "check with your kidney-care team before adding this" wording; no new CKD-stage field required |
| G1 calcium, iron + levothyroxine | Caution with the supported 4 h instruction; one card for shared management |
| G1 magnesium + levothyroxine | Keep; ThyroMag added; 4 h recorded as adopted precaution |
| G1 chromium + levothyroxine | Narrow the direct evidence to chromium picolinate |
| G1 zinc + levothyroxine | Informational/theoretical; any spacing marked as precautionary policy |
| G1 B6 + lactation | Remove the milk-suppression caution at routine amounts; 50 mg boundary not established; B6 toxicity kept separate |
| G1 niacin + diabetes | Narrow by form and exposure; no absolute 1 g boundary; nicotinamide does not inherit nicotinic-acid claims |
| G1 green tea + antihypertensives | Drug-specific coverage (nadolol); remove the 400 mg threshold; caffeine tied to caffeine exposure |
| G1 L-theanine + antihypertensives | Informational/theoretical; no Stack grade effect |
| G4 Stack grade | Algorithm unchanged; before/after grade examples required |
| G4 kidney profile | Conditional wording with the existing field; no stage questionnaire now |
| G4 anonymous users | Show avoid and contraindicated drug/condition findings as conditional notes when applicability is unknown; no personalized verdict |

## Questions for Dr. Pham

1. **SAMe with MAOIs other than tranylcypromine.** The current labels for phenelzine (NARDIL), isocarboxazid
   (MARPLAN) and selegiline (EMSAM, ZELAPAR, capsules) do not name SAMe (read 2026-11-11). This batch keeps the
   class-wide contraindication as a documented class inference, so no warning is lowered. Confirm, or set "avoid"
   for those medicines.
2. **Vitamin E.** What counts as "ordinary nutrient exposure" for the less prominent note (form, amount, frequency)?
