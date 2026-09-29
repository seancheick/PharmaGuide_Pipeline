# N. Remediation plan (nothing implemented; each record follows the 16-field contract; ordering is dependency-aware per §39)

Rule for every item: **enhance the existing owner; no parallel implementation, no new engine/registry/field/state/scorer/parser.** Where a record proposes a config value or a policy, it goes to Sean first.

## Order
1. Safety / data loss: RR-08 (dormant fail-open wiring) — small, closes the §15 gap before anything ships.
2. Contract: RR-11 (panel Evidence state) — trivial, user-visible, already in the candidate.
3. Identity/enrichment correctness: RR-07 (botanical hijack), RR-04 (phantom anchor), RR-09/RR-10 (cleaner dispositions).
4. Scoring policy for Sean: RR-01 (form ceiling), RR-03 (adequacy basis), RR-05 (coverage-gap zero), RR-02 (B12 receipts) → one candidate-evaluator packet, then config/data changes only.
5. Docs/tests: RR-06 and K rows.
6. Dead/duplicate: L-6, L-7, J rows.

---
### RR-08 · safety-resolver failure must not ship SAFE
- Canonical owner: `scripts/scoring_v4/gate_completeness.py` (completeness policy) reading `SafetyGateResult.ingredient_assessment_complete` (already produced by `gate_safety.py`).
- Root cause: B3 added the fact without a consumer.
- Smallest fix: in the completeness gate, `ingredient_assessment_complete is False` ⇒ `not_scored` with reason `safety_assessment_incomplete` and the error list surfaced in `strict_scoring_contract.findings`; the artifact's `product_safety_status` becomes an explicit unassessed value only if one already exists in the enum (else `not_scored` withholds the product, which is the release rule's safe side).
- Files/symbols: `gate_completeness.py::evaluate_completeness_gate` (+ one branch), `scored_artifact.py` (reads existing findings), test `test_safety_policy_readiness.py` (raise inside `_inactive_resolver()` via monkeypatch → `not_scored`).
- Schema: none (existing findings list). Pipeline: none. Flutter: none (not_scored already handled).
- Tests: the monkeypatched-resolver test; a parity test that a normal run keeps `ingredient_assessment_complete: True` on the 143 frozen labels.
- Probes: 33360 (blocked stays blocked), 184004 (normal). Replay: frozen sample (0 changes expected). Expected score/safety change: none in normal runs.
- Migration/compat: none. Dead code made removable: none. Docs: `.claude/rules/release.md` gains the sentence "an incomplete safety assessment is not_scored". Rollback: revert the branch. Human decision: no (established invariant §15 / release rule).

### RR-11 · panel routes emit an Evidence result state
- Owner: `multi_prenatal_evidence.py::score_evidence`, `b_complex.py::_score_evidence` (metadata `evidence_result_state`). Root cause: f2efb793 dropped the state when replacing the generic pipeline.
- Smallest fix: emit `evaluated_authority` when `authority_covered_count > 0` (state already exists, ee76a231) else `no_assessable_actives`/`evaluated_null` per the existing enum; no assembler change. Reason copy for `evaluated_authority` already exists in `_EVIDENCE_ZERO_REASON`/authority reason.
- Files: the two modules; tests `test_v4_multi_prenatal_evidence_p33.py`, `test_v4_b_complex_module.py` (assert state + display_state `assessed`), plus a route-wide contract test in `test_v4_quality_score.py`: every scored fixture's evidence pillar has a declared state (blocks the regression class).
- Schema/Flutter: none (existing enum value). Probes: 180316, 3565, 12012, 19173 (b_complex). Replay: frozen sample; expected: 22 products change `display_state` and reason only, 0 score changes. Docs: SCORING_ENGINE_SPEC evidence-state table. Rollback: revert. Human decision: no.

### RR-07 · botanical profile must not zero a non-botanical product
- Owner: `botanical_profile.py::is_botanical_product` (+ `_is_botanical_active`, `_primary_botanical_active`). Root cause: the profile's row set admits a fiber/other row with a botanical *source* form as the primary botanical, and an unrecognized primary yields 0 − 4 instead of "not a botanical product".
- Smallest fix: (a) `is_botanical_product` returns False when `_recognized_botanical_identity(primary)` is False (the docstring's own rule: no recognizable botanical active ⇒ not the botanical path); (b) `_is_botanical_active` must not admit a row whose canonical registry/category is fiber/protein/mineral/vitamin on the strength of a source form alone. Keep the −4 for recognized-but-weak botanicals.
- Files: `botanical_profile.py`; regression `test_v4_botanical_profile.py` (233404 fixture: `is_botanical_product` False, Formulation A1 8.71 → pillar > 0) and a control (282638 greens stays botanical, 8.0).
- Schema/Flutter: none. Probes: 233404/233406, 282638, 243271. Replay: frozen sample + affected cohort = every generic-routed product with `botanical_profile_applied` and `recognized: False` (census on the candidate blobs' `formulation_detail`); expected: Formulation rises on the hijacked set only. Docs: botanical_profile docstring already states the invariant. Rollback: revert. Human decision: no (established invariant in the code's own contract).

### RR-04 · no phantom child anchor when the children are dosed
- Owner: `scoring_input_contract.py::_derive_blend_header_anchor_from_nested_child`. Root cause: the anchor is emitted for every `blend_header_total`, including headers whose children carry amounts.
- Smallest fix: return None when any nested child under the header has a positive usable amount (`_positive_quantity`), or when the header already produced `identity_bearing_blend_header_mass`; keep the anchor for undosed children (67304).
- Files: the contract; tests `test_scoring_input_contract.py` (270253-shaped: exactly one row per canonical; 67304-shaped: anchor kept), `test_v4_sports_dose_p171.py` (order-independence: reversed rows give the same `group_bcaa` result).
- Schema/Flutter: none (anchors never reach the blob). Probes: 270253, 59952, 67304, 77108. Replay: frozen sample; expected: Formulation A1 may move slightly on blend products (the phantom row's bio 13 leaves the mean); Dose unchanged. Docs: contract docstring. Rollback: revert. Human decision: no.

### RR-09 / RR-10 · cleaner dispositions
- Owner: `enhanced_normalizer.py` header rule (4867–4897) and dual-context mineral rule (11169–11215). Smallest fixes: (RR-09) a `Header`-group row with a positive mass and nested rows is a `blend_header_total`; (RR-10) either route the dosed Chloride row to `nutritionalInfo` as the comment says, or admit it as an active mineral — **RR-10 is a policy question** (electrolyte products). Probes: 269317 (anchor + 2:1:1 reading appears), 311733. Replay: the ~9 header labels; the 369 chloride labels only after the policy call. Human decision: RR-09 no, RR-10 yes.

### RR-01 · form-quality reference (policy packet, C1)
- Owner: IQM (`ingredient_quality_map.json`, ADR-0003) for an authored per-parent reference; `scoring_reference_resolver.parent_relative_form_quality` as the one reader. Options for the candidate evaluator (read-only, `replay.py report`): (A) raw bio_score (no ceiling), (B) dynamic ceiling (status quo), (C) authored `formulation_reference_score` per parent (C1 as written; requires reviewing 373 parents — start with the 265 whose ceiling ≤ 11). Measure on the frozen 143 + a full frozen corpus: pillar deltas, movers (336348, 252451, 288632, 233404), tier crossings. Expected: (A) lowers Formulation broadly; (C) is the only option that expresses "good enough form for this nutrient" without rewarding a poor-only parent. Docs: RECONCILIATION C1 rewritten to the decision. Human decision: **yes**.

### RR-03 · one adequacy basis
- Owner: `serving_frequency.resolve_daily_serving_range` + `scoring_v4/exposure.py` (one Exposure object) with every Dose owner reading one field. Decision for Sean: minimum (fail-closed, glossary) or maximum (Task 2, matches UL's risk reading) or per-route with an authored reason. Evaluator arms: min-everywhere, max-everywhere; movers from the Task 2 shadow (77 labels) plus the omega/botanical mirror set. Docs: GLOSSARY or TASK2 corrected. Human decision: **yes**.

### RR-05 · coverage gap in the public total
- Owner: `quality_score.py::_pillar_evidence` / `assemble_quality_score`. Options: (a) neutral baseline for `not_yet_reviewed` like Verification `fail_open_neutral` (config `evidence_subscale.neutral_baseline`), (b) re-weight remaining pillars, (c) status quo with copy. Evaluator on the 309 candidate products and the 7 sample ones; report SAFE↔POOR flips. Human decision: **yes** (C5).

### RR-02 · B12 form receipts
- Owner: IQM data + RECONCILIATION C9. Action: Sean confirms/rejects the tie; three commit bodies amended in a follow-up note (git history is immutable: record in RECONCILIATION with the `form_evidence` references); extend the census to vitamin C / calcium / folate / thiamine (`git diff 7b031050..HEAD` on their forms). Human decision: **yes**.

### RR-06 + K rows · docs
- Update SCORING_ENGINE_SPEC header stamp, PIPELINE_ARCHITECTURE (stage fingerprints, owner scoping, authority panels, parent-relative forms), DATABASE_SCHEMA IQM 5.6.1, matrix `_metadata.last_updated`, LEDGER Q36 counts and FiberSMART rows, test docstring in `test_safety_only_rows_get_scored.py`, rename `test_fibersmart_unmapped_quarantine.py`; memory `project_v4_score_is_rubric_raw.md`. No code.

### Calibration direction (answer to Codex's status; policy for Sean)
- Codex's "complete" list checks out on HEAD for: one scorer; unspecified-form handling; daily exposure for fiber/sports (but not one basis: RR-03); EPA+DHA ownership; protein/generic source scoping; non-delivering forms; dose disclosure owner; full-disclosure Transparency; raw active/inactive/Nutrition Facts separation (with the two cleaner gaps RR-09/10). "Scoring penalty and safety concern ownership" is partly open (D12 double deductions listed in F). Not complete as claimed: C1 is in production as a dynamic ceiling (RR-01), C9 B12 values are live (RR-02).
- Recommended evaluator arms for one packet (read-only on the frozen 143 + full frozen corpus): base = HEAD; A1 = raw bio_score (no ceiling); A2 = authored references for the 265 low-ceiling parents (pilot: the 20 most-shipped); B = one adequacy basis (min vs max); C = neutral Evidence for `not_yet_reviewed`; D = omega evidence floor 376 → 250 mg with the prenatal-DHA authority extended to any label at ≥ 200 mg DHA (C-4), each arm measured by route/subroute distribution, pillar deltas, large movers, SAFE↔POOR flips, and the 30 reference products' ordering (`reference_cases.json`). Ratify benchmark v7 (D15) before adopting any arm.
- Fairness principles for the packet (no numbers proposed here): unknown ≠ bad (RR-05); one fact, one pillar (F §7: presence feeds three pillars on panel routes; additives and UL feed two — D12); a parent's best form is a reviewed fact, not a maximum (RR-01); the label's directions are read one way everywhere (RR-03); Verification stays attribution-only.
