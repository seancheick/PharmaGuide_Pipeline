# Screening brief — PharmaGuide Wave 1 clinical evidence

You screen already-retrieved PubMed records. You do NOT search, do NOT call any API, do NOT decide what scores. A central reviewer re-verifies every item you return against the live source, so an honest "unclear" is worth more than a confident guess.

## Input (already on disk — read with Bash/Read, no network)
Base dir: `/private/tmp/claude-501/-Users-seancheick-Downloads-dsld-clean/198c0b43-32a9-488c-8f04-6e252fe38fe3/scratchpad/candidates/`
For each identity in your partition file:
- `<canonical_id>.index.tsv` — one line per record: `pmid, year, roles(reviews|trials|safety), pub_types, humans_mesh, integrity, title`. Triage titles here first.
- `<canonical_id>.json` — `{identity: {...}, search: {...}, records: [{pmid, doi, title, abstract, journal, published_date, publication_types, mesh_terms, retracted, expression_of_concern, has_erratum, pmc_id, query_roles}]}`. Read abstracts only for records your title triage kept (use `python3 -c` to pull specific PMIDs — do not cat the whole file).

`identity` gives: canonical_id, the label name and the exact label spellings/forms seen on scored products, product counts. That label reality decides relevance: evidence must concern the SAME material an oral supplement label delivers.

## What to return per identity (write ONE json file per identity; see output)
1. **Title triage over every record.** Keep a record only if it plausibly studies this identity in humans. Reject with a short reason code: `different_substance` (e.g. Garcinia kola vs Garcinia cambogia; tyrosine-kinase drug), `not_this_route` (IV/parenteral/enteral tube feeding/topical/injection), `animal_or_invitro`, `not_intervention` (epidemiology of dietary intake, assay/method paper, protocol), `off_topic`, `duplicate`.
2. **For kept records, read the abstract** and record:
   - `design`: guideline | systematic_review | meta_analysis | network_meta_analysis | rct | crossover_rct | controlled_nonrandomized | observational | case_report | other
   - `human_status`: confirmed (≥2 of: Humans MeSH, participants described in abstract, trial registration id) | ambiguous | nonhuman — list the signals you used
   - `evidence_role`: efficacy | safety | pharmacokinetic | interaction | dose_guidance | mechanistic
   - `intervention_as_stated`: exact wording of what was given (form/salt/extract/species/plant part/brand/combination). Set `combination: true` when it was not given alone.
   - `route`: oral | iv | enteral_tube | topical | other | unstated
   - `population_as_stated`, `indication_as_stated`
   - Verbatim quotes, each an EXACT substring of the stored abstract (never paraphrase, never reconstruct): `dose_quote`, `primary_outcome_quote`, `primary_result_quote`, `sample_size_quote`, `funding_quote`. Use null when the abstract does not state it. Never infer, convert, or complete a dose.
   - `primary_outcome_identifiable`: true/false. If the abstract reports a null/neutral primary outcome and a positive secondary one, say so explicitly in `direction_note` — that is NOT a positive trial.
   - `direction_primary`: positive | mixed | null | negative | unresolved (unresolved when the abstract does not report the primary result)
   - `registrations`: NCT/ISRCTN/CTRI ids in the abstract; `included_studies`: PMIDs if a review lists them, else "extraction_pending"
   - `label_material_match`: exact_match | related_form_differs | different_material | unclear — compare `intervention_as_stated` against the identity's label spellings/forms; explain in one line.
   - `integrity`: copy retracted / expression_of_concern / has_erratum from the record.
3. **`shortlist`**: up to 12 PMIDs per identity that a curator should read in full first — highest-quality human evidence about the label material, INCLUDING null/negative/mixed results. Never rank by positivity. Note when the best available evidence is weak, indirect, or absent.
4. **`handoff`**: records whose primary role belongs to another owner (safety/adverse events, drug interactions, pharmacokinetics, nutrient depletion, dosing/UL guidance): pmid, role, one-line reason. No clinical interpretation.
5. **`identity_notes`**: anything that blocks applicability — e.g. most trials use a different salt/ester than the label, evidence is only IV, species mismatch, the canonical lumps distinct materials (say which), or no qualifying human evidence exists in this retrieved scope.

## Hard rules
- **Quote fields carry COPIED text only.** A quote must be one contiguous run of characters that exists verbatim in the stored abstract, copied character for character. No ellipsis joining distant sentences, no paraphrase, no summary you composed, no items joined with "/" or "and" across sentences.
- If no single contiguous span states the fact, leave the quote field null and set `needs_central_extraction: true` on that record, describing the fact in a prose note field instead. A missing quote is fine; a composed one is a defect.
- Verification is deterministic and byte-exact against the live source, and it is the final gate — anything that does not match is rejected.
- Never invent or infer a PMID, dose, unit, exponent, sample size, direction, or conclusion.
- Never treat a secondary-endpoint positive as a positive trial; never call an IV/enteral trial evidence for an oral supplement; never let a combination trial stand for one component.
- Do not write anywhere except your output dir. Do not modify the repo. Do not spawn subagents. No network calls.
- Budget: keep it under ~120 tool calls. Prefer batched `python3 -c` reads over per-record calls.

## Output
One file per identity: `<OUTPUT_DIR>/<canonical_id>.screen.json`
```json
{"canonical_id": "...", "screened": N, "kept": N,
 "rejected": [{"pmid": "...", "reason": "different_substance", "note": "Garcinia kola, different species"}],
 "records": [{ ...fields from step 2... }],
 "shortlist": ["pmid", ...],
 "handoff": [{"pmid": "...", "role": "safety", "reason": "..."}],
 "identity_notes": "..."}
```
Final message: one line per identity — screened/kept/shortlisted/handoff counts + the single most important applicability caveat. No efficacy summaries, no recommendations.
