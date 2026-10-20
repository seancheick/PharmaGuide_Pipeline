"""Batch A: literature records whose Evidence determination changes.

Rules (receipts in research.md):
  A1 material/preparation/combination/route/plant-part/species mismatch -> applicability_unestablished
  A2 the cited evidence contradicts the recorded direction -> direction the article reports
  A3 no qualifying human trial remains after correction (ghost or non-trial citation)
     -> verification_result verification_failure_unresolved (Evidence reads "review pending")
Each study row is restated from its own abstract (or PMC full text where noted); figures the
article does not report are removed.
"""
D = "__DELETE__"
PENDING = "verification_failure_unresolved"

REPLACEMENTS = {
    "24913818": {"title": "Rapid and sustainable detoxication of airborne pollutants by broccoli sprout beverage: results of a randomized clinical trial in China.",
                 "quote": "Thus, intervention with broccoli sprouts enhances the detoxication of some airborne pollutants and may provide a frugal means to attenuate their associated long-term health risks."},
}

SPEC = {
    # ---- A1: combination / mixture -------------------------------------------------------
    "l_isoleucine": {
        "record": {
            "effect_direction": "applicability_unestablished",
            "population_context": "Ten resistance-trained young men after resistance exercise (BCAA-only drink)",
            "studied_dose_exposure": {"values": [1400], "unit": "mg", "basis": "acute_challenge"},
            "applicability_decision": "The cited trial gave one 5.6 g BCAA drink (2.6 g leucine, 1.4 g isoleucine, 1.6 g valine) after resistance exercise and measured acute myofibrillar protein synthesis. A mixed-BCAA acute surrogate result does not establish standalone L-isoleucine efficacy or a daily dose.",
        },
        "studies": {"28638350": {"dose": "5.6 g BCAA drink containing 1.4 g isoleucine (2.6 g leucine, 1.6 g valine)", "duration": "single post-exercise dose", "outcome": "myofibrillar protein synthesis 22% higher than placebo over 4 h after exercise"}},
    },
    "l_valine": {
        "record": {
            "effect_direction": "applicability_unestablished",
            "population_context": "Ten resistance-trained young men after resistance exercise (BCAA-only drink)",
            "studied_dose_exposure": {"values": [1600], "unit": "mg", "basis": "acute_challenge"},
            "applicability_decision": "The cited trial gave one 5.6 g BCAA drink (2.6 g leucine, 1.4 g isoleucine, 1.6 g valine) after resistance exercise and measured acute myofibrillar protein synthesis. A mixed-BCAA acute surrogate result does not establish standalone L-valine efficacy or a daily dose.",
        },
        "studies": {"28638350": {"dose": "5.6 g BCAA drink containing 1.6 g valine (2.6 g leucine, 1.4 g isoleucine)", "duration": "single post-exercise dose", "outcome": "myofibrillar protein synthesis 22% higher than placebo over 4 h after exercise"}},
    },
    "ginger_extract": {
        "record": {
            "effect_direction": "applicability_unestablished",
            "material_form": "Combined Zingiber officinale + Alpinia galanga extract (EV.EXT 77) in one trial; ginger powder in the other",
            "studied_dose_exposure": {},
            "applicability_decision": "The knee-osteoarthritis RCT (247 evaluable patients, 6 weeks) used a combined extract of two ginger species, Zingiber officinale and Alpinia galanga (EV.EXT 77), taken twice daily; the second trial gave 1 g/day ginger powder and measured only nitric oxide and hs-CRP. Neither establishes standalone Zingiber officinale extract efficacy or a dose.",
        },
        "studies": {
            "11710709": {"dose": D, "outcome": "more responders with reduced knee pain on standing than placebo (63% vs 50%) with a combined Zingiber officinale + Alpinia galanga extract; more mild GI adverse events"},
            "27419081": {"dose": "1 g/day ginger powder (two 500 mg capsules)", "outcome": "serum nitric oxide and hs-CRP fell more than with placebo after 12 weeks; pain was not an outcome in the abstract"},
        },
    },
    "l_tryptophan": {
        "record": {
            "effect_direction": "applicability_unestablished",
            "material_form": "Alpha-lactalbumin (tryptophan-rich whey protein), not free L-tryptophan",
            "population_context": "Athletes and healthy adults in eight alpha-lactalbumin sleep studies",
            "studied_dose_exposure": {},
            "applicability_decision": "The cited systematic review covers alpha-lactalbumin protein supplied at 20-60 g/day (eight studies; five reported a positive association with sleep, mainly shorter sleep-onset latency). Whole-protein evidence does not establish free L-tryptophan efficacy or a dose.",
        },
        "studies": {"38185736": {"sample_size": D, "dose": "20-60 g alpha-lactalbumin, evening (<= 3.5 h before sleep)", "duration": D, "outcome": "five of eight studies found a positive association between evening alpha-lactalbumin and sleep, mainly shorter sleep-onset latency", "effect_direction": "positive_weak"}},
    },
    "cyanidin_3_glucoside": {
        "record": {
            "effect_direction": "applicability_unestablished",
            "material_form": "Purified anthocyanin mixture (the abstract does not identify a single-compound cyanidin-3-glucoside preparation)",
            "population_context": "Adults with type 2 diabetes",
            "studied_dose_exposure": {},
            "applicability_decision": "The cited 24-week RCT gave 160 mg purified anthocyanins twice daily to 58 adults with type 2 diabetes and improved lipids, antioxidant capacity and insulin resistance versus placebo. An anthocyanin mixture does not establish standalone cyanidin-3-glucoside efficacy or a dose.",
        },
        "studies": {"25833778": {"sample_size": 58, "dose": "160 mg purified anthocyanins twice daily (320 mg/day)", "outcome": "LDL-C and triglycerides fell, HDL-C rose, antioxidant capacity rose and fasting glucose and HOMA-IR fell versus placebo"}},
    },
    "phosphatidylcholine": {
        "record": {
            "effect_direction": "applicability_unestablished",
            "material_form": "Delayed intestinal-release lecithin containing 30% phosphatidylcholine",
            "population_context": "Adults with ulcerative colitis",
            "studied_dose_exposure": {},
            "applicability_decision": "The cited meta-analysis pooled three RCTs (160 patients with ulcerative colitis) of a delayed intestinal-release 30% phosphatidylcholine lecithin; a trial of >94% phosphatidylcholine lecithin failed. Ordinary or purified phosphatidylcholine supplements do not inherit this preparation-specific result, and no dose is established.",
        },
        "studies": {"33440385": {"study_type": "meta_analysis_rct", "sample_size": 160, "dose": "delayed intestinal-release 30% PC lecithin (dose not given in the abstract)", "duration": D, "outcome": "remission, clinical and endoscopic outcomes improved versus placebo in ulcerative colitis; one trial of >94% PC lecithin failed"}},
    },
    "marshmallow_root": {
        "record": {
            "effect_direction": "applicability_unestablished",
            "material_form": "Combination cough syrup (ivy leaf extract main active, thyme and aniseed decoction, marshmallow root mucilage)",
            "population_context": "Patients aged 16-89 with irritating cough",
            "studied_dose_exposure": {},
            "applicability_decision": "The only cited study is an open, uncontrolled trial of a combination cough syrup whose main active ingredient is ivy leaf extract. It does not establish standalone marshmallow root efficacy or a dose.",
        },
        "studies": {"16391481": {"study_type": "open_uncontrolled_trial", "sample_size": 62, "dose": "mean 10 mL/day (7.5-15 mL) combination syrup", "duration": "mean 12 days (3-23 days)", "outcome": "cough and expectoration symptom scores improved from baseline; no control group", "effect_direction": "positive_weak"}},
    },
    "keratin": {
        "record": {
            "effect_direction": "applicability_unestablished",
            "material_form": "Cynatine HNS: Cynatine keratin (500 mg/day) combined with vitamins and minerals",
            "population_context": "Women",
            "studied_dose_exposure": {},
            "applicability_decision": "The only cited RCT (50 women, 90 days) tested Cynatine HNS, keratin combined with vitamins and minerals. A combination result does not establish standalone keratin efficacy or a dose.",
        },
        "studies": {"25386609": {"dose": "2 capsules/day of Cynatine HNS (500 mg keratin plus vitamins and minerals)", "outcome": "hair and nail measures improved versus placebo"}},
    },
    "winged_treebine": {
        "record": {
            "effect_direction": "applicability_unestablished",
            "material_form": "Cissus quadrangularis formulation that also contains green tea, soy, chromium, selenium and B vitamins",
            "population_context": "Overweight and obese adults (123 participants)",
            "studied_dose_exposure": {},
            "applicability_decision": "The cited 8-week RCT tested a Cissus quadrangularis formulation (514 mg twice daily) that also contains green tea, soy, chromium, selenium and B vitamins (full text, PMC1570348). A multi-ingredient formulation does not establish standalone Cissus efficacy or a dose.",
        },
        "studies": {"16948861": {"sample_size": 123, "dose": "514 mg Cissus formulation twice daily (formulation includes green tea, soy, chromium, selenium, B vitamins)", "outcome": "net reductions in weight, central obesity, fasting glucose, lipids and CRP versus placebo"}},
    },
    "magnolia_bark": {
        "record": {
            "effect_direction": "applicability_unestablished",
            "material_form": "Relora: proprietary Magnolia officinalis + Phellodendron amurense blend",
            "population_context": "Overweight premenopausal women with stress-related eating and above-average anxiety",
            "studied_dose_exposure": {},
            "applicability_decision": "The only cited trial tested Relora, a Magnolia + Phellodendron blend, 250 mg three times daily for 6 weeks (40 women in the intent-to-treat population). It reduced transitory (state) anxiety but did not change trait anxiety, salivary cortisol, sleep or appetite. A blend does not establish standalone magnolia bark efficacy or a dose.",
        },
        "studies": {"18426577": {"sample_size": 40, "dose": "250 mg Relora (Magnolia + Phellodendron) three times daily", "duration": "6 weeks", "outcome": "state anxiety fell versus placebo; trait anxiety, salivary cortisol, sleep and appetite did not change"}},
    },
    "fucoxanthin": {
        "record": {
            "effect_direction": "applicability_unestablished",
            "material_form": "Xanthigen: brown seaweed extract (fucoxanthin) combined with pomegranate seed oil",
            "population_context": "Obese premenopausal women with or without NAFLD",
            "studied_dose_exposure": {},
            "applicability_decision": "The cited 16-week RCT (151 women) tested Xanthigen, brown seaweed fucoxanthin combined with pomegranate seed oil (Xanthigen-600: 300 mg oil + 300 mg seaweed extract with 2.4 mg fucoxanthin). A combination result does not establish standalone fucoxanthin efficacy or a dose.",
        },
        "studies": {"19840063": {"dose": "Xanthigen-600/2.4 mg (300 mg pomegranate seed oil + 300 mg seaweed extract with 2.4 mg fucoxanthin)", "outcome": "body weight, body and liver fat, triglycerides and CRP fell versus placebo with the combination product"}},
    },
    "fennel": {
        "record": {
            "effect_direction": "applicability_unestablished",
            "material_form": "Fennel fruit essence (2%) oral drops",
            "population_context": "Women aged 15-24 with moderate to severe primary dysmenorrhea",
            "studied_dose_exposure": {},
            "applicability_decision": "The cited study compared an untreated cycle, a mefenamic acid cycle and a fennel-essence cycle (25 drops of 2% essence every 4 hours) in 30 women; it was not randomized. Fennel relieved pain versus the untreated cycle but was less potent than mefenamic acid on days 2-3, and 5 women withdrew because of its odour. An essence preparation does not establish seed or extract efficacy or a dose.",
        },
        "studies": {"12566188": {"study_type": "self_controlled_sequential_cycles", "sample_size": 30, "dose": "2% fennel fruit essence, 25 drops every 4 hours", "duration": "one treated cycle (of three observed)", "outcome": "pain relieved versus the untreated control cycle; mefenamic acid was more potent on days 2-3; 5 of 30 withdrew because of fennel's odour"}},
    },
    # ---- A1: food / beverage / fruit / topical / species / plant part -----------------------
    "pomegranate": {
        "record": {
            "effect_direction": "applicability_unestablished",
            "material_form": "Pomegranate in different forms across 22 RCTs (the abstract singles out juice)",
            "population_context": "Adults in 22 RCTs; larger systolic reductions when baseline SBP > 130 mmHg",
            "studied_dose_exposure": {},
            "applicability_decision": "The cited meta-analysis pooled 22 RCTs of pomegranate in different forms and found lower SBP and DBP with high heterogeneity; the authors attribute the pooled effect mainly to juice. Mixed-form and juice evidence does not establish a standardized extract or punicalagin dose without bioequivalence.",
        },
        "studies": {"38410857": {"sample_size": D}},
    },
    "acai_berry": {
        "record": {
            "effect_direction": "applicability_unestablished",
            "studied_dose_exposure": {},
            "applicability_decision": "The only cited study is an open-label, uncontrolled 1-month pilot in 10 overweight adults who ate 100 g acai fruit pulp twice daily. Whole-fruit pulp evidence does not transfer to acai powder or extract without bioequivalence.",
        },
        "studies": {"21569436": {"study_type": "open_label_uncontrolled_pilot", "dose": "100 g acai pulp twice daily", "outcome": "fasting glucose, insulin and total cholesterol fell from baseline and the post-meal glucose rise was smaller; blood pressure, hs-CRP and exhaled NO did not change"}},
    },
    "chrysin": {
        "record": {
            "effect_direction": "applicability_unestablished",
            "material_form": "Propolis and honey containing chrysin (food matrix), not isolated chrysin",
            "population_context": "Male volunteers",
            "studied_dose_exposure": {},
            "applicability_decision": "The only cited study gave propolis and honey containing chrysin for 21 days and found no change in urinary testosterone. A food-matrix result does not establish an effect, or a lack of effect, for isolated chrysin supplements; the abstract does not report a chrysin dose or bioavailability.",
        },
        "studies": {"14977449": {"sample_size": D, "dose": "propolis and honey containing chrysin (amount not given in the abstract)", "outcome": "urinary testosterone did not change at 7, 14 or 21 days versus baseline or controls"}},
    },
    "cat_s_claw": {
        "record": {
            "effect_direction": "applicability_unestablished",
            "material_form": "Freeze-dried Uncaria guianensis (cited trial); U. tomentosa equivalence shown only in vitro",
            "studied_dose_exposure": {},
            "applicability_decision": "The cited 4-week knee-osteoarthritis trial (30 treated, 15 placebo) used freeze-dried Uncaria guianensis; U. tomentosa was compared only in vitro. The trial does not establish U. tomentosa pentacyclic-alkaloid extract efficacy or a dose.",
        },
        "studies": {"11603848": {"dose": "freeze-dried Uncaria guianensis (amount not given in the abstract)", "outcome": "pain on activity and medical and patient assessment scores fell versus placebo; pain at rest or at night and knee circumference did not"}},
    },
    "wild_yam_root": {
        "record": {
            "effect_direction": "applicability_unestablished",
            "material_form": "Topical wild yam cream (no oral preparation studied)",
            "population_context": "Healthy menopausal women",
            "applicability_decision": "The only cited trial applied wild yam cream to the skin for 3 months (23 women, crossover) and found no difference from placebo in symptoms, lipids or hormones. A topical result does not establish an effect, or a lack of effect, for oral wild yam preparations.",
        },
        "studies": {"11428178": {"dose": "topical wild yam cream (active vs placebo cream)", "outcome": "no difference from placebo in menopausal symptom scores; no change in lipids, FSH, estradiol or serum/salivary progesterone"}},
    },
    "pumpkin_seed_oil": {
        "record": {
            "effect_direction": "applicability_unestablished",
            "material_form": "Pumpkin seed extract capsules (cited trial); no seed-oil arm",
            "population_context": "Men aged 50-80 with BPH/LUTS",
            "studied_dose_exposure": {},
            "applicability_decision": "In the GRANU trial (1,431 men, 12 months) the pumpkin seed extract arm (500 mg twice daily) did not differ from placebo; only the whole-seed arm (5 g twice daily) showed a descriptive difference needing confirmation. No seed-oil arm was studied, so the trial does not establish pumpkin seed oil efficacy or a dose.",
        },
        "studies": {"25196580": {"dose": "500 mg pumpkin seed extract twice daily (a separate arm took 5 g pumpkin seed twice daily)", "outcome": "IPSS responder rate with the extract did not differ from placebo at 12 months; the whole-seed arm was descriptively better (58.5% vs 47.3%)", "effect_direction": "null"}},
    },
    "spearmint": {
        "record": {
            "effect_direction": "applicability_unestablished",
            "material_form": "Brewed tea from a high-rosmarinic acid spearmint variety",
            "studied_dose_exposure": {},
            "applicability_decision": "The cited 16-week trial (46 analysed) compared high-rosmarinic acid spearmint tea with commercial spearmint tea twice daily: pain fell only within the high-rosA group (the abstract reports no between-group pain test), stiffness and disability fell in both, and quality-of-life scores did not differ between groups. Brewed-tea evidence does not establish an extract's efficacy or dose without bioequivalence.",
        },
        "studies": {"25058311": {"dose": "tea brewed from high-rosmarinic acid spearmint, twice daily (control: commercial spearmint tea)", "outcome": "WOMAC pain fell within the high-rosA group only (no between-group pain test reported); stiffness and disability fell in both groups", "effect_direction": "mixed"}},
    },
    "moringa": {
        "record": {
            "effect_direction": "applicability_unestablished",
            "material_form": "Fresh Moringa oleifera leaves added to the diet (20, 40 or 60 g/day)",
            "population_context": "Adults with type 2 diabetes in rural Nigeria",
            "studied_dose_exposure": {},
            "applicability_decision": "The only cited trial added 20, 40 or 60 g Moringa leaves to the diet of 40 adults with type 2 diabetes for 14 days and found no significant effect on glucose, blood pressure or lipids after adjustment. Whole-leaf food use does not establish effects of powder or extract preparations.",
        },
        "studies": {"37229639": {"sample_size": 40, "dose": "20, 40 or 60 g Moringa leaves daily added to the diet", "duration": "14 days", "outcome": "fasting glucose did not differ between groups; no significant differences in any parameter after adjusting for baseline", "effect_direction": "null"}},
    },
    "shiitake": {
        "record": {
            "effect_direction": "applicability_unestablished",
            "material_form": "Whole dried shiitake mushrooms eaten daily (5 or 10 g)",
            "population_context": "Healthy adults aged 21-41",
            "studied_dose_exposure": {},
            "applicability_decision": "The cited 4-week study fed 52 healthy adults 5 or 10 g of whole dried shiitake daily (two dose groups, no placebo) and measured immune-cell and sIgA changes. Whole-mushroom food evidence does not establish mycelial extract (AHCC or lentinan) efficacy or a dose.",
        },
        "studies": {"25866155": {"study_type": "randomized_parallel_dose_groups_no_placebo", "outcome": "gamma-delta T and NK-T cell proliferation and salivary sIgA rose, CRP fell after 4 weeks of eating shiitake"}},
    },
    "shiitake_mushroom": {
        "record": {
            "effect_direction": "applicability_unestablished",
            "material_form": "Whole dried shiitake mushrooms eaten daily (5 or 10 g)",
            "population_context": "Healthy adults aged 21-41",
            "studied_dose_exposure": {},
            "applicability_decision": "The cited 4-week study fed 52 healthy adults 5 or 10 g of whole dried shiitake daily (two dose groups, no placebo). Whole-mushroom food evidence does not establish mycelial or fruiting-body extract (AHCC or beta-glucan) efficacy or a dose.",
        },
        "studies": {"25866155": {"study_type": "randomized_parallel_dose_groups_no_placebo", "dose": "5 or 10 g whole dried shiitake mushrooms daily", "outcome": "gamma-delta T and NK-T cell proliferation and salivary sIgA rose, CRP fell after 4 weeks of eating shiitake"}},
    },
    "oolong_tea_leaf": {
        "record": {
            "effect_direction": "applicability_unestablished",
            "material_form": "Oolong tea (8 g/day)",
            "studied_dose_exposure": {},
            "applicability_decision": "The cited 6-week study gave 8 g/day oolong tea to 102 overweight or obese adults without a control group. Uncontrolled tea-drinking evidence does not establish oolong extract efficacy or a dose.",
        },
        "studies": {"19271168": {"study_type": "uncontrolled_intervention", "dose": "8 g/day oolong tea", "outcome": "64-70% of participants lost more than 1 kg; plasma TG and TC fell in hyperlipidemic participants (no control group)"}},
    },
    "dark_sweet_cherry": {
        "record": {
            "effect_direction": "applicability_unestablished",
            "material_form": "Fresh Bing sweet cherries (280 g, single dose)",
            "population_context": "Healthy women aged 22-40",
            "studied_dose_exposure": {},
            "applicability_decision": "The only cited study fed 10 healthy women one 280 g serving of fresh Bing cherries and measured urate over 5 hours (no control). A single whole-fruit serving does not establish a cherry extract's efficacy or dose, and exercise recovery was not studied.",
        },
        "studies": {"12771324": {"study_type": "uncontrolled_single_dose", "sample_size": 10, "dose": "280 g fresh Bing sweet cherries, single dose", "duration": "5 hours", "outcome": "plasma urate fell 14% at 5 h and urinary urate excretion rose; CRP and NO fell marginally (P < 0.1)"}},
    },
    "olive_fruit_extract": {
        "record": {
            "effect_direction": "applicability_unestablished",
            "material_form": "Olive LEAF polyphenol extract (51.1 mg oleuropein, 9.7 mg hydroxytyrosol per day)",
            "population_context": "Overweight middle-aged men",
            "studied_dose_exposure": {},
            "applicability_decision": "The cited 12-week crossover RCT (46 men) used olive leaf polyphenols and improved insulin sensitivity and beta-cell responsiveness, with no effect on lipids, blood pressure or body composition. Leaf-extract evidence does not establish olive fruit extract efficacy or a dose.",
        },
        "studies": {"23516412": {"outcome": "insulin sensitivity improved 15% and beta-cell responsiveness 28% versus placebo with olive leaf extract; lipids, blood pressure and body composition unchanged"}},
    },
    "black_garlic": {
        "record": {
            "effect_direction": "applicability_unestablished",
            "material_form": "Aged garlic extract (1.2 g/day, 1.2 mg S-allylcysteine), not black (heat-fermented) garlic",
            "population_context": "Adults with uncontrolled hypertension",
            "studied_dose_exposure": {},
            "applicability_decision": "The cited 12-week RCT (88 adults with uncontrolled hypertension) tested aged garlic extract, which lowered systolic pressure 5.0 mmHg versus placebo (11.5 mmHg in responders). Aged garlic extract is a different preparation from black garlic, so the trial does not establish black garlic efficacy or a dose.",
        },
        "studies": {"26869811": {"dose": "1.2 g/day aged garlic extract (1.2 mg S-allylcysteine)", "outcome": "systolic BP fell 5.0 mmHg versus placebo overall and 11.5 mmHg in responders; central hemodynamic measures tended to improve"}},
    },
    "undecylenic_acid": {
        "record": {
            "effect_direction": "applicability_unestablished",
            "material_form": "Topical powder: 2% undecylenic acid + 20% zinc undecylenate",
            "population_context": "Patients with tinea pedis",
            "studied_dose_exposure": {},
            "applicability_decision": "The only cited trial applied an undecylenic acid / zinc undecylenate powder to the feet twice daily for 4 weeks in tinea pedis. Topical antifungal evidence does not establish oral undecylenic acid efficacy or a dose.",
        },
        "studies": {"6987185": {"dose": "topical powder (2% undecylenic acid, 20% zinc undecylenate) applied twice daily", "outcome": "88% of culture-positive patients on active powder were culture-negative at 4 weeks versus 17% on placebo"}},
    },
    # ---- A2: direction contradicted -----------------------------------------------------------
    "barberry_root": {
        "record": {
            "effect_direction": "null",
            "material_form": "Berberis vulgaris root extract capsules (500 mg)",
            "population_context": "Patients with schizophrenia on atypical antipsychotics",
            "studied_dose_exposure": {"values": [1500], "unit": "mg", "basis": "daily_intake"},
            "applicability_decision": "In the cited 3-month RCT (88 patients with schizophrenia on atypical antipsychotics), 500 mg barberry root extract three times daily did not prevent antipsychotic-related metabolic-syndrome changes; weight and waist were higher than with placebo.",
        },
        "studies": {"37575603": {"sample_size": 88, "dose": "500 mg barberry root extract three times daily", "duration": "3 months", "outcome": "metabolic syndrome measures worsened in both groups; weight and waist were higher than placebo", "effect_direction": "null"}},
    },
    "l_threonine": {
        "record": {
            "effect_direction": "applicability_unestablished",
            "studied_dose_exposure": {},
            "applicability_decision": "Essential amino acid dietary adequacy is established under DRI benchmarks. The cited study measured the threonine requirement (indicator amino acid oxidation) in 11 healthy men and is not an efficacy trial; standalone therapeutic claims beyond nutrition authority require indication proof.",
        },
        "studies": {"37004875": {"study_type": "amino_acid_requirement_study", "sample_size": 11, "dose": "six test intakes from 5 to 35 mg/kg/day", "duration": "9-day periods (1, 3 and 7 days of adaptation)", "outcome": "mean threonine requirement 10.5-12.1 mg/kg/day; adaptation length did not change it", "effect_direction": D}},
    },
    # ---- A3: no qualifying human trial remains -----------------------------------------------
    "l_carnosine": {
        "record": {"_pending": True, "effect_direction": "applicability_unestablished", "population_context": "Not established: no verified human L-carnosine trial is cited", "studied_dose_exposure": {},
                   "applicability_decision": "No verified human L-carnosine trial is recorded. The previously cited PMID 20091069 is a review of beta-alanine supplementation, not an L-carnosine trial, and the recorded dose, duration and sample size were not in it. Evidence review pending."},
        "studies": {"20091069": "REMOVE"},
    },
    "l_phenylalanine": {
        "record": {"_pending": True, "effect_direction": "applicability_unestablished", "population_context": "Not established: no verified human L-phenylalanine trial is cited", "studied_dose_exposure": {},
                   "applicability_decision": "Essential amino acid under DRI authority. No verified human L-phenylalanine trial is recorded: the previously cited PMID 37629744 is a review of depression treatments in Parkinson's disease, and the recorded open-label trial facts were not in it. Evidence review pending."},
        "studies": {"37629744": "REMOVE"},
    },
    "docosapentaenoic_acid_dpa": {
        "record": {"_pending": True, "effect_direction": "applicability_unestablished", "population_context": "Not established: the only cited source is a narrative review", "studied_dose_exposure": {},
                   "applicability_decision": "No verified human DPA intervention trial is recorded. The cited PMID 30716358 is a narrative review of n-3 DPA; the recorded RCT (24 participants, 1,000 mg/day, 4 weeks, platelet aggregation) is not in it. Evidence review pending."},
        "studies": {"30716358": {"study_type": "narrative_review", "sample_size": D, "dose": D, "duration": D, "outcome": "narrative review of n-3 DPA sources, metabolism and reported effects; no intervention estimate", "effect_direction": D, "scoring_eligible": False}},
    },
    "dimethyl_glycine": {
        "record": {"_pending": True, "effect_direction": "applicability_unestablished", "population_context": "Not established: the only cited source is a narrative review", "studied_dose_exposure": {},
                   "applicability_decision": "No verified human DMG trial is recorded. The cited PMID 34823458 is a narrative review of DMG in autism spectrum disorder; the recorded endurance RCT (16 athletes, 1,500 mg/day, 14 days) is not in it. Evidence review pending."},
        "studies": {"34823458": {"study_type": "narrative_review", "sample_size": D, "dose": D, "duration": D, "outcome": "narrative review of DMG chemistry, pharmacology and clinical studies in autism spectrum disorder; no exercise outcome", "effect_direction": D, "scoring_eligible": False}},
    },
    "boswellia_serrata_resin": {
        "record": {"_pending": True, "effect_direction": "applicability_unestablished", "population_context": "Not established: the only cited source is a rat and in-vitro study", "studied_dose_exposure": {},
                   "applicability_decision": "No verified human Boswellia trial is recorded. The cited PMID 32565872 is an in-vitro and rat osteoarthritis study of the LI13019F1 (Serratrin) composition; the recorded human RCT (75 adults, 100 mg/day, 90 days) is not in it. Evidence review pending."},
        "studies": {"32565872": {"study_type": "animal_and_in_vitro", "sample_size": D, "dose": D, "duration": D, "outcome": "LI13019F1 inhibited 5-LOX and inflammatory mediators in vitro and reduced pain and cartilage damage in MIA-induced osteoarthritic rats", "effect_direction": D, "scoring_eligible": False}},
    },
    "perilla_oil": {
        "record": {"_pending": True, "effect_direction": "applicability_unestablished", "population_context": "Not established: the only cited source is a narrative review", "studied_dose_exposure": {},
                   "applicability_decision": "No verified human perilla oil trial is recorded. The cited PMID 21909287 is a narrative review of perilla fatty-acid composition; the recorded RCT (60 adults, 3-5 g/day, 12 weeks) is not in it. Evidence review pending."},
        "studies": {"21909287": {"study_type": "narrative_review", "sample_size": D, "dose": D, "duration": D, "outcome": "narrative review of perilla seed oil fatty-acid composition (ALA 54-64%); no intervention estimate", "effect_direction": D, "scoring_eligible": False}},
    },
    "superoxide_dismutase": {
        "record": {"_pending": True, "effect_direction": "applicability_unestablished", "population_context": "Not established: the only cited source is an animal study", "studied_dose_exposure": {},
                   "applicability_decision": "No verified human GliSODin trial is recorded. The cited PMID 15742357 reports supplementation in animals; the recorded human RCT (40 adults, 500 mg/day, 4 weeks) is not in it. Evidence review pending."},
        "studies": {"15742357": {"study_type": "animal_study", "sample_size": D, "dose": D, "duration": D, "outcome": "in animals, gliadin-combined melon SOD (but not unprotected SOD) raised circulating antioxidant enzymes and resistance to oxidative stress", "effect_direction": D, "scoring_eligible": False}},
    },
    "schisandra_berry": {
        "record": {"_pending": True, "effect_direction": "applicability_unestablished", "population_context": "Not established: the only cited source is a narrative overview", "studied_dose_exposure": {},
                   "applicability_decision": "No verified human Schisandra trial with a dose or outcome is recorded. The cited PMID 18515024 is a narrative overview of Russian research; it reports no sample size, dose or pooled effect. Evidence review pending."},
        "studies": {"18515024": {"study_type": "narrative_review", "sample_size": D, "dose": D, "duration": D, "outcome": "narrative overview of Russian pharmacological and clinical research; no pooled human dose or effect estimate", "effect_direction": D, "scoring_eligible": False}},
    },
    "schisandra": {
        "record": {"_pending": True, "effect_direction": "applicability_unestablished", "population_context": "Not established: the only cited source is a narrative overview", "studied_dose_exposure": {},
                   "applicability_decision": "No verified human Schisandra trial with a dose or outcome is recorded. The cited PMID 18515024 is a narrative overview of Russian research; it reports no sample size, dose, duration or pooled effect. Evidence review pending."},
        "studies": {"18515024": {"study_type": "narrative_review", "sample_size": D, "dose": D, "duration": D, "outcome": "narrative overview of Russian pharmacological and clinical research; no pooled human dose or effect estimate", "effect_direction": D, "scoring_eligible": False}},
    },
    # broccoli keeps its determination (crude powder blocked); its only citation was a narrative review, so it
    # now cites the verified sprout-beverage trial whose evidence it cannot inherit (also in broccoli_sprout).
    "broccoli": {
        "record": {"studied_dose_exposure": {}, "population_context": "Adults in Qidong, China, exposed to airborne pollutants (broccoli sprout beverage trial)",
                   "applicability_decision": "Blocked from material form transfer. The only verified human trial concerns a broccoli sprout beverage providing 600 umol glucoraphanin and 40 umol sulforaphane daily (PMID 24913818); crude whole broccoli vegetable powder cannot inherit sprout or sulforaphane research. The previously cited PMID 30372361 is a narrative review with no human dose or outcome."},
        "studies": {"30372361": {"_replace_pmid": "24913818", "study_type": "randomized_controlled_trial", "sample_size": 291,
                                 "dose": "broccoli sprout beverage providing 600 umol glucoraphanin and 40 umol sulforaphane daily", "duration": "12 weeks",
                                 "outcome": "urinary excretion of glutathione-derived conjugates of benzene (+61%) and acrolein (+23%) rose versus placebo", "effect_direction": "positive_moderate"}},
    },
}
