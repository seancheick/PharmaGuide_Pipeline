# Batch A: severity-conflict source receipts (2026-11-11)

Read-only research. Records read from /Users/seancheick/worktrees/dsld-interaction-baseline
(`scripts/audits/interaction_audit_20261111/conflicts.json`, `scripts/data/curated_interactions/*.json`,
`scripts/data/ingredient_interaction_rules.json`). Raw sources saved under
`/private/tmp/claude-501/-Users-seancheick-Downloads-dsld-clean/3bef6da5-f891-47f1-85be-767d3f9063d6/scratchpad/conflicts/src_a/`
(PubMed efetch for all 11 PMIDs in one call; NCCIH, MSKCC, DailyMed fetched once each).

---

## 1. DSI_ANTIHYP_LICORICE vs RULE_IQM_LICORICE_HYPERTENSION/drug_class_rules[0]

- **Pair:** Major -> `avoid`. Whole antihypertensive class; "Licorice root (glycyrrhizin)". Management: avoid glycyrrhizin-containing licorice unless the clinician has reviewed it; DGL is a different preparation, but only if the label establishes it.
- **Rule:** `caution`, evidence `probable`. Action: "Monitor blood pressure and review supplement use with clinician." Mechanism text says it "Does not apply to DGL", but `profile_gate.excludes.nutrient_forms_any` is empty, so the DGL exclusion exists only in prose (not enforced by the gate). Dose gate: none.
- **Scope difference:** the same class and the same subject. Both records exclude DGL, but only in text. Neither record has a dose gate.

| Source | Quote | Supports |
|---|---|---|
| NCCIH https://www.nccih.nih.gov/health/licorice-root (cited by both) | "Even small amounts of glycyrrhizin from licorice root products have been linked to severe adverse effects ... in people with hypertension" | Pair (severe effects at small amounts in the population on these drugs). No explicit "avoid" verb; NCCIH otherwise says to talk with a provider. |
| NCCIH (same) | "Oral licorice products that do not contain glycyrrhizin (deglycyrrhizinated licorice) might be safe for up to 4 months." | Both (DGL carve-out) |
| PMID 28660884 (pair) meta-analysis, 18 studies, >=100 mg GA/day | "chronic licorice ingestion is associated with an increase in blood pressure and a drop in plasma potassium, even at modest doses ... of particular relevance for individuals with existing cardiovascular disease" | Pair (content matches the claim) |
| PMID 38246526 (rule) RCT, healthy young adults | "significant increases in BP, after a daily intake of only 100 mg GA. Thus, the safe limit ... might need to be reconsidered" | Both; it supports the rule's mechanism text (content matches) |
| PMID 12574791 (rule) | "mean rise in systolic BP ... 3.5 mmHg (p<0.06) in NT and 15.3 mmHg (p=0.003) in hypertensive subjects" | Pair: hypertensive people respond about 4x more strongly, which argues against "monitor" alone |

- **Sources support:** a stronger action than "monitor" for glycyrrhizin-containing licorice in people with hypertension: NCCIH reports severe effects even at small amounts, and hypertensive people respond about 4x more. No source gives a regulatory "do not use", but no source supports a "monitor only" action either.
- **Proposed resolution:** align on the pair (`avoid` for glycyrrhizin-containing licorice, with DGL excluded only when the label establishes it). Reason: in people with hypertension, the cited NCCIH page and the hypertensive-cohort trial describe severe or amplified BP effects at small doses. Also note for the owner: the rule's DGL exclusion is prose-only and the gate does not enforce it.
- **Confidence:** medium (the direction is clear, but no source uses an explicit "avoid" verb).
- **Ghost/dead citations:** none. All 3 PMIDs match their topic, and NCCIH is live.

---

## 2. DSI_CALCIUM_CIPROFLOXACIN vs RULE_IQM_CALCIUM/drug_class_rules[1]

- **Pair:** Major -> `avoid`. Ciprofloxacin only (RxCUI 2551). Its management is a timing instruction: "Take oral ciprofloxacin at least 2 hours before or 6 hours after calcium-containing supplements".
- **Rule:** `caution`, evidence `established`, whole fluoroquinolone class. Action: separate doses by the interval on the antibiotic label.
- **Scope difference:** one drug vs the whole class. Both records are oral-route chelation. Both actions are separation, so the pair's severity (`avoid`) contradicts its own management text.

| Source | Quote | Supports |
|---|---|---|
| DailyMed ciprofloxacin tablets, setid d10f7c93-a08b-4e9c-bfa2-6646e3ea21bd (pair; label effectiveTime 2012-09-14, old generic SPL) | "Ciprofloxacin should be administered at least 2 hours before or 6 hours after ... other products containing calcium, iron or zinc." | Rule (a separation instruction, not avoidance); also confirms the pair's 2 h/6 h interval |
| Same label | "may be taken with a meal that contains these products" | Rule: the combination is not prohibited, only timed |
| DailyMed levofloxacin tablets, setid 5261da15-1b6c-fbe2-e063-6394a90ad85e (rule) | "Absorption of levofloxacin is decreased when the tablets are taken within 2 hours of these products." | Rule (class scope; a timing interaction) |
| DailyMed setid 1496ea0f-1419-c809-e063-6294a90a0b43 (rule) | HTTP 404 from the SPL v2 service | **Dead citation** |
| PMID 1524699 (pair) Drug Saf 1992 review | "Quinolone absorption is markedly reduced with antacids containing aluminium, magnesium and/or calcium and therapeutic failure may result." | Mechanism only (content matches); gives no action |

- **Sources support:** the drug label's instruction is to separate doses (cipro 2 h before or 6 h after), not to avoid the combination. That fits the rule's `caution` and both records' separation action. The label outranks the 1992 review.
- **Proposed resolution:** move the pair to `caution`, keeping its cipro-specific 2 h/6 h text. The rule stays `caution`. Reason: the label's interaction instruction is a timing separation, and `avoid` contradicts both the label and the pair's own management text.
- **Confidence:** high.
- **Ghost/dead citations:** the rule source DailyMed setid 1496ea0f-1419-c809-e063-6294a90a0b43 returns 404 (dead). The pair's cipro SPL is a 2012 version; it is live but old, and a current label could replace it.

---

## 3. DSI_IMMUNO_ASTRAGALUS vs RULE_INGREDIENT_ASTRAGALUS__AUTOIMMUNE/drug_class_rules[0]

- **Pair:** Moderate -> `caution`, but its management says "Avoid astragalus with immunosuppressant therapy" (it contradicts itself). Whole class.
- **Rule:** `avoid`, evidence `theoretical`. Action: "Do not use astragalus with immunosuppressive medications." Its own mechanism admits "preclinical work involved isolated compounds and tumor-immunotherapy models, not clinical antagonism of all immunosuppressants". Alert: "Astragalus stimulates the exact immune pathways immunosuppressants calm".
- **Scope difference:** the same class. The rule id is autoimmune-themed, but this sub-rule is gated on the drug class only, with no condition gate.

| Source | Quote | Supports |
|---|---|---|
| NCCIH https://www.nccih.nih.gov/health/astragalus (pair) | "astragalus may interact with medications that suppress the immune system." | Pair `caution` ("may interact"; no avoid) |
| NCCIH (same) | "Because astragalus might worsen symptoms of autoimmune diseases, people with autoimmune diseases should avoid using astragalus." | `avoid` belongs to the **autoimmune-disease condition** scope, not the drug class |
| NCCIH (same) | "adding astragalus to supportive care or immunosuppressive therapy for ... membranous nephropathy resulted in greater improvements" | Contradicts the rule's blanket claim that astragalus undermines immunosuppressants |
| PMID 32190660 (rule) mouse study: APS-derived anti-PD-1 scFv, antitumor | "phage-display technology was utilized to isolate specific anti-programmed death-1 (PD-1) antibodies from mice stimulated by APS" | Neither. It says nothing about immunosuppressant drugs; it is off-topic for the interaction claim |

- **Sources support:** `caution` for the drug class ("may interact"). `avoid` is supported only for a person with an autoimmune disease (a condition scope), which this drug-class sub-rule does not gate on.
- **Proposed resolution:** the drug-class severity is `caution` (pair). Change the pair's management verb from "Avoid" to talk-with-transplant-or-rheumatology-team wording. Downgrade the rule sub-rule to `caution`, or leave the avoid to the autoimmune condition rule. Remove or replace PMID 32190660 as the interaction source. Reason: NCCIH says only "may interact" for immunosuppressants, reserves "avoid" for autoimmune disease, and reports astragalus used alongside immunosuppressive therapy.
- **Confidence:** medium-high.
- **Ghost/dead citations:** PMID 32190660 is a ghost reference for this claim: a real paper on a different topic (an antitumor anti-PD-1 antibody, not an immunosuppressant interaction). The rule's alert copy ("exact immune pathways") is unsourced.

---

## 4. DSI_IMMUNO_CATSCLAW vs RULE_INGREDIENT_CAT_S_CLAW/drug_class_rules[3]

- **Pair:** Moderate -> `caution`, but its management says "Avoid cat's claw with immunosuppressants" (it contradicts itself). Whole class.
- **Rule:** `avoid`, evidence `probable`. Action: "Do not combine with immunosuppressants."
- **Scope difference:** the same class; no gates.

| Source | Quote | Supports |
|---|---|---|
| Pair URL https://nccih.nih.gov/health/herbsataglance.htm | Redirects to the Herbs at a Glance **index page**, which only lists herb names | Neither. It is a non-specific citation that gives no claim |
| NCCIH cat's claw fact sheet https://www.nccih.nih.gov/health/cats-claw (fetched as the specific page behind that index; not cited) | "Cat's claw might make the immune system more active ... If you have an autoimmune disease, consult your health care provider before using cat's claw." | `caution`, and in an autoimmune-condition scope. The page lists theoretical interactions with anticoagulant, antiplatelet and BP drugs, and none with immunosuppressants. |
| MSKCC https://www.mskcc.org/cancer-care/integrative-medicine/herbs/cat-claw (rule) | "Oxindole alkaloids in cat's claw have immunostimulating properties in vitro" | Mechanism is in vitro only, which is not `probable` evidence |
| MSKCC (same) | "In vitro, cat's claw inhibits CYP3A4 and may increase the serum levels of drugs such as ... cyclosporine" | Neither. It is a different mechanism (raises drug levels, the opposite of antagonism) and gives no avoid instruction. MSKCC has no contraindication with immunosuppressants. |

- **Sources support:** at most `caution`, on theoretical or in-vitro evidence. No cited source says "avoid" or "do not combine" with immunosuppressants. The only clinical-facing guidance (NCCIH) is "consult your provider" for autoimmune disease.
- **Proposed resolution:** `caution` (pair severity). Set rule evidence_level to `theoretical`, drop "Do not combine", and fix the pair management verb. Optionally mention the in-vitro CYP3A4 effect, which may raise cyclosporine levels. Replace the pair's index-page URL with the NCCIH cat's claw page. Reason: no source supports `avoid`, and the rule's "probable" grade rests on in-vitro data.
- **Confidence:** medium (the sources are thin either way; `avoid` is clearly unsupported).
- **Ghost/dead citations:** the pair's herbsataglance URL is an index page with no relevant content (non-specific citation).

---

## 5. DSI_MAOI_SAME vs RULE_IQM_SAME/drug_class_rules[0]

- **Pair:** Contraindicated -> `contraindicated`. Whole MAOI class. Clinical confidence `low`; its own evidence_notes say "This is a precaution, not a quantified human combination risk."
- **Rule:** `avoid`, evidence `limited`. Action: "avoid SAMe unless cleared by your prescriber. Allow washout if switching." Its mechanism text says outright: "No study of SAMe with an MAOI was found."
- **Scope difference:** none (the same class, no gates).

| Source | Quote | Supports |
|---|---|---|
| NCCIH https://www.nccih.nih.gov/health/sadenosyllmethionine-same-in-depth (both) | "It's also possible that SAMe might interact with drugs and dietary supplements that increase levels of serotonin ... such as antidepressants" | Rule, or weaker. "Possible ... might" does not support contraindicated |
| PMID 7854515 (rule) Neurology 1995, case report + review | "serotonin syndrome occurs following the use of serotomimetic agents (... S-adenosylmethionine) alone or in combination with monoamine oxidase inhibitors" | Rule `avoid` (a class listing; the case patient took trazodone + isocarboxazid, not SAMe) |
| PMID 8434674 (rule) Am J Psychiatry 1993 letter "Toxic interaction of S-adenosylmethionine and clomipramine" | Letter, no abstract; the title matches the rule text | Rule. It concerns SAMe + a TCA, not an MAOI |

- **Sources support:** `avoid`. No source documents SAMe with an MAOI, and NCCIH says only "might interact". The case literature puts SAMe among serotomimetics that are risky with MAOIs, which supports avoidance but not a contraindication.
- **Proposed resolution:** move the pair to `avoid`, matching the rule. Reason: the pair's own notes and clinical_confidence `low` concede there is no established combination risk, and contraindicated needs a stronger source than "might interact".
- **Confidence:** medium.
- **Ghost/dead citations:** none; the PMIDs match their topics. Minor: the rule's "Allow washout if switching" has no source, though it gives no specific number.

---

## 6. DSI_NADOLOL_GREEN_TEA vs RULE_IQM_GREEN_TEA_HYPERTENSION/drug_class_rules[0]

- **Pair:** Major -> `avoid`. **Nadolol only** (RxCUI 7226); applies_to `dose_dependent`. Management: avoid concentrated extract; for brewed tea, consult the prescriber, because separating doses may not fully prevent the interaction.
- **Rule:** `caution`, evidence `theoretical`, gated on the **whole antihypertensives class**. The mechanism, action and alert copy are all nadolol-specific, and the copy itself says "Effects on other blood-pressure medicines need separate review."
- **Scope difference:** a single drug vs the whole class. The rule fires for every antihypertensive although all of its evidence is about nadolol. Preparation also differs: the pair distinguishes extract from brewed tea, the rule does not.

| Source | Quote | Supports |
|---|---|---|
| PMID 24419562 (both) 10 volunteers, 700 mL/day x14 d | "Green tea markedly decreased the maximum plasma concentration ... and AUC ... of nadolol by 85.3% and 85.0% ... effects of nadolol on systolic blood pressure were significantly reduced" | Pair, for nadolol: human PK plus a BP effect, so evidence is not "theoretical" |
| PMID 29480324 (pair) single-dose EGCG extract | "geometric mean ratios ... 0.72 ... for the low and 0.60 ... for the high dose ... No significant changes were observed for blood pressure" | Partly contradicts the pair's extract-over-tea emphasis: the extract cut AUC 28-40% with no BP change |
| PMID 32320490 (pair) single cup of brewed tea | "AUC0-48 was 0.371 ... with concomitant GT ... 1 hour before ... 0.536" | Pair: brewed tea cut exposure about 63%, and a 1 h gap still cut about 46%, so separation does not prevent it |
| PMID 25312732 (rule) review | "limited so far to warfarin, simvastatin and nadolol, and suggest that the average effects are mild to modest" | Rule: no human data for other antihypertensives, so the class-wide scope is unsupported |

- **Sources support:** different scopes. For **nadolol**, human studies show large exposure loss (up to 85%) and a blunted BP effect, which separating doses does not prevent. That supports the pair's stronger action at evidence grade established/probable, not theoretical. No label instruction exists. For **other antihypertensives**, the sources are insufficient: the review says data are limited to nadolol, and the rule's own copy concedes this.
- **Proposed resolution:** keep the pair (`avoid`) for nadolol, but note that the data do not support its split between extract (avoid) and brewed tea (consult): brewed tea had the larger effect, so both preparations should get the same action. Narrow the rule sub-rule to nadolol, or drop its class-wide firing. A class-wide alert for every antihypertensive is unsupported (insufficient source). Reason: all the human evidence is nadolol-specific.
- **Confidence:** medium. The scope finding is high-confidence. `avoid` vs `caution` for nadolol is a judgement, since no label instruction exists.
- **Ghost/dead citations:** none; all 4 PMIDs match their topics. The rule's evidence_level `theoretical` contradicts its own cited human PK study.
