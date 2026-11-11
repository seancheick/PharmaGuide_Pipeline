# PharmD review packet: interaction audit (2026-11-11)

Prepared by agents for the designated PharmD. Nothing here is clinician-reviewed yet. Approve, change or reject each
row; approval is recorded against the exact content named. Receipts: `research_stage2.md`, `research_stage3.md`,
`conflict_receipts_{a,b,c}.md` (per-source quotes). "Verified" means the main agent re-read the quoted passage
itself; other rows rest on the research-agent receipt.

## A. Severity conflicts: curated pair vs profile rule (17)

The app shows the profile rule on the product page and, in the Stack, the harder of the two. Each row needs one decision
per situation. Proposals never raise a severity without a source and never lower one silently.

| Pair / rule | Now (pair vs rule) | Proposal | Basis | Conf. |
|---|---|---|---|---|
| `DSI_OC_SJW` / SJW `[7]` | avoid vs contraindicated | avoid (rule ↓) | YAZ label lists St. John's wort among products that "may decrease the effectiveness"; not in Contraindications. Verified | high |
| `DSI_WAR_SJW` / SJW `[1]` | avoid vs contraindicated | avoid (rule ↓); rule wording "Do not combine" softened to match; scope to vitamin-K antagonists | Warfarin label §7.5: botanicals that "may decrease the effects" (CoQ10, St. John's wort, ginseng); more frequent INR monitoring. Verified | high |
| `DSI_MAOI_SAME` / SAMe `[0]` | contraindicated vs avoid | avoid (pair ↓) | NCCIH: SAMe "might interact" with serotonin-raising drugs; the rule notes no study of SAMe with an MAOI. Verified | medium |
| `DSI_WAR_COQ10` / CoQ10 `[0]` | caution vs monitor | monitor (pair ↓), INR at start/stop | Warfarin label §7.5 (as above). Verified. Rule covers all anticoagulants; evidence is warfarin-only | medium |
| `DSI_WAR_GINKGO` / ginkgo `[1]` | avoid vs caution | caution (pair ↓); rule alert_body "do not combine" contradicts its own caution | NCCIH: "may increase the risk of bleeding in people who are taking anticoagulant drugs, such as warfarin". Verified. Rule's 120 mg threshold is not in its source | medium |
| `DSI_WAR_GARLIC` / garlic `[0]` | caution vs monitor | caution (rule ↑) | NCCIH: talk with provider; MSKCC lists warfarin under "do not take if". Rule's 600 mg floor not in its source | medium-high |
| `DSI_WAR_GLUCOSAMINE` / glucosamine `[0]` | monitor vs caution | caution, warfarin only | FDA pharmacovigilance review PMID 18363538 (20 MedWatch reports). Rule's class scope and "2–4 weeks" have no source | medium |
| `DSI_WAR_CRANBERRY` / cranberry `[0]` | caution vs monitor | monitor (pair ↓) | NCCIH: evidence "conflicting"; warfarin label does not name cranberry. Pair's only source (MHRA PDF) is dead | medium |
| `DSI_WAR_GINGER` / ginger `[0]` | monitor vs caution | no change until sourced | Both records cite NCCIH ginger, which never mentions bleeding or anticoagulants (verified): ghost citation in both | low |
| `DSI_NSAID_FISHOIL` / fish oil `[2]` | caution vs monitor | monitor (pair ↓); drop rule's unsourced "Take NSAIDs with food" | No readable cited source covers fish oil with NSAIDs | low |
| `DSI_SEDATIVES_ASHWAGANDHA` / ashwagandha `[0]` | monitor vs caution | monitor (rule ↓) | NCCIH "might interact"; rule's only PMID 38003702 is an endocrine review (verified title) | medium |
| `DSI_ZINC_FLUOROQUINOLONE` / zinc `[1]` | avoid vs caution | caution with the label's spacing (pair ↓) | CIPRO label: take 2 h before or 6 h after zinc-containing products; no "avoid". Verified | high |
| `DSI_CALCIUM_CIPROFLOXACIN` / calcium `[1]` | avoid vs caution | caution with spacing (pair ↓) | same label. Verified | high |
| `DSI_ANTIHYP_LICORICE` / licorice `[0]` | avoid vs caution | avoid for glycyrrhizin licorice (rule ↑), with a DGL exclusion in the gate, not only in text | NCCIH: severe effects at small amounts with hypertension; PMID 12574791 | medium |
| `DSI_IMMUNO_ASTRAGALUS` / astragalus `[0]` | caution vs avoid | caution (rule ↓); pair's "Avoid" wording fixed | NCCIH "may interact"; rule's only PMID 32190660 is a tumour anti-PD-1 antibody study (verified title): ghost | medium-high |
| `DSI_IMMUNO_CATSCLAW` / cat's claw `[3]` | caution vs avoid | caution (rule ↓); evidence → theoretical | MSKCC in vitro only; pair's NCCIH link is an index page | medium |
| `DSI_NADOLOL_GREEN_TEA` / green tea `[0]` | avoid vs caution | different scopes: keep pair avoid for nadolol; narrow the rule from all antihypertensives to the drugs its sources cover | human studies on nadolol only | medium (scope high) |

## B. Label-backed severity questions (possible under-warning)

| Pair | Now | Label |
|---|---|---|
| `DDI_STATIN_GEMFIBROZIL` | Moderate (caution) | gemfibrozil label: simvastatin contraindicated; any statin "DOES NOT OUTWEIGH THE RISKS OF SEVERE MYOPATHY, RHABDOMYOLYSIS, AND ACUTE RENAL FAILURE". Verified |
| `DDI_THEOPHYLLINE_CIPRO` | Moderate | CIPRO label: "Serious and fatal reactions"; monitor levels "if concomitant use cannot be avoided". Verified |

## C. Text changed in Stage 3 batch 1 (already applied; confirm)

Unsupported intervals removed: iron + calcium "2 hours" → "different times of the day" (ODS); levothyroxine + soy
"4 hours" → different time, ask how far apart; psyllium + diabetes medicines "2 hours" → talk to prescriber, monitor
glucose. Magnesium + levothyroxine "4 hours" kept (Sean, D27). Open: publish the held magnesium timing card on the D27
basis?

## D. Stage 2 membership questions

1. Thyroid class excludes antithyroid drugs, but the profile vocabulary's examples list methimazole.
2. Diphenhydramine and tricyclics are not in the anticholinergic class.
3. Tirzepatide and pramlintide sit in the conservative unknown hypoglycemic tier.

## E. Sources still missing (no change until sourced)

- `RULE_IQM_PSYLLIUM_DIABETES`: its only source never mentions psyllium.
- Ginger + anticoagulants (both records); fish oil + NSAIDs; cranberry pair's dead MHRA source.

## G. Stage 4: volume drivers, theoretical rules, held timing (review lists)

Full tables: `stage4_review_list.md` (regenerate with `stage4_review_list.py`). Volumes come from the 4,000-product
baseline sample and only rank rules for review; they are not a false-positive rate. No severity, scope or dose gate
changes without a decision here. A dose gate is added only where a source sets the number, or as a product policy
you approve and we label as policy.

### G1. Decide first (largest effect on what a user sees)

| Rule | Fires for | Question |
|---|---|---|
| `RULE_IQM_VITAMIN_E_PREGNANCY_EXCESS` anticoagulants | 534 of 4,000 products (any vitamin E) | Text says "above 400 IU/day", but nothing gates on amount, so a 30 IU multivitamin gets the bleeding caution. The cited ODS sheet (read 2026-11-11): amounts needed for clinically significant effects "are unknown but probably exceed 400 IU/day". Gate at 400 IU/day on that basis (below it: monitor or informational), or keep presence-based? |
| `RULE_IQM_DHA_BLEEDING`, `RULE_IQM_EPA_BLEEDING` anticoagulants/antiplatelets | 226 / 203 | caution, evidence theoretical, any amount. Monitor, or caution only above a sourced amount? |
| `RULE_INGREDIENT_VITAMIN_D` anticoagulants | 187 | monitor, theoretical; text names 10,000 IU, not gated |
| `RULE_IQM_MAGNESIUM_HYPERTENSION` kidney_disease, `RULE_IQM_POTASSIUM_HYPERTENSION` kidney_disease | 484 / 411 | avoid on any amount. The app does not know CKD stage. Avoid, or caution with "depends on kidney function; ask your nephrologist"? |
| `RULE_IQM_CALCIUM`, `RULE_IQM_ZINC`, `RULE_IQM_MAGNESIUM_HYPERTENSION`, `RULE_IQM_CHROMIUM_GLUCOSE`, `RULE_IQM_IRON_HYPERTENSION` thyroid_medications | 684 / 597 / 484 / 370 / 265 | All caution. These are absorption interactions managed by spacing. Zinc's evidence is theoretical with one source. One message with the spacing as the management; severity per mineral? |
| `RULE_IQM_VITAMIN_B6_LACTATION` lactation | 499 | caution, theoretical; text names 50 mg and 600 mg, not gated |
| `RULE_IQM_NIACIN_DIABETES` | 513 | caution, established; text names 1 g, not gated: most products carry nutrient amounts of niacin |
| `RULE_IQM_GREEN_TEA_HYPERTENSION`, `RULE_IQM_L_THEANINE_ANTIHYPERTENSIVES` | 82 / 56 | caution, theoretical; text names amounts, not gated |

### G2. Theoretical or limited evidence at caution or above (109 sub-rules)

Listed individually in `stage4_review_list.md`. Decision per row: keep, lower, narrow scope, or source it. Rows
already in section A keep their section A decision. Notable: `RULE_INGREDIENT_ST_JOHNS_WORT` maois contraindicated
on theoretical evidence; `RULE_IQM_CITRUS_BERGAMOT_CHOLESTEROL` immunosuppressants contraindicated on limited
evidence; four MAOI contraindications (phenylethylamine, hordenine, L-tyrosine, St. John's wort) rest on one or two
sources each.

### G3. The 13 held timing rules

Each stays unpublished until a decision: approve, narrow, replace the unsupported precision, or reject. Batch 1 made
sure no other record restates a held interval (gate `TestHeldIntervalsStayUnpublished`).

| Rule | Held for |
|---|---|
| `timing_iron_calcium_separate`, `timing_iron_zinc_separate`, `timing_thyroid_med_magnesium_separate`, `timing_thyroid_med_soy_separate` | interval not in the cited source (magnesium: see C, D27) |
| `timing_calcium_vitamin_d_together`, `timing_psyllium_water_med_spacing`, `timing_quercetin_vitamin_c_together`, `timing_l_theanine_caffeine_together` | awaiting clinician decision |
| `timing_melatonin_before_bed`, `timing_bromelain_timing_by_purpose` | citation not content-verified |
| `timing_probiotics_by_formulation`, `timing_calcium_carbonate_with_food` | canonical identity unresolved |
| `timing_egcg_iron_separate` | form-specific evidence missing |

### G4. App behaviour checked (code read, app SHA on `claude/interaction-matching`)

- Stack tier (`StackIntelligence.deriveTier`): counts only contraindicated, avoid, caution and monitor; an
  informational finding never lowers the tier. Any caution caps the stack at "Decent", so each G1 caution that
  becomes monitor also lifts the tier for those users. No code change needed.
- Kidney disease: the profile stores kidney disease as one condition with no stage, so every kidney rule fires as
  if disease were present and significant. Options: word kidney rules as "depends on kidney function", or add a
  stage to the profile (a new profile field: Sean's call).
- Anonymous users (`build_final_db.py::_INTERACTION_DISPLAY_MODE`, sprint E1.1.2): with no profile, "avoid"
  condition and drug-class rules show as a neutral note, while "contraindicated" ones are hidden. Intentional per
  its comment (condition-specific copy should not reach users it does not apply to), but the same reasoning applies
  to "avoid" copy such as pregnancy wording. Decide: suppress both without a profile, or show both as neutral notes.

## F. Stage 3 proposed additions (not applied)

Receipts with full proposed records: `additions_receipts_a.md`, `additions_receipts_b.md` (agent research). "Verified"
means the main agent re-read the label passage on 2026-11-11. Nothing below is in the data until approved.

| Proposal | Severity proposed | Basis | Open for you |
|---|---|---|---|
| `DSI_ISOTRETINOIN_VITAMIN_A` (isotretinoin RxCUI 6064 + vitamin A) | Major | Absorica §7.1: "Avoid concomitant use … with supplements containing vitamin A". Verified | RxCUI covers all routes (topical too); include beta-carotene? |
| `DSI_LEVODOPA_IRON` (levodopa 6375 + iron) | Moderate | Sinemet: iron salts "should be coadministered with caution"; chelation lowers absorption. Verified. No interval stated, none supplied | does the matcher map carbidopa/levodopa products to 6375? |
| `DSI_CALCIUM_BISPHOSPHONATE` (class:bisphosphonates + calcium) | Major, matching `DSI_MAGNESIUM_BISPHOSPHONATE` | each label's own spacing: alendronate ≥½ h after dose; risedronate IR ≥30 min before, calcium another time of day; ibandronate 60 min | class includes IV zoledronic acid (same gap as the magnesium pair) |
| `DSI_CARDIAC_GLYCOSIDE_LICORICE` (class:cardiac_glycosides + glycyrrhizin licorice; DGL is a separate id) | Major (judgment) | LANOXIN: hypokalemia "may predispose to digoxin toxicity"; PMID 28660884 glycyrrhizin lowers potassium; one case report (title only) | severity on an inferred chain |
| Lamotrigine + ethinyl estradiol (RxCUI 4124, not class:oral_contraceptives, which holds progestins only) | Moderate | Lamictal: ethinylestradiol "increased the clearance of lamotrigine up to 2-fold"; progestin-only pills "had no effect". Verified | lands together with narrowing `DDI_ANTICONV_OCP` |
| `DDI_ANTICONV_OCP` narrowed to class:enzyme_inducing_antiseizure_medications (carbamazepine, phenobarbital, phenytoin, primidone) | unchanged | its text describes inducers | its text names oxcarbazepine and topiramate: oxcarbazepine needs its own pair (Trileptal label warning); topiramate is dose-dependent |
| CBD: split `RULE_BANNED_CBD_INTERACTIONS` anticonvulsants into clobazam and valproate sub-rules | caution | Epidiolex label (8bf27097): clobazam active-metabolite rise; valproate transaminase rise | current text is accurate but generic; clobazam also raises transaminases less often |
| Ashwagandha + thyroid_medications sub-rule | monitor, limited | NCCIH "might interact with … thyroid hormone medications"; PMID 28829155 raised T3/T4 off levothyroxine | the existing condition rule says "Contraindicated in hyperthyroidism"; NCCIH says "not recommended" |
| NAC + nitroglycerin (4917) | Minor | PMID 9120179: oral NAC with transdermal nitroglycerin, side effects mainly headache, about twice nitroglycerin alone | NAC CUI needs UMLS check; no nitrate class |
| Psyllium + digoxin | none recommended | PMID 3038494: ispaghula "had no influence"; LANOXIN names bran meals, not psyllium | optional general spacing record |
| `RULE_IQM_PSYLLIUM_DIABETES` source | replace ghost NCCIH link with PMID 38844885 (2024 meta-analysis, 19 trials) | glucose-lowering supported | no human source for "fiber delays absorption of metformin/sulfonylureas": remove that claim |
