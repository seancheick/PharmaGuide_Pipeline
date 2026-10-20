# EPA/DHA oil family — October 20, 2026

Problem: the DSLD group "Omega-3" repaired 305211's "life'sOmega" (form: Algal Oil Concentrate)
to fish_oil, and ADR-0005's guard kept the repair because algae_oil answered no omega-3 rule; krill
oil (302654) was repaired the same way. Other algal-DHA and krill products kept their identity but
carried **no** omega-3 bleeding advisory at all. Sean (ADR-0005 amendment, 2026-10-19): preserving
a warning must not force an incorrect identity.

## Change

- IQM `relationships` (the existing owner): algae_oil contains dha (algal DHA oils are bioequivalent
  DHA sources, PMID 17713804); krill_oil contains epa and dha (krill oil delivers EPA and DHA at
  plasma levels comparable to fish oil, PMID 26328782). Both verified by content (PubMed abstracts).
- `identity/interaction.py::INTERACTION_SUBJECT_FAMILY`: algae_oil and krill_oil answer to the EPA/DHA
  oil rule authored on fish_oil; `test_interaction_subject_family.py` pins the family to every IQM
  oil whose relationships contain DHA or EPA.
- algae_oil alias "life'sOmega": the printed spelling of the curated DSM brand alias "life's omega".
- RULE_INGREDIENT_FISH_OIL consumer copy (alert bodies, actions, informational notes, pregnancy body)
  says "omega-3 (EPA/DHA)" instead of fish oil. Verbs, the "3 g/day or higher" qualifier, INR
  monitoring advice, severities, materiality, sources and gates are unchanged. The mechanism text
  (fish-oil studies) is unchanged.

Supporting evidence also read: Conquer & Holub 1996 (PMID 9001371, algal DHA raises platelet DHA;
no change in measured thrombogenic factors), Vidgren 1997 (PMID 9252957), Cottin 2011 review (PMID
21349231, DHA lowers platelet aggregation; algal sources).

## Replay

Every raw label naming algal/algae/krill/life's/Schizochytrium (399), 300 sampled fish-oil labels and
150 controls (842), main 2e80642ca vs this branch, `--full --blob`. Per product: `replay_changes.tsv`.

- **+29 RULE_INGREDIENT_FISH_OIL** on krill-oil, vegan/algal DHA and prenatal-with-algal-DHA products
  that had no omega-3 bleeding advisory; **0 removed**.
- **2 identity corrections**: 305211 life'sOmega fish_oil → algae_oil (69.7 → 75.5), 302654 Krill Oil
  fish_oil → krill_oil (71.8 → 76.6); Formulation follows the corrected identity.
- **230 reworded** (source-neutral copy); 0 product_safety_status changes.

## For Sean

- Krill and algal products whose EPA/DHA children also fire RULE_IQM_DHA_BLEEDING /
  RULE_IQM_EPA_BLEEDING show anticoagulant/antiplatelet advice from two rules (302654). Collapsing
  them would drop the oil rule's bleeding-disorder, surgery and pregnancy advice, so both stay.
- `_is_generic_unspecified_omega3` still sends a generic "Omega-3 Fatty Acids" total to fish_oil
  under an algal parent (293409, 278454, 323711); 42683/43191 Nordic Naturals Algae Omega remain
  label-correction candidates (raw form "Fish Oil").

## Independent audit follow-up (October 20, 2026)

- **F1:** RULE_INGREDIENT_FISH_OIL `mechanism` ships as warnings[].detail, and Flutter shows it
  (interaction_warning.dart). Fish-oil findings are now scoped as such:
  - Factor VII: "In fish-oil studies, lower factor VII levels … have also been reported; algal DHA
    at 1.62 g/day did not alter the thrombogenic factors measured (PMID 9001371)". The PMID was
    added to that sub-rule.
  - The subdural-hematoma case is "in one reported case".
  - The NSAID line says "omega-3 (EPA/DHA) supplements".
  - `mechanism_batch.py`; the copy test now covers mechanisms.
- **F2:** merged main 3d7fe8adf (IQM conflict on `_metadata` only; batch re-applied). Both batch
  scripts note their `data_batch.py check` line.
- **F4, blob-only changes, no score or safety change:** 243663, 328792 and 75286 "Superba Boost
  Krill Oil", and 82325 "Algae Oil". The oil row moves from inactive to active_form_duplicate, and
  that blob row then loses its CUI/UNII/RXCUI/notes.
- **For Sean (F3, unchanged):** the rule has no dose gates, so "EPA/DHA at 3 g/day or higher can
  thin the blood" shows on 62–92 mg products. The "3 g" figure is not in this sub-rule's cited
  sources (ODS gives 2–15 g/day).
- **Next follow-up, same class:** cod_liver_oil, tuna_oil, calamari_oil, calanus_oil and seal_oil
  have no omega-3 family link or rule.
