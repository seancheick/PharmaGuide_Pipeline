# Synergy Cluster Deep Audit (2026-03-04)

## Scope
- File audited: `scripts/data/synergy_cluster.json`
- Runtime consumers audited:
  - `scripts/enrich_supplements_v3.py` (`_collect_synergy_data`, `_project_scoring_fields`)
  - `scripts/score_supplements.py` (`_synergy_cluster_qualified`)
- Goal: validate contract integrity, matching precision, and evidence quality for A5c synergy bonus.

## What was fixed in code
1. **Scoring fallback alignment**
   - `score_supplements.py` fallback no longer grants A5c when a cluster has no dose-checkable ingredients.
   - This now matches enrichment projection behavior.
2. **Schema/contract enforcement upgraded**
   - `db_integrity_sanity_check.py` now enforces:
     - `evidence_tier` is `int` and in `{1,2,3}`
     - `synergy_mechanism` is `str|null`
     - every `min_effective_doses` key exists in `ingredients`
     - every dose is finite and `> 0`
3. **Data contract bug fix**
   - Added missing `zinc` aliases to clusters:
     - `respiratory_health_lung_support`
     - `prostate_health`
4. **Explainability fields enabled**
   - Added `note` and `sources` to all 54 clusters.
   - Seeded primary-source citations for 8 high-impact clusters in phase 1.
   - Enricher now propagates `note` + `sources` into matched cluster outputs.
5. **User-facing note quality + precision cleanup**
   - Replaced generic note text with explicit bonus-rule explanations and tier labels.
   - Added missing min-dose anchors for key ingredients in sourced clusters (sleep/eye/iron).
   - Removed several noisy ingredients likely to create false positives (`cbd`, `anthocyanins`, `osteocalcin`).
6. **Phase-3 citation cleanup**
   - Replaced query-placeholder references with curated source-page links.
   - Source coverage remains `54/54` with zero query-placeholder URLs.
   - Source typing is now constrained to `pubmed`, `nih_ods`, `fda`, `nccih`.

## Runtime behavior observed on current sample outputs
- Dataset examined: 6 enriched batches, 1,186 products.
- `synergy_cluster_qualified = true`: **389 products (32.8%)**.
- Most frequent qualifying clusters (first qualifying cluster per product):
  - `magnesium_nervous_system` (70)
  - `sleep_stack` (69)
  - `immune_defense` (51)
  - `hair_skin_nutrition` (33)
  - `bone_health` (26)

## Evidence validation (primary sources)

### Strongly supported pair-level anchors
1. **Curcumin + piperine (bioavailability)**
   - Supported by human study showing increased curcumin bioavailability with piperine.
   - Source: PubMed PMID 9619120
2. **Iron + vitamin C (absorption support)**
   - NIH ODS states vitamin C can improve nonheme iron absorption.
   - Source: NIH ODS Iron Fact Sheet
3. **Calcium + vitamin D (bone pathway)**
   - NIH ODS documents vitamin D promoting calcium absorption and bone mineralization.
   - Source: NIH ODS Vitamin D Fact Sheet
4. **Lutein + zeaxanthin (AREDS2 eye formula)**
   - AREDS2 reports support carotenoid-based formulation benefit in AMD context.
   - Source: PubMed PMID 23644932

### Mixed or limited evidence for broad stacks
1. **Glucosamine/chondroitin-containing clusters**
   - NCCIH notes mixed evidence; benefit signal is not uniformly strong.
   - Source: NCCIH Glucosamine and Chondroitin page
2. **Magnesium + B6 stress/sleep style stacks**
   - RCT signal exists in stressed subgroup, but not strong universal evidence for broad multi-ingredient stack synergy.
   - Source: PubMed PMID 30807974
3. **Sleep multi-stack (melatonin/magnesium/zinc + many extras)**
   - Small trial evidence exists for specific combo in older adults, but not for a 20+ ingredient generalized “sleep stack”.
   - Source: PubMed PMID 34959948

### Regulatory checks relevant to claim framing
1. **FDA supplement oversight context**
   - Supplements are not FDA pre-approved before market.
   - Source: FDA “Questions and Answers on Dietary Supplements”
2. **Vitamin K2 osteoporosis claim status**
   - FDA denied a K2-osteoporosis health-claim notification.
   - Source: FDA constituent update on K2 claim denial

## Accuracy risks still open
1. Source coverage is complete (`54/54` non-empty `sources`), but some clusters still rely on broad context pages rather than cluster-specific trial papers.
2. Many tier-1 clusters are broad formula archetypes; pair-level evidence exists, but full cluster-level causal synergy is often not directly proven.
3. Broad clusters can still qualify when only a subset of ingredients are dose-anchored (by design), which is stable but can inflate perceived evidence strength.

## Recommended next hardening step (before export)
1. Add a citation contract to each cluster:
   - `sources: [{source_type, id_or_url, evidence_scope}]`
   - `evidence_scope` in `{pair_level, cluster_level, mechanistic}`
2. CI gate:
   - Tier-1 cluster requires at least one primary source and non-empty `synergy_mechanism`.
3. Keep scoring deterministic:
   - no network lookups in runtime pipeline; all citations remain static local data.

## Source links
- NIH ODS Vitamin D Fact Sheet: https://ods.od.nih.gov/factsheets/VitaminD-HealthProfessional/
- NIH ODS Iron Fact Sheet: https://ods.od.nih.gov/factsheets/Iron-HealthProfessional/
- NCCIH Glucosamine and Chondroitin: https://www.nccih.nih.gov/health/glucosamine-and-chondroitin-for-osteoarthritis
- PubMed PMID 9619120 (curcumin + piperine): https://pubmed.ncbi.nlm.nih.gov/9619120/
- PubMed PMID 23644932 (AREDS2): https://pubmed.ncbi.nlm.nih.gov/23644932/
- PubMed PMID 30807974 (magnesium + B6 stress subgroup): https://pubmed.ncbi.nlm.nih.gov/30807974/
- PubMed PMID 34959948 (melatonin+magnesium+zinc sleep trial): https://pubmed.ncbi.nlm.nih.gov/34959948/
- FDA Q&A on Dietary Supplements: https://www.fda.gov/food/information-consumers-using-dietary-supplements/questions-and-answers-dietary-supplements
- FDA K2 claim denial update: https://www.fda.gov/food/cfsan-constituent-updates/fda-denies-health-claim-notification-vitamin-k2-osteoporosis
