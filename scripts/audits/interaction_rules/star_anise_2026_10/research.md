# Star anise safety rule: evidence receipts (2026-10-20)

Entry: `RULE_BOTAN_STAR_ANISE_SEIZURE` (subject `botanical_ingredients/star_anise`, Illicium verum,
UNII XKC1657P78). Every source below was read on 2026-10-20 by an agent (not clinician-reviewed).
Applied by `apply.py`; `data_batch.py check --expect interaction_rules/RULE_BOTAN_STAR_ANISE_SEIZURE`
reports 1 entry changed and 0 problems. `verify_interaction_rules_citations.py --strict
--changed-since origin/main` passes: PMID 22484123 on topic; PMID 15492355 reviewed as a heuristic miss
in `interaction_rules_ghost_review.json`.

## Sources

- **FDA news release P03-67, "FDA Issues Advisory on Star Anise 'Teas'", 2003-09-10**, read from the
  archived FDA page (`web.archive.org/web/20050115085515/http://www.fda.gov/bbs/topics/NEWS/2003/NEW00941.html`).
  FDA advised consumers not to consume teas brewed from star anise, which were associated with
  illnesses in about 40 people, about 15 of them infants. The illnesses ranged from seizures to
  vomiting, jitteriness and rapid eye movement, and everyone affected recovered. FDA did not identify
  the species involved. It said Chinese star anise (Illicium verum) is GRAS as a spice or flavoring
  and may contain Japanese star anise (Illicium anisatum), which is not GRAS, and that the two cannot
  be distinguished by eye once dried. FDA also told consumers not to give the teas to infants and
  children.
- **PMID 15492355**, Ize-Ludlow et al., Pediatrics 2004;114(5):e653-6, "Neurotoxicities in infants seen
  with the consumption of star anise tea." The abstract reports 7 infants with adverse neurologic
  reactions after home-given star anise tea and evidence that Chinese star anise had been contaminated
  with Japanese star anise. It concludes that star anise tea should no longer be given to infants. MeSH
  terms: Neurotoxicity Syndromes, Food Contamination, Illicium/adverse effects. Cited for those facts
  only, not for the seizure claim.
- **PMID 22484123**, Shen et al., J Chromatogr A 2012;1259:179-86. Products with Chinese star anise
  contaminated or adulterated with Japanese star anise or other Illicium species "can cause epilepsy,
  hallucinations, and nausea" because of anisatin. In the same study, 8 retail teas contained no
  significant anisatin.
- Read but not cited: PMID 23802692 (Mathon 2013, LC-MS/MS: high anisatin in I. anisatum,
  I. lanceolatum and I. majus); PMID 16001842 (Joshi 2005, I. anisatum as an adulterant of powdered
  I. verum); PMID 12014240 and PMID 12617067 (adult seizures after Japanese star anise; title only,
  no abstract). Abstracts are in `~/pg_quality/star_anise_safety_20261020/pubmed/`.

## Decision

- **Owner: an interaction rule, not banned_recalled or harmful_additives.** A `watchlist` or
  `high_risk` entry in banned_recalled turns every matching product into CAUTION and zeroes its safety
  pillar (`gate_safety.py`, `quality_score.json`). That would treat a GRAS spice as hazardous for
  everyone. The sources do not support that. The hazard is contamination of unknown prevalence (the
  2012 tea survey found none), and FDA's advisory was an interim measure about teas.
  harmful_additives covers additives, not actives.
- **Who: seizure_disorder, at `caution`, with evidence `limited`** (case reports and an FDA advisory;
  the species was unconfirmed in FDA's cases). This follows the contamination-based ginkgo seizure
  rule (ginkgotoxin). The copy says "talk to your doctor", with a stop-and-get-care instruction for the
  symptoms FDA reported. The rule fires on presence: no dose floor has threshold evidence.
- **Pregnancy and breastfeeding: `no_data`**, the standard limited-data block. No source addresses
  pregnancy, and none shows transfer into breast milk.
- **No drug_class rule.** No interaction evidence exists, and an anticonvulsant rule would only
  restate the condition rule.
- **Not encoded: infants and children.** The best-supported population (FDA; Ize-Ludlow) has no
  profile flag or condition in `clinical_risk_taxonomy.json`. All 10 corpus products are adult bulk
  powders labelled "Keep out of reach of children." This is reported as a gap, not worked around.

## Identity

- Raw census of `~/Downloads/PharmaGuide_Datasets/staging/brands`: 10 labels name star anise, all
  BulkSupplements single-ingredient extract powders, 500 mg taken 1-3 times daily (252910,
  254540-254542, 311657, 311658, 311660, 311662, 330859, 330861). No label names Illicium anisatum,
  Japanese star anise or shikimi.
- Probe: rows named "Japanese Star Anise", "Illicium anisatum" or "Shikimi" stay unmapped and never
  take the GRAS `star_anise` identity. This is pinned in `test_star_anise_seizure_rule_20261020.py`.
  The GSRS synonym "ILLICIUM ANISATUM [HPUS]" on the star anise record is not used. A separate entry
  for Japanese star anise would be a dormant guard (0 labels today), so it is left as a follow-up.

## Measurement

Replay (`scripts/audits/quality_redesign/replay.py`, freeze-raw, then `snapshot --full --blob` on main
`e55b6ccef` and on this branch): 18 labels, the 10 above plus 8 controls (18453, 79431, 212457,
285635, 15717, 204040, 312995, 328723). Exactly the 10 star anise products changed, in enriched and
blob only. Each gained 3 profile-gated warnings: seizure_disorder `caution`, pregnancy `no_data` and
lactation `no_data`, all `RULE_BOTAN_STAR_ANISE_SEIZURE`. Score (57.1), quality status, tier and
`product_safety_status` (`no_known_catalog_concern`) are unchanged for all 10. All 8 controls are
byte-identical apart from clock stamps. Receipts are in `~/pg_quality/star_anise_safety_20261020/`.
