# Phase 1.5 — Full Baseline Dump

Reviewer baseline (5.2.0) did not include these 16 entries.
Live schema is 6.0.2; we will bump after edits.

## [129] BANNED_PENNYROYAL  (banned_recalled_ingredients)
**URLs cited (2):**
- https://medlineplus.gov/druginfo/natural/480.html
- https://www.nccih.nih.gov/health/pennyroyal

```json
{
  "id": "RULE_BANNED_PENNYROYAL_PREGNANCY",
  "subject_ref": {
    "db": "banned_recalled_ingredients",
    "canonical_id": "BANNED_PENNYROYAL"
  },
  "condition_rules": [
    {
      "condition_id": "pregnancy",
      "severity": "contraindicated",
      "evidence_level": "established",
      "mechanism": "Pennyroyal contains pulegone and related hepatotoxic constituents; pregnancy use is unsafe because of toxicity and abortifacient concern.",
      "action": "Do not use in pregnancy.",
      "sources": [
        "https://www.nccih.nih.gov/health/pennyroyal",
        "https://medlineplus.gov/druginfo/natural/480.html"
      ],
      "alert_headline": "Unsafe during pregnancy",
      "alert_body": "Pennyroyal contains toxic compounds that can harm the liver and has abortifacient concern. If you are pregnant, do not use it.",
      "informational_note": "Pennyroyal contains hepatotoxic constituents and is not safe in pregnancy.",
      "profile_gate": {
        "gate_type": "profile_flag",
        "requires": {
          "conditions_any": [],
          "drug_classes_any": [],
          "profile_flags_any": [
            "pregnant"
          ]
        },
        "excludes": {
          "conditions_any": [],
          "drug_classes_any": [],
          "profile_flags_any": [],
          "product_forms_any": [],
          "nutrient_forms_any": []
        },
        "dose": null
      }
    }
  ],
  "drug_class_rules": [],
  "dose_thresholds": [],
  "pregnancy_lactation": {
    "pregnancy_category": "contraindicated",
    "lactation_category": "avoid",
    "evidence_level": "moderate",
    "notes": "Banned/recalled or high-risk substance — avoid in pregnancy regardless of underlying mechanism.",
    "alert_headline": "Do not use in pregnancy",
    "alert_body": "This substance is banned, recalled, or high-risk and should not be used during pregnancy or breastfeeding under any circumstances.",
    "informational_note": "Banned/recalled or high-risk substance — pregnancy default is contraindicated.",
    "profile_gate": {
      "gate_type": "profile_flag",
      "requires": {
        "conditions_any": [],
        "drug_classes_any": [],
        "profile_flags_any": [
          "pregnant",
          "breastfeeding"
        ]
      },
      "excludes": {
        "conditions_any": [],
        "drug_classes_any": [],
        "profile_flags_any": [],
        "product_forms_any": [],
        "nutrient_forms_any": []
      },
      "dose": null
    }
  },
  "last_reviewed": "2026-04-26",
  "review_owner": "pharmaguide_clinical_team"
}
```

## [130] BANNED_TANSY  (banned_recalled_ingredients)
**URLs cited (2):**
- https://www.ncbi.nlm.nih.gov/books/NBK547852/
- https://www.nccih.nih.gov/health/herbsataglance

```json
{
  "id": "RULE_BANNED_TANSY_PREGNANCY",
  "subject_ref": {
    "db": "banned_recalled_ingredients",
    "canonical_id": "BANNED_TANSY"
  },
  "condition_rules": [
    {
      "condition_id": "pregnancy",
      "severity": "contraindicated",
      "evidence_level": "established",
      "mechanism": "Tansy contains thujone and other toxic constituents; pregnancy exposure is not clinically acceptable.",
      "action": "Do not use in pregnancy.",
      "sources": [
        "https://www.nccih.nih.gov/health/herbsataglance",
        "https://www.ncbi.nlm.nih.gov/books/NBK547852/"
      ],
      "alert_headline": "Unsafe during pregnancy",
      "alert_body": "Tansy contains thujone and other toxic constituents. If you are pregnant, do not use it.",
      "informational_note": "Tansy contains toxic compounds and is not clinically acceptable in pregnancy.",
      "profile_gate": {
        "gate_type": "profile_flag",
        "requires": {
          "conditions_any": [],
          "drug_classes_any": [],
          "profile_flags_any": [
            "pregnant"
          ]
        },
        "excludes": {
          "conditions_any": [],
          "drug_classes_any": [],
          "profile_flags_any": [],
          "product_forms_any": [],
          "nutrient_forms_any": []
        },
        "dose": null
      }
    }
  ],
  "drug_class_rules": [],
  "dose_thresholds": [],
  "pregnancy_lactation": {
    "pregnancy_category": "contraindicated",
    "lactation_category": "avoid",
    "evidence_level": "moderate",
    "notes": "Banned/recalled or high-risk substance — avoid in pregnancy regardless of underlying mechanism.",
    "alert_headline": "Do not use in pregnancy",
    "alert_body": "This substance is banned, recalled, or high-risk and should not be used during pregnancy or breastfeeding under any circumstances.",
    "informational_note": "Banned/recalled or high-risk substance — pregnancy default is contraindicated.",
    "profile_gate": {
      "gate_type": "profile_flag",
      "requires": {
        "conditions_any": [],
        "drug_classes_any": [],
        "profile_flags_any": [
          "pregnant",
          "breastfeeding"
        ]
      },
      "excludes": {
        "conditions_any": [],
        "drug_classes_any": [],
        "profile_flags_any": [],
        "product_forms_any": [],
        "nutrient_forms_any": []
      },
      "dose": null
    }
  },
  "last_reviewed": "2026-04-26",
  "review_owner": "pharmaguide_clinical_team"
}
```

## [131] BANNED_BITTER_ORANGE  (banned_recalled_ingredients)
**URLs cited (2):**
- https://www.canada.ca/en/health-canada/services/drugs-health-products/natural-non-prescription/regulation/about-products/synephrine.html
- https://www.nccih.nih.gov/health/bitterorange

```json
{
  "id": "RULE_BANNED_BITTER_ORANGE_PREGNANCY",
  "subject_ref": {
    "db": "banned_recalled_ingredients",
    "canonical_id": "BANNED_BITTER_ORANGE"
  },
  "condition_rules": [
    {
      "condition_id": "pregnancy",
      "severity": "contraindicated",
      "evidence_level": "probable",
      "mechanism": "Synephrine is a sympathomimetic; pregnancy is not the place for stimulant-driven cardiovascular stress.",
      "action": "Do not use supplement-dose bitter orange in pregnancy.",
      "sources": [
        "https://www.nccih.nih.gov/health/bitterorange",
        "https://www.canada.ca/en/health-canada/services/drugs-health-products/natural-non-prescription/regulation/about-products/synephrine.html"
      ],
      "alert_headline": "Not for use in pregnancy",
      "alert_body": "Supplement-dose bitter orange contains synephrine, a stimulant that can stress the cardiovascular system. If you are pregnant, do not use it.",
      "informational_note": "Bitter orange contains synephrine and is not appropriate in pregnancy.",
      "profile_gate": {
        "gate_type": "profile_flag",
        "requires": {
          "conditions_any": [],
          "drug_classes_any": [],
          "profile_flags_any": [
            "pregnant"
          ]
        },
        "excludes": {
          "conditions_any": [],
          "drug_classes_any": [],
          "profile_flags_any": [],
          "product_forms_any": [],
          "nutrient_forms_any": []
        },
        "dose": null
      }
    }
  ],
  "drug_class_rules": [],
  "dose_thresholds": [
    {
      "scope": "condition",
      "target_id": "pregnancy",
      "comparator": ">=",
      "value": 3,
      "unit": "mg",
      "basis": "per_day",
      "severity_if_met": "contraindicated",
      "severity_if_not_met": "avoid",
      "profile_gate": {
        "gate_type": "combination",
        "requires": {
          "conditions_any": [],
          "drug_classes_any": [],
          "profile_flags_any": [
            "pregnant"
          ]
        },
        "excludes": {
          "conditions_any": [],
          "drug_classes_any": [],
          "profile_flags_any": [],
          "product_forms_any": [],
          "nutrient_forms_any": []
        },
        "dose": {
          "basis": "per_day",
          "comparator": ">=",
          "value": 3,
          "unit": "mg",
          "severity_if_met": "contraindicated",
          "severity_if_not_met": "avoid"
        }
      }
    }
  ],
  "pregnancy_lactation": {
    "pregnancy_category": "contraindicated",
    "lactation_category": "avoid",
    "evidence_level": "moderate",
    "notes": "Banned/recalled or high-risk substance — avoid in pregnancy regardless of underlying mechanism.",
    "alert_headline": "Do not use in pregnancy",
    "alert_body": "This substance is banned, recalled, or high-risk and should not be used during pregnancy or breastfeeding under any circumstances.",
    "informational_note": "Banned/recalled or high-risk substance — pregnancy default is contraindicated.",
    "profile_gate": {
      "gate_type": "profile_flag",
      "requires": {
        "conditions_any": [],
        "drug_classes_any": [],
        "profile_flags_any": [
          "pregnant",
          "breastfeeding"
        ]
      },
      "excludes": {
        "conditions_any": [],
        "drug_classes_any": [],
        "profile_flags_any": [],
        "product_forms_any": [],
        "nutrient_forms_any": []
      },
      "dose": null
    }
  },
  "last_reviewed": "2026-04-26",
  "review_owner": "pharmaguide_clinical_team"
}
```

## [132] ginkgo_biloba_leaf  (botanical_ingredients)
**URLs cited (1):**
- https://www.nccih.nih.gov/health/ginkgo

```json
{
  "id": "RULE_BOTAN_GINKGO_PREGNANCY",
  "subject_ref": {
    "db": "botanical_ingredients",
    "canonical_id": "ginkgo_biloba_leaf"
  },
  "condition_rules": [
    {
      "condition_id": "pregnancy",
      "severity": "avoid",
      "evidence_level": "probable",
      "mechanism": "Antiplatelet effects make peripartum bleeding the main concern.",
      "action": "Avoid chronic use in pregnancy and stop before delivery if used.",
      "sources": [
        "https://www.nccih.nih.gov/health/ginkgo"
      ],
      "alert_headline": "May raise bleeding risk",
      "alert_body": "Ginkgo can have antiplatelet effects, which is a concern near delivery. If you are pregnant, avoid chronic use and stop before birth if your clinician has you taking it.",
      "informational_note": "Ginkgo's antiplatelet activity is a peripartum bleeding concern, especially near delivery.",
      "profile_gate": {
        "gate_type": "profile_flag",
        "requires": {
          "conditions_any": [],
          "drug_classes_any": [],
          "profile_flags_any": [
            "pregnant"
          ]
        },
        "excludes": {
          "conditions_any": [],
          "drug_classes_any": [],
          "profile_flags_any": [],
          "product_forms_any": [],
          "nutrient_forms_any": []
        },
        "dose": null
      }
    }
  ],
  "drug_class_rules": [],
  "dose_thresholds": [],
  "pregnancy_lactation": {
    "pregnancy_category": "no_data",
    "lactation_category": "no_data",
    "evidence_level": "no_data",
    "notes": "Limited data — discuss with your healthcare provider before use during pregnancy or breastfeeding.",
    "alert_headline": "Limited safety data",
    "alert_body": "There isn't enough specific safety data to give a confident recommendation for pregnancy or breastfeeding. Talk to your obstetrician or pediatrician before using this supplement.",
    "informational_note": "Pregnancy/lactation safety data is limited — clinician guidance recommended."
  },
  "last_reviewed": "2026-04-26",
  "review_owner": "pharmaguide_clinical_team"
}
```

## [133] holy_basil  (ingredient_quality_map)
**URLs cited (1):**
- https://www.nccih.nih.gov/health/herbsataglance

```json
{
  "id": "RULE_IQM_HOLY_BASIL_PREGNANCY",
  "subject_ref": {
    "db": "ingredient_quality_map",
    "canonical_id": "holy_basil"
  },
  "condition_rules": [
    {
      "condition_id": "pregnancy",
      "severity": "informational",
      "evidence_level": "theoretical",
      "mechanism": "Pregnancy data are limited and animal data raise endocrine and uterotonic uncertainty.",
      "action": "Avoid concentrated extracts; culinary use is not the same as supplement use.",
      "sources": [
        "https://www.nccih.nih.gov/health/herbsataglance"
      ],
      "alert_headline": "Not well studied in pregnancy",
      "alert_body": "Holy basil has limited pregnancy data, and animal studies raise endocrine and uterotonic uncertainty. If you are pregnant, avoid concentrated extracts.",
      "profile_gate": {
        "gate_type": "profile_flag",
        "requires": {
          "conditions_any": [],
          "drug_classes_any": [],
          "profile_flags_any": [
            "pregnant"
          ]
        },
        "excludes": {
          "conditions_any": [],
          "drug_classes_any": [],
          "profile_flags_any": [],
          "product_forms_any": [],
          "nutrient_forms_any": []
        },
        "dose": null
      }
    }
  ],
  "drug_class_rules": [],
  "dose_thresholds": [],
  "pregnancy_lactation": {
    "pregnancy_category": "no_data",
    "lactation_category": "no_data",
    "evidence_level": "no_data",
    "notes": "Limited data — discuss with your healthcare provider before use during pregnancy or breastfeeding.",
    "alert_headline": "Limited safety data",
    "alert_body": "There isn't enough specific safety data to give a confident recommendation for pregnancy or breastfeeding. Talk to your obstetrician or pediatrician before using this supplement.",
    "informational_note": "Pregnancy/lactation safety data is limited — clinician guidance recommended."
  },
  "last_reviewed": "2026-04-26",
  "review_owner": "pharmaguide_clinical_team"
}
```

## [134] maca  (ingredient_quality_map)
**URLs cited (1):**
- https://www.nccih.nih.gov/health/maca

```json
{
  "id": "RULE_IQM_MACA_PREGNANCY",
  "subject_ref": {
    "db": "ingredient_quality_map",
    "canonical_id": "maca"
  },
  "condition_rules": [
    {
      "condition_id": "pregnancy",
      "severity": "informational",
      "evidence_level": "theoretical",
      "mechanism": "Human pregnancy safety data are sparse.",
      "action": "Do not present as proven pregnancy support; monitor rather than hard-block.",
      "sources": [
        "https://www.nccih.nih.gov/health/maca"
      ],
      "alert_headline": "Pregnancy safety is unclear",
      "alert_body": "Human pregnancy safety data for maca are sparse. If you are pregnant, discuss use with your clinician rather than treating it as proven support.",
      "profile_gate": {
        "gate_type": "profile_flag",
        "requires": {
          "conditions_any": [],
          "drug_classes_any": [],
          "profile_flags_any": [
            "pregnant"
          ]
        },
        "excludes": {
          "conditions_any": [],
          "drug_classes_any": [],
          "profile_flags_any": [],
          "product_forms_any": [],
          "nutrient_forms_any": []
        },
        "dose": null
      }
    }
  ],
  "drug_class_rules": [],
  "dose_thresholds": [],
  "pregnancy_lactation": {
    "pregnancy_category": "no_data",
    "lactation_category": "no_data",
    "evidence_level": "no_data",
    "notes": "Limited data — discuss with your healthcare provider before use during pregnancy or breastfeeding.",
    "alert_headline": "Limited safety data",
    "alert_body": "There isn't enough specific safety data to give a confident recommendation for pregnancy or breastfeeding. Talk to your obstetrician or pediatrician before using this supplement.",
    "informational_note": "Pregnancy/lactation safety data is limited — clinician guidance recommended."
  },
  "last_reviewed": "2026-04-26",
  "review_owner": "pharmaguide_clinical_team"
}
```

## [135] l_carnitine  (ingredient_quality_map)
**URLs cited (1):**
- https://ods.od.nih.gov/factsheets/Carnitine-HealthProfessional/

```json
{
  "id": "RULE_IQM_L_CARNITINE_DIABETES",
  "subject_ref": {
    "db": "ingredient_quality_map",
    "canonical_id": "l_carnitine"
  },
  "condition_rules": [
    {
      "condition_id": "diabetes",
      "severity": "informational",
      "evidence_level": "probable",
      "mechanism": "May modestly affect fuel utilization and insulin sensitivity.",
      "action": "Monitor glucose trends if used chronically.",
      "sources": [
        "https://ods.od.nih.gov/factsheets/Carnitine-HealthProfessional/"
      ],
      "alert_headline": "May change glucose trends",
      "alert_body": "L-carnitine may modestly affect fuel use and insulin sensitivity. If you use it chronically with diabetes, monitor glucose trends.",
      "profile_gate": {
        "gate_type": "condition",
        "requires": {
          "conditions_any": [
            "diabetes"
          ],
          "drug_classes_any": [],
          "profile_flags_any": []
        },
        "excludes": {
          "conditions_any": [],
          "drug_classes_any": [],
          "profile_flags_any": [],
          "product_forms_any": [],
          "nutrient_forms_any": []
        },
        "dose": null
      }
    }
  ],
  "drug_class_rules": [],
  "dose_thresholds": [],
  "pregnancy_lactation": {
    "pregnancy_category": "no_data",
    "lactation_category": "no_data",
    "evidence_level": "no_data",
    "notes": "Limited data — discuss with your healthcare provider before use during pregnancy or breastfeeding.",
    "alert_headline": "Limited safety data",
    "alert_body": "There isn't enough specific safety data to give a confident recommendation for pregnancy or breastfeeding. Talk to your obstetrician or pediatrician before using this supplement.",
    "informational_note": "Pregnancy/lactation safety data is limited — clinician guidance recommended."
  },
  "last_reviewed": "2026-04-26",
  "review_owner": "pharmaguide_clinical_team"
}
```

## [136] white_mulberry  (botanical_ingredients)
**URLs cited (2):**
- https://pubmed.ncbi.nlm.nih.gov/27092496/
- https://www.nccih.nih.gov/health/herbsataglance

```json
{
  "id": "RULE_BOTAN_WHITE_MULBERRY_DIABETES",
  "subject_ref": {
    "db": "botanical_ingredients",
    "canonical_id": "white_mulberry"
  },
  "condition_rules": [
    {
      "condition_id": "diabetes",
      "severity": "caution",
      "evidence_level": "established",
      "mechanism": "Alpha-glucosidase inhibition slows carbohydrate absorption.",
      "action": "Monitor if combined with acarbose-like therapy or insulin.",
      "sources": [
        "https://www.nccih.nih.gov/health/herbsataglance"
      ],
      "alert_headline": "May lower glucose after meals",
      "alert_body": "White mulberry can slow carbohydrate absorption through alpha-glucosidase inhibition. If you use it with acarbose-like therapy or insulin, monitor for low blood sugar.",
      "profile_gate": {
        "gate_type": "condition",
        "requires": {
          "conditions_any": [
            "diabetes"
          ],
          "drug_classes_any": [],
          "profile_flags_any": []
        },
        "excludes": {
          "conditions_any": [],
          "drug_classes_any": [],
          "profile_flags_any": [],
          "product_forms_any": [],
          "nutrient_forms_any": []
        },
        "dose": null
      }
    }
  ],
  "drug_class_rules": [],
  "dose_thresholds": [
    {
      "scope": "condition",
      "target_id": "diabetes",
      "basis": "per_day",
      "comparator": ">",
      "value": 1000,
      "unit": "mg",
      "severity_if_met": "caution",
      "severity_if_not_met": "monitor",
      "note": "May potentiate blood-sugar lowering medications. https://pubmed.ncbi.nlm.nih.gov/27092496/",
      "profile_gate": {
        "gate_type": "combination",
        "requires": {
          "conditions_any": [
            "diabetes"
          ],
          "drug_classes_any": [],
          "profile_flags_any": []
        },
        "excludes": {
          "conditions_any": [],
          "drug_classes_any": [],
          "profile_flags_any": [],
          "product_forms_any": [],
          "nutrient_forms_any": []
        },
        "dose": {
          "basis": "per_day",
          "comparator": ">",
          "value": 1000,
          "unit": "mg",
          "severity_if_met": "caution",
          "severity_if_not_met": "monitor"
        }
      }
    }
  ],
  "pregnancy_lactation": {
    "pregnancy_category": "no_data",
    "lactation_category": "no_data",
    "evidence_level": "no_data",
    "notes": "Limited data — discuss with your healthcare provider before use during pregnancy or breastfeeding.",
    "alert_headline": "Limited safety data",
    "alert_body": "There isn't enough specific safety data to give a confident recommendation for pregnancy or breastfeeding. Talk to your obstetrician or pediatrician before using this supplement.",
    "informational_note": "Pregnancy/lactation safety data is limited — clinician guidance recommended."
  },
  "last_reviewed": "2026-04-26",
  "review_owner": "pharmaguide_clinical_team"
}
```

## [137] phenylethylamine  (ingredient_quality_map)
**URLs cited (1):**
- https://www.fda.gov/drugs/resources-you/drug-interactions-what-you-should-know

```json
{
  "id": "RULE_IQM_PHENYLETHYLAMINE",
  "subject_ref": {
    "db": "ingredient_quality_map",
    "canonical_id": "phenylethylamine"
  },
  "condition_rules": [],
  "drug_class_rules": [
    {
      "drug_class_id": "maois",
      "severity": "contraindicated",
      "evidence_level": "established",
      "mechanism": "PEA is a direct MAO substrate; combination with MAOIs causes hypertensive crisis.",
      "action": "Do not combine PEA-containing supplements with MAOIs. Discontinue MAOI for the appropriate washout period before any PEA-containing product.",
      "sources": [
        "https://www.fda.gov/drugs/resources-you/drug-interactions-what-you-should-know"
      ],
      "alert_headline": "Do not combine with MAOIs",
      "alert_body": "If you take MAO inhibitors, do not combine with this product. PEA combined with MAO-inhibitor antidepressants can cause a dangerous spike in blood pressure.",
      "informational_note": "PEA is an MAO substrate — relevant to anyone taking phenelzine, tranylcypromine, selegiline, or related drugs.",
      "profile_gate": {
        "gate_type": "drug_class",
        "requires": {
          "conditions_any": [],
          "drug_classes_any": [
            "maois"
          ],
          "profile_flags_any": []
        },
        "excludes": {
          "conditions_any": [],
          "drug_classes_any": [],
          "profile_flags_any": [],
          "product_forms_any": [],
          "nutrient_forms_any": []
        },
        "dose": null
      }
    }
  ],
  "dose_thresholds": [],
  "pregnancy_lactation": {
    "pregnancy_category": "no_data",
    "lactation_category": "no_data",
    "evidence_level": "no_data",
    "notes": "Limited data — discuss with your healthcare provider before use during pregnancy or breastfeeding.",
    "alert_headline": "Limited safety data",
    "alert_body": "There isn't enough specific safety data to give a confident recommendation for pregnancy or breastfeeding. Talk to your obstetrician or pediatrician before using this supplement.",
    "informational_note": "Pregnancy/lactation safety data is limited — clinician guidance recommended."
  },
  "last_reviewed": "2026-04-30",
  "review_owner": "pharmaguide_clinical_team"
}
```

## [138] l_tryptophan  (ingredient_quality_map)
**URLs cited (1):**
- https://ods.od.nih.gov/factsheets/Tryptophan/

```json
{
  "id": "RULE_IQM_L_TRYPTOPHAN",
  "subject_ref": {
    "db": "ingredient_quality_map",
    "canonical_id": "l_tryptophan"
  },
  "condition_rules": [],
  "drug_class_rules": [
    {
      "drug_class_id": "maois",
      "severity": "contraindicated",
      "evidence_level": "established",
      "mechanism": "Serotonin precursor combined with MAOI inhibition → serotonin syndrome.",
      "action": "Do not combine L-tryptophan with MAOIs.",
      "sources": [
        "https://ods.od.nih.gov/factsheets/Tryptophan/"
      ],
      "alert_headline": "Do not combine with MAOIs",
      "alert_body": "If you take MAO inhibitors, do not combine with this product. L-tryptophan raises serotonin levels and can cause serotonin syndrome when combined with MAO-inhibitor antidepressants.",
      "informational_note": "L-tryptophan increases serotonin — relevant to anyone on MAOIs, SSRIs, SNRIs, or other serotonergic drugs.",
      "profile_gate": {
        "gate_type": "drug_class",
        "requires": {
          "conditions_any": [],
          "drug_classes_any": [
            "maois"
          ],
          "profile_flags_any": []
        },
        "excludes": {
          "conditions_any": [],
          "drug_classes_any": [],
          "profile_flags_any": [],
          "product_forms_any": [],
          "nutrient_forms_any": []
        },
        "dose": null
      }
    }
  ],
  "dose_thresholds": [],
  "pregnancy_lactation": {
    "pregnancy_category": "no_data",
    "lactation_category": "no_data",
    "evidence_level": "no_data",
    "notes": "Limited data — discuss with your healthcare provider before use during pregnancy or breastfeeding.",
    "alert_headline": "Limited safety data",
    "alert_body": "There isn't enough specific safety data to give a confident recommendation for pregnancy or breastfeeding. Talk to your obstetrician or pediatrician before using this supplement.",
    "informational_note": "Pregnancy/lactation safety data is limited — clinician guidance recommended."
  },
  "last_reviewed": "2026-04-30",
  "review_owner": "pharmaguide_clinical_team"
}
```

## [139] ADD_HORDENINE  (banned_recalled_ingredients)
**URLs cited (1):**
- https://www.fda.gov/drugs/resources-you/drug-interactions-what-you-should-know

```json
{
  "id": "RULE_BANNED_ADD_HORDENINE",
  "subject_ref": {
    "db": "banned_recalled_ingredients",
    "canonical_id": "ADD_HORDENINE"
  },
  "condition_rules": [],
  "drug_class_rules": [
    {
      "drug_class_id": "maois",
      "severity": "contraindicated",
      "evidence_level": "established",
      "mechanism": "Hordenine is a β-PEA analog and direct MAO substrate. Often combined with PEA in pre-workout / fat-burner stacks, compounding the risk.",
      "action": "Do not combine hordenine with MAOIs. Avoid pre-workout and fat-burner products listing hordenine if you take an MAOI.",
      "sources": [
        "https://www.fda.gov/drugs/resources-you/drug-interactions-what-you-should-know"
      ],
      "alert_headline": "Do not combine with MAOIs",
      "alert_body": "If you take MAO inhibitors, do not combine with this product. Hordenine works like PEA and can cause dangerous blood pressure changes with MAO-inhibitor antidepressants.",
      "informational_note": "Hordenine is an MAO substrate — relevant to anyone on MAOIs.",
      "profile_gate": {
        "gate_type": "drug_class",
        "requires": {
          "conditions_any": [],
          "drug_classes_any": [
            "maois"
          ],
          "profile_flags_any": []
        },
        "excludes": {
          "conditions_any": [],
          "drug_classes_any": [],
          "profile_flags_any": [],
          "product_forms_any": [],
          "nutrient_forms_any": []
        },
        "dose": null
      }
    }
  ],
  "dose_thresholds": [],
  "pregnancy_lactation": {
    "pregnancy_category": "contraindicated",
    "lactation_category": "avoid",
    "evidence_level": "moderate",
    "notes": "Limited data — discuss with your healthcare provider before use during pregnancy or breastfeeding.",
    "alert_headline": "Do not use in pregnancy",
    "alert_body": "This substance is banned, recalled, or high-risk and should not be used during pregnancy or breastfeeding under any circumstances.",
    "informational_note": "Banned/recalled or high-risk substance — pregnancy default is contraindicated.",
    "profile_gate": {
      "gate_type": "profile_flag",
      "requires": {
        "conditions_any": [],
        "drug_classes_any": [],
        "profile_flags_any": [
          "pregnant",
          "breastfeeding"
        ]
      },
      "excludes": {
        "conditions_any": [],
        "drug_classes_any": [],
        "profile_flags_any": [],
        "product_forms_any": [],
        "nutrient_forms_any": []
      },
      "dose": null
    }
  },
  "last_reviewed": "2026-04-30",
  "review_owner": "pharmaguide_clinical_team"
}
```

## [140] same  (ingredient_quality_map)
**URLs cited (1):**
- https://www.nccih.nih.gov/health/same

```json
{
  "id": "RULE_IQM_SAME",
  "subject_ref": {
    "db": "ingredient_quality_map",
    "canonical_id": "same"
  },
  "condition_rules": [],
  "drug_class_rules": [
    {
      "drug_class_id": "maois",
      "severity": "avoid",
      "evidence_level": "established",
      "mechanism": "Methyl donor with antidepressant activity; serotonergic potentiation when combined with MAOIs raises serotonin syndrome risk.",
      "action": "If you take an MAOI, avoid SAMe unless cleared by your prescriber. Allow washout if switching.",
      "sources": [
        "https://www.nccih.nih.gov/health/same"
      ],
      "alert_headline": "Avoid combining with MAOIs",
      "alert_body": "If you take MAO inhibitors, do not combine with this product. SAMe has antidepressant-like activity. Combined with MAO-inhibitor antidepressants, it can raise the risk of serotonin syndrome.",
      "informational_note": "SAMe is serotonergic — relevant to anyone on MAOIs or other antidepressants.",
      "profile_gate": {
        "gate_type": "drug_class",
        "requires": {
          "conditions_any": [],
          "drug_classes_any": [
            "maois"
          ],
          "profile_flags_any": []
        },
        "excludes": {
          "conditions_any": [],
          "drug_classes_any": [],
          "profile_flags_any": [],
          "product_forms_any": [],
          "nutrient_forms_any": []
        },
        "dose": null
      }
    }
  ],
  "dose_thresholds": [],
  "pregnancy_lactation": {
    "pregnancy_category": "no_data",
    "lactation_category": "no_data",
    "evidence_level": "no_data",
    "notes": "Limited data — discuss with your healthcare provider before use during pregnancy or breastfeeding.",
    "alert_headline": "Limited safety data",
    "alert_body": "There isn't enough specific safety data to give a confident recommendation for pregnancy or breastfeeding. Talk to your obstetrician or pediatrician before using this supplement.",
    "informational_note": "Pregnancy/lactation safety data is limited — clinician guidance recommended."
  },
  "last_reviewed": "2026-04-30",
  "review_owner": "pharmaguide_clinical_team"
}
```

## [141] sodium  (ingredient_quality_map)
**URLs cited (2):**
- https://ods.od.nih.gov/factsheets/Sodium-HealthProfessional/
- https://www.cdc.gov/salt/index.html

```json
{
  "id": "RULE_IQM_SODIUM",
  "subject_ref": {
    "db": "ingredient_quality_map",
    "canonical_id": "sodium"
  },
  "condition_rules": [],
  "drug_class_rules": [
    {
      "drug_class_id": "lithium",
      "severity": "monitor",
      "evidence_level": "established",
      "mechanism": "High sodium intake increases lithium clearance. Low sodium increases lithium retention → toxicity risk. Like caffeine, the principle is consistency.",
      "action": "If you take lithium, keep sodium intake stable. Avoid sudden low-sodium diets or salt-tablet supplements without prescriber approval.",
      "sources": [
        "https://ods.od.nih.gov/factsheets/Sodium-HealthProfessional/",
        "https://www.cdc.gov/salt/index.html"
      ],
      "alert_headline": "Keep sodium intake stable",
      "alert_body": "Big swings in sodium intake change your lithium levels. Talk to your prescriber before starting a low-sodium diet or salt supplement.",
      "informational_note": "Sodium intake affects lithium levels bidirectionally — relevant to anyone on lithium therapy.",
      "profile_gate": {
        "gate_type": "drug_class",
        "requires": {
          "conditions_any": [],
          "drug_classes_any": [
            "lithium"
          ],
          "profile_flags_any": []
        },
        "excludes": {
          "conditions_any": [],
          "drug_classes_any": [],
          "profile_flags_any": [],
          "product_forms_any": [],
          "nutrient_forms_any": []
        },
        "dose": null
      }
    }
  ],
  "dose_thresholds": [],
  "pregnancy_lactation": {
    "pregnancy_category": "no_data",
    "lactation_category": "no_data",
    "evidence_level": "no_data",
    "notes": "Limited data — discuss with your healthcare provider before use during pregnancy or breastfeeding.",
    "alert_headline": "Limited safety data",
    "alert_body": "There isn't enough specific safety data to give a confident recommendation for pregnancy or breastfeeding. Talk to your obstetrician or pediatrician before using this supplement.",
    "informational_note": "Pregnancy/lactation safety data is limited — clinician guidance recommended."
  },
  "last_reviewed": "2026-04-30",
  "review_owner": "pharmaguide_clinical_team"
}
```

## [142] bromelain  (ingredient_quality_map)
**URLs cited (2):**
- https://pubmed.ncbi.nlm.nih.gov/11577981/
- https://www.nccih.nih.gov/health/bromelain

```json
{
  "id": "RULE_IQM_BROMELAIN",
  "subject_ref": {
    "db": "ingredient_quality_map",
    "canonical_id": "bromelain"
  },
  "condition_rules": [],
  "drug_class_rules": [
    {
      "drug_class_id": "anticoagulants",
      "severity": "monitor",
      "evidence_level": "theoretical",
      "mechanism": "Mild fibrinolytic / antiplatelet activity at high dose (≥500 mg/day). Bromelain enhances plasmin generation and modestly inhibits platelet aggregation. Clinical bleeding events with warfarin are rare but documented in case reports.",
      "action": "If you take warfarin or an antiplatelet, mention bromelain supplements ≥500 mg/day to your prescriber. Watch for unusual bruising or bleeding.",
      "sources": [
        "https://pubmed.ncbi.nlm.nih.gov/11577981/",
        "https://www.nccih.nih.gov/health/bromelain"
      ],
      "alert_headline": "Mild bleeding risk at high dose",
      "alert_body": "High-dose bromelain (500 mg/day or more) has mild blood-thinning activity. Combined with warfarin or antiplatelet drugs, this can slightly raise bleeding risk.",
      "informational_note": "Bromelain has fibrinolytic activity at clinical doses — relevant to anyone on blood thinners.",
      "profile_gate": {
        "gate_type": "drug_class",
        "requires": {
          "conditions_any": [],
          "drug_classes_any": [
            "anticoagulants"
          ],
          "profile_flags_any": []
        },
        "excludes": {
          "conditions_any": [],
          "drug_classes_any": [],
          "profile_flags_any": [],
          "product_forms_any": [],
          "nutrient_forms_any": []
        },
        "dose": null
      }
    }
  ],
  "dose_thresholds": [],
  "pregnancy_lactation": {
    "pregnancy_category": "no_data",
    "lactation_category": "no_data",
    "evidence_level": "no_data",
    "notes": "Limited data — discuss with your healthcare provider before use during pregnancy or breastfeeding.",
    "alert_headline": "Limited safety data",
    "alert_body": "There isn't enough specific safety data to give a confident recommendation for pregnancy or breastfeeding. Talk to your obstetrician or pediatrician before using this supplement.",
    "informational_note": "Pregnancy/lactation safety data is limited — clinician guidance recommended."
  },
  "last_reviewed": "2026-04-30",
  "review_owner": "pharmaguide_clinical_team"
}
```

## [143] ADD_TYRAMINE_RICH_EXTRACT  (harmful_additives)
**URLs cited (1):**
- https://www.fda.gov/drugs/resources-you/drug-interactions-what-you-should-know

```json
{
  "id": "RULE_HARM_TYRAMINE_RICH_EXTRACT",
  "subject_ref": {
    "db": "harmful_additives",
    "canonical_id": "ADD_TYRAMINE_RICH_EXTRACT"
  },
  "condition_rules": [],
  "drug_class_rules": [
    {
      "drug_class_id": "maois",
      "severity": "contraindicated",
      "evidence_level": "established",
      "mechanism": "Tyramine is a sympathomimetic biogenic amine and MAO substrate. With MAO-inhibitor medication, ingested tyramine cannot be metabolized normally, producing massive norepinephrine release and severe hypertensive crisis ('cheese reaction'). Documented fatalities in the clinical literature.",
      "action": "Do not combine tyramine-rich extracts with MAOIs. Read supplement labels for aged-yeast, fermented bovine, or tyramine-containing protein hydrolysates if you take an MAOI.",
      "sources": [
        "https://www.fda.gov/drugs/resources-you/drug-interactions-what-you-should-know"
      ],
      "alert_headline": "Do not combine with MAOIs",
      "alert_body": "If you take MAO inhibitors, do not combine with this product. Tyramine-rich supplement extracts combined with MAO-inhibitor antidepressants can cause a life-threatening blood pressure spike. This i...",
      "informational_note": "Tyramine is the classic MAOI dietary contraindication — relevant to anyone on phenelzine, tranylcypromine, isocarboxa...",
      "profile_gate": {
        "gate_type": "drug_class",
        "requires": {
          "conditions_any": [],
          "drug_classes_any": [
            "maois"
          ],
          "profile_flags_any": []
        },
        "excludes": {
          "conditions_any": [],
          "drug_classes_any": [],
          "profile_flags_any": [],
          "product_forms_any": [],
          "nutrient_forms_any": []
        },
        "dose": null
      }
    }
  ],
  "dose_thresholds": [],
  "pregnancy_lactation": {
    "pregnancy_category": "caution",
    "lactation_category": "caution",
    "evidence_level": "limited",
    "notes": "Concentrated tyramine extracts may elevate sympathetic tone — talk to your clinician before use during pregnancy or breastfeeding.",
    "alert_headline": "Talk to your clinician",
    "alert_body": "Concentrated tyramine sources can elevate blood pressure and sympathetic tone. Discuss with your obstetrician or pediatrician before use during pregnancy or breastfeeding.",
    "informational_note": "Tyramine elevates sympathetic tone — pregnancy/lactation guidance recommended.",
    "profile_gate": {
      "gate_type": "profile_flag",
      "requires": {
        "conditions_any": [],
        "drug_classes_any": [],
        "profile_flags_any": [
          "pregnant",
          "breastfeeding"
        ]
      },
      "excludes": {
        "conditions_any": [],
        "drug_classes_any": [],
        "profile_flags_any": [],
        "product_forms_any": [],
        "nutrient_forms_any": []
      },
      "dose": null
    }
  },
  "last_reviewed": "2026-04-30",
  "review_owner": "pharmaguide_clinical_team"
}
```

## [144] bupleurum_root  (botanical_ingredients)
**URLs cited (1):**
- https://www.fda.gov/drugs/resources-you/drug-interactions-what-you-should-know

```json
{
  "id": "RULE_BOTAN_BUPLEURUM_CYP2D6",
  "subject_ref": {
    "db": "botanical_ingredients",
    "canonical_id": "bupleurum_root"
  },
  "condition_rules": [],
  "drug_class_rules": [
    {
      "drug_class_id": "cyp2d6_substrates",
      "severity": "caution",
      "evidence_level": "theoretical",
      "mechanism": "Saikosaponins inhibit CYP2D6 in vitro and in animal models. Clinical evidence in humans is limited but consistent in mechanism. Bupleurum often appears in multi-herb TCM formulas (Xiao Yao San, Bupleurum & Dragon Bone) where users may not recognize it on the ingredient label.",
      "action": "If you take a CYP2D6-substrate prescription drug, consider discussing this supplement with your prescriber. Especially relevant for many SSRIs/SNRIs, tricyclics, codeine, tramadol, and tamoxifen.",
      "sources": [
        "https://www.fda.gov/drugs/resources-you/drug-interactions-what-you-should-know"
      ],
      "alert_headline": "May affect prescription drug levels",
      "alert_body": "If you take a CYP2D6-substrate prescription drug, consider discussing bupleurum with your prescriber. Bupleurum may slow how some antidepressants and pain medications are processed.",
      "informational_note": "Bupleurum inhibits CYP2D6 in preclinical evidence — relevant to anyone on antidepressants, opioids, or tamoxifen.",
      "profile_gate": {
        "gate_type": "drug_class",
        "requires": {
          "conditions_any": [],
          "drug_classes_any": [
            "cyp2d6_substrates"
          ],
          "profile_flags_any": []
        },
        "excludes": {
          "conditions_any": [],
          "drug_classes_any": [],
          "profile_flags_any": [],
          "product_forms_any": [],
          "nutrient_forms_any": []
        },
        "dose": null
      }
    }
  ],
  "dose_thresholds": [],
  "pregnancy_lactation": {
    "pregnancy_category": "caution",
    "lactation_category": "no_data",
    "evidence_level": "limited",
    "mechanism": "Emmenagogue activity in TCM literature; limited modern safety data in pregnancy. Lactation safety data absent.",
    "notes": "Use caution in pregnancy due to traditional emmenagogue activity. Lactation safety not established — clinician guidance recommended.",
    "alert_headline": "Talk to your clinician",
    "alert_body": "Bupleurum has traditional emmenagogue activity and limited safety data in pregnancy. Talk to your obstetrician before use during pregnancy or breastfeeding.",
    "informational_note": "Bupleurum has limited pregnancy safety data — clinician guidance recommended.",
    "profile_gate": {
      "gate_type": "profile_flag",
      "requires": {
        "conditions_any": [],
        "drug_classes_any": [],
        "profile_flags_any": [
          "pregnant",
          "breastfeeding"
        ]
      },
      "excludes": {
        "conditions_any": [],
        "drug_classes_any": [],
        "profile_flags_any": [],
        "product_forms_any": [],
        "nutrient_forms_any": []
      },
      "dose": null
    }
  },
  "last_reviewed": "2026-04-30",
  "review_owner": "pharmaguide_clinical_team"
}
```
