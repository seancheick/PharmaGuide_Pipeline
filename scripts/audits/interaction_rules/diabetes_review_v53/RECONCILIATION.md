# Diabetes Rule Review — Reconciliation Report

**Reviewer baseline**: `ingredient_interaction_rules_Reviewed.json` @ schema 5.2.0, 129 entries
**Live baseline**: `ingredient_interaction_rules.json` — started at 5.3.0, now at **6.1.0** (145 entries)
**Generated**: 2026-05-05
**Last updated**: 2026-05-06
**Scope**: Full reconciliation — Phase 1 (content cleanup), Phase 1.5 (new-entry clinical review), Phase 2 (hypoglycemics split)

---

## Ship log

| Phase | Schema | Commits | Date | What shipped |
|---|---|---|---|---|
| Phase 1 | 5.3.1 → 5.3.3 | Multiple | 2026-05-05 | 10 APPLY items: mechanism rewrites, evidence-level corrections, headline refresh |
| Phase 1.5 | 6.0.3 | `f6b2478` | 2026-05-06 | Clinical review of 16 new entries: 1 ghost PMID removed, 5 dead URLs replaced, copy fixes |
| Phase 2 | 6.1.0 | `9bf00d1` + `d7bcd4d` | 2026-05-06 | Hypoglycemics 3-way split (high_risk / lower_risk / unknown) + Flutter adoption |
| v6.0 profile_gate | 6.0.0 → 6.0.2 | Multiple | 2026-05-05 | profile_gate schema on every sub-rule; Flutter evaluator + drift contract |
| URL-rot audit | 6.1.0 | `9f227e8` | 2026-05-06 | 23 dead URLs replaced with verified PubMed PMIDs across all 145 entries |
| Full clinical sweep | 6.1.0 | Multiple | 2026-05-06 | All 14 condition batches reviewed: 210→196 rules, 14 deduped, zero templates remaining |
| Flutter UX | — | Multiple | 2026-05-06 | Splash, onboarding, medication entry, fit score, product detail, profile labels |

---

## Snapshot delta (5.2.0 → 5.3.0 → 6.1.0)

- **126** rules in both the reviewer's file and the original 5.3.0 baseline
- **16** rules added since reviewer's snapshot — **all 16 clinically reviewed in Phase 1.5**
- **1** rule renamed/removed (`silymarin` in 5.2.0 → no exact match in 5.3.0)
- **3** new drug-class IDs added in Phase 2: `hypoglycemics_high_risk`, `hypoglycemics_lower_risk`, `hypoglycemics_unknown`

### 16 entries added since reviewer (Phase 1.5 — DONE)

| db | canonical_id | Phase 1.5 verdict |
|---|---|---|
| banned_recalled_ingredients | ADD_HORDENINE | PASS |
| banned_recalled_ingredients | BANNED_BITTER_ORANGE | EDIT — URL slug fix |
| banned_recalled_ingredients | BANNED_PENNYROYAL | EDIT — dead NCCIH URL → PMIDs 8633832 + 25512112 |
| banned_recalled_ingredients | BANNED_TANSY | EDIT — near-ghost NBK → PMID 28472675 |
| harmful_additives | ADD_TYRAMINE_RICH_EXTRACT | EDIT — fixed truncated alert_body + informational_note |
| botanical_ingredients | bupleurum_root | EDIT — generic FDA URL → PMID 33273809 (CYP2D6 primary) |
| botanical_ingredients | ginkgo_biloba_leaf | PASS |
| botanical_ingredients | white_mulberry | **BLOCK resolved** — ghost PMID 27092496 removed → PMID 27974904; evidence established→probable |
| ingredient_quality_map | bromelain | EDIT — removed unsupported warfarin case-report sentence |
| ingredient_quality_map | holy_basil | PASS (theoretical + generic landing acceptable) |
| ingredient_quality_map | l_carnitine | PASS |
| ingredient_quality_map | l_tryptophan | EDIT — dead ODS URL → PMID 31523132 |
| ingredient_quality_map | maca | EDIT — dead NCCIH URL → PMID 38440178 |
| ingredient_quality_map | phenylethylamine | PASS |
| ingredient_quality_map | same | EDIT — dead NCCIH URL → PMID 38423354 |
| ingredient_quality_map | sodium | EDIT — dead ODS URL → PMID 9022564 |

Full audit trail: `scripts/audits/interaction_rules/phase_1_5/CLINICAL_REVIEW.md`

---

## Reviewer worklist — final status

| # | Ingredient | Reviewer recommendation | Final status | Shipped in |
|---|---|---|---|---|
| 1 | aloe_vera | evidence theoretical → limited + oral/topical note | **SHIPPED** | Phase 1 (5.3.1) |
| 2 | alpha_lipoic_acid | soften severity for low-risk users | **SHIPPED** | Phase 2 (6.1.0) — lower_risk=monitor, high_risk=caution, unknown=caution |
| 3 | berberine_supplement | caution by default, avoid only with insulin/sulfonylurea | **SHIPPED** | Phase 2 (6.1.0) — high_risk=avoid, lower_risk=caution, unknown=caution |
| 4 | bitter_melon | remove "plant insulin analog" framing | **SHIPPED** | Phase 1 (5.3.1) |
| 5 | black_seed_oil | downgrade unless dose/extract standardized | **PARTIALLY SHIPPED** | Phase 2 (6.1.0) — lower_risk=monitor. Full dose gate still needs authoring |
| 6 | chromium | tighten mechanism wording | **SHIPPED** | Phase 1 (5.3.1) |
| 7 | cinnamon | acknowledge mixed evidence | **SHIPPED** | Phase 1 (5.3.1) |
| 8 | fenugreek | action-oriented headline | **SHIPPED** | Phase 1 (5.3.1) |
| 9 | fiber | add medication-timing informational_note | **SHIPPED** | Phase 1 (5.3.1) |
| 10 | garlic | diabetes severity caution → monitor | **SHIPPED** | Phase 1 (5.3.1) |
| 11 | ginseng | keep | **DONE** (no change needed) | — |
| 12 | gymnema_sylvestre | remove "beta-cell regeneration" claim | **SHIPPED** | Phase 1 (5.3.1) |
| 13 | inositol | keep | **DONE** (no change needed) | — |
| 14 | l_carnitine | keep | **DONE** (no change needed) | — |
| 15 | magnesium | evidence established → probable | **SHIPPED** | Phase 1 (5.3.1) |
| 16 | olive_leaf | dose/extract gate | **DONE** (already dose-gated) + Phase 2 split | — |
| 17 | psyllium | add medication-timing note | **SHIPPED** | Phase 1 (5.3.1) |
| 18 | stinging_nettle | downgrade unless strong extract/dose | **PARTIALLY SHIPPED** | Phase 2 (6.1.0) — lower_risk=monitor. Extract/dose gate still pending |
| 19 | tribulus | evidence probable → limited | **SHIPPED** | Phase 1 (5.3.1) |
| 20 | vanadyl_sulfate | add toxicity safety note | **SHIPPED** | Phase 1 (5.3.1) |
| 21 | vitamin_b3_niacin | dose-gate | **DONE** (already dose-gated) | — |
| 22 | vitamin_d | downgrade to informational unless deficient | **BLOCKED** | Needs user-profile lab/deficiency state |
| 23 | white_mulberry | scope to leaf extract / DNJ-standardized | **BLOCKED** | Needs form-scoped variant architecture |

**Scorecard: 17 shipped, 2 partially shipped, 2 blocked, 2 were already done.**

---

## Phase 2: Hypoglycemics split — SHIPPED (6.1.0)

Replaced the single broad `hypoglycemics` drug class with three risk-stratified subclasses:

| Subclass | Drugs | User-facing label |
|---|---|---|
| `hypoglycemics_high_risk` | insulin, sulfonylureas, meglitinides | Insulin, Sulfonylureas, Meglitinides |
| `hypoglycemics_lower_risk` | metformin, GLP-1 RAs, SGLT2i, DPP-4i | Metformin, GLP-1 RAs, SGLT2i, DPP-4i |
| `hypoglycemics_unknown` | legacy / unrefined profiles | Diabetes medication (tap to specify) |

Severity remapping (18 rules × 3 subclasses = 54 drug_class_rules):

| Rule category | high_risk | lower_risk | unknown |
|---|---|---|---|
| 7 monitor rules (cinnamon, chromium, etc.) | monitor | monitor | monitor |
| 9 caution rules (alpha-lipoic, bitter melon, etc.) | caution | monitor | caution |
| berberine (avoid) | avoid | caution | caution |
| niacin (raises glucose — same for all) | caution | caution | caution |

Flutter migration: legacy `hypoglycemics` → `hypoglycemics_unknown` (not false-precision high_risk). Profile-setup shows all three options for refinement. IDs normalized with `trim().toLowerCase()`.

Clinical rationale: per Dr. Pham review — auto-mapping to high_risk creates false precision and perpetuates the over-warning problem. Unknown = honest uncertainty with middle-ground caution.

---

## What's next (remaining backlog)

### Still blocked (needs new architecture)

| Item | Blocker | Effort |
|---|---|---|
| vitamin_d — downgrade to informational unless deficient | Engine has no `lab_status` / deficiency state in user profile | ~4h (profile schema + UI + rule gating) |
| white_mulberry — scope to DNJ-standardized leaf extract | Needs `form_scope` variant architecture (product-level form matching) | ~3h |
| black_seed_oil — full dose/extract gate | Dose threshold authoring for thymoquinone-standardized extracts | ~2h |
| stinging_nettle — extract/dose gate | Same pattern as black_seed_oil | ~1h |

### Cross-repo operational

| Item | Status |
|---|---|
| Run pipeline to push v6.1.0 catalog to Supabase production | Pending — `batch_run_all_datasets.sh` |
| v6.1 cleanup — remove legacy `matchesProfile` fallback in Flutter | ~30 days post-rollout (marked with `TODO(v6.1)`) |
| Drop pre-6.0 schemas from `import_catalog_artifact.sh` whitelist | Coordinate with v6.1 cleanup |
| Systemic NIH URL-rot audit (5/9 NCCIH/ODS URLs in Phase 1.5 batch were 404) | Needs a sweep of all 145 entries |

### Source verification (completed for Phase 1.5 entries)

All Phase 1.5 replacement PMIDs were content-verified via PubMed eutils (esummary + efetch abstract). Audit trail in `scripts/audits/interaction_rules/phase_1_5/`:
- `CLINICAL_REVIEW.md` — per-entry verdicts
- `pubmed_candidates.json` — search results
- `abstracts.txt` — fetched abstracts for verified candidates

Phase 1 source URLs (NCCIH, PMC, LiverTox) verified during the original Phase 1 work.

---

## Commit reference

| Commit | Repo | What |
|---|---|---|
| Phase 1 series | dsld_clean | 5.3.1 → 5.3.3 mechanism rewrites, evidence corrections, headlines |
| `f6b2478` | dsld_clean | Phase 1.5 — ghost PMID, dead URLs, copy fixes (6.0.3) |
| `9bf00d1` | dsld_clean | Phase 2 — hypoglycemics 2-way split (6.1.0) |
| `d7bcd4d` | dsld_clean | Phase 2 — add hypoglycemics_unknown bucket |
| `1778bdd` | Pharmaguide.ai | Flutter — adopt hypoglycemics split + high_risk migration |
| `297c4fc` | Pharmaguide.ai | Flutter — adopt unknown migration per Dr. Pham review |
