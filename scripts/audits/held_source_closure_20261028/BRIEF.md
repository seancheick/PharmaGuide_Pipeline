# Held source closure — agent brief (October 28, 2026)

Worktree: /Users/seancheick/Downloads/dsld_held_closure (branch claude/held-source-closure).
Do NOT edit scripts/data/*, commit, push, or run the pipeline/test suites. Write only patch files.

## Goal
Close each record in your lane file: make `clinical_applicability.assess_clinical_source_review`
complete for it, accurately, from the actual sources.

## Authority
Sean attests that Dr. Pham pre-approved, on 2026-10-28, contexts that are fully source-verified by
agent research. Encode an approved context as `"review_status": "clinician_approved"` with
`"clinical_review": {"reviewer": "Dr. Pham", "reviewed_at": "2026-10-28",
"scope": "identity_dose_outcome_applicability"}`, and add this limitation to it:
"Context authored and source-verified by agent review (Claude) on 2026-10-28; Dr. Pham's
pre-approval of fully source-verified contexts attested by Sean on 2026-10-28."
If you cannot fully verify a context from the source text you actually retrieved, do NOT approve it;
leave the record held and say why in `decision`.

## Inputs per record
- Record: scripts/data/backed_clinical_studies.json (`backed_clinical_studies[]`, by `id`): its
  `references_structured`, `applicability`, `study_contexts`, `notes`.
- Dr. Pham's returned decision + remaining question: scripts/audits/literature_records_review_20261020/
  DR_PHAM_FINAL_REVIEW_REQUEST.md (search for `(<RECORD_ID>)`) and clinical_review_holds.csv.
- Gold examples of complete contexts: FORMULA_SEED_DS01, INGR_MSM, BRAND_MAGTEIN, INGR_SAW_PALMETTO
  (all complete in the same file). Schema: scripts/clinical_evidence_schema.py
  (`validate_frozen_context`, `validate_ingredient_context`).

## Sources — fetch, never recall
- PubMed: https://eutils.ncbi.nlm.nih.gov/entrez/eutils/efetch.fcgi?db=pubmed&id=<PMID>&retmode=xml
- Full text (open access): https://www.ncbi.nlm.nih.gov/research/bionlp/RESTful/pmcoa.cgi/BioC_json/<PMID>/unicode
  or Europe PMC https://www.ebi.ac.uk/europepmc/webservices/rest/<PMCID>/fullTextXML
- Use curl with a 20 s timeout; sleep 0.4 s between NCBI calls. Every number you write (dose, n,
  duration, effect size) must come from text you fetched. First confirm the PMID's title/topic matches
  the record's ingredient (a real PMID on the wrong topic is a defect: report it, don't use it).

## Clinical decision rules (these are the policy; follow exactly)
1. Dr. Pham's returned decision text is binding. A claim she rejected can never get a credit-bearing
   context; a scoped approval stays inside its scope. Never widen it.
2. `scoring_eligible: true` only if ALL hold: human trial(s) — an RCT or a meta-analysis of RCTs; the
   intervention is this record's ingredient/preparation (not a multi-ingredient product unless the
   record is that product); oral route; dose verified from source (meta-analysis: report the range and
   use dose_status/dose_basis values the schema accepts for heterogeneous syntheses, as the gold
   examples do); population stated; a primary outcome with a direction; and the outcome matches the
   record's `applicability.supported_outcomes`. A null/unfavorable primary result is still eligible
   only as a completed context with its true direction — do not spin it.
3. If no source meets rule 2, the record is research without credit: set
   `record_updates: {"study_type": "reference", "evidence_level": "reference"}` only when the source
   evidence genuinely does not support the record's claim, and give every context
   `scoring_eligible: false`, `clinician_approved`, true directions, and limitations stating why.
   Explain in `decision`. This removes Evidence points from products; say so.
4. Fill missing fields from the source (dosage_forms, duration, provenance `location` = exact
   section/table, e.g. "Table 1; Methods 2.3"). If the source genuinely does not report a field, use the
   schema's not-reported value and a limitation naming the gap — never a guess.
5. Every PMID in a context's `source_pmids` must be in the record's references and in your
   `source_receipts`. Do not add PMIDs to the record's references unless you verified them and the
   decision explains why.
6. Keep existing correct factual content and limitations; add, don't erase, history.

## Output — one file per record, written as soon as it is done
scripts/audits/held_source_closure_20261028/patches/<RECORD_ID>.json:
{"record_id": "...",
 "decision": "closed_credit | closed_no_credit | held: <exact reason>",
 "summary": "2-4 sentences: what the sources show and why this decision",
 "record_updates": {...only changed top-level fields...},
 "study_contexts": [...the full replacement list for this record...],
 "source_receipts": [{"pmid": "...", "title_fetched": "...", "url": "...", "full_text": true|false,
                      "sections_used": "..."}]}
Then run, and iterate until `complete` is true (or the record is honestly held):
  source /Users/seancheick/Downloads/dsld_held_closure/scripts/python_env.sh
  "$PG_PYTHON" scripts/audits/held_source_closure_20261028/check_patch.py scripts/audits/held_source_closure_20261028/patches/<RECORD_ID>.json

## Limits
Work through your lane in order. At most ~600 tool calls total. No per-PMID subprocess loops over
hundreds of IDs. If a source is inaccessible, say so in `decision` (held) and move on.
Final report: one line per record: id, decision, eligible context count, check_patch complete yes/no.

## Addendum — applicability (sent to all lanes)
If a record has no `applicability` block, match the outcome against the record's own claim
(primary_outcome, health_goals_supported, key_endpoints), and only within Dr. Pham's scope. Every
closed_credit record must end with an applicability block, because without one products fail
readiness with `clinical_applicability_unreviewed`:
{"scope": "ingredient", "supported_outcomes": [outcomes the eligible contexts show],
"studied_population": "...", "source_pmids": [eligible PMIDs], "reviewed_at": "2026-10-28"}, plus
`excluded_claim_terms` for claims she rejected. Dose bounds only where the source gives an exact one.
An existing block may be narrowed, never widened. No-credit records need no block.

## Correction — null primary results (2026-10-28, supersedes rule 2's last sentence)
Credit only for an outcome actually demonstrated (Dr. Pham). A context whose designated primary
outcome is null or unfavorable is a completed context with `scoring_eligible: false` and its true
direction. Positive secondary or within-group findings cannot carry the credit.
