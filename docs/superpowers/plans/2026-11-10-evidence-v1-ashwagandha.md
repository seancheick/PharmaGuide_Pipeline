# Evidence V1 ashwagandha implementation plan

**Goal:** A real scan explains bounded human ingredient research independently of marketing, preserves preparation uncertainty, and uses the existing 20-point Evidence calculation.

**Authority:** Sean's explicit implementation approval in attachment cdd7483a-5044-425b-9bb1-e9b2010f38b6, November 10, 2026. This is a NEW V1 applicability policy, not a retrospective clinical signature. The October 28 exact-brand decisions remain historical and exact branded grades are retained.

**Architecture:** Extend canonical reviewed records and the existing clinical applicability matcher. Identified standardized root extracts can receive existing positive_weak ingredient-human support for short-term perceived stress, based on two retained primary trial families. This is a limited class inference, not preparation bioequivalence or proof of product efficacy. Root powder, unknown, root+leaf via root-only trials, ratio-only and novel delivery preparations cannot borrow that grade. All recognized preparations can display the bounded research and its limitations. Sleep is descriptive research, not an expansion of signed numerical endpoints. No claim required.

**Owners:** `backed_clinical_studies.json::INGR_ASHWAGANDHA`; `clinical_applicability.py::assess_clinical_applicability`; `evidence_resolver.py::resolve_product_evidence`; `generic_evidence.py::score_evidence`; `enrich_supplements_v3.py::_collect_evidence_data`; `build_final_db.py` evidence_data projection; Flutter `evidence_section.dart` / `ResearchSupportSection`. Evidence: rg required_form_terms, clinical_matches, source_references, ingredient_research, required_form_groups; matrix/GLOSSARY reviewed. Will NOT create a second engine, scale, registry, generic Dose threshold, safety override or app efficacy computation.

- [ ] Preserve PR430 merge receipt and provisional reference-scope bug patch separately; avoid concurrent rice edits owned by the other thread.
- [ ] Freeze real generic/root-extract/standardized/powder/KSM/Sensoril/Shoden/unknown representatives and source-bound baseline through existing replay. Record absent corpus representatives honestly.
- [ ] Fail-first shared preparation matching tests: optional required_form_groups (AND of OR groups), same source row, affirmative source-only proof; malformed/missing/negated/split-row/excluded preparation fails closed. Existing required_form_terms stays OR. No arbitrary percentage cutoff.
- [ ] Fail-first ingredient research projection tests: canonical consumer_research authored summary, studied_uses and references are informational; export as evidence_data.ingredient_research for an identity-bound match even if product applicability is unestablished. Reject unrelated/unresolved identity and never infer points from this copy.
- [ ] Explicit data_batch patch only INGR_ASHWAGANDHA. Preserve old rejected meta contexts/references; add two V1 contexts attributed to new V1 review, same primary family IDs as exact KSM contexts, factual actual KSM preparation retained. No duplicated enrollment or branded/generic stacking. No unread meta preparation-table claim. Record new decision and reviewer separately.
- [ ] App fail-first malformed/null/informational-only/unknown preparation tests, then render producer strings and citations in existing Evidence surface. No hardcoded ingredient claims or rating computation.
- [ ] Review source actual methods/results and independent policy/source receipts; measure before/after points/totals/status/citations and unchanged safety/identity/amount/Dose/Formulation on frozen real labels.
- [ ] One completed combined owner/local/hosted CI/native replay/Core/performance checkpoint and independent review, then authorized integration. Native app screenshot/journey requires explicit simulator/build/catalog identity, not source-green inference.
- [ ] Fresh global census after integration using current stage fingerprints; apply the qualified shared rule only where existing reviewed sources support it. Keep GLN numerical HOLD. Publication/release separate.

**Verification:** `scripts/test.sh fast <focused owners>` for iteration; one `scripts/test.sh local` plus hosted complete CI at finished checkpoint. Flutter supported make test/check commands. No full corpus per edit. Source qualification, code integration, installed-data parity, publication and observed app behavior reported separately.

## Final bounded qualification notes

The finite-review distinction is limited to fully reviewed **ingredient_general** contexts. Exact-form and branded-material unknowns remain held, as required by the creatine/nattokinase/glutathione controls. Canonical historical citations are retained, but accepted clinical-match citations follow qualified contexts; generic ashwagandha contributes two RCTs and zero meta-reviews. Literal source-note provenance fixes actual GNC18343 and Solgar201708 without a percentage cutoff. New policy/source attribution is recorded in `scripts/audits/evidence_v1_ashwagandha_20261110/research.md`.

Corrected final owner checkpoint: 1498 passed, one declared missing-built-interaction artifact skip. Final exact-source26 native captures include six held/control labels and preserve all five non-Evidence pillars. Broader local, performance explanation, native final frames and exact hosted CI are separate gates before merge.
