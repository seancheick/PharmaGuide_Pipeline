# Tart cherry literature record — receipt (2026-10-20)

Batch: `scripts/data/literature_evidence_records.json`, the record with `canonical_id` `tart_cherry_fruit` (one
entry). Corrected by hand against the PubMed abstract of PMID 20459662 (Kuehl et al., J Int Soc Sports Nutr 2010;7:17),
not by `verify_literature_records.py` (which rewrites the whole file). Its existing PMID/title provenance stays true.

| Field | Before → after | Abstract |
|---|---|---|
| `material_form` | "Prunus cerasus (Montmorency tart cherry) standardized extract" → "Montmorency tart cherry juice" | "tart cherry juice ... placebo cherry drink" |
| study `dose` | "480 mg tart cherry anthocyanins equivalent" → "355 mL tart cherry juice twice daily" | "ingested 355 mL bottles of tart cherry juice or placebo cherry drink twice daily" |
| study `duration` | "7 days" → "7 days before and on race day" | "for 7 days prior to the event and on the day of the race" |
| study `outcome` | "...muscle pain and exercise-induced inflammation" → muscle pain only | VAS pain only; no inflammation measure |
| `population_context` | "athletes and active adults ..." → "healthy runners in a long-distance relay race" | "Fifty-four healthy runners ... long distance relay race" |
| `studied_dose_exposure` | 480 mg → removed | no mg dose in the paper (561 of 808 records carry none) |
| `effect_direction` / `applicability_decision` | positive_moderate / ">= 480 mg standardized anthocyanin extract" → `applicability_unestablished` / juice does not transfer to powder or extract without bioequivalence | goji precedent (`literature_evidence_records::goji_berry`, `verify_semantic_applicability` MATERIAL_FORM_MISMATCH_CANARIES) |

Class scan (same defect elsewhere): all 264 PMIDs cited by the 237 records with qualifying studies were fetched from
PubMed. 87 studies state a dose whose figures appear nowhere in the abstract (heuristic; `class_scan.json`). A content
sample of 10: 3 format-only matches (agmatine 2.670 g, lion's mane 4×250 mg×3, rose hips 5 g); 5 abstracts state no dose
(rose hips 18384191, ginger 11710709, chlorophyll 7350215, L-carnosine 20091069, DMAE 12844472; need full text); 2
contradicted by the abstract, the same class as this record: pumpkin 25196580 ("320 mg/day oil extract"; the trial gave
5 g seed b.i.d. or 500 mg extract b.i.d.) and açaí 21569436 ("1000 mg extract equivalent"; the trial gave 100 g açaí pulp
twice daily). Not changed here; queued.
