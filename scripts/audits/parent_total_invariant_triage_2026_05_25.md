# Parent-total invariant triage — 2026-05-25

Source scanner: `scripts/audits/audit_parent_total_invariant_2026_05_25.py`

Source report: `scripts/audits/parent_total_invariant_report.json`

Baseline finding: 1,163 pass groups / 64 miss groups.

## Shipped narrow fix

Commit `6f19cd72` adds one deliberately narrow parent-total extension:

- top-level row and nested child share `canonical_id`
- row names normalize to the same string
- units normalize to the same string
- positive numeric quantities are equal

This catches exact duplicate label restatements while preserving true
multi-source cases.

Confirmed fixed in-process before corpus rerun:

| DSLD | Canonical ID | Shape |
|---|---|---|
| 271087 | `vitamin_c` | `Vitamin C 500 mg` top-level + `Vitamin C 500 mg` nested under `Polyphenol-C Proprietary Blend` |
| 231826 | `chromium` | `Chromium 100 mcg` top-level + `Chromium 100 mcg` nested under Phase 3 blend |
| 62816 | `chromium` | `Chromium 100 mcg` top-level + `Chromium 100 mcg` nested under Phase 3 blend |

Negative controls preserved:

| DSLD | Canonical ID | Why not a parent total |
|---|---|---|
| 82369 | `caffeine` | standalone caffeine plus green-tea-derived caffeine are distinct sources |
| 316791 | `caffeine` | caffeine anhydrous plus coffee-bean caffeine are distinct sources |

## Remaining 61 miss groups after the narrow fix

These are not safe to fold into one broad parent-total rule. They split into
separate semantics.

| Bucket | Count | Status | Notes |
|---|---:|---|---|
| Valid multi-source | 8 | leave as-is | caffeine anhydrous plus coffee/green-tea caffeine |
| Child constituent demotion — omega | 23 | next rule candidate | fish oil / omega total / EPA-DHA constituent patterns need omega-specific handling |
| Child constituent demotion — marker/extract constituents | 15 | next rule candidate, lower priority | silymarin/silybin, diosmin, BioVin/resveratrol, PreticX/XOS, choline forms, etc. |
| Needs human label review — L-carnitine matrices | 5 | do not auto-fix yet | same ingredient appears in ripped/proprietary matrices, but quantities differ |
| Needs human label review — BioCell chondroitin | 4 | do not auto-fix yet | top-level chondroitin plus BioCell-derived chondroitin may be additive label semantics |
| Needs human label review — B-vitamin nested forms | 3 | do not auto-fix yet | pantothenic acid/pantethine and B6/P5P form relationships |
| Nutrient-form parent-total extension | 2 | separate narrow rule | `vitamin_k`/MK-4 and `vitamin_b6`/P5P are not exact-name duplicates |
| Needs human label review — alpha-linolenic acid | 1 | do not auto-fix yet | cod-liver/omega oil constituent context |

## Recommended next parent-total slice

Do **not** broaden cleaner demotion. The current rule belongs in the enricher.

Next highest-yield rule should be omega-specific constituent handling:

- target only omega/fish-oil products
- recognize top-level source oil rows (`fish_oil`, algae oil/life'sOmega)
- demote or parent-total source-oil rows when EPA/DHA/omega constituent rows
  are disclosed as children of total omega/EPA-DHA containers
- preserve products where two distinct source oils are intentionally additive

That slice needs its own red tests from the report examples before any code
change.

## Slice #2 — omega/fish-oil constituent handling

Rule added in this slice:

- only applies to omega canonical groups: `fish_oil`, `epa`, `dha`, `epa_dha`
- requires at least one nested child with positive dose
- requires the nested child to sit under a `parentBlend` that normalizes like
  a total omega / EPA-DHA constituent container (`Total Omega-3 Fatty Acids`,
  `Total Omega-3 Fatty Acids Ethyl Esters`, etc.)
- marks only top-level source-oil rows as `is_parent_total=True`; nested
  disclosed constituent rows remain score-eligible

Confirmed fixed in-process before corpus rerun:

| Canonical ID | Groups fixed | Examples |
|---|---:|---|
| `fish_oil` | 19 | Nature Made `Fish Oil 1000 mg`, `Full Strength Minis Super Omega-3` |
| `dha` | 3 | Sports Research `Vegan Omega-3 Algae Oil`, `Vegan Omega + D3`, `Keto Omega-3 1400 mg` |

Negative control preserved:

| DSLD | Canonical ID | Why not a parent total |
|---|---|---|
| 178674 | `fish_oil` | Spring Valley `Fish, Flax & Borage Oil`: nested omega row is under `Borage Oil`, not a total-omega disclosure for the top-level fish-oil row |

Expected parent-total invariant state after slices #1 and #2: 25 of the
original 64 miss groups are addressed in code (3 exact duplicate restatements
+ 22 omega source-oil/constituent rows), leaving 39 miss groups for later
human-reviewed slices.
