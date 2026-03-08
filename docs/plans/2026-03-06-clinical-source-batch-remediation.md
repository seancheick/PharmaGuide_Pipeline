# Clinical Source Batch Remediation Implementation Plan

> **For Claude:** REQUIRED SUB-SKILL: Use superpowers:executing-plans to implement this plan task-by-task.

**Goal:** Verify and repair `backed_clinical_studies.json` in small, source-backed batches so every clinical entry carries explicit evidence references without broad unreviewed rewrites.

**Architecture:** Add a lightweight audit that flags entries lacking explicit source breadcrumbs, then remediate the database in small batches of high-impact human-evidence entries. Each batch adds explicit PMIDs or official-source identifiers, fixes any clear evidence-level contradictions, and finishes with targeted regression tests plus integrity checks.

**Tech Stack:** Python, JSON data files, pytest, PubMed/NIH ODS/NCCIH primary sources

---

### Task 1: Lock in the batch audit contract

**Files:**
- Create: `scripts/audit_clinical_sources.py`
- Create: `scripts/tests/test_clinical_source_audit.py`
- Test: `scripts/tests/test_clinical_source_audit.py`

**Step 1: Write the failing test**

Add a regression test that proves the audit flags uncited entries and contradiction-shaped entries.

**Step 2: Run test to verify it fails**

Run: `pytest scripts/tests/test_clinical_source_audit.py -q`

**Step 3: Write minimal implementation**

Implement the audit helper with:
- explicit source token detection
- contradiction heuristics
- JSON report output

**Step 4: Run test to verify it passes**

Run: `pytest scripts/tests/test_clinical_source_audit.py -q`

**Step 5: Commit**

Commit after the audit utility is stable.

### Task 2: Batch 1 high-impact human evidence remediation

**Files:**
- Modify: `scripts/data/backed_clinical_studies.json`
- Modify: `scripts/tests/test_clinical_schema_compat.py`
- Test: `scripts/tests/test_clinical_schema_compat.py`

**Step 1: Write the failing test**

Add a batch-specific regression test asserting explicit source breadcrumbs for the Batch 1 IDs:
- `BRAND_MITOQ`
- `BRAND_SETRIA`
- `BRAND_UCII`
- `BRAND_NIAGEN`
- `BRAND_MENAQ7`
- `BRAND_AFFRON`
- `BRAND_EGB761`
- `BRAND_MITOPURE`

**Step 2: Run test to verify it fails**

Run: `pytest scripts/tests/test_clinical_schema_compat.py -q`

**Step 3: Verify primary sources**

For each batch entry:
- find PubMed or official NIH/NCCIH/brand trial pages
- confirm the entry is accurately classified
- record PMID or official source name directly in `notable_studies`

**Step 4: Patch minimal data changes**

Only change:
- `notable_studies`
- `notes`
- `study_type` or `evidence_level` if the contradiction is clear from primary sources
- `last_updated`

**Step 5: Run tests**

Run:
- `pytest scripts/tests/test_clinical_schema_compat.py scripts/tests/test_db_integrity.py -q`

### Task 3: Publish batch status

**Files:**
- Modify: `docs/plans/2026-03-06-clinical-source-batch-remediation.md`

**Step 1: Run the audit utility**

Run: `python3 scripts/audit_clinical_sources.py`

**Step 2: Record remaining uncited count**

Add a short progress note with:
- batch completed
- entries remediated
- remaining uncited count

**Step 3: Verify broader suite**

Run:
- `pytest scripts/tests/test_clinical_source_audit.py scripts/tests/test_clinical_schema_compat.py scripts/tests/test_db_integrity.py scripts/tests/test_pipeline_integrity.py -q`

**Step 4: Commit**

Commit the batch once the audit and test suite are green.

---

## Progress Notes

- `2026-03-06` Batch 1 completed for:
  - `BRAND_MITOQ`
  - `BRAND_SETRIA`
  - `BRAND_UCII`
  - `BRAND_NIAGEN`
  - `BRAND_MENAQ7`
  - `BRAND_AFFRON`
  - `BRAND_EGB761`
  - `BRAND_MITOPURE`
- Explicit source-breadcrumb backlog after Batch 1: `129` entries remaining in `scripts/data/backed_clinical_studies.json`
- `2026-03-06` Batch 2 completed for:
  - `BRAND_MEGASPORE_BIOTIC`
  - `BRAND_ESTERC`
  - `BRAND_OPTIFERRIN`
  - `BRAND_CIRCADIN`
  - `BRAND_CARNIPURE`
  - `BRAND_PHOSPHATIDYLSERINE`
  - `BRAND_MEDIHERB_SILYMARIN`
  - `INGR_BETA_ALANINE`
- Batch 2 classification corrections:
  - `BRAND_OPTIFERRIN` downgraded from `product-human` to `ingredient-human` and from `tier_1` to `tier_2` because no verifiable brand-specific RCTs were found
  - `BRAND_PHOSPHATIDYLSERINE` downgraded from `branded-rct` to `ingredient-human` because the cited trials support phosphatidylserine ingredient evidence rather than a clearly SerinAid-specific trial set
- Explicit source-breadcrumb backlog after Batch 2: `121` entries remaining in `scripts/data/backed_clinical_studies.json`
- `2026-03-06` Batch 3 completed for:
  - `BRAND_KANEKA_UBIQUINOL`
  - `BRAND_QUATREFOLIC`
  - `BRAND_SEAKELP`
  - `BRAND_COGNIZIN`
  - `BRAND_SUNTHEANINE`
  - `BRAND_LACTOSPORE`
  - `BRAND_OPTISHARP`
  - `BRAND_WELLMUNE`
- Batch 3 source-policy notes:
  - `BRAND_QUATREFOLIC` now carries explicit EFSA-reviewed human-evidence breadcrumbs because the strongest support is regulatory/PK rather than disease-endpoint RCTs
  - `BRAND_SEAKELP` remains `ingredient-human`; no branded-product RCTs were identified
- Explicit source-breadcrumb backlog after Batch 3: `113` entries remaining in `scripts/data/backed_clinical_studies.json`
- `2026-03-06` Batch 4 completed for:
  - `BRAND_PYCNOGENOL`
  - `BRAND_FLORASTOR`
  - `BRAND_ASTAREAL`
  - `BRAND_OPTIMSM`
  - `BRAND_AQUAMIN`
  - `BRAND_CURCUMIN_C3`
  - `BRAND_BIOCELL`
  - `BRAND_RELORA`
- Batch 4 source-policy notes:
  - `BRAND_FLORASTOR` now states the evidence as strain-mapped (`S. boulardii CNCM I-745`) rather than implying a distinct Florastor product-RCT program
  - `BRAND_CURCUMIN_C3` now anchors to the directly indexed rheumatoid-arthritis trial and trims overstated total-trial-count language
  - `BRAND_ASTAREAL` keeps skin-aging support explicit while softening broader eye-strain and exercise claims that were less directly sourced
- Explicit source-breadcrumb backlog after Batch 4: `105` entries remaining in `scripts/data/backed_clinical_studies.json`
- `2026-03-06` Batch 5 completed for:
  - `BRAND_MERIVA`
  - `BRAND_KSM66`
  - `BRAND_SENSORIL`
  - `BRAND_BCM95`
  - `BRAND_THERACURMIN`
  - `BRAND_FORCEVAL`
  - `BRAND_LIFE_EXTENSION_SUPER_BIOCURCUMIN`
  - `BRAND_ZYLOFRESH`
- Batch 5 source-policy notes:
  - `BRAND_SENSORIL` now anchors to one clear Sensoril-labeled PubMed trial and no longer overstates the branded RCT count
  - `BRAND_LIFE_EXTENSION_SUPER_BIOCURCUMIN` was downgraded from `branded-rct` to `ingredient-human` because no PubMed-indexed finished-product trials were identified
  - `BRAND_ZYLOFRESH` now reflects a preclinical-only posture with `animal_study` support after confirming no PubMed-indexed human branded trials
  - `BRAND_FORCEVAL` now records formulary and SmPC support rather than implying product-specific RCT evidence
- Explicit source-breadcrumb backlog after Batch 5: `97` entries remaining in `scripts/data/backed_clinical_studies.json`
- `2026-03-06` Batch 6 completed for:
  - `BRAND_CREAPURE`
  - `BRAND_ALBION_MINERALS`
  - `BRAND_NITROSIGINE`
  - `BRAND_LJ100`
  - `BRAND_SHODEN`
  - `BRAND_TESTOFEN`
  - `BRAND_MAGTEIN`
  - `BRAND_SUNFIBER`
- Batch 6 source-policy notes:
  - `BRAND_ALBION_MINERALS` was downgraded from `branded-rct` to `ingredient-human` because the strongest PubMed support is for chelated mineral forms, not a clearly Albion-branded trial set
  - `BRAND_LJ100` now reflects standardized tongkat-ali extract evidence more conservatively because the indexed trials are not clearly LJ100-labeled
  - `BRAND_SUNFIBER` now treats PHGG as ingredient-level evidence rather than a clearly branded-product RCT corpus
  - `BRAND_CREAPURE` keeps a branded posture but now states that the evidence is source-material validation within broader creatine literature, not unique superiority evidence
- Explicit source-breadcrumb backlog after Batch 6: `89` entries remaining in `scripts/data/backed_clinical_studies.json`
- `2026-03-06` Batch 7 completed for:
  - `BRAND_CYNATINE_HNS`
  - `BRAND_TAMAFLEX`
  - `BRAND_HMB`
  - `BRAND_ZYNAMITE`
  - `BRAND_HEAL9`
  - `BRAND_LUTEMAX_2020`
  - `BRAND_PRIMAVIE_SHILAJIT`
  - `BRAND_PUREWAY_C`
- Batch 7 source-policy notes:
  - `BRAND_HEAL9` no longer overstates sleep-specific support; the strongest indexed evidence is for common-cold outcomes plus a later cognition/stress study
  - `BRAND_LUTEMAX_2020` was downgraded from `branded-rct` to `ingredient-human` because the indexed carotenoid trials do not cleanly support a uniquely branded trial corpus
  - `BRAND_PUREWAY_C` was narrowed from `branded-rct` to `product-human` because the clinical evidence remains limited to a small comparative biomarker study
  - `BRAND_HMB` now cites modern meta-analytic support rather than relying primarily on older landmark trials without explicit source breadcrumbs
- Explicit source-breadcrumb backlog after Batch 7: `81` entries remaining in `scripts/data/backed_clinical_studies.json`
- `2026-03-06` Batch 8 completed for:
  - `INGR_L_CITRULLINE`
  - `INGR_COLLAGEN_PEPTIDES`
  - `INGR_HYALURONIC_ACID`
  - `INGR_GARLIC`
  - `INGR_VITAMIN_K2`
  - `INGR_SELENIUM`
  - `INGR_SAME`
  - `INGR_CAFFEINE`
- Batch 8 source-policy notes:
  - `INGR_L_CITRULLINE` now states the exercise signal as strongest and explicitly notes that blood-pressure and erectile-function evidence are more mixed or combination-based
  - `INGR_SELENIUM` now centers thyroid-autoimmunity evidence and trims broader cancer-prevention framing
  - `INGR_CAFFEINE` now distinguishes strong acute exercise and vigilance evidence from weaker generalized fat-loss claims
  - `INGR_HYALURONIC_ACID` now separates stronger skin evidence from the less consolidated osteoarthritis literature
- Explicit source-breadcrumb backlog after Batch 8: `73` entries remaining in `scripts/data/backed_clinical_studies.json`
- `2026-03-07` Batch 9 completed for:
  - `INGR_BERBERINE_HCL`
  - `INGR_RHODIOLA_3_SALIDROSIDE`
  - `INGR_MAG_GLYCINATE`
  - `INGR_NAC`
  - `INGR_QUERCETIN`
  - `INGR_L_THEANINE`
  - `INGR_BACOPA`
  - `INGR_COQ10`
- Batch 9 source-policy notes:
  - `INGR_MAG_GLYCINATE` now explicitly states that direct glycinate-specific human evidence is limited and that broader magnesium sleep data should not be over-attributed to the glycinate form
  - `INGR_NAC` now centers respiratory and glutathione-related evidence, with psychiatric use described as growing but more heterogeneous
  - `INGR_QUERCETIN` now treats antiviral language more cautiously because much of the human literature uses combination regimens
  - `INGR_COQ10` now grounds heart-failure claims in the indexed trial and meta-analytic evidence without overstating generic ATP/mitochondrial endpoints as universally demonstrated clinical outcomes
- Explicit source-breadcrumb backlog after Batch 9: `65` entries remaining in `scripts/data/backed_clinical_studies.json`
- `2026-03-07` Batch 10 completed for:
  - `INGR_ZINC_PICOLINATE`
  - `INGR_LUTEIN`
  - `INGR_BIOTIN`
  - `INGR_MELATONIN`
  - `INGR_GINSENG`
  - `INGR_RHODIOLA`
  - `INGR_VITAMIN_B12`
  - `INGR_PROBIOTICS`
- Batch 10 source-policy notes:
  - `INGR_ZINC_PICOLINATE` now makes clear that common-cold efficacy is based on zinc acetate or gluconate lozenges, not picolinate-specific evidence
  - `INGR_BIOTIN` now treats the evidence base as deficiency- and combination-product-weighted rather than implying robust standalone RCT support in replete adults
  - `INGR_VITAMIN_B12` now centers deficiency correction and avoids overstating general cognition or fatigue benefits in non-deficient populations
  - `INGR_PROBIOTICS` now states the evidence as strain-specific rather than a class-wide guarantee for any Lactobacillus/Bifidobacterium blend
- Explicit source-breadcrumb backlog after Batch 10: `57` entries remaining in `scripts/data/backed_clinical_studies.json`
- `2026-03-07` Batch 11 completed for:
  - `INGR_TURMERIC`
  - `INGR_VITAMIN_C`
  - `INGR_GINGER`
  - `INGR_ASHWAGANDHA`
  - `INGR_GREEN_TEA`
  - `INGR_LION_MANE`
  - `INGR_GLYCINE`
  - `INGR_TART_CHERRY`
- Batch 11 source-policy notes:
  - `INGR_TURMERIC` now ties anti-inflammatory and osteoarthritis claims to actual meta-analytic evidence while explicitly noting formulation dependence
  - `INGR_VITAMIN_C` now centers modest cold-duration benefit rather than overbroad prevention language
  - `INGR_LION_MANE`, `INGR_GLYCINE`, and `INGR_TART_CHERRY` now describe their human evidence as promising but limited or mixed instead of overstating certainty
  - `INGR_GREEN_TEA` now frames weight and fat-oxidation benefits as statistically real but clinically modest
- Explicit source-breadcrumb backlog after Batch 11: `49` entries remaining in `scripts/data/backed_clinical_studies.json`
- `2026-03-07` Batch 12 completed for:
  - `INGR_ELDERBERRY`
  - `INGR_FENUGREEK`
  - `INGR_BITTER_MELON`
  - `INGR_ALPHA_LIPOIC_ACID`
  - `INGR_RED_YEAST_RICE`
  - `INGR_GLUCOSAMINE_SULFATE`
  - `INGR_CINNAMON_EXTRACT`
  - `INGR_DIGESTIVE_ENZYMES`
- Batch 12 source-policy notes:
  - `INGR_ELDERBERRY` now treats the respiratory-illness evidence as small and formulation-specific rather than strongly antiviral or oseltamivir-like
  - `INGR_BITTER_MELON` now explicitly states that pooled evidence is mixed and low-certainty
  - `INGR_RED_YEAST_RICE` now ties efficacy and safety interpretation directly to monacolin K's statin-like mechanism
  - `INGR_DIGESTIVE_ENZYMES` now distinguishes strong pancreatic-insufficiency evidence from weak evidence for general OTC digestive-support claims
- Explicit source-breadcrumb backlog after Batch 12: `41` entries remaining in `scripts/data/backed_clinical_studies.json`
- `2026-03-07` Batch 13 completed for:
  - `INGR_INULIN`
  - `INGR_IRON_BISGLYCINATE`
  - `INGR_FOLATE_MTHF`
  - `INGR_VALERIAN`
  - `INGR_PASSIONFLOWER`
  - `INGR_LEMON_BALM`
  - `STRAIN_REUTERI_PRODENTIS`
  - `INGR_VITAMIN_A_BETA_CAROTENE`
- Batch 13 source-policy notes:
  - `INGR_FOLATE_MTHF` now states the evidence as primarily biomarker and comparative-bioavailability support rather than hard superiority on clinical endpoints
  - `STRAIN_REUTERI_PRODENTIS` now keeps the periodontal signal but trims marketing-style language about scale and certainty
  - `INGR_VITAMIN_A_BETA_CAROTENE` now frames evidence around AREDS-type targeted populations and deficiency correction instead of blanket supplementation
  - `INGR_VALERIAN`, `INGR_PASSIONFLOWER`, and `INGR_LEMON_BALM` now present their sleep/anxiety evidence as promising but heterogeneous rather than uniformly established
- Explicit source-breadcrumb backlog after Batch 13: `33` entries remaining in `scripts/data/backed_clinical_studies.json`
- `2026-03-07` Batch 14 completed for:
  - `PRECLIN_FISETIN`
  - `PRECLIN_AKG`
  - `PRECLIN_QUERCETIN_PHYTOSOME`
  - `PRECLIN_NADH`
  - `PRECLIN_ASTAXANTHIN_GENERIC`
  - `PRECLIN_SULFORAPHANE`
  - `PRECLIN_PTEROSTILBENE`
  - `PRECLIN_ARTICHOKE`
- Batch 14 source-policy notes:
  - `PRECLIN_FISETIN` remains `preclinical`; the published human record is still limited to a small uncontrolled pilot, with the stronger placebo-controlled programs still ongoing on ClinicalTrials.gov
  - `PRECLIN_AKG` remains `preclinical`; the indexed human literature is protocol- and feasibility-level rather than completed randomized efficacy evidence
  - `PRECLIN_QUERCETIN_PHYTOSOME` was upgraded to `ingredient-human` and `tier_2` because formulation-specific human RCT evidence exists, but the notes now make clear that the strongest signal is bioavailability plus narrow indication-specific outcomes
  - `PRECLIN_NADH` now states standalone evidence more conservatively and distinguishes it from the larger CoQ10-plus-NADH combination trials
  - `PRECLIN_ASTAXANTHIN_GENERIC`, `PRECLIN_SULFORAPHANE`, `PRECLIN_PTEROSTILBENE`, and `PRECLIN_ARTICHOKE` now anchor their upgraded human-evidence status to explicit PMIDs while trimming overstated certainty where the pooled literature is heterogeneous or moderate in effect size
- Explicit source-breadcrumb backlog after Batch 14: `25` entries remaining in `scripts/data/backed_clinical_studies.json`
- `2026-03-07` Batch 15 completed for:
  - `PRECLIN_DGL`
  - `PRECLIN_ZINC_CARNOSINE`
  - `PRECLIN_BOSWELLIA`
  - `PRECLIN_HUPERZINE_A`
  - `PRECLIN_CORDYCEPS`
  - `PRECLIN_BETAINE_HCL`
  - `PRECLIN_SAFFRON`
  - `PRECLIN_CHROMIUM_PICOLINATE`
- Batch 15 source-policy notes:
  - `PRECLIN_DGL` now distinguishes the stronger modern GutGard evidence from older classic DGL ulcer studies, rather than treating all DGL evidence as equally strong
  - `PRECLIN_ZINC_CARNOSINE` now frames the evidence as gastric-mucosal and adjunctive-ulcer/H. pylori support instead of overbroad generic gut-barrier certainty
  - `PRECLIN_BETAINE_HCL` was upgraded from `preclinical` to cautious `ingredient-human` status because human gastric re-acidification studies exist, even though direct digestive-symptom efficacy trials still do not
  - `PRECLIN_HUPERZINE_A`, `PRECLIN_CORDYCEPS`, `PRECLIN_SAFFRON`, and `PRECLIN_CHROMIUM_PICOLINATE` now anchor their human-evidence posture to explicit PMIDs while keeping the notes honest about trial quality, heterogeneity, or effect-size limits
- Explicit source-breadcrumb backlog after Batch 15: `17` entries remaining in `scripts/data/backed_clinical_studies.json`
- `2026-03-07` Batch 16 completed for:
  - `PRECLIN_NMN`
  - `PRECLIN_PQQ`
  - `PRECLIN_RESVERATROL`
  - `PRECLIN_CURCUMIN_GENERIC`
  - `PRECLIN_BERBERINE_GENERIC`
  - `INGR_MAGNESIUM_GENERIC`
  - `INGR_VITAMIN_B6`
  - `INGR_THIAMINE_B1`
- Batch 16 source-policy notes:
  - `PRECLIN_NMN` now states the main signal accurately as NAD-biomarker elevation with mixed or still-emerging functional outcome evidence
  - `PRECLIN_PQQ` remains cautiously positive but now makes clear that the best human data are small cognition-focused trials, including one combination-formula study rather than a large standalone replication base
  - `PRECLIN_RESVERATROL`, `PRECLIN_CURCUMIN_GENERIC`, and `PRECLIN_BERBERINE_GENERIC` now anchor their large human literatures to explicit PMIDs while trimming overbroad certainty where meta-analytic heterogeneity remains substantial
  - `INGR_MAGNESIUM_GENERIC`, `INGR_VITAMIN_B6`, and `INGR_THIAMINE_B1` now carry NIH ODS anchors plus representative randomized/meta-analytic human evidence, with the notes tightened around indication-specific use and dose-related safety limits
- Explicit source-breadcrumb backlog after Batch 16: `9` entries remaining in `scripts/data/backed_clinical_studies.json`
- `2026-03-07` Batch 17 completed for:
  - `INGR_PANTOTHENIC_ACID_B5`
  - `INGR_RIBOFLAVIN_B2`
  - `INGR_POTASSIUM`
  - `INGR_MANGANESE`
  - `INGR_PHOSPHORUS`
  - `INGR_BORON`
  - `INGR_HONEY`
  - `PRECLIN_DIM`
  - `PRECLIN_SHILAJIT_GENERIC`
- Batch 17 source-policy notes:
  - `INGR_PANTOTHENIC_ACID_B5`, `INGR_MANGANESE`, and `INGR_PHOSPHORUS` now anchor mainly to NIH ODS essentiality/deficiency evidence and avoid implying strong stand-alone supplement efficacy that the literature does not support
  - `INGR_RIBOFLAVIN_B2`, `INGR_POTASSIUM`, and `INGR_HONEY` now carry explicit human efficacy references for their best-supported indications: migraine prevention, blood-pressure reduction, and acute cough/URTI symptom relief
  - `INGR_BORON` now states the evidence as small and biomarker-focused, with both positive calcium-fructoborate trials and older null athletic-performance data
  - `PRECLIN_DIM` and `PRECLIN_SHILAJIT_GENERIC` now cite the actual early human trial base rather than vague “early human” or “mechanistic” wording, while keeping the interpretation conservative
- Explicit source-breadcrumb backlog after Batch 17: `0` entries remaining in `scripts/data/backed_clinical_studies.json`
