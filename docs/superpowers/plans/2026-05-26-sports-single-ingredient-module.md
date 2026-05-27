# Wave 6 Sports Single-Ingredient Module Implementation Plan

> **For agentic workers:** REQUIRED: Use superpowers:subagent-driven-development (if subagents available) or superpowers:executing-plans to implement this plan. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Add a v4 sports scoring module that evaluates transparent sports-nutrition products with class-appropriate dose math instead of the generic RDA/UL proxy.

**Architecture:** Keep the existing Clean -> Enrich -> Score contracts intact. Add a `sports` v4 module that reuses generic formulation, evidence, trust, transparency, manufacturer trust, and manufacturer violations, but replaces generic dose with a sports-specific dose rubric. Route only products with explicit sports identity, avoiding broad "amino_acid" routing that would catch NAC, theanine, tryptophan, and other non-sports products.

**Tech Stack:** Python 3.13, pytest 9, existing `scripts/scoring_v4` module pattern, fresh enriched/scored artifacts in `scripts/products`, v4 shadow report tooling.

---

## Why This Is The Right Root Fix

Current v4 sports canaries route through `generic`. Generic dose uses RDA/UL proxy math, which is correct for vitamins/minerals but wrong for ergogenic sports actives:

- `269425 Nutricost Creatine Monohydrate 3 g`: dose is `null` because creatine has no RDA/UL reference in the generic proxy.
- `325587 Transparent Labs Creatine HMB`: generic accidentally evaluates creatine through pseudo-RDA data and overweights micronutrient rows mixed into the product.
- `268690 Sports Research Whey Protein Isolate`: protein serving is present, but generic dose is diluted by incidental minerals/vitamins.
- `229913 GNC Precision BCAA`: BCAA serving is present, but generic dose averages mineral RDA rows and misses sports-intent dose adequacy.
- `306381 Nutricost PRE`: pre-workout ingredients are disclosed, but generic routing cannot express class-specific dose ceilings and stimulant risk.

Do not patch individual scores or canary ranges. The root is missing class-specific dose semantics.

## Current Evidence From Fresh Artifacts

Fresh canary shadow state:

- `scripts/api_audit/v4_shadow_canary_report.py` currently reports these sports products as `v4_module="generic"`.
- `scripts/data/canary_products.json` already labels sports canaries with `primary_class` values like `sports_opaque` and `sports_transparent`.
- `scripts/scoring_v4/router.py` has only four valid classes: `generic`, `probiotic`, `multi_or_prenatal`, and `omega`.
- `scripts/scoring_v4/modules/generic_dose.py` explicitly declares its dose method as `rda_ul_proxy_until_dietary_intake_table`.

Clinical anchors checked on 2026-05-26:

- ISSN creatine position stand: creatine has its own exercise/sports efficacy framework and should not be evaluated as a normal RDA nutrient. PubMed PMID: 28615996. Source: https://pubmed.ncbi.nlm.nih.gov/28615996/
- ISSN beta-alanine position stand: 4-6 g/day for at least 2-4 weeks is the relevant performance dosing frame, not RDA/UL. Source: https://link.springer.com/article/10.1186/s12970-015-0090-y
- ISSN protein position stand: practical serving targets are 20-40 g high-quality protein and 700-3000 mg leucine, with daily intake context. PubMed PMID: 28642676. Source: https://pubmed.ncbi.nlm.nih.gov/28642676/
- ISSN EAA position stand: EAA supplementation has a distinct skeletal muscle/performance frame. PubMed PMID: 37800468. Source: https://pubmed.ncbi.nlm.nih.gov/37800468/
- Citrulline evidence is mixed and should be conservative; 2023 JISSN systematic review exists, and citrulline malate literature commonly tests acute 6-12 g, often 8 g, with variable outcomes. PubMed PMID: 37155582. Source: https://pubmed.ncbi.nlm.nih.gov/37155582/
- HMB has a recent ISSN position stand and should be included only after the core sports dose framework is stable. PubMed PMID: 39699070. Source: https://pubmed.ncbi.nlm.nih.gov/39699070/

## Non-Goals

- Do not change v3 shipped scoring.
- Do not change Clean or Enrich unless a concrete contract bug is discovered.
- Do not add clinical evidence entries or PMIDs in this slice.
- Do not add broad IQM aliases.
- Do not route every `amino_acid` product to sports.
- Do not route every `protein_powder` taxonomy product to sports; inventory found that taxonomy bucket includes keratin/lactoferrin products that must stay generic unless they carry sports-protein identity.
- Do not credit opaque proprietary blends as fully dosed.
- Do not make the app-visible catalog depend on this until shadow tests and canary audit pass.

## File Map

Modify:

- `scripts/scoring_v4/router.py`
  - Add `sports` to valid classes.
  - Add a conservative `_is_sports_class(product, name_text)` helper.
  - Route explicit `pre_workout` taxonomy to `sports`.
  - Route `protein_powder` taxonomy to `sports` only when paired with sports-protein evidence such as whey/protein/gainer product text or protein canonicals.
  - Route `amino_acid` to `sports` only when sports-active identity is present.

- `scripts/score_supplements_v4_shadow.py`
  - Dispatch `sports` to the new module.

- `scripts/scoring_v4/gate_completeness.py`
  - Add sports completeness rules: must have at least one sports-active row with positive dose, or be explicitly opaque with a traceable not-evaluable reason.

- `scripts/api_audit/v4_shadow_canary_report.py`
  - Include `sports` in module counts.
  - Add sports-specific compression flags for not-evaluable dose, opaque sports blend, and generic-routing regression.

Create:

- `scripts/scoring_v4/modules/sports.py`
  - Final assembly wrapper, mirroring `generic.py` shape.

- `scripts/scoring_v4/modules/sports_dose.py`
  - Class-specific dose dimension.

- `scripts/scoring_v4/modules/sports_helpers.py`
  - Sports-active detection, dose normalization, group aggregation.

- `scripts/tests/test_v4_sports_router_p170.py`
  - Router unit tests and negative guards.

- `scripts/tests/test_v4_sports_dose_p171.py`
  - Sports dose rubric tests.

- `scripts/tests/test_v4_sports_final_assembly_p172.py`
  - Module assembly and canary tests.

- `scripts/tests/test_v4_shadow_sports_canaries_p173.py`
  - Shadow report regression tests.

Optional, only if a data-driven threshold table is preferable after Task 1:

- `scripts/data/sports_dose_rubric.json`
  - If added, must include `_metadata`, citations, and tests. Prefer code constants first unless the rubric grows.

## Scoring Contract

The new module returns the same public breakdown shape as `generic`:

```python
{
    "module": "sports",
    "dimensions": {
        "formulation": {...},
        "dose": {...},
        "evidence": {...},
        "trust": {...},
        "transparency": {...},
    },
    "manufacturer_trust": {...},
    "manufacturer_violations": {...},
    "raw_score_100": 0.0,
    "score_100": 0.0,
    "phase": "P1.7_sports_module",
    "metadata": {...},
}
```

Dimension reuse:

- Formulation: reuse `generic_formulation.score_formulation`.
- Evidence: reuse `generic_evidence.score_evidence`.
- Trust: reuse `generic_trust.score_trust`.
- Transparency: reuse `generic_transparency.score_transparency`; its sports B5 multiplier already exists.
- Manufacturer trust/violations: reuse generic manufacturer modules.
- Dose: replace with `sports_dose.score_dose`.

## Sports Dose Rubric V1

Dimension cap: 25, same as generic dose.

Components:

- `sports_primary_active_dose`: up to 20
- `sports_stack_support`: up to 3
- `sports_ratio_or_completeness`: up to 2

Penalties:

- `opaque_primary_sports_blend`: up to -10 when the product is sports-primary but primary doses are hidden.
- `stimulant_high_caffeine`: up to -5 when caffeine dose crosses configured safety band.
- `dose_not_evaluable`: metadata flag only, not a penalty unless opacity caused it.

V1 active dose bands:

- Creatine monohydrate / creatine salts:
  - 0 if no dose.
  - 8 if >0 and <3 g/day.
  - 16 if 3 to <5 g/day.
  - 20 if 5 g/day.
  - Cap at 20. Do not add more credit above 5 g.

- Whey/protein powder:
  - 0 if no protein dose.
  - 8 if >0 and <15 g protein.
  - 16 if 15 to <20 g protein.
  - 20 if 20 to 40 g protein.
  - 16 if >40 g protein, because serving may be large but not necessarily better.
  - Leucine bonus belongs in `sports_ratio_or_completeness`, not primary dose.

- Beta-alanine:
  - 0 if no dose.
  - 8 if >0 and <2 g/day.
  - 16 if 2 to <4 g/day.
  - 20 if 4 to 6 g/day.
  - 16 if >6 g/day, plus metadata `above_common_beta_alanine_band`.

- Citrulline / citrulline malate:
  - Conservative due mixed evidence.
  - For L-citrulline: 16 at 3 to <6 g, 18 at 6 to 8 g, no higher than 18.
  - For citrulline malate: 14 at 6 to <8 g, 18 at 8 to 12 g, no higher than 18.
  - Below these ranges receives proportional partial credit.

- BCAA:
  - Group leucine + isoleucine + valine.
  - 0 if any one of the three is missing or total dose is missing.
  - 12 if total BCAA is 3 to <5 g.
  - 18 if total BCAA is >=5 g with recognizable 2:1:1-ish ratio.
  - If total dose is high but ratio is incomplete, cap at 14.

- EAA:
  - Group essential amino acids when at least six EAA rows are present.
  - 12 for 5 to <8 g.
  - 18 for >=8 g.
  - Add ratio/completeness credit when leucine is present at 700-3000 mg or equivalent per protein source.

- Caffeine:
  - No primary-active dose credit by default.
  - It can support pre-workout stack completeness but should not make a product high-scoring alone.
  - Add safety metadata and high-dose penalty bands after a dedicated stimulant review.

V1 explicitly defers:

- HMB standalone scoring. Keep HMB as support component unless added in Task 8 with PMID-verified threshold.
- Electrolyte sport products.
- Energy drinks/shots.
- Opaque proprietary pre-workouts with hidden caffeine or stimulant doses.

## Task 1: Read-Only Sports Inventory

**Files:**
- Create: `reports/v4_sports_module_inventory_2026_05_26.json`
- Create: `reports/v4_sports_module_inventory_2026_05_26.md`

- [ ] Step 1: Write a scanner that reads fresh `scripts/products/output_*_enriched/enriched/*.json`.

Use a temporary script or inline Python. It should classify products into these buckets:

- `protein_powder` (sports-protein signal only; taxonomy alone is insufficient)
- `creatine_single`
- `creatine_stack`
- `bcaa_eaa`
- `pre_workout_transparent`
- `pre_workout_opaque`
- `sports_accessory_or_ambiguous`
- `non_sports_amino_guard`

- [ ] Step 2: Emit counts and 5 examples per bucket.

Command:

```bash
python3 /tmp/v4_sports_inventory.py
```

Expected:

- Counts sum to the number of products scanned.
- Canary ids `306381`, `2722`, `268690`, `325587`, `269425`, `229913`, `274376` land in deterministic sports buckets.
- NAC, L-theanine, tryptophan, 5-HTP, and digestive enzyme products land outside sports.

- [ ] Step 3: Review the inventory before writing tests.

Stop if any bucket is too broad. The router must be conservative.

## Task 2: Router Tests

**Files:**
- Create: `scripts/tests/test_v4_sports_router_p170.py`
- Modify: `scripts/scoring_v4/router.py`

- [ ] Step 1: Write failing router tests.

Test cases:

```python
def test_pre_workout_taxonomy_routes_to_sports():
    product = {"supplement_taxonomy": {"primary_type": "pre_workout"}, "fullName": "Pre-Workout"}
    assert class_for_product(product) == "sports"


def test_whey_protein_powder_routes_to_sports():
    product = {"supplement_taxonomy": {"primary_type": "protein_powder"}, "fullName": "Whey Protein Isolate"}
    assert class_for_product(product) == "sports"


def test_keratin_protein_powder_stays_generic():
    product = {"supplement_taxonomy": {"primary_type": "protein_powder"}, "fullName": "Keratin 500 mg"}
    assert class_for_product(product) == "generic"


def test_creatine_amino_acid_routes_to_sports_by_canonical():
    product = _product(primary_type="amino_acid", rows=[_row("creatine_monohydrate", 3, "g")])
    assert class_for_product(product) == "sports"


def test_nac_amino_acid_stays_generic():
    product = _product(primary_type="amino_acid", rows=[_row("nac", 600, "mg")], name="NAC 600 mg")
    assert class_for_product(product) == "generic"


def test_theanine_sleep_support_stays_generic():
    product = _product(primary_type="amino_acid", rows=[_row("l_theanine", 200, "mg")], name="Calm Sleep L-Theanine")
    assert class_for_product(product) == "generic"
```

- [ ] Step 2: Run router tests and confirm RED.

```bash
python3 -m pytest scripts/tests/test_v4_sports_router_p170.py -q
```

Expected: sports-positive tests fail because `sports` is not valid/routed yet; negative guards pass or fail only if helper is missing.

- [ ] Step 3: Implement router changes.

Minimal implementation:

```python
VALID_CLASSES = ("generic", "probiotic", "multi_or_prenatal", "omega", "sports")

_SPORTS_PRIMARY_TAXONOMY = {"pre_workout"}
_SPORTS_PROTEIN_CANONICALS = {"whey_protein", "pea_protein", "rice_protein", "soy_protein"}
_SPORTS_CANONICALS = {
    "creatine_monohydrate",
    "beta-alanine",
    "l_citrulline",
    "whey_protein",
    "l_leucine",
    "l_isoleucine",
    "l_valine",
    "hmb",
    "caffeine",
}
```

Use scorable positive rows only. Require explicit name/taxonomy/canonical signal for `amino_acid`.

- [ ] Step 4: Run router tests and existing router suite.

```bash
python3 -m pytest scripts/tests/test_v4_sports_router_p170.py scripts/tests/test_v4_b5_class_adoption_t4.py scripts/tests/test_v4_taxonomy_adoption.py -q
```

Expected: all pass.

- [ ] Step 5: Commit.

```bash
git add scripts/scoring_v4/router.py scripts/tests/test_v4_sports_router_p170.py
git commit -m "feat(v4): route explicit sports products to sports module"
```

## Task 3: Sports Helpers

**Files:**
- Create: `scripts/scoring_v4/modules/sports_helpers.py`
- Create: `scripts/tests/test_v4_sports_dose_p171.py`

- [ ] Step 1: Write tests for dose normalization and grouping.

Tests:

- `3 Gram(s)` normalizes to 3000 mg and 3 g.
- `5000 mg` normalizes to 5 g.
- BCAA group totals leucine/isoleucine/valine.
- EAA group requires at least six essential amino acid rows.
- Incidental minerals do not dilute sports dose.

- [ ] Step 2: Run tests and confirm RED.

```bash
python3 -m pytest scripts/tests/test_v4_sports_dose_p171.py -q
```

- [ ] Step 3: Implement helper functions.

Public helpers:

```python
def sports_rows(product: dict) -> list[dict]: ...
def dose_g(row: dict) -> float | None: ...
def dose_mg(row: dict) -> float | None: ...
def canonical(row: dict) -> str: ...
def group_bcaa(rows: list[dict]) -> dict: ...
def group_eaa(rows: list[dict]) -> dict: ...
def primary_sports_identity(product: dict) -> str | None: ...
```

- [ ] Step 4: Run tests.

Expected: all helper tests pass.

- [ ] Step 5: Commit.

```bash
git add scripts/scoring_v4/modules/sports_helpers.py scripts/tests/test_v4_sports_dose_p171.py
git commit -m "feat(v4): add sports active dose helpers"
```

## Task 4: Sports Dose Module

**Files:**
- Create: `scripts/scoring_v4/modules/sports_dose.py`
- Modify: `scripts/tests/test_v4_sports_dose_p171.py`

- [ ] Step 1: Add failing dose tests.

Required test cases:

- Creatine 3 g earns partial/high dose credit, not `None`.
- Creatine 5 g earns max primary dose credit.
- Whey 22.5 g earns max protein serving credit.
- Beta-alanine 3.2 g earns near-high credit but below 4-6 g max.
- Citrulline malate 6 g earns conservative partial credit.
- BCAA 5:2.5:2.5 g earns high BCAA credit and ratio/completeness credit.
- Opaque pre-workout with hidden primary dose returns not-evaluable metadata and opacity penalty.
- Incidental calcium/iron/potassium rows do not reduce sports dose score.

- [ ] Step 2: Confirm RED.

```bash
python3 -m pytest scripts/tests/test_v4_sports_dose_p171.py -q
```

- [ ] Step 3: Implement `score_dose(product)`.

Return shape:

```python
{
    "score": 0.0,
    "max": 25.0,
    "components": {
        "sports_primary_active_dose": 0.0,
        "sports_stack_support": 0.0,
        "sports_ratio_or_completeness": 0.0,
    },
    "penalties": {
        "opaque_primary_sports_blend": 0.0,
        "stimulant_high_caffeine": 0.0,
    },
    "phase": "P1.7_sports_dose_v1",
    "metadata": {
        "phase": "P1.7_sports_dose_v1",
        "method": "sports_active_dose_bands_v1",
        "primary_identity": "...",
        "dose_basis": "...",
        "not_evaluable_reason": None,
    },
}
```

- [ ] Step 4: Run dose tests.

Expected: all pass.

- [ ] Step 5: Commit.

```bash
git add scripts/scoring_v4/modules/sports_dose.py scripts/tests/test_v4_sports_dose_p171.py
git commit -m "feat(v4): score sports active dose bands"
```

## Task 5: Sports Module Assembly

**Files:**
- Create: `scripts/scoring_v4/modules/sports.py`
- Create: `scripts/tests/test_v4_sports_final_assembly_p172.py`
- Modify: `scripts/score_supplements_v4_shadow.py`

- [ ] Step 1: Write failing module assembly tests.

Assertions:

- `score_sports(product).module == "sports"`.
- Breakdown contains all five dimensions.
- Dose dimension phase is `P1.7_sports_dose_v1`.
- Formulation/evidence/trust/transparency are reused and still populated.
- Final score is calibrated using the same v4 assembly convention unless a later calibration task changes it.

- [ ] Step 2: Confirm RED.

```bash
python3 -m pytest scripts/tests/test_v4_sports_final_assembly_p172.py -q
```

- [ ] Step 3: Implement `score_sports`.

Mirror `score_generic`, swapping only the dose import.

- [ ] Step 4: Wire shadow dispatch.

In `scripts/score_supplements_v4_shadow.py`, dispatch `class_for_product(product) == "sports"` to `score_sports`.

- [ ] Step 5: Run assembly tests.

Expected: all pass.

- [ ] Step 6: Commit.

```bash
git add scripts/scoring_v4/modules/sports.py scripts/score_supplements_v4_shadow.py scripts/tests/test_v4_sports_final_assembly_p172.py
git commit -m "feat(v4): assemble sports scoring module"
```

## Task 6: Completeness Gate

**Files:**
- Modify: `scripts/scoring_v4/gate_completeness.py`
- Create or modify: `scripts/tests/test_v4_completeness_gate.py`

- [ ] Step 1: Write failing gate tests.

Cases:

- Sports product with positive creatine dose passes.
- Sports product with protein dose passes.
- Opaque sports product with no disclosed sports-active dose fails or passes with explicit `sports_dose_not_evaluable` depending on current gate pattern.
- Non-sports amino acid product still uses generic gate.

- [ ] Step 2: Confirm RED.

```bash
python3 -m pytest scripts/tests/test_v4_completeness_gate.py -k sports -q
```

- [ ] Step 3: Implement sports gate.

Keep it simple:

- Require at least one positive sports row for transparent scoring.
- Allow opaque products only when the gate result carries a deterministic reason consumed by the shadow report.

- [ ] Step 4: Run tests.

Expected: all pass.

- [ ] Step 5: Commit.

```bash
git add scripts/scoring_v4/gate_completeness.py scripts/tests/test_v4_completeness_gate.py
git commit -m "feat(v4): add sports completeness gate"
```

## Task 7: Canary And Shadow Report Integration

**Files:**
- Create: `scripts/tests/test_v4_shadow_sports_canaries_p173.py`
- Modify: `scripts/api_audit/v4_shadow_canary_report.py`

- [ ] Step 1: Write failing canary tests using fresh artifacts.

Assertions:

- `306381`, `2722`, `268690`, `325587`, `269425`, `229913`, and `274376` are no longer `v4_module="generic"` when appropriate.
- `269425` no longer carries `dose_not_evaluable_with_large_score_drop`.
- `268690` protein dose is evaluated from protein serving, not incidental minerals.
- `229913` dose metadata says BCAA grouping.
- `306381` and `2722` are sports, but opacity/pre-workout metadata remains visible.

- [ ] Step 2: Confirm RED.

```bash
python3 -m pytest scripts/tests/test_v4_shadow_sports_canaries_p173.py -q
```

- [ ] Step 3: Update shadow report.

Add:

- `sports` module count.
- `sports_dose_not_evaluable`
- `opaque_sports_blend`
- `sports_generic_routing_regression`

- [ ] Step 4: Run shadow report.

```bash
python3 scripts/api_audit/v4_shadow_canary_report.py --out-dir /tmp/v4_shadow_sports_check
```

Expected:

- Sports canaries route to `sports`.
- No missing enriched.
- No broad score explosion.
- Confidence improves for transparent sports products.

- [ ] Step 5: Commit.

```bash
git add scripts/api_audit/v4_shadow_canary_report.py scripts/tests/test_v4_shadow_sports_canaries_p173.py
git commit -m "feat(v4): report sports module canary coverage"
```

## Task 8: Optional HMB And Stimulant Tightening

Only do this after Tasks 1-7 pass.

**Files:**
- Modify: `scripts/scoring_v4/modules/sports_dose.py`
- Modify: `scripts/tests/test_v4_sports_dose_p171.py`

- [ ] Step 1: Add HMB tests if the canary/product inventory justifies it.

Use ISSN HMB position stand as clinical anchor. Do not invent a threshold without source support.

- [ ] Step 2: Add caffeine safety tests.

Do not credit caffeine as a primary active by default. Only add safety penalty/metadata if current enriched data exposes reliable per-serving caffeine dose.

- [ ] Step 3: Implement only if tests and evidence are clear.

- [ ] Step 4: Commit separately.

```bash
git add scripts/scoring_v4/modules/sports_dose.py scripts/tests/test_v4_sports_dose_p171.py
git commit -m "feat(v4): tighten sports HMB and stimulant handling"
```

## Task 9: Verification Suite

Run after all implementation tasks.

- [ ] Focused sports tests:

```bash
python3 -m pytest \
  scripts/tests/test_v4_sports_router_p170.py \
  scripts/tests/test_v4_sports_dose_p171.py \
  scripts/tests/test_v4_sports_final_assembly_p172.py \
  scripts/tests/test_v4_shadow_sports_canaries_p173.py \
  -q
```

- [ ] Existing v4 tests:

```bash
python3 -m pytest scripts/tests/test_v4_*.py -q
```

- [ ] Fast suite:

```bash
bash scripts/test.sh fast
```

- [ ] Shadow report:

```bash
python3 scripts/api_audit/v4_shadow_canary_report.py --out-dir /tmp/v4_shadow_sports_final
```

- [ ] Verify canary deltas manually:

Expected:

- `269425` dose is evaluable.
- `325587` dose is anchored on creatine/HMB stack, not calcium/vitamin D proxy.
- `268690` and `274376` dose use protein serving.
- `229913` dose uses BCAA grouping.
- `306381` and `2722` route sports but do not hide opacity/stimulant limitations.

## Task 10: Corpus Smoke Check

Do not run full corpus until focused v4 tests are green.

- [ ] Run a targeted v4 shadow scan on products where `supplement_taxonomy.primary_type in {"protein_powder", "pre_workout", "amino_acid"}`.

- [ ] Confirm no obvious false sports routing:

Negative examples must remain generic:

- NAC
- L-theanine sleep/calm products
- 5-HTP
- tryptophan
- collagen
- digestive enzymes

- [ ] Confirm sports module count is plausible.

Expected outcome depends on inventory, but should not include every amino acid product.

## Task 11: Final Commit And Handoff

- [ ] Review `git diff --stat`.

- [ ] Confirm no unrelated Wave 8 interaction files were staged.

```bash
git status --short
```

- [ ] Run final focused tests one more time.

- [ ] Commit final cleanup if needed.

- [ ] Handoff summary:

Include:

- Files changed.
- Tests run.
- v4 shadow sports module counts.
- Remaining deferred items: HMB if not implemented, stimulant policy, electrolyte sports products, opaque blends.

## Success Criteria

Functional:

- Sports canaries route to `sports`, except any explicit negative/ambiguous cases documented by inventory.
- Transparent creatine, protein, and BCAA products have dose scores based on sports-active serving doses.
- Generic RDA/UL dose proxy no longer controls sports-active dose adequacy.
- Non-sports amino acid products remain generic.

Safety:

- Opaque pre-workout products do not receive full dose credit.
- Stimulant products preserve caffeine metadata and can receive penalties once policy is locked.
- No product earns extra credit from incidental minerals/vitamins in protein/pre-workout panels.

Testing:

- New sports tests pass.
- Existing v4 tests pass.
- Fast suite has no new failures.
- Shadow report has no missing enriched products and no sports-generic regression flags.

Operational:

- No full rerun required until the module is green in shadow.
- No app-facing behavior changes unless/until v4 shadow output becomes production scoring.
