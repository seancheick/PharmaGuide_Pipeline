# Batch C: severity conflict source receipts (read-only)

Worktree: /Users/seancheick/worktrees/dsld-interaction-baseline. Records were printed from
`scripts/data/curated_interactions/curated_interactions_v1.json` and
`scripts/data/ingredient_interaction_rules.json`. Raw fetched sources are in
`/private/tmp/claude-501/-Users-seancheick-Downloads-dsld-clean/3bef6da5-f891-47f1-85be-767d3f9063d6/scratchpad/conflicts/src_c/`.
Mapping used by conflicts.json: Major→avoid, Moderate→caution, Minor→monitor.

Changing a severity is a clinical/policy decision for the owner (AGENTS.md). The resolutions below are proposals.

---

## 1. DSI_WAR_GARLIC vs RULE_INGREDIENT_GARLIC/drug_class_rules[0]

- **Pair:** Moderate → **caution**. Warfarin (RxCUI 11289) + "Garlic (supplement)". Materiality: presence; dose_threshold null. Management: "Talk to your warfarin prescriber before starting, stopping or changing garlic supplements… ask whether INR checks are needed." Source: NCCIH garlic.
- **Rule:** **monitor**, evidence_level established. Applies to the whole anticoagulants class. Materiality dose_dependent, with min_effective_dose 600 mg/day (source MSKCC garlic, confidence "inferred_from_dose_range"). Action: "monitor for bruising or bleeding when adding a garlic supplement."
- **Scope difference:** the pair covers warfarin only, from any amount of supplement. The rule covers all anticoagulants and only fires at 600 mg/day or more. The pair's own mechanism text says the cited monographs "do not establish a 600 mg safe-below threshold".

| Source | Quote | Supports |
|---|---|---|
| NCCIH garlic, https://www.nccih.nih.gov/health/garlic (the pair's old ataglance URL redirects here) | "If you take anticoagulants, aspirin, or any other medicine, talk with your health care provider before using garlic" | Pair: consult before use, which is caution, not monitor |
| NCCIH garlic | "Taking garlic supplements may increase the risk of bleeding." | Both records (direction only) |
| MSKCC garlic, https://www.mskcc.org/cancer-care/integrative-medicine/herbs/garlic | "Do Not Take if: You are taking warfarin or other blood thinners: Garlic may increase the risk of bleeding or bruising." | Neither record: stronger than both, at the avoid level |
| MSKCC garlic | "Patients taking warfarin or other blood thinners should ask their doctor before taking garlic supplements." | Pair (caution) |
| MSKCC garlic (checked for the rule's 600 mg threshold) | The page contains no "600" and no threshold dose (grep returned 0 hits) | Contradicts the rule's min_effective_dose citation |

- **Sources support:** at least caution, meaning talk to the prescriber before use. That applies to warfarin and, per both sources, to "other blood thinners". No source supports a 600 mg threshold or a monitor-only action. MSKCC leans toward avoid.
- **Proposed resolution:** move the rule to **caution** to match the pair, and use a consult-before-use action. Remove the 600 mg min_effective_dose or re-source it. Reason: both sources tell anticoagulant users to consult before starting garlic, and the cited threshold is not in its source.
- **Confidence:** medium-high on caution over monitor. Whether MSKCC's "Do Not Take" justifies avoid is a separate decision for the owner.
- **Citation defect:** the rule's `min_effective_dose.source` (MSKCC) does not contain the 600 mg figure, so the value is unsupported. All URLs were live.

---

## 2. DSI_WAR_GINGER vs RULE_IQM_GINGER_BLEEDING/drug_class_rules[0]

- **Pair:** Minor → **monitor**. display_layer is background. Warfarin + "Ginger (high dose supplement)". Mechanism: "Human platelet studies of ginger have mixed results." Source: NCCIH ginger.
- **Rule:** **caution**, evidence_level probable. Applies to the whole anticoagulants class. Materiality presence with no dose gate. Alert: "Ginger has mild antiplatelet or anticoagulant activity… talk to your prescriber before adding ginger". Source: NCCIH ginger.
- **Scope difference:** warfarin with high-dose supplements (pair) versus all anticoagulants with any amount of ginger, culinary included (rule).

| Source | Quote | Supports |
|---|---|---|
| NCCIH ginger, https://www.nccih.nih.gov/health/ginger | The page has 0 matches for bleed, platelet, warfarin or anticoag. The only interaction text is "If you take any type of medicine, talk with your health care provider before using ginger or any other herbal products" | Neither record. It is generic advice and says nothing about a bleeding interaction. |
| NCCIH ginger | "Ginger has been used safely in many research studies where it was taken orally (by mouth) as a dietary supplement." | Neither record. If anything it argues against caution. |

- **Sources support:** nothing. The only source both records cite does not mention bleeding, platelets or anticoagulants. It supports neither the pair's "platelet studies" mechanism nor the rule's "mild antiplatelet or anticoagulant activity".
- **Proposed resolution:** **insufficient source.** Keep the pair's lower-assertion background monitor and do not raise anything to caution until a real source is added (for example a ginger–warfarin clinical study or review, checked by content). The rule's presence-level caution on all anticoagulants is the larger unsupported claim.
- **Confidence:** low, because no source answers either way.
- **Citation defect:** NCCIH ginger is cited for a bleeding claim it does not make. It is a real page on the wrong topic, which counts as a ghost reference for this claim in both records.

---

## 3. DSI_WAR_GINKGO vs RULE_IQM_GINKGO_HYPERTENSION/drug_class_rules[1]

- **Pair:** Major → **avoid**. Warfarin + ginkgo, presence. Management: "Avoid adding ginkgo during warfarin treatment without anticoagulation-clinician review." Sources: NCCIH ginkgo and PMID 26958257. The pair's own evidence_notes say the evidence is "Mixed… controlled studies at recommended doses show no significant effect."
- **Rule:** **caution**, evidence_level established. Applies to the whole anticoagulants class. Materiality dose_dependent with min_effective_dose 120 mg/day (source NCCIH ginkgo). The rule's own text is avoid-level: action "avoid ginkgo unless your prescriber clears it" and alert_body "If you take anticoagulants, do not combine with this product."
- **Scope difference:** warfarin with any amount (pair) versus all anticoagulants at 120 mg/day or more (rule). The two records give practically the same action. They differ only in the severity tier, and the rule's severity contradicts its own alert text.

| Source | Quote | Supports |
|---|---|---|
| NCCIH ginkgo, https://www.nccih.nih.gov/health/ginkgo | "Ginkgo may increase the risk of bleeding in people who are taking anticoagulant drugs, such as warfarin." | Both records on direction. This is "may increase" language with no avoid instruction. |
| NCCIH ginkgo | "If you take any type of medicine, talk with your health care provider before using ginkgo" | Caution-level (consult before use) |
| PMID 26958257 (Stoddard 2015, VA records) | "gingko does significantly increase patients' risk of a bleeding adverse event (hazard ratio = 1.38, 95%CI: 1.20 to 1.58" | Warfarin-specific harm; supports a meaningful warning. Observational only. |
| PMID 26958257 | "Literature, however, provides conflicting evidence on the presence and severity of the interaction." | Argues against a firm avoid |
| NCCIH ginkgo (checked for the rule's 120 mg threshold) | No "120" appears on the page | Contradicts the rule's min_effective_dose citation |

- **Sources support:** a bleeding-risk warning for warfarin (HR 1.38) and anticoagulants generally (NCCIH), with advice to consult a clinician before use. No source gives an avoid or do-not-combine instruction. The pair's own notes admit the evidence is mixed.
- **Proposed resolution:** settle on **caution** with a consult-before-use action for warfarin and anticoagulants. Rewrite the rule's alert_body, because "do not combine" conflicts with its caution severity and goes beyond NCCIH. Re-source or remove the 120 mg threshold. Keeping the pair at Major (avoid) would be a precautionary policy choice for the owner; the sources alone do not require it.
- **Confidence:** medium. The VA HR gives real support for a warfarin-specific warning, and owners might reasonably keep Major as a precaution.
- **Citation defects:** the rule's 120 mg `min_effective_dose.source` (NCCIH ginkgo) does not contain that number. Both PMIDs and URLs were live and on topic.

---

## 4. DSI_WAR_GLUCOSAMINE vs RULE_INGREDIENT_GLUCOSAMINE/drug_class_rules[0]

- **Pair:** Minor → **monitor**. Background layer, clinical_confidence low. Warfarin + glucosamine. Management: "Monitor INR when starting glucosamine." Source: NCCIH glucosamine/chondroitin. source_pmids is empty.
- **Rule:** **caution**, evidence_level established. Applies to the whole anticoagulants class, presence. Action: "Check INR within 2-4 weeks of starting or stopping glucosamine." Sources: PMIDs 18363538, 14986566 and 23946031.
- **Scope difference:** warfarin only (pair) versus all anticoagulants (rule). Every source is about warfarin and INR. None covers DOACs or heparins.

| Source | Quote | Supports |
|---|---|---|
| NCCIH, https://www.nccih.nih.gov/health/glucosamine-and-chondroitin-for-osteoarthritis-what-you-need-to-know (the pair's URL redirects here) | "glucosamine and chondroitin have been associated with an increased risk of bleeding in people who are taking the anticoagulant warfarin." | Both records on direction, for warfarin |
| PMID 18363538 (Knudsen & Sokol 2008, FDA) | "20 reports of glucosamine or glucosamine-chondroitin sulfate use with warfarin associated with altered coagulation" | Rule: more than a minor signal |
| PMID 18363538 | "One report described an intraventricular bleed and subdural hematoma, which resulted in a persistent vegetative state." | Rule (caution). A serious outcome contradicts "Minor". |
| PMID 18363538 | "Patients should be advised that the use of the two products may cause an increase in INR, and they should inform their health care provider" | Caution-level action (inform the provider) |
| PMID 14986566 (Rozenfeld 2004) | Letter with no abstract; title only: "Possible augmentation of warfarin effect by glucosamine-chondroitin." | Direction only; content not readable |
| PMID 23946031 (Dumont 2013, "Warfarin: its highs and lows") | No abstract. PMC3743701 "does not allow downloading of the full text in XML form." | **Not readable.** Could not confirm it mentions glucosamine. |

- **Sources support:** caution for **warfarin**. The evidence is a pharmacovigilance series that includes a catastrophic bleed, together with the FDA authors' instruction to inform the provider. Nothing supports the rule's class-wide scope beyond warfarin or vitamin K antagonists, or its specific "2-4 weeks" INR interval (that interval appears in no readable source). The rule's dose-escalation detail (1000 → 3000 mg/day, INR 2.3 → 3.9) matches the abstract. "Then to 4.7 on further dose reduction delay" is a garbled paraphrase: the abstract says the dose was reduced to 750 mg/day and INR was 4.7 sixteen days later.
- **Proposed resolution:** **caution** for warfarin, which means raising the pair from background monitor. Narrow the rule's scope to warfarin/VKA, or flag the class extension as unsourced. Remove the unsourced "2-4 weeks" interval or source it. Reason: the FDA review documents serious bleeding outcomes and advises informing the provider, and all evidence is specific to warfarin.
- **Confidence:** medium. The evidence is case reports and spontaneous reports only, and the interaction is undefined in the authors' own words.
- **Citation defects:** 23946031 is not readable, so its relevance is unverified. 14986566 is title-only. The "2-4 weeks" interval has no source.

---

## 5. DSI_ZINC_FLUOROQUINOLONE vs RULE_IQM_ZINC/drug_class_rules[1]

- **Pair:** Major → **avoid**. Fluoroquinolones (class) + zinc, presence, evidence_basis label_regulatory. Management already says to separate doses and follow the drug-specific label interval. Sources: PMID 1524699, DailyMed ciprofloxacin d10f7c93 and DailyMed moxifloxacin 1e6bc886.
- **Rule:** **caution**, evidence_level established, fluoroquinolones class. Action: "Separate zinc supplements from ciprofloxacin, levofloxacin, and related fluoroquinolones by the interval on the antibiotic label". Sources: DailyMed 1496ea0f and DailyMed levofloxacin 5261da15.
- **Scope difference:** none. Both cover the oral fluoroquinolone class. Both give the same action (separate by the label interval). Only the severity tier differs.

| Source | Quote | Supports |
|---|---|---|
| DailyMed ciprofloxacin, setid d10f7c93-a08b-4e9c-bfa2-6646e3ea21bd | "Ciprofloxacin should be administered at least 2 hours before or 6 hours after… other products containing calcium, iron or zinc." | Rule: separate, not avoid |
| Same cipro label | "concurrent administration of ciprofloxacin with… products containing calcium, iron or zinc should be avoided." | Avoid *simultaneous dosing*. The same label resolves this by separating doses. |
| DailyMed moxifloxacin, setid 1e6bc886-eec9-4cd8-be78-7563817457f2 | "Administer moxifloxacin tablets at least 4 hours before or 8 hours after products containing magnesium, aluminum, iron or zinc" | Rule (separate) |
| DailyMed levofloxacin, setid 5261da15-1b6c-fbe2-e063-6394a90ad85e | "multivitamin preparations with zinc… should be taken at least two hours before or two hours after oral levofloxacin administration." | Rule (separate) |
| DailyMed setid 1496ea0f-1419-c809-e063-6294a90a0b43 (rule source) | The SPL API returned HTTP 404 | **Dead citation** |
| PMID 1524699 (Brouwers 1992) | "Other metallic ion-containing drugs, such as sucralfate, iron salts, and zinc salts, can also reduce absorption." | Mechanism only; no severity or timing |

- **Sources support:** caution with dose separation. Every label tells patients to separate zinc from the fluoroquinolone by a drug-specific interval: cipro 2 h before/6 h after, levo 2 h/2 h, moxi 4 h before/8 h after. No label says to avoid zinc during the antibiotic course. A drug label's interaction instruction outranks the 1992 mechanism review.
- **Proposed resolution:** **caution**, matching the rule. The pair's severity Major/avoid tells users to avoid the combination, but the labels only say to avoid taking them at the same time. The pair's management text already describes separation, so only the pair's severity tier is out of line. Separately, replace the dead 1496ea0f citation in the rule.
- **Confidence:** high. Three current FDA labels agree on separation.
- **Citation defects:** RULE_IQM_ZINC drug_class_rules[1] cites DailyMed setid 1496ea0f-1419-c809-e063-6294a90a0b43, which returns 404 (dead or superseded). The pair's moxifloxacin and ciprofloxacin labels and the rule's levofloxacin label are live and on topic.
