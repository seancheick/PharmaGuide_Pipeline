# V4 Phase 7 — Collagen Profile (design)

**Status:** shipped (feat(v4-collagen))
**Date:** 2026-06-01
**Plan:** `.planning/v4-finalization/PLAN.md` Step 7 (re-scoped)

## Re-scope (grounding corrected the plan)

The plan's premise — "collagen evidence averages 1.1/20, fix it" — was stale. By
Phase 6 the generic evidence pipeline already gives collagen ~6.3/20, and there
are 0 collagen entries in `backed_clinical_studies.json` to map. The real gap is
**dose**: collagen products borrow their co-formulated vitamins' RDA/UL dose
(e.g. "Collagen 2500 mg" scored dose 22 off its Vitamin A), so dose was
collagen-blind. Phase 7 scores collagen on its own clinical dose range +
formulation, mass-dominance routed (a multivitamin with token collagen stays
generic).

## Collagen is not one ingredient

Each type has a DISTINCT clinical effective dose. Using one range mis-scores the
low-mg subtypes. Verified clinical ranges (all PMIDs content-verified via PubMed
efetch — see `scripts/audits/collagen_phase7/research.md`):

| Subtype | Range | Unit | Key verified PMIDs |
|---------|-------|------|--------------------|
| Hydrolyzed peptides I & III (incl. marine) | 2.5-10 | g | 24401291 (Verisol 2.5 g skin), 28177710 (Fortigel 5 g joint), 29337906 (Fortibone 5 g bone), 18416885 (10 g joint), 39075819 (marine) |
| Undenatured Type II (UC-II) | 40 | mg | 26822714 (Lugo, knee OA) |
| Hydrolyzed Type II (BioCell / chicken sternum) | 500-2000 | mg | 31221944 (skin), 22486722 (OA) |
| Gelatin (denatured) | 5-15 | g | 27852613 (synthesis marker; lower bioavailability) |
| Natural Eggshell Membrane (NEM) | 500 | mg | 19340512 (knee OA) |

The previous single "Collagen Peptides 10-20 g" entry was WRONG (too high) — it
crushed 2.5 g skin collagen (the validated Verisol dose) as underdosed. Corrected
to 2.5-10 g.

## Design

### Routing — `is_collagen_product(product)`
A recognizable collagen active (canonical_id `collagen` or a collagen/gelatin
token) that is **mass-dominant** over the product's actives (Phase-6 gate, so a
collagen-beauty multivitamin with vitamins dominant stays generic/multi).

### Subtype classifier — `_collagen_dosing_entry(row, product)`
Precedence, most specific first: UC-II (undenatured/native/NT2) → NEM (eggshell
membrane) → hydrolyzed Type II (BioCell / chicken sternum/sternal / a PURE Type-II
that is NOT a multi-type I/III peptide blend) → gelatin (gelatin and not
hydrolyzed) → hydrolyzed peptides (default, incl. marine). The product NAME is
folded into the signal because the collagen TYPE is often disclosed there
("Type II Collagen Complex") rather than on the ingredient row.

### Dose adapter — `score_collagen_dose` (never None)
Matches the subtype entry, parses its range (`_parse_dose_range` handles single
points like UC-II "40"), converts to mg (`_range_mg`, unit-aware g/mg). Bands:
within 21 / near 16 / below 10 / above 12 / disclosed-no-ref 10 / blend or anchor
total 7 / primary-no-dose 0. B7 dose-safety penalty still applies.

### Formulation adapter — `score_collagen_formulation` (max 15)
recognized identity +6, hydrolyzed peptides (not gelatin) +2, type disclosed +3,
source disclosed +2, quantified dose +2, branded clinically-studied +3 (Verisol/
BioCell/Peptan/UC-II/NEM…). Occupies the A1 slot; A2 + A5b disabled for collagen.

## Validation
- `scripts/tests/test_v4_collagen_profile.py` (23 tests): routing incl. mass-
  dominance + multivitamin guard; per-subtype dose (UC-II 40 mg, BioCell 1 g,
  NEM 500 mg, gelatin, peptide 2.5 g within / 0.5 g below, pure Type-II routing,
  multi-type peptide guard); formulation caps + gelatin-vs-peptide.
- Catalog: UC-II 40 mg POOR→SAFE, 2.5 g Verisol skin POOR→SAFE, chicken-sternum
  Type II POOR→within; genuinely underdosed (100 mg) stays POOR.

## Deferred / boundaries
- Collagen in a multivitamin that routes to `multi_or_prenatal` is not collagen-
  scored (same module boundary as botanical).
- BodyBalance (body-composition collagen, ~15 g) not specially handled.
- Gelatin's exact 5 vs 15 g split is a surrogate-marker endpoint (tier 3).
