# Stage 2 receipts: medication classes (2026-11-11)

Applied by `apply_stage2_memberships.py`; tested by
`scripts/tests/test_medication_class_membership_reachability.py` (members and exclusions per class).
Every RxCUI added directly was checked on RxNorm `historystatus` (name, tty IN, status Active) on
2026-11-11: `stage2_rxnorm_verification.txt`. Members copied from `class:ssris` and `class:insulins`
keep those classes' existing verification. Membership candidates came from live RxClass ATC
membership (`rxclass/classMembers`, relaSource ATC) or exact RxNorm name lookups. Agent review;
no clinician has reviewed these memberships yet.

| Class | Basis | Members | Excluded on purpose | Open for PharmD |
|---|---|---|---|---|
| `class:cardiac_glycosides` | ATC C01AA | 8 (digoxin 3407, digitoxin 3403, …) | — | — |
| `class:thyroid_medications` | ATC H03AA; RxClass returns only tiratricol, so levothyroxine 10582, liothyronine 10814 and thyroid USP 10572 come from exact name lookups | 4 | Antithyroid drugs (methimazole, propylthiouracil; H03B). Every thyroid sub-rule is about thyroid-hormone absorption or action | The profile vocabulary lists methimazole as an example of `thyroid_medications` |
| `class:antidepressants_ssri_snri` | `class:ssris` (N06AB) plus venlafaxine 39786, desvenlafaxine 734064, duloxetine 72625, milnacipran 588250, levomilnacipran 1433212 | 11 | Bupropion, tricyclics | — |
| `class:anticholinergics` | ATC G04BD, N04AA; benztropine 1424, scopolamine 9601, glycopyrronium 1546438 (IN; 4955 is a PIN), dicyclomine 3361, hyoscyamine 153970 | 22 | Mirabegron and vibegron (beta-3 agonists in G04BD), flavoxate | Diphenhydramine and tricyclics (secondary anticholinergic effect), which the vocabulary's examples include |
| `class:hypoglycemics_high_risk` | Signed vocabulary tier: `class:insulins` plus A10BB sulfonylureas, repaglinide 73044, nateglinide 274332 | 22 | — | — |
| `class:hypoglycemics_lower_risk` | Signed vocabulary tier: metformin, phenformin, GLP-1 agonists (A10BJ), SGLT2 (A10BK), DPP-4 (A10BH) | 19 | Tirzepatide (the vocabulary names neither tier for it) | — |
| `class:hypoglycemics_unknown` | Diabetes medicines named in neither tier: TZDs, acarbose, miglitol, pramlintide, benfluorex, tirzepatide | 8 | Guar gum (A10BX01, a dietary fiber) | Tier for tirzepatide and pramlintide. The unknown tier carries the high-risk severities, so this placement is the conservative one |
| `class:clobazam` | clobazam 21241 | 1 | Not added to `class:anticonvulsants`, which also reaches the enzyme-induction contraceptive pair | — |

Rules and taxonomy:

- `RULE_BANNED_CBD_INTERACTIONS` anticonvulsants sub-rule: `drug_classes_any` gains `clobazam` and
  `valproate`, the two medicines the cannabidiol label names. Valproate stays out of
  `class:anticonvulsants` (it inhibits, not induces, CYP enzymes; see `test_med_nutrient_antiseizure`).
  Severity and wording are unchanged.
- `clinical_risk_taxonomy.json` 5.5.0 → 5.6.0 adds the gate ids `valproate` and `clobazam`. This is
  gate vocabulary only, like `ssris` and `lithium`; the profile picker (`drug_class_vocab.json`) is
  unchanged. The app validates gates at runtime without the taxonomy (`safety_alert.dart`), so a
  device on the old taxonomy file does not drop the rule.

Still unreachable from entered medicines (ratchet ceiling 8): `cyp3a4_substrates` 3,
`cyp2d6_substrates` 3, `antiarrhythmics` 2. Their membership needs a per-drug source review (Stage 3).

Noted, not changed: `scripts/api_audit/seed_drug_classes.py --live` rewrites drug_classes.json from its own
class list, which already lacks `class:lithium` and `class:valproate` and now these eight. A reseed would drop them.
