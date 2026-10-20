# Tart cherry one identity — receipt (2026-10-20)

Goal: botanical `tart_cherry_fruit` and IQM `tart_cherry` are one substance, but 33 CherryPure rows resolved to the
botanical record (current main, all 552 cherry-mentioning labels). Built on PR212 (the literature record fix).

| Change | File / entry | Verified (2026-10-20) |
|---|---|---|
| exact_equivalent botanical `tart_cherry_fruit` → IQM `tart_cherry` | canonical_equivalences.json, equivalences[7] | Same UNII 1L29G6428X: GSRS "SOUR CHERRY", parent substance PRUNUS CERASUS WHOLE. Precedents: bromelain, acerola. |
| IQM `external_ids.unii` = 1L29G6428X | ingredient_quality_map.json `tart_cherry` | As above. |
| CherryPure spellings filed under IQM forms | `tart_cherry` forms | The "… Proanthocyanidin extract" and "… (Prunus cerasus) extract" spellings → 'tart cherry extract' (the label prints "extract"); "… Proanthocyanidin powder" and "Whole Montmorency Tart Cherry Fruit Powder" → 'tart cherry (unspecified)' (a printed powder never reads an extract form). |
| Remove RXCUI 1012134 | botanical_ingredients.json `tart_cherry_fruit` | RxNav 1012134 = "sour cherry allergenic extract" (TTY IN), an allergen-immunotherapy concept, not dietary tart cherry. Not moved to IQM. |
| CUIs kept | both records | UMLS C0330657 = "Prunus cerasus" (semantic type Plant) on the botanical record; C5448936 = "Tart Cherry" (Organic Chemical / Pharmacologic Substance) on IQM. Each fits its record type. |
| Literature record keyed to `tart_cherry` | literature_evidence_records.json [111] | Content corrected in PR212; only the key changes. |
| Remove species-ambiguous "cherry puree", "cherry puree powder" | botanical `tart_cherry_fruit`, `dark_sweet_cherry` | "Cherry puree powder" names no species, yet it sat on both cherry records. With tart cherry deferring to IQM, the redirect would have broken the tie in tart cherry's favour (test_species_ambiguous_cherry_puree_remains_unresolved). "tart cherry puree powder" stays. Corpus: **27203** (DSLD group "cherry (unspecified)") resolved to `dark_sweet_cherry` on main through the shared alias; it is now unresolved, which is correct (pinned by test_gnc_cherry_puree_powder_is_no_longer_called_sweet_cherry). **78306** keeps `dark_sweet_cherry`, from its DSLD group "Sweet Cherry", not from the alias. |

Tooling: `data_batch.py` now owns canonical_equivalences `_metadata.total_entries` (it counted only total_relationships,
so the count went stale on an added row).

## One evidence policy for tart cherry (independent audit F1)

`evidence_resolver` reads `backed_clinical_studies` (step 7a) before `literature_evidence_records` (7b). With the
literature record keyed to `tart_cherry`, INGR_TART_CHERRY would decide every tart cherry row, and the literature
record's juice-only decision (PR212) would apply to no product. INGR_TART_CHERRY now carries the same applicability:

| Field | Value | Basis (PubMed abstracts read 2026-10-20) |
|---|---|---|
| `required_form_terms` | "juice" (source label) | The record's positive trial, PMID 22038497, gave 20 adults tart cherry **juice concentrate** for 7 days (melatonin up, sleep time up). |
| `excluded_form_terms` | powder, extract, dried, capsule(s) | PMID 35790450 (44 healthy adults, 30 days) had juice and **powdered-capsule** arms; neither changed sleep. PMID 40964149 (sleep SR, 7 studies) calls the evidence limited and heterogeneous. PMID 33440334 (recovery SR/MA, 14 studies) pools supplements and does not establish that a dry powder or extract is bioequivalent to juice. |

Same rule as the literature record (PMID 20459662, juice) and the goji precedent. No corpus label prints tart cherry
juice (0 of 191 tart cherry rows), so today the record credits no product; a juice label would be credited.
Not done here: the recovery SR abstract does not report its 14 studies' preparations. Whether any dry-powder trial
supports a powder or extract would need the full text and its own per-trial review.

Citation backlog: the botanical `tart_cherry_fruit` notes named PMID 23075559 (milk consumption and resistance
training, an unrelated paper) as its source. The sentence is removed and its backlog row deleted
(`citation_content_backlog.json`, 261 → 260); the record stays as the redirect source.
