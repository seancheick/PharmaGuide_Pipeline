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
