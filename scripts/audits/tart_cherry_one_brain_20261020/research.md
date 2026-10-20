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
| Remove species-ambiguous "cherry puree", "cherry puree powder" | botanical `tart_cherry_fruit`, `dark_sweet_cherry` | "Cherry puree powder" names no species. It sat on both cherry records, so it stayed unresolved; with tart cherry deferring to IQM, the redirect would have broken the tie in tart cherry's favour (test_species_ambiguous_cherry_puree_remains_unresolved). "tart cherry puree powder" stays. Corpus: 27203 and 78306. |

Tooling: `data_batch.py` now owns canonical_equivalences `_metadata.total_entries` (it counted only total_relationships,
so the count went stale on an added row).
