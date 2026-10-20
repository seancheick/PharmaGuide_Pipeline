# Panax notoginseng identity — October 20, 2026

Problem: IQM ginseng form "ginseng (unspecified)" carried the aliases "senactiv", "senactiv panax
notoginseng", "Seneactiv", "Panax notoginseng, Rosa roxburghii" and the source names "panax
notoginseng", "rosa roxburghii". 295773's "Seneactiv" (forms: Panax notoginseng, Rosa roxburghii)
therefore became Panax ginseng and carried RULE_INGREDIENT_GINSENG. Panax notoginseng is a
different species, and Senactiv is a branded complex that already has an owner
(other_ingredients NHA_SENACTIV).

## Change (`data_batch.py`)

| Entry | Before → after | Receipt |
|---|---|---|
| IQM `ginseng` | loses the 4 Senactiv aliases and the 2 source names | Panax notoginseng ≠ Panax ginseng (GSRS GQX1C1175U vs CUQ3A77YXI); Rosa roxburghii is chestnut rose |
| other_ingredients `NHA_SENACTIV` | + "seneactiv", "senactiv panax notoginseng", "panax notoginseng, rosa roxburghii" | the existing owner already describes Senactiv as Panax notoginseng + Rosa roxburghii fractions |
| botanical `panax_notoginseng` | new: Panax notoginseng root; UNII GQX1C1175U, CUI C1011520 (Panax notoginseng, plant; same convention as ginseng_root_panax), RxCUI 1365707 | names taken from the GSRS record's own names (SAN QI, SANQI, SANCHI, TIAN QI ROOT, TIENCHI GINSENG ROOT, NOTOGINSENG ROOT, PSEUDOGINSENG ROOT, PANAX PSEUDOGINSENG VAR. NOTOGINSENG ROOT); verified by `verify_unii.py --search`, `verify_cui.py --search/--cui`, RxNav properties |
| rule `RULE_BOTAN_PANAX_NOTOGINSENG_ANTIPLATELET` | new: antiplatelets only, monitor, evidence limited, presence | below |

## Rule evidence (read by content, PubMed)

- **Used, PMID 33370633** (Wang 2020, Biomed Pharmacother): a randomized, assessor-blinded trial of
  42 people with stable coronary heart disease. Panax notoginseng saponins plus aspirin, given for 2
  months, further inhibited platelet aggregation and activation compared with aspirin alone. Bleeding
  was not an outcome. Copy says "a bleeding risk is not established" and asks the user to tell their
  clinician. No stop, no dose change.
- **Used, PMID 36754189** (Xie 2023 review): lists antiplatelet synergy among notoginseng's
  pharmacodynamic interactions.
- **Not used: anticoagulant rule.** Two human studies found no warfarin change: PMID 24142885 (T89
  Danshen + Sanqi, 24 healthy volunteers, INR and warfarin PK unchanged) and PMID 31053296 (compound
  Danshen dripping pills, warfarin dose and INR unchanged, no bleeding). The rat studies (PMIDs
  35138605, 39263307) conflict. No rule was written.
- **Not used: pregnancy claim.** No source was read that sets one. The block is the standard
  limited-data text (`no_data`).

## Not changed

- AstraGin (Astragalus + "Tienchi ginseng root extract"; 274620, 330833, 330834) keeps its own
  owner (NHA_ASTRAGIN / ENHANCER_ASTRAGIN).
- The Senactiv rows (295773, 309960, 329215) are now the branded complex. They meet no notoginseng
  rule, because the complex is not the root. **For Sean:** should the branded complex link to the
  notoginseng advisory?
- GNC Re-Built Mass 42235/42236/42237/36992 print "Panax notoginseng root extract" inside a blend
  inside a blend. The cleaner emits no active row for any member at that depth (a separate defect
  class: 291 members in 66 products), so the new identity reaches them only after that fix.

## Replay

Every raw label naming notoginseng, Senactiv/Seneactiv, Tienchi, San Qi/Sanqi/Sanchi, Tian Qi,
pseudoginseng or Rosa roxburghii (10), every label naming ginseng (176), and 150 seeded controls
(336). Base: main ec5dd058c; candidate: this branch. `replay.py snapshot --full --blob`.

- **Rules removed (1):** RULE_INGREDIENT_GINSENG on 295773 Bulk Strawberry Kiwi. The Seneactiv row
  (ginseng → NHA_SENACTIV) was its only Panax ginseng subject.
- **0 rules added, 0 score changes, 0 product_safety_status changes.** All 176 ginseng labels are
  unchanged.
- Raw canary check (`freeze_contract_snapshots.py --check`): 33 checked, 0 failed.

## Independent audit follow-up (October 20, 2026; `audit_batch.py`)

- **F1, under-warning:** 295773 "Seneactiv" now resolves to other_ingredients NHA_SENACTIV and
  met no rule. It now gets `RULE_OTHER_SENACTIV_ANTIPLATELET`. This follows the existing
  other_ingredients-subject precedent (RULE_OTHER_GINGER_EXTRACT_BLEEDING → NHA_GINGER_EXTRACT),
  and the copy is the notoginseng advisory naming Senactiv. 309960/329215 "Senactiv" sit in the
  DSLD group "Proprietary Blend" and stay BLEND_GENERAL by ADR-0005's branded-complex rule, so
  they don't resolve to NHA_SENACTIV. **For Sean.**
- **F2:** bleeding_disorders and surgery_scheduled lines at monitor, with qualified copy ("a
  bleeding risk is not established"), on both rules.
  - Added PMIDs, read by content:
    - 31471773: clopidogrel–TCM review; Panax notoginseng increased antiplatelet activity.
    - 39364700: esophageal submucosal hematoma after five notoginseng capsules.
    - 34307625: the same lesion after a homemade hirudin + notoginseng mixture. Hirudin is an
      anticoagulant, so this case cannot be attributed to notoginseng alone; the mechanism text
      says so.
  - Still no anticoagulant line. Correction to the earlier receipt: the two human warfarin studies
    tested **Danshen combinations**, not notoginseng alone (24142885: T89, Danshen + Sanqi;
    31053296: compound Danshen dripping pills).
  - 36754189 (review) calls notoginseng's CYP/P-gp effects "a red flag for drugs with a narrow
    therapeutic window". That rests on in vitro and animal pharmacokinetic data, so no
    drug-class line was written from it.
- **F3:** a Chinese Pharmacopoeia pregnancy caution for San Qi was **not verified** at its
  primary source. The HK PolyU herbal database lists "Use with caution in pregnancy" with no
  citation. The pregnancy block stays the standard no_data text.
- **F4:** `test_blend_header_amount_is_not_its_substances_dose` also asserts
  `reason == "missing_or_invalid_dose"`.
- **Ghost review:** 12 reviewed entries for the Senactiv rule's citations. They concern Panax
  notoginseng; "Senactiv" does not appear in them. `verify_interaction_rules_citations.py
  --strict`: PASS.
- **Replay after the audit** (336 labels; base main 3d7fe8adf, candidate this branch; records in
  `~/pg_quality/lostsubj_pr202_20261020/`, `fulldiff.out`): 295773 gains
  RULE_OTHER_SENACTIV_ANTIPLATELET and loses RULE_INGREDIENT_GINSENG (the wrong identity); 0
  score or safety changes.
