# Interaction Rule Gap Audit — 2026-04-26

**Replaces:** `docs/CURATED_INTERACTIONS_PREGNANCY_DIABETES_PLAN.md` v2.0
(deleted in commit alongside this doc).

**Audit date:** 2026-04-26
**Audited against:** `scripts/data/ingredient_interaction_rules.json`
schema 5.2.0, 129 rules. (System B `curated_interactions_v1.json` is
out of scope here — that's pair-shaped data, not condition-tagged
single-supplement guidance. See `INTERACTION_DB_SPEC.md` and
`INTERACTION_TIER2_AND_BRIDGE_PLAN.md`.)

---

## Authoritative process

This doc contributes **the gap data only**. Authoring process,
schema details, severity calibration, and source-priority rules live
in:
- `scripts/INTERACTION_RULE_AUTHORING_SOP.md` — SOP / contract
- `scripts/PROMPT_ADD_INTERACTION_RULES.md` — agent prompt template

Read both before authoring. They cover the SOP-mandated workflow
(verify canonical_id exists → verify taxonomy IDs → use authoritative
sources → run tests → bump `_metadata.total_entries`).

**Verification gate (NEW, 2026-04-26):** every PMID added must clear
`scripts/api_audit/verify_interactions.py --check-pubmed` (Check 11).
A 49-defect audit on the existing 136 curated entries surfaced 41
ghost references — all were authored without PubMed content
verification. Don't repeat that mistake.

---

## Pregnancy gaps — 14 rules to add (28 → 42)

Existing 28 rules already cover: 7-keto DHEA, ephedra, yohimbe, banned
CBD, blue cohosh, mugwort, rue, butterbur, feverfew, aloe vera, black
cohosh, dong quai, goldenseal, st johns wort, wild yam, chasteberry,
senna, cascara sagrada, chinese skullcap, black seed oil, ginseng,
vitamin A, vitamin C, vitamin E, iodine, caffeine, 5-HTP.

| # | Priority | Severity | Subject DB | canonical_id | Dose? | Basis |
|---|---|---|---|---|---|---|
| 1 | **HIGH** | avoid | IQM | `licorice` | ✓ | Strandberg 2002 (PMID:12450910) — high-dose preterm labor + cortisol disruption |
| 2 | **HIGH** | contraindicated | banned_recalled† | `pennyroyal` | — | Classic abortifacient + hepatotoxin |
| 3 | **HIGH** | contraindicated | banned_recalled† | `tansy` | — | Thujone abortifacient |
| 4 | **HIGH** | avoid | IQM | `saw_palmetto` | — | Anti-androgen — fetal genitourinary concern |
| 5 | **HIGH** | contraindicated | banned_recalled† | `bitter_orange` | — | Synephrine = ephedra-class sympathomimetic |
| 6 | MED | caution | IQM | `curcumin` | ✓ | High-dose uterine stimulation (PMID:30744609) |
| 7 | MED | caution | botanical | `ginkgo_biloba_leaf` | ✓ | Bleeding risk near term + theoretical placental effect |
| 8 | MED | monitor | IQM | `vitamin_d` | ✓ | High-dose hypercalcemia at >4000 IU/day |
| 9 | MED | avoid | IQM | `dhea` | — | Hormonal (7-keto banned, plain DHEA gap) |
| 10 | MED | caution | IQM | `holy_basil` | — | Anti-fertility historical use |
| 11 | LOW | monitor | IQM | `maca` | — | Hormonal — limited pregnancy data |
| 12 | LOW | caution | <add to IQM> | `dim` | — | Estrogen modulator |
| 13 | LOW | monitor | IQM | `resveratrol` | — | Limited pregnancy safety data |
| 14 | LOW | monitor | IQM | `nac` | ✓ | High-dose limited data |

†Items 2, 3, 5 don't exist in `banned_recalled_ingredients.json`. Author
the banned entries first as their own atomic commits (mirror the
schema of `BANNED_EPHEDRA` / `BANNED_YOHIMBE`), then the rule entries.

---

## Diabetes gaps — 8 rules to add (17 → 25)

Existing 17 rules already cover: aloe vera, alpha lipoic acid,
berberine, bitter melon, chromium, cinnamon, fenugreek, fiber, ginseng,
gymnema, psyllium, vanadyl sulfate, niacin, tribulus, black seed oil,
stinging nettle, olive leaf.

| # | Priority | Severity | Subject DB | canonical_id | Dose? | Basis |
|---|---|---|---|---|---|---|
| 1 | MED | monitor | IQM | `magnesium` | ✓ | Modulates insulin sensitivity at high dose |
| 2 | MED | monitor | IQM | `vitamin_d` | — | Emerging evidence on insulin sensitivity |
| 3 | MED | caution | IQM | `garlic` | ✓ | High-dose additive hypoglycemia |
| 4 | MED | caution | IQM | `inositol` | — | Used for PCOS insulin resistance |
| 5 | MED | monitor | <see note> | `niacinamide` | — | Distinct metabolic profile from niacin |
| 6 | LOW | caution | <needs IQM> | `banaba` | — | Corosolic acid alpha-glucosidase claim |
| 7 | LOW | caution | botanical | `white_mulberry` | — | Alpha-glucosidase inhibitor |
| 8 | LOW | monitor | IQM | `l_carnitine` | — | Emerging insulin-sensitivity evidence |

**Niacinamide note:** check IQM for `niacinamide` form on
`vitamin_b3_niacin` parent. System A keys by parent canonical_id today.
If niacinamide-only routing is needed, use `form_scope` field on the
existing niacin rule (per PROMPT doc §"Field Rules").

**Banaba note:** not in IQM. Either skip (LOW priority) or author IQM
parent first.

---

## Lactation gaps — 11 rule extensions (4 → 15)

Existing 4: fenugreek (galactagogue note), vitamin B6 (high-dose),
sage (lactation suppression), wild yam.

**Best practice (per SOP §"One rule per ingredient"):** extend each
existing pregnancy rule with a `pregnancy_lactation` block instead of
creating a duplicate `condition_id: lactation` rule.

```jsonc
"pregnancy_lactation": {
  "lactation_severity": "avoid",
  "lactation_evidence": "probable",
  "lactation_notes": "Anthranoid laxatives transfer to milk — infant diarrhea risk."
}
```

Standalone `condition_id: lactation` rules only when the lactation
guidance differs SIGNIFICANTLY from pregnancy guidance for the same
supplement.

| # | Priority | Lactation severity | Subject | Action |
|---|---|---|---|---|
| 1 | HIGH | contraindicated | banned (BANNED_EPHEDRA) | Extend existing rule |
| 2 | HIGH | avoid | IQM `yohimbe` | Extend existing rule |
| 3 | HIGH | avoid | IQM `aloe_vera` | Extend existing rule |
| 4 | HIGH | avoid | IQM `black_cohosh` | Extend existing rule |
| 5 | HIGH | contraindicated | botanical `blue_cohosh` | Extend existing rule |
| 6 | HIGH | caution (high-dose) | IQM `vitamin_a` | Reuse existing dose threshold |
| 7 | HIGH | monitor (high-dose) | IQM `caffeine` | Reuse existing dose threshold |
| 8 | MED | avoid | IQM `cascara_sagrada` | Extend existing rule |
| 9 | MED | caution | IQM `senna` | Extend existing rule |
| 10 | MED | avoid | IQM `chasteberry` | Extend existing rule |
| 11 | MED | caution | IQM `st_johns_wort` | Extend existing rule |

---

## Authoring sequence (when greenlit)

1. Read SOP + PROMPT first.
2. For pregnancy rules 2/3/5: author the `BANNED_*` entries FIRST in
   `banned_recalled_ingredients.json` (separate atomic commits).
3. For each existing-rule extension (most lactation entries; some
   pregnancy entries like `vitamin_d`): EDIT the existing rule, don't
   create new.
4. For each new-ingredient rule: full SOP authoring flow.
5. Run `python3 scripts/api_audit/verify_interactions.py --drafts
   scripts/data/curated_interactions --check-pubmed` to verify EVERY
   cited PMID. Build fails (or surfaces warnings) on dead/wrong PMIDs.
6. Atomic commit per rule: `rules: pregnancy — licorice high-dose
   preterm-labor risk`.

---

## Out of scope

- Drug-class rule expansion (nsaids: 0, antiplatelets: 1, statins: 1
  — all per SOP coverage status). Real gaps but not pregnancy/diabetes.
- Newer drug classes (sglt2_inhibitors, glp1_agonists,
  dpp4_inhibitors). Add via RxClass API when authorizing diabetes
  drug-class extensions.
- System B pair entries — none of the original "diabetes pair"
  proposals belong in System B. They're better expressed as System A
  drug_class_rule extensions on existing rules (e.g., extend the
  niacin rule with `drug_class_id: hypoglycemics` instead of authoring
  a new System B `DSI_NIACIN_DIABETES_MEDS_RX` entry).
