# PMID Citation Audit — 2026-04-30 (post-triage)

Audit pass on all 213 unique PMID URLs in `scripts/data/ingredient_interaction_rules.json` via NCBI E-utils content verification, with manual per-PMID classification.

## Summary

- **126 PMIDs** auto-matched their topic ✓
- **32 PMIDs** flagged by auto-audit but manually classified KEEP (paper IS topic-relevant; my keyword set was too narrow)
- **48 PMIDs** classified STRIP (real hallucinations). Stripped from data.
- **7 PMIDs** classified REVIEW (clinician judgment needed)

---

## REVIEW Cases (clinician judgment needed)

### PMID `10479204` — Liu S 1999

**Cited at:** `psyllium` × `cond:diabetes`

**Title:** Whole-grain consumption and risk of coronary heart disease: results from the Nurses' Health Study.

**Why flagged:** Liu 1999 whole-grain CHD; tangential to psyllium-diabetes (psyllium is fiber, fiber-glucose plausible link). Need clinician to decide if topic-relevant or strip.

**Abstract excerpt:** Although current dietary guidelines for Americans recommend increased intake of grain products to prevent coronary heart disease (CHD), epidemiologic data relating whole-grain intake to the risk of CHD are sparse. Our objective was to evaluate whether high whole-grain intake reduces risk of CHD in w

**Decision:** ☐ Keep ☐ Strip ☐ Replace with: ___________

---

### PMID `19146936` — Andrade-Cetto A 2009

**Cited at:** `rue` × `cond:pregnancy`; `rue` × `pl`

**Title:** Ethnobotanical study of the medicinal plants from Tlanchinol, Hidalgo, M&#xe9;xico.

**Why flagged:** Andrade-Cetto 2009 — Mexican ethnobotany. Could mention rue if traditional medicine; tangential. Clinician decide.

**Abstract excerpt:** The people in Mexico still depend upon the use of medicinal plants to treat simple health problems, including those who live in regions like Tlanchinol Hidalgo, where it is still possible to find people who speak the pre-Hispanic Nahua language. This area is surrounded by rain forest, which is more 

**Decision:** ☐ Keep ☐ Strip ☐ Replace with: ___________

---

### PMID `23946031` — Dumont Z 2013

**Cited at:** `glucosamine` × `anticoagulants`

**Title:** Warfarin: its highs and lows.

**Why flagged:** Dumont 2013 — warfarin highs and lows. Generic; may discuss glucosamine. Clinician verify.

**Decision:** ☐ Keep ☐ Strip ☐ Replace with: ___________

---

### PMID `24472406` — Markert C 2014

**Cited at:** `st_johns_wort` × `cond:hypertension`

**Title:** Influence of St. John's wort on the steady-state pharmacokinetics and metabolism of bosentan.

**Why flagged:** Markert 2014 — SJW × bosentan PK. Bosentan is for pulmonary HTN. Cited at SJW × hypertension condition. Tangential.

**Abstract excerpt:** We assessed the effect of St. John's wort (SJW) on bosentan pharmacokinetics at steady-state in different CYP2C9 genotypes in healthy volunteers. Nine healthy extensive metabolizers of CYP2C9 and 4 poor metabolizers received therapeutic doses of bosentan (125 mg q.d. on study day 1; 62.5 mg b.i.d. o

**Decision:** ☐ Keep ☐ Strip ☐ Replace with: ___________

---

### PMID `30980598` — Dhariwala MY 2019

**Cited at:** `saw_palmetto` × `cond:ttc`

**Title:** An overview of herbal alternatives in androgenetic alopecia.

**Why flagged:** Dhariwala 2019 — herbal alternatives androgenetic alopecia. Saw palmetto IS used for AGA (anti-androgenic). Cited at TTC; saw palmetto's anti-androgenic effects could affect TTC. Tangential.

**Abstract excerpt:** The second most common alopecia-Androgenetic alopecia (AGA)-occurs due to hormonal imbalance. Dihydrotestosterone (DHT) an androgenic hormone is a sex steroid, produced in the gonads. The target sites of DHT are similar to that of testosterone, and it attaches easily remaining bound for 53&#xa0;minu

**Decision:** ☐ Keep ☐ Strip ☐ Replace with: ___________

---

### PMID `32486167` — Cozzolino M 2020

**Cited at:** `vitamin_d` × `cond:bleeding_disorders`

**Title:** Current Therapy in CKD Patients Can Affect Vitamin K Status.

**Why flagged:** Cozzolino 2020 — CKD therapy affects vitamin K status. Cited at vitamin_d × bleeding; the paper is about vit K. Tangential.

**Abstract excerpt:** Chronic kidney disease (CKD) patients have a higher risk of cardiovascular (CVD) morbidity and mortality compared to the general population. The links between CKD and CVD are not fully elucidated but encompass both traditional and uremic-related risk factors. The term CKD-mineral and bone disorder (

**Decision:** ☐ Keep ☐ Strip ☐ Replace with: ___________

---

### PMID `8983860` — Palareti G 1996

**Cited at:** `vitamin_d` × `anticoagulants`

**Title:** Warfarin withdrawal. Pharmacokinetic-pharmacodynamic considerations.

**Why flagged:** Palareti 1996 — warfarin withdrawal pharmacokinetics. Generic warfarin paper; may not specifically discuss vitamin D.

**Abstract excerpt:** Warfarin, like all the 4-hydroxycoumarin compounds, has an asymmetric carbon atom. The clinically available warfarin preparations consist of a racemic mixture of equal amounts of 2 distinct S and R isomers, the former being 4-times more potent as anticoagulant and more susceptible to drug interactio

**Decision:** ☐ Keep ☐ Strip ☐ Replace with: ___________

---

## KEEP Decisions (transparency reference)

| PMID | Author Year | Reason kept |
|---|---|---|
| 10902065 | Heck AM 2000 | Heck 2000 — direct review of alternative therapies × warfarin. Saw palmetto, omega-3, evening primrose all covered. |
| 12192964 | Gabay MP 2002 | Gabay 2002 — galactogogue medications. Fenugreek IS a known galactogogue. Direct match. |
| 12579996 | Levine PH 2003 | Levine 2003 — hepatic stellate-cell lipidosis from HYPERVITAMINOSIS A → cirrhosis. Direct vitamin A liver toxicity match |
| 12609386 | Spinella M 2001 | Spinella 2001 — herbal medicines and epilepsy. Guarana as stimulant lowers seizure threshold; topic-relevant. |
| 15072439 | Zhou S 2004 | Zhou 2004 — herbal P-glycoprotein modulation. Milk thistle IS a known P-gp modulator. |
| 15133406 | Wilburn AJ 2004 | Wilburn 2004 — natural treatment of HTN. Garlic and L-arginine both covered. |
| 16997936 | Barad D 2006 | Barad 2006 — DHEA effect on oocyte/embryo IVF. Direct match (DHEA + fertility/TTC). |
| 18090773 | Beckert BW 2007 | Beckert 2007 — herbal medicines on platelet function. Saw palmetto bleeding context covered. |
| 18989760 | Dong GC 2009 | Dong 2009 — cynarin from ECHINACEA blocks CD28 (immunosuppressive). Direct match. |
| 21155624 | Kidd PM 2010 | Kidd 2010 — Vitamins D and K cardiovascular pleiotropic. Vitamin D + K (anticoagulant context) covered. |
| 21676849 | Moaddeb J 2011 | Moaddeb 2011 — hypertensive urgency from Xenadrine EFX (stimulant supplement). Guarana = caffeine-stimulant similar prof |
| 21726792 | Ritchie MR 2011 | Ritchie 2011 — Echinaforce treatment on blood cells. Direct echinacea autoimmune match. |
| 23397375 | Hansen DK 2013 | Hansen 2013 — Citrus aurantium cardiovascular toxicity. RISK_BITTER_ORANGE = Citrus aurantium. Direct match. |
| 23653088 | Sarris J 2013 | Sarris 2013 — plant-based medicines for anxiety. Gotu kola covered as anxiolytic. |
| 25296654 | Jayaprakasan K 2014 | Jayaprakasan 2014 — DHEA ovarian aging RCT. Direct DHEA + TTC match. |
| 26949700 | Wang CZ 2015 | Wang 2015 — dietary supplements coagulation in surgery. Direct chondroitin surgery context. |
| 27402097 | Brown AC 2017 | Brown 2017 — liver toxicity herbs/dietary supplements case reports. Niacin liver toxicity covered. |
| 28617146 | Othong R 2017 | Othong 2017 — Thai folk medicine hypokalemia + HTN. Same mechanism as licorice (mineralocorticoid-like). |
| 28981338 | Brown AC 2018 | Brown 2018 — heart toxicity herbs/dietary supplements case reports. Licorice heart toxicity covered. |
| 29806946 | Weiss KH 2018 | Weiss 2018 — WTX101 Wilson disease (copper accumulation in liver). Direct copper liver match. |
| 29953177 | Bedi O 2016 | Bedi 2016 — herbal hepatoprotection/hepatotoxicity. Andrographis liver covered. |
| 31927673 | Song Y 2020 | Song 2020 — microbiota in hematologic malignancies. Probiotic-immunosuppressed transplant context relevant. |
| 32478963 | Tan CSS 2021 | Tan 2021 — warfarin × food/herbal/supplements systematic review. Chamomile anticoagulant covered. |
| 33091497 | Kolodziejczyk-Czepas J 2021 | Kolodziejczyk-Czepas 2021 — Uncaria tomentosa (cat's claw) antiplatelet. Direct match. |
| 33584551 | Miccoli P 2020 | Miccoli 2020 — levothyroxine therapy in thyroidectomized patients. Thyroid med interactions context relevant. |
| 33676282 | Martinefski MR 2021 | Martinefski 2021 — CoQ10 deficiency in hereditary hemochromatosis (iron overload → liver). Iron-liver context relevant. |
| 34036101 | Dai C 2021 | Dai 2021 — homocysteine and pregnancy. B12 affects homocysteine. Direct match. |
| 36017706 | Dal Forno GO 2023 | Dal Forno 2023 — soy isoflavones (genistein) → subclinical hypothyroidism. Direct match. |
| 36992844 | Anushree A 2023 | Anushree 2023 — generalized dystonia Wilson disease (copper). Direct copper liver match. |
| 37988295 | Moran C 2024 | Moran 2024 — raised thyroid hormones with nonsuppressed TSH. Biotin's interference with thyroid immunoassays is well-doc |
| 41717291 | Delgadillo F 2026 | Delgadillo 2026 — Hashimoto's thyroiditis (autoimmune). Vitamin D × autoimmune and selenium × thyroid topic-relevant. |
| 7906886 | Wolfman C 1994 | Wolfman 1994 — chrysin (a passionflower flavonoid) at benzodiazepine receptors. Direct match. |

## STRIP Decisions (already applied)

| PMID | Author Year | Cited at | Why stripped |
|---|---|---|---|
| 10940988 | Zhu XJ 2000 | senna, senna | Zhu 2000 — methylthio radical chemistry. Completely unrelated to senna/cascara. |
| 11176247 | Sawyer MH 2001 | vanadyl_sulfate, vanadyl_sulfate | Sawyer 2001 — enterovirus diagnosis. Unrelated to vanadyl sulfate/diabetes. |
| 11302778 | MacKay D 2001 | ginkgo | MacKay 2001 — hemorrhoid/varicose vein treatment. Unrelated to ginkgo bleeding. |
| 11507730 | Koshy AS 2001 | forskolin, forskolin | Koshy 2001 — Garcinia cambogia flavonoids. Wrong herb (forskolin = Coleus, not G |
| 11869656 | Shaw K 2002 | l_tyrosine, l_tyrosine | Shaw 2002 — Tryptophan/5-HTP for depression. Wrong amino acid (cited at l_tyrosi |
| 12065157 | Dhawan K 2002 | quercetin, quercetin | Dhawan 2002 — Passiflora benzoflavone. Wrong herb (cited at quercetin). |
| 12162764 | Wenig BL 2002 | bacopa, bacopa | Wenig 2002 — head/neck cancer chemo. Unrelated to bacopa. |
| 12197782 | Kidd PM 2002 | white_willow_bark, white_willow_bark | Kidd 2002 — autism integrative medicine. Unrelated to white willow bark. |
| 12495553 | Kressmann S 2002 | rue, rue | Kressmann 2002 — Ginkgo bioavailability. Wrong herb (cited at rue). |
| 15070161 | Somova LI 2004 | blue_cohosh | Somova 2004 — olive triterpenoids cardiotonic. Unrelated to blue cohosh. |
| 15266021 | Huang H 2004 | ginseng | Huang 2004 — p38 MAPK iNOS. Cell signaling, unrelated to ginseng surgery. |
| 15470137 | Hasegawa H 2004 | acetyl_l_carnitine, acetyl_l_carnitine | Hasegawa 2004 — neocortex laminar patterning. Unrelated to acetyl-L-carnitine. |
| 15764334 | Caldas ED 2004 | ginkgo | Caldas 2004 — pesticide residues in Brazil. Unrelated to ginkgo bleeding. |
| 15857459 | Paulsen E 2005 | cordyceps, cordyceps | Paulsen 2005 — Aloe vera psoriasis trial. Wrong herb (cited at cordyceps). |
| 16112024 | Guzman VB 2005 | icariin, icariin | Guzman 2005 — CD28 polymorphism Brazilian populations. Unrelated to icariin. |
| 16236036 | Holmes G 2005 | mugwort, mugwort | Holmes 2005 — insulin aspart pharmacokinetics. Unrelated to mugwort. |
| 16243026 | Wilkie TM 2005 | resveratrol, resveratrol | Wilkie 2005 — Galpha/RGS proteins cell biology. Unrelated to resveratrol. |
| 16894152 | Zilhão J 2006 | l_arginine | Zilhão 2006 — Aurignacian/Neandertals archaeology. Unrelated to L-arginine heart |
| 16923387 | Ogura Y 2006 | cascara_sagrada | Ogura 2006 — inflammasome immunology. Unrelated to cascara liver. |
| 17301931 | Andersen K 2007 | manganese | Andersen 2007 — Wilson disease imaging. Wilson's = copper not manganese; cited a |
| 17490952 | Maintz L 2007 | dha, dha | Maintz 2007 — histamine intolerance. Unrelated to DHA bleeding. |
| 17569230 | Monté CP 2007 | milk_thistle, milk_thistle | Monté 2007 — ictal bradycardia syndrome neurology. Unrelated to milk thistle. |
| 18381752 | ?  | vitamin_b3_niacin, vitamin_b3_niacin | Title not retrieved by E-utils; cannot verify content. Strip per critical_no_hal |
| 20109089 | Scollie S 2010 | lions_mane | Scollie 2010 — NAL-NL1 hearing aid prescription. Unrelated to lions mane. |
| 21537493 | Stohs SJ 2011 | black_seed_oil, black_seed_oil | Stohs 2011 — synephrine + bioflavonoids. Wrong herb (cited at black seed oil). |
| 21538168 | Padwal R 2011 | dandelion | Padwal 2011 — bariatric surgery review. Unrelated to dandelion kidney. |
| 22566672 | Raubenheimer D 2012 | butterbur | Raubenheimer 2012 — conservation physiology nutritional ecology. Unrelated to bu |
| 23098397 | Kuznetsov VA 2012 | stinging_nettle, stinging_nettle | Kuznetsov 2012 — heart failure biomarkers ICDs. Unrelated to stinging nettle. |
| 24130475 | Suderman R 2013 | olive_leaf, olive_leaf | Suderman 2013 — MAPK signaling cell biology. Unrelated to olive leaf. |
| 24378636 | Cheng YJ 2013 | fenugreek, fenugreek | Cheng 2013 — salt-stress potato plants agriculture. Unrelated to fenugreek. |
| 24573804 | Stojanovska N 2014 | huperzine_a, huperzine_a | Stojanovska 2014 — amphetamine forensic analysis. Unrelated to huperzine A. |
| 25230580 | Yang Y 2014 | ginger, ginger | Yang 2014 — melatonin myocardial. Wrong subject (cited at ginger). |
| 25630523 | Meister S 2015 | feverfew, feverfew | Meister 2015 — FCGR2B promoter rheumatoid arthritis genetics. Unrelated to fever |
| 25747286 | Pope L 2015 | magnesium | Pope 2015 — food TV BMI. Unrelated to magnesium kidney. |
| 26312811 | ?  | berberine_supplement, berberine_supplement | Title not retrieved; cannot verify content. Strip per integrity rule. |
| 27885969 | Bateman RM 2016 | probiotics | Bateman 2016 — symposium proceedings on intensive care/sepsis. Conference abstra |
| 28133296 | Murayama M 2016 | licorice, licorice_root | Murayama 2016 — colonic obstruction stenting. Unrelated to licorice. |
| 29136493 | Powell KE 2017 | fish_oil, fish_oil | Powell 2017 — childhood obesity policy modeling. Unrelated to fish oil bleeding. |
| 30417375 | Najafi M 2019 | BANNED_CBD_US, BANNED_CBD_US | Najafi 2019 — cancer stem cells oncology. Unrelated to CBD anticonvulsants. |
| 32444096 | Zijlstra JG 2020 | chinese_skullcap, chinese_skullcap | Zijlstra 2020 — AKI acronym editorial. Unrelated to chinese skullcap. |
| 32750587 | Arshad H 2020 | bitter_melon | Arshad 2020 — Red-S3B textile dye soil microbes. Unrelated to bitter melon. |
| 34853508 | ? 2021 | alpha_lipoic_acid | Erratum on hearing protection electrode array. Completely unrelated to alpha-lip |
| 36220193 | Delorme M 2023 | aloe_vera, aloe_vera | Delorme 2023 — noninvasive ventilation device technology. Unrelated to aloe vera |
| 36771367 | Khongrum J 2023 | fiber, fiber | Khongrum 2023 — Lactobacillus paracasei cholesterol. Wrong subject (cited at fib |
| 8247568 | Amble FR 1993 | alpha_gpc | Amble 1993 — middle ear adenoma surgery. Unrelated to alpha-GPC. |
| 8298118 | Antes G 1993 | nac, nac | Antes 1993 — turning maneuver for intubation. Unrelated to NAC. |
| 9161097 | Kałuza J 1997 | pygeum | Kałuza 1997 — paraneoplastic syndrome testicular seminoma. Unrelated to pygeum. |
| 9600579 | Bagdy G 1998 | blue_cohosh | Bagdy 1998 — oxytocin/TSH endocrinology. Unrelated to blue cohosh pregnancy. |