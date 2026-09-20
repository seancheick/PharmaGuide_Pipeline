# PharmaGuide — pharmacist review packet (Phase-3 engineering closed, source corrections applied)

Date: 2026-09-20 · For: licensed pharmacist release authority
Landed as: **`de260e3c`** on `origin/main` — the Phase-3 source-resolution runtime tip. Later documentation-only commits (including this packet's own revision) do not change that runtime tip.
Supersedes: `PHARMACIST_PACKET_PHASE3_SOURCE_RESOLVED_20260920.md` (source-resolution draft)

**Scope: three policy decisions and one release signature.** Every source/data
question raised by the Phase-3 clinical review has been resolved from the live
NIH DSLD API, the archived DSLD label image, DSLD sibling label records, and
manufacturer panels — and the accepted corrections are now **applied in the
pipeline**, not merely documented. Nothing below asks you to re-do source
research.

---

## Status — what is already closed

| Domain | Status |
|---|---|
| Source verification | **COMPLETE** |
| Source corrections | **APPLIED** — 9 product corrections applied and replay-verified, plus one structural folate parent-total contract change. 10 products carry a correction receipt; the tenth (`201420`) is reported and **not** applied (see §4). |
| Engineering validation | **COMPLETE** (fast tier 0 failed; static source-of-truth audit 0 findings) |
| Frozen-corpus replay | **COMPLETE** (15,414 records per arm, 0 crashes, every delta classified) |
| EDTA product policy | **PHARMACIST DECISION** |
| Botanical standardization-marker policy | **PHARMACIST DECISION** |
| Discrete-enzyme formulation policy | **PHARMACIST DECISION** |
| Release authority | **PHARMACIST SIGN-OFF** |

Source/data unresolved: **0** · Engineering unresolved: **0** ·
Products with an undefined disposition: **0**

### Resolved — do not research these

| Item | Resolution |
|---|---|
| E2 vitamin-unit defects (223563, 223572, 328644) | `mg RAE` → `mcg RAE`, unit only. `mg RAE` occurs on no other vitamin-A row in the 15,414-record corpus, and each row's own printed %DV resolves on the microgram basis. |
| E2 rows 231334 / 231335 / 263865 | Printed denomination is DFE-shaped but cannot be separated from RAE at audit grade. **Explicitly withheld** — no plausibility rewrite. |
| B12 raw-material tubs (254396, 254413) | Printed panel carries no Supplement Facts dose and states "not intended for individual use … qualified professionals only"; classified `intentional_non_scoreable` (`professional_formulation_material`). |
| 12300 Fem-Mend proprietary blend | The label declares only a 860 mg blend total with zero component doses. Withheld on source insufficiency — no dose may be invented. |
| Vitamin-A form on Bulk 1340 (228823, 243799, 243808, 243812, 243815) | The printed vitamin/mineral blend names `Natural beta-Carotene` as the only vitamin A source. Form provenance is **recorded**; the row is not defaulted to retinol. |
| Vitamin-A UL applicability for provitamin A | **Not a clinical judgement.** NIH ODS states the Vitamin A UL applies to preformed vitamin A only, and beta-carotene and other provitamin-A carotenoids have no established UL. PharmaGuide already implements this (`beta_carotene_no_established_ul`; `ul_applies: false` on the supplemental beta-carotene conversion rule), and regression coverage pins it. |
| Folate source duplication (243808, 246430, 201420) | Source structure established (two printed preparation-basis columns; parent DFE total with its own included form breakdown). The parent-total contract was completed so a declared DFE total is not charged again for the breakdown it includes, and sibling rows that are one printed form split across serving bases collapse instead of summing. `243808` and `246430` are reconciled by that contract and confirmed on the frozen replay. `201420` is **not** reconciled: its declared-total row is mis-named `Folic Acid`, byte-identical to its own child row, so a row-wise rename cannot be scoped without renaming the child too. It stays with the dose-safety/folate owner as a pre-existing residual. **Not a question for you.** |
| Serrapeptase 269360 | The printed Supplement Facts panel declares `Serrapeptase Enzyme 40,000 SPU` with its own SPU footnote; the amount is restored from the panel, never from the product name. |
| DSLD nesting / label-version questions | Resolved against sibling label records and the archived label images; no open item remains. |

---

## 1. EDTA policy — 16 standalone orally marketed products

**Decision required:** consumer-facing disposition.

| | |
|---|---|
| Products | 252358, 252426, 253331, 253335, 253336, 253339, 253350, 253357, 311259, 311260, 311261, 311262, 312449, 312450, 312451, 312452 (all BulkSupplements) |
| Source state (resolved) | The manufacturer label carries oral dietary-supplement directions — 500 mg EDTA disodium daily, or 500 mg calcium disodium EDTA. **Disodium EDTA and calcium disodium EDTA are distinct identities in the model.** |
| Engineering position | These are deliberately consumer-ingested standalone products, not trace formulation excipients. Their source and identity representation is complete; nothing is pending on the data side. |
| FDA context on record | No FDA-approved OTC chelation product exists; approved chelation therapy is prescription-supervised; inappropriate chelation has caused dehydration, kidney failure and death. |

**Choose one:**

- (a) hidden / BLOCKED with no consumer exposure;
- (b) BLOCKED with a Safety card and no quality score;
- (c) scored with a written rationale.

---

## 2. Standardization-marker clinical policy — five products

**Decision required:** confirm that a declared standardization constituent listed beneath a
separately dosed *standardized botanical extract* is disclosure/provenance rather than an
independent additive dose.

| DSLD | Product | Parent (dose-bearing) | Constituents re-roled as markers |
|---|---|---|---|
| 216948 | PM Phytogen Complex | standardized Pueraria mirifica root extract 80 mg | Miroestrol 16 mcg, Isoflavonoids 16 mcg |
| 232718 | Longevity A.I. | Ashwagandha extract (std. 3% withaferin A) | Withaferin A 12 mg |
| 216776 | Herbal Complex | six `standardized <botanical> extract` parents @ 100 mg | Triterpene Glycosides 0.5 mg, Alkaloids 3 mg, Polyphenols 15/30 mg, Echinacosides 4 mg, Glycyrrhizin 1 mg, Oleuropein 6 mg |
| 44423 | Deglycyrrhized Licorice Root Extract | standardized Deglycyrrhized Licorice extract 250 mg | Glycyrrhizin 3 mg (<1%) |
| 77254 | Male Multiple | standardized American Ginseng 25 mg + standardized Korean Ginseng 25 mg | Ginsenosides 2.5 mg (10%), 2 mg (8%) |

**Established facts (not questions):** every child amount is exactly the parent's own stated
percentage (3 % of 100 mg = 3 mg; <1 % of 250 mg ≈ 3 mg; 10 % of 25 mg = 2.5 mg). The
dose-bearing identity (the extract) stays scoreable. All declared quantities are preserved as
disclosure. **Safety is byte-identical before and after** — 232718 keeps
`B0_WATCHLIST_SUBSTANCE`, 216948 keeps `B0_HIGH_RISK_SUBSTANCE`. The three non-target
products (216776, 44423, 77254) moved +1.9 / +1.9 / +0.2 points, tier-preserving.

**Decision:** approve this modelling, or define the alternative treatment of a declared
standardization constituent.

---

## 3. Discrete-enzyme formulation policy

**Decision required:** approve the resulting Formulation state, or specify the required
alternative.

**Background (closed engineering).** The Phase-3 remediation removed a mechanism by which
discrete enzyme identities inherited the evidence credit of a collapsed multi-enzyme
`digestive_enzymes` identity — unsupported evidence transfer. Consequences, measured on the
frozen 15,412-record replay: 28 score changes, all within the discrete-enzyme /
probiotic-evidence family and all traced to that single removal; 0 Safety-field changes;
0 quarantine exits; 1 new quarantine (`269360` Serrapeptase — its printed panel declares
40,000 SPU, which the source-resolution phase has now restored; the product's residual
quarantine is an **identity-scoring** condition, not a missing dose). Discrete enzyme identities now sit in a neutral/unrated
Formulation state because no per-enzyme evidence applies.

**Decision:** accept neutral/unrated for discrete enzyme identities, or define the rating
treatment you want (for example an explicit "not individually rated" presentation).

---

## 4. Release sign-off

Sign or withhold according to PharmaGuide's release governance, using the closed Phase-3
engineering record:

- static source-of-truth audit: **0 findings** (`scoring-static`, re-run at `de260e3c`)
- fast tier at the landed tip: **15,868 passed / 0 failed / 198 skipped** (clean detached
  worktree at the landed commit; `FAST_TIER_CLOSURE_20260920.md` is the earlier
  closure-phase record)
- frozen corpus replay: **15,414 row-level / 15,412 scored records per arm, 0 crashes**, every
  changed product mapped to a reviewer-signed source correction — 0 score changes,
  9 conclusion changes, 8 quarantine exits, 0 new quarantine entries, 2 Safety changes,
  **0 changes outside the intended family**
- source resolution, receipt-ledger basis (defined in `COUNT_BASIS_20260920.md`):
  **11 correction items, 6 records confirmed correct, 3 explicitly withheld,
  3 intentional non-scoreable** — 23 receipt items, **0 unresolved source/data questions**
- of the 10 products carrying a correction receipt, **9 are applied and replay-verified**
  and **1 (`201420`) is reported and not applied** (reason above). That is an engineering
  follow-up against a pre-existing defect, **not** a decision for you.

**Outstanding after your decisions:** nothing engineering-resolvable. The only items that
remain are the three decisions above and this signature.

---

## Reviewer complete? A quick check

- Did anything in this packet ask you to look up a label, a unit, a dose or a DSLD id? **No.**
- Does any item below remain marked TBD, stale or `needs_info`? **No.** One receipt is named
  as **not applied** (`201420`, §4) — it is a pre-existing folate residual with an assigned
  engineering owner, not an open question and not a decision for you.
- **You may approve with specified products held.** Approval does not require every product to
  score. `231334` / `231335` / `263865` have no authorable printed denomination and stay
  explicitly withheld; `201420` stays a documented residual. The release can be signed with
  those held.
- Is the provitamin-A UL question on your list? **No** — it is a deterministic rule
  application with an NIH citation, already implemented and test-pinned.

---

## Reconciliation of the counts in this packet

The three records that summarise this phase previously carried different totals because the
denominators were never stated: a receipt *item* (one row per product-and-issue), a
corrected *product*, and a *measured replay delta* are three different things. The canonical
definitions and the enumeration behind every number here are in
`COUNT_BASIS_20260920.md`; verified by
`python3 scripts/audits/quarantine_triage_20260919/source_resolution_20260920/count_reconciliation_20260920.py`.

| Basis | Corrections | Confirmed correct | Withheld | Non-scoreable | Total |
|---|---:|---:|---:|---:|---:|
| Receipt items (ledger) | **11** | **6** | **3** | **3** | **23** |
| Distinct products | **10** (9 applied + 1 not applied) | 6 | 3 | 3 | — |
| Measured on the frozen replay | 9 products changed | — | — | — | — |

The item and product totals differ only because `243808` carries two separate receipts — a
vitamin-A form correction (§C) and a folate structural correction (§D). No unexplained
discrepancy remains, and the one receipt that is **not** applied (`201420`) is named rather
than folded into a favourable total.
