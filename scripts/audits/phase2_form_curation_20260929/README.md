# Phase 2 form curation — 2026-09-29

## Owner Check

Owner: `scripts/data/ingredient_quality_map.json::forms` — evidence:
`rg -n "ingredient_quality_map|parent_relationship|source_form_aliases" scripts/contracts/source_of_truth_matrix.json scripts/GLOSSARY.md scripts`.

Owner: `scripts/scoring_reference_resolver.py::unknown_floor` — evidence:
`rg -n "unknown_floor|floor_eligible" scripts/scoring_reference_resolver.py scripts/tests`.

Will NOT create: a second form registry, a second normalizer, a second vanadium identity, a
brand-token scoring shortcut, or a species-equivalence rule.

## Q38 closure

The historical `unknown_floor` override is retired. An authored unspecified form now stores the
lowest eligible named score minus one. A legacy Excellent named form without approved structured
evidence cannot propagate a new Excellent unspecified score. When no evidence-approved named basis
exists, an unsupported unspecified form is capped at 11 by the existing Excellent evidence gate.

The migration changed 54 authored unspecified scores from branch HEAD. Eight unsupported
unspecified forms dropped below Excellent and were removed from `remaining_forms` in the frozen
evidence backlog; `initial_forms` remains unchanged.

## Verified mineral batch

Fresh NIH DSLD raw JSON was fetched for 14 representative labels. The active-row parent, category,
and `forms[]` data are preserved in `raw_label_receipts.json`. Nine exact salt identities were
verified through PubChem PUG REST; receipts are in `pubchem_identity_receipts.json`.

The new named forms receive the conservative parent baseline and no absorption premium:

- calcium acetate, sulfate, chloride, and glycerophosphate;
- magnesium glycerophosphate;
- potassium iodate;
- sodium metasilicate, magnesium trisilicate, and calcium silicate as silicon sources.

`phosphorus oxide` remains held because the label term is chemically ambiguous and PubChem returned
no exact compound. OT2, Chromium GlycoProtein Matrix, Zychrome, Lipo-Cmax, and ChelaMax remain held:
they are branded or contextual tokens whose chemistry was not established by this identity batch.

## Vanadium ownership

The two chemical identities remain distinct: elemental vanadium owns UNII `00J9J9XKDE`, and exact
vanadyl sulfate owns `6DU9Y533FA`. Nutrient rows whose raw DSLD parent is Vanadium now read
parent-scoped source forms for vanadyl sulfate, BMOV, BPOV, amino-acid chelate, aspartate, and
citrate. Exact compound aliases remain on `vanadyl_sulfate`; generic nutrient-source aliases were
removed from its unspecified form.

## Species and plant-part holds

Expanded regression coverage keeps the unresolved D21 species and plant-part mismatches held,
including Salix babylonica, oat seed, Lycium chinense, Cucurbita moschata, celery stalk,
Plantago asiatica, grape skin, and wild green oat aerial parts. Existing separate owners resolve
Prunus avium and other identities already curated since the original queue was written; they are
not forced back into a stale hold.
