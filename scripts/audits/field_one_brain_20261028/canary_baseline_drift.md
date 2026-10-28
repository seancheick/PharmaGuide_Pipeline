# Canary baseline drift on main (found while qualifying PR #272)

The local rung's `test_e1_2_2_preflight_invariant` compares the nine canary blobs, rebuilt from
current code, against the approved baseline `reports/baseline_pre_e1_2_2/dose_v41_approved_20261018`.
Ten invariant checks fail.

**Not caused by PR #272.** The canaries rebuilt from main e6885790d in a temporary detached
checkout are identical to the PR candidate's, timestamps aside. The main checkout's local rung
passes only because its `reports/canary_rebuild/*.json` files were built on 2026-10-18 at 16:43,
the same day as the baseline.

**Procedure (unchanged, not run here).** A refresh is a new dated, reviewed capture beside the
others under `reports/baseline_pre_e1_2_2/`, with its README naming each approved contract change,
followed by an update to `release_artifact_paths.canary_baseline_dir`. That belongs to the
integrator. The expected values were not refreshed and the gate was not weakened.

Field-level drift, baseline compared with a rebuild from current main code:

```
## 1002 Double Strength Fish Oil
  penalty B2 fields changed: ['id', 'label', 'presence', 'severity'] | before {'id': None, 'label': None, 'presence': None} | after {'id': 'B2', 'label': 'Declared allergen source: Fish', 'presence': 'contains'}
## 1036 Ultra Mega Gold
  penalty B5 fields changed: ['blend_count', 'id', 'label', 'score'] | before {'blend_count': None, 'id': None, 'label': None} | after {'blend_count': 1, 'id': 'B5', 'label': 'Proprietary blend opacity'}
  warnings lost: [('interaction', 'monitor', 'Vitamin D / pregnancy', ('pregnancy',), ()), ('interaction', 'no_data', 'Iron / lactation', ('lactation',), ()), ('interaction', 'no_data', 'Iron / pregnancy', ('pregnancy',), ())]  gained: [('interaction', 'monitor', 'Iron / lactation', ('lactation',), ()), ('interaction', 'monitor', 'Iron / pregnancy', ('pregnancy',), ())]
## 176872 Vitamin D3 3000 IU Natural Blueberry Flavor
  penalty B2 fields changed: ['id', 'label', 'presence', 'severity'] | before {'id': None, 'label': None, 'presence': None} | after {'id': 'B2', 'label': 'Made in a facility that also handles: Crustacean Shellfish, Eggs, Fish, Soy & Soy Lecithin, Tree Nuts', 'presence': 'manufactured_in_facility'}
  warnings lost: [('interaction', 'monitor', 'Vitamin D / pregnancy', ('pregnancy',), ())]  gained: []
## 19055 Enteric Coated Fish Oil Mini Softgels 1290 mg
  display_ingredients[5] fields: ['display_type', 'resolution_type']
## 246324 CBD Mixed Berry
  penalty B2 fields changed: ['id', 'label', 'presence', 'severity'] | before {'id': None, 'label': None, 'presence': None} | after {'id': 'B2', 'label': 'Made in a facility that also handles: Crustacean Shellfish, Eggs, Fish, Soy & Soy Lecithin, Tree Nuts', 'presence': 'manufactured_in_facility'}
  warnings lost: []  gained: [('harmful_additive', 'low', 'Contains Unspecified Colors', (), ())]
## 266975 E 400 IU (180 mg)
## 306237 KSM-66 600 mg
  warnings lost: []  gained: [('harmful_additive', 'low', 'Contains Silicon Dioxide (E551)', (), ())]
```

**Needs review before any refresh.** For 1036 (Ultra Mega Gold) and 176872 (D3 3000 IU), the
baseline carried two "Vitamin D / pregnancy" warnings for the same condition, both
`display_mode_default: suppress`:
- an `informational` dose-guidance warning ("Use labs to guide dosing");
- a generic `monitor` warning from `RULE_INGREDIENT_VITAMIN_D` ("Standard nutrient — clinician
  guidance suggested").

Current main emits only the dose-guidance warning, so the pregnancy warning is still present, with
one entry instead of two. This looks like intended de-duplication, but it changes the warning
severity a pregnant user receives, from monitor to informational. The warning owner must confirm
it before the baseline adopts it.

The other changes are additive disclosures: B2 allergen and facility penalties, B5 blend opacity,
new low-severity harmful-additive warnings (colors, silicon dioxide), iron pregnancy/lactation
moving from `no_data` to `monitor`, and display type labels on 19055.
