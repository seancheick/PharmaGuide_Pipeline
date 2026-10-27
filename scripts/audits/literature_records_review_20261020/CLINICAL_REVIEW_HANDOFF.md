# Current shared-cause completion handoff

## October 27 — shared-cause completion candidate

Owner: `scripts/api_audit/verify_literature_records.py::verify_reference_citations` and `scripts/dose_assessment.py::verified_reference_citations` — evidence: fail-first changed-source/retry/wrong-identity/malformed/correction tests and source-bound receipts. Owner: `scripts/scoring_v4/modules/botanical_profile.py::_botanical_benchmark`, `scripts/evidence_resolver.py::_evidence_owner_selection`, `scripts/enhanced_normalizer.py::_exact_ingredient_group_lookup` / `_single_declared_source_form_identity`, and existing applicability/native context owners. Will NOT create another scorer, registry, clinical authority, identity matcher, threshold, grade, public product field or release system.

Behavioral code/data batch; no weights changed. 321 general Dose decisions now have separate content-bound source proofs. Dose source verification cannot qualify empty trial lists for Evidence. Missing, changed or malformed proof fails closed; repeat runs cannot auto-clear invalidated proof. Exact reviewed corrections can support the limited Dose source conclusion, while retractions/expressions of concern remain blocked. Existing freshness policy is unchanged.

Confirmed fixes: sole-active Pepogest Evidence prominence and delivery scope; known hidden-quantity botanical identities; direct label-active versus blend-total classification; exact native IBS-only exclusions; descriptive non-scoring uncontrolled interventions; source-based Reishi/spinach routing. 119 new source-specific contexts remain pending/non-scoring, with 4 scoped rejected contexts. Bibliography pointers are not asserted to be independently qualified included trials. Exact inositol/lactoferrin relationships are withheld where underlying source integrity is unresolved; unrelated sources/quantities/safety remain.

Read-only frozen preparation reconciliation: 306 of352 groups completed/outside winning owner; 46 unresolved. Source-owner state: 26 of146 frozen contributing subjects complete; 120 retain required source/input or scoped-review holds. All155/514 original register rows and frozen product bindings preserved. These are not rebuilt-product completion counts, new missing responses or universal new signature requests.

Bounded real-label evidence:66 frozen raw labels through baseline/current Clean→Enrich→Score→blob;52 records changed,42 score movements, only2 cleaned identity changes (Reishi294009/spinach330851), zero top-level safety/banned/recalled/quality-score-status changes. Most movements are0→11.4 Dose under existing general-neutral policy; Pepogest Evidence0→7.3; fisetin Evidence1.2→0. Additional final source cases and controls are measured separately. Full-corpus/app/100k validation is not claimed.

Qualification: named owner/consumer checks and local checks recorded in the LEDGER; CI/integration pending until an exact green checkpoint. Complete raw33-canary check passed after source-grounded refresh of336337 (Dose+11.4) and a pre-existing main204571 stale fixture (main and candidate both45.6, Evidence0). No production change restored unsupported fixture credit.

Remaining: the existing source and benchmark CSVs and the [single forwardable message](DR_PHAM_FINAL_REVIEW_REQUEST.md) enumerate the exact holds. Source access/reporting limits and required scoped approvals are separate. After qualified integration, run Clean→Enrich→Score only: all three stage fingerprints changed, with the earliest change in Clean. This is permission to compute/verify, not publication clearance. No pipeline, export promotion, upload, app import, native rendering or release was run.


Historical snapshots remain in git and the dated verification report; they are not current remaining-work requests.
