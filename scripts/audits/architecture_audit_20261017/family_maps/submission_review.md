# Family map — scripts/submission_review/ and product_submission_import.py (Level 1)

Source: listing agent (sonnet, read-only, 25 tool calls) at `5fb2be1ca`. Facts here are Level-1
evidence; any line AUDIT.md relies on is re-verified against source by the main audit and cited
with its command in EVIDENCE_LEDGER.md.

Method: LOC is `wc -l`. Callers were found by an AST import scan of `scripts/**/*.py`, excluding `tests/`, `audits/` and `__pycache__`, plus grep of `*.sh`, `.claude/skills/**`, `docs/runbooks/**`, `.github/**`. `supabase/**` does not exist in this repo.

| file (rel. to scripts/) | LOC | kind | purpose | invoked by | external I/O | core imports |
|---|---|---|---|---|---|---|
| submission_review/__init__.py | 1 | library (package marker) | Reviewer console and extraction package for user product submissions | none found | none | none |
| submission_review/extraction/__init__.py | 0 | library (package marker) | no docstring | 1: agent_reader.py | none | none |
| submission_review/extraction/adapters/__init__.py | 0 | library (package marker) | no docstring | none found | none | none |
| submission_review/extraction/adapters/fake_adapter.py | 68 | test helper | Deterministic adapter for tests and exercising the worker path | 1: prepare_product_submissions.py | none | none |
| submission_review/extraction/adapters/hosted_adapter.py | 457 | library | Bounded Gemini and Groq vision transports for the label-draft contract | 2: diagnose_dsld_extraction.py, prepare_product_submissions.py | Gemini API; Groq API | none |
| submission_review/extraction/adapters/ocr_adapter.py | 644 | library | Deterministic reading of a Supplement Facts panel from OCR geometry | 6: diagnose_dsld_extraction.py, rapidocr_reader.py, agent_reader.py, +3 | none | none |
| submission_review/extraction/adapters/ollama_adapter.py | 391 | library | A local, digest-pinned Ollama adapter | 3: diagnose_dsld_extraction.py, prepare_product_submissions.py, hosted_adapter.py | local Ollama HTTP | none |
| submission_review/extraction/adapters/rapidocr_reader.py | 107 | library | Bind RapidOCR to the reader protocol | 5 | local RapidOCR, PIL, numpy | none |
| submission_review/extraction/agent_reader.py | 617 | CLI (argparse subcommands) | An agent as a reader: reads photographs and files a label_draft_v1 | 1: .claude/skills/product-submissions-prep/SKILL.md:54 (skill) | Supabase edge function `/functions/v1/review-product-submissions`; SUPABASE_ANON_KEY and SUPABASE_SERVICE_ROLE_KEY (line 185); filesystem workdir; RapidOCR | env_loader, product_submission_import |
| submission_review/extraction/benchmark.py | 956 | CLI | Score a candidate extraction configuration against the frozen holdout | 4: prepare_holdout_set.py, catalog_gold.py, development.py, print_fidelity.py | filesystem `reports/submission_holdout`; fcntl lock | none |
| submission_review/extraction/bounded_http.py | 90 | library | One bounded HTTP boundary for private extraction traffic | 7 | generic HTTP | none |
| submission_review/extraction/catalog_gold.py | 584 | library | Match a bottle to a label transcription nobody derived from it | 2: diagnose_dsld_extraction.py, prepare_holdout_set.py | none | label_record_contract (line 30), normalization (line 31) |
| submission_review/extraction/checks.py | 269 | library | Typed findings a careful reader can reach without asking a model | 2: agent_reader.py, extractor.py | none | none |
| submission_review/extraction/development.py | 257 | library | Run the extractor over the development split | 2 | filesystem | none |
| submission_review/extraction/envelope.py | 626 | library | `label_draft_v1`: the provenance-bound partial draft | 12 (incl. skill reference doc) | none (mirrors `supabase/functions/review-product-submissions/schema.ts` in the app repo) | none |
| submission_review/extraction/extractor.py | 387 | library | The extractor boundary: one interface, provider-neutral | 14 | none | none |
| submission_review/extraction/grounding.py | 406 | library | Check that a reading is present in the photograph it cites | 1: extractor.py (named in audit_dead_code.py:68 KEEP) | none | none |
| submission_review/extraction/photo_guidance.py | 71 | library | One conservative photo-section vocabulary | 2 | none | none |
| submission_review/extraction/photo_prep.py | 198 | library | Turn leased evidence into bytes an adapter may see, or refuse | 7 | none | none |
| submission_review/extraction/print_fidelity.py | 486 | CLI | Measure what the shared preparation step costs fine print | none found (tests only) | local RapidOCR, PIL fonts | none |
| submission_review/extraction/queue_client.py | 552 | library (worker transport) | The authenticated queue client | 1: prepare_product_submissions.py | Supabase RPCs ×6; Storage bucket `product-submission-photos`; refuses secret keys in env (:108) | none |
| submission_review/extraction/to_manual_label.py | 234 | library | Turn a `label_draft_v1` reading into a `manual_label_v1` skeleton | 3 | none | none |
| submission_review/extraction/worker.py | 295 | worker (drain loop + heartbeat thread; no `__main__`) | Drain the extraction queue | 2: prepare_product_submissions.py, queue_client.py | none directly | none |
| submission_review/gtin.py | 61 | library | Shared barcode comparison rules | 7 | none | none |
| submission_review/photo_guidance_service.py | 244 | library plus `__main__` subprocess helper | Authorized, bounded local photo guidance | 1: serve.py | Supabase Storage signed URLs; RapidOCR; subprocess | none |
| submission_review/serve.py | 719 | CLI (HTTP server) | Local reviewer console | 2: submission_review/start.sh, prepare_holdout_set.py:293 | Supabase edge-function proxy; `scripts/dist/pharmaguide_core.db` read-only; reads `output_*_enriched/enriched/*.json`; serves static/ | env_loader, stage_manifest |
| submission_review/solo_review.py | 367 | library | Private single-reviewer development results | 1: serve.py | Supabase edge function; `reports/submission_solo/*.json` | none |
| product_submission_import.py | 1543 | CLI | Import human-approved product submissions into the manual-label contract | 4: release_full.sh:429, :568, :951 (release); dsld_validator.py:68; agent_reader.py; skill reference | Supabase RPCs ×3 (secret or service-role key); Storage GET; manual-label output, images, receipts | env_loader, enhanced_normalizer (lazy, :503), submission_review.gtin |

Totals: 27 `.py` files under submission_review = 9,087 LOC; with product_submission_import.py = 10,630 LOC.
Other callers: `scripts/prepare_product_submissions.py` (preflight/status/run/reconcile) is the only entry point that runs `worker.drain`; `prepare_holdout_set.py` and `diagnose_dsld_extraction.py` also import the package.

## Boundary with the pipeline

Direct imports across the boundary:
- `scripts/product_submission_import.py:503`: lazy `from enhanced_normalizer import parse_other_ingredient_disclosure` (submission code → Clean).
- `scripts/dsld_validator.py:68`: lazy `from product_submission_import import _required_uuid` (Clean path → private function of the submission importer; only inside the `external_manual` / `private_product_submission` branch, lines 58-69).
- No imports in either direction with `enrich_supplements_v3`, `scoring_input_contract`, `build_final_db`. No `scripts/*.py` pipeline module imports anything from `submission_review/`.

Other production imports: `env_loader` (import, agent_reader, serve), `stage_manifest` (serve), `label_record_contract` and `normalization` (catalog_gold).

Contract/string coupling without import: `build_final_db.py:1755` (`source_kind == "private_product_submission"`), `enrich_supplements_v3.py:24006-24014` (`manual_product_provenance` / `external_manual` lineage), `enhanced_normalizer.py:384-385`, `:7085-7087`, `dsld_validator.py:63`.

Filesystem coupling: `serve.py:254` reads Enrich output; `:202` the stage manifest; `:286`, `:355`, `:387`, `:657` read `scripts/dist/pharmaguide_core.db` read-only.

Release-train hooks: `release_full.sh:429` (`--fetch`), `:568` (`--copy-images`), `:951` (`--mark-promoted`).

## Non-Python assets

- `scripts/submission_review/`: 4 `.js` (`static/app.js`, `canonical.js`, `solo.js`, `vendor/supabase.js`), `static/index.html`, `static/help.json`, 4 fixture `.json`, 1 `.css`, 2 `.md`, `start.sh`.
- Supabase project lives in `/Users/seancheick/PharmaGuide ai/supabase`: `functions/review-product-submissions/` (20 `.ts`, 3 `.json`), `cleanup-product-submissions/` (3 `.ts`), `notify-new-product-submissions/` (5 `.ts`), `tests/submission_identity/` (15 `.sql`, 2 `.sh`), ~30 of 58 migrations match submission/extraction/reviewer by filename.
- dsld_clean `scripts/sql/` has no submission references.

## Level-2 candidates (agent's list; promotion decided by census criteria)

- `product_submission_import.py`: 1,543 LOC; boundary file (imports `enhanced_normalizer` :503, imported by `dsld_validator.py:68`, called 3× by `release_full.sh`).
- `extraction/benchmark.py`: 956 LOC; CLI with fcntl-locked holdout protocol.
- `extraction/worker.py` + `extraction/queue_client.py`: mutual import (`queue_client.py:36` imports from `worker`).
- `extraction/agent_reader.py`: skill-invoked CLI, 617 LOC, uses `SUPABASE_SERVICE_ROLE_KEY` (:185).
- `serve.py`: 719-LOC HTTP server on the pipeline boundary (stage_manifest, core DB, enriched JSON glob).
- `extraction/catalog_gold.py`: the only extraction module importing production modules.
- `extraction/adapters/hosted_adapter.py`: the only file calling external model APIs.
