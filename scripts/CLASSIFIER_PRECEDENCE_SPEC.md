# Classifier Precedence Specification (consolidation Phase 0d)

**Status:** implemented through R7b on 2026-07-16. The original measurements
below remain as historical evidence; the as-built R5/R6/R7b disposition is
recorded beside each rule.
**Scope:** `supplement_taxonomy.classify_supplement` only.
**Original baseline:** 14,193 enriched products; every original number below
was measured by recomputing taxonomy, not read from embedded artifacts. The
post-R7b verification used the current 13,143-product manifest set and exact ID
parity rather than assuming the historical count.

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

## 5. Electrolyte accessory pool — **preserve owning identity**

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

**As-built disposition:** these 17 accessory/cofactor products remain unchanged.
R5 addresses a different pool: bounded hydration/electrolyte title intent plus
at least three canonical electrolyte anchors. Accessory phrases such as "with
hydration" are explicitly excluded, so the guard above and R5 are consistent.
No new electrolyte vocabulary was added.

---

## 6. Panels: `multivitamin` vs `vitamin_mineral_combo` vs `b_complex`

> ### ✅ R4 SHIPPED 2026-07-16
> One-line bound `len(vitamin_ids) >= 1` added to `multi_panel_signal`. Measured:
> 8 products, all `multivitamin → vitamin_mineral_combo` ("Trace Minerals", "Only
> Trace Minerals", …). multivitamin 1463 → 1455; §10 empty-reason gate stays 0.
> The mineral-only panel originally landed on `vitamin_mineral_combo`; R7b now
> routes homogeneous mineral panels to `mineral_complex`. Near-miss negatives
> remain pinned: one vitamin is enough to
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

**RULE R5 — bounded intent plus panel evidence outranks a generic panel.** The
original 24-candidate pool was re-measured against current artifacts; the final
rule changes 20 primary types and emits fact-only evidence for 14 more products.
classify `multivitamin` while their title says pre-workout / hydration /
electrolyte (`309959` Preseries Lean Pre-Workout → `multivitamin`;
`295773` Bulk Strawberry Kiwi → `multivitamin`).

- **Implemented:** pre-workout/endurance/N.O. title intent requires at least two
  canonical pre-workout anchors; electrolyte/hydration intent requires at least
  three canonical electrolyte anchors. Title intent alone cannot mint a type.
- **Accessory guard:** "with hydration" / "with electrolytes" is companion
  language and cannot steal the owning amino-acid or other specialized class.
- **Measured result:** 14 `multivitamin → electrolyte`, three
  `multivitamin → pre_workout`, and three
  `general_supplement → pre_workout`; the BCAA hydration negative is unchanged.
- **Tests:** `test_classifier_specialized_panel_precedence_r5.py`.

**RULE R6 — B-complex dominance is explicit.** A mineral-containing panel is
`b_complex` only when the title is explicitly B-complex, it has at least three
distinct B vitamins, at most one non-B vitamin, at least three minerals, and B
vitamins are at least 60% of all vitamin/mineral identities. Broad panels stay
`multivitamin`; no distribution quota is used. Positive and near-miss tests live
in `test_classifier_b_complex_dominance_r6.py`.

### Vocabulary decision — ✅ R7b COMPLETE

Corpus evidence supported honest family terms: the current preview contains
143 `single_mineral → mineral_complex` and 71
`single_vitamin → vitamin_complex` changes. Both terms are defined in
`scripts/GLOSSARY.md`, declared in the canonical 22-entry
`product_type_vocab.json`, routed through the existing generic v4 module, and
synced into Flutter by the release reference-data gate. Multiple forms of one
canonical identity remain `single_*`; a bounded name-dominant multi-row product
may retain a single-family cohort but never earns the single-active fact.

---

## 7. `single_*` must mean one identity

**RULE R7.** 346 products are `single_mineral`/`single_vitamin` with **≥2
distinct** canonical identities (223 + 123). Verified: **0** are explained by
duplicate rows, so this is *not* RC2 — it is the homogeneous-combo collapse
(§7 #5). The branch contradicts itself in one breath:

    primary_type = "single_mineral"
    reasons.append(f"mineral combo: {sorted(mineral_ids)}")   # says "combo"

> ### R7 SPLIT — ✅ R7a AND R7b COMPLETE 2026-07-16
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
> **R7b — the type name (done).** Homogeneous panels of two or more distinct
> vitamin or mineral identities now use `vitamin_complex` or `mineral_complex`.
> The former strict xfail is a normal passing regression test. The canonical
> vocabulary has 22 types and the classification contract is `1.3.0`.

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

## 9. Historical implementation order (complete)

1. **R1** (RC2 dedup) — biggest win; likely resolves a large share of the 503
   empty-reason residuals on its own. Re-measure after landing.
2. **R2** (no silent residual) — then assert the §10 gate at 0.
3. **R3** (collagen precedence + empty-id protein branch).
4. **R7** (`single_*` ⇒ one identity) — unblocks Phase 1.
5. **R4/R5/R6** (panels) — completed as independent evidence decisions.
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
>
> **RC1 must also make R7a's unresolved count identity-aware** (adversarial-audit
> catch, latent today). `is_single_scorable_active` derives
> `unresolved_active_count` by counting unresolved ROWS. Today classification
> reads only mapped rows, so that count is 0 corpus-wide and the fact is correct.
> Once RC1 feeds unmapped-but-dosed rows in, a genuinely single-identity product
> whose one nutrient appears as one mapped + one unmapped row would get
> `unresolved_active_count = 1` → `is_single_scorable_active = False` → silently
> denied the single floor. The RC1 pass must resolve unmapped-row identity (or
> collapse same-nutrient mapped/unmapped pairs) before counting, or the fact
> will under-credit exactly the products RC1 is meant to recover.

### RC1 entry/exit contract for the next agent

Do not implement RC1 as a union of `ingredients_scorable` plus every dosed row.
That would create a second eligibility engine and admit known excipients. Use
one authoritative row-role resolver and expose two views from the same result:

1. `quantified_label_active_rows`: genuine label actives, including unresolved
   identities, after structural/excipient/non-quantified exclusions;
2. `score_eligible_rows`: the mapped, validated scoring subset already owned by
   `get_scoring_ingredients(strict=True)`.

Before code, produce a reason-bucket inventory of all 3,662 candidates and
manually review a stratified sample from every bucket. RED fixtures must include
Nattokinase `294772` and Horsetail `294422` as included positives, and EDTA,
Calcium Disodium EDTA, a filler/carrier, a blend header, and a nutrition rollup
as excluded negatives. The helper must return stable source paths and exclusion
codes so the SoT gate can audit the result without parsing prose.

RC1 exits only when: unresolved identities cannot earn score; mapped/unmapped
rows for the same identity cannot falsely defeat `is_single_scorable_active`;
row order remains invariant; the schema-3 full-corpus ledger is reviewed; and
every primary/score/safety delta is attributable to a named reason-code bucket.

Each rule lands as its own RED-first slice with its positive **and** near-miss
fixtures, measured on the corpus via
`scripts/audits/supptype_drift_preview.py compare --score`.

---

## 10. Adversarial audit (2026-07-16, fresh-context opus reviewer)

Ran an independent adversarial reviewer over the whole branch diff before the
Phase 2 checkpoint. Verdict: **no CRITICAL or HIGH defects; the completed work
(0a/0b/0c/0d-R1–R4/R7a/Phase 1) is safe to present for merge review.** The
reviewer empirically re-verified on the full corpus: §10 gate = 0 (both
interpretations), `is_single_scorable_active` internally consistent (0
violations), R1/R2/R3/R7a fixtures correct on real data, distribution matches
the measured predictions, 159 targeted tests green.

Findings and dispositions:

- **MEDIUM — collagen title clause deviated from spec R5** (title alone minted
  collagen over a rival identity; the in-code comment misrepresented it as
  compliant). **FIXED** in commit `fix(taxonomy): collagen title clause must not
  override a rival identity`: the clause now fires only when every non-collagen
  active is a micronutrient adjunct. 11 products collagen→general_supplement;
  near-miss test added.
- **LOW — R7a unresolved count is row-based, latent RC1 false-negative.**
  Recorded in the RC1 section above; the RC1 pass must make it identity-aware.
- **LOW — Phase 1 guard tests are wiring/grep, not behavioral.** Accepted: the
  real behavioral coverage lives in `test_v4_generic_formulation_p131.py` (ported
  to inject the taxonomy fact and run the actual scoring functions); the new
  file's value is the source guards and the helper contract.
- **LOW — strict-release version gate skipped taxonomy-less products.** A later
  independent review rejected this disposition and **fixed it**: strict mode now
  fails closed for missing taxonomy and malformed current-version contracts.
- **LOW/informational — `0.0 or fallback` confidence bug in
  `score_supplements.py`.** Fixed on a separate branch and cherry-picked into
  this branch as `4ed09667`: first-non-`None` semantics preserve truthful `0.0`
  confidence and an intentionally empty signal list.

## 11. Independent implementation review (2026-07-16)

A second review did not accept aggregate green tests as sufficient and found
four contract defects in the completed classifier work:

1. category numerators were still counted by rows while the denominator used
   distinct identities, allowing duplicate forms to manufacture dominance;
2. `secondary_type` used the first ingredient row, creating 1,442 corpus drifts
   when ingredient order was reversed;
3. 10,664 products had no decisive `classification_reason_codes` (117 of 421
   type-changed products), so the expected-change ledger was not auditable;
4. strict SoT mode accepted missing taxonomy and malformed current-version
   evidence, while the harness omitted the new identity/raw-row count fields.

All four were fixed at contract `1.1.0`. Category decisions use one deterministic category vote per
identity and emit raw `category_row_breakdown` separately; multi-ingredient
secondary type is absent unless product-name or family evidence identifies it;
every branch emits a decision code or raises; strict SoT fails closed; and the
harness is schema 3. R7b subsequently advanced the current contract to `1.3.0`.

Adversarial canaries added during this review include duplicate botanical forms,
two-botanical and two-amino panels, probiotic-plus-fiber support, collagen ties,
gelatin title corroboration, malformed/missing taxonomy contracts, and complete
row-order invariance. A full 14,193-product reversal now yields **0 drift** in
all classification facts and evidence. No canonical identity carried conflicting
categories in the reviewed corpus.

Relative to Claude tip `33ca27ca`, the corrected code changes 114 primary types
and only four score-preview surfaces. There are **0** safety/verdict/status/
suppression/blocking/coverage flips. Explicit quality review items:

- `28479` Acid Defense: `fiber_digestive` → `general_supplement`, 57.3 → 58.7;
- `29032` Raw Candida Cleanse: `fiber_digestive` → `general_supplement`,
  70.0 Acceptable → 67.5 Weak;
- `298079` and `336322` Metabolic Health: `general_supplement` →
  `herbal_botanical`, confidence `moderate` → `high`, score unchanged.

Historical verification at that checkpoint was 10,835 passed, 42 skipped, and
one strict R7b xfail. The completed R7b state is 10,896 passed, 134 skipped,
with no xfail; the former xfail is now a passing regression test.
