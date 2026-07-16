# Classifier Precedence Specification (consolidation Phase 0d)

**Status:** authored 2026-07-16, before any 0d code, as required by
`SUPP_TYPE_CONSOLIDATION_PLAN.md` §9 ("Branch reordering alone is not an
implementation specification").
**Scope:** `supplement_taxonomy.classify_supplement` only.
**Baseline:** 14,193 enriched products; every number below was measured by
recomputing the taxonomy with current code, not read from artifacts.

> ⚠️ **Measure before you fix.** The on-disk enriched artifacts predate the 0a
> evidence contract, so reading `classification_row_evidence` off them yields
> empty sets and a silently vacuous result (it reports every multivitamin as a
> "pure mineral panel"). Recompute.

---

## 1. Measured incidence — and where §7's severity ratings are wrong

| §7 | Defect | Plan rating | **Measured** | Verdict |
|---|---|---|---|---|
| #2 | 2-active band → `general_supplement` | HIGH | **749** (5.28%) | **Confirmed, worst defect.** Root cause is RC2 (§2 below) |
| — | `general_supplement` with **empty reasons** | §10 gate | **503** (3.54%) | **§10 hard gate is violated today** |
| — | `general_supplement` @ 0.0 confidence | §10 gate | **1,776** (12.5%) | Truthful only when reason-coded; today mostly not |
| #5 | multi-active called `single_*` | MED | **346** (2.44%) | **Confirmed.** 0/346 are duplicate rows — all genuinely multi-identity |
| #1 | collagen not reaching `collagen` | HIGH | **27** dominance-clear (of a 173 pool) | **Confirmed** |
| #7 | confident wrong residual (≥0.8) | MED | **187** (1.32%) | Confirmed |
| #6 | B-complex + ≥3 minerals → `multivitamin` | MED | **33** (0.23%) | Confirmed, small |
| #3 | pure mineral panel → `multivitamin` | **HIGH** | **8** (0.06%) | **Over-rated.** Gate is wrong in principle, near-theoretical in practice |
| #4 | electrolyte panel → not `electrolyte` | **MED-HIGH** | **17 candidates, ~0 defects** | **NOT A DEFECT — see §5. Do not "fix".** |

**Do not treat the pool as the defect.** 577 products carry ≥3 electrolyte
minerals and 173 carry a collagen row, but 330/400 and 68/173 respectively are
**multivitamins** where those rows are adjuncts. The plan's warnings — "three
arbitrary minerals must not automatically become an electrolyte", "an incidental
collagen row must not hijack a multivitamin" — are exactly right, and the raw
pools are the trap they warn about.

---

## 2. Root cause: RC2 feeds the 2-active black hole

The single highest-value fix. `classify_supplement` never calls
`mark_compound_duplicate_rows`, so an elemental + compound-salt pair counts as
**two** actives when it is **one** identity. That pushes genuinely
single-ingredient products into the 2-active band, which has no vocabulary and
emits `general_supplement` with **nothing at all**:

| dsld | product | actives | distinct ids | result |
|---|---|---|---|---|
| `242284` | **Vitamin B3** | 2 | **1** | `general_supplement` @ **0.0, reasons=[]** |
| `252532` | **Choline L-Bitartrate 600 mg** | 2 | **1** | `general_supplement` @ **0.0, reasons=[]** |
| `252751` | **Niacinamide (Vitamin B3) 650 mg** | 2 | **1** | `general_supplement` @ **0.0, reasons=[]** |
| `269490` | **Pure Collagen Types 1 and 3 Powder** | 2 | **1** | `general_supplement` @ **0.0, reasons=[]** |

A product named "Vitamin B3" is unclassified with zero stated reason. RC2's fix
collapses each pair to one active, which routes it into the existing and
already-correct single-active branch.

**RULE R1 — deduplicate identity before counting actives.**
- **Evidence required:** two or more included rows resolving to the same
  canonical identity (elemental/compound sibling per `mark_compound_duplicate_rows`).
- **Action:** count them as **one** active. Reuse the existing
  `supplement_type_utils.mark_compound_duplicate_rows` — do not reimplement
  (plan §9 keeps that helper alive for enrich's UL path).
- **Output/reason code:** `compound_duplicate_rows_collapsed`.
- **Positive fixture:** `252532` Choline L-Bitartrate → `single_vitamin` (choline).
- **Near-miss negative:** magnesium glycinate + **zinc** (2 distinct identities)
  must stay 2 actives and must **not** become `single_mineral`.
- **Invariance:** row order must not change the collapse; a decorative
  zero-dose sibling must not resurrect the second count.

---

## 3. The 2-active band must always speak

**RULE R2 — no silent residual.** Independent of RC2, the `active_count == 2`
band must emit a type *and* a reason code. Today it can recognise the dominant
ingredient and still refuse to name it:

    269491 "Collagen Types 1 and 3 1000 mg"  (collagen + vitamin_c)
      -> general_supplement @0.85
      reason: "name-dominant single ingredient: collagen (other=vitamin_c not named)"

The branch *identified* collagen as name-dominant and emitted
`general_supplement` anyway — it has the evidence and lacks the vocabulary.

- **Action:** when the band identifies a dominant named identity, emit that
  identity's type. When it cannot, emit `general_supplement` with an explicit
  code — never `reasons=[]`.
- **Reason codes:** `two_active_name_dominant_identity`,
  `no_quantified_active_evidence` (the §10-sanctioned zero-confidence code).
- **Positive fixture:** `269491` → `collagen`.
- **Near-miss negative:** two co-equal unrelated actives with neither named in
  the title stay `general_supplement`, reason-coded, confidence > 0 only if
  justified.
- **Gate:** after 0d, `general_supplement` with empty reasons must be **0**
  (today: 503).

---

## 4. Collagen precedence

**RULE R3 — collagen identity outranks the `protein` category.**

    19435 "Comfort"  (2x collagen rows + hyaluronic_acid)
      -> protein_powder @0.9
      reason: "protein powder signal: ids=[]"        <-- empty id list!

The protein branch (`supplement_taxonomy.py:1060`) fires on
`category_counts.get("protein", 0) > 0` at **confidence 0.9** with **no protein
identity at all** — collagen's category *is* `protein`, and collagen is not in
`_PROTEIN_IDS`, which is why the rendered id list is empty. It sits at `:1060`;
the collagen branch is at `:1085` and is never reached.

Anchors verified live 2026-07-16 (symbols authoritative, line numbers drift):
`multi_panel_signal` `:707`, b-complex bound `:803`, protein branch `:1060`,
collagen branch `:1085`, DSLD-disagreement gate `:1130`,
`mark_compound_duplicate_rows` in `supplement_type_utils.py:152` (referenced
**zero** times from `supplement_taxonomy.py` today).

- **Required identity evidence:** ≥1 row whose canonical id ∈ `_COLLAGEN_IDS`.
- **Dominance:** collagen must be ≥50% of distinct included actives, **or** the
  sole non-cofactor active. Vitamin C / hyaluronic acid are collagen cofactors
  and must not defeat it.
- **Exclusions / higher priority:** `multivitamin` wins when a broad
  vitamin/mineral panel is present — an incidental collagen row must **not**
  hijack it (68 real multivitamins carry one).
- **Output:** `collagen`, reason `collagen_dominant_identity`.
- **Positive fixtures:** `269490` (Pure Collagen Types 1&3, via R1),
  `269491` (Collagen + vitamin C), `19435` (Collagen + hyaluronic acid).
- **Near-miss negative:** a 12-active multivitamin carrying one collagen row
  stays `multivitamin`.
- **Also fix:** `protein powder signal: ids=[]` must not fire on an empty id
  set. A branch with no identity evidence has no business claiming a type.

---

## 5. Electrolyte — **decision: no change, reason-coded residual**

§7 rated this MED-HIGH. The corpus does not support a fix.

Only **17** products have ≥3 electrolyte minerals where the vitamin/mineral
panel is *entirely* electrolytes, and reading them, the current answer is
**right**:

| dsld | product | current | why current is correct |
|---|---|---|---|
| `69579` | Precision BCAA Tropical Punch | `amino_acid` | BCAAs dominate; electrolytes are adjunct |
| `228856` | Keto BHB + Carnitine | `amino_acid` | carnitine/BHB dominate |
| `175375` | Complete Vegan Protein | `general_supplement` | a protein product |
| `182869` | Diet Detox | `herbal_botanical` | botanical dominant |

None of the 17 carry an `electrolyte`/`hydration` name token — the ones that do
already classify as `electrolyte`. So §2's "`electrolyte` = 5 is an
investigation target" is **not** supported: the catalog appears to contain few
genuine hydration products, and promoting these 17 would be inventing certainty
to make a distribution look plausible (**TRAP 4**).

**Action:** none. Keep the name-token requirement. Per §9, retain a reason-coded
conservative residual rather than a speculative rule. Revisit only if a
hydration-brand ingest lands. **No new vocabulary; no GLOSSARY change.**

---

## 6. Panels: `multivitamin` vs `vitamin_mineral_combo` vs `b_complex`

**RULE R4 — `multivitamin` requires vitamins.** `multi_panel_signal`
(`supplement_taxonomy.py:707`) fires on
`len(vitamin_ids) + len(mineral_ids) >= 6` with **zero vitamins required**, so a
pure 6-mineral panel becomes a "multivitamin".

- **Action:** require `len(vitamin_ids) >= 1` for `multivitamin`; a pure mineral
  panel routes to `vitamin_mineral_combo`'s mineral-only sibling or
  `single_mineral` per active count.
- **Measured impact: 8 products.** Small, but the gate is wrong in principle and
  the fix is a one-line bound.
- **Positive fixture:** the 8 (enumerate at implementation).
- **Near-miss negative:** a real multivitamin with 5 vitamins + 1 mineral stays
  `multivitamin`.
- **Reason code:** `multi_panel_requires_vitamin_evidence`.

**RULE R5 — a name that contradicts the panel blocks the panel.** 24 products
classify `multivitamin` while their title says pre-workout / hydration /
electrolyte (`309959` Preseries Lean Pre-Workout → `multivitamin`;
`295773` Bulk Strawberry Kiwi → `multivitamin`).

- **Action:** DSLD/title intent is **corroborating, not sufficient** — it may
  **veto** a panel claim but must not by itself mint a type. A pre-workout's
  vitamin panel must not own the product.
- **Open:** whether these become `pre_workout` needs the `pre_workout` identity
  rule below; a vetoed panel falls to the residual with a code, not to a guess.
- **Reason code:** `panel_vetoed_by_product_intent`.

**RULE R6 — B-complex bound.** `non_b_minerals <= 2` (`:803`) sends
B-vitamins + ≥3 minerals to `multivitamin`. **33 products.** Decide explicitly:
`b_complex` (B-dominant) vs `vitamin_mineral_combo`. Requires the vocabulary
decision below before code.

### Vocabulary decision (required by §9, still OPEN)

Pure multi-mineral, pure multi-vitamin, and B-plus-mineral panels need an
explicit vocabulary call backed by corpus evidence. The existing vocab has
`vitamin_mineral_combo` but **no mineral-only panel term**. Options:

1. reuse `vitamin_mineral_combo` for mineral-only panels (dishonest name);
2. add `mineral_complex` — **requires a `scripts/GLOSSARY.md` entry first** and
   a `product_type_vocab.json` change that ships to Flutter;
3. route mineral-only panels to `single_mineral` when one mineral dominates,
   else the reason-coded residual.

**Recommendation: option 3** — it needs no new term and only 8 products are
affected. Do not add vocabulary for 8 products (**TRAP 4** / §13
"evidence-only vocabulary").

---

## 7. `single_*` must mean one identity

**RULE R7.** 346 products are `single_mineral`/`single_vitamin` with **≥2
distinct** canonical identities (223 + 123). Verified: **0** are explained by
duplicate rows, so this is *not* RC2 — it is the homogeneous-combo collapse
(§7 #5).

- **Action:** a homogeneous 2–5 combo of *distinct* identities is not "single".
  It keeps its family type only if one identity is dominant; otherwise it is a
  combo.
- **This is the Phase 1 driver.** `is_single_scorable_active` must derive from
  **distinct score-eligible identities after R1 dedup**, never from the type
  name — 346 products would otherwise claim a single-ingredient bonus.
- **Positive fixture:** a 3-distinct-mineral blend → not `single_mineral`,
  `is_single_scorable_active = false`.
- **Near-miss negative:** magnesium glycinate + magnesium citrate (same identity,
  R1-collapsed) **is** single.

---

## 8. Verified-correct — do not "fix"

Per §7, plus what this measurement confirms:
Paradise-style decorative probiotics (`total_cfu=0` → `single_mineral`);
empty/all-NP/0-active → `general_supplement` @0.0 **with** a code;
named-amino-with-cofactors; omega carrier-oil exception; `sole_active_is_strain`;
fiber-primary-with-accessory-probiotics; **and the 17 electrolyte candidates in
§5**.

---

## 9. Implementation order

1. **R1** (RC2 dedup) — biggest win; likely resolves a large share of the 503
   empty-reason residuals on its own. Re-measure after landing.
2. **R2** (no silent residual) — then assert the §10 gate at 0.
3. **R3** (collagen precedence + empty-id protein branch).
4. **R7** (`single_*` ⇒ one identity) — unblocks Phase 1.
5. **R4/R5/R6** (panels) — smallest impact; R6 needs the vocabulary call.
6. **RC1** (two row populations) — sequence last among classifier changes: it
   changes the row population itself, so land it when the counts above are
   stable, and re-measure everything. The 0a contract already carries
   `unresolved_quantified_active_count` for it.

Each rule lands as its own RED-first slice with its positive **and** near-miss
fixtures, measured on the corpus via
`scripts/audits/supptype_drift_preview.py compare --score`.
