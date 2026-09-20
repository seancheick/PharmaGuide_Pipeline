# PharmaGuide — pharmacist review packet (Phase-3 source resolution complete)

Date: 2026-09-20 · For: licensed pharmacist release authority
Scope: **four decisions only.** Every source/data question in the Phase-3 packet has
already been resolved from live NIH DSLD, the archived DSLD label images, DSLD sibling
label records, and manufacturer panels — see
`SOURCE_RESOLUTION_RECEIPTS_20260920.json` and `SOURCE_RECONCILIATION_20260920.md`.
Nothing below asks you to re-do source research.

---

## 1. EDTA policy — 16 standalone orally marketed products

**Decision required:** consumer-facing disposition.

| | |
|---|---|
| Products | 252358, 252426, 253331, 253335, 253336, 253339, 253350, 253357, 311259, 311260, 311261, 311262, 312449, 312450, 312451, 312452 (all BulkSupplements) |
| Source state (resolved) | Manufacturer label carries oral dietary-supplement directions — 500 mg EDTA disodium daily, or 500 mg calcium disodium EDTA. **Disodium EDTA and calcium disodium EDTA are distinct identities in the model.** |
| Engineering position | These are deliberately consumer-ingested standalone products, not trace formulation excipients. Representation and evidence package are complete; nothing further is pending on the data side. |
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
`digestive_enzymes` identity — unsupported evidence transfer. Consequences, all measured on
the frozen 15,412-record replay: 28 score changes, all within the discrete-enzyme /
probiotic-evidence family and all traced to that single removal; 0 Safety-field changes;
0 quarantine exits; 1 new quarantine (`269360` Serrapeptase — now source-resolved in §source
resolution, the printed panel declares 40,000 SPU). Discrete enzyme identities now sit in a
neutral/unrated Formulation state because no per-enzyme evidence applies.

**Decision:** accept neutral/unrated for discrete enzyme identities, or define the rating
treatment you want (for example an explicit "not individually rated" presentation).

---

## 4. Provitamin-A upper-limit applicability

**Decision required:** how a **provitamin-A (beta-carotene) RAE** amount should be treated
against PharmaGuide's retinol upper limit.

**Source state (resolved).** The Bulk 1340 family (228823, 243799, 243808, 243812, 243815)
declares Vitamin A with no Supplement Facts parenthetical; the label's own vitamin/mineral
blend names **`Natural beta-Carotene`** as the vitamin A source, and the row's %DV
(334 % for 3,000 mcg; 380 % for 3,417 mcg) resolves on the ~900 mcg RAE basis. The
form-provenance question is therefore closed — engineering will record the form.

**What remains yours:** the UL applicability rule (the retinol UL is a preformed-vitamin-A
limit; beta-carotene is not associated with the same toxicity, while high-dose beta-carotene
supplementation carries its own caution in smokers) and whether a beta-carotene-specific
caution should surface to consumers.

---

## 5. Release sign-off

Sign or withhold according to PharmaGuide's release governance, using the closed Phase-3
engineering record:

- static source-of-truth audit: **0 findings**
- fast tier: **15,835 passed / 0 failed / 196 skipped**
- frozen corpus replay: **15,412 records per arm, 0 crashes**, every score delta classified
- source resolution: **11 corrections authored, 9 records confirmed correct, 3 explicitly withheld, 3 intentional non-scoreable — 0 unresolved source/data items**

**Outstanding after your decisions:** one reviewed dose-safety reconciliation change (folate
parent/child serving-basis handling), fully specified with fixtures — an engineering change,
not a clinical judgement.
