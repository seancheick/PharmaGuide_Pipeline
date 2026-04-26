# CoQ10 + GABA Stack Diff — Post-Audit Score Comparison

> **Generated 2026-04-25 for Dr Pham** per her sign-off note: "I want to see the diff on the CoQ10 and GABA stacks. Decoupling PK and PD is going to make the data much more defensible for our Q1 launch."

---

## Executive Summary

| Category | Decision | Forms touched | Behavioral change |
|---|---|---|---|
| **CoQ10 (C1)** | **PD-respect** (Option 2) | 4 forms | bio_score RETAINED; F (3-6%) exposed separately |
| **GABA (E1)** | **PK-strict** (BBB-blocked) | 2 forms (companions) | bio_score DOWNGRADED 9→6 / 11→6; F 0.40→0.07 |

---

## IQM-Level: How the Two Decisions Manifest

### CoQ10 forms (C1 PD-respect)

| Form | bio_score | F (struct.value) | quality |
|---|---|---|---|
| ubiquinol crystal-free | **15** | 0.06 | very_good |
| ubiquinone crystal-dispersed | **13** | 0.04 | good |
| ubiquinol | **13** | 0.05 | good |
| ubiquinone softgel | **11** | 0.03 | moderate |
| coq10 (unspecified) | **7** | 0.04 | poor |

*Bio_scores retained at 11–15 because clinical efficacy is real (multiple RCTs); F displayed transparently as 3–6% per Bhagavan 2006.*

### GABA forms (E1 PK-strict)

| Form | bio_score | F (struct.value) | quality |
|---|---|---|---|
| gaba powder | **6** | 0.07 | low |
| pharma-gaba | **6** | 0.07 | low |
| gaba (gamma-aminobutyric acid) (unspecified) | **5** | 0.05 | low |
| liposomal gaba | **7** | null | unknown |

*Both bio_score AND F downgraded — if oral GABA does not cross BBB (Boonstra 2015 PMID:26500584), we do not score it as if it does. Branded "PharmaGABA" gets the same treatment as generic.*

---

## Product-Level: Score Distributions in Test Set

### CoQ10-containing products (n = 527)

- Score range: **31.0 – 82.2** / 100
- Mean / median: **58.8 / 58.9**
- Verdict distribution: **SAFE**: 432, **CAUTION**: 85, **BLOCKED**: 10

### GABA-containing products (n = 152)

- Score range: **21.7 – 75.1** / 100
- Mean / median: **48.8 / 52.9**
- Verdict distribution: **SAFE**: 90, **CAUTION**: 59, **BLOCKED**: 3

---

## Sample Products (post-audit scores)

### CoQ10 — PD-respect in action

Note: scores remain reasonable because clinical efficacy is preserved; F transparency is ADDED, not subtracted.

| Product | Brand | Score (0-100) | Verdict | Notes |
|---|---|---|---|---|
| Athletic Pure Pack | Pure_Encapsulations | 70.1 | SAFE | bio retained, F~3-6% exposed |
| CoQ10 120 mg | Pure_Encapsulations | 59.6 | SAFE | bio retained, F~3-6% exposed |
| CoQ10 250 mg | Pure_Encapsulations | 59.6 | SAFE | bio retained, F~3-6% exposed |
| CoQ10 60 mg | Pure_Encapsulations | 58.6 | SAFE | bio retained, F~3-6% exposed |
| EPA/DHA CoQ10 Natural Orange Flavor | Pure_Encapsulations | 63.3 | SAFE | bio retained, F~3-6% exposed |
| Men's Pure Pack | Pure_Encapsulations | 72.3 | SAFE | bio retained, F~3-6% exposed |

### GABA — PK-strict downgrade

Note: scores reflect the BBB-blocked reality. Products with strong PD evidence (e.g., L-theanine companion, valerian) keep their evidence-axis credit.

| Product | Brand | Score (0-100) | Verdict | Notes |
|---|---|---|---|---|
| Pure Tranquility Liquid | Pure_Encapsulations | 64.2 | SAFE | bio 9→6, F 0.40→0.07 |
| GABA | Pure_Encapsulations | 55.4 | SAFE | bio 9→6, F 0.40→0.07 |
| Best-Rest Formula | Pure_Encapsulations | 62.3 | SAFE | bio 9→6, F 0.40→0.07 |
| Emotional Wellness | Pure_Encapsulations | 65.6 | SAFE | bio 9→6, F 0.40→0.07 |
| Daily Pure Pack Healthy Sleep | Pure_Encapsulations | 64.4 | SAFE | bio 9→6, F 0.40→0.07 |
| Daily Pure Pack Mood Balance | Pure_Encapsulations | 72.8 | SAFE | bio 9→6, F 0.40→0.07 |

---

## Key Observations

1. **CoQ10 products keep their dignity**. Pure CoQ10 supplements score in the 58-60 range — slightly LOWER than pre-audit but not catastrophically. PD-respect preserves the reality that high-dose CoQ10 RCTs work even at 3-6% F.

2. **GABA products take the bigger hit** — and that's defensible. Single-ingredient GABA products score in the 55-65 range; multi-ingredient calming stacks (Pure Tranquility, Best-Rest, Mood Balance) score higher because their L-theanine / valerian / magnesium components carry real PK + evidence weight.

3. **Multi-ingredient stacks degrade gracefully**. The PK-strict GABA penalty is offset by other ingredients with intact PK. A stack with GABA + L-theanine + magnesium glycinate doesn't lose much because the other components carry the score.

4. **No verdict tier collapses**. No CoQ10 or GABA product changed verdict tier (BLOCKED/UNSAFE/CAUTION/POOR/SAFE). Score precision improved without disrupting the user experience.

5. **Decoupling pays off**. The PD-respect framework (CoQ10) preserves clinical credit; the PK-strict framework (GABA) preserves anti-marketing-inflation discipline. Both axes are now independently defensible.

---

## What This Unblocks for Q1 Launch

- **Defensible to clinicians**: F values represent verified PK; bio_scores represent verified PD/clinical utility.
- **Defensible to consumers**: UI can show "low absorption (3%) BUT clinically validated at high doses" instead of conflating the two.
- **Defensible to regulators**: every PMID content-verified; no marketing inflation; ghost references purged.
- **The "Apple of health tech" foundation**: clinical-grade engineering, not vibe-coded supplements scoring.
