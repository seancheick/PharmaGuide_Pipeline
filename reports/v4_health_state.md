# V4 Scoring — Consolidated Health State (2026-06-07)

**Status: v4 is comprehensively healthy across every category, verified under current
`main` HEAD. v4 remains SHADOW-ONLY — v3 is still the production export. Not cutover.**

This report consolidates a full session of v4 finalization work (multi-agent: this
agent's P5/harshness lane + codex's omega/blend lane + the dev's IQM lane).

---

## What shipped today (all on `main`)

| Commit | Author lane | What |
|--------|-------------|------|
| `4b794561` | this agent | **P5** essential-nutrient evidence floor (DRI authority = 10) |
| `9891752b` | codex | P1–P3 omega molecular-form + prenatal B5/B7 harshness fixes |
| `9f25a3e6` | codex | folate mg-DFE dose normalization |
| `3a552d36` | codex | soften omega data-limited disclosure |
| `bdae6612` | codex | **recover blend anchor scoring signals** (branded/IQM-form recovery) |
| `f2ebc0c1` | codex | **soften omega low-dose cliff** (100/200mg EPA+DHA partial-credit bands) |
| `73fdf1ab` | codex | **formulation presence floor** for real cleaner-promoted actives |
| `9479a221` | codex | tighten presence floor to require a real cleaner active (Moducare edge) |
| `17a96e8f` | codex | **probiotic aggregate-CFU low-tier dose floor** + route-aware dose-zero audit |
| `b916d3e9`, `bb90da12`, `9f014520` | dev | IQM: carnitine routing, mushroom calibration, defensibility locks |

---

## Category health (re-scored under current HEAD)

| Category | Representative scores | Verdict |
|----------|----------------------|---------|
| Premium singles/sports | Thorne Creatine 93, KSM-66 87, Curcumin Phytosome 87.5, Astaxanthin 84 | ✅ branded evidence floor (18) working |
| Prenatal / multi | Thorne Basic Prenatal 87.9, Pure PreNatal 82.4, Thorne **Prenatal DHA 82** (was 76) | ✅ codex P1/P6 lifting toward 90s |
| Essential singles (P5) | Copper 40 (was 30), B12/iron/folate floored to ev 10 | ✅ 338/7016 floored, ZERO non-DRI leakage |
| Botanical / blend | Relora 54 (was 25), Dipan-9 48 (was 35), Pancreatic Enz 53 | ✅ codex `bdae6612` fixed formulation=0 |
| Omega | Pro-Resolve Omega 35.2, Spring Valley DHA 200mg 32.0; Vitafusion 50mg remains 40.5 with dose 0 | ✅ codex `f2ebc0c1` fixed low-dose cliff without inflating trace-dose products |
| Probiotic (403) | Thorne FloraSport 20B 86.5; Primadophilus low aggregate-CFU labels now receive dose 2.0; no-CFU labels stay 0 | ✅ strain+CFU rewarded, aggregate-CFU floor fixed, no-CFU zeros honest |
| Collagen (121, P7) | Hydraplenish 82.7, Marine Collagen 82.5; gelatin 33–40 POOR | ✅ evidence **1.1 → 11.4** avg; gelatin correctly low |
| Stimulant CAUTIONs | Pulse 59, LIT 49, Mega Men Energy 70 — all CAUTION | ✅ 156/156 justified (caffeine safety) |
| Safety gates | — | ✅ G1=0 downgrades, G2=0 banned→SAFE, G3=1 (pre-existing `25935`) |

---

## P5 — essential-nutrient evidence floor (this agent's lane)

DRI-essential vitamin/mineral that is the mass-dominant active floors evidence to 10
(below the 14 clinical / 18 branded-consensus tiers). Verified: copper 0→10 (score
30.1→40.1); 338/7016 generic floored, ALL DRI-essential, **zero leakage** to
botanicals/novel compounds; boron (UL-only) correctly excluded; safety-inert. Tests
green. See commit `4b794561`.

## Harshness triage — GREEN (this agent's lane)

All 156 residual v3-SAFE → v4-CAUTION flips are legitimate caffeine/stimulant safety
calls (disclosed 180–350mg, or stimulants hidden in proprietary blends). Zero
false-positives. v3 under-warned; v4 is correct. Full detail in
`reports/v4_caution_triage.md`. No scoring change.

## Blend fix — independently verified (codex's `bdae6612`)

Root cause confirmed: branded-blend / enzyme products had **0 scorable actives** (the
proprietary-blend *header* was never decomposed). `bdae6612` recovers branded/IQM-form
signals at the blend anchor. Verified: Relora 25.2→54.2, Dipan-9 35.1→48.1, zero safety
downgrades (G1=0), zero premium regressions. The "122 formulation=0 with mapped actives"
are NOT bugs — they are correct penalty-clamps (e.g. magnesium oxide bio 3 − harmful-
additive penalty 4 → clamp 0).

## Omega low-dose fix — independently verified (codex's `f2ebc0c1`)

Root cause confirmed: the remaining omega problem was mostly a hard zero-credit cliff
below the EFSA 250mg/day adequate-intake threshold, not a silent EPA/DHA extraction
failure. `f2ebc0c1` adds purpose-fit partial-credit bands in `omega_rubric.json`:
200-249mg/day EPA+DHA earns 4.0 dose points, 100-199mg/day earns 2.5, and <100mg/day
stays zero. Verified: Pro-Resolve Omega (EPA 225mg + raw DSLD DHA `200 mcg`) now gets
dose 4.0 / score 35.2; Spring Valley DHA 200mg gets dose 4.0; Vitafusion 50mg aggregate
stays dose 0. Local omega scan after the fix: 39 sub-250mg products lifted, dose-zero
reduced to 28, trace/no-disclosure products still uncredited. Targeted omega/config
tests: 108 passed, 1 skipped (missing local canary).

---

## Open items

1. **Omega residuals are now bounded.** The low-dose scorer cliff is fixed. Remaining
   dose-zero products are mostly either trace-dose (<100mg/day), no EPA/DHA disclosure,
   or enrichment/routing cases with no EPA/DHA in scorable actives. Example: Vitafusion
   Omega-3 EPA/DHA 267461 discloses only 50mg aggregate EPA/DHA, so dose 0 is still
   correct under the current rubric. These are not cutover blockers unless a fresh audit
   finds adult EPA/DHA products with >=100mg/day still scoring dose 0.

2. **Seditol-class data gaps.** Seditol stays POOR (38.7) because no verified clinical
   evidence exists for it — needs verified evidence DATA, not a scorer patch.

3. **70 generic `formulation=0` without cleaner scorable actives** — minor blend-
   decomposition / commodity data gaps (Moducare, MCT Oil, Coconut, Sytrinol).
   Correctly remain 0 after `9479a221`; product-level evidence can support dose/profile
   scoring but no longer qualifies for the formulation presence floor.

4. **P7 score-display semantics — user decision.** Bands (90+ Elite / 85–89 Excellent /
   80–84 Strong) vs pushing 90+ via real-signal fixes. At 87, Thorne Basic Prenatal /
   KSM-66 read correctly as "Excellent" under bands.

## Minor observations (no action needed)

- Probiotic module reports `confidence=low` pervasively even on top products
  (FloraSport 20B). Score-correct; a confidence-reporting conservatism, not a defect.

---

## Zero-section calibration — "no section should read 0 with a real signal" (2026-06-07)

Prompted by the question: *should any score dimension ever be literally 0 if a product
has actives?* Audited all 4 core dimensions across 10,060 scored products and resolved it
with data. **Refined principle:** a dimension should never read 0 when the product
discloses a real positive signal for it (form, dose) — but 0 is the honest, correct answer
when the signal genuinely does not exist (no clinical science) or is deliberately hidden
(opaque label).

| Dimension | 0s justified? | Outcome |
|-----------|---------------|---------|
| **Formulation** | No — 120/175 zeros were penalty-clamps of a real form signal | **Fixed:** codex `73fdf1ab` `FORMULATION_PRESENCE_FLOOR=2.0`. Verified: Mg-oxide 0→2.0, formulation-zero-with-mapped-actives 123→3, premium stable, G1=0, 103 tests pass. |
| **Dose** | Partly — omega cliff + probiotic CFU were real | **Fixed:** omega (`f2ebc0c1`) and probiotic aggregate-CFU (`17a96e8f`). Dose-zero audit now reports **110 valid_zero / 0 bug_candidate**. |
| **Evidence** | Yes — 1,605 (16%) are honest "no clinical science exists" | **Keep 0** — flooring = ghost citations. P5 already floored the defensible subset (DRI essentials). |
| **Transparency** | Yes — **254/254 are proprietary-blend opacity** (verified) | **Keep 0** — flooring would reward hiding the label. |

### Probiotic CFU dose=0 — fixed (`17a96e8f`)

Root cause confirmed in `scripts/scoring_v4/modules/probiotic_dose.py`: when a product
disclosed a *total* CFU but no per-strain CFU, the aggregate-CFU proxy computed
`proxy_cfu_per_strain = total / strain_count`; a low result (e.g. Primadophilus Reuteri
Pearls: 1B ÷ 4 strains = 250M/strain → `tier='low'`) mapped to 0 points → dose 0 even
though a real CFU was on the label. `17a96e8f` fixes this inside the aggregate-proxy path
without changing shared per-strain `TIER_POINTS`: low-tier numeric total CFU now gets a
small 2.0/25 dose floor, and products with total CFU but no clinical-strain mapping also
get the same conservative floor. No-CFU labels remain 0. Verification: dose-zero audit
`110 valid_zero / 0 bug_candidate`; targeted suite `87 passed, 1 skipped`; full delta
`shipped_safety_downgrades=0`, large deltas `0`.

### Moducare presence-floor edge — tightened (`9479a221`)

Claude correctly caught that the first presence-floor implementation treated product-level
evidence rows as "mapped active" rows. That gave Moducare-class products with no cleaner-
promoted `ingredients_scorable` rows a 2.0 formulation floor. `9479a221` tightened the
predicate: the floor now requires a real cleaner-promoted active row. Product-level
evidence can still support dose/profile scoring, but it does not prove a concrete active
form for formulation display hygiene. Verification: real Moducare `182620` formulation
returned to 0.0; real magnesium oxide `179534` still gets the intended 2.0 floor;
presence-floor applications dropped 139 → 120; full delta `shipped_safety_downgrades=0`.

---

## Cutover gate (unchanged)

v4 stays shadow-only until: P7 display decision is made, remaining non-score data gaps
are accepted or queued, and a final full-corpus delta + release-readiness pass with
shipped_safety_downgrades = 0. v3 remains the production export until explicit sign-off.
