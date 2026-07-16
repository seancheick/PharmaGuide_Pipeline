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

**RULE R1 — count distinct IDENTITIES, not label rows.**

> ### ✅ R1 SHIPPED 2026-07-16 — and it is **not** what RC2 prescribed
>
> **RC2's nominated fix does not work.** Measured against the 503 empty-reason
> products: `mark_compound_duplicate_rows` collapses **19**; counting distinct
> identities collapses **216**. The helper misses products literally named
> "Vitamin B3" / "Niacin (Vitamin B3)" (`marked=0, distinct=1`) because it
> requires a *bare* row named exactly like the canonical, and only for DRI
> canonicals — it does not cover collagen at all.
>
> **Why: it answers a different question.** The helper is a DOSE rule — "is this
> row a restatement of the same amount, so don't sum it?" — and it deliberately
> leaves genuinely additive multi-form labels alone. Niacin + niacinamide are two
> additive **doses** of one **identity**: the dose path must sum them; the
> classifier must see one ingredient. Using a dose helper to count identities is
> a category error, which is exactly why it under-reaches. The helper stays the
> owner of enrich's UL/dose path; R1 does not touch it.

- **Action:** `active_count = len({canonical identity of each quantified row})`.
  Rows with no canonical id each count separately — an unresolved row cannot be
  *proven* to be the same ingredient, so never under-count.
- **Emitted:** `distinct_active_identity_count` (the decision) and
  `quantified_active_row_count` (raw rows, diagnostic only — a gate that counts
  rows re-creates this defect). `quantified_active_count` now means identities.
- **Reason code:** `identity dedup: N label rows -> M distinct active(s)`.
- **Positive fixtures:** `252532` Choline L-Bitartrate (elemental + salt);
  `242284` "Vitamin B3" (niacin + niacinamide — the helper misses this one);
  `269490` Pure Collagen Types I+III (not a DRI canonical at all).
- **Near-miss negative:** magnesium + **zinc** stay 2 identities.
- **Invariance:** row order does not change the collapse; a decorative NP
  sibling does not resurrect the count. Both tested.

**Panel breadth stays measured in ROWS — deliberately.** `multi_panel_signal`
asks "does the label present a broad panel?", and a prenatal declaring
Folate + Folic Acid still presents one. Switching it to identities silently
re-calibrated the threshold and dropped a real prenatal into `omega_3` on its
DHA row. Lowering `>=6` to `>=5` to compensate **over-corrected**: measured, it
recovered 3 products but minted **13 bogus multivitamins**, 6 of them
beauty/hair/nails. So the gate reads `quantified_row_count >= 6`; whether that
threshold should change at all is **R4's** call, with R4's evidence. R1 must not
re-tune panel routing on the way past — and it does not: `multivitamin` is
**1463 → 1463**.

### R1 measured impact (full corpus)

| | before | after |
|---|---|---|
| `general_supplement` with **empty reasons** (§10 gate) | **503** | **287** (−216) |
| `general_supplement` total | 4264 | **3999** (−265) |
| `multivitamin` | 1463 | **1463** (untouched) |
| products reclassified | — | 296 / 14,193 (2.1%) |

Recovered into real cohorts: herbal_botanical +137, single_vitamin +76,
single_mineral +43, vitamin_mineral_combo +18, amino_acid +7, collagen +1.

**Four products move TO the residual. None is an R1 defect — R1 removed a wrong
answer and exposed the gap underneath. They are canaries for the next rules:**

| dsld | product | was | now | owner |
|---|---|---|---|---|
| `64848` | Gamma E Mixed Tocopherols (7 rows → `vitamin_e`×6 + `lignans`) | `vitamin_mineral_combo` | `general_supplement` | **R2** — the 2-identity band must name vitamin E |
| `250086` | Collagen Natural Berry | `protein_powder` (the `category='protein'` hijack) | `general_supplement` | **R3** — must reach `collagen` |
| `60843` | Immune Senescence (reishi ×2) | `immune_support` | `general_supplement` | reason says *"single ingredient, **uncategorized**: reishi"* — a category-vocabulary gap, not a branch bug |
| `297666` | Beets Detox (5 mixed identities) | `vitamin_mineral_combo` | `general_supplement` | genuinely mixed; defensible |

`74660` "Elderberry Fruit 550 mg" (`immune_support` → `herbal_botanical`, one of
18) is **not** a regression: it is a single-botanical product, and
herbal_botanical is the more honest answer than a functional category.

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

> ### ✅ R4 SHIPPED 2026-07-16
> One-line bound `len(vitamin_ids) >= 1` added to `multi_panel_signal`. Measured:
> 8 products, all `multivitamin → vitamin_mineral_combo` ("Trace Minerals", "Only
> Trace Minerals", …). multivitamin 1463 → 1455; §10 empty-reason gate stays 0.
> The mineral-only panel lands on `vitamin_mineral_combo` (the closest existing
> term) rather than a new `mineral_complex` — that refinement is the R6/R7b
> vocabulary decision below. Near-miss negatives pinned: one vitamin is enough to
> stay `multivitamin`; a real multivitamin is unaffected.

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

> ### ⏸ R5 and R6 DEFERRED 2026-07-16 — one user decision, not two agent fixes
>
> Both were re-measured post-R1/R3 (R5 = 24 products, R6 = 33) and both are
> genuinely ambiguous in a way R4 was not:
>
> **R5 (name contradicts panel).** The 24 are hydration/pre-workout products with
> a vitamin panel (`316790 "Amplified Hydration"`, `18529 "Amplified Endurance
> Booster"`). "multivitamin" is wrong for them — but where they *should* go is
> the open `pre_workout`/`electrolyte` identity question. §5 already declined to
> route to `electrolyte` on this corpus, and vetoing the panel only sends them to
> the residual, trading a wrong-specific label for a vague one with no clear win.
> Needs the `pre_workout` identity rule §2 flagged as a real (12-product) target
> — additive work, not a veto.
>
> **R6 (b-complex + ≥3 minerals).** The 33 are genuine broad panels —
> `239602 "Vitamin C Fizzy"` is 7 vitamins + 6 minerals — so "multivitamin" may
> be *correct*, or they are `vitamin_mineral_combo`. This is exactly the
> vocabulary decision below, not a branch bug.
>
> Forcing either would violate TRAP 4 (don't reclassify to reshape a
> distribution) and could make a legitimately-broad-panel product *worse*. They
> wait on the same decision as R7b.

### Vocabulary decision (required by §9, still OPEN — bundles R4-landing, R6, R7b)

> **CONSOLIDATED — this is ONE user decision.** R4's mineral-only landing, R6's
> b-complex-vs-combo, and R7b's 346 mislabeled `single_*` products all reduce to:
> *what do we call a broad mineral-only or mineral-dominant panel, and do we want
> a `mineral_complex`/`multimineral` term at all?* §13's evidence-only rule now
> **supports** a term — R7b alone is a 346-product base — but minting one is a
> cross-repo contract change (`scripts/GLOSSARY.md` first per §9, then
> `product_type_vocab.json`, which ships to Flutter), so it is the user's call,
> not the agent's. Until then every affected product has a correct *fact* and an
> imprecise *label*; nothing is mis-scored.


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
(§7 #5). The branch contradicts itself in one breath:

    primary_type = "single_mineral"
    reasons.append(f"mineral combo: {sorted(mineral_ids)}")   # says "combo"

> ### R7 SPLIT — ✅ R7a SHIPPED 2026-07-16 / ⏸ R7b DEFERRED (needs vocabulary)
>
> **R7a — the fact (done).** The *clinical* harm is `is_single=True` granting a
> single-ingredient bonus to a multi-ingredient product, and that flows from
> `is_single_scorable_active`, not the type name. Emitted now, derived from
> distinct score-eligible identities after R1 dedup, plus the plan's carve-out
> (one mapped + one unmapped active is **not** single). Also emits the two
> populations: `quantified_label_active_count` (what classification sees,
> including unresolved actives) and `scorable_active_count` (the validated
> subset). **Phase 1 is unblocked.**
>
> **Measured: 542 products** — not 346 — would take a bogus single bonus from the
> type name, because `amino_acid` counts too. The cleanest proof is
> **"BCAA 2:1:1" → `amino_acid` with 3 scorable actives** (leucine, isoleucine,
> valine): a BCAA product is three amino acids. This is exactly §8's harness
> requirement ("a multi-active amino-acid product is not reported as single from
> its type name"), now confirmed on real data.
>
> **R7b — the type name (deferred, with evidence).** Renaming the 346 needs a
> vocabulary call and neither available option is acceptable unilaterally:
> - route them to `general_supplement` → **+346 to the catch-all**, undoing the
>   −348 that R1–R3 just won, and it is less honest than `single_mineral`
>   ("Cal Mag Zinc" is a mineral product, not a general supplement);
> - mint `mineral_complex` / `multimineral` → a **cross-repo contract change**
>   (`scripts/GLOSSARY.md` first per §9, then `product_type_vocab.json`, which
>   ships to Flutter).
>
> §13's evidence-only rule now *supports* a term — 346 products is a real base,
> unlike the 8 that R4's pure-panel case would have justified. **This is a user
> decision, not an agent one.** Until then the name stays and the fact is
> correct, so no scoring is wrong; only the cohort label is imprecise.
> `test_classifier_identity_count_r1.py::test_r7_distinct_identities_must_not_yield_a_single_type`
> is a **strict xfail** holding the place — it fails loudly the moment R7b lands.

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

> ### ⛔ RC1 HELD FOR A DEDICATED, REVIEWED PASS — do NOT land it in a loop
>
> Measured 2026-07-16: **3,662 products (25.80%)** carry a dose-bearing row that
> classification currently drops — **~25× the plan §4 estimate of "~1.0%"**, and
> it touches the whole distribution (multivitamin 606, protein_powder 323,
> omega_3 143). Two things make this a stop-and-review item, not a mechanical
> fix:
>
> 1. **The estimate is off by an order of magnitude.** Either the fix is far
>    broader than scoped, or "unmapped-but-dosed active" needs a much tighter
>    definition than "any dropped dose-bearing row".
> 2. **It entangles active-vs-excipient disambiguation.** The dropped rows
>    include genuine unmapped actives (the plan's Nattokinase `294772`, Horsetail
>    `294422`) AND things that are correctly excluded — `EDTA Disodium`,
>    `Calcium Disodium EDTA` (chelators/preservatives), fillers like "Carrot
>    Powder". Pulling all of them into classification would corrupt it. Telling
>    them apart is per-row clinical judgment, exactly the "review individually"
>    work Phase 5 is built for.
>
> RC1 interacts with every branch R1–R4 and the R7a fact (all count identities
> over this row set), so it must land AFTER them (done) and be re-measured whole,
> under review. It is intentionally the last classifier change and is **not**
> appropriate for autonomous execution. The 0a prerequisite (SoT gate off the
> path literal) is already done, so nothing blocks a future reviewed pass.

Each rule lands as its own RED-first slice with its positive **and** near-miss
fixtures, measured on the corpus via
`scripts/audits/supptype_drift_preview.py compare --score`.
