"""Batch B: literature records whose study facts are corrected without changing the Evidence
determination (resolver disposition before == after; checked by the apply script).

Each study row is restated from its own abstract (or PMC full text where noted); figures the
article does not report are removed; studied_dose_exposure keeps only verified study doses;
applicability_decision drops thresholds no cited source states.
"""
D = "__DELETE__"

REPLACEMENTS = {
    # wrong-PMID rows whose described trial exists: PMID found by PubMed search, content-verified
    "11255425": {"title": "Ipriflavone in the treatment of postmenopausal osteoporosis: a randomized controlled trial.",
                 "quote": "Our data indicate that ipriflavone does not prevent bone loss or affect biochemical markers of bone metabolism. Additionally, ipriflavone induces lymphocytopenia in a significant number of women."},
    "9418683": {"title": "Does dong quai have estrogenic effects in postmenopausal women? A double-blind, placebo-controlled trial.",
                "quote": "Used alone, dong quai does not produce estrogen-like responses in endometrial thickness or in vaginal maturation and was no more helpful than placebo in relieving menopausal symptoms."},
    "18646097": {"title": "Chitosan for overweight or obesity.",
                 "quote": "Results obtained from high quality trials indicate that the effect of chitosan on body weight is minimal and unlikely to be of clinical significance."},
    "17495878": {"title": "Supplementation with goldenseal (Hydrastis canadensis), but not kava kava (Piper methysticum), inhibits human CYP3A activity in vivo.",
                 "quote": "These findings suggest that significant herb-drug interactions may result from the concomitant ingestion of goldenseal and CYP3A substrates."},
}

SPEC = {
    "l_leucine": {"studies": {"16507602": {"sample_size": D}}},
    "citrus_bioflavonoids": {
        "record": {"studied_dose_exposure": {},
                   "applicability_decision": "The cited Cochrane review pools drug-grade phlebotonics (rutosides, hidrosmine and diosmine, calcium dobesilate and others) for chronic venous insufficiency: oedema probably falls slightly, with little or no effect on quality of life or ulcer healing and slightly more adverse events. It does not establish efficacy of crude citrus bioflavonoid powders; transfer is prohibited."},
        "studies": {"33141449": {"sample_size": 7690, "dose": D, "duration": D, "outcome": "phlebotonics as a class probably reduce lower-leg oedema slightly versus placebo; little or no difference in quality of life or ulcer healing; slightly more adverse events"}},
    },
    "l_glutamine": {
        "record": {"population_context": "Adults with post-infectious IBS-D and intestinal hyperpermeability (efficacy trial); healthy men (acute GI tolerance study)",
                   "studied_dose_exposure": {"values": [15000], "unit": "mg", "basis": "daily_intake"},
                   "applicability_decision": "The IBS trial gave 5 g L-glutamine three times daily (15 g/day) for 8 weeks to adults with post-infectious IBS-D and intestinal hyperpermeability. The second study measured acute GI tolerance of single 0.3-0.9 g/kg fat-free-mass doses in healthy men and is not an efficacy trial. Sports performance or muscle recovery is not established by these sources."},
        "studies": {"32992440": {"sample_size": 14, "dose": "single beverages of 0.3, 0.6 or 0.9 g/kg fat-free mass (crossover)"}},
    },
    "l_tyrosine": {
        "record": {"studied_dose_exposure": {},
                   "applicability_decision": "The military trial gave a protein-rich drink containing 2 g tyrosine, five daily doses, during a combat training course (21 cadets); a review concludes tyrosine helps cognition mainly in short-term stressful or demanding situations. No mg/kg threshold is stated by these sources, and daily chronic mood support is not established."},
        "studies": {"26424423": {"sample_size": D, "design": "narrative_review"},
                    "10230711": {"sample_size": 21}},
    },
    "cayenne_pepper": {"record": {"studied_dose_exposure": {"values": [2, 2.56], "unit": "mg", "basis": "active_capsaicinoids_per_meal"}}},
    "gamma_linolenic_acid": {
        "record": {"studied_dose_exposure": {},
                   "applicability_decision": "Seven RCTs in the Cochrane herbal-therapy review suggest GLA from evening primrose, borage or blackcurrant seed oil reduces rheumatoid-arthritis pain and disability (moderate evidence); the eczema Cochrane review found no benefit. The cited abstracts state no GLA dose threshold."},
        "studies": {"21328257": {"sample_size": D}},
    },
    "cla": {
        "record": {"studied_dose_exposure": {"values": [3200], "unit": "mg", "basis": "daily_intake"},
                   "applicability_decision": "A dose-adjusted meta-analysis reported modest fat loss at the median 3.2 g/day; a meta-analysis of trials lasting at least 6 months found small weight (-0.70 kg) and fat (-1.33 kg) differences of uncertain clinical relevance. No insulin-sensitivity finding is reported in these sources."},
        "studies": {"17490954": {"sample_size": D, "dose": "3.2 g/day (median dose; fat loss -0.024 kg per g per week)", "duration": D},
                    "21990002": {"sample_size": D, "dose": D, "outcome": "small weight (-0.70 kg) and fat (-1.33 kg) loss versus placebo; clinical relevance uncertain"}},
    },
    "glutathione": {
        "record": {"applicability_decision": "One 6-month RCT in 54 healthy non-smoking adults found 250 or 1,000 mg/day oral GSH raised blood, erythrocyte, plasma, lymphocyte and buccal GSH stores. The abstract does not name the branded material, so brand-specific transfer is not established."},
        "studies": {("24791752", 1): "REMOVE"},
    },
    "blueberry": {
        "record": {"material_form": "Freeze-dried blueberry powder (9 of 12 studies), whole blueberries (2) or blueberry concentrate (1)",
                   "population_context": "Children, young adults and older adults with or without cognitive impairment",
                   "studied_dose_exposure": {},
                   "applicability_decision": "A systematic review of 12 studies (mostly freeze-dried blueberry) found blueberries may improve some cognitive measures; doses, durations and anthocyanin content varied too much for a dose threshold, and anthocyanin extracts were not studied."},
        "studies": {"30999017": {"sample_size": D}},
    },
    "flaxseed": {"studies": {"25740909": {"sample_size": D}}},
    "lignans": {
        "record": {"effect_direction": "mixed",
                   "studied_dose_exposure": {"values": [50, 360], "unit": "mg", "basis": "sdg_extract_daily"},
                   "applicability_decision": "A 12-week crossover RCT in 68 adults with type 2 diabetes found a modest HbA1c improvement with 360 mg/day flaxseed lignan; a 60-day crossover of 50 mg/day SDG in 46 healthy adults found no effect on plasma bile acids. No dose threshold is established."},
        "studies": {"32575611": {"sample_size": 46, "dose": "50 mg/day SDG flaxseed lignan extract", "outcome": "no intervention effect on plasma bile acids; secondary bile acids were associated with enterolactone excretion", "effect_direction": "null"}},
    },
    "cryptoxanthin": {
        "record": {"effect_direction": "applicability_unestablished",
                   "material_form": "Beta-cryptoxanthin supplement (source material not stated in the abstract)",
                   "population_context": "Healthy Asian women aged 21-35",
                   "studied_dose_exposure": {"values": [3, 6], "unit": "mg", "basis": "daily_intake"},
                   "applicability_decision": "The cited 8-week RCT (90 healthy women; 3 or 6 mg/day) established pharmacokinetics and tolerability but found no effect on mood, sleep, metabolic or microbiome outcomes, so efficacy is not established."},
        "studies": {"37242207": {"sample_size": 90, "dose": "3 or 6 mg/day beta-cryptoxanthin", "outcome": "plasma beta-cryptoxanthin rose dose-dependently; no effect on retinol-dependent gene expression, mood, activity, sleep, metabolic parameters or fecal microbiota"}},
    },
    "garcinia_cambogia": {
        "record": {"studied_dose_exposure": {"values": [1500], "unit": "mg", "basis": "hca_daily"},
                   "applicability_decision": "Reviewed null for clinically meaningful weight loss: the 12-week RCT (135 randomized; 1,500 mg/day HCA) found no weight or fat-mass difference versus placebo, and a meta-analysis of nine pooled trials found only a small short-term difference (-0.88 kg) of uncertain clinical relevance."},
        "studies": {"21197150": {"sample_size": D, "primary_endpoint": "body weight loss compared to placebo", "effect": "positive_weak",
                                 "notes": "Pooled MD -0.88 kg (95% CI -1.75 to -0.00) versus placebo; magnitude small and clinical relevance uncertain."}},
    },
    "green_coffee_bean": {
        "record": {"population_context": "Adults with mild hypertension (BP trial); overweight adults (weight trials)",
                   "studied_dose_exposure": {"values": [140], "unit": "mg", "basis": "cga_daily"},
                   "applicability_decision": "One RCT (28 adults with mild hypertension) found 140 mg/day chlorogenic acid from green coffee bean extract lowered blood pressure. A meta-analysis of three weight trials, all at high risk of bias, found -2.47 kg versus placebo and called the evidence promising but of poor quality."},
        "studies": {"20871849": {"sample_size": D}, "16820341": {"sample_size": 28}},
    },
    "linoleic_acid": {"studies": {"23386268": {"effect": "negative", "primary_endpoint": "all-cause and cardiovascular mortality (higher in the linoleic acid group)"}}},
    "pumpkin": {
        "record": {"population_context": "Men aged 50-80 with BPH/LUTS", "studied_dose_exposure": {},
                   "applicability_decision": "Blocked from material form transfer. The GRANU trial (1,431 men, 12 months) tested 5 g pumpkin seed twice daily and 500 mg pumpkin seed extract twice daily: the extract did not differ from placebo and the whole-seed result was descriptive only, needing confirmation. No seed-oil arm was studied and no dose is established for powders."},
        "studies": {"25196580": {"sample_size": 1431, "dose": "5 g pumpkin seed twice daily, or 500 mg pumpkin seed extract twice daily", "outcome": "extract did not differ from placebo at 12 months; whole seed was descriptively better (58.5% vs 47.3% responders)", "effect_direction": "mixed"}},
    },
    "rose_hips": {
        "record": {"material_form": "Powder of seeds and shells of a Rosa canina subspecies (rose hip and seed powder)",
                   "applicability_decision": "One crossover RCT (94 patients with hip or knee osteoarthritis) gave 5 g/day of a rose hip seed-and-shell powder for 3 months; a systematic review describes the proprietary powder (Litozin) studies as exploratory, with clinical effect sizes still to be determined."},
        "studies": {"18384191": {"study_type": "systematic_review", "sample_size": D, "dose": D, "duration": D, "outcome": "proprietary rose hip and seed powder (Litozin) used successfully in exploratory studies in osteoarthritis, rheumatoid arthritis and low back pain; effect sizes not yet established", "effect_direction": "positive_weak"},
                    "16195164": {"sample_size": 94, "dose": "5 g/day rose hip seed-and-shell powder", "outcome": "WOMAC pain fell versus placebo at 3 weeks; stiffness, disability and global severity fell at 3 months; less rescue medication"}},
    },
    "dandelion": {"record": {"studied_dose_exposure": {}}, "studies": {"19678785": {"dose": "8 mL fresh-leaf hydroethanolic extract, three doses in one day"}}},
    "agmatine": {
        "record": {"studied_dose_exposure": {"values": [2670], "unit": "mg", "basis": "daily_intake"},
                   "applicability_decision": "The randomized phase gave 2.67 g/day agmatine sulfate for 14 days to adults with lumbar disc-associated radiculopathy (61 analysed) and improved pain and quality of life versus placebo; lower doses appeared only in an open-label safety escalation."},
    },
    "chlorophyll": {
        "record": {"studied_dose_exposure": {},
                   "applicability_decision": "An uncontrolled report in 62 geriatric nursing-home patients found chlorophyllin tablets helpful for body and fecal odour; the abstract gives no dose or duration."},
        "studies": {"7350215": {"study_type": "uncontrolled_clinical_report", "dose": D, "duration": D}},
    },
    "apple_cider_vinegar": {
        "record": {"material_form": "Vinegar (type varies across trials)", "studied_dose_exposure": {},
                   "applicability_decision": "A meta-analysis found vinegar with a meal lowered postprandial glucose and insulin; a crossover study's title reports improved insulin sensitivity to a high-carbohydrate meal in insulin resistance or type 2 diabetes. The cited abstracts state no acetic-acid dose."},
        "studies": {"28292654": {"sample_size": D, "dose": D}, "14694010": {"sample_size": D, "dose": D}},
    },
    "goldenseal": {
        "record": {"studied_dose_exposure": {},
                   "applicability_decision": "Goldenseal supplementation for 14 days inhibited CYP3A activity in 16 healthy volunteers (midazolam probe), a clinically relevant drug-interaction finding; standalone antimicrobial or immune efficacy in humans is not established by the cited source."},
        "studies": {"32591416": {"_replace_pmid": "17495878", "study_type": "randomized_crossover_pharmacokinetic", "sample_size": 16, "dose": D, "duration": "14 days per supplementation phase",
                                 "outcome": "midazolam AUC rose (107.9 to 175.3 ng*h/mL) and clearance fell after goldenseal, showing CYP3A inhibition; kava had no effect", "effect_direction": "mixed"}},
    },
    "guarana": {
        "record": {"studied_dose_exposure": {"values": [37.5, 75], "unit": "mg", "basis": "acute_single_dose"},
                   "applicability_decision": "Single doses of 37.5-300 mg of a standardized guarana extract (PC-102) were tested in 26 adults; the two lower doses (37.5 and 75 mg) gave more positive acute cognitive effects than the higher doses."},
        "studies": {"16533867": {"dose": "single doses of 37.5, 75, 150 and 300 mg standardized extract (PC-102)", "outcome": "improved secondary memory and alert and content mood ratings; lower doses more positive than higher doses"}},
    },
    "olive_leaf_powder": {
        "record": {"studied_dose_exposure": {"values": [1000], "unit": "mg", "basis": "daily_intake"},
                   "applicability_decision": "Olive leaf extract (EFLA 943) 500 mg twice daily for 8 weeks lowered SBP and DBP from baseline in stage-1 hypertension, similarly to captopril (active-controlled; no placebo arm)."},
        "studies": {"21036583": {"sample_size": D, "outcome": "SBP and DBP fell from baseline, not significantly different from captopril; triglycerides fell with olive leaf extract"}},
    },
    "lecithin": {
        "record": {"applicability_decision": "One uncontrolled study in 30 hypercholesterolemic adults aged 58-70 (full text, PMC3065734) took one 500 mg soy lecithin capsule daily for 2 months; total and LDL cholesterol fell from baseline."},
        "studies": {"21490917": {"study_type": "uncontrolled_clinical_study", "outcome": "total cholesterol fell 40.7-42.0% and LDL cholesterol 42.1-56.2% from baseline after 1-2 months (no control group)"}},
    },
    "OI_BEETROOT_POWDER": {
        "record": {"studied_dose_exposure": {"values": [372], "unit": "mg", "basis": "inorganic_nitrate_daily"},
                   "applicability_decision": "Requires a quantified inorganic nitrate exposure: the umbrella review's time-to-exhaustion benefit was more pronounced with at least 6 mmol/day (372 mg/day) for more than 3 days. Whole dehydrated beetroot powder lacking standardized nitrate disclosure cannot establish applicability."},
        "studies": {"40085422": {"sample_size": 2672, "dose": ">= 6 mmol/day (372 mg/day) dietary nitrate, > 3 days (time-to-exhaustion subgroup)",
                                 "outcome": "nitrate improved time-to-exhaustion, total distance, muscular endurance, peak power and time to peak power; no significant improvement in other outcomes; most reviews low to critically low quality"}},
    },
    "hops": {"studies": {"17486686": {"sample_size": D, "duration": "4 weeks", "outcome": "the fixed valerian-hops combination reduced sleep latency versus placebo; valerian alone did not"}}},
    "nicotinamide_riboside": {
        "record": {"studied_dose_exposure": {"values": [100, 300, 1000], "unit": "mg", "basis": "daily_intake"},
                   "applicability_decision": "In an 8-week RCT of 140 overweight adults, 100, 300 and 1,000 mg/day NR raised whole-blood NAD+ dose-dependently (22%, 51% and 142%) within 2 weeks; a crossover study in 12 adults showed single 100-1,000 mg doses raised the blood NAD+ metabolome."},
        "studies": {"27721479": {"dose": "single doses of 100, 300 and 1,000 mg NR (crossover)", "duration": "single doses"},
                    "31278280": {"dose": "100, 300 or 1,000 mg/day NR chloride", "outcome": "whole-blood NAD+ rose 22%, 51% and 142% by dose within 2 weeks and stayed raised to 8 weeks"}},
    },
    "licorice": {
        "record": {"material_form": "Glycyrrhiza glabra extract GutGard (glycyrrhizin <= 0.5%, flavonoids >= 10%; full text PMC3123991)",
                   "applicability_decision": "GutGard 75 mg twice daily for 30 days reduced functional dyspepsia symptoms and improved quality of life versus placebo in 50 patients."},
        "studies": {"21747893": {"dose": "75 mg GutGard twice daily (150 mg/day)"}},
    },
    "dgl_deglycyrrhizinated_licorice": {
        "record": {"material_form": "Glycyrrhiza glabra extract GutGard (glycyrrhizin <= 0.5%, flavonoids >= 10%; full text PMC3123991)",
                   "studied_dose_exposure": {"values": [150], "unit": "mg", "basis": "daily_intake"},
                   "applicability_decision": "GutGard, a low-glycyrrhizin (<= 0.5%) licorice extract, 75 mg twice daily for 30 days reduced functional dyspepsia symptoms versus placebo in 50 patients; blood pressure was not an outcome."},
        "studies": {"21747893": {"outcome": "total dyspepsia symptom scores and Nepean dyspepsia index fell versus placebo at days 15 and 30; well tolerated"}},
    },
    "gotu_kola": {
        "record": {"studied_dose_exposure": {"values": [60, 120], "unit": "mg", "basis": "ttfca_daily"},
                   "applicability_decision": "In a single-blind, placebo-controlled trial in venous hypertensive microangiopathy, 60 and 120 mg/day TTFCA improved microcirculatory measures versus placebo; symptom effects were larger at 120 mg/day."},
        "studies": {"11666126": {"sample_size": D, "duration": D, "study_type": "single_blind_randomized_controlled_trial"}},
    },
    "omega_6_fatty_acids": {
        "record": {"studied_dose_exposure": {},
                   "applicability_decision": "Essential fatty acid family established under DRI authority. In the cited dietary-substitution trial (458 men after a coronary event) replacing saturated fat with linoleic acid raised all-cause and cardiovascular mortality, and the updated meta-analysis showed no cardiovascular benefit."},
        "studies": {"23386268": {"study_type": "randomized_controlled_trial_recovered_data_with_meta_analysis", "outcome": "higher all-cause (HR 1.62) and cardiovascular mortality with linoleic acid substitution; updated meta-analysis showed no cardiovascular benefit", "effect_direction": "negative"}},
    },
    "nattokinase": {
        "record": {"studied_dose_exposure": {"values": [2000], "unit": "FU", "basis": "single_dose"},
                   "applicability_decision": "A single 2,000 FU dose of nattokinase (NSK-SD) changed coagulation and fibrinolysis markers, all within normal ranges, in 12 healthy young men (crossover). The abstract gives no mg amount or daily-use outcome."},
        "studies": {"26109079": {"dose": "single dose of 2,000 FU nattokinase (NSK-SD)"}},
    },
    "evening_primrose_oil": {"studies": {"23633319": {"dose": D, "duration": D}}},
    "pygeum": {
        "record": {"effect_direction": "positive_moderate", "studied_dose_exposure": {},
                   "applicability_decision": "A Cochrane review of 18 RCTs (1,562 men; mean 64 days) found Pygeum africanum preparations, alone or in combination, moderately improved urologic symptoms and flow measures versus placebo; the studies were small and short and used varied doses and preparations, so no dose is established."},
        "studies": {"11869585": {"dose": D, "duration": "30-122 days (mean 64)", "outcome": "moderately large improvement in combined urologic symptoms and flow; nocturia -19%, residual urine -24%, peak flow +23% versus placebo", "effect_direction": "positive_moderate"}},
    },
    "rosemary": {
        "record": {"material_form": "Dried rosemary leaf powder",
                   "applicability_decision": "In 28 older adults, a single 750 mg dose of dried rosemary leaf powder improved speed of memory versus placebo, while the highest dose (6,000 mg) impaired it; extracts were not studied."},
        "studies": {"21877951": {"dose": "750 mg dried rosemary leaf powder (single dose; 6,000 mg impaired memory speed)"}},
    },
    "l_cysteine": {
        "record": {"material_form": "Glutathione-precursor combination containing N-acetylcysteine (not L-cysteine)", "studied_dose_exposure": {},
                   "applicability_decision": "Multi-precursor combination trials do not isolate standalone L-cysteine clinical efficacy: the cited 8-week study (30 adults, 15 per group; full text PMC7690269) gave a combination of glutamine, alpha-ketoglutarate, alanine, N-acetylcysteine and glycine, with or without polydatin."},
        "studies": {"33105552": {"sample_size": 30, "dose": "combination supplement (glutamine, alpha-ketoglutarate, alanine, N-acetylcysteine, glycine; amounts not in the abstract)", "duration": "8 weeks", "outcome": "reduced glutathione and other reduced thiols rose and oxidized species fell with both combination supplements", "effect_direction": "positive_weak"}},
    },
    "globe_artichoke": {
        "record": {"studied_dose_exposure": {"values": [1920], "unit": "mg", "basis": "daily_intake"},
                   "applicability_decision": "A 6-week RCT in 244 functional dyspepsia patients gave 2 x 320 mg artichoke leaf extract three times daily (1,920 mg/day) and improved symptoms and quality of life versus placebo."},
        "studies": {"14653829": {"dose": "2 x 320 mg artichoke leaf extract three times daily (1,920 mg/day)"}},
    },
    "uva_ursi_leaf": {
        "record": {"effect_direction": "mixed", "population_context": "Adult women with suspected uncomplicated urinary tract infection in primary care", "studied_dose_exposure": {},
                   "applicability_decision": "In an active-controlled RCT (398 women with uncomplicated UTI), initial uva ursi treatment reduced antibiotic courses but caused a higher symptom burden, failed non-inferiority and was followed by more pyelonephritis (8 vs 2) than fosfomycin. No placebo-controlled or recurrent-UTI prevention benefit is established."},
        "studies": {"34111592": {"study_type": "randomized_controlled_trial_active_comparator", "sample_size": 398, "dose": "uva ursi extract 105 mg, 2 tablets three times daily (versus fosfomycin 3 g once)", "duration": "5 days; outcomes to day 28",
                                 "outcome": "63.6% fewer antibiotic courses, but symptom burden 136.5% of fosfomycin (non-inferiority failed) and 8 vs 2 pyelonephritis cases", "effect_direction": "mixed"}},
    },
    "dong_quai": {
        "record": {"studied_dose_exposure": {},
                   "applicability_decision": "Monotherapy for menopausal vasomotor symptoms failed in a double-blind RCT (Hirata et al., 71 women, 24 weeks): no difference from placebo in endometrial thickness, vaginal maturation, flushes or Kupperman index; reviewed null."},
        "studies": {"34090852": {"_replace_pmid": "9418683", "sample_size": 71, "dose": D, "duration": "24 weeks", "outcome": "no differences versus placebo in endometrial thickness, vaginal maturation index, vasomotor flushes or Kupperman index", "effect_direction": "null"}},
    },
    "aloe_vera": {
        "record": {"material_form": "Aloe vera preparations (varied across 8 trials)", "studied_dose_exposure": {},
                   "applicability_decision": "A meta-analysis of 8 RCTs (470 patients) found Aloe vera improved fasting glucose in prediabetes and HbA1c in type 2 diabetes, with high heterogeneity; standardized preparations and better trials are needed, and no dose is established."},
        "studies": {"27009750": {"dose": D, "duration": D, "outcome": "fasting glucose fell in prediabetes (-0.22 mmol/L); in type 2 diabetes FPG fell marginally and HbA1c fell (-11 mmol/mol)"}},
    },
    "hawthorn": {
        "record": {"studied_dose_exposure": {},
                   "applicability_decision": "A meta-analysis of 8 trials (632 patients, NYHA I-III, mostly adjunct to conventional treatment) found hawthorn extract monopreparations improved maximal workload and dyspnoea and fatigue versus placebo; the abstract does not name the extracts or doses."},
        "studies": {"12798455": {"sample_size": 632, "dose": D, "duration": D, "outcome": "maximal workload +7 W and lower pressure-heart rate product versus placebo; dyspnoea and fatigue improved"}},
    },
    "oat_straw": {
        "record": {"population_context": "Adults aged 40-65 with self-reported age-related memory decline",
                   "applicability_decision": "Single 800 mg and 1,600 mg doses of a green oat extract (Neuravena) were tested; benefits appeared with 800 mg, and the authors suggest the optimal dose lies at or below 800 mg."},
        "studies": {"26618715": {"sample_size": D, "dose": "single doses of 800 or 1,600 mg green oat extract (Neuravena)", "outcome": "800 mg improved global task speed, delayed word recall and an executive-function task (Peg and Ball)"}},
    },
    "lion_s_mane": {
        "record": {"material_form": "Hericium erinaceus dry fruiting-body powder tablets (96% powder)",
                   "studied_dose_exposure": {"values": [3000], "unit": "mg", "basis": "daily_intake"},
                   "applicability_decision": "Four 250 mg tablets (96% dry fruiting-body powder) three times daily (3 g/day) for 16 weeks improved HDS-R cognitive scores versus placebo in 30 adults aged 50-80 with MCI; scores fell after stopping."},
    },
    "butterbur": {
        "record": {"material_form": "Petasites hybridus standardized special root extract (pyrrolizidine-alkaloid content not stated in the cited abstract)",
                   "studied_dose_exposure": {"values": [100, 150], "unit": "mg", "basis": "daily_intake"},
                   "applicability_decision": "In 245 migraine patients, 75 mg twice daily (150 mg/day) of a standardized Petasites root extract reduced attack frequency versus placebo over 4 months; 50 mg twice daily did not reach significance."},
        "studies": {"15623680": {"dose": "75 mg twice daily standardized root extract (50 mg twice daily arm not significant)"}},
    },
    "red_clover": {
        "record": {"studied_dose_exposure": {},
                   "applicability_decision": "A meta-analysis of 8 trials (1,179 women; full text PMC8069620) found red clover isoflavone extracts reduced daily hot flushes by 1.73 versus placebo with high heterogeneity; isoflavone doses ranged 37.1-160 mg/day and the >= 80 mg/day subgroup was not significant."},
        "studies": {"33920485": {"sample_size": 1179, "dose": "37.1-160 mg/day isoflavones (mean 65.1 mg)", "duration": D, "outcome": "daily hot flushes -1.73 versus placebo; larger but non-significant difference at >= 80 mg/day"}},
    },
    "grape_seed": {
        "record": {"studied_dose_exposure": {"values": [300], "unit": "mg", "basis": "daily_intake"},
                   "applicability_decision": "300 mg/day Enovita grape seed extract for 16 weeks modulated blood pressure versus placebo in 80 healthy adults with mildly elevated blood pressure."},
    },
    "l_serine": {
        "record": {"population_context": "Adults with hereditary sensory and autonomic neuropathy type 1 (HSAN1)", "studied_dose_exposure": {},
                   "applicability_decision": "One RCT in 18 patients with HSAN1, a rare genetic neuropathy, found 400 mg/kg/day L-serine slowed progression and lowered deoxysphingolipids. This disease-specific, very-high-dose evidence does not establish general neurological benefit or a supplement dose."},
        "studies": {"30626650": {"sample_size": 18, "outcome": "CMTNS neuropathy score improved versus placebo after 1 year; deoxysphinganine fell 59%"}},
    },
    "beta_glucan": {"studies": {"23378458": {"sample_size": 77}}},
    "blood_orange_extract": {
        "record": {"applicability_decision": "400 mg/day Moro juice extract (Morosil) for 12 weeks reduced BMI, weight and waist and hip circumference versus placebo in overweight healthy adults."},
        "studies": {"25588369": {"sample_size": D}},
    },
    "siberian_ginseng": {
        "record": {"studied_dose_exposure": {"values": [800], "unit": "mg", "basis": "daily_intake"},
                   "applicability_decision": "800 mg/day Eleutherococcus senticosus for 8 weeks improved endurance time and VO2 peak in a crossover trial in 9 recreationally trained men."},
    },
    "borage_seed_oil": {
        "record": {"studied_dose_exposure": {"values": [1400], "unit": "mg", "basis": "gla_daily"},
                   "applicability_decision": "1.4 g/day GLA in borage seed oil for 24 weeks reduced rheumatoid-arthritis signs and symptoms versus cotton seed oil placebo in 37 patients; the authors note this dose is far above usual supplement doses."},
        "studies": {"8214997": {"sample_size": 37}},
    },
    "goji_berry": {"record": {"studied_dose_exposure": {}}},
    "atp": {"studies": {"28080323": {"sample_size": 42, "duration": "2 weeks", "outcome": "prevented post-exercise falls in ATP and muscle excitability and increased later-bout Wingate peak power versus baseline"}}},
    "neurofactor": {
        "record": {"applicability_decision": "A single 100 mg dose of whole coffee fruit concentrate raised plasma BDNF 143% from baseline in 10 fasted adults; no daily-use or neurological outcome was measured."},
        "studies": {"23312069": {"study_type": "randomized_single_dose_parallel_groups", "sample_size": 10, "duration": "single dose; 120 min sampling", "outcome": "plasma BDNF rose 143% from baseline with whole coffee fruit concentrate (n=10)"}},
    },
    "coffeeberry": {
        "record": {"applicability_decision": "A single 100 mg dose of whole coffee fruit concentrate raised plasma BDNF 143% from baseline in 10 fasted adults; cognition was not measured."},
        "studies": {"23312069": {"study_type": "randomized_single_dose_parallel_groups", "sample_size": 10, "duration": "single dose; 120 min sampling", "outcome": "plasma BDNF rose 143% from baseline with whole coffee fruit concentrate (n=10)"}},
    },
    "coffee_fruit": {
        "record": {"applicability_decision": "A single 100 mg dose of whole coffee fruit concentrate raised plasma BDNF 143% from baseline in 10 fasted adults; cognition or alertness was not measured."},
        "studies": {"23312069": {"study_type": "randomized_single_dose_parallel_groups", "sample_size": 10, "duration": "single dose; 120 min sampling", "outcome": "plasma BDNF rose 143% from baseline with whole coffee fruit concentrate (n=10)"}},
    },
    "pregnenolone": {
        "record": {"population_context": "Adults with schizophrenia (adjunctive treatment)",
                   "applicability_decision": "Reviewed null for cognition: in an 8-week adjunctive RCT in 120 people with schizophrenia, pregnenolone did not improve cognition (MCCB) but improved functional capacity (UPSA-B). This disease-specific result does not establish cognitive benefit in general adults."},
        "studies": {"25030803": {"sample_size": 120, "dose": D, "duration": "8 weeks", "outcome": "no improvement in MCCB cognition versus placebo; UPSA-B functional capacity improved (p = 0.03)", "effect_direction": "mixed"}},
    },
    "d_beta_hydroxybutyrate_bhb": {
        "record": {"effect_direction": "mixed", "studied_dose_exposure": {},
                   "applicability_decision": "Two acute 0.38 g/kg doses of BHB salts before exercise raised plasma BHB to about 0.3-0.4 mM in 19 trained cyclists, with no effect on lactate, perceived exertion or efficiency; GI symptoms occurred in 13 of 19."},
        "studies": {"29338584": {"sample_size": 19, "dose": "0.38 g/kg BHB salts at 60 and 15 min before exercise", "outcome": "plasma BHB rose to 0.33-0.44 mM; glucose lower and RER higher; no effect on lactate, exertion or efficiency; GI symptoms in 13 of 19", "effect_direction": "mixed"}},
    },
    "guanidinoacetate": {
        "record": {"effect_direction": "positive_weak", "studied_dose_exposure": {},
                   "applicability_decision": "An uncontrolled 8-week study in 5 healthy men (36 mg/kg/day for 4 weeks, then up to 60 mg/kg/day) found brain creatine rose in several regions; no clinical benefit or dose threshold is established."},
        "studies": {"27497517": {"study_type": "uncontrolled_case_study", "sample_size": 5, "dose": "36 mg/kg/day for 4 weeks, then up to 60 mg/kg/day", "duration": "8 weeks", "outcome": "brain creatine rose in cerebellum and white and grey matter (10.7% at 4 weeks); thalamus creatine fell at 4 weeks", "effect_direction": "positive_weak"}},
    },
    "feverfew": {
        "record": {"material_form": "Dried feverfew leaf capsules", "studied_dose_exposure": {},
                   "applicability_decision": "One capsule of dried feverfew leaves daily for 4 months reduced migraine frequency and severity versus placebo in a crossover RCT (72 randomized, 59 analysed); the abstract gives no mg or parthenolide amount."},
        "studies": {"2899663": {"sample_size": 72, "dose": "one capsule of dried feverfew leaves daily (amount not given in the abstract)"}},
    },
    "oregano": {
        "record": {"studied_dose_exposure": {"values": [600], "unit": "mg", "basis": "daily_intake"},
                   "applicability_decision": "600 mg/day emulsified oregano oil for 6 weeks cleared or reduced enteric parasites in an uncontrolled study of 14 adults."},
        "studies": {"10815019": {"study_type": "uncontrolled_clinical_study"}},
    },
    "activated_charcoal": {"studies": {"3521259": {"sample_size": 99, "dose": D}}},
    "maitake": {
        "record": {"effect_direction": "mixed", "studied_dose_exposure": {},
                   "applicability_decision": "A phase I/II dose-escalation study in 34 postmenopausal breast cancer survivors found an oral Maitake polysaccharide extract both enhanced and depressed immune measures, with non-monotonic dose-responses; no beneficial dose is established."},
        "studies": {"19253021": {"dose": "0.1, 0.5, 1.5, 3 or 5 mg/kg twice daily Maitake liquid extract", "outcome": "both immune-stimulatory and immune-inhibitory effects in peripheral blood; non-monotonic dose-response", "effect_direction": "mixed"}},
    },
    "OI_SHARK_CARTILAGE": {"studies": {"15912493": {"dose": D, "duration": D}}},
    "butchers_broom_root": {
        "record": {"studied_dose_exposure": {},
                   "applicability_decision": "A 12-week RCT in 148 women with chronic venous insufficiency found a Ruscus extract (Fagorutin Ruscus) reduced leg volume and symptoms versus placebo at the German-monograph dose; the abstract does not give the amount."},
        "studies": {"12040966": {"dose": D, "outcome": "leg volume, ankle and leg circumference and heavy-leg symptoms improved versus placebo"}},
    },
    "cranberry_fruit": {
        "record": {"material_form": "Cranberry products (juice, tablets or capsules; PAC dose varied)", "studied_dose_exposure": {},
                   "applicability_decision": "A Cochrane review (50 studies, 8,857 participants) found cranberry products probably reduce symptomatic culture-verified UTIs in women with recurrent UTI (RR 0.74), children and people susceptible after interventions, with no difference between low, moderate and high PAC doses; no benefit was shown in elderly institutionalised people, pregnant women or adults with bladder-emptying problems."},
        "studies": {"37068952": {"sample_size": 8857, "dose": "cranberry products (juice or tablets/capsules; no difference between PAC dose levels)", "duration": D}},
    },
    "hibiscus_extract": {
        "record": {"material_form": "Hibiscus sabdariffa calyx tea or extract", "studied_dose_exposure": {},
                   "applicability_decision": "A comprehensive narrative review of animal and human studies reports that in RCTs hibiscus calyx tea or extract lowered SBP and DBP in pre- to moderate hypertension and type 2 diabetes; the review gives no pooled sample, dose or duration."},
        "studies": {"23333908": {"study_type": "narrative_review", "sample_size": D, "dose": D, "duration": D, "outcome": "in RCTs, daily hibiscus tea or extract lowered SBP and DBP; tea comparable to captopril, less effective than lisinopril", "effect_direction": "positive_weak"}},
    },
    "tudca": {
        "record": {"population_context": "Patients with primary biliary cirrhosis",
                   "studied_dose_exposure": {"values": [500, 1000, 1500], "unit": "mg", "basis": "daily_intake"},
                   "applicability_decision": "In a 6-month dose-response study (24 PBC patients, no placebo arm), 500, 1,000 and 1,500 mg/day TUDCA all lowered liver enzymes; the authors suggest about 10 mg/kg/day for long-term study."},
        "studies": {"8674405": {"sample_size": 24, "dose": "500, 1,000 or 1,500 mg/day TUDCA", "outcome": "serum liver enzymes fell with all three doses after the first month; no significant difference between doses; no placebo arm"}},
    },
    "nopal": {
        "record": {"material_form": "Opuntia ficus-indica cladode and fruit-skin extract", "population_context": "Healthy, physically active men", "studied_dose_exposure": {},
                   "applicability_decision": "In an acute crossover in 6 healthy men, 1,000 mg OFI extract taken before and after a 75 g glucose load lowered the glucose AUC at rest and after exercise and raised insulin at rest; no diabetic or metabolic-syndrome population was studied."},
        "studies": {"22805855": {"sample_size": 6, "dose": "1,000 mg OFI extract 30 min before and immediately after an OGTT", "outcome": "glucose AUC fell 26% at rest and 37% after exercise; serum insulin was higher at rest"}},
    },
    "celery_seed": {
        "record": {"studied_dose_exposure": {"values": [1340], "unit": "mg", "basis": "daily_intake"},
                   "applicability_decision": "Four capsules daily (1.34 g/day) of celery seed extract for 4 weeks lowered 24-hour ambulatory BP from baseline in 52 hypertensive patients (crossover); placebo produced no change."},
    },
    "lychee_polyphenol": {
        "record": {"studied_dose_exposure": {"values": [200], "unit": "mg", "basis": "daily_intake"},
                   "applicability_decision": "200 mg/day Oligonol (oligomerized lychee polyphenols; 40 mg flavanol monomers and dimers from lychee and tea) for 12 weeks reduced CT-measured visceral fat area versus placebo in 66 overweight Japanese adults."},
        "studies": {"40887285": {"sample_size": 66, "dose": "200 mg/day Oligonol", "outcome": "visceral fat area fell versus placebo (primary endpoint)"}},
    },
    "horse_chestnut_seed": {
        "record": {"studied_dose_exposure": {},
                   "applicability_decision": "A Cochrane review found oral horse chestnut seed extract monopreparations improved chronic venous insufficiency signs and symptoms versus placebo (leg pain in 6 of 7 trials; leg volume in 5 trials, n = 289); more rigorous RCTs are needed and the abstract gives no escin dose."},
        "studies": {"15106197": {"sample_size": D, "dose": D, "duration": D}},
    },
    "colostrum": {
        "record": {"studied_dose_exposure": {},
                   "applicability_decision": "14 days of bovine colostrum truncated the exercise-induced rise in gut permeability by 80% in 12 volunteers (crossover); the abstract gives no daily dose."},
        "studies": {"21148400": {"sample_size": 12, "dose": D}},
    },
    "yerba_mate_leaf": {
        "record": {"studied_dose_exposure": {"values": [3000], "unit": "mg", "basis": "daily_intake"},
                   "applicability_decision": "3 g/day Yerba Mate (three capsules with each meal) for 12 weeks reduced body fat mass, percent body fat and waist-hip ratio versus placebo in 30 obese Korean adults."},
        "studies": {"26408319": {"dose": "3 g/day Yerba Mate (three capsules with each meal)"}},
    },
    "milk_basic_protein": {"studies": {"17048062": {"sample_size": 35, "outcome": "lumbar (L2-L4) BMD rose 1.57% versus 0.13% with placebo; urinary NTx fell and osteocalcin rose"}}},
    "picrorhiza": {
        "record": {"material_form": "Picrorhiza kurroa root powder capsules (picroside-standardized)",
                   "studied_dose_exposure": {"values": [1125], "unit": "mg", "basis": "daily_intake"},
                   "applicability_decision": "Picrorhiza root powder 375 mg three times daily for 2 weeks (15 patients versus 18 on placebo with acute viral hepatitis) sped the fall in bilirubin and transaminases."},
        "studies": {"9715310": {"sample_size": 33}},
    },
    "algae_oil": {
        "record": {"studied_dose_exposure": {"values": [600], "unit": "mg", "basis": "dha_daily"},
                   "applicability_decision": "600 mg/day algal DHA for 2 weeks raised plasma and red-cell DHA equivalently to cooked salmon in 32 adults (open-label); cardiovascular or cognitive outcomes were not studied."},
        "studies": {"18589030": {"study_type": "randomized_open_label_parallel_vs_salmon", "sample_size": 32}},
    },
    "alpha_amylase": {"record": {"studied_dose_exposure": {}}, "studies": {"30156436": {"dose": "50 mg multienzyme complex (DigeZyme) three times daily"}}},
    "larch_arabinogalactan": {
        "record": {"studied_dose_exposure": {"values": [4500], "unit": "mg", "basis": "daily_intake"},
                   "applicability_decision": "4.5 g/day of a larch arabinogalactan extract (ResistAid) for 72 days gave larger pneumococcal-vaccine IgG responses than placebo for 2 of 7 antibody subtypes (18C, 23F) in 45 healthy adults."},
        "studies": {"20796315": {"outcome": "greater IgG response than placebo for 2 of 7 pneumococcal subtypes (18C, 23F); no effect on salivary IgA, white cells, cytokines or complement"}},
    },
    "olive_fruit": {
        "record": {"material_form": "Oleuropein, hydroxytyrosol and tyrosol supplements (sources not specified in the abstract)", "studied_dose_exposure": {},
                   "applicability_decision": "A meta-analysis of 14 studies (594 participants) found oleuropein, hydroxytyrosol and tyrosol supplementation modestly reduced total cholesterol, triglycerides and insulin; the abstract gives no hydroxytyrosol dose threshold."},
        "studies": {"39828996": {"sample_size": 594, "dose": D, "duration": D, "outcome": "total cholesterol, triglycerides and insulin fell modestly"}},
    },
    "jujube": {
        "record": {"population_context": "Adults with insomnia",
                   "studied_dose_exposure": {"values": [2000], "unit": "mg", "basis": "daily_intake"},
                   "applicability_decision": "A randomized crossover feasibility trial in 12 adults with insomnia gave 2 g/day encapsulated Ziziphus spinosa seed granules for 4 weeks; PSQI sleep quality improved versus placebo."},
        "studies": {"33385511": {"study_type": "randomized_crossover_feasibility", "sample_size": 12, "dose": "2 g/day encapsulated Ziziphus spinosa seed granules", "outcome": "PSQI improved versus placebo (p = 0.046); diary sleep improved after ZS; other outcomes did not differ"}},
    },
    "turkey_rhubarb_root": {
        "record": {"studied_dose_exposure": {"values": [12.5, 25], "unit": "mg", "basis": "rhein_daily"},
                   "applicability_decision": "Rhubarb extract dosed at 12.5 or 25 mg rhein per day for 30 days improved stool frequency, consistency and transit questionnaires versus placebo in middle-aged adults (42 completed; full text PMC9738964)."},
        "studies": {"36499011": {"sample_size": 42, "dose": "rhubarb extract providing 12.5 or 25 mg rhein per day", "duration": "30 days", "outcome": "stool frequency, consistency and transit questionnaires improved in both doses versus placebo"}},
    },
    "broccoli_sprout": {
        "record": {"studied_dose_exposure": {},
                   "applicability_decision": "A broccoli sprout beverage providing 600 umol glucoraphanin and 40 umol sulforaphane daily for 12 weeks increased urinary excretion of benzene and acrolein conjugates versus placebo in 291 adults in Qidong, China."},
    },
    "graviola": {
        "record": {"applicability_decision": "The cited laboratory study found annonacin, the main acetogenin of Annona muricata (soursop), toxic to cultured dopaminergic neurons; soursop is suspected of causing an atypical parkinsonism in Guadeloupe. No human efficacy evidence is recorded."},
        "studies": {"14521988": {"study_type": "in_vitro", "sample_size": D, "dose": D, "duration": D, "outcome": "annonacin killed cultured mesencephalic dopaminergic neurons more potently than MPP+; suspected, not established, as a cause of atypical parkinsonism in Guadeloupe"}},
    },
    "puerarin": {
        "record": {"material_form": "Isolated puerarin (kudzu root isoflavone)", "studied_dose_exposure": {"values": [1200], "unit": "mg", "basis": "daily_intake"},
                   "applicability_decision": "1,200 mg/day puerarin for one week reduced beer consumption in a single 1.5-hour drinking session in 10 heavy drinkers (crossover); no vascular outcome was studied."},
        "studies": {"22578529": {"sample_size": 10, "duration": "1 week before a 1.5 h drinking session (crossover)", "outcome": "beers consumed fell from 3.5 to 2.4 versus placebo; smaller sips and slower drinking"}},
    },
    "cocoa": {
        "record": {"effect_direction": "positive_weak", "material_form": "Flavanol-rich chocolate or cocoa products", "studied_dose_exposure": {},
                   "applicability_decision": "A Cochrane review of 20 short-term trials (856 mainly healthy adults; 30-1,080 mg flavanols/day) found a small blood-pressure reduction (SBP -2.77, DBP -2.20 mmHg), seen only against flavanol-free controls and with high heterogeneity; no flavanol dose threshold is established."},
        "studies": {"22895979": {"study_type": "systematic_review_meta_cochrane", "dose": "30-1,080 mg flavanols/day (mean 545 mg) in 3.6-105 g cocoa products", "outcome": "SBP -2.77 and DBP -2.20 mmHg in 2-18 week trials; significant only versus flavanol-free controls", "effect_direction": "positive_weak"}},
    },
    "citrus_bergamot": {
        "record": {"population_context": "Adults with type 2 diabetes and mixed hyperlipidemia", "studied_dose_exposure": {},
                   "applicability_decision": "In a placebo-controlled trial in 60 patients with type 2 diabetes and mixed hyperlipidemia, standard and phytosomal bergamot polyphenolic fraction both lowered fasting glucose, LDL-C and triglycerides and raised HDL-C; the abstract gives no dose or duration."},
        "studies": {"30501605": {"sample_size": 60, "dose": D, "duration": D, "outcome": "fasting glucose, LDL-C and triglycerides fell and HDL-C rose with both BPF formulations versus placebo"}},
    },
    "coleus_forskohlii_root": {"studies": {"16129715": {"outcome": "body fat percentage and fat mass fell and bone mass rose versus placebo; lean body mass only trended up (p = 0.097); free testosterone rose"}}},
    "chitosan": {
        "studies": {"32437302": {"_replace_pmid": "18646097", "study_type": "systematic_review_meta_cochrane", "sample_size": 1219, "dose": D, "duration": "at least 4 weeks",
                                 "outcome": "pooled weight loss -1.7 kg versus placebo, but high-quality trials showed a minimal effect unlikely to be clinically significant", "effect_direction": "null"}},
    },
    "english_ivy": {
        "record": {"effect_direction": "positive_weak", "studied_dose_exposure": {},
                   "applicability_decision": "A systematic review (6 RCTs, 1 CCT, 4 observational studies of ivy leaf mono- or combination preparations) found effects on cough are minimal at best and of uncertain clinical importance, with high risk of bias; no EA 575 dose is established by the abstract."},
        "studies": {"33523253": {"study_type": "systematic_review", "sample_size": D, "dose": D, "duration": D, "outcome": "three RCTs reported faster reduction in cough severity or frequency; effects minimal at best and of uncertain clinical importance", "effect_direction": "positive_weak"}},
    },
    "eps_7630": {
        "record": {"effect_direction": "positive_weak", "studied_dose_exposure": {},
                   "applicability_decision": "A Cochrane review found low-quality evidence that the liquid P. sidoides preparation, but not tablets, relieves acute bronchitis in adults and children, and very low-quality evidence for sinusitis and the common cold; no dose is established by the abstract."},
        "studies": {"24146345": {"study_type": "systematic_review_cochrane", "sample_size": D, "dose": D, "duration": D, "outcome": "liquid preparation effective for most acute-bronchitis outcomes (low-quality evidence), tablets not; very low-quality evidence for sinusitis and common cold", "effect_direction": "positive_weak"}},
    },
    "ginkgo_biloba_leaf": {
        "record": {"applicability_decision": "A meta-analysis of 9 trials (2,561 patients with cognitive impairment or dementia, 22-26 weeks) found EGb 761 improved cognition, daily activities and global change versus placebo, mainly at 240 mg/day."},
        "studies": {"25114079": {"study_type": "systematic_review_meta", "sample_size": 2561, "dose": "EGb 761; benefits mainly at 240 mg/day"}},
    },
    "guggul": {
        "record": {"effect_direction": "negative", "studied_dose_exposure": {"values": [3000, 6000], "unit": "mg", "basis": "daily_intake"},
                   "applicability_decision": "In a double-blind RCT (103 adults with hypercholesterolemia), guggulipid 1,000 mg or 2,000 mg three times daily for 8 weeks raised LDL-C 4-5% versus a 5% fall with placebo, and 6 participants developed a hypersensitivity rash; reviewed unfavorable."},
        "studies": {"12915429": {"dose": "1,000 mg or 2,000 mg guggulipid (2.5% guggulsterones) three times daily", "outcome": "LDL-C rose 4-5% versus a 5% fall with placebo (P = .01 and .006); hypersensitivity rash in 6", "effect_direction": "negative"}},
    },
    "deer_antler_velvet": {
        "record": {"studied_dose_exposure": {},
                   "applicability_decision": "In 38 active men in a 10-week training study, deer antler velvet extract or powder did not change endocrine markers, red cell mass or VO2max; the powder group gained more isokinetic strength and endurance than placebo, a result the authors say may be a type I error; reviewed null for ergogenic effect."},
        "studies": {"14669926": {"dose": D, "outcome": "no endocrine, red-cell or VO2max change; 6RM strength gains equal in all groups; powder gave greater isokinetic knee-extensor strength and endurance than placebo", "effect_direction": "mixed"}},
    },
    "green_tea_leaf": {
        "record": {"effect_direction": "positive_moderate", "material_form": "Green tea beverages or green tea extracts", "studied_dose_exposure": {},
                   "applicability_decision": "A meta-analysis of 14 RCTs (1,136 adults) of green tea beverages or extracts found total cholesterol fell 7.2 mg/dL and LDL-C 2.19 mg/dL, with no HDL effect; results did not depend on catechin dose, so no EGCG threshold is established."},
        "studies": {"21715508": {"study_type": "meta_analysis_rct", "sample_size": 1136, "dose": D, "duration": D, "outcome": "total cholesterol -7.20 mg/dL and LDL-C -2.19 mg/dL; HDL unchanged", "effect_direction": "positive_moderate"}},
    },
    "turkey_tail": {
        "record": {"population_context": "Cancer patients receiving conventional anticancer treatment", "studied_dose_exposure": {},
                   "applicability_decision": "A meta-analysis of 13 trials found Yun Zhi (Coriolus versicolor) added to conventional anticancer treatment gave a 9% absolute reduction in 5-year mortality, mainly in breast, gastric and colorectal cancer. This oncology-adjunct survival evidence does not establish general immune support or a dose."},
        "studies": {"22185453": {"study_type": "systematic_review_meta", "sample_size": D, "dose": D, "duration": D, "outcome": "9% absolute reduction in 5-year mortality with Yun Zhi plus conventional treatment (13 trials)"}},
    },
    "arjuna": {
        "record": {"effect_direction": "positive_weak", "material_form": "Terminalia arjuna bark stem powder", "studied_dose_exposure": {"values": [1500], "unit": "mg", "basis": "daily_intake"},
                   "applicability_decision": "In a non-randomized study, 12 patients with post-MI angina or ischaemic cardiomyopathy took 500 mg arjuna bark powder every 8 hours for 3 months with conventional treatment; LVEF and LV mass improved versus 12 matched controls, while angina frequency fell in both groups."},
        "studies": {"9505018": {"study_type": "controlled_open_study_matched_controls", "sample_size": 24, "dose": "500 mg arjuna bark stem powder every 8 hours", "outcome": "LVEF rose and LV mass fell in the treated group only; angina frequency fell in both groups", "effect_direction": "positive_weak"}},
    },
    "diosmin": {
        "record": {"effect_direction": "positive_weak", "material_form": "Oral phlebotonics (the review's 11 hidrosmine and diosmine trials among others)", "studied_dose_exposure": {},
                   "applicability_decision": "The cited Cochrane review (56 RCTs, 7,690 participants) pooled phlebotonics as a class: oedema probably falls slightly, with little or no effect on quality of life or ulcer healing and slightly more adverse events. The abstract does not report a diosmin- or MPFF-specific dose or result."},
        "studies": {"33141449": {"study_type": "systematic_review_cochrane", "dose": D, "duration": D, "outcome": "phlebotonics probably reduce oedema slightly; little or no difference in quality of life or ulcer healing; slightly more adverse events", "effect_direction": "positive_weak"}},
    },
    "ipriflavone": {
        "studies": {"10479216": {"_replace_pmid": "11255425", "sample_size": 474, "dose": "200 mg three times daily (600 mg/day) with 500 mg/day calcium", "duration": "36 months of treatment (4-year study)",
                                 "outcome": "no effect on BMD, bone resorption markers or vertebral fractures versus placebo; subclinical lymphocytopenia in 13.2%", "effect_direction": "negative"}},
    },
    "nad": {"studies": {"29599478": {"outcome": "NAD+ in peripheral blood mononuclear cells rose about 60% versus placebo (crossover, 30 adults); well tolerated"}}},
    "PII_ARTEMISININ": {
        "record": {"applicability_decision": "A CDC report describes hepatitis temporally associated with a 1-week course of a supplement containing 100 mg artemisinin; causality was not established. WHO recommends artemisinins only within combination therapy for malaria."},
        "studies": {"19680221": {"study_type": "case_report", "outcome": "hepatitis (ALT 898 IU/L) after a 1-week course of a 100 mg artemisinin supplement; the supplement contained no other pharmaceutical actives; causal link not established"}},
    },
    "artemisinin": {
        "record": {"applicability_decision": "A CDC report describes hepatitis temporally associated with a 1-week course of a supplement containing 100 mg artemisinin; causality was not established. WHO recommends artemisinins only within combination therapy for malaria."},
        "studies": {"19680221": {"study_type": "case_report", "outcome": "hepatitis (ALT 898 IU/L) after a 1-week course of a 100 mg artemisinin supplement; the supplement contained no other pharmaceutical actives; causal link not established"}},
    },
    "siberian_rhubarb": {
        "record": {"effect_direction": "positive_moderate", "studied_dose_exposure": {},
                   "applicability_decision": "One enteric-coated ERr 731 tablet daily for 12 weeks reduced Hamilton Anxiety Scale scores (27.5 to 9.4 versus 25.1 to 21.6 with placebo) in 109 perimenopausal women; hot flushes fell alongside anxiety. The abstract gives no mg amount."},
        "studies": {"17213754": {"dose": "one enteric-coated ERr 731 tablet daily", "outcome": "Hamilton Anxiety Scale fell from 27.5 to 9.4 versus 25.1 to 21.6 with placebo; health state and well-being improved", "effect_direction": "positive_moderate"}},
    },
    "african_geranium": {
        "record": {"effect_direction": "positive_weak", "studied_dose_exposure": {},
                   "applicability_decision": "The cited source is an open, uncontrolled observational study (2,099 patients aged 0-93 with acute bronchitis) of an age-dosed EPs 7630 solution for 14 days; it has no placebo arm and establishes no dose."},
        "studies": {"17184981": {"study_type": "open_observational_study", "sample_size": 2099, "dose": "age-dependent EPs 7630 solution", "duration": "14 days", "outcome": "Bronchitis Severity Score fell from 7.1 to 1.0 (uncontrolled); adverse events in 1.2%", "effect_direction": "positive_weak"}},
    },
    "fucoidan": {
        "record": {"population_context": "Adults with asthma on regular treatment",
                   "studied_dose_exposure": {"values": [4400], "unit": "mg", "basis": "daily_intake"},
                   "applicability_decision": "In a 24-week placebo-controlled trial in 20 asthma patients on regular treatment (full text PMC9616827: 4 x 550 mg oligo-fucoidan tablets twice daily), WBC and IL-8 fell and FEV1/FVC rose."},
        "studies": {"36307493": {"sample_size": 20, "dose": "oligo-fucoidan 4 x 550 mg tablets twice daily (4.4 g/day)", "duration": "24 weeks", "outcome": "WBC and IL-8 fell, FEV1/FVC and IFN+ CD4+ cells rose versus placebo"}},
    },
    "lumbrokinase": {
        "record": {"population_context": "Patients after ischaemic stroke on standard treatment", "studied_dose_exposure": {},
                   "applicability_decision": "In a randomized trial with a standard-care control arm (310 ischaemic stroke patients, 1 year), enteric-coated lumbrokinase lowered fibrinogen, carotid IMT and plaque and vascular events (2.08% vs 6.78%); the abstract gives no dose."},
        "studies": {"24229674": {"study_type": "randomized_controlled_standard_care_control", "dose": D, "outcome": "fibrinogen, carotid IMT, plaque volume and vascular events (2.08% vs 6.78%) lower than standard care"}},
    },
    "maqui_berry": {
        "record": {"studied_dose_exposure": {},
                   "applicability_decision": "Delphinol maqui extract (162 mg anthocyanins) three times daily for 4 weeks lowered Ox-LDL and urinary F2-isoprostanes from baseline in 42 healthy, overweight or smoking adults; no difference remained 40 days after stopping."},
        "studies": {"26400431": {"dose": "Delphinol extract providing 162 mg anthocyanins, three times daily", "outcome": "Ox-LDL and urinary 8-iso-PGF2a fell from baseline at 4 weeks; no blood pressure, lipid or anthropometric change"}},
    },
    "capsaicin": {"record": {"studied_dose_exposure": {"values": [2.56], "unit": "mg", "basis": "capsaicin_per_meal"}}},
    "diamine_oxidase": {
        "record": {"studied_dose_exposure": {"values": [0.3], "unit": "mg", "basis": "per_capsule_before_meals"},
                   "applicability_decision": "An open-label pilot in 28 patients with histamine intolerance (DAOSIN capsules, 0.3 mg DAO each, before meals up to three times daily for 4 weeks; full text PMC6859183) reported fewer and milder symptoms, which rose again after stopping; there was no placebo arm."},
        "studies": {"31807350": {"study_type": "open_label_pilot", "sample_size": 28, "dose": "0.3 mg DAO capsule before meals, up to three times daily", "outcome": "all symptom scores improved during DAO and rose again after stopping (no placebo)"}},
    },
    "lactase": {
        "record": {"studied_dose_exposure": {},
                   "applicability_decision": "In a 60-patient RCT of lactose-intolerant adults, tilactase taken 15 minutes before a lactose breath test normalized breath hydrogen and reduced symptoms more than placebo or L. reuteri; the abstract gives no ALU dose."},
        "studies": {"20391953": {"sample_size": 60, "dose": "tilactase 15 minutes before a lactose breath test (amount not given in the abstract)", "outcome": "higher breath-test normalization and lower peak hydrogen and symptom scores than placebo; tilactase more effective than L. reuteri"}},
    },
    "serrapeptase": {
        "record": {"effect_direction": "null",
                   "applicability_decision": "A systematic review of 24 clinical studies found the evidence for serratiopeptidase as an analgesic or anti-inflammatory is based on poor-quality studies and is insufficient to support its use as an analgesic or health supplement; long-term safety data are lacking."},
        "studies": {"23380245": {"sample_size": D, "outcome": "evidence from 24 studies is of poor methodology and insufficient to support analgesic or supplement use; safety data lacking"}},
    },
    "mucuna_pruriens": {"record": {"studied_dose_exposure": {}}},
    "strontium": {"record": {"studied_dose_exposure": {}}},
    "mastic_gum": {"record": {"studied_dose_exposure": {"values": [1050], "unit": "mg", "basis": "daily_intake"}}},
    "d_ribose": {
        "record": {"studied_dose_exposure": {"values": [15000], "unit": "mg", "basis": "daily_intake"},
                   "applicability_decision": "An open-label, uncontrolled pilot gave 5 g D-ribose three times daily (280 g in total) to 41 patients with fibromyalgia or chronic fatigue syndrome; symptom scores improved. No placebo-controlled efficacy or dose threshold is established."},
    },
}

# Second pass over the fields the first patches left untouched (population, material, endpoint
# wording, unverified figures). Merged into SPEC below.
RESIDUAL = {
    "cat_s_claw": {"record": {"population_context": "Patients with knee osteoarthritis"}},
    "l_threonine": {"record": {"population_context": "Healthy adult men (requirement study)"}},
    "boswellia_serrata_resin": {"record": {"material_form": "Boswellia serrata gum resin extract"}},
    "perilla_oil": {"record": {"material_form": "Perilla frutescens seed oil"}},
    "schisandra": {"record": {"material_form": "Schisandra chinensis fruit extract"}},
    "l_tyrosine": {"record": {"population_context": "Healthy adults under acute stress or cognitive demand (a military combat training course in the trial)"},
                   "studies": {"10230711": {"primary_endpoint": "memory and tracking task performance and blood pressure during a combat training course"}}},
    "cayenne_pepper": {"studies": {"23844093": {"sample_size": D, "outcome": "in 25% negative energy balance, 2.56 mg capsaicin per meal counteracted the fall in diet-induced thermogenesis and resting energy expenditure and raised fat oxidation"}}},
    "capsaicin": {"record": {"population_context": "Adults in a 36-hour respiration-chamber study in negative energy balance"},
                  "studies": {"23844093": {"sample_size": D, "outcome": "in 25% negative energy balance, 2.56 mg capsaicin per meal counteracted the fall in diet-induced thermogenesis and resting energy expenditure and raised fat oxidation; blood pressure unchanged"}}},
    "cla": {"record": {"material_form": "Conjugated linoleic acid (isomer mixtures or purified trans-10,cis-12)",
                       "population_context": "Adults in CLA trials; overweight and obese adults in the long-term meta-analysis"}},
    "blueberry": {"studies": {"30999017": {"primary_endpoint": "cognitive performance (memory) and mood"}}},
    "flaxseed": {"record": {"population_context": "Patients with peripheral artery disease (trial) and pooled flaxseed trial populations"}},
    "garcinia_cambogia": {"record": {"material_form": "Garcinia cambogia extract (hydroxycitric acid)"}},
    "green_coffee_bean": {"record": {"material_form": "Green coffee bean extract (chlorogenic acids)"}},
    "apple_cider_vinegar": {"studies": {"14694010": {"study_type": "clinical_study_abstract_unavailable"}}},
    "goldenseal": {"record": {"material_form": "Hydrastis canadensis supplement (preparation not stated in the abstract)"}},
    "hops": {"record": {"population_context": "Patients with non-organic insomnia"}},
    "dgl_deglycyrrhizinated_licorice": {"record": {"population_context": "Adults with functional dyspepsia"}},
    "gotu_kola": {"studies": {"11666126": {"outcome": "laser Doppler flux, transcutaneous PO2/PCO2 and symptom scores improved versus placebo, more at 120 mg/day"}}},
    "omega_6_fatty_acids": {"studies": {"23386268": {"duration": D}}},
    "pygeum": {"record": {"material_form": "Pygeum africanum bark extract preparations (alone or in combination)"}},
    "l_cysteine": {"record": {"population_context": "Adults aged 45-75"}},
    "dong_quai": {"record": {"material_form": "Angelica sinensis (dong quai) preparation (form not stated in the abstract)"}},
    "grape_seed": {"record": {"population_context": "Healthy adults with mildly elevated blood pressure"}},
    "beta_glucan": {"record": {"material_form": "Baker's yeast beta-1,3/1,6-glucan (Wellmune)", "population_context": "Healthy women with moderate psychological stress"},
                    "studies": {"23378458": {"outcome": "fewer reported upper respiratory symptoms than placebo (10% vs 29%); better global mood and vigor"}}},
    "blood_orange_extract": {"record": {"population_context": "Overweight healthy adults"},
                             "studies": {"25588369": {"outcome": "body weight, BMI and waist and hip circumference differed from placebo"}}},
    "siberian_ginseng": {"record": {"population_context": "Recreationally trained men"}},
    "atp": {"record": {"population_context": "Healthy men"}},
    "coffee_fruit": {"studies": {"23312069": {"dose": "single 100 mg dose of whole coffee fruit concentrate powder"}}},
    "neurofactor": {"studies": {"23312069": {"dose": "single 100 mg dose of whole coffee fruit concentrate powder"}}},
    "coffeeberry": {"studies": {"23312069": {"dose": "single 100 mg dose of whole coffee fruit concentrate powder"}}},
    "d_beta_hydroxybutyrate_bhb": {"record": {"population_context": "Trained cyclists"}, "studies": {"29338584": {"study_type": "randomized_crossover"}}},
    "guanidinoacetate": {"record": {"population_context": "Healthy men"}},
    "oregano": {"record": {"material_form": "Emulsified oil of Mediterranean oregano", "population_context": "Adults with stool-positive enteric parasites"},
                "studies": {"10815019": {"outcome": "Entamoeba hartmanni and Endolimax nana disappeared and Blastocystis hominis cleared in 8 cases; GI symptoms improved in 7 of 11 (no control group)"}}},
    "activated_charcoal": {"studies": {"3521259": {"outcome": "lower breath hydrogen and fewer bloating and abdominal-cramp symptoms than placebo in both populations"}}},
    "maitake": {"record": {"material_form": "Maitake (Grifola frondosa) polysaccharide liquid extract"}},
    "celery_seed": {"studies": {"35624525": {"outcome": "SBP fell from 141.2 to 130.0 and DBP from 92.2 to 84.2 mmHg with celery; no change with placebo"}}},
    "horse_chestnut_seed": {"studies": {"15106197": {"outcome": "leg pain and leg volume reduced versus placebo"}}},
    "colostrum": {"record": {"material_form": "Bovine colostrum", "population_context": "Volunteers performing standardized exercise"},
                  "studies": {"21148400": {"outcome": "colostrum truncated the exercise-induced 2.5-fold rise in gut permeability (lactulose/rhamnose) by 80%"}}},
    "algae_oil": {"record": {"population_context": "Healthy adults aged 20-65"}},
    "larch_arabinogalactan": {"record": {"material_form": "Larch (Larix spp.) arabinogalactan extract (ResistAid)"}},
    "jujube": {"record": {"material_form": "Ziziphus spinosa seed granules"}},
    "turkey_rhubarb_root": {"record": {"material_form": "Rhubarb extract dosed by rhein content", "population_context": "Middle-aged adults (95% women) with constipation"}},
    "broccoli_sprout": {"record": {"material_form": "Broccoli sprout beverage (glucoraphanin + sulforaphane)"},
                        "studies": {"24913818": {"dose": "broccoli sprout beverage providing 600 umol glucoraphanin and 40 umol sulforaphane daily"}}},
    "graviola": {"record": {"material_form": "Annona muricata (annonacin, its main acetogenin)", "population_context": "Not a human study: cultured mesencephalic neurons"}},
    "puerarin": {"record": {"population_context": "Heavy-drinking adult volunteers"}},
    "cocoa": {"record": {"population_context": "Mainly healthy adults"}},
    "citrus_bergamot": {"record": {"material_form": "Bergamot polyphenolic fraction (standard and phytosomal formulations)"}},
    "coleus_forskohlii_root": {"record": {"population_context": "Overweight and obese men"}},
    "chitosan": {"record": {"population_context": "Overweight or obese adults"}},
    "english_ivy": {"record": {"material_form": "Ivy leaf (Hedera helix) mono- or combination preparations", "population_context": "Adults and children with acute upper respiratory infection or bronchitis"}},
    "eps_7630": {"record": {"population_context": "Children and adults with acute respiratory infections"}},
    "ginkgo_biloba_leaf": {"record": {"population_context": "Patients with cognitive impairment or dementia"}},
    "guggul": {"record": {"population_context": "Healthy adults with hypercholesterolemia"}},
    "deer_antler_velvet": {"record": {"population_context": "Active men in a 10-week strength-training program"}},
    "green_tea_leaf": {"record": {"population_context": "Adults"}},
    "turkey_tail": {"record": {"material_form": "Yun Zhi (Coriolus versicolor) preparations"}},
    "arjuna": {"record": {"population_context": "Patients with post-MI angina or ischaemic cardiomyopathy"}},
    "diosmin": {"record": {"population_context": "Patients with chronic venous insufficiency"}},
    "ipriflavone": {"record": {"population_context": "Postmenopausal women with low bone mineral density"}},
    "nad": {"record": {"population_context": "Healthy middle-aged and older adults"}},
    "PII_ARTEMISININ": {"record": {"population_context": "One patient (CDC case report)"}, "studies": {"19680221": {"dose": "supplement containing 100 mg artemisinin, 1-week course"}}},
    "artemisinin": {"record": {"population_context": "One patient (CDC case report)"}, "studies": {"19680221": {"dose": "supplement containing 100 mg artemisinin, 1-week course"}}},
    "siberian_rhubarb": {"record": {"population_context": "Perimenopausal women with climacteric complaints and anxiety"}},
    "african_geranium": {"record": {"population_context": "Patients aged 0-93 with acute bronchitis"}},
    "fucoidan": {"record": {"material_form": "Oligo-fucoidan (species not stated in the abstract)"}},
    "maqui_berry": {"record": {"material_form": "Delphinol standardized maqui berry extract", "population_context": "Healthy, overweight and smoking adults aged 45-65"}},
    "diamine_oxidase": {"record": {"population_context": "Patients with histamine intolerance"}},
    "lactase": {"record": {"population_context": "Lactose-intolerant patients"}},
    "mucuna_pruriens": {"record": {"applicability_decision": "Acute 15-30 g whole seed powder Parkinson's trials do not transfer to low-dose dietary supplement extracts without demonstration of clinical equivalence."},
                        "studies": {"15548480": {"dose": "single 15 g and 30 g doses of a mucuna seed powder preparation"}}},
    "strontium": {"studies": {"14749454": {"dose": "2 g/day strontium ranelate"}}},
    "mastic_gum": {"record": {"population_context": "Patients with functional dyspepsia"}},
    "d_ribose": {"record": {"population_context": "Patients with fibromyalgia and/or chronic fatigue syndrome"}, "studies": {"17109576": {"duration": D, "study_type": "open_label_uncontrolled_pilot"}}},
}

for _cid, _patch in RESIDUAL.items():
    _entry = SPEC.setdefault(_cid, {})
    for _part in ("record", "studies"):
        if _part in _patch:
            _merged = _entry.setdefault(_part, {})
            for _key, _value in _patch[_part].items():
                if isinstance(_value, dict) and isinstance(_merged.get(_key), dict):
                    _merged[_key] = {**_merged[_key], **_value}
                else:
                    _merged[_key] = _value
