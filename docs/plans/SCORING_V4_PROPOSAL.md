# Scoring v4 Proposal — Class-Aware Quality + Hard Safety Gates

**Status:** DRAFT — working document
**Owners:** Sean (product), Claude + Codex (engineering)
**Started:** 2026-05-18
**Last updated:** 2026-05-18
**Supersedes:** N/A (v3 scoring remains in production until v4 cutover gate passes)

This document is the single source of truth for the v4 scoring redesign.
Edit it as decisions land. Never delete sections — strike through superseded
content with a dated note.

---

## 1. Why we are doing this

v3 scoring uses one rubric for every supplement. That creates structural
unfairness for classes where the underlying signals are categorically different:

| Symptom | Example | Root cause |
|---|---|---|
| Good probiotics underscored | Garden of Life Once Daily Prenatal Probiotic (DSLD `274081`) = `45.6/100`. Has 20B CFU, 16 named species, HN001 clinical strain, NSF, vegan, gluten-free. | B5 proprietary blend penalty (`-9`) treats a probiotic blend with named strains identically to an opaque stimulant blend. Probiotic category bonus capped at `+3`. |
| Cert overcredit on premium singles | Thorne Magnesium Bisglycinate = `72.6/100`. Score depends on B4a stacking `NSF Sport + NSF Certified + USP Verified = +15` with no per-SKU verification. | B4a = `5 pts × len(programs)` capped at 15 ([`score_supplements.py:2073`](../../scripts/score_supplements.py#L2073)). Worse: manufacturer-level injection ([`enrich_supplements_v3.py:9089`](../../scripts/enrich_supplements_v3.py#L9089)) propagates brand-level certs onto every SKU of that brand. |
| Incomplete multivitamins overscored | Nature Made Adult Gummies ≈ `79.1/100`. Common gummy multis lack iron/iodine/choline/DHA but get full broad-mapping credit. | v3 has no "completeness of expected micronutrient panel" concept for multivitamin/prenatal classes. |
| Nutrient evidence under-credited | Thorne Magnesium scores only `5.76/20` for evidence (Section C). | Evidence scorer demands product-level PMID citations; nutrient-level RCT evidence (NCCIH, NIH ODS) is under-credited. |
| Discontinued products mixed into live catalog | `~2009` discontinued products in the shipped bundle. | No active-only release gate. Stale-label trust risk. |
| Probiotic prebiotic credit missing | Garden of Life Once Daily Prenatal Probiotic has an organic prebiotic fiber blend (potato, acacia), but `probiotic_detail` does not reliably credit `prebiotic_present`. | Probiotic scoring path has a gap. Captured as P0/P1 audit fix. |

**We are not making scoring "softer." We are making it class-correct.** The
better model will simultaneously: raise true premium singles modestly, lift
good probiotics, lower incomplete gummies/multis, sharply penalize risky
opaque stimulant blends, and gate unsafe products entirely outside the
quality score.

---

## 2. Pipeline shape

v4 keeps the existing pipeline stages and adds (a) a v4 shadow scorer that
runs alongside v3, and (b) a live-catalog gate at the build step.

```
raw DSLD
  └─ clean_dsld_data.py
       └─ enrich_supplements_v3.py
            (emits identity, dose, forms, safety, cert claims,
             blend/probiotic detail, certification_data with 3-tier split)
            ├─ score_supplements.py              # v3 — stays default until cutover
            └─ score_supplements_v4_shadow.py    # NEW — shadow, emits shadow_score_v4_* cols
                 └─ build_final_db.py
                      ├─ live catalog: active + complete + scored only
                      └─ archive/QA bundle: discontinued, incomplete, NOT_SCORED
```

No production scoring changes until v4 shadow passes canary rank order
and full-catalog deltas review (see §15 Shadow Report Requirements).

---

## 3. Live catalog gates

These are **release gates**, not scoring dimensions. The live Flutter
catalog must satisfy every gate. Products that fail any gate go to the
archive/QA bundle and never reach the app.

| Gate | Live requirement |
|---|---|
| Product status | `product_status = active` |
| Scoring status | no `verdict = NOT_SCORED` rows in live catalog |
| Detail blob | every live row has a valid blob + blob SHA |
| Safety consistency | no SAFE row with banned/recalled/critical warning |
| Canonical IDs | required for interaction-bearing actives (drug-interaction lookups depend on these) |
| Flutter contract | all emitted enums parse and render |
| Completeness | class-specific minimum fields present (see §4 Layer 2 table) |

The completeness gate uses **class-aware required fields** — a probiotic
without per-strain CFU is still eligible (we score it with moderate
confidence). A stimulant blend without doses is also eligible (we score
it with CAUTION + heavy opacity penalty). The gate excludes products the
scorer literally cannot score, not products the scorer can warn about.

---

## 4. Architecture

Four independent layers. Safety never bleeds into quality. Confidence is
metadata, not a score adjustment.

```
┌──────────────────────────────────────────────────────────┐
│ Layer 1: SAFETY GATE              (hierarchical, blocking) │ → verdict / blocking_reason
├──────────────────────────────────────────────────────────┤
│ Layer 2: LIVE-CATALOG ELIGIBILITY (class-aware fields)     │ → is_live_eligible
├──────────────────────────────────────────────────────────┤
│ Layer 3: CLASS-AWARE SCORE        (0–100, per-class)       │ → score_100
├──────────────────────────────────────────────────────────┤
│ Layer 4: CONFIDENCE BAND          (metadata)               │ → confidence
└──────────────────────────────────────────────────────────┘
```

### Layer 1 — Safety gate

Precedence: **BLOCKED > UNSAFE > CAUTION > NOT_SCORED > POOR > SAFE**.

| Tier | Triggers | Verdict |
|---|---|---|
| Regulatory | Banned/recalled active; FDA Class I recall; DEA-scheduled | **BLOCKED** |
| Hard contraindication | Adulterant, undeclared Rx, life-stage contraindicated (e.g. yohimbine in pregnancy) | **BLOCKED** or **UNSAFE** by class |
| Dose excess | `B7`: >150% UL without life-stage-specific hazard | score penalty only; verdict stays driven by other gates |
| Life-stage-sensitive dose hazard | e.g. retinol vitamin A or iron excess in pregnancy, where evidence/policy says dose creates direct risk | **UNSAFE** or **BLOCKED** by policy |
| Interaction (profile-gated) | Curated interaction with declared medication | **CAUTION** |
| Opacity with risk | Stimulant/nootropic blend with undisclosed doses | **CAUTION** |
| Opacity without risk | Probiotic blend with named strains but no per-strain CFU | **SAFE** + confidence flag |
| Clean | None of the above | **SAFE** |

**Key change vs v3:** opacity is no longer class-blind. A hidden CFU in a
probiotic is not the same risk as a hidden stimulant dose.

### Layer 2 — Live-catalog eligibility gate (class-aware)

**Naming:** the gate produces a boolean `is_live_eligible`. Products that
fail go to `verdict = NOT_SCORED` in the archive/QA blob, but **the live
catalog filters them out entirely** — the Flutter app never displays
NOT_SCORED.

```
completeness fail  →  is_live_eligible = false  →  excluded_from_live_catalog
                      verdict = NOT_SCORED (archive only)
```

**Class-aware required fields.** A single threshold like "≥ 80% of actives
have normalized dose" wrongly excludes products we explicitly want to
score — a probiotic with named strains + total CFU but no per-strain CFU
is exactly the case the probiotic module is designed to score (Garden of
Life Prenatal Probiotic). Required fields vary by class:

| Class | Hard-required for eligibility | Soft-required (lowers confidence band, doesn't gate) |
|---|---|---|
| **Generic mineral / single nutrient** | Active identity (canonical_id), elemental dose + unit, form_factor | Synergy cluster, evidence band |
| **Generic vitamin** | Active identity, dose + unit, form, life-stage applicability | RDA cohort, NCT references |
| **Generic botanical** | Active identity, extract ratio OR standardization marker, plant part, dose | Branded extract identity (KSM-66, Meriva) |
| **Generic omega-3** | EPA + DHA dose, source (fish/krill/algae), oxidation/IFOS status | EPA:DHA ratio, lot star rating |
| **Probiotic** | Total CFU, ≥1 named strain, active identity, safety parsed | Per-strain CFU, clinical strain code, delivery tier |
| **Multi / prenatal** | Class detected, ≥ 60% of expected micronutrient panel present with dose | Methylfolate vs folic acid, DHA presence, choline presence |
| **Stimulant / nootropic blend** | Active identity for the named blend components, total dose | Per-component dose (missing → strong opacity penalty, NOT exclusion) |

**Key principle:** missing dose on a stimulant blend does **not** exclude
the product. It still ships, but with `verdict = CAUTION` and a heavy B5
opacity penalty. The gate exists to exclude products the scorer literally
cannot score, not to hide risky products from users.

**Class-agnostic minimums (apply to all classes):**

| Field | Threshold |
|---|---:|
| `mapped_coverage` (identity) | ≥ 0.85 |
| `form_factor` resolved | required |
| Class detection confidence | ≥ 0.80 (else routes to `generic`) |
| `product_status` | `active` |

### Layer 3 — Class-aware quality score

A router picks one of three modules. v1 ships three only — everything else
falls through to `generic`.

| Module | Covers | Why first |
|---|---|---|
| `generic` | Single-ingredient supplements; simple stacks (Mg, vit D, single-strain fish oil, single-extract botanical) | ~70% of catalog |
| `probiotic` | `supplement_type=probiotic` | Most structurally underscored today |
| `multi_or_prenatal` | Multivitamin, prenatal multi, men's/women's complete formulas | Stacked-credit + completeness issues |

Shared spine, class-tuned weights:

| Dimension | generic | probiotic | multi/prenatal |
|---|---:|---:|---:|
| Formulation quality | 30 | 25 | 25 |
| Dose / clinical relevance | 25 | 25 | 30 |
| Evidence strength | 20 | 20 | 15 |
| Testing & manufacturing trust | 15 | 15 | 15 |
| Transparency | 10 | 15 | 15 |
| **Total** | **100** | **100** | **100** |

### Layer 4 — Confidence band (typed metadata)

Per Codex review-pass: avoid "confidence" becoming a junk-drawer field.
Split drivers into typed sub-categories so each kind of uncertainty can
be tracked, displayed, and audited independently.

```json
"confidence": {
  "band": "high | moderate | low",
  "score_uncertainty_pts": 3,
  "evidence": {
    "level": "high | moderate | low",
    "drivers": ["product_specific_nct_absent", "indication_relevance_partial"]
  },
  "label_completeness": {
    "level": "high | moderate | low",
    "drivers": ["per_strain_cfu_not_disclosed"]
  },
  "verification": {
    "level": "high | moderate | low",
    "drivers": ["cert_sku_verified", "manufacturer_signal_present_no_sku_match"]
  },
  "identity": {
    "level": "high | moderate | low",
    "drivers": []
  }
}
```

The four sub-categories map to four distinct failure modes:

| Sub-category | What it tracks | Example driver |
|---|---|---|
| `evidence` | Strength of clinical/nutrient evidence basis | "product_specific_nct_absent", "human_rct_lacking", "animal_only_evidence" |
| `label_completeness` | What the product disclosed vs. should have disclosed | "per_strain_cfu_not_disclosed", "extract_ratio_absent", "epa_dha_breakdown_missing" |
| `verification` | Quality of third-party verification | "cert_sku_verified", "cert_product_line_only", "ifos_lot_5_star", "claimed_only_no_registry" |
| `identity` | Canonical-ID and form-resolution confidence | "canonical_id_fuzzy_match", "form_factor_inferred", "supplement_type_low_confidence" |

`band` (top-level) is derived from the four sub-levels via a simple
worst-case rule: `band = min(evidence, label_completeness, verification, identity)`.
Flutter uses `band` for the dimmed/asterisked rendering and shows the
typed drivers in the expanded score-detail view. The number itself
never changes based on confidence.

### Score scale anchors

Per Codex review-pass: "100 unreachable" is philosophically right but
operationally vague. Three explicit anchors so reviewers know what's
possible vs. expected vs. observed.

| Anchor | Definition | Implication |
|---|---|---|
| **Theoretical maximum: 100** | Sum of all dimension caps for a class. Mathematically achievable if every signal is maxed | Stays unreachable in practice — included so the scale has headroom |
| **Practical maximum: ~95** | Achievable by a real product with: SKU-verified multi-program testing, product-specific NCT trial(s), perfect identity match, optimal class-appropriate dose, zero ancillary excipients, published lot-level COA | Reserved for genuinely best-in-class products. Expected catalog frequency: < 0.5% of live products |
| **Observed ceiling (v1)** | The highest score any v1-shipped product actually reaches. Captured in the first shadow report and re-confirmed each release cycle | Likely ~88–92 in the early shadow runs. If a product hits > 92, audit the breakdown before accepting the score |
| **Premium ceiling (typical)** | The expected score range for products we call "premium" (Thorne, Nordic Naturals, FullWell, Visbiome) | 82–92 |
| **Quality floor (live catalog)** | The lowest score a product can have and still ship to the live catalog | ~20. Anything lower indicates a CAUTION/UNSAFE verdict, BLOCKED, or live-eligibility failure |

If any canary product or shadow result lands above the observed ceiling
in a release cycle, the breakdown must be reviewed before merging. This
is the operational version of "score inflation guard" — it's not about
penalizing high scores, it's about confirming the high score is earned.

---

## 5. B5 opacity policy (class-aware)

Opacity is no longer class-blind. A hidden CFU in a probiotic and a hidden
stimulant dose are different risks and earn different penalties:

| Product type | Missing detail | Effect |
|---|---|---|
| **Probiotic** | per-strain CFU hidden, strains named, total CFU shown | Moderate score/confidence penalty (–3 to –5). SAFE verdict. Confidence band: moderate. UI caveat: "Strain-level CFU not disclosed." |
| **Stimulant / nootropic** | per-component stimulant dose hidden | **CAUTION verdict**. Severe opacity penalty (–10 to –15). Cannot reach SAFE |
| **Mineral chelate** | elemental dose and form both disclosed | No opacity penalty. (Chelated minerals routinely use named complexes; the dose math still works.) |
| **Botanical** | no plant part / no standardization / no extract ratio | Quality + transparency penalty (–4 to –8) |
| **Multi / prenatal** | proprietary blend hides expected micronutrient doses | Penalty (–6 to –10) OR live-catalog eligibility failure when blend hides >40% of expected panel |
| **Generic blend (greens, AG1-style)** | total ingredient count high, per-component dose hidden | Penalty (–5 to –10), CAUTION verdict triggered when blend includes interaction-bearing actives |

**Rule of thumb:** the penalty scales with **what the hidden dose
prevents you from knowing**. Hidden per-strain CFU on a named-strain
probiotic prevents you from judging clinical dose adequacy (modest
penalty). Hidden stimulant dose prevents you from judging safety
(severe penalty + verdict change).

---

## 6. Per-class rubric — Probiotic module

This rubric **preserves v3's `probiotic_bonus` + `probiotic_cfu_adequacy`
+ blend transparency logic** and rebalances them into the 5 v4 dimensions.
Nothing about CFU adequacy, strain identification, or category gating is
new — it's reorganized.

| Item | Max | v3 source | Earned by |
|---|---:|---|---|
| **Formulation quality (25)** | | | |
| Total CFU disclosed | 4 | A.probiotic_bonus + probiotic_cfu_adequacy.hard_gates.require_cfu_guarantee | `total_cfu` present |
| ≥10B CFU appropriate for class | 4 | A.probiotic_bonus tier | Tiered by indication (gut, immune, vaginal, infant, etc.) |
| Named species (≥3) | 4 | A.probiotic_bonus.non_probiotic_strict_gate.min_strain_id_count | `strain_count_named >= 3` |
| Exact clinical strain codes (HN001, BB-12, GG, 35624…) | 4 | A.probiotic_bonus.non_probiotic_strict_gate.min_clinical_strain_count | `clinical_strain_id` present |
| Delivery (delayed release, enteric, lyophilized) | 4 | A3 delivery_system | `delivery_tier` |
| Prebiotic complement disclosed | 5 | A.probiotic_bonus.prebiotic_terms | `prebiotic_present` (folded into formulation, NOT a separate bonus) |
| **Dose / clinical relevance (25)** | | | |
| Per-strain CFU disclosed | 15 | (new — preserves the principle that CFU adequacy is per-strain) | `per_strain_cfu_present=true` |
| Strain CFU adequacy (clinical-trial range match) | 10 | **probiotic_cfu_adequacy** — tier (low 0 / adequate 1 / good 2 / excellent 3) × support level (high 1.0 / moderate 0.75 / weak 0.5), capped at +5 in v3 → scaled to /10 in v4 module | Per-strain CFU compared to strain's clinical-trial dose, weighted by evidence support level |
| **Evidence (20)** | | | |
| Strain-clinical / clinical_strain study credit (per-strain, multiplicative pipeline) | 12 | C section: `study_type_base_points.clinical_strain = 4` × `evidence_level_multipliers.strain-clinical = 0.65` × effect/enrollment/dose multipliers × top-N weight + depth_bonus, capped at `cap_per_ingredient = 7` per strain | PMID content-verified evidence for the named strain |
| Indication relevance to product positioning | 8 | C.effect_direction_multipliers (positive_strong 1.0 / mixed 0.6 / null 0.25 / negative 0.0) | Strain evidence supports the product's marketed indication |
| **Testing & trust (15) — hard-clamped at 15 across B4a + B4b + B4c** | | | See §10 cert verification |
| Third-party SKU-verified (B4a) | up to 10 (with diminishing returns) | B4a, now SKU-scope-gated | `cert_verified_for_sku=true` required |
| GMP / facility audit (B4b) | up to 4 | B4b unchanged | Verified GMP cert |
| Batch traceability (B4c) | up to 1 | B4c.coa(1) + batch_lookup(1) → contribute toward 15 cap | Public lot-COA or batch lookup |
| **Transparency (15)** | | | |
| All strain identities named on label (regardless of whether a "Probiotic Blend" container is used) | 8 | B5 proprietary_blends, class-aware: not penalized if strain identities are disclosed | Per Codex correction: the rule is **strain identities disclosed**, not the absence of the word "blend" |
| Per-strain CFU on label | 7 | B5 transparency state | Intentionally double-counts with the Dose dimension (strong signal) |
| **Penalties (subtracted from dimension totals)** | | | |
| B1 harmful_additives | up to −15 | B1.cap = 15, critical −3 / high −2 / moderate −1 / low −0.5 per additive | Applied against Formulation |
| B1 dietary sugar penalty | up to −1.5 | B1_dietary_sugar_penalty.cap = 1.5 | Applied against Formulation |
| B2 allergen presence penalty | up to −2 | B2.cap = 2, severity_points high 2.0 / moderate 1.5 / low 1.0 | Applied against Transparency (allergens are disclosure facts) |
| B5 opacity-with-named-strains | up to −5 | B5 class-aware (probiotic): named strains + total CFU but no per-strain CFU → moderate penalty | §5 |
| B6 marketing penalty | −5 | B6.penalty = 5 | Layer 1 CAUTION + Transparency penalty |
| B7 dose safety penalty (>150% UL — rare for probiotics) | up to −3 | B7.single_penalty = 2, cap = 3 | Applied against Dose |
| **Bonuses (added separately, count toward dimension caps)** | | | |
| B3 claim_compliance bonus (allergen-free / gluten-free / vegan/vegetarian) | up to +4 | B3.cap = 4 | Folded into Transparency (display claims, capped) |

**Expected outcome — Garden of Life Once Daily Prenatal Probiotic (`274081`):**

| Dimension | Math | Subtotal |
|---|---|---:|
| Formulation | total CFU 4 + ≥10B 4 + 16 named 4 + HN001 4 + capsule 3 + prebiotic 5 = 24 | **24 / 25** |
| Dose | per-strain CFU hidden 0/15 + CFU adequacy (HN001 unknown CFU × moderate support 0.75 = 0) = 0 | **0 / 25** |
| Evidence | HN001 strain-clinical (4 × 0.65 × positive_strong 1.0 ≈ 2.6, but cap_per_ingredient 7 allows scaling × enrollment 1.0 × top-N 1.0 + depth 0 ≈ 8) + indication relevance (mostly infant outcomes, prenatal partial = 4) | **12 / 20** |
| Testing & trust | NSF if SKU-verified 8 + GMP 4 + no batch COA 0 = 12, under 15 cap | **12 / 15** |
| Transparency | strain identities 8 + per-strain 0 + B3 claim bonus (vegan +1, gluten-free +1, allergen-free +0 = +2) − allergen penalty 0 = 10, capped at 15 | **10 / 15** |
| Penalties | B1 additives 0 (NSF clean) − B1 sugar 0 − B6 0 = 0 | **0** |
| **Total** | | **~58 / 100** |

SAFE verdict, **moderate** confidence band, UI caveat "Strain-level CFU not
disclosed." Lands in the agreed `50–60` band.

---

## 7. Per-class rubric — Multi / Prenatal module

Differences from generic:

- **Micronutrient panel completeness** is scored, not a precondition.
  Multivitamins are judged on what they include.
- **Dose adequacy is RDA/AI-anchored**, not "premium form" — 50% of RDA
  across the board is worse than 100% with simpler forms.
- **Prenatal sub-class** specifically checks: folate (methylfolate preferred),
  iron, iodine, choline, DHA. Missing 2+ critical nutrients = floor at 60.
- **Form quality** is secondary to coverage.

Detailed sub-rubric TBD in P3. Anchor canary set is the gate before locking.

---

## 8. Per-class rubric — Generic module

Inherits v3 Section A logic — form/bioavailability/synergy/delivery/
absorption — with the P0 integrity fixes baked in.

> **Important fix from Sean's review-pass:** A1 IS the form bioavailability
> mapping. The IQM `bio_score` is computed *from* the matched form. There
> is no separate "mapped to a form" line. Earlier drafts double-counted
> this and inflated the dimension. **One line: form-specific bioavailability
> (bio_score).** Other A2–A6 sub-components stay distinct because they
> measure different things (premium forms beyond the first, delivery
> system, absorption pairing, formulation excellence, single-ingredient
> efficiency).

### Generic rubric — line by line

| Item | Max | v3 source | Earned by |
|---|---:|---|---|
| **Formulation quality (30)** | | | |
| Form-specific bioavailability (IQM bio_score) | 15 | **A1 bioavailability_form** (v3 cap 18, scaled to 15). This IS the form mapping; no separate "mapped to a form" line | bio_score from IQM, weighted by ingredient share of formula |
| Premium forms bonus (additional premium forms beyond the primary) | 4 | A2 premium_forms (v3 cap 5). Skip-first-premium-form rule preserved | +0.5 per additional premium form when at least one ingredient ≥ A2.threshold_score |
| Delivery system | 3 | A3 delivery_system (v3 cap 3) | Tier 1 (liposomal, enteric, sustained-release) = 3, Tier 2 = 2, Tier 3 = 1 |
| Absorption enhancer pairing | 3 | A4 absorption_enhancer (v3 cap 3) | Bioperine + curcumin, vit C + iron, etc. — paired enhancement |
| Formulation excellence (rollup) | 4 | **A5 formulation_excellence** (v3 cap 4). Includes the 4-tier synergy cluster | organic +1, standardized botanical +1, **synergy cluster tier 1 +1.0 / tier 2 +0.75 / tier 3 +0.5 / tier 4 +0.25**, non-GMO Project Verified +0.5, natural source +1 |
| Single-ingredient efficiency | 1 | A6 single_ingredient_efficiency (v3 cap 3, scaled down to 1). Already covered by A1 bio_score for premium chelated singles | +1 for single-ingredient products with bio_score ≥14 |
| Enzyme recognition (single-ingredient enzyme products only) | up to 2 | enzyme_recognition (v3 cap 2.5, +0.5 per named enzyme; requires named enzyme) | Counts named enzymes; lives in Formulation for single-ingredient enzyme products. Enzymes inside a blend route through B5 opacity instead |
| **Dose / supplemental adequacy (25)** | | | |
| Dose inside the supplemental window | 22 | (new framing) — replaces the v3 implicit "% of RDA" assumption | `max(0, RDA − typical_dietary_intake) ≤ supplemental_dose ≤ supplemental_UL`. Per NIH ODS: supplemental UL is explicit and excludes food-source intake |
| Multi-form complex bonus (e.g., Mg glycinate + malate + citrate) | 3 | (new — captures the "multi-form is more complete" intuition) | When ≥2 premium forms of the same nutrient are present |
| B7 dose safety penalty (>150% UL) | up to −3 | **B7 dose_safety**: single_penalty 2.0, cap 3.0, threshold_pct 150 | At >150% of UL, NOT a verdict change — just a small penalty. Verdict change happens only via Layer 1 for life-stage-sensitive nutrients (retinol/iron in pregnancy) |
| **Evidence (20)** | | | |
| Multiplicative evidence pipeline (study_type × evidence_level × effect_direction × enrollment × dose_guard × top_N + depth_bonus) | up to 20 | **Section C full pipeline preserved.** cap_per_ingredient = 7 | study_type_base: meta-analysis 6, multi-RCT 5, single RCT 4, observational 2, animal 2, in-vitro 1. Multipliers: product-human 1.0, branded-RCT 0.9, ingredient-human 0.8, strain-clinical 0.65, preclinical 0.3. Effect_direction: positive_strong 1.0 / weak 0.85 / mixed 0.6 / null 0.25 / negative 0.0. Enrollment quality bands, top-N diminishing returns 1.0/0.7/0.5/0.3, depth bonus +0.25 (20–39 trials) / +0.5 (≥40) |
| **Testing & trust (15) — hard-clamped at 15 across B4a + B4b + B4c** | | | See §10 and §16 |
| Third-party SKU-verified (B4a) | up to 10 (diminishing returns) | B4a, now SKU-scope-gated | First SKU cert 8, second 4, third 2 |
| GMP / facility audit (B4b) | up to 4 | B4b: certified 4, FDA-registered 2 | Verified GMP |
| Batch traceability (B4c) | up to 1 | B4c: coa 1, batch_lookup 1 → contribute toward 15 cap | Public lot-COA or batch lookup |
| **Transparency (10)** | | | |
| Single active, clear dose, named form, no hidden blends | 6 | B5 transparency state (no proprietary opacity for chelated minerals) | Mineral chelates with disclosed elemental dose: no opacity penalty |
| B3 claim_compliance bonus (allergen-free / gluten-free / vegan-vegetarian) | up to +4 | **B3 claim_compliance** (v3 cap 4): allergen_free +2, gluten_free +1, vegan_vegetarian +1 | Display claims fold into Transparency |
| **Penalties (subtracted from dimension totals)** | | | |
| B0 immediate_fail (moderate / watchlist tier) | up to −10 | **B0_immediate_fail**: moderate_penalty 10, high_risk_penalty 10, watchlist_penalty 5 | Safety hits NOT severe enough for BLOCKED verdict but still penalize the score |
| B1 harmful_additives | up to −15 | B1 cap 15, critical −3 / high −2 / moderate −1 / low −0.5 per additive | Against Formulation |
| B1 dietary_sugar | up to −1.5 | B1_dietary_sugar_penalty cap 1.5 | Against Formulation |
| B2 allergen_presence | up to −2 | B2 cap 2 | Against Transparency (allergen is disclosure fact, not testing) |
| B5 proprietary_blends opacity | up to −10 | **B5** class-aware: chelated mineral with disclosed elemental dose = 0 penalty. See §5 | Only applies if a generic product hides actives in a blend |
| B6 marketing_penalty | −5 | B6.penalty = 5 | Forbidden claims → Layer 1 CAUTION + Transparency penalty |
| B8 CAERS adverse events (currently disabled) | up to −5 | B8: strong −4 / moderate −2 / weak −1, cap −5 | Routes to Layer 1 CAUTION when re-enabled |

### Manufacturer Trust dimension (separate, 5 pts) and Manufacturer Violations adjustment (separate, 0 to −25)

For the generic module (and every module), these two **separate**
dimensions apply on top of the 100-pt class score:

| Dimension | Range | v3 source |
|---|---:|---|
| **Manufacturer Trust (was Section D)** | 0 to +5 | D1 reputation 2 + D1 mid-tier 1 + D2 disclosure 1 + (D3 physician 0.5 + D4 region 1 + D5 sustainability 0.5, capped at 2 collectively) |
| **Manufacturer Violations (separate negative adjustment)** | **0 to −25** | `manufacturer_violations.json` (89 entries) + `manufacture_deduction_expl.json` rules. Severity-tiered (CRITICAL −12 to −20, HIGH −10 to −12, MODERATE smaller), recency-weighted. Total cap −25. See §16 |

**Important: Manufacturer Violations was buried inside "Testing & Trust"
in earlier drafts. It is a separate dimension at the −25 scale, NOT
inside the +15 testing/trust cap.** A bad manufacturer (Diamond Shruumz
−20 base, Prophet Premium Blends) can lose 25 points entirely from the
Manufacturer Violations dimension while still earning their full
testing/trust certs if any apply.

### Worked outcome — Thorne Magnesium Bisglycinate

> **Class-aware dose semantics (load-bearing rubric principle).**
> For a generic single-nutrient supplement, dose adequacy is NOT scored
> against full RDA. RDA is a total-intake target (food + supplements +
> meds). The relevant window is:
>
> `max(0, RDA − typical_dietary_intake)   ≤   supplemental_dose   ≤   supplemental_UL`
>
> Per [NIH ODS Magnesium fact sheet](https://ods.od.nih.gov/factsheets/Magnesium-HealthProfessional/),
> adult supplemental UL is 350 mg/day, explicitly excluding food sources.
> Multi/prenatal classes target full-RDA coverage. Probiotics target
> clinical-trial dose ranges per strain. Same dimension name,
> class-specific target.

| Dimension | Math | Subtotal |
|---|---|---:|
| Formulation | bio_score 15 (bisglycinate, bio=14 → high) + premium forms 0 (only one premium form here) + delivery 2 (capsule, tier 2) + absorption 0 + excellence (synergy 0 + non-GMO 0.5 + natural 0 = 0.5) + single-ingredient 1 = 18.5/30 (v3 actual A = 19.8/25 → consistent) | **~18.5 / 30** |
| Dose | 22 (200 mg inside supplemental window, no B7 penalty under UL) + 0 multi-form = 22 | **22 / 25** |
| Evidence | nutrient-human evidence band, magnesium has strong RCT, scaled through multiplicative pipeline. −4 because no product-specific NCT | **16 / 20** |
| Testing & trust | NSF Sport SKU-verified (+8) + USP product-line (+4) + GMP (+0, Thorne is FDA-registered = +2 in v3, scaled to v4 ≈ +2) → 14, clamped at 15 if MN COA evidence holds, here ~12 | **12 / 15** |
| Transparency | single active + clear dose + named form (5) + B3 claim bonus (vegan +1 if claimed, gluten-free +1) − B2 allergen 0 = 7, capped at 10 | **~8 / 10** |
| **Subtotal (5 class dimensions)** | | **~76 / 100** |
| Manufacturer Trust (+5) | Thorne trusted (+2) + disclosure (+1) + physician/region/sustainability rollup (+1.5 capped at 2) = 4.5 | **+4.5** |
| Manufacturer Violations (0 to −25) | Thorne has no entries → 0 | **0** |
| Penalties (B1, B6, B8) | Purefruit Select low-tier additive −0.5 | **−0.5** |
| **Quality Score** | | **~80 / 100** |

**Note: the ~80 above comes from mechanically mapping v3 sub-component
weights into v4 dimensions. That mapping inherits v3's structural bias
of under-rewarding premium single-nutrient products** — the Generic
module's Formulation Quality dimension naturally rewards multi-form
complexes, synergy clusters, and absorption-enhancer pairings, none of
which a standalone premium chelate has by design. **A clean, clearly
dosed, high-quality bisglycinate with verified SKU certs should land
higher than 80** — and v4 is supposed to fix exactly this kind of v3
class unfairness, not preserve it.

### Expected Thorne band — PROVISIONAL, locked at P1 canary tuning

| Cert resolution status | Provisional v4 expected band |
|---|---:|
| NSF Sport SKU-verified + USP SKU-verified | **85–92** (provisional) |
| One SKU + one product-line | **82–88** (provisional) |
| Both product-line only | **78–84** (provisional) |
| Claimed-only (regex hit, no registry proof) | **72–78** (provisional) |

These bands are **deliberately not locked**. They will be tuned at the
P1 canary review when the shadow scorer's actual output for Thorne Mg
and the other 27 canary products is compared against the AI panel +
API ground truth + clinician queue resolution. **Known v1 tuning area:
Generic-module weighting for single-nutrient products** (likely
candidates: bio_score weight bump, A6 single-ingredient bonus expansion,
or a `generic_single_nutrient` sub-class with a remixed Formulation
rubric).

**100 is still effectively unreachable.** Reasons this specific product
cannot reach 100 even at the upper provisional band:

- No public lot-level COA in DSLD artifact (Thorne posts these on
  their site but not in DSLD)
- No product-specific clinical trial / NCT ID
- Single-form Mg (multi-form complex theoretically more complete)
- Small additive ding (Purefruit Select)
- 100 reserved for ideal-reference future products

### Principle: v4 is not a v3 reskin

v4 **preserves valid v3 mechanics** (bio_score, multiplicative evidence
pipeline, synergy 4-tier, probiotic CFU adequacy, manufacturer
violations cap, etc. — see §17 and the engineering bridge doc). It is
**not constrained by v3's old weighting** where that weighting
under-rewarded a legitimate class signal. The shadow scorer + canary
review is where we discover those cases and adjust weights — not by
mechanically copying v3 sub-section caps into v4 dimensions.

Locking score bands by instinct now would be the wrong move. The
canary set + AI panel + API ground truth are the anchor.

---

## 9. Omega / fish oil policy

Omega-3 starts in the `generic` module for v1, but only conditionally —
the signals are different enough from minerals/vitamins/botanicals that
omega is the most likely candidate to graduate to a dedicated module.
The P1.5 decision checkpoint (see §19 Phased migration) tests this on canary rows 5–9.

Minimum signals an omega-3 product needs to be scored fairly under any
module (generic or future `omega`):

| Signal | What it gates |
|---|---|
| EPA mg + DHA mg per serving | Primary dose relevance. **A product labeled "1000 mg fish oil" with no EPA/DHA breakdown should score significantly lower** than one with clear amounts — total mass is not a clinical dose |
| Source (fish / krill / algae / cod liver) | Bioavailability, EPA:DHA ratio expectations, sustainability scoring |
| IFOS / Nutrasource verification status + star rating | Active ingredient content, contaminant levels, oxidation/peroxide values |
| Sustainability cert (Friend of the Sea, MSC) | Source credit, **lower weight** than purity/testing certs |
| Form (triglyceride / ethyl ester / phospholipid) | Bioavailability tier — TG > rTG > EE for most measures |
| Oxidation status (TOTOX, peroxide value, anisidine) | Quality signal independent of label dose |

**Rules:**

- "Fish oil 1000 mg" with no EPA/DHA breakdown → cap at ~55/100
  regardless of brand/cert claims
- IFOS 5★ SKU-verified → up to +8 testing/trust (under the §10 SKU
  scope rule)
- IFOS lot star rating drives confidence band, not score directly (3★ on
  a lot still meets the standard, just at the floor)
- EPA:DHA ratio outside therapeutic ranges (e.g., for the marketed
  indication) → evidence-strength penalty, not dose-adequacy penalty

**Decision gate at P1.5:** if the generic module fails to rank canary
rows 5–9 (Nordic Naturals, Carlson, Nature Made, Sports Research,
generic 1000mg) within ±1 expected position, an `omega` module joins v1
before P2. Otherwise omega stays in `generic` and we revisit in v5.

> **Codex review-pass call: omega is very likely to need its own module.**
> The signal list above (EPA/DHA, source, IFOS lot rating, oxidation,
> form, sustainability) is distinct enough from minerals/vitamins/
> botanicals that the generic module probably can't rank canary rows 5–9
> correctly. We're keeping P1.5 as the formal decision gate, but plan
> capacity for an `omega` module landing in v1 scope. If the gate
> surprises us and generic handles it, that's a free win — but engineering
> shouldn't assume it.

---

## 10. Cert verification design (free / cheap)

### Today's broken behavior

| Layer | Behavior | Problem |
|---|---|---|
| Regex extraction | [`enrich_supplements_v3.py:9161`](../../scripts/enrich_supplements_v3.py#L9161) detects "NSF Sport", "NSF Certified", "USP Verified" from DSLD label text | Label text is brand claim, not third-party proof |
| Manufacturer injection | [`enrich_supplements_v3.py:9089`](../../scripts/enrich_supplements_v3.py#L9089) injects certs from `top_manufacturers_data.json` evidence | Brand-level inflation — every Thorne SKU inherits Thorne's certs |
| Scorer | `5 × len(programs)`, cap 15 | Pure stacking, no diminishing returns, no verification gate |

### Guiding principle — demote, do not delete

Codex correction (2026-05-18): the brand/manufacturer cert signal is **not
worthless** — it's just not **scoring-worthy**. A signal like "Thorne has
NSF Sport products" is useful display/trust metadata. The fix is to **route
it to a separate, non-scoring field**, not to delete the code:

```
brand/manufacturer evidence  →  manufacturer_cert_signals  (display only)
SKU/product-line registry hit →  verified_cert_programs   (scores points)
```

Also (Codex): **false positives on cert verification are worse than missed
bonuses** for a clinical product. Fuzzy match thresholds must be
conservative. Borderline matches go to a manual-review queue rather than
auto-classifying as `sku` or `product_line`.

### Proposed: 3-stage cert resolver

**Stage 1 — Public registry snapshots, refreshed on schedule.**
All free, no paid dependencies. **ConsumerLab is NOT a free anchor and is
out of scope** for automated verification — it can inform manual review only
when a paid license is present.

Source URLs verified 2026-05-18 (Codex):

| Source | URL | Refresh | Scope |
|---|---|---|---|
| NSF Certified for Sport (search + printable list) | https://www.nsfsport.com/certified-products/index.php | Quarterly | SKU + lot |
| NSF Dietary Supplements (NSF/ANSI 173 listings) | https://info.nsf.org/Certified/dietary/ | Quarterly | Product line |
| NSF supplement certification overview | https://www.nsf.org/consumer-resources/articles/supplement-vitamin-certification | Reference | Reference |
| USP Verification Program participants | https://www.usp.org/verification-services/verification-program-participants | Quarterly | SKU (manual overrides likely) |
| IFOS / Nutrasource (omega-3) | https://certifications.nutrasource.ca/en/about/how-certifications-work/ifos | Monthly | Lot + star rating |
| Informed Sport / Informed Choice | https://sport.wetestyoutrust.com/ | Quarterly | SKU |
| Non-GMO Project | https://www.nongmoproject.org/find-non-gmo | Quarterly | Product line (claim display, not B4a purity) |
| Clean Label Project | https://cleanlabelproject.org/certified-products/ | Quarterly | Product line (medium trust until cert detail is machine-verified) |
| Friend of the Sea | https://friendofthesea.org/ | Quarterly | Sustainability/source (lower weight than purity certs) |
| MSC (Marine Stewardship Council) | https://www.msc.org/ | Quarterly | Sustainability/source |

**Stage 2 — Resolver function** (`scripts/cert_resolver.py`).
Conservative thresholds (precision over recall — false positives are
worse than missed bonuses):

```python
def resolve_certification_scope(
    brand: str,
    product_name: str,
    claimed_program: str,
    registry: CertRegistry,
) -> CertResolution:
    """
    Returns scope ∈ {sku, product_line, brand_only, claimed_only, needs_review}
    using rapidfuzz token_set_ratio (already a project dep).

    Conservative thresholds (Codex calibration — precision > recall):
      - brand exact-normalized + product ratio >= 92  → sku
      - brand exact-normalized + product ratio 80–91  → needs_review (queue)
      - brand exact-normalized + product-line keyword overlap >= 85 → product_line
      - brand exact-normalized + product-line keyword overlap 70–84 → needs_review
      - brand exact-normalized but no product hit → brand_only
      - no brand match → claimed_only

    `needs_review` items land in cert_verification_overrides.json as
    pending entries with the auto-suggested scope; a human confirms or
    downgrades before any scoring credit is granted.
    """
```

**Stage 3 — Manual override + review queue** at
`scripts/data/curated_overrides/cert_verification_overrides.json`. Seeded
from the canary set, expanded over time. Follows the existing
`curated_overrides` pattern. Two record types:

- `verified` — manually confirmed; scorer trusts this scope
- `pending_review` — auto-flagged as borderline; scorer treats as `claimed_only` (zero points) until reviewed

### Cache artifact (new data file)

`scripts/data/cert_registry.json` (schema v6.0):

```json
{
  "_metadata": {
    "schema_version": "6.0.0",
    "last_updated": "2026-05-18",
    "registry_sources": [
      {"program": "NSF Sport", "url": "...", "snapshot_date": "2026-05-18", "entry_count": 412}
    ],
    "total_verified_records": 0
  },
  "verified_records": [
    {
      "record_id": "NSF_SPORT_THORNE_MAG_BIS_2025Q4",
      "program": "NSF Sport",
      "brand_normalized": "thorne",
      "product_normalized": "magnesium bisglycinate",
      "match_keys": ["thorne magnesium bisglycinate", "thorne_mag_bis_200mg"],
      "scope": "sku",
      "lot_numbers_tested": ["A30821", "A40522"],
      "verified_at": "2026-01-15",
      "source_url": "https://www.nsfsport.com/...",
      "evidence_band": "strong"
    }
  ]
}
```

### Enricher contract change

Three-tier field split (Codex 2026-05-18). Each tier has a different
purpose and only the third tier scores points:

```jsonc
"certification_data": {
  "claimed_cert_programs": [                          // regex from DSLD label text — display only
    "NSF Sport", "NSF Certified", "USP Verified"
  ],
  "manufacturer_cert_signals": [                      // brand/manufacturer-level evidence — display + UX trust only
    {"program": "NSF Sport", "evidence": "Thorne has NSF Sport products on file",
     "source": "top_manufacturers_data.json"}
  ],
  "verified_cert_programs": [                         // SKU/product-line registry match — SCORES POINTS
    {"program": "NSF Sport",
     "scope": "sku",
     "record_id": "NSF_SPORT_THORNE_MAG_BIS_2025Q4",
     "match_confidence": 0.97,
     "verified_at": "2026-01-15",
     "source_url": "https://www.nsfsport.com/..."}
  ]
}
```

The previously-buggy manufacturer-injection code at
[`enrich_supplements_v3.py:9089`](../../scripts/enrich_supplements_v3.py#L9089)
is **rerouted, not deleted**: its output now lands in
`manufacturer_cert_signals` and never reaches the scorer.

### Scorer change — B4a v4

```python
# Per-cert scope points with diminishing returns (anti-stacking).
SCOPE_POINTS = {
    "sku":          {"first": 8, "second": 4, "third": 2},
    "product_line": {"first": 6, "second": 3, "third": 1},
    "brand_only":   {"first": 1, "second": 0, "third": 0},  # routed to manufacturer trust D, not B4a
    "claimed_only": {"first": 0, "second": 0, "third": 0},  # display only, never scores
}

# Sub-component soft caps (orientation only — hard cap is the dimension cap below).
B4A_SOFT_CAP   = 10   # third-party programs (was 12 in earlier draft; tightened to leave headroom for B4b + B4c)
B4B_SOFT_CAP   = 4    # verified GMP / facility audit
B4C_SOFT_CAP   = 1    # public lot-COA / batch lookup

# Hard dimension cap — applies across all three sub-components.
# Per Codex review pass: B4a_cap(10) + B4b(4) + B4c(1) could total 15
# at the cap, but stacked SKU certs + GMP can mathematically reach 17.
# The hard clamp below is the authoritative bound — no combination of
# sub-component points can exceed 15 in the final score.
TESTING_TRUST_DIMENSION_HARD_CAP = 15

realized_testing_trust = min(
    TESTING_TRUST_DIMENSION_HARD_CAP,
    sum(verified_cert_points) + gmp_points + batch_traceability_points,
)
```

Worked example — Thorne Magnesium with everything verified:
`SKU NSF Sport (8) + SKU USP (4) + verified GMP (4) + public lot-COA (1) = 17 → clamped to 15.`
The clamp is the single source of truth — the soft caps above are
orientation for reviewers, not enforced bounds.

Brand-only routes to manufacturer trust (D, separate dimension), not B4a.

### Why this is free

- All listed registries are publicly searchable or publish downloadable
  lists. No API keys, no scraping behind authentication, no paid licensing.
- `rapidfuzz` is already a dependency.
- Engineering cost ≈ 5–7 days for full resolver + 8 fetchers. NSF Sport
  alone as a proof-of-concept = ~1 day.
- Manual override file seeds with the 28-product canary set first (~2 hrs).

---

## 11. Anchor methodology (API ground truth + AI panel + async clinician queue)

Per Sean's decision 2026-05-18: **no synchronous clinician panel.** We are
optimizing for throughput and using AI models as the rank-order scoring
reviewers, with **authoritative APIs as ground truth** and an
**asynchronous clinician verification queue** for cases where AI panels
disagree or where clinical nuance matters.

This trades off some clinical-judgment authority for throughput. The
mitigations below preserve verification rigor.

### Authority order (highest first)

| Rank | Source | What it anchors | Trust level |
|---|---|---|---|
| 1 | **Live-API content verification** (PubMed, UMLS, RxNorm, OpenFDA, ClinicalTrials.gov, NIH ODS, NCCIH) | PMID/CUI/NCT identity + content match; RDA/UL/AI values; recall status; drug interactions | **Ground truth — beats any model opinion** |
| 2 | **Public certification registries** (NSF Sport, USP, IFOS, Informed Sport) — see §10 | SKU-level testing facts | Ground truth for cert scope |
| 3 | **Multi-model AI panel** — Claude + ChatGPT, fixed rubric prompt | Class rubric tuning, canary rank-order, dimension-weight calibration | Authoritative when both models agree; conservative default when they don't |
| 4 | **Web research via subagent** — NIH/NCCIH/peer-reviewed/Examine.com summary | Real-world expert consensus on dose adequacy, indication relevance, form quality | Cross-check signal, never sole anchor |
| 5 | **Verified DSLD blobs + audited product canaries** | Identity, dose, form factor | Ground truth for label facts |
| 6 | **Async clinician verification queue** at [docs/plans/CLINICIAN_VERIFICATION_QUEUE.md](CLINICIAN_VERIFICATION_QUEUE.md) | Edge cases, AI panel disagreements, judgment calls | Asynchronous — production does NOT block on this |

### AI panel rules (replacing the clinician panel discipline)

Codex's "anti-bias rules for clinician panel" translated to a multi-model
AI panel:

| Codex requirement | AI panel implementation |
|---|---|
| Blinded reviews | Each model scores independently. Neither sees the other's score or breakdown |
| Fixed rubric | Same prompt template at `scripts/scoring_v4/prompts/canary_rubric_review.md`. Rubric loaded from `scripts/scoring_v4/rubric/*.json`. Prompt version pinned in the comparison report |
| Minimum reviewer count | **Two model families minimum:** Claude (Anthropic) + ChatGPT (OpenAI). Different model families = different failure modes |
| Disagreement handling | If model bands differ by **> 1 band**, take the **lower band** (conservative default) and log to clinician queue |
| Tie resolution | API ground truth wins. If no API value exists, use the lower of the two model bands |
| Conflict logging | Every disagreement → CLINICIAN_VERIFICATION_QUEUE.md with brand, product, dimension, Claude band, ChatGPT band, API ground truth (if any), conservative score applied |
| Anti-convergence | Track over time: if Claude and ChatGPT agree > 95% of the time, suspect they're converging on the same wrong answer. Add a third model (e.g., Gemini) for spot-checks |

### Web research integration

For class-tuning questions without clean API ground truth (e.g., "what's
a clinically adequate ashwagandha dose for stress?"), spawn a
research subagent (per CLAUDE.md global rules — never run WebSearch in
the main session). The subagent's report must:

- Cite only **NIH/NCCIH/peer-reviewed/Examine.com summary** sources
- **Content-verify** any PMIDs returned via PubMed API before citing
  (per `critical_no_hallucinated_citations` memory rule)
- Return one of: clear consensus value, range with explicit reasoning,
  or "insufficient reliable sources" verdict (which routes the question
  to the clinician queue)

### What the async clinician queue is for

[CLINICIAN_VERIFICATION_QUEUE.md](CLINICIAN_VERIFICATION_QUEUE.md) is
the safety valve. Items added include:

- AI panel disagreements (> 1 band) — production ships the conservative
  score, the case is queued for later clinician review
- Decisions where the API ground truth conflicts with a model's
  confident output — defer to the API but log the model error
- Class-rubric tuning calls without API ground truth and where web
  research returns ambiguous consensus
- Edge cases flagged by enrichment (e.g., novel ingredient not in IQM,
  unusual life-stage claim)

When a clinician later corrects an entry, the correction lands as:
1. A regression test in `scripts/tests/test_clinician_corrections.py`
2. A curated override in `scripts/data/curated_overrides/`
3. A decision-log entry in this doc

**Production never blocks on the queue.** The conservative default ships;
clinician feedback only changes future releases.

ConsumerLab remains **out of scope** for automated verification.

---

## 12. Canary set (28 products, 12 classes)

Used for rank-order validation. v4 ships only when canary rank order matches
the API-grounded + AI-panel review target **within ±1 position for ≥ 23 of
28**, with disagreements routed to the async clinician queue and conservative
defaults applied until resolved.

| # | Product | Class | Current (est) | Expected v4 band | Tests what |
|---:|---|---|---:|---:|---|
| 1 | Thorne Magnesium Bisglycinate 200mg | mineral | 72.6 | **provisional 85–92 (SKU+SKU) / 82–88 (SKU+line) / 78–84 (line+line) / 72–78 (claimed-only)** — **locked at P1 canary tuning** | Premium single-form; cert verification swing AND known tuning area: generic single-nutrient weighting may need rebalance to avoid v3-style class unfairness |
| 2 | Doctor's Best Magnesium Glycinate 400mg | mineral | ~65 | 70–80 | Higher dose, commodity brand |
| 3 | Solgar Chelated Magnesium 400mg | mineral | ~62 | 65–75 | Mainstream mineral |
| 4 | NOW Magnesium Citrate 400mg | mineral | ~55 | 55–65 | Cheaper form, full dose |
| 5 | Nordic Naturals Ultimate Omega 1280mg | omega-3 | varies | 85–95 | IFOS 5★, EPA/DHA dose |
| 6 | Carlson Labs Maximum Omega 1600 | omega-3 | varies | 75–85 | Strong dose, IFOS varies |
| 7 | Nature Made Fish Oil 1200mg | omega-3 | ~60 | 60–72 | Mainstream, USP |
| 8 | Sports Research Triple Strength Omega 1250 | omega-3 | varies | 70–82 | IFOS, mid-tier |
| 9 | Generic 1000mg Fish Oil softgel | omega-3 | ~45 | 45–58 | No testing baseline |
| 10 | Thorne Basic Prenatal | prenatal multi | 90.5 | 82–92 | Premium prenatal completeness |
| 11 | FullWell Prenatal | prenatal multi | varies | 80–90 | Boutique complete panel |
| 12 | Nature Made Prenatal + DHA | prenatal multi | 80.1 | 72–82 | Mainstream, USP |
| 13 | One A Day Prenatal | prenatal multi | varies | 55–68 | Lower-tier mainstream |
| 14 | Garden of Life Raw Prenatal | prenatal multi | 66.1 | 55–68 | Blend opacity in prenatal |
| 15 | **Garden of Life Once Daily Prenatal Probiotic (`274081`)** | probiotic | 45.6 | 50–60 | Probiotic class fix anchor |
| 16 | Visbiome High Potency (per-strain CFU disclosed) | probiotic | varies | 82–92 | Class ceiling: full disclosure |
| 17 | Culturelle Daily (LGG only) | probiotic | varies | 65–78 | Single clinical strain |
| 18 | Align Probiotic (B. infantis 35624) | probiotic | varies | 65–78 | Single clinical strain |
| 19 | Nature Made Multi Adult Gummies | multi/gummy | 79.1 | 50–65 | **Current overscores gummy** |
| 20 | Centrum Silver | multi | varies | 45–58 | Broad mainstream multi |
| 21 | Ritual Essential 18+ | multi | varies | 60–72 | Boutique limited multi |
| 22 | **Transparent Labs KSM-66 Ashwagandha 600mg** (DSLD `305203`) | botanical (branded) | **61.5** | **provisional 82–90 (SKU-verified) / 78–86 (line) / 72–82 (claimed-only)** — **locked at P1 canary tuning** | Branded standardized extract; current 61.5 is under-credited primarily on Evidence (4.5/20). Artifact check confirms KSM-66 *does* match `BRAND_KSM66`; the issue is not a missing match, it is whether one summarized branded-RCT entry should carry more weight for branded extracts. Also review the IQM PK caveat: KSM-66 currently has `bio_score=11` due low human withanolide plasma exposure. Anchor for branded-extract weighting tuning |
| 23 | NOW Ashwagandha Extract 450mg | botanical (commodity) | varies | 55–70 | 2.5% withanolides, no brand |
| 24 | Generic ashwagandha root powder | botanical | varies | 30–50 | No standardization |
| 25 | Athletic Greens AG1 | multi+blend | varies | 50–62 (CAUTION) | Broad proprietary blend |
| 26 | Generic pre-workout with proprietary stim blend | stimulant | varies | 18–35 (CAUTION) | Opacity gating |
| 27 | Vital Proteins Collagen Peptides 20g | collagen | varies | 60–72 | Type/source/dose |
| 28 | Recalled adulterant canary (e.g., DMAA product) | regulatory | n/a | BLOCKED | Safety gate validation |

---

## 13. Code architecture

**Separate shadow scorer, not in-place rewrite of v3.** Per Codex
(2026-05-18): `scripts/score_supplements.py` remains v3 production truth
through the entire v4 build. `score_supplements_v4_shadow.py` is the v4
entry point. They share the **same enriched input contract** (enriched
blob from `enrich_supplements_v3.py`) and shared helpers where stable
(e.g., `cert_resolver.py`, `enhanced_normalizer.py` lookups). They do
NOT share scoring policy — v4 owns its own rubric/dimension/penalty
layer to prevent drift between two giant files. Cutover is a
config/contract decision after canaries + full-catalog deltas pass
(§19 P5), not a risky scorer rewrite.

```
scripts/
  score_supplements.py                # v3, UNTOUCHED throughout v4 build; remains production truth
  score_supplements_v4_shadow.py      # v4 entry point — same input contract as v3, emits shadow_score_v4_* columns
  cert_resolver.py                    # NEW — cert verification lookup (shared between any scorer)
  scoring_v4/
    __init__.py
    router.py                         # picks class module
    gate_safety.py                    # Layer 1
    gate_completeness.py              # Layer 2 (class-aware required fields)
    confidence.py                     # Layer 4 (typed sub-categories)
    modules/
      generic.py
      probiotic.py
      multi_or_prenatal.py
    rubric/
      probiotic_rubric.json           # point allocations + class-specific dimension descriptions
      multi_rubric.json               # same — each rubric file owns its UI explanation text
      generic_rubric.json
    prompts/
      canary_rubric_review.md         # NEW — fixed prompt for AI panel review (Claude + ChatGPT)
      dimension_explanation.md        # NEW — generates class-aware "why this scored this way" UI cards
    ai_panel/
      __init__.py
      claude_reviewer.py              # NEW — calls Claude API with fixed rubric prompt
      chatgpt_reviewer.py             # NEW — calls OpenAI API with same rubric prompt
      consensus.py                    # NEW — agreement check, band disagreement → conservative + queue
    audit/
      score_diff_v3_v4.py             # full-catalog comparator
      canary_runner.py                # rank-order check on canary set
      ai_panel_runner.py              # NEW — runs AI panel on canary set, logs disagreements
  api_audit/
    verify_certifications.py          # NEW — refreshes cert_registry.json
  data/
    cert_registry.json                # NEW — public registry snapshots
    curated_overrides/
      cert_verification_overrides.json  # NEW — manual SKU verification
      clinician_corrections.json        # NEW — items reviewed offline, fed back as overrides
  tests/
    test_cert_resolver.py             # NEW
    test_b5_class_aware_opacity.py    # NEW
    test_active_only_export.py        # NEW
    test_not_scored_gate.py           # NEW
    test_probiotic_module.py          # NEW (P2)
    test_multi_prenatal_module.py     # NEW (P3)
    test_canary_rank_order.py         # NEW (P4)
    test_ai_panel_consensus.py        # NEW (P4) — disagreement → conservative default
    test_clinician_corrections.py     # NEW — regression for every queue-resolved item
docs/plans/
  SCORING_V4_PROPOSAL.md              # this document — canonical spec
  CLINICIAN_VERIFICATION_QUEUE.md     # NEW — async queue for clinician review (production never blocks)
```

### Class-specific UI explanation cards (Codex review-pass)

Each rubric file (`probiotic_rubric.json`, `multi_rubric.json`,
`generic_rubric.json`) owns a `dimension_descriptions` block with
class-specific wording. Flutter renders this on the score-detail
screen so a probiotic 84 and a fish-oil 84 don't read as evaluated
against the same criteria.

```jsonc
// probiotic_rubric.json
{
  "dimension_descriptions": {
    "formulation_quality": "How well the strains, CFU count, delivery system, and prebiotic complement are designed to survive and reach target sites.",
    "dose_clinical_relevance": "Whether per-strain CFU on the label matches doses used in clinical trials for the indication this product targets.",
    "evidence_strength": "Strength of human clinical evidence for the exact strains named (not just genus/species).",
    "testing_trust": "Independent third-party verification of identity, contaminants, and CFU count at SKU level.",
    "transparency": "Whether all strain identities and per-strain CFU are disclosed on the label."
  }
}
```

Same `dimension_descriptions` key on every rubric file, different
content. Cross-class score comparison happens against this text, not
against a shared dictionary.

---

## 14. Schema / contract changes

### `products_core` columns (additive during shadow phase)

**Shadow architecture, not in-place rewrite.** v3 stays untouched as
production truth until the cutover gate (§19 P5) passes. The shadow
scorer emits side-by-side columns; v3 columns remain authoritative until
cutover.

```sql
shadow_score_v4_100         REAL       -- calibrated v4 0-100 display number during shadow phase
shadow_score_v4_module      TEXT       -- 'generic' | 'probiotic' | 'multi_or_prenatal' (and 'omega' if P1.5 promotes it)
shadow_score_v4_verdict     TEXT       -- 'SAFE' | 'POOR' | 'CAUTION' | 'NOT_SCORED' | 'UNSAFE' | 'BLOCKED'
shadow_score_v4_confidence  TEXT       -- scoreable rows: 'high' | 'moderate' | 'low'; gate failures: 'blocked_by_safety_gate' | 'blocked_by_completeness_gate'; non-generic module stubs may emit 'skeleton' until their module lands
shadow_score_v4_breakdown   TEXT       -- JSON, full per-dimension audit trail (Formulation, Dose, Evidence, Trust, Transparency, manufacturer violations applied, penalties)
shadow_score_v4_anchored    INTEGER    -- 1 if product is in the §12 canary set
```

During P1.5 shadow calibration, `shadow_score_v4_breakdown.module`
keeps both the raw assembly and the calibrated display value:
`raw_score_100` is the direct sum/rescale of the five dimensions plus
manufacturer adjustments; `score_100` is the calibrated value currently
emitted to `shadow_score_v4_100`. The P1.5 calibration is affine:

```
shadow_score_v4_100 = clamp(25 + 0.75 * raw_score_100, 0, 100)
```

The transform is intentionally applied only at final assembly. Dimension
scores, manufacturer adjustments, safety/completeness gates, carried
CAUTION verdicts, and raw audit math remain unchanged.

After cutover (§19 P5): columns rename to production names; v3 columns
kept for one release cycle as `legacy_score_*` then deprecated.

### Blob `certification_detail` change

`claimed_cert_programs` is now display-only; `verified_cert_programs` gates
B4a scoring.

### Flutter contract

No breaking change during shadow phase. At cutover:
- `score_quality_80` and `score_display_100_equivalent` keep their names but
  read from v4 internally.
- New `confidence` block surfaced as `confidence_band` and
  `confidence_drivers` on the card.
- New `score_breakdown_v4` JSON exposed for audit / power-user UI.

---

## 15. Shadow report requirements

Before any v4 cutover, the shadow scorer must emit a comparison report
covering the full catalog. This is the explicit gate for P5 — not
"shadow ran without errors" but "the deltas are explainable and the
expected movement bands hold." The report is regenerated every shadow
release cycle.

The report must include:

1. **Old score vs v4 score** for every live-eligible product. One row
   per product with the breakdown (v4 dimension points) attached.
2. **Delta histogram by class.** Visual or table — distribution of v4
   minus v3 scores per module (generic / probiotic / multi-prenatal),
   plus the catalog-wide histogram.
3. **Top 100 positive movers** (largest gainers) **and top 100 negative
   movers** (largest losers), each with brand/product/class/old/new/
   delta/reason and a one-line plain-English rationale.
4. **Median, p25, p75 movement by class.** Catalog-wide median movement
   should not exceed ±5 points without explicit review. Class-specific
   movement can exceed this when the class is known broken
   (probiotics, gummy multis) — but the magnitude must match what the
   class redesign predicted, not exceed it.
5. **Canary detail.** Each of the 28 canary products, point-by-point
   v4 breakdown, expected band (from §12), actual v4 score, in/out of
   band flag.
6. **Cert audit deltas.** For each product whose `verified_cert_programs`
   changed: brand, product, previous B4a points, new B4a points,
   `manufacturer_cert_signals` (display-only) for visibility.
7. **Products excluded from live catalog** with explicit reasons (which
   eligibility gate failed, which class-aware required field is missing).
   This is the QA list that gets reviewed before each release.
8. **Safety contradiction counts. Must be zero.** Specifically: no
   `verdict=SAFE` product carries banned/recalled/critical warning;
   no `verdict=BLOCKED` product reaches the live catalog; no
   life-stage-contraindicated active is unflagged in profile-gated
   warnings.
9. **AI panel agreement summary.** For the canary set (and any
   sampled non-canary subset reviewed by the AI panel): per-product
   Claude band, ChatGPT band, agreement flag (within 1 band yes/no),
   ground-truth API value where applicable, conservative-default
   applied flag, queue routing flag. Track aggregate agreement rate
   across releases — a sudden jump or fall is its own signal worth
   reviewing.
10. **Clinician queue delta.** New entries added to
    [CLINICIAN_VERIFICATION_QUEUE.md](CLINICIAN_VERIFICATION_QUEUE.md)
    this cycle, resolved entries (with the correction applied as a
    curated override), and unresolved-age distribution (e.g., how
    many items have been pending > 30 days). Queue is async — these
    counts are informational, not gating.

If item 8 is non-zero, the release is held. If items 1–7 reveal
unexpected catalog-wide shifts (median movement > 5 pts), the rubric
is re-tuned and shadow rerun before cutover. Items 9–10 inform but
do not gate cutover unless AI agreement rate drops below 80% on the
canary set — that's a "models are drifting apart, investigate" signal.

---

## 16. Manufacturer Violations dimension (separate, 0 to −25)

Per Sean's review-pass: this dimension was buried inside "Testing & trust"
in earlier drafts. It is **separate**, with a separate cap of −25, NOT
inside the +15 Testing & Trust dimension. A bad manufacturer can lose 25
points entirely from this dimension while still earning their full
testing/trust certs if any apply.

### Data source

`scripts/data/manufacturer_violations.json` (89 entries as of 2026-05-14)
+ `scripts/data/manufacture_deduction_expl.json` (rules).

### v3 config

```jsonc
"manufacturer_violations": {
  "cap_total": -25,
  "stored_sign": "negative",
  "_note": "Read total_deduction_applied and add directly to quality_raw"
}
```

### Severity tiers (from manufacturer_violations.json `_metadata`)

| Severity | Base deduction range | Example triggers |
|---|---:|---|
| **CRITICAL** | **−12 to −20** | Class I Recall (toxic substances, undeclared drugs); deaths reported; FDA seizure |
| **HIGH** | −10 to −12 | Class II Recall, critical cGMP failures |
| **MODERATE** | smaller | Class III Recall, warning letters, label compliance |
| **LOW** | small | Minor regulatory findings |

### Recency weighting

| Days since violation | `recency_multiplier` |
|---|---:|
| ≤ 365 (within 1 year) | 1.0 |
| 365–730 (1–2 years) | 0.75 |
| 730–1095 (2–3 years) | 0.5 |
| > 1095 (>3 years) | 0.25 |

The recency multiplier reduces the deduction over time — a 2024 Class I
recall hits the score in 2026 at 0.5× weight.

### Realized example — Prophet Premium Blends / Diamond Shruumz

From the actual data file (`V001`):

```jsonc
{
  "manufacturer": "Prophet Premium Blends",
  "product": "Diamond Shruumz (Infused Cones, Chocolate Bars, Gummies)",
  "violation_type": "Class I Recall",
  "severity_level": "critical",
  "violation_code": "CRI_TOXIC",
  "base_deduction": -20,
  "reason": "Toxic levels of muscimol causing seizures, hospitalizations, and death",
  "date": "2024-06-27",
  "days_since_violation": 685,
  "recency_multiplier": 0.5,
  "illnesses_reported": 39,
  "deaths_reported": ...
}
```

Realized deduction: `−20 × 0.5 = −10` (after 685 days). If the violation
were within the past year, full `−20`. Total across all violations on
this manufacturer is capped at −25.

### How it interacts with verdict

- BLOCKED safety verdict overrides — products from CRITICAL-violation
  manufacturers may also be removed entirely via Layer 1 safety gate
- CAUTION: surfaced when the violation is severe but the product itself
  isn't on a recall list
- The deduction always applies on top of Layer 1 verdict logic

### Implementation note

In v4 the field `manufacturer_violation_deduction` is exposed as its own
column on `products_core` (range 0 to −25), separate from the testing/
trust dimension. The Flutter UI rolls it into the "Trust" pillar for end
users (see §18) but the engineering separation is preserved for audit.

---

## 17. v3 → v4 dimension mapping (full side-by-side)

This table is the **architectural** bridge between v3 and v4 (concept-level).

For the **engineering** bridge — code locations, config keys, test files,
SQLite migration columns, and the shadow-comparator column layout — see
the companion doc [SCORING_V3_TO_V4_MAPPING.md](SCORING_V3_TO_V4_MAPPING.md).
That doc is the reference an engineer opens alongside `score_supplements.py`
when implementing the shadow scorer.

Every v3 sub-section is preserved here; nothing is silently dropped.

| v3 section / sub-component | v3 max / range | v4 module → dimension | v4 max | Notes |
|---|---|---|---:|---|
| **Section A — Ingredient Quality** | base cap 25 + 5 category pool | **Formulation Quality + Dose (class-split)** | 25–30 by class | |
| A1 bioavailability_form (IQM bio_score) | 18 | Generic → Formulation: form bio_score line | 15 | **Single line. This IS the form mapping.** No double-count |
| A2 premium_forms | 5 | Generic → Formulation: premium forms bonus | 4 | Additional premium forms beyond A1's primary; skip-first rule preserved |
| A3 delivery_system | 3 | Generic → Formulation: delivery line | 3 | Tier 1=3, Tier 2=2, Tier 3=1 |
| A4 absorption_enhancer | 3 | Generic → Formulation: absorption pairing | 3 | Paired enhancement (Bioperine+curcumin, vitC+iron) |
| A5 formulation_excellence rollup | 4 | Generic → Formulation: excellence | 4 | Organic +1 + standardized +1 + **synergy cluster 4-tier (1.0/0.75/0.5/0.25)** + non-GMO +0.5 + natural source +1 |
| A6 single_ingredient_efficiency | 3 | Generic → Formulation: single-ingredient bonus | 1 | Reduced — already captured via A1 bio_score for premium chelated singles |
| category_bonus_pool (shared cap 5) | 5 | **Splits into class modules** | varies | Pool dissolved; sub-bonuses move into class modules |
| ↳ probiotic_bonus (default 3 / extended 10) | 3 / 10 | Probiotic module → Formulation | (folded into 25) | |
| ↳ probiotic_cfu_adequacy (up to +5 uplift) | 5 | Probiotic module → Dose dimension (tier × support_level) | 10 (scaled) | Tier low 0 / adequate 1 / good 2 / excellent 3; support high 1.0 / moderate 0.75 / weak 0.5 |
| ↳ omega3_dose_bonus | 2 | **Omega module** (P1.5) → Dose dimension | (folded) | Was Section E in v3.0–v3.2, moved to A.category_bonus_pool in v3.3 |
| ↳ enzyme_recognition | 2.5 | Generic → Formulation (single-ingredient enzyme bonus) | 2 | Enzymes inside blends route through B5 opacity |
| **Section B — Safety & Purity** | base 25 + bonus 5, cap 30 | **Distributed across Layer 1 gate + dimensions + penalties** | distributed | |
| B0 immediate_fail | −5 to −10 | Layer 1 Safety gate (some BLOCKED) + Formulation penalty (moderate/watchlist tiers) | gate or penalty | |
| B1 harmful_additives | up to −15 | Formulation penalty (Generic/Multi/Probiotic) | up to −15 | Same scale preserved |
| B1 dietary_sugar | up to −1.5 | Formulation penalty (Generic/Multi) | up to −1.5 | |
| B2 allergen_presence | up to −2 | Transparency penalty (allergens are disclosure facts) | up to −2 | |
| B3 claim_compliance | up to +4 | **Transparency dimension** (display claims) | up to +4 | Allergen-free +2, gluten-free +1, vegan/vegetarian +1 |
| B4 quality_certifications | up to +21 | **Testing & Trust dimension, hard-clamped at 15** | 15 | Was the bug. Now SKU-scope-verified, no manufacturer injection |
| B4a named_programs | up to +15 | B4a inside Testing & Trust, diminishing returns | up to 10 | First SKU 8, second 4, third 2 |
| B4b GMP | 4 (certified) / 2 (FDA registered) | B4b inside Testing & Trust | up to 4 | |
| B4c batch_traceability | 2 | B4c inside Testing & Trust | up to 1 | |
| B5 proprietary_blends | up to −10 | **§5 B5 Opacity Policy (class-aware)** | varies | Probiotic with named strains: −3 to −5. Stimulant blend: −10 to −15 + CAUTION |
| B6 marketing_penalty | −5 | Layer 1 CAUTION + Transparency penalty | −5 | Forbidden claims |
| B7 dose_safety (>150% UL) | up to −3 (single 2, cap 3) | Dose dimension penalty; Layer 1 only for life-stage-sensitive | up to −3 | Corrected — small penalty, NOT UNSAFE by itself |
| B8 CAERS adverse events | up to −5 (currently disabled) | Layer 1 CAUTION when re-enabled | up to −5 | |
| **Section C — Evidence & Research** | 20, cap_per_ingredient 7 | **Evidence Strength dimension** | 20 (Generic), 15 (Multi) | **Multiplicative pipeline preserved in full** |
| study_type_base | meta 6 / multi-RCT 5 / single 4 / clinical strain 4 / observational 2 / animal 2 / in-vitro 1 | Same | same | |
| evidence_level_multipliers | product-human 1.0 / branded 0.9 / ingredient-human 0.8 / strain-clinical 0.65 / preclinical 0.3 | Same | same | |
| effect_direction_multipliers | positive_strong 1.0 / weak 0.85 / mixed 0.6 / null 0.25 / negative 0.0 | Same | same | |
| enrollment_quality_bands | <50→0.6, 50-199→0.8, 200-499→1.0, 500-999→1.1, ≥1000→1.2 | Same | same | |
| sub_clinical_dose_guard | 0.25× when product dose < clinical | Same | same | |
| supra_clinical_multiple | 3.0 max | Same | same | |
| top_n_weights | [1.0, 0.7, 0.5, 0.3] diminishing returns | Same | same | |
| depth_bonus_bands | 20-39 trials +0.25, ≥40 +0.5 | Same | same | |
| cap_per_ingredient | 7 | Same | 7 | One over-evidenced ingredient cannot dominate |
| **Section D — Brand Trust** | 5 | **Manufacturer Trust dimension (separate small dim)** | 5 | Renamed for clarity; same logic |
| D1 manufacturer_reputation | 2 | Manufacturer Trust: reputation | 2 | |
| D1 mid_tier_reputation | 1 | Manufacturer Trust: mid-tier | 1 | |
| D2 disclosure_quality | 1 | Manufacturer Trust: disclosure | 1 | |
| D3+D4+D5 combined (physician, region, sustainability) | capped at 2 collectively | Manufacturer Trust: rollup | capped at 2 | |
| **Manufacturer Violations (top-level adjustment)** | **0 to −25** | **Manufacturer Violations dimension (separate negative adjustment, §16)** | **0 to −25** | NOT inside testing/trust |
| **Section E — Dose Adequacy (deprecated)** | 2 | Omega module → Dose dimension | (folded) | Moved to A.omega3_dose_bonus in v3.3 |
| **(no v3 equivalent)** | — | **Layer 1 Safety gate** (verdict overrides score) | gate | New: combines B0/B7-life-stage/B8/banned/recalled/curated interactions |
| **(no v3 equivalent)** | — | **Layer 2 Live-catalog eligibility** (class-aware fields) | gate | New: replaces global NOT_SCORED with class-aware required-field check |
| **(no v3 equivalent)** | — | **Layer 4 Confidence band** (typed metadata) | metadata | New: never changes the number |
| **(no v3 equivalent)** | — | **Class router** | gate | New: routes to generic / probiotic / multi_or_prenatal / omega (P1.5) |

### What v4 preserves entirely from v3

- IQM bio_score as the source of formulation quality (A1)
- Section C multiplicative evidence pipeline with all multipliers and bands
- Manufacturer Violations as a separate negative dimension (−25 cap)
- 4-tier synergy cluster credits
- Probiotic CFU adequacy tier × support-level multiplier
- Omega-3 dose adequacy bonus
- Enzyme recognition
- B0/B1/B2/B6/B8 penalty scales and severity weights
- B3 claim compliance bonus (display claims)
- Cap_per_ingredient = 7 on evidence

### What v4 changes from v3

- B4a now SKU-scope-verified (was regex + manufacturer-level injection)
- B4a + B4b + B4c collectively capped at 15 (was effectively 21+)
- B5 opacity is class-aware (was flat penalty across product types)
- Dose semantics class-aware (generic = supplemental window, multi = full RDA, probiotic = clinical-trial range)
- Section maximums redistributed across 5 dimensions (was 4)
- Top-level scale is 0–100 (was 0–80 then ratio-converted)

### What v4 adds

- 4-layer architecture (safety gate, live-catalog eligibility, class-aware score, confidence)
- Class router with 3 v1 modules (generic, probiotic, multi/prenatal) + omega P1.5 checkpoint
- AI panel + API ground truth + async clinician queue (replaces synchronous clinician panel)
- Cert verification via public registries + cached snapshots + manual overrides
- Typed confidence sub-categories (evidence / label_completeness / verification / identity)
- Shadow scorer + canary rank-order gate + 28-product canary set
- Manufacturer Violations explicitly separated as its own dimension

---

## 18. Flutter score breakdown UI design

This section is the **end-user-facing redesign** that pairs with the v4
scoring rubric. The pipeline tracks more engineering detail than a user
needs; the UI condenses it into the right number of chips.

### Current state (v3) — 4 pillars

The existing Flutter app shows 4 pillars on the score detail screen,
driven by these `products_core` columns:

| v3 pillar | Backing columns |
|---|---|
| Ingredient Quality | `score_ingredient_quality` / `score_ingredient_quality_max` |
| Safety & Purity | `score_safety_purity` / `score_safety_purity_max` |
| Evidence | `score_evidence_research` / `score_evidence_research_max` |
| Brand Trust | `score_brand_trust` / `score_brand_trust_max` |

These map to v3 Sections A / B / C / D. They miss: opacity nuance,
manufacturer violations, transparency, class-aware dose adequacy.

### Proposed v4 — 5 pillars + verdict + confidence + Fit

| v4 pillar | What it shows | What's rolled in (engineering view) |
|---|---|---|
| **Formulation** | What's inside: forms, delivery, synergy, additives | v4 Formulation Quality dimension. Includes A1 bio_score (single line), A2 premium forms, A3 delivery, A4 absorption, A5 excellence (synergy 4-tier), A6 single-ingredient bonus, enzyme recognition; minus B0 moderate, B1 additives, B1 sugar |
| **Dose** | Is the dose meaningful for this class | v4 Dose / clinical relevance dimension. Class-aware: generic = supplemental window, multi = full RDA, probiotic = clinical-trial range. Minus B7 penalty |
| **Evidence** | Backed by science | v4 Evidence Strength dimension. Multiplicative pipeline preserved |
| **Trust** | Tested + Manufacturer history | v4 Testing & Trust (cert verification, GMP, lot-COA) + Manufacturer Trust (D1/D2/D3/D4/D5) − Manufacturer Violations (0 to −25). **Rolled into one user-facing chip; the three engineering dimensions stay separated in `score_breakdown_v4` JSON for audit and power-user expand** |
| **Transparency** | What's disclosed vs hidden | v4 Transparency dimension. Includes B3 claim bonuses (allergen-free / gluten-free / vegan) − B2 allergen penalty − B5 opacity penalty |

### Above the pillars

| Element | Source | Behavior |
|---|---|---|
| **Big score number** | `score_100` | The calibrated 0–100 quality score; audit JSON also carries `raw_score_100` during shadow calibration |
| **Verdict badge** | Layer 1 safety gate | SAFE (green) / CAUTION (yellow) / UNSAFE (orange) / BLOCKED (red, not in live catalog) |
| **Confidence indicator** | Layer 4 typed metadata | Small dot/asterisk: high/moderate/low band. Tap to expand the four typed sub-categories (evidence, label_completeness, verification, identity) |
| **Your Fit** | Flutter-side `fit_score_provider` | 0–20 personalized score, displayed as a band: Strong / Good / Limited / Poor |

### Drill-down on each pillar

Tapping a pillar opens a detail card with the rubric lines that earned
points and the lines that lost points. Stays grounded in real
sub-components — no "magic number." Example for Trust on Thorne Mg:

```
Trust                                            14 / 20
─────────────────────────────────────────────────────────
+ NSF Sport certified (SKU-verified)              +8
+ USP Verified (product-line)                     +4
+ GMP certified manufacturer                      +2
+ Thorne is a trusted manufacturer                +2
+ Full label disclosure                           +1
+ FDA-registered region (US)                      +1
+ Manufacturer violations on file                 0/-25
─────────────────────────────────────────────────────────
Lot-level COA not in our artifact: testing chip
shows "high" confidence; lot-COA would push higher.
```

### Mapping to existing Flutter columns

| Existing column | Replaced by | Removed | Added |
|---|---|---|---|
| `score_ingredient_quality` | `score_formulation_quality` + `score_dose_relevance` | — | Split into 2 |
| `score_safety_purity` | (redistributed) | ✓ | Replaced by Verdict badge + per-dimension penalties |
| `score_evidence_research` | `score_evidence_strength` | — | Same concept, renamed |
| `score_brand_trust` | `score_trust_combined` | — | Now includes manufacturer trust + cert testing + manufacturer violations rolled in |
| (new) | `score_transparency` | — | Added |
| (new) | `verdict` already exists, behavior changed | — | Now driven by Layer 1 gate hierarchy |
| (new) | `confidence_band` + `confidence_drivers` typed JSON | — | Added |

### Worked example — what a user sees on Thorne Magnesium Bisglycinate

```
┌─────────────────────────────────────────────┐
│  Thorne — Magnesium Bisglycinate            │
│                                             │
│           80 / 100                          │
│           SAFE                              │
│           Confidence: High                  │
│                                             │
├─────────────────────────────────────────────┤
│ Formulation       18 / 30   ████░░░░░░     │
│ Dose              22 / 25   ████████░     │
│ Evidence          16 / 20   ████████░     │
│ Trust             14 / 20   ███████░░     │
│ Transparency       8 / 10   ████████░     │
├─────────────────────────────────────────────┤
│ Your Fit: Strong match  (5/5 alignment)    │
│  E1 Dose ✓  E2a Goals ✓  E2b Age ✓         │
│  E2c Interactions: none                    │
├─────────────────────────────────────────────┤
│ Why this score? Tap a chip to see details. │
└─────────────────────────────────────────────┘
```

### Worked example — Garden of Life Once Daily Prenatal Probiotic

```
┌─────────────────────────────────────────────┐
│  Garden of Life Dr. Formulated              │
│  Once Daily Prenatal Probiotic              │
│                                             │
│           58 / 100                          │
│           SAFE                              │
│           Confidence: Moderate              │
│           ⓘ Strain-level CFU not disclosed  │
│                                             │
├─────────────────────────────────────────────┤
│ Formulation       24 / 25   █████████░     │
│ Dose               0 / 25   ░░░░░░░░░░     │
│ Evidence          12 / 20   ██████░░░░     │
│ Trust             12 / 20   ██████░░░░     │
│ Transparency      10 / 15   ██████░░░░     │
├─────────────────────────────────────────────┤
│ Your Fit: Good match (your goal: gut       │
│  health). Pregnant users: this is a        │
│  probiotic — NOT a complete prenatal       │
│  multivitamin.                             │
└─────────────────────────────────────────────┘
```

Note the Dose chip is at zero — strong visual signal that this product
*can't* be evaluated on dose because per-strain CFU is hidden. The
Confidence: Moderate indicator + caveat string make the limitation
explicit without lying about what we don't know.

### What never gets exposed to users

The following are engineering-only and stay in audit/QA, not the UI:

- v3 sub-section labels (A1, B4a, etc.)
- Cert resolver scope details (`sku` vs `product_line` vs `claimed_only`)
- AI panel band votes and disagreement queue routing
- Class-router confidence threshold
- Manufacturer violation severity tier codes

Users see the conclusion, not the engineering reasoning. Power users
can expand each chip to see the rubric lines, but not the internal
classification machinery.

---

## 19. Phased migration

| Phase | Scope | Gate to next phase |
|---|---|---|
| **P0.1a — audit only** | NSF Sport registry POC: fetcher + resolver + comparison report. Run against canary set + top 200 products with claimed certs. Report columns: brand, product, claimed_certs, manufacturer_signals, verified_certs (sku/product_line/brand_only/needs_review/claimed_only), current B4a, proposed B4a, score delta. **No scoring changes yet.** | Comparison report reviewed; false-positive rate < 5% on canary; manual review queue triaged |
| **P0.1b — wire scoring** | Once P0.1a report is approved: rewrite `_compute_certifications_bonus` to read `verified_cert_programs`; reroute manufacturer-injection code at [enrich_supplements_v3.py:9089](../../scripts/enrich_supplements_v3.py#L9089) to populate `manufacturer_cert_signals` (display only). Tests. | All tests green; audit_contract_sync = GREEN; canary 1 (Thorne Mg) score moves into expected band |
| **P0.2** | B5 class-aware opacity: probiotic (named strains, no per-strain CFU) gets reduced penalty; stimulant/nootropic blend keeps full penalty; mineral chelate with elemental dose: no opacity penalty. Tests. | Tests green; targeted regression on canary 1, 15, 26 |
| **P0.3** | Active-only release gate: `build_final_db.py` ships active by default; `--include-discontinued` writes archive bundle. Tests + integrity check. | `audit_raw_to_final.py` clean |
| **P0.4** | NOT_SCORED completeness gate: identity/dose/form completeness enforced at scorer entry. Tests. | Tests green; full pipeline run shows expected NOT_SCORED counts |
| **P0.5** | Probiotic prebiotic credit fix: `prebiotic_present` flows through to probiotic_detail and probiotic bonus. Tests + canary 15 regression. | Canary 15 score moves expectedly |
| **P1** | v4 shadow scaffold: router, both gates, generic module only. Emit shadow columns. **Known tuning areas (two):** (1) **generic single-nutrient weighting** — mechanically mapping v3 sub-section caps into v4 dimensions under-rewards premium single-nutrient products (e.g., Thorne Mg lands ~80 instead of expected 85–92). Likely tuning candidates: bump bio_score weight in Generic Formulation Quality, expand A6 single-ingredient bonus, or add a `generic_single_nutrient` sub-class with a remixed Formulation rubric. (2) **Branded-extract evidence credit** — Transparent Labs KSM-66 currently scores 61.5 with C=4.5/20. Artifact check confirms the evidence pipeline recognizes `BRAND_KSM66` and applies the branded-RCT 0.9× multiplier; the open question is whether the v3 one-entry evidence summary under-credits branded extracts with multiple verified RCT references. Investigate during P1: should `registry_completed_trials_count`, verified PMID count, endpoint relevance, or product-dose alignment increase the branded-extract evidence ceiling? Also decide whether KSM-66's IQM PK caveat (`bio_score=11`, low plasma withanolides) should cap Formulation or be offset by outcome evidence. Fix lands in P1 or as a P0.6 evidence-data audit if root cause is data-side. Decide after first shadow run against canary rows 1–4 (mineral singles) and 22–23 (branded vs commodity botanical). | Generic canary subset (1–9, 19–24) ranks correctly **and** premium single-nutrient products (rows 1, 22) land in their provisional bands |
| **P1.5 — shadow calibration + omega module decision checkpoint** | Apply the final-assembly-only affine calibration `25 + 0.75 * raw_score_100` to correct generic-module score compression while preserving raw dimension math for audit. Then run the generic-module shadow scorer specifically against the omega-3 canary subset (rows 5–9). Compare expected vs actual rank order and review IFOS/EPA/DHA/oxidation signals. **Decision gate:** does calibrated generic-module handle omega-3 acceptably, or does omega need its own module before P2? Codex flagged this — fish oil signals (IFOS lot star ratings, EPA:DHA ratio, oxidation) are not the same as generic minerals. | Calibration keeps canary rank order stable and removes clearly unfair SAFE→POOR compression without top-end inflation; then either (a) omega rows rank correctly within ±1 → omega stays in `generic` for v1, or (b) omega rows fail → add `omega` module to the v1 scope BEFORE P2 |
| **P2** | Probiotic module. Shadow on full probiotic subset (~696 products). Review top movers ±15. | Probiotic canary (15–18) rank-order passes |
| **P3** | Multi/prenatal module. Shadow on full subset. | Multi canary (10–14, 19–21) rank-order passes |
| **P4** | **AI panel + API ground-truth rank-order check** across full 28-canary set. Claude + ChatGPT each score independently against the fixed rubric prompt; agreements stand; disagreements (>1 band) take the lower band and route to [CLINICIAN_VERIFICATION_QUEUE.md](CLINICIAN_VERIFICATION_QUEUE.md). API values (NIH ODS, NCCIH, PubMed content-verified) override any model opinion. Web research via subagent for class-tuning calls without API ground truth. Clinician queue is async; production does NOT block. | ≥ 23 of 28 within ±1 rank; AI panel agreement rate ≥ 80% on canary; all API contradictions resolved in favor of API; queue entries logged with full context |
| **P5** | Cutover: Flutter reads v4; v3 columns deprecated; one clean release cycle. | One release cycle with no regressions; manifest version bump |

Each phase is 1–2 weeks. Total: 8–12 weeks. Reversible at every gate.

### Immediate recommendation — start P0.1a only

Concrete deliverables for the first work item. **No scoring changes
land in P0.1a.** This is an audit-only POC that gives hard evidence
before we touch production scoring.

1. **Parse NSF Sport public registry / printable list** into a normalized
   snapshot at `scripts/data/cert_registry.json` (schema v6.0, with
   `_metadata` contract). NSF Sport only — other registries deferred
   until the pipeline pattern is proven.
2. **Build the cert resolver** at `scripts/cert_resolver.py` with the
   conservative fuzzy thresholds in §10 and the `needs_review` queue.
3. **Build the comparison report** at
   `scripts/api_audit/cert_audit_report.py`. Run against the canary
   set + top 200 products with claimed certs. Emit a CSV/JSON with
   columns: brand, product, claimed_certs, manufacturer_signals,
   verified_certs (scope), current B4a, proposed B4a, score delta,
   needs_review rows.
4. **Review the report manually.** False-positive rate on canary must
   be < 5%. Triage the `needs_review` queue. Sanity-check a sample of
   `claimed_only` matches to confirm no real SKU-verified certs are
   being missed.
5. **Only after the report is approved**, proceed to P0.1b (wire
   `verified_cert_programs` into scoring, reroute manufacturer-injection
   to `manufacturer_cert_signals`).

If the FP rate exceeds 5%, raise the fuzzy thresholds and rerun. If
the registry doesn't match any canary products, add manual overrides
at `scripts/data/curated_overrides/cert_verification_overrides.json`
and rerun. Iterate until the report is trusted before any scoring
code moves.

---

## 20. Risks & mitigations

| Risk | Mitigation |
|---|---|
| Class router misclassifies (probiotic with vitamins) | Conservative threshold 0.8; fallback to `generic`; manual override via `supplement_type_audit` |
| Cert registry incomplete | Stage; partially-verified products keep partial credit with confidence flag, not full removal |
| Multi-class products (AG1) | Route to dominant nutrient class + apply opacity penalty; canary 25 covers |
| Score inflation across catalog | Mandatory diff report: median, p25, p75 must not shift > 5 pts catalog-wide |
| External anchors disagree | API ground truth wins. Document disagreements in canary report. Clinician queue holds residual judgment calls |
| Cognitive debt — 3 modules → 10 | Hard cap: no new module until P1–P4 pass for existing 3 |
| ConsumerLab licensing | Out of scope. Manual reference only when paid access exists |
| Cert registry scraping fragility | Quarterly cadence, not real-time; manual overrides cover gaps; tests assert >= 80% canary registry hit rate |
| **LLM hallucination on clinical claims** (per `critical_no_hallucinated_citations` memory) | AI panel output is **never** ground truth for PMIDs/CUIs/RXCUIs/NCT IDs/UNIIs — every identifier is content-verified via live API (`scripts/api_audit/verify_*.py`). AI panel scores are class-rubric calibration only; clinical identifiers route through the existing verification pipeline. |
| **AI model agreement convergence** (Claude + ChatGPT quietly agree on the same wrong answer) | Track aggregate agreement rate per release; if > 95% on canary, add a third model family (Gemini or Mistral) for spot-check. Sample N=10 random canary items per release for human spot-review to catch convergent error |
| **Clinician queue grows unbounded** | Track queue age distribution in shadow report (§15 item 10). Items pending > 90 days auto-flagged for triage. Resolved items become regression tests so future releases can't regress |
| **No synchronous clinician review introduces drift** | Accept the trade-off explicitly: throughput over synchronous clinical authority. Compensated by (a) API ground truth taking precedence, (b) conservative-default-on-disagreement, (c) async clinician feedback loop, (d) confidence band surfacing uncertainty to end users. Re-evaluate after first shadow release cycle: if queue resolution rate is high and corrections are systematic, the trade is working; if corrections are scattered random fixes, reconsider |
| **AI panel prompt drift across model versions** | Prompt template pinned to a hash, stored in `scripts/scoring_v4/prompts/`. Prompt-hash + model-version + timestamp captured in every comparison report. Prompt updates require explicit decision-log entry |

---

## 21. What we will NOT do

- Manually bump one product. Fix the class.
- Build 10 modules at once. Three in v1: generic, probiotic, multi/prenatal.
- Use ConsumerLab as an automated anchor (paid, licensing risk).
- Let brand-level cert evidence score as product-level certification.
- Hide risky opaque blends by excluding them. Show CAUTION when enough
  identity exists to warn.
- Ship NOT_SCORED or incomplete products in the live catalog.
- Cut over to v4 without a full shadow release cycle and canary review.
- Add "UX confidence" as a scored dimension. Confidence is metadata.
- Make identity completeness a 20-pt scored line. It is a gate.
- Pick scoring numbers because they "feel fair." Anchor first.
- Touch enrichment in v1 except for the two known bugs (manufacturer
  cert injection rerouting, prebiotic credit fix). Per-strain CFU
  extraction and other major enrichment upgrades are P6+.

---

## 22. Open questions (track decisions here)

- [ ] Where do `+1` brand-only cert credits land? Manufacturer trust (D) is
      currently capped at 5. Confirm cap headroom.
- [ ] For multi/prenatal: does the "missing 2+ critical nutrients = floor at
      60" rule create odd cliff behavior? Pilot on canary 10–14, 19–21.
- [ ] Confidence band — three levels (high/moderate/low) or five? UX call.
- [ ] What's the freshness threshold for cert registry hits? `verified_at`
      older than 18 months → drop to `claimed_only`?
- [ ] Should B7 (>150% UL) become BLOCKED for life-stage-sensitive nutrients
      (vitamin A retinol in pregnancy)? Tracked in safety gate spec.
- [ ] Canary 28 (BLOCKED safety canary) — pick a real product ID once a
      DMAA-positive recalled SKU is identified in the catalog.
- [ ] **Fuzzy match precision target.** Current draft sets `sku` threshold
      at ratio ≥ 92 and `needs_review` band at 80–91. Validate against
      P0.1a comparison report — if false-positive rate > 5%, raise
      thresholds. (Codex principle: false positives worse than missed
      bonuses.)
- [ ] **Dietary intake defaults per nutrient** for the supplemental-window
      dose calculation. Need a small reference table (NIH ODS / NHANES)
      mapping each scored nutrient to typical adult intake so the
      `supplemental_window` can be evaluated at scoring time.
- [ ] **Are gummy multis a sub-class or just a multi with a delivery
      penalty?** Canary 19 (Nature Made Gummies) will tell us whether
      multi-module logic alone is enough, or if `multi_gummy` needs its
      own micronutrient-coverage expectations (gummies typically can't
      carry iron).
- [ ] **Omega-3 dedicated module — yes/no?** Decided at P1.5 gate. If
      generic-module shadow fails on canary rows 5–9, add an `omega`
      module to v1 (IFOS lot ratings, EPA:DHA ratio, oxidation status,
      source = fish/krill/algae). Otherwise omega stays in `generic` and
      we revisit in v5.
- [ ] **What does the Flutter app show for products that fail the
      live-catalog eligibility gate?** Three options: (a) excluded
      entirely from search/scan, (b) shown with "insufficient label data
      to score" banner and no number, (c) shown only via direct UPC scan
      with stale-label warning. Currently the doc implies (a); UX call.
- [ ] **AI panel model composition.** v1 = Claude + ChatGPT. Which
      specific model IDs? (e.g., Claude Sonnet 4.7 vs Opus, GPT-4 vs
      GPT-5.) Stable model ID pinning required so prompt-hash +
      model-version pair is reproducible. Re-evaluated each release —
      bump to newer model only via decision-log entry.
- [ ] **AI panel disagreement threshold.** Current spec: "> 1 band"
      triggers conservative default + queue. Is "band" defined as
      ±10 pts? ±5 pts? Need a concrete numeric threshold piloted on the
      canary set before P4.
- [ ] **Third model for convergence spot-check** — if Claude + ChatGPT
      agree > 95% on canary, when do we add Gemini/Mistral as a
      tiebreaker, and how often is the spot-check run (every release?
      every quarter?)
- [ ] **Clinician verification queue cadence.** No SLA on synchronous
      review, but: when does an unresolved queue entry get flagged for
      escalation? Suggested: 90 days. Confirm with product.
- [ ] **Web research subagent source whitelist.** Restrict to
      NIH/NCCIH/peer-reviewed/Examine.com summary by default. Should
      Cochrane reviews be added? r/Supplements expert posts (no)? Need a
      curated source whitelist in `scripts/scoring_v4/prompts/`.
- [ ] **AI panel scoring rubric prompt — initial draft.** Each rubric
      file already has `dimension_descriptions`. The AI panel prompt
      should consume the rubric file directly so dimension definitions
      stay class-aware. Confirm prompt format before P4.

---

## 23. Decision log

| Date | Decision | Owner |
|---|---|---|
| 2026-05-18 | Lock 4-layer architecture (safety gate / completeness gate / class score / confidence metadata) | Sean, Claude, Codex |
| 2026-05-18 | Lock 3 modules in v1: generic, probiotic, multi/prenatal | Sean, Codex |
| 2026-05-18 | ConsumerLab dropped as automated anchor | Codex |
| 2026-05-18 | P0 ordering: cert → B5 opacity → active-only → NOT_SCORED → prebiotic credit, then v4 shadow | Sean, Codex |
| 2026-05-18 | Cert verification via public registry snapshots + rapidfuzz resolver + manual overrides | Claude, Codex |
| 2026-05-18 | B4a v4: SKU=8/4/2, product_line=6/3/1, brand_only=0 (routes to D), claimed_only=0, cap=12 | Claude |
| 2026-05-18 | Canary set = 28 products across 12 classes; cutover requires ≥23/28 within ±1 rank | Claude, Sean |
| 2026-05-18 | 100 is effectively unreachable for shipped products; premium ceilings ~88–95 | Sean (Thorne pushback), Codex (agreement) |
| 2026-05-18 | **Class-aware dose semantics.** Generic single-nutrient scored against `supplemental_window`, NOT full RDA. Verified against [NIH ODS Mg fact sheet](https://ods.od.nih.gov/factsheets/Magnesium-HealthProfessional/) — adult supplemental UL = 350 mg, food-source UL not applicable. Multi/prenatal still scored against full-RDA coverage of expected panel. | Codex (correction), Claude (research), Sean |
| 2026-05-18 | **Thorne Mg expected band raised** from initial 78–88 to **88–92 (SKU-verified) / 82–88 (product-line) / 76–82 (claimed-only)**. Driver: supplemental-window framing, not full-RDA penalty. | Codex (pushback), Sean (agreement) |
| 2026-05-18 | **Demote, don't delete manufacturer cert signal.** Reroute [enrich_supplements_v3.py:9089](../../scripts/enrich_supplements_v3.py#L9089) output to new `manufacturer_cert_signals` field (display/trust metadata only, never scores). Preserves UX signal while removing scoring pollution. | Codex (correction), Claude |
| 2026-05-18 | **Three-tier cert field split** on `certification_data`: `claimed_cert_programs` (regex, display) / `manufacturer_cert_signals` (brand evidence, display) / `verified_cert_programs` (SKU/product-line registry hit, scores). Only the third tier reaches the scorer. | Codex, Claude |
| 2026-05-18 | **Conservative fuzzy match — precision over recall.** Borderline matches go to `needs_review` queue rather than auto-classifying. Initial thresholds: SKU ≥ 92 ratio, product-line keyword overlap ≥ 85. Tuned via P0.1a report. | Codex principle, Claude implementation |
| 2026-05-18 | **P0.1 split into P0.1a (audit-only POC + comparison report) and P0.1b (scoring wire-in).** No scoring changes land until P0.1a report is reviewed and false-positive rate < 5% on canary. | Codex, Sean |
| 2026-05-18 (review pass) | **Completeness gate is class-aware**, not a single threshold. Probiotic eligibility = total CFU + named strains + active identity + safety parsed (per-strain CFU is *not* required — Garden of Life Prenatal Probiotic is explicitly scoreable). Multi/prenatal, generic mineral/vitamin/botanical/omega-3, stimulant/nootropic blend each get their own required-field list. | Codex (correction), Claude |
| 2026-05-18 (review pass) | **Live-catalog eligibility, not NOT_SCORED verdict on app.** Failed completeness → `is_live_eligible=false` and excluded from live catalog. Archive/QA still emits `verdict=NOT_SCORED` for the blob. Flutter never displays NOT_SCORED. | Codex, Sean |
| 2026-05-18 (review pass) | **Prebiotic credit folded into probiotic formulation quality**, not an external "up to +5 bonus". Formulation rebalanced 5+5+5+5+5 → 4+4+4+4+4+5(prebiotic) = 25. Prevents score inflation past 100. | Codex (correction), Claude |
| 2026-05-18 (review pass) | **Probiotic transparency rule: "all strain identities named"**, not "no blend". Many legitimate probiotic labels use a named "Probiotic Blend" container while listing every strain. | Codex (correction) |
| 2026-05-18 (review pass) | **Testing & trust dimension hard-capped at 15** across B4a + B4b + B4c collectively. B4a soft cap tightened from 12 → 10 to leave headroom. Realized max (SKU NSF Sport 8 + SKU USP 4 + GMP 4 + lot-COA 1 = 17) is clamped to 15. | Codex (correction), Claude |
| 2026-05-18 (review pass) | **Canary row 1 expected band aligned** to cert-conditional form: 88–92 (SKU) / 82–88 (product-line) / 76–82 (claimed-only). Earlier 78–88 single-band was inconsistent with decision-log entry. | Codex (correction) |
| 2026-05-18 (review pass) | **Omega-3 gets a v1 decision checkpoint at P1.5**, not deferred to v5. Generic-module shadow runs against omega canary rows 5–9 first; if rank order fails, add `omega` module to v1 scope before P2. | Codex (correction), Claude |
| 2026-05-18 (merge) | **Single canonical doc — Option A.** Merged Codex's `SCORING_V4_FINAL_WORKING_PLAN.md` structural improvements into this doc and retired the working-plan file. New sections: §2 Pipeline shape, §3 Live catalog gates, §5 B5 opacity policy, §9 Omega/fish oil policy, §15 Shadow report requirements. Kept: decision log, open questions, schema fields, code architecture, worked examples, class-aware completeness table, risks/mitigations, source-code line refs, prebiotic credit fix. Two docs would have drifted. | Codex, Claude, Sean |
| 2026-05-18 (merge) | **Explicit testing/trust dimension hard clamp.** `realized_testing_trust = min(15, sum(verified_cert_points) + gmp_points + batch_traceability_points)`. The clamp is the single source of truth — sub-component soft caps are reviewer orientation, not enforced bounds. | Codex |
| 2026-05-18 (merge) | **Public registry source URLs verified live.** All 8 cert registry URLs in §10 checked 2026-05-18 and locked into the doc with full URLs (not bare domains). Future quarterly refresh validates each URL still resolves and the listing format hasn't changed. | Codex |
| 2026-05-18 (Codex review-pass) | **Confidence ontology typed.** Layer 4 split from `{band, drivers[]}` into typed sub-categories: `evidence`, `label_completeness`, `verification`, `identity`. Top-level `band` derived via worst-case rule. Prevents `confidence` from becoming a junk drawer. | Codex (correction), Claude |
| 2026-05-18 (Codex review-pass) | **Score scale anchors formalized.** Theoretical max 100, practical max ~95, observed ceiling per-release, premium ceiling 82–92, quality floor ~20. Anchors the "100 unreachable" principle operationally. | Codex (correction), Claude |
| 2026-05-18 (Codex review-pass) | **Class-specific UI explanation cards.** Each rubric file owns `dimension_descriptions` block with class-specific wording for Flutter render. A probiotic 84 and fish-oil 84 are no longer rendered as evaluated against identical criteria. | Codex (correction), Claude |
| 2026-05-18 (Codex review-pass) | **Omega module is likely mandatory in v1.** P1.5 decision gate stays as the formal check, but engineering plans capacity for an `omega` module landing in v1 scope. EPA/DHA, IFOS, oxidation, source, form are distinct enough from minerals/vitamins that generic-module probably can't rank canary rows 5–9 correctly. | Codex (prediction), Claude (acceptance) |
| 2026-05-18 (Sean) | **No synchronous clinician panel.** Replaced with multi-model AI panel (Claude + ChatGPT) + authoritative API ground truth + async clinician verification queue at [CLINICIAN_VERIFICATION_QUEUE.md](CLINICIAN_VERIFICATION_QUEUE.md). Production never blocks on clinician review. Trade-off: throughput over synchronous clinical authority. Mitigations: API ground truth beats LLM opinion, conservative default on AI disagreement, clinician corrections feed back as curated overrides + regression tests. | Sean (decision), Claude (rigor preservation), Codex (anti-bias rules) |
| 2026-05-18 (AI panel) | **API ground truth precedence: NIH ODS / NCCIH / FDA / PubMed (content-verified) / NSF/USP registries override any model opinion.** Per `critical_no_hallucinated_citations` memory: every PMID/CUI/RXCUI/NCT ID/UNII used in scoring is content-verified via live API. AI panel scores are class-rubric calibration only, never the source of truth for clinical identifiers. | Sean, Claude (rigor) |
| 2026-05-18 (AI panel) | **AI panel anti-bias rules.** Blinded scoring (each model independently), fixed rubric prompt at `scripts/scoring_v4/prompts/canary_rubric_review.md`, two model families minimum (Claude + ChatGPT), disagreement > 1 band → conservative (lower) default + queue, API ground truth beats both, conflict logged with full context, anti-convergence spot-check (third model when agreement > 95%). | Codex (clinician-panel principles translated to AI), Claude |
| 2026-05-18 (web research) | **Web research integration via subagent only.** Per CLAUDE.md global rule, WebSearch never runs in main session. Subagent returns summarized findings restricted to NIH/NCCIH/peer-reviewed/Examine.com sources. PMIDs content-verified before citation. "Insufficient reliable sources" → clinician queue. | Sean, Claude |
| 2026-05-18 (Sean rubric-grounding review) | **Fixed bio_score double-count in Generic module.** Earlier drafts had "Mapped to a recognized form: 10" and "Bioavailability score from IQM: 10" as separate lines. These are the same field — IQM `bio_score` IS the form mapping (v3 A1, cap 18). Generic Formulation Quality now has ONE bio_score line at 15, plus distinct A2-A6 sub-components (premium forms 4, delivery 3, absorption 3, excellence 4 including synergy 4-tier, single-ingredient bonus 1, enzyme up to 2). | Sean (catch), Claude (fix) |
| 2026-05-18 (Sean rubric-grounding review) | **Manufacturer Violations is its own dimension (0 to −25), NOT inside Testing & Trust.** Earlier drafts buried it as "−5 to testing/trust" which understated by 5×. New §16 formalizes: severity-tiered (CRITICAL −12 to −20, HIGH −10 to −12, MODERATE smaller), recency-weighted (0.25–1.0×), cap_total −25. Data source: `scripts/data/manufacturer_violations.json` (89 entries) + `manufacture_deduction_expl.json`. Example: Prophet Premium Blends (Diamond Shruumz Class I recall, deaths reported) = −20 base × 0.5 recency = −10 realized. | Sean (correction), Claude |
| 2026-05-18 (Sean rubric-grounding review) | **B7 dose_safety is a penalty (−2 per offense, cap −3 at >150% UL), NOT a verdict change by itself.** Earlier drafts conflated B7 with the UNSAFE verdict. Verdict change only occurs via Layer 1 safety gate for life-stage-sensitive nutrients (e.g., retinol in pregnancy). | Sean (correction), Claude |
| 2026-05-18 (Sean rubric-grounding review) | **Restored stripped v3 sub-components.** Re-incorporated: 4-tier synergy cluster credits (A5), probiotic_cfu_adequacy (tier × support-level multiplier), omega3_dose_bonus (was Section E), enzyme_recognition, B0_immediate_fail (moderate/watchlist tiers), B1_dietary_sugar_penalty, B3_claim_compliance (allergen-free/gluten-free/vegan), B6_marketing_penalty, B8_caers_adverse_events (currently disabled in v3, retained framework), cap_per_ingredient = 7 on Section C, full Section C multiplicative pipeline (study_type × evidence_level × effect_direction × enrollment × dose_guard × top_N + depth_bonus). | Sean (catch), Claude |
| 2026-05-18 (Sean rubric-grounding review) | **Added §17 v3 → v4 mapping table.** Full side-by-side from v3 sub-section to v4 module/dimension. Records what's preserved entirely, what changes, what's added — the bridge between existing codebase and the v4 redesign. Engineering can read v3 code with v4 docs side-by-side without re-deriving the mapping. | Sean (request), Claude |
| 2026-05-18 (Sean rubric-grounding review) | **Added §18 Flutter score breakdown UI design.** Replaces the v3 4-pillar display (Ingredient Quality / Safety & Purity / Evidence / Brand Trust) with the v4 5-pillar layout (Formulation / Dose / Evidence / Trust / Transparency) + verdict badge + confidence indicator + Your Fit. Manufacturer Trust + Testing certs + Manufacturer Violations roll into the user-facing "Trust" pillar; the three engineering dimensions stay separated in the `score_breakdown_v4` JSON for audit. Worked examples for Thorne Mg and Garden of Life prenatal probiotic show the UI layout. | Sean (request), Claude |
| 2026-05-18 (Sean rubric-grounding review) | **Thorne Mg expected band lowered to 74–86 across cert scopes** (was 76–92 in earlier drafts that double-counted bio_score). Both NSF Sport + USP SKU-verified: 82–86. One SKU + one product-line: 78–82. Both product-line: 74–78. Claimed-only: 68–74. The lower numbers reflect honest mapping from v3 without inflation. | Sean (correction), Claude |
| 2026-05-18 (Sean — option 3) | **Companion engineering bridge doc created at [SCORING_V3_TO_V4_MAPPING.md](SCORING_V3_TO_V4_MAPPING.md).** §17 of this spec is the **concept-level** mapping (architectural); the companion doc is the **code-level** mapping (config keys, file:line code refs, test paths, SQLite migration column list, shadow-comparator column layout). Both stay in sync via the decision log. An engineer opens the companion alongside `score_supplements.py` when implementing v4; reviewers/architects/Codex stay in this spec. | Sean (request — option 3), Claude |
| 2026-05-18 (Codex band correction) | **Thorne band re-opened to provisional 85–92 (SKU+SKU) / 82–88 (SKU+line) / 78–84 (line+line) / 72–78 (claimed) — NOT locked at the mechanical 74–86 from v3-direct mapping.** v4 must not inherit v3's structural bias of under-rewarding premium single-nutrient products. Final band locks at P1 canary tuning, with the AI panel + API ground truth + clinician queue as anchors — not by instinct. | Codex (correction), Sean (agreement) |
| 2026-05-18 (principle) | **v4 is not a v3 reskin.** v4 preserves valid v3 mechanics (bio_score, multiplicative evidence pipeline, synergy 4-tier, probiotic CFU adequacy, manufacturer violations cap, etc.) **but is not constrained by v3's old weighting where that weighting under-rewards a legitimate class signal.** The shadow scorer + canary review is where mis-weights surface and get tuned — not by mechanically copying v3 sub-section caps into v4 dimensions. | Codex, Sean |
| 2026-05-18 (P1 tuning area) | **Generic single-nutrient weighting flagged as the known v1 tuning area.** P1 phase explicitly captures that mechanically-mapped Thorne lands ~80 vs expected 85–92, and lists three tuning candidates (bio_score weight bump, A6 single-ingredient bonus expansion, or `generic_single_nutrient` sub-class with remixed Formulation rubric). Decision made after first shadow run against canary rows 1–4, 22–24. | Sean, Claude |
| 2026-05-18 (UI confirmation) | **One user-facing Trust pillar for v1**, with the audit JSON keeping three engineering dimensions separate: verified testing/certs, manufacturer trust, manufacturer violations. Confirmed per Codex's recap. Re-evaluate splitting if user research shows the single chip hides important Trust nuance. | Codex, Sean |
| 2026-05-18 (Sean canary correction — KSM-66, artifact recheck) | **Transparent Labs KSM-66 band kept provisional but narrowed to 82–90 (SKU-verified) / 78–86 (line) / 72–82 (claimed-only).** Catalog check (DSLD `305203`) confirmed current 61.5 score with Evidence=4.5/20. Artifact check also confirmed this is **not a missing match**: `evidence_data.clinical_matches[0]` is `BRAND_KSM66`, `match_method=standard_name`, `evidence_level=branded-rct`, `study_type=rct_multiple`; Section C arithmetic is 5 × 0.9 = 4.5. The P1 question is weighting/calibration, not resolver failure. | Sean (catch), Claude, Codex recheck |
| 2026-05-18 (P1 tuning area #2) | **Branded-extract evidence credit added as a P1 tuning area** (alongside generic single-nutrient weighting). Root-cause options corrected after artifact inspection: not "does KSM-66 match?" (it does), but whether v4 should credit verified PMID count / registry trial count / endpoint relevance / dose alignment more heavily for branded extracts, and how to balance outcome evidence against IQM's KSM-66 PK caveat (`bio_score=11`, low plasma withanolides). Fix lands in P1 or as a P0.6 evidence-data audit if root cause is data-side. | Sean, Claude, Codex recheck |
| 2026-05-18 (P0.1a COMPLETE — audit-only, no scoring changes) | **Cert verification resolver + NSF Sport fetcher + audit report shipped.** Files: `scripts/cert_resolver.py` (conservative thresholds + needs_review queue), `scripts/api_audit/verify_certifications.py` (NSF Sport DS-ABS PDF parser, listings.nsf.org live-URL stub), `scripts/api_audit/cert_audit_report.py` (canary + top 200 comparison report), `scripts/data/cert_registry.json` (1058 NSF Sport SKU records from DS-ABS PDF dated 2020-12-18), `scripts/data/curated_overrides/cert_verification_overrides.json` (empty seed, schema v6.0). Tests: `scripts/tests/test_cert_resolver.py` (20/20 pass) + `scripts/tests/test_cert_audit_canary.py` (7/7 pass). **Audit findings on canary + top 200 claimed-cert products: 36 of 202 have at least one SKU-verified cert; 164 (81%) had v3 overcredit and would demote under v4. Median Δ B4a = −10, mean = −11.1.** Confirms manufacturer-injection bug at scale (Thorne Basic Prenatal et al. all show v3 B4a 15 → v4 0). Canary anchors behave correctly: Thorne Mg Bisglycinate → sku (NSF Sport); other claims (NSF Certified, USP) resolve to claimed_only since those registries aren't loaded yet. **Live source (listings.nsf.org) pending Sean's URL confirmation before any P0.1b scoring wire-in. PDF is Dec 2020 stale; do not promote to production scoring until live source confirmed and re-audited.** | Sean (direction), Claude (build) |
| 2026-05-18 (P0.1a UPGRADED — live registries, recency gate, queue workflow) | **Following Codex code-review:** swapped the stale 2020 PDF for live NSF sources. Added live NSF Sport scraper (`fetch_nsf_sport_live` — single GET to `nsfsport-prod.nsf.org/certified-products/search-results.php`, returns 1253 SKU records server-rendered) and NSF/ANSI 173 Contents Certified scraper (`fetch_nsf_173_live` — single GET to `info.nsf.org/Certified/Dietary/Listings.asp`, returns 263 companies → 2850 product records). Added recency gate: `RECENCY_AUDIT_ONLY_DAYS=180`, per-source snapshot tracking, per-record `_recency_status`, `CertResolution.scoring_blocked_reason`. Stale snapshots still match (audit useful) but `scores_points()` returns False — production scorers cannot grant points against blocked records. Audit report schema v1.1: top-level `needs_review_queue` and `scoring_blocked_queue` arrays with reviewer-ready context (matched candidate, confidence, recency, override template). PDF parser kept as fixture path with `audit_only` semantics. Tests: **37/37 pass** including 4 new recency-gate cases, 2 multi-source registry cases, 3 audit-report schema cases. **Live-data audit (4103 records, today's snapshot): 83 of 202 products have SKU-verified cert (up from 32), 118 demote (down from 168), mean Δ B4a −8.71. Thorne Mg now matches BOTH NSF Sport AND NSF/ANSI 173 → v4 B4a 12 (was 8 with stale PDF).** | Codex (review), Claude (build) |
| 2026-05-18 (architecture lock — Codex) | **v4 ships as a SEPARATE shadow scorer at `scripts/score_supplements_v4_shadow.py`, NOT an in-place edit of `score_supplements.py`.** v3 remains production truth through the entire v4 build. Both consume the same enriched input contract from `enrich_supplements_v3.py`. Shared helpers where stable (`cert_resolver.py`, normalizer lookups). Independent scoring policy/rubric layer to prevent drift between two giant files. Shadow emits side-by-side `shadow_score_v4_{100,module,verdict,confidence,breakdown,anchored}` columns; v3 columns stay authoritative. Cutover at §19 P5 is a config/contract decision after canaries + full-catalog deltas pass, not a scorer rewrite. **No Flutter cutover until shadow comparator report passes.** Renamed §14 schema field `shadow_score_v4_band` → `shadow_score_v4_confidence` and added `shadow_score_v4_verdict` per Codex's field-list spec. | Codex (lock), Claude (doc alignment), Sean |
| 2026-05-18 (P0.1b SHIPPED — cert overcredit integrity fix, narrow scope) | **Enrichment + scorer patches land the three-tier cert split in production.** `enrich_supplements_v3.py`: (a) renamed `_inject_manufacturer_certs` → `_collect_manufacturer_cert_signals`, which returns a separate list instead of mutating `third_party_programs.programs` (manufacturer-injection bug structurally removed); (b) new `_resolve_verified_cert_programs` calls `cert_resolver.resolve()` against the live registry; (c) `certification_data` now emits three fields — `third_party_programs` (claimed display only), `manufacturer_cert_signals` (brand evidence display only), `verified_cert_programs` (scorer-only). Top-level projection adds `verified_cert_programs` and `manufacturer_cert_signals` alongside legacy `named_cert_programs`. `score_supplements.py`: `_compute_certifications_bonus()` rewritten to read `verified_cert_programs` only, applies SCOPE_POINTS diminishing returns (sku 8/4/2, product_line 6/3/1, brand_only/needs_review/claimed_only 0), refuses entries with `scoring_blocked_reason`, hard cap B4a=12. Tests: 10 new in `test_b4a_p01b_integrity.py` covering Thorne Mg 2-sku=12 (not v3-stacked 15), Thorne Basic Prenatal brand_only=0 (not v3 inflated 15), stale registry=0, needs_review=0, mixed scopes clamped, missing `verified_cert_programs` field=0 (no fallback to old behavior). Two pre-existing v3 IFOS-cert tests updated to provide `verified_cert_programs` per new contract. **304/304 scoring + cert tests pass.** | Sean (approval), Codex (review), Claude (build) |
| 2026-05-18 (P0.1b config drift fix — Codex) | **`scoring_config.json` patched to document the scope-aware B4a contract.** Stale config still showed `B4a_named_programs: {points_per_program: 5, cap: 15}`, dangerous for future devs. Codex added `B4a_verified_programs.scope_points` (sku/product_line/brand_only/needs_review/claimed_only) with cap=12 and `requires_no_scoring_blocked_reason: true`. Deprecated `B4a_named_programs.points_per_program` and `cap` to 0 with `_deprecated` note. New regression test `test_scoring_config_documents_scope_aware_b4a_contract` locks the config shape so it cannot drift back silently. **305/305 cert tests pass** with the drift gate in place. | Codex (catch + fix), Claude (acknowledge) |
| 2026-05-18 (P0.1b PROOF-OF-WORK — canary pipeline rerun) | **Reran enrichment + scorer on a 6-product canary batch to prove the integrity fix actually changes shipped data, not just code/tests.** Results: **Thorne Magnesium Bisglycinate (298074):** v3 stacked all 3 claimed programs for B4a=15; v4 fresh enrichment only verifies NSF Sport SKU on the live registry → B4a **8** (Δ −7). **Thorne S.A.T. / Siliphos / Glucosamine Sulfate (63571 / 63600 / 63601):** v3 inherited B4a from Thorne's manufacturer evidence; v4 resolver returns brand_only → B4a **0**. Section_breakdown.B confirms: B4a=0, scope_counts={}, no points granted from manufacturer-injection alone. **Garden of Life prenatal probiotic (274081):** resolver flags NSF Certified at 0.85 confidence → needs_review → B4a **0** until reviewer confirms via overrides. **Transparent Labs KSM-66 (305203):** no claimed certs → B4a **0** (unchanged). **Caveat:** v4 enrichment resolver only verifies programs CLAIMED on label or in manufacturer evidence; it does not eagerly auto-discover registry matches for unclaimed programs. Conservative default by design (matches Codex's "regex finds claims, registry verifies" model). Auto-discovery is out of P0.1b scope. **Note:** the integrity fix's effect on the visible total quality score is partially masked by Section B's existing `bonus_pool_cap=5` — the inflated B4a was getting clamped at the section level anyway. The fix is still real (B4a breakdown number is now honest, shadow-report deltas are correct, manufacturer-injection structurally removed); the section_cap was the v3 safety net hiding the bug from total-score visibility. | Codex (insistence on rerun proof), Claude (build) |
| 2026-05-18 (full-suite green fix — Python 3.9 compat in ingest_suppai) | **`scripts/ingest_suppai.py:162` used `zip(..., strict=False)` which is Python 3.10+ only.** Pre-existing bug (unrelated to certs) caused the broader suite to fail on the current Xcode-bundled Python 3.9. Fix: removed the `strict=` kwarg — plain `zip()` already stops at shortest (equivalent to `strict=False` semantics), so behavior is identical on 3.10+ and now works on 3.9. Added comment explaining the choice. Targeted test `test_build_drug_name_to_rxcui_index` passes. Sean's rule: don't accept a red full suite even when failures are unrelated. | Sean (rule), Codex (concur), Claude (fix) |
| 2026-05-18 (P0.1c — cert claim provenance audit, AUDIT-ONLY) | **Built `scripts/api_audit/cert_claim_provenance_audit.py` to separate label-text cert claims from manufacturer-injected ones, per Codex's recommendation that current `claimed_only=0` may UNDERCREDIT legitimate product-level label claims for programs we haven't scraped yet (USP, Informed, IFOS, etc.). Audit walks all 8440 catalog blobs (2583 with cert claims) and reports per-program: `label_count` (product-level evidence), `manufacturer_count` (brand injection), `total_products`. Plus interim handling guidance (provisional_b4a_if_product_label_evidence / omega_only / formulation_a5_not_b4a / b3_claim_compliance / manual_review_only / regulatory_filing_not_purity). **Findings (close match to Codex's count):** USP Verified 1451 (763 label + 688 mfg), Informed Choice 379 (all label), IFOS 262 (only 10 label vs 252 mfg — risky), Friend of the Sea 112 (all label), MSC 28, Informed Sport 2, BSCG/GOED/Labdoor/Health Canada NPN 1 each. **Decision deferred:** whether to add `label_asserted_product` interim scope (proposed 2/1/0 cap 3 B4a) lands in P0.1d after Sean/Codex review the report. P0.1c output: `scripts/api_audit/reports/cert_claim_provenance_audit_*.{json,md}`. **No scoring changes applied.** | Codex (proposal), Claude (build + run) |
| 2026-05-19 (P0.1 scraper batch — USP/Informed/IFOS) | **Live registry cache expanded to six sources without a production pipeline rerun.** Added USP Verified (159 records via Playwright-backed `quality-supplements.org` parser), Informed Choice (805 records), Informed Sport (1764 records), and IFOS (745 Nutrasource records via `GetFilteredProducts` + product detail pages) on top of NSF Sport (1253) and NSF/ANSI 173 (2850). Registry total: 7576 records across 6 programs, each with fresh per-source snapshot dates. `--merge-existing` preserves existing sources during single-source refreshes. | Codex |
| 2026-05-19 (resolver variant guards) | **Cert resolver variant safety tightened.** Dose/form guard prevents 100 mg ↔ 200 mg and gummies ↔ softgels false SKU matches; stim/non-stim guard prevents `10X Stim` ↔ `10X Pump Non-Stim`; flavor guard is asymmetric: a flavor-specific registry row must match the product flavor or go `needs_review`, while a base registry row can still verify a flavored label when the registry lists product lines. Canary catch: Sports Research Omega DSLD name matched IFOS `Omega-3 Fish Oil Lemon Flavor`; now `needs_review` and scores 0 until reviewed. Transparent Labs `Creatine HMB Strawberry Lemonade` still verifies against base Informed Choice `Creatine HMB`. | Codex |
| 2026-05-19 (canary after IFOS) | **10-product targeted canary rerun completed, no full catalog rerun.** `Sports Research Omega-3 1055 mg Fish Oil 1250 mg` IFOS changed from provisional label B4a 2 → `needs_review` B4a 0 because the only matched IFOS registry row is flavor-specific (`Lemon Flavor`) and DSLD label name omits flavor. Informed Sport/Choice canaries stayed stable: Sports Research Whey and Transparent Labs Creatine HMB remain B4a 8. Score-delta report: `/tmp/pg_ifos_canary/informed_to_ifos_delta_final_*.md`. | Codex |
| 2026-05-19 (P0.2 SHIPPED — class-aware B5 opacity + canary set + label-vs-registry audit) | **B5 opacity penalty multiplier becomes class-aware in scorer.** `_b5_class_for_product` routes products to one of four classes (probiotic / multi_or_prenatal / sports_active / generic) with multipliers `{0.4, 1.3, 1.5, 1.0}` applied to the v3 per-blend penalty raw value; cap stays 10. Priority order: probiotic supp_type → sports keyword in name → multivitamin supp_type → prenatal name → primary_category=multivitamin fallback → primary_category in {omega-3, protein, collagen, enzyme} generic override → generic default. Sports regex extended to catch whey/casein/protein-powder/concentrate/hydrolysate. `class_multipliers` block added to scoring_config; config-drift test locks it. 30 contract tests in `test_b5_p02_class_aware_opacity.py`. Curated 35-product canary set at `scripts/data/canary_products.json` covering 14 primary classes + all 4 B5 routes + edge cases. 15 coverage tests in `test_v4_canary_coverage.py` including live router-match against shipped catalog. Diagnostic `scripts/api_audit/cert_label_registry_audit.py` predicts pipeline-rerun B4a outcomes: pre-RC audit showed 75.3% of USP-label products would zero out (Doctor's Best CoQ10 anchor case = USP-grade ingredient claim ≠ USP Verified Mark Program enrollment). | Claude (build), Codex (router generic-override extension + canary expected_b5_class corrections) |
| 2026-05-19 (RC SHIPPED — non-production full pipeline rerun + audit + delta) | **First full-catalog rerun since P0.1b: `PYTHON=python3.13 bash batch_run_all_datasets.sh --skip-release` rebuilt `scripts/dist/` + `scripts/final_db_output/` from the 21 staging brands.** Pre-RC snapshot at `scripts/final_db_output.preRC_20260519T013812Z/`. **Pipeline: 21/21 brands passed, 8,440 products shipped.** **Audit gates GREEN:** db_integrity_sanity_check 0 findings, audit_inactive_safety 0 banned-signal violations / 0 false-positives, audit_contract_sync required-fields GREEN (optional yellow on form/is_harmful/severity_level/additive_type — backlog cleanup, not blocker), audit_raw_to_final 10/10 canary clean, coverage_gate 1715/1715 / 0 blocked, coverage_gate_functional_roles 572/572. **8 contract failures correctly EXCLUDED** from shipped catalog (5 NOT_SCORED + 3 missing canonical_id → review-queue, not shipped). **Cert audit P0.1b structural cleanup verified at scale:** USP "claims" dropped 1,451 → 749 (−702 phony manufacturer-injection removed), NSF Sport 450 → 55 (−395 removed; % real verify jumped 13% → 74.5%), NSF Certified 628 → 475 (−153 removed). ~1,250 phony cert claims eliminated. **Catalog-wide score delta (8,376 products in both builds):** mean Δ −1.01, median 0, stdev 2.24, range [−10.0, +7.6]. **0 BLOCKED → anything**, **0 anything → BLOCKED** (safety integrity preserved). 32 SAFE → POOR + 29 POOR → SAFE — comparable transitions only, roughly symmetric, all near the 40-pt threshold, all explained by P0.1b mfg-injection cleanup / P0.1d label_asserted adjustment / P0.2 B5 class multiplier. 64 added / 64 removed = UPC-dedupe ID churn, NOT real transitions (score_delta_report fix landed per Codex's RC review: comparable-only verdict counter `verdict_changed_comparable` + verdict_transitions breakdown + scores now pulled from `pharmaguide_core.db` since detail_blobs lack top-level `score_100_equivalent`). **All 35 canaries verified:** 23 stable (Δ ≤ ±1, anchor SKU verifications holding: Thorne Mg 72.6→72.6, SR Whey 70.3→70.3, TL Creatine HMB 85.2→85.2); 5 down −5 to −7 (cert-overcredit cleanup: Doctor's Best CoQ10 USP-label-but-not-in-registry 65.2→60.2, Thorne Vit K2 51.5→45.2, Thorne Meriva-SR 67.3→61.1, GoL Greens 69.6→64.6, Legion Whey+ 68.1→61.9); 1 favorable verdict change (Spring Valley Probiotic 50B: 39.3 POOR → 44.6 SAFE via P0.2 probiotic 0.4x multiplier); 3 BLOCKED stayed BLOCKED. Pending_review entries (DSLD 274081 GoL prenatal probiotic, 236845 GoL Sport Energy+Focus) correctly scored 0 — fail-closed contract holding. **Verdict: RC production-ready.** Reports under `reports/RC_*` and `scripts/api_audit/reports/cert_label_registry_audit_*`. RC review checklist preserved at `docs/plans/RC_review_checklist_20260519.md`. Next: Supabase dry-run (`python3 scripts/sync_to_supabase.py scripts/dist --dry-run`); if clean, `bash scripts/release_full.sh`. **Open follow-up:** v4 shadow scorer / softer verdict display to remove the 40-pt SAFE/POOR cliff (UX-unstable on near-threshold products — Codex's RC review note). | Claude (review + audit + canary walkthrough + score_delta_report fix), Codex (RC artifact verification + delta-report design feedback), Sean (RC kickoff + go/no-go authority) |
| 2026-05-19 (PRODUCTION RELEASE) | **`bash scripts/release_full.sh` shipped catalog v2026.05.19.031440 (schema 1.6.0) + interaction DB v1.0.0 to Supabase + Flutter bundle.** 8440 products + 138 interactions, SHA-256 verified, integrity_check ok, embedded-vs-JSON manifest cross-check ok. Supabase cleanup: 4 storage objects deleted, 2 manifest rows deleted (stale products correctly purged). Flutter assets bundled to `PharmaGuide ai/assets/db/`, `.previous` backups pruned. Total wall-clock 7,623s (~2h 7min) including DSLD product image extract (7665 cached / 775 fresh / 0 failed). Post-release smoke on 7 canary products in shipped catalog: all expected values (Thorne Mg 72.6 SAFE, Doctor's Best CoQ10 60.2 SAFE −5.0, SR Whey 70.3 SAFE, GoL prenatal probiotic 51.1 SAFE +5.5, TL KSM-66 61.5 SAFE, GNC Fish Oil 38.0 POOR boundary, Spring Valley Probiotic 50B 44.6 SAFE POOR→SAFE). **Live in production.** | Sean (release authority), Claude (post-release smoke), Codex (RC verification + git hygiene) |
| 2026-05-19 (P0.4 CLOSED — NOT_SCORED gate verified) | **Codex read-only audit: P0.4 satisfied with no further work.** Current shipped `products_core` contains 0 NOT_SCORED rows, 0 null-score non-blocked rows, 8 contract failures correctly EXCLUDED from SQLite + detail_blobs. Code paths: `build_final_db.py` lines 671 (NOT_SCORED quarantine doc), 724 (verdict==NOT_SCORED rejection), 5502 (defensive sweep). 39 tests pass across final-DB integrity / NOT_SCORED / verdict vocab / UPC dedupe. | Codex (audit), Claude (acknowledge closure) |
| 2026-05-19 (P0.5 SHIPPED — probiotic/prebiotic split-brain fix) | **Codex's RC audit surfaced: 74 products had scorer prebiotic credit > 0 but `probiotic_detail.prebiotic_present = false` on the shipped blob.** Anchor: DSLD 274081 GoL Once Daily Prenatal — active "organic Acacia Fiber" → scorer credits via "acacia" substring → `probiotic_breakdown.prebiotic = 1.0`, but enricher's strict exact-match against `clinically_relevant_strains.json` missed it → display said no prebiotic. **Fix:** `_collect_probiotic_data` in `enrich_supplements_v3.py` now runs a second-pass substring fallback against `scoring_config.section_A_ingredient_quality.probiotic_bonus.prebiotic_terms` (same list the scorer reads) after the existing exact-match pass. New `_get_prebiotic_terms()` lazy-loads from config with a byte-equal hardcoded fallback for resilience. End-to-end verified on real DSLD 274081 cleaned input: `prebiotic_present=True, prebiotic_name='Prebiotics'`. 15 contract tests in `test_p05_probiotic_prebiotic_consistency.py` (Acacia Fiber anchor, parametrized over 9 prebiotic term families incl. FOS/GOS/Pea Fiber/Raftiline that exact-match missed, nested-blend coverage, negative cases on Apple Fiber, single-source-of-truth lock that config and code stay aligned). 650+ targeted tests green across probiotic / enrichment / scorer / cert / canary suites. Live effect lands on next pipeline rerun. | Codex (split-brain finding), Claude (test-first patch) |
| 2026-05-19 (P1.5 SHADOW CALIBRATION — affine display transform) | **v4 generic shadow score now preserves raw assembly and emits a calibrated display score.** Raw dimension math remains unchanged: `raw_score_100` is the five v4 dimensions rescaled for non-evaluable dimensions plus manufacturer trust/violations. The top-level `shadow_score_v4_100` now uses the P1.5 affine calibration `clamp(25 + 0.75 * raw_score_100, 0, 100)` to correct canary compression without touching per-dimension evidence/trust/formulation math. Breakdown metadata records `calibration.method=affine_p15`, intercept, slope, raw score, calibrated score, and reason (`p1_5_canary_score_compression`). Canary report now shows Raw v4 and Cal v4 side-by-side, plus raw and calibrated deltas. This is shadow-only; v3 production remains truth until P5 cutover. | Sean (calibration direction), Codex (implementation) |
| 2026-05-19 (P1.5 OMEGA DEBT logged — known rubric gaps) | **Manual omega review on the 2 fish-oil canaries (Sports Research Omega-3 DSLD 327776, Nordic Naturals Ultimate Omega DSLD 288740) surfaced four structural gaps where v4 generic-module routing under-credits IFOS-verified omega-3 products vs v3.** (1) **IFOS scope handling under-credits real evidence:** Sports Research has registry-verified IFOS (`record_id=IFOS_CB72E5AB70B7`, `recency_status=fresh`, source `nutrasource.ca`) but `scope=needs_review` → B4a credits 0 pts; Nordic Naturals has IFOS at `scope=brand_only` → 0 pts. v3 Section B credited both (Section B 28-28.5/30 for both, vs v4 Trust 0–4/15). (2) **EPA/DHA dose adequacy not modeled:** both products have EPA/DHA ingredients with `pct_rda=None, pct_ul=None` in `rda_ul_data.adequacy_results` — Sports Research lands Dose=None (excluded from denominator), Nordic only lands Dose=22 via its CoQ10 co-active. v3 had `omega3_dose_bonus` (cap +2) in Section E that flows through; v4 has no equivalent. (3) **Form-specific bio_score doesn't differentiate TG/rTG/EE:** Sports Research's "Triglycerides" form bio_score=11 vs Nordic's bio_score=10 — under-rewards TG bioavailability per §9 line 504. (4) **Marine sustainability certs (Friend of the Sea, MSC) score zero** with no dimension home. **Net deltas calibrated:** Sports Research v3 63.7 → v4 cal 52.6 (−11.1), Nordic 68.6 → 64.2 (−4.4). Both still SAFE post-calibration; rank order preserved; automated `generic_ok_for_now` checkpoint passes. **Decision: omega debt is NOT a blocker for P2 (probiotic affects 14× more catalog products — 696 vs ~50), but a dedicated P1.6 `omega` module is queued per §9 for after P2 lands.** P1.6 scope: IFOS scope-aware credit (brand_only at partial, needs_review at intermediate), EPA/DHA dose adequacy bands per AHA guidance (250-1000 mg/day optimal, 1000-3000 high, 3000+ prescription), TG/rTG/EE form differentiation, oxidation/TOTOX signals, marine sustainability +0.5; all weights config-driven via `omega_rubric.json` per the §13 line 874 long-term plan. **Related cross-module Trust scope policy (P1.7):** `brand_only` and `needs_review` cert scopes currently zero across all modules. **Re-scoped per Codex's 2026-05-20 catalog audit:** P1.7 is NOT a calibration tweak (no fractional credit for either scope) but a curated-overrides triage. Audit numbers across 8,440 shipped products: `brand_only` 1,317 entries / 1,300 products, `needs_review` 458 / 456, `sku` 467 / 459, `product_line` 27 / 23, `claimed_only` 977 / 960. `brand_only` stays 0 in B4a indefinitely — brand-level certs ≠ product-level testing; crediting them would silently reintroduce the manufacturer-inflation bug cleaned up at P0.1b (brand-level evidence routes to `manufacturer_cert_signals` for display and Manufacturer Trust D1, not Trust dim). `needs_review` is a mixed bag: real false positives (Nature Made Vit E 200 IU matching the USP Vit E 1000 IU registry row; Nordic Naturals IFOS matching "Naturalis Inc"; Thorne K2 matching Multi-Vitamin Elite) and real product-line variants (GNC AMP Wheybolic flavors → genuine Informed Choice; Sports Research Omega-3 flavor variants → genuine IFOS; GoL Sport flavor variants). **P1.7 triage workflow:** (1) cluster `needs_review` entries by (program, record_id, matched_product) — likely 30-50 distinct registry rows claimed by ~458 products; (2) batch-reject obvious dose/form mismatches and brand-name collisions; (3) batch-verify obvious product-line variants; (4) write per-claim overrides to `scripts/data/curated_overrides/cert_verification_overrides.json` with `scope: product_line` or `scope: rejected`; (5) re-run resolver and recompute Trust distribution. Mitigation note: 4,932 of 6,599 Trust=0 products still have nonzero Manufacturer Trust, so the practical ceiling is less harsh than the raw Trust dim suggests. | Claude (manual omega review), Sean (deferral decision), Codex (catalog audit + triage framing) |
| 2026-05-19 (P2.1 SHIPPED — probiotic Formulation dimension) | **Probiotic module now populates Formulation 25 while Dose/Evidence/Trust/Transparency remain skeletons.** Components: total CFU disclosed +4, CFU amount tier +4 (50B=4, 10B=3, >1B=2, >0=1), named species diversity +4 (10+=4, 6+=3, 3+=2, >0=1), exact clinical strain codes +4 (5+=4, 3+=3, 1+=2), delivery/survivability +4, prebiotic complement +5. Clinical-strain cap intentionally uses the v4 4-point budget rather than v3 extended-mode 3-point cap because the probiotic Formulation dimension is explicitly balanced to 25. Real canary smoke: Spring Valley Probiotic 50B = 25/25, GoL prenatal probiotic = 17/25 on current artifact (pre-P0.5 rerun, prebiotic not yet re-emitted), GNC Ultra Probiotic remains completeness-blocked before module scoring. | Sean (clinical-strain cap guidance), Codex (implementation) |
| 2026-05-19 (P2.2 SHIPPED — probiotic Dose dimension) | **Probiotic module now populates Dose 25 while Evidence/Trust/Transparency remain skeletons.** Components: per-strain CFU disclosure 15 (proportional to named strains with individual CFU values) + CFU adequacy 10 (v3 `probiotic_cfu_adequacy` tier × support-level math, v3 cap 5 scaled 2× to v4 cap 10). Hard gates preserved: no adequacy tier = 0, no `cfu_per_day` = 0, postbiotic/inactivated strains = 0, unknown support defaults to weak 0.5×. Aggregate blend CFU **does not** count as per-strain CFU and never gets inferred across blend members. Direct canary smoke on shipped detail blobs: Spring Valley 50B, GNC Ultra Probiotic, and GoL prenatal probiotic all score Dose 0/25 because the labels disclose aggregate CFU but not per-strain CFU; this is intentional and will surface as a transparency/confidence caveat in P2.5 rather than fabricated dose adequacy. Module now reads both enriched `probiotic_data` and final-blob `probiotic_detail` for canary/debug parity. | Codex |
| 2026-05-19 (P2.3 SHIPPED — probiotic Evidence dimension) | **Probiotic module now populates Evidence 20 while Trust/Transparency remain skeletons.** Components: strain-clinical evidence 12 (reuses the verified v4 multiplicative evidence pipeline, capped to the probiotic 12-point sub-budget) + indication relevance 8 (conservative category overlap between product positioning text and `clinical_strains[].indication_primary`). Relevance levels: direct overlap = +8, related/partial overlap = +4, generic probiotic with gut/immune strain evidence = +4, none/not-evaluable = 0, then multiplied by the best available evidence-direction multiplier (positive_strong 1.0, positive_weak 0.85, mixed 0.6, null 0.25, negative 0.0) so negative evidence never earns relevance credit. Direct canary smoke on shipped detail blobs: Spring Valley 50B Evidence 10.964/20 (6.964 pipeline + 4 broad), GNC Ultra 50B Evidence 11.7/20 (7.7 pipeline + 4 broad), GoL prenatal probiotic Evidence 13.46/20 (9.46 pipeline + 4 partial infant/immune relevance). This is intentionally data-bound: if product positioning or strain indication text is absent, the relevance line scores 0 with metadata reason rather than inferred marketing intent. | Codex |
| 2026-05-20 (P2.4 SHIPPED — probiotic Trust dimension) | **Probiotic module now populates Trust 15 while Transparency remains skeleton.** Trust dimension is implemented as a verbatim reuse of `generic_trust.score_trust()` because the B4a/B4b/B4c sub-rubrics + caps + scope-aware diminishing returns are identical across modules per §6 line 292-295. No probiotic-specific cert programs exist in the catalog today: NSF / USP / Informed Choice are class-agnostic, IFOS is omega-specific and the existing marine-cert gate (`_is_omega_like`) correctly filters it out for probiotic products. The cross-module `brand_only` / `needs_review` cert scope policy question affecting probiotic NSF certs is tracked separately as P1.7 (not patched here in probiotic). Real-canary smoke on current artifacts: Spring Valley 50B, GNC Ultra Probiotic, and GoL Prenatal Probiotic all score Trust 0/15 — Spring Valley and GNC because no cert programs are present at all; GoL because the only cert (NSF Certified) carries scope=needs_review which currently zeroes per B4a policy. Module-level phase rolls to "P2.4_probiotic_trust"; per-dimension phase markers stay locked to their owning slice. Cumulative probiotic canary subtotals through 4 of 5 dimensions: Spring Valley 35.96/85, GNC Ultra 29.70/85, GoL Prenatal 30.46/85. | Claude (P2.4 implementation), Codex (P2.0-2.3 implementation) |
| 2026-05-20 (P1.8 ENRICHER AUDIT — cert/GMP/batch_traceability collection findings) | **Audit of `verified_cert_programs` / `gmp_level` / `has_coa` / `has_batch_lookup` collection paths in `enrich_supplements_v3.py` requested by Sean before P2.5 lands.** Findings, with severity tagged: **(1) REAL signal-miss — `transparency_program` rules-db evidence never scores.** `_collect_traceability_data` uses a narrow legacy regex `\b(batch|lot)\s+(lookup|search|verify)\b` that misses "transparency program", "traceability program", "track your batch/product". The richer rules-db patterns in `cert_claim_rules.json` (TRACE_TRANSPARENCY, points_if_eligible=2, evidence_strength=medium) are collected into `certification_data.evidence_based.batch_traceability` but **never merged into** `certification_data.batch_traceability.has_batch_lookup`, so they don't flow through to top-level `has_batch_lookup` either. Empirically rare (10/13,746 products have rules-db batch evidence vs 233/13,746 with regex-detected `has_batch_lookup=True`) but real undercrediting for brands with formal transparency programs. **Fix queued as P1.8a** — merge only entries with `points_if_eligible > 0` AND `evidence_strength != "weak"` to avoid reintroducing the FDA-lab false positive. **(2) MINOR contract inconsistency — nested vs top-level `has_batch_lookup`.** Top-level `enriched["has_batch_lookup"]` correctly OR-rolls `has_qr_code` (line 10268-10270), but `certification_data.batch_traceability.has_batch_lookup` stays narrow. Zero scoring impact (scorer reads top-level) but audit tooling reading the nested form gets inconsistent data. **Fix queued as P1.8b** — 1-line consistency fix. **(3) NOT A BUG — GMP "undercrediting" is intentional false-positive avoidance.** 24 products had rules-db catch "FDA-registered" with `gmp_level=None`. Inspection shows the matched text is "FDA-registered **laboratory**" (a third-party tester) not "FDA-registered **facility**" (the manufacturer's plant). Legacy regex `\bFDA[\s-]?(registered\|inspected)[\s-]+facility\b` correctly requires "facility" to distinguish these. The rules-db `fda_registered` pattern is broader and explicitly tagged `points_if_eligible=0` because the rules-db itself agrees it shouldn't score without facility context. **(4) NOT A BUG — `batch_tested` correctly doesn't score.** Rules-db catches "lot tested" / "batch tested" but flags `points_if_eligible=0, evidence_strength=weak` — claim without verification path. Current scoring correctly ignores. **(5) OPEN CALIBRATION QUESTION — QR-without-batch-context.** Legacy regex `\bQR\s*code\b` credits any product mentioning "QR code" with +1 B4c (via has_qr_code → has_batch_lookup rollup), 233 products affected. Rules-db requires batch/lot/trace context. Whether v4 should tighten matches a calibration call — defer to canary review. **Decision: P1.8a/b are scoped fixes for after P2.6 final assembly, not P2.5 blockers.** Affects shared `enrich_supplements_v3.py` collection layer; benefits all v4 modules (generic, probiotic, multi/prenatal) equally. | Claude (audit), Sean (defer decision) |
