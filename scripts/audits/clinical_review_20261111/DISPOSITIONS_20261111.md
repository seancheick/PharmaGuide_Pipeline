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
| A3 SAMe + MAOIs | Decided: reject the downgrade; contraindicated for tranylcypromine (PARNATE §4.1 and §7 list SAM-e). Pending (**ask 1**): the other MAOIs, whose labels do not name SAMe | Corrected after an outside review of #444 (`apply_same_scope_correction.py`). New exact pair `DSI_TRANYLCYPROMINE_SAME` Contraindicated (evidence established). Class pair `DSI_MAOI_SAME` stays Contraindicated, so nothing is lowered while ask 1 is open; its exported mechanism states the class inference and its evidence is moderate. Profile rule `RULE_IQM_SAME` maois keeps its published avoid (evidence moderate): a profile that says only "MAOI" does not identify tranylcypromine, and a contraindicated profile rule is hidden without a matching profile until G4, which would drop SAMe's conditional note |
| B1 statin + gemfibrozil | Split by statin; simvastatin contraindicated; others per own label | New exact pair `DDI_SIMVASTATIN_GEMFIBROZIL` Contraindicated; class pair Moderate → Major (every marketed statin label says avoid or not recommended); the advice to switch to pravastatin or fenofibrate is removed. App: an exact medicine pair now replaces the class pair for the same two medicines |
| B2 ciprofloxacin + theophylline | Avoid for systemic ciprofloxacin | Moderate → Major; label management only (avoid; if unavoidable, theophylline levels monitored and dose adjusted by the prescriber); unsourced "30–50%" and the azithromycin suggestion removed; text says it is for tablets, liquid or IV, and asks drop users to check with a pharmacist. Medicines carry no route, so drops are not silently excluded |
| F9 NAC + nitroglycerin | Caution, hypotension-focused | New pair `DSI_NITROGLYCERIN_NAC` (RxCUI 4917 + acetylcysteine C0001047, canonical `nac`) Moderate, from the UK acetylcysteine SmPC §4.5 and PMID 9120179. Nitroglycerin only; no other nitrate is claimed. Management follows §4.5: if both are used, ask the prescriber how blood pressure should be checked. NAC's ingredient-map entry gets its exact CUI back (C0001047, acetylcysteine; RXNORM atom 197 is the entry's RxCUI) so the verifier keeps the pair's canonical id `nac` |

Data consistency check for the exact-over-class rule: an authored exact pair that overlaps a class pair for the same
two agents must never be the weaker warning (`test_an_exact_pair_that_hides_a_class_pair_is_never_the_weaker_warning`).
It checks records only; how the app matches medicines is covered by the app checker tests: an exact pair replaces a
class pair for the same two medicines only when each class side contains the exact pair's medicine in `drug_class_map`,
so a combination product keeps a class warning another ingredient matches, even with a partial saved ingredient list. Overlaps today: simvastatin + gemfibrozil
(Contraindicated over Major), tranylcypromine + SAMe (Contraindicated over Contraindicated) and warfarin + turmeric
(Moderate over Moderate). Equal severity alone does not make two findings interchangeable; each overlap is the same
concern for the same two agents.

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

### Batch 3a implemented: anticoagulant scope (`apply_batch3a_anticoagulant_scope.py`)

"Warfarin only" is two sub-rules with one text (`apply_batch3a_vka_scope.py`, after an independent review showed
that `anticoagulants` minus `doacs` let a DOAC elsewhere in the list veto an identified warfarin):
`vitamin_k_antagonists` fires for an identified warfarin-type medicine whatever else is entered; `anticoagulants`
minus `doacs` and `vitamin_k_antagonists` is the fallback for a blood thinner that is not identified ("Blood
thinners" is the only selectable blood-thinner class). A DOAC user gets neither. Each rule's evidence level equals
the tier `verify_interactions.py` derives for its pair (one interaction, one tier).

Limits of this scope (agent finding; see "Other vitamin K antagonists" under Questions): other VKAs (phenprocoumon, acenocoumarol)
receive the warfarin-label findings through the class. Betrixaban, an oral factor Xa inhibitor (ATC B01AF, inside
the `doacs` class's ATC scope; BEVYXXA label: P-gp substrate), was in neither class; it now joins `doacs` (identity
fix, `apply_batch3a_betrixaban_doac.py`), so it leaves the warfarin-addressed fallback and gets the DOAC St. John's
wort finding, still avoid. Four identified medicines in `anticoagulants` remain in neither class: the injected direct
thrombin inhibitors argatroban, bivalirudin, desirudin and lepirudin (ATC B01AE but not oral). They fall into the
fallback, as before 3a, and see the warfarin-addressed text ("If you take warfarin, ..."); a "Blood thinners"
selection plus an entered DOAC reads as that DOAC. Separating them needs a new exclusion id in the profile vocabulary,
and so Dr. Pham's sign-off (question 7).

| Row | Implemented as |
|---|---|
| A2 SJW + warfarin | Pair Major; rule contraindicated → avoid, warfarin only; UK SmPC 4.5 and DailyMed warfarin label cited; "other vitamin-K antagonists" removed (not verified) |
| A4 CoQ10 + warfarin | Pair Moderate → Minor (background lane, a pipeline label), label evidence with low confidence (tier probable: the label's "may" example and mixed trials); rule monitor, warfarin only. Headline "May reduce warfarin effect" ("mildly" removed: the label says "may decrease", not how much); the cohort PMID 17723077 (CoQ10 associated with self-reported bleeding, OR 3.69; observational, does not establish cause) is cited and stated |
| A5 ginkgo + warfarin | Pair Major → Moderate; rule caution on presence (120 mg floor removed); "do not combine" removed |
| A6 garlic + warfarin | Pair Moderate; rule monitor → caution on presence. Removed the 600 mg floor **and** a rule-level tier the packet did not show (> 1200 mg avoid, otherwise monitor), which replaced the sub-rule severity in the enricher; its source (NCCIH garlic) states no dose. Caution now ships at every amount |
| A7 glucosamine + warfarin | Pair Minor → Moderate; rule caution, warfarin only; "2–4 weeks" removed; PMID 18363538 and the UK SmPC cited; PMID 23946031 kept (teaching case, INR 3.9 after a glucosamine–chondroitin supplement; full text read 2026-11-11) |
| A8 cranberry + warfarin | Pair Moderate, rule monitor → caution, warfarin only; mixed evidence (PMIDs 18516070, 19553405); UK avoid instruction recorded in evidence_notes; MHRA link removed |
| A9 ginger + warfarin | Pair Minor → Moderate; rule caution, warfarin only (identified VKA, or an unidentified blood thinner; DOACs excluded) with copy naming warfarin; cohort (17723077) and crossover (15801937) cited with limits; NCCIH ginger page removed (it does not mention bleeding) |
| A10 fish oil + NSAIDs | Pair Moderate → Minor (background lane); rule monitor; LOVAZA label with the extrapolation stated; icosapent ethyl named as separate; "with food" removed |

Agent dispositions in the same batch (not Dr. Pham's decisions, no review record on them):
- Ginger's blood-thinner scope (outside review on PR #447, reproduced): the rule first kept every blood thinner, but
  its sources cover warfarin users and healthy volunteers only, so it now has the warfarin-only scope of A2, A4, A7
  and A8. Ginkgo and garlic keep every blood thinner: each cites an NCCIH page that names blood thinners in general.
- `RULE_OTHER_GINGER_EXTRACT_BLEEDING` (the same subject under its other-ingredient identity) cited the NCCIH ginger
  page, which does not mention bleeding, warfarin or platelets (read 2026-11-11), and claimed "mild antiplatelet or
  anticoagulant activity". It now carries the A9 finding and scope (`apply_batch3a_ginger_scope.py`).
- The 600 mg (garlic) and 120 mg (ginkgo) floors also sat on the antiplatelet sub-rules; same unsupported floor, removed.
- The same floors on the antihypertensive sub-rules (garlic 600 mg, ginkgo 120 mg) and garlic's diabetes tier stay for
  batch 4 with the other noise rows.
- `DSI_WAR_GINGER` left the high-dose exemption list (its text no longer mentions high-dose use); two gold profile-gate
  cases that pinned the removed garlic tier were replaced by cases on live gates (garlic on presence; the
  warfarin-only gate for a DOAC user and for an unknown blood thinner). The app's copy of that fixture moves with it.
- April "clinician-locked" severities W2, W3, W6 and W12 in tests now follow this review.

### Batch 3b part 1 implemented: medication membership (`apply_batch3b_memberships.py`)

Membership is by RxNorm ingredient (IN), the level the app matches on, so combination products are reached through
their ingredients and route is not distinguished. Labels were read on DailyMed 2026-11-11; setids are in each class's
notes.

| Row | Implemented as |
|---|---|
| D1 thyroid examples | `methimazole` removed from the vocabulary examples; "replace or modulate" now reads "thyroid hormone replacement". class:thyroid_medications already excluded methimazole and propylthiouracil |
| D2 anticholinergics | Added diphenhydramine and nine tricyclics whose own labels state anticholinergic properties or atropine-like action: amitriptyline, amoxapine, clomipramine, desipramine, doxepin, imipramine, nortriptyline, protriptyline, trimipramine. Not added: maprotiline (no current DailyMed label), other antihistamines, SSRIs. Real combination sleep aids (RxNorm 1092189 acetaminophen/diphenhydramine, 895664 diphenhydramine/ibuprofen) reach the class in the pipeline and app tests |
| D3 tirzepatide, pramlintide | Tirzepatide: unknown → lower-risk tier (MOUNJARO 5.3); with insulin or a sulfonylurea entered, that medicine adds the high-risk tier. Pramlintide stays in the conservative unknown tier (SYMLIN 5.2), whose severities equal the high-risk tier's |
| F7 CBD split | **Not applied (ask 5).** Separate sub-rules need the rule classes `clobazam` and `valproate`, and every vocabulary entry carries consumer copy (group label, "commonly used for") under your 2026-08-08 sign-off |

Agent dispositions in the same batch (not Dr. Pham's decisions):
- The thyroid tap-to-learn note told users to separate iodine, kelp, soy isoflavones and biotin from levothyroxine by
  4 hours. The SYNTHROID label gives 4 hours for binders such as calcium carbonate and ferrous sulfate, and says to
  stop biotin at least 2 days before TSH/T4 tests; the note now says that.
- The class reaches two rules, which now also reach diphenhydramine and tricyclic users. An independent review found
  their text did not fit: alpha-GPC promised lost efficacy and "monitor for loss of efficacy" for every member, and
  huperzine A said the effects "cancel" (the donepezil label says cholinesterase inhibitors have the "potential to
  interfere"). Alpha-GPC's text is now scoped to medicines taken for their anticholinergic action; huperzine A's
  says the two "can work against each other". Severities unchanged (alpha-GPC caution, huperzine A avoid); ask 6.

### Batch 3b part 2 implemented: licorice, levodopa + iron, CBD/everolimus (`apply_batch3b_part2_*.py`)

| Row | Implemented as |
|---|---|
| A14 licorice + antihypertensives | Both sub-rules (`RULE_IQM_LICORICE_HYPERTENSION`, `RULE_BOTANICAL_LICORICE_ROOT`) caution → avoid with one shared text; EMA liquorice monograph (EMA/HMPC/108399/2024 Rev. 1, 4.5) cited. Verified DGL is excluded by identity; an unknown preparation is not assumed to be DGL |
| F4 cardiac glycosides + licorice | New `cardiac_glycosides` avoid sub-rule and pair `DSI_CARDIACGLYC_LICORICE` (Major): EMA 4.5, the LANOXIN hypokalemia warning, PMID 28660884. No glycyrrhizin floor |
| Licorice identity | Chinese licorice (G. uralensis, inside the monograph's scope) now twins to licorice, and "Glycyrrhiza uralensis root" / "... root extract" reach it; DGL lost its bare "Glycyrrhiza glabra" alias, which belongs to whole licorice, and gained the DGL names that were unmapped ("Licorice Root Extract, DGL", "GutGard Deglycyrrhizinated Licorice (DGL) root extract", "standardized Deglycyrrhized Licorice extract"). "Licorice root extract (deglycyrrhizinated)" and "... (DGL)" now reach DGL: the cleaner reads a trailing parenthetical that names a distinct botanical preparation as its curated comma form; source parentheticals such as "(Glycyrrhiza glabra)" keep whole licorice (second review; no current label uses these names). No current label names G. inflata |
| F2 levodopa + iron | Pair `DSI_LEVODOPA_IRON` (Moderate), keyed on levodopa's ingredient RxCUI 6375, from the SINEMET label; no interval (the label gives none). The label names iron salts, including multivitamins that contain them; the pair covers every iron form as a precaution and says so. Carbidopa/levodopa (SCD 197444) and carbidopa/entacapone/levodopa (SCD 403851) reach it through their ingredients; carbidopa alone does not (app test). Inhaled levodopa (INBRIJA) also matches the ingredient, and its own label (setid 077c0f39, section 7.3) says iron salts can chelate levodopa and reduce its bioavailability, with no interval; the pair cites both labels (second review) |

Representative replay (second review, `replay.py` freeze-raw on origin/main 50d07e40e vs this branch): GutGard DGL
(229869), Solgar standardized deglycyrrhized extract plus raw licorice powder (44423), Herbal Terra Gan Cao
(G. uralensis, 233763, label fetched from the DSLD API) and Jarrow licorice root extract (307549, control). Score,
all six pillars and status are unchanged on all four. Identity changes do reach Evidence review: GutGard's row moved
from whole licorice to DGL, which has a Dose record but no Evidence review yet, so its evidence readiness went from
complete to incomplete; Solgar's not-yet-evaluated count went from 1 to 2. Warnings: GutGard lost the whole-licorice
findings; Solgar keeps them through its raw licorice powder; Gan Cao gained them; the control gained the
antihypertensive and cardiac glycoside gates. Corpus-wide impact is measured only by the final corpus run.

Agent dispositions in the same batch (not Dr. Pham's decisions):
- **GutGard.** It keeps routing to DGL. The source (PMID 39929150) describes a deglycyrrhizinated extract with
  glycyrrhizin ≤3.0% w/w, and the one DSLD label (229935, on market) states <1%. The exemption rests on your DGL policy,
  not on interaction-safety evidence for that glycyrrhizin level.
- **CBD + immunosuppressants.** Everolimus (RxCUI 141704) is already in `class:immunosuppressants`, so it reaches
  the CBD caution. The text named only tacrolimus and sirolimus and said "CBD affects immune function", which the
  label does not say. It now follows EPIDIOLEX 7.2: oral everolimus exposure about 2.5-fold, other oral
  P-glycoprotein substrates may rise, monitor levels and adjust the dose; not generalized to every CYP3A4
  substrate. The headline and body no longer say "transplant" (everolimus is also used for tuberous sclerosis and
  cancer). Severity and gate unchanged. Two gaps go to ask 5.
- **Licorice citation.** `RULE_BOTANICAL_LICORICE_ROOT` dropped PMID 31605160 and its "failed BP control" claim: the
  paper is a glycyrrhizin-metabolite biomarker study, not an interaction study.
- **Copy length** (`apply_batch3b_part2_copy_limits.py`). The licorice antihypertensive and digoxin bodies and the
  CBD immunosuppressant body and note were over the authoring limits (`validate_safety_copy`). Each is shortened
  only: severity, "avoid" with the prescriber condition, the DGL distinction, the named medicines and the sources
  are unchanged, and the `action` fields keep the full wording.
- **Twelve stored canonical ids** that differed from what the build ships, one disposition each. Nothing shipped
  changes; a test keeps stored and shipped ids equal.

| Pair(s) | Stored → now | Why |
|---|---|---|
| DSI_ANTICOAG_VINPOCETINE | `nootropic_vinpocetine` → `vinpocetine` | stale stored id; shipped id correct |
| DSI_IMMUNOSUP_PROBIOTICS | `probiotic_unspecified` → `probiotics` | stale stored id; shipped id correct |
| DSI_BETABLOCK_EPHEDRA | `ephedra` → `BANNED_EPHEDRA` | product-side id (banned list); 0 products |
| DSI_MAOI_TYRAMINE | `tyramine` → `ADD_TYRAMINE_RICH_EXTRACT` | product-side id (additive); 0 products |
| DSI_STATINS_GRAPEFRUIT, DSI_CCB_GRAPEFRUIT, DSI_IMMUNO_GRAPEFRUIT, DSI_LEVOTHYROXINE_COFFEE | `grapefruit` / `coffee` → none | food advisories; no supplement id by design |
| DSI_STATINS_RYR; DSI_ANTICOAG_CBD, DSI_ANTIHYP_CBD, DSI_STATINS_CBD | unchanged | stored and shipped ids normalize to the same supplement (`BANNED_RED_YEAST_RICE` / `RISK_RED_YEAST_RICE` → red yeast rice; `cbd` / `BANNED_CBD_US` → cbd) |

### Batch 3c part 1 implemented: fluoroquinolone spacing (`apply_batch3c_fluoroquinolone_spacing.py`)

| Row | Implemented as |
|---|---|
| A12 zinc + fluoroquinolones | Three exact pairs, each Moderate with its own label interval and direction: `DSI_ZINC_CIPROFLOXACIN` (at least 2 hours before or 6 hours after; CIPRO setid 888dc7f9), `DSI_ZINC_LEVOFLOXACIN` (2 hours before or after; levofloxacin setid 5c6c117c), `DSI_ZINC_MOXIFLOXACIN` (4 hours before or 8 hours after; moxifloxacin setid 1e6bc886). Each says injected forms are not affected. The class pair `DSI_ZINC_FLUOROQUINOLONE` Major → Moderate and still tells ofloxacin, delafloxacin and gemifloxacin users to follow their own label; the app's exact-over-class rule shows the exact pair to users of the three named medicines |
| A13 calcium + ciprofloxacin | `DSI_CALCIUM_CIPROFLOXACIN` Major → Moderate; calcium supplements, multivitamins with calcium and antacids at least 2 hours before or 6 hours after; not with milk, yogurt or calcium-fortified juice on their own, while the label allows a meal that contains them; injected ciprofloxacin not affected |

Labels read 2026-11-11 from DailyMed SPL XML; RxCUIs 2551, 82122 and 139462 checked live; PMID 1524699 (a 1992
review) stays as supporting evidence. The profile rules (`RULE_IQM_ZINC`, `RULE_IQM_CALCIUM` fluoroquinolone rows)
were already caution with "the interval on the antibiotic label", so they agree without change.

### Batch 3c part 2 (timing rules, rows C and G3): constraint found before authoring

The timing contract (`timing_optimization.dart`, `TimingRelation`) rejects a `separate_from` rule without a positive
`minimum_hours`, and has no "take together" or combination-information relation. So three decisions cannot be
published as written without a new relation type (a new semantic owner, which needs Sean): iron–calcium "different
times of day" (publishable only by adopting MedlinePlus's 2-hour context, which Dr. Pham allows), iron–zinc
non-precise advice (also needs the ≥25 mg elemental iron condition, and no dose gate is proven), and L-theanine–caffeine
optional combination information. Plan for the rest, not yet authored or source-checked: publish levothyroxine–magnesium on D27
with the evidence split; split psyllium into liquid guidance, label spacing and 3 hours for digoxin, salicylates and
nitrofurantoin; reject calcium–vitamin D and quercetin–vitamin C into `timing_rules_rejected.json`; keep melatonin,
bromelain, probiotics, soy and EGCG held with her decision recorded; calcium carbonate with food waits on form
matching.

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
   (MARPLAN) and selegiline (EMSAM, ZELAPAR, capsules) do not name SAMe (read 2026-11-11). NARDIL contraindicates
   "concomitant use of NARDIL with serotoninergic agents" as a category. For each medicine: is SAMe covered by its
   label language (contraindicated), a precautionary class inference (which severity), or pending? Until then the
   class pair stays Contraindicated and the class profile rule stays avoid.
2. **Vitamin E.** What counts as "ordinary nutrient exposure" for the less prominent note (form, amount, frequency)?
3. **Glucosamine with warfarin.** The UK warfarin SmPC (section 4.5) says the combination is not recommended, which is
   closer to avoid than to the caution you chose. Keep caution, or align with the UK label? Batch 3a ships caution.
4. **Low-dose doxepin.** Doxepin joins the anticholinergic class (its capsule label states anticholinergic effects),
   so huperzine A shows avoid and alpha-GPC caution for every doxepin user. SILENOR (3-6 mg for sleep) lists
   anticholinergic effects only above 6 mg. Membership is by ingredient, so neither strength nor route can be told
   apart (topical diphenhydramine and doxepin products also match). Keep doxepin in the class, or leave it out? And
   is the topical match acceptable, as with ciprofloxacin drops in batch 2?
   **Release blocker:** the wider class ships no further than this branch until asks 4 and 6 are answered. No
   SILENOR strength cutoff is derived meanwhile: membership is by ingredient, and the label sets no supplement
   threshold.
5. **CBD split (F7): wording for two new rule classes.** Separate clobazam and valproate rules need two rule-only
   vocabulary entries. Proposed copy, for your sign-off:
   - `clobazam`: group label "Seizure medications"; "Commonly used to help prevent seizures, including in
     Lennox-Gastaut syndrome."
   - `valproate`: group label "Seizure medications"; "Commonly used to help prevent seizures, and also for bipolar
     mania or migraine prevention."
   The rules would follow the EPIDIOLEX label (setid 8bf27097, read 2026-11-11): clobazam, about 3-fold higher
   N-desmethylclobazam (its active metabolite) and more somnolence and sedation (46% with clobazam vs 16% without);
   valproate, more liver-enzyme elevations with no change in valproate exposure; both stated as findings for
   prescription oral cannabidiol. The label also names **stiripentol** (higher stiripentol exposure; monitor for its
   adverse reactions), which the packet did not list. The current single rule warns everyone in the 40-medicine
   anticonvulsant class (stiripentol and cannabidiol included) plus clobazam and valproate. Should the split add a
   stiripentol rule, and should it end the warning for the other anticonvulsants, for which the label reports no
   effect of cannabidiol on the medicine? The seizure-disorder condition rule stays either way.
   Two related gaps from the everolimus check: `class:immunosuppressants` also holds injected biologics the
   EPIDIOLEX label does not concern, and digoxin (a P-glycoprotein substrate the label names) has no CBD rule.
   Should the CBD immunosuppressant rule be limited to oral small-molecule immunosuppressants, and should digoxin
   get a CBD finding?
6. **Rules the wider anticholinergic class reaches.** Huperzine A (avoid, "do not combine") and alpha-GPC (caution)
   now reach every diphenhydramine and tricyclic user, including combination sleep aids. Should both reach medicines
   whose anticholinergic effect is a side effect, or only the primary antimuscarinics? Narrowing either needs a
   separate rule class, which needs your copy sign-off like ask 5.
7. **Other vitamin K antagonists.** The four warfarin-only findings (A2, A4, A7, A8) cite warfarin sources. They now
   fire for the `vitamin_k_antagonists` class, which also holds phenprocoumon and acenocoumarol where a user enters
   them. Keep the class scope (same mechanism, no source read for those medicines), or limit the findings to warfarin?
   Also: argatroban, bivalirudin, desirudin and lepirudin are identified but reach the unidentified blood-thinner
   fallback and its warfarin-addressed text. Should these four injected direct thrombin inhibitors get a class of
   their own that the fallback excludes? (Betrixaban now reads as a DOAC: its label and ATC code place it there.)
