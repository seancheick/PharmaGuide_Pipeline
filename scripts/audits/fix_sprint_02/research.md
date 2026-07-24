# Fix Sprint 02 — statins→CoQ10, corticosteroids→calcium, corticosteroids→vitamin D

Scope locked to exactly 3 records. Every citation PubMed content-verified (title
+ abstract read). Field-level results use `verified | needs_revision |
unsupported | not_applicable`; the entry-level `citation_review_status` is the
roll-up — `verified` only when every PUBLISHED field passes.

Reviewer: `lead_clinician_fix_sprint_02` · 2026-07-23

| Entry | Roll-up |
|-------|---------|
| DEP_STATINS_COQ10 | **verified** (severity→mild) |
| DEP_CORTICOSTEROIDS_CALCIUM | **verified** (scope narrowed) |
| DEP_CORTICOSTEROIDS_VITAMIND | **verified** — **retyped `depletion` → `monitoring_stability`** |

---

## 1. DEP_STATINS_COQ10 → verified

**Evidence.** Statins lowering *circulating* CoQ10 is established:
- **PMID 26192349** Banach 2015, Pharmacol Res — meta-analysis of 8
  placebo-controlled arms: WMD **−0.44 µmol/L** (95%CI −0.52,−0.37; p<0.001);
  consistent across atorvastatin/simvastatin/rosuvastatin/pravastatin and across
  lipophilic vs hydrophilic. Authors state the **clinical relevance is unclear**.
- **PMID 8463436** Ghirlanda 1993, J Clin Pharmacol — double-blind
  placebo-controlled; ~40% plasma CoQ10 reduction.

**Supplementation evidence genuinely CONFLICTS — both are cited, neither is
presented as settled:**
- **PMID 30371340** Qu 2018, JAHA — 12 RCTs / 575 patients: CoQ10 *improved*
  muscle symptoms (no CK change).
- **PMID 32179207** Kennedy 2020, Atherosclerosis — 7 RCTs / 321 patients: **no**
  benefit for myalgia (WMD −0.42, 95%CI −1.47 to 0.62) and no adherence benefit.

| Field | Result | Action |
|-------|--------|--------|
| relationship | verified | kept — statins lower circulating CoQ10 |
| scope | verified | `class:statins` supported across all 4 statins studied |
| mechanism | needs_revision | kept mevalonate/ubiquinone; **removed "cardiac CoQ10 is particularly affected"** (unsupported) |
| clinical impact | unsupported | **removed causal myopathy claim**; replaced with explicit uncertainty |
| monitoring | unsupported | **removed "check CoQ10 plasma levels"** — not standard care |
| recommendation | unsupported | **removed routine 100–200 mg**; now "uncertain… discuss persistent muscle symptoms" + do-not-self-stop guard |
| consumer copy | needs_revision | removed "a common and reasonable addition" endorsement and "a supplement is usually the practical route" |
| citations | needs_revision | NIH-ODS placeholder → the 4 PMIDs above |
| comparison amount | unsupported | **`adequacy_threshold_mg: 100` REMOVED** — encoded an efficacy assumption |
| relationship type | verified | `depletion` retained (circulating level genuinely falls) |

severity `significant`→**`mild`** (real relationship, unproven consequence);
evidence_level stays `established` **for the circulating-level relationship only**.

---

## 2. DEP_CORTICOSTEROIDS_CALCIUM → verified

**Evidence.**
- **PMID 14687590** Ferrari 2003, Best Pract Res Clin Endocrinol Metab — GCs
  "increase bone resorption, inhibit bone formation and have an indirect action
  on bone by **decreasing intestinal Ca2+ absorption**, but also inducing a
  **sustained renal Ca2+ excretion**." → the calcium-balance mechanism.
- **PMID 37845798** 2022 ACR GIOP Guideline (Arthritis Rheumatol 2023) — scoped
  to **>3 months of GC at ≥2.5 mg/day**; **strongly** recommends early fracture-risk
  assessment (clinical fracture assessment, BMD w/ vertebral fracture assessment,
  FRAX if ≥40); pharmacologic treatment by risk tier, shared decision-making.
- **PMID 28585373** 2017 ACR GIOP — most recommendations explicitly *conditional*.

| Field | Result | Action |
|-------|--------|--------|
| relationship | verified | real negative calcium balance (Ferrari 2003) |
| scope | needs_revision | **narrowed to prolonged SYSTEMIC use**; copy now excludes short courses, inhalers, creams, joint injections |
| mechanism | needs_revision | rewritten + cited; framed as bone strength, not a blood-calcium drop |
| clinical impact | needs_revision | stated with the guideline's duration/dose threshold |
| monitoring | verified | now the ACR fracture-risk assessment (verbatim-supported by the 2022 abstract) |
| recommendation | unsupported | **removed "All patients … should take 1,000–1,500 mg calcium and 800–2,000 IU vitamin D3"**; replaced with guideline-directed assessment |
| consumer copy | needs_revision | removed "calcium is part of standard support" (universal framing) |
| citations | needs_revision | NIH-ODS placeholder → 37845798 + 14687590 |
| comparison amount | unsupported | **`adequacy_threshold_mg: 500` REMOVED** — guideline targets TOTAL intake incl. diet, which the app cannot see; a threshold would read as a supplement target |
| relationship type | verified | `depletion` retained — a genuine loss mechanism exists |

**No specific mg figure is quoted**, because the ACR abstracts read do not state
one; asserting an unread number would violate the no-uncited-claim rule.

---

## 3. DEP_CORTICOSTEROIDS_VITAMIND → verified, RETYPED to `monitoring_stability`

**The direct-depletion claim does not survive.** A targeted search for human
evidence that glucocorticoids lower 25(OH)D returned:
- **PMID 25055165** Peracchi 2014 (juvenile SLE) — low 25(OH)D was common but
  explicitly **"not associated with … medication intake"**.
- **PMID 32623952** Cardona-Cardona 2020 (SLE) — only a *confounded
  cross-sectional correlation* in a diseased, sun-avoiding population.
- Remaining hits were **veterinary** (PMID 22141403 dogs — prednisolone-treated
  dogs did **not** have lower 25(OH)D; PMID 11110384 cats).

→ Per the stated criterion ("reject if the depletion claim cannot be supported
independently of glucocorticoid-treated populations having low vitamin D"), the
depletion framing fails. The **CYP24A1 mechanism is removed entirely**: the old
text claimed corticosteroids "accelerate **hepatic** catabolism of 25-OH-D by
inducing CYP24A1" — CYP24A1 is the renal/target-tissue 24-hydroxylase, not a
hepatic enzyme, and no source supports that exact clinical claim.

Rather than delete a real clinical signal, the record is **retyped to
`monitoring_stability`** — an existing taxonomy value the app already renders
("Monitoring {nutrient} may be relevant while taking {drug}…"). Vitamin D
assessment during prolonged GC therapy IS guideline-backed (**PMID 37845798**).

| Field | Result | Action |
|-------|--------|--------|
| relationship | unsupported (as depletion) | **retyped** to a monitoring consideration |
| scope | needs_revision | narrowed to prolonged systemic GC |
| mechanism | unsupported | **CYP24A1/hepatic-catabolism claim DELETED**; copy now explicitly says the drug is not known to drain vitamin D |
| clinical impact | needs_revision | reframed to bone-health risk |
| monitoring | verified | ACR fracture-risk assessment |
| recommendation | unsupported | **removed "1,000–2,000 IU … up to 4,000 IU"**; no universal dose |
| consumer copy | unsupported | headline "Can lower vitamin D with long-term use" was false → replaced |
| citations | needs_revision | NIH-ODS placeholder → 37845798 |
| comparison amount | unsupported | **`adequacy_threshold_mcg: 25` REMOVED** |
| relationship type | unsupported | `depletion` → **`monitoring_stability`** (added to the taxonomy lock in `test_medication_depletions.py`) |

evidence_level `established`→**`probable`**; severity `significant`→**`moderate`**.

---

## Residual limitation (not fixable in this sprint)

Both corticosteroid records still reference `class:corticosteroids`, which the
app cannot yet resolve to *systemic-only, >3-month* exposure. Scope is therefore
stated in the copy (which is what the user reads) but cannot yet gate firing —
the same class-resolver gap tracked for Sprint 3 (diuretics / antacids /
anticonvulsants). Documented so it is not mistaken for a completed narrowing.
