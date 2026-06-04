# Plan — `standardized_botanicals.json` A5b Bonus Cleanup

**Status:** DRAFT for review. No code/data changes until approved.
**Created:** 2026-06-04
**Decision (user):** Reuse the existing in-file discriminator (NOT a 5-file split). Full plan before any edit.

---

## 0. Ground truth (verified against running engine, not assumed)

**What the bonus actually is**
- The file feeds **one** scoring field: `A5b_standardized_botanical` inside Section A → A5 (Formulation Excellence).
- Magnitude: **max +1.0 point out of 80** (`score_supplements.py:1774–1827`). The loop `break`s on the first qualifying botanical → a product earns **+1 total**, no matter how many botanicals it has. A5 pool cap = 5.0.
- Verdict on ChatGPT's "unfair score inflation": **overstated.** Worst-case contamination = +1/80 (≈ +1.25/100) per product. This is a fairness / data-integrity cleanup, **not** a scoring emergency.

**How the bonus is currently earned** (`enrich_supplements_v3.py:7790–7856`, `score_supplements.py:1774`)
- enrich sets `meets_threshold` + `evidence_source` per matched entry:
  - `branded_form: true` → `evidence_source="branded_form"` → full credit (1.0)
  - label `percentage >= min_threshold` → `percentage_local/context` → full credit (1.0)
  - marker-word match only → `marker_word_only` → partial (0.5)
- **Label proof is already required** for the percentage path (ChatGPT's rec #4 is already implemented).

**The schema already has the discriminator ChatGPT wanted**
- Field `standardization_basis` (enum): `marker_percent` (13), `branded_extract` (26), `mushroom_fraction` (2), **None (136)**.
- `_metadata.bonus_eligibility_contract` already states: *"An entry may stay in standardized_botanicals.json only if it has at least one of the four standardization bases… If none applies, move the entry to botanical_ingredients.json (basic identity, no A5b bonus)."*
- ⇒ The file is **mid-migration**. 136 None-basis entries are the backlog. This is the OPPOSITE direction from "create 5 new files."

**THE KEY GAP:** the scorer/enricher do **not** read `standardization_basis` or `bonus_eligible` when granting the bonus. They key only on `min_threshold`/`branded_form`/marker-word. So the basis enum and `bonus_eligible` flag are **documentation, not enforced.** Any entry physically in the file that clears a threshold or is branded earns +1 — regardless of whether it's a botanical. **Making `standardization_basis` load-bearing is the real fix.**

---

## 1. Verified findings

### F1 — Unit bug in `min_threshold` (only finding with real scoring-accuracy impact)
`enrich:7825` treats `min_threshold` as a **percent uniformly**, but values mix types:
| entry | min_threshold | standardization_unit | effect today |
|---|---|---|---|
| `ginkgo_biloba` | 24 | (none) | ✓ correct (24%) |
| `acai`/`blueberry` | 1 | (none) | over-loose (1% — trivially met) |
| `broccoli` | 0.4 | (none) | over-loose |
| `bromelain` | 2400 | `GDU/g` | ✗ compared as "≥2400%" → **can never meet → silently under-credited** |
| `cranrx` | 36 | `mg_per_dose` | ✗ compared as "≥36%" → never met |
- Only **2/177** entries carry `standardization_unit`; the enricher ignores it entirely.
- Direction of error: under-credit (mg/activity thresholds) **and** over-credit (sub-1% markers).

### F2 — Category contamination (matters for v4 **routing**, not the A5b bonus)
The A5b bonus never reads `category`, but the **v4 router / profile_eligibility is category-sensitive** (`scoring_input_contract.py:310, 2016–2071`). Errors:
- `dandelion: category="mushroom"` — outright wrong.
- 15 non-botanical-category entries living in the file (see F3).

### F3 — Non-botanicals in a botanical-standardization file (15 entries)
| entry | category | branded_form | bonus_eligible | suggested standardization_basis |
|---|---|---|---|---|
| chromax | mineral_chelate | ✓ | ✓ | `branded_extract` (mineral) — or move to IQM mineral form |
| sunactive_iron | mineral | ✓ | ✓ | branded mineral form |
| thermosil | mineral | ✓ | ✓ | branded mineral form |
| fruitex_b_calcium_fructoborate | mineral_complex | ✓ | ✓ | branded mineral form |
| life_s_dha | algal_oil | ✓ | ✓ | branded omega form |
| microactive_melatonin | hormone_analog | ✓ | ✓ | branded delivery form |
| uniflex | structural_protein | ✓ | ✓ | branded form |
| keraglo | structural_protein | ✓ | — | branded form |
| epicor | fermentate | ✓ | — | branded fermentate |
| bromelain | active_compound (enzyme) | — | — | enzyme_activity (GDU) |
| wellmune | polysaccharide (β-glucan) | — | — | branded form |
| setria | tripeptide (glutathione) | — | — | branded form |
| levagen | fatty_acid_amide (PEA) | — | — | branded form |
| cognizin_citicoline | nootropic | — | — | branded form |
| alphawave_l_theanine | amino_acid | — | — | branded form |

Decision per entry in Phase 4 — **none require a new file**; each is either (a) tagged with an honest `standardization_basis` + correct `category` and kept, or (b) `bonus_eligible:false` / migrated to `botanical_ingredients.json` per the existing metadata contract.

### F4 — Missing classic botanical thresholds (ChatGPT's list — to verify, not blindly add)
Candidates to add/tighten **after** content-verifying each marker % against NIH ODS / USP / pharmacopeia (no fabricated thresholds): ginkgo 24% flavone glycosides + 6% terpene lactones, saw palmetto 85–95% fatty acids, milk thistle 70–80% silymarin, bacopa 20–55% bacosides, rhodiola 3% rosavins/1% salidroside, grape seed 90–95% OPC, pine bark 65–75% procyanidins, horse chestnut 20% aescin, valerian 0.8% valerenic acids, etc. **Each gets a verified source before it earns a threshold.**

---

## 2. Design (lean — reuse existing fields)

- **Discriminator:** extend the existing `standardization_basis` enum (do NOT add `bonus_class`). Add at most: `branded_form` (already have `branded_extract`; reconcile naming), `enzyme_activity`. Keep `marker_percent`, `mushroom_fraction`.
- **Units:** populate the existing `standardization_unit` field (already present on 2 entries) for every threshold; add `threshold_marker` only where it disambiguates. No new parallel fields.
- **Make basis load-bearing:** the bonus must require a valid `standardization_basis` (or `bonus_eligible:true`). This is the change that makes contamination harmless permanently.
- **Honor the existing migration contract:** None-basis entries either get a verified basis or move to `botanical_ingredients.json` (identity only, no bonus).

---

## 3. Phased execution (each phase: TDD red→green, corpus delta, atomic commit)

### Phase 0 — Corpus impact baseline (read-only, do FIRST)
- Snapshot `A5b_standardized_botanical` for every product in a fresh full scored run → `reports/a5b_bonus_baseline.csv` (dsld_id, a5b_points, matched_entry, evidence_source).
- Gives the exact "how many products move" denominator before any edit. Expected: a5b is 0 or 1 per product; total affected = products whose matched entry changes basis/eligibility.

### Phase 1 — Unit bug fix (the only real accuracy fix)
- **Red:** test that `bromelain` (2400 GDU/g) and a mg_per_dose entry do NOT get a spurious/missing percentage comparison; that a 24% ginkgo still passes.
- **Fix:** `enrich:7826` — only apply the `percentage >= min_threshold` test when `standardization_unit` is percent/empty; for `GDU/g`, `mg_per_dose`, etc. fall back to branded_form/marker evidence (or a unit-appropriate compare if the label quantity exists).
- **Gate:** corpus delta vs Phase 0 baseline; confirm only intended a5b changes; rebuild + verdict-flip check.

### Phase 2 — Category audit (routing correctness)
- Fix `dandelion` (mushroom→herb/root) and re-tag the 15 non-botanical categories to truthful values.
- **Gate:** v4 route audit (`audit_v4_route_consistency.py`) + profile audit must not regress; these categories feed v4 routing.

### Phase 3 — Make `standardization_basis` load-bearing (the strictness lever)
- **Red:** test that an entry physically present but with `standardization_basis: null` / `bonus_eligible:false` earns **0** A5b even if a percentage clears `min_threshold`.
- **Fix:** enrich/score gate the bonus on a valid basis. Now contamination can't leak a bonus regardless of file membership.
- **Gate:** corpus delta — this is where the most products may move (the 136 None-basis entries lose any latent bonus). Verify each delta is intended.

### Phase 4 — Per-entry contamination decisions (the 15)
- One at a time, verified: assign honest `category` + `standardization_basis`, OR set `bonus_eligible:false`, OR migrate to `botanical_ingredients.json` per the metadata contract.
- Policy: chromium picolinate / isolated curcumin / etc. should NOT earn a *botanical-standardization* point; if they deserve a branded-form bonus it's via v4's `premium_form_diversity` (IQM forms), not this file.

### Phase 5 — Add/tighten classic thresholds (F4)
- Per-entry, each new threshold content-verified against an authoritative source (NIH ODS/USP). Same discipline as the IQM batches. Optional / lowest priority.

---

## 4. Test strategy
- Extend `test_standardized_botanicals_v6_contract.py`: every `bonus_eligible:true` entry MUST have a valid `standardization_basis`; every numeric `min_threshold` MUST have a `standardization_unit`; no non-botanical `category` may be `bonus_eligible:true` unless basis ∈ {branded_form, enzyme_activity}.
- New `test_a5b_bonus_unit_discipline.py`: bromelain/cranrx do not mis-compare; ginkgo 24% still earns; null-basis earns 0 (Phase 3).
- Regression: `audit_v4_route_consistency.py`, profile audit, full v4 suite, db integrity — all green before each commit.

## 5. Branded / patented bonus — answer + recommendation
- **You already have it:** (1) v3 `branded_form:true` → +1 A5b (27 entries); (2) v4 `premium_form_diversity` + `key_form_support` in the formulation dimension (IQM-form-driven).
- **Recommendation:** do NOT build a separate patented-ingredient registry — v4 already rewards premium forms, so a parallel bonus risks double-counting. If you want patent provenance, add an optional `patent_id` field to existing entries for display/traceability only (no extra points).

## 6. Risk / rollback
- Blast radius is bounded: A5b ≤ 1 point/product. Largest mover is Phase 3 (null-basis entries lose latent bonus).
- Every phase is an atomic commit with a corpus delta artifact → trivially revertable.
- Branch off `main` first; the parallel Codex session is active in scoring files — coordinate Phase 1/3 (enrich/score edits) to avoid collision.
