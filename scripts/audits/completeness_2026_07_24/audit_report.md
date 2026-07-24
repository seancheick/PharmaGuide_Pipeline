# Drug-class membership completeness audit — 2026-07-24

Codex flagged ~12 classes as differing from current RxClass/ATC. Verified per-class
against **clinical intent** (not a blind ATC diff): most classes are already
ATC-comprehensive. The real risk is a few *current, commonly-prescribed* members
missing from otherwise-complete classes.

Method: opus sweep for candidate omissions → **every candidate's rxcui resolved +
entity-confirmed live on RxNorm** → added only where the class's rule applies
**uniformly** to the new member (so it closes a missed-warning without creating a
wrong one).

## Applied (6 drugs / 7 insertions) — all live-verified Active + correct entity

| drug | rxcui | class(es) | rule uniformity |
|---|---|---|---|
| dexlansoprazole | 816346 | proton_pump_inhibitors, acid_suppressants | acid-suppression depletion, all PPIs |
| delafloxacin | 1927663 | fluoroquinolones | cation chelation, all FQs |
| gemifloxacin | 138099 | fluoroquinolones | cation chelation, all FQs |
| dipyridamole | 3521 | antiplatelet_agents | additive bleeding, all antiplatelets |
| insulin isophane (NPH) | 1605101 | insulins | Mg cellular uptake, all insulins |
| lopinavir | 195088 | hiv_protease_inhibitors | co-formulated w/ritonavir → both PI rules apply |

## Deferred to their section — adding now would fire WRONG warnings

- **valproate (11118), gabapentin (25480), pregabalin (187832) → anticonvulsants** —
  **Section 3.** `class:anticonvulsants` drives drug-SPECIFIC depletions: folate/B12/
  biotin/L-carnitine name valproate, but CALCIUM ("secondary to vitamin D") and
  VITAMIN K ("enzyme-inducing AEDs") are enzyme-inducer-specific yet still on the
  broad class. Adding any non-inducer AED fires wrong Ca/vitK warnings until those
  two rules are repointed to `class:enzyme_inducing_antiseizure_medications` (the
  same fix Sprint 3 applied to vitamin D). **This is the key Section 3 finding.**
- **norgestimate (31994), norgestrel (7518), dienogest (22968) → oral_contraceptives** —
  **Section 4.** All 7 OCP rules are *estrogen*-mechanism on a progestin-only class;
  norgestrel is now an OTC progestin-only pill (Opill) → matching it could fire
  estrogen-depletion warnings for progestin-only users. Needs the estrogen-component
  structural decision.

## Excluded (verified, deliberate)

- **pamidronate (11473)** — IV-only; the bisphosphonate rule is oral-bioavailability
  chelation ("in the GI tract"), so an IV drug would get a wrong oral-timing warning.
- International/obscure/discontinued (delapril, temocapril, roxatidine, norfloxacin
  [US-discontinued], most Asian DPP-4/SGLT2, etc.) — below the current-US/major bar,
  consistent with the class's existing inclusion policy.

## Class-intent decisions surfaced for the user (NOT changed unilaterally)

- **maois** — add MAO-B inhibitors (selegiline/rasagiline/safinamide)? Real tyramine/
  serotonergic risk with St. John's Wort/5-HTP/SAMe, but broadens the class from
  antidepressant-MAOIs to all MAO inhibitors.
- **acid_suppressants** — add vonoprazan (P-CAB)? Same micronutrient-depletion risk,
  but it is not a PPI/H2 — a mechanism-broadening decision.
- **corticosteroids** — add systemic oral budesonide (ATC-classified outside H02AB)?
- **b_vitamins** — idiosyncratic class (contains vitamin E); folate/B12 absent —
  clarify intent before adding.
- **antibiotics_broadspectrum** direct-drug id (2 rules) — suppressed as
  `needs_revision`; real fix = `class:broad_spectrum_antibiotics` in **Section 8**.

## Also surfaced (not fixed here)

- `class:bisphosphonates` mixes oral + IV members (zoledronic acid, and now excluded
  pamidronate) under an oral-only chelation rule — a latent over-match to review.
