# Rubric proxy removal — quality_score 1.2.0 (2026-09-14)

Pass 1 of the rubric semantic cleanup. Each removed rule rewarded or punished a proxy
instead of answering its pillar's question. Nothing here adds new scoring logic.

## What changed

| Rule removed | Where | Why |
|---|---|---|
| Blanket gummy format penalties: prenatal `gummy_formulation_limit` (−3) + `dosage_form_suitability` (+2 for non-gummies), fiber `fiber_gummy_delivery_penalty` (−3) + gummy practicality (0.5 vs 2), immune `B1_immune_gummy_or_syrup` (−2) + loss of `immune_daily_clean_design` (2), melatonin `B1_sleep_melatonin_gummy` (−2) | multi_prenatal_formulation, fiber_digestive_formulation, immune_support, sleep_support, generic_formulation, penalty_registry | Dosage form alone was charged 2–3 times. Real consequences (sugar via `B1_dietary_sugar`, low doses in Dose) still score. |
| Organic (+1), Non-GMO Project (+0.5), natural source (+1) | `formulation_magnitudes` a5a/a5d/a5e = 0.0 | Consumer attributes, not clinical formulation quality. Detection + metadata kept. |
| Marine sustainability cert (+2) | `omega_rubric.json` formulation.sustainability_cert.score = 0 | Same: attribute. Program stays in `sustainability_cert_program` metadata. |
| Omega EPA:DHA 1:3–3:1 ratio (+5 Dose) | omega_dose.py, omega_rubric.json, schema | No clinical optimum ratio for a generic omega product. Per-serving EPA/DHA stay in metadata. |
| Astaxanthin 85 / CoQ10 93 public caps | generic.py, config | The six pillars must explain the public number. |

References (divisors) moved only where a component's maximum was removed, keeping the
prior slack below the raw ceiling: prenatal_multi formulation 23→21, omega formulation
23→21, omega dose 23→18. Config versions: quality_score `1.2.0-rubric-proxy-removal`,
omega `1.1.0-rubric-proxy-removal`; both pinned in `config_fingerprint_history.json`.

## Deliberately NOT changed

- **Omega 250 mg evidence floor.** It is established EPA/DHA evidence gated at the EFSA
  250 mg/day threshold — dose applicability, the same rule probiotics use. Removing it
  would have zeroed evidence for ~620 of 719 omega products whose generic evidence score is
  ~5.5.
- **Probiotic CFU-size, strain-count and identity-count points.** Deferred until strain
  curation and dose applicability settle (owner's reviewer, 2026-09-14). Note: the 8-point
  identity component is itself a count ladder (1 exact strain = 3, five = 8).
- Generic dose (≥25% RDA), verification ordering, transparency claim bonuses: later passes.

## Known side effects to review

- Outside the immune-support adapter (up to +12, so 30 stays reachable there), the richest
  generic formulation reaches 29. The A5 excellence cap could only collect 2 (standardization
  1 + synergy 1), so 1.2.1 lowers that cap from 4 to 2; no score changes.
- Build-final-db bonus chips for Non-GMO (A5d) disappear because the component is 0. The
  attribute facts themselves are unchanged in enrichment.

## How it was verified (no full-corpus run)

Frozen, stratified packets replace corpus re-scoring. The committed id files are the
source of truth (`packet_ids.json` = pass 1, 111 products; `packet_ids_pass2.json` =
generic dose + verification, 79 products); nothing is re-selected.

```bash
A=scripts/audits/rubric_proxy_removal_2026_09_14
python3 $A/select_packet.py --packet pass1              # extract frozen ids from enriched outputs (~1 min)
git worktree add --detach /tmp/base <commit-before>     # frozen baseline code
python3 $A/score_packet.py /tmp/base before.json --packet pass1   # ~10 s; records input sha256 + ids + commit
python3 $A/score_packet.py . after.json --packet pass1
python3 $A/diff_packet.py before.json after.json --packet pass1 --allow-group <groups>   # or --no-moves
```

`diff_packet.py` exits 1 when a product outside the allowed groups moves (score, status,
tier, cap or any pillar), and refuses snapshots scored from different inputs or id lists,
unknown group names, or any `control_` group in `--allow-group`.

| Step | Allowed groups | Result |
|---|---|---|
| Harness check (baseline vs unedited main) | none | 0 moves |
| Gummy penalties | prenatal_gummy, prenatal_control, fiber_gummy, melatonin_gummy, immune_gummy | gummies +2.7 to +3.5 mean; prenatal controls −0.51 (lost the free non-gummy credit); 0 unexpected |
| Organic / Non-GMO / natural | generic_organic, generic_non_gmo, generic_natural | −0.5 to −1.3; 6 gummy-group products also moved and each carried A5a/A5d/A5e points in its breakdown |
| Omega ratio + sustainability + caps | omega_ratio_in_range, omega_ratio_none, generic_capped | in-range ratio −0.67 mean, no-ratio +2.88 mean; astaxanthin 85.0→86.8 and CoQ10 93.0→93.9 = their pillar sums; 0 unexpected |

Archetype fixtures refreshed (6 cases, every leaf change explained above); every failure
fixture still scores below its ideal pair. Invariance tests added: dosage form alone,
organic/natural/Non-GMO, sustainability and EPA:DHA ratio leave the score unchanged; no
generic single active carries a hidden public cap.

Tests: `scripts/test.sh fast` — 15,090 passed, 73 skipped, 0 failed (before the final import/docstring touch-up, which re-ran generic/omega/archetype/quality_score: 1,031 passed).

## Pass 2a — verification evidence tiers (quality_score 1.3.0)

Problem (reproduced exactly on all 15,106 stored 2026-09-13 scores): an unknown product took
`max(6, signals) + soft`, a product with a real signal took `signals + soft`. So a batch-COA
product scored 2.5 (7.5 with soft points), a label cert claim 3-7, and an unknown product with
reputation + region points 9. Every enricher GMP flag is a label-text regex match
(`enrich_supplements_v3.py`), yet `gmp_level=certified` counted as certified GMP for ~3,150
products.

Rule: score = neutral 6 + points, bounded by the best evidence tier present:

| Tier | What qualifies | Bound |
|---|---|---|
| unknown | nothing | 6 |
| claim_or_brand | label-asserted cert, own purity testing, manufacturer reputation (<= 2) | <= 8 |
| manufacturing | GMP inferred from a verified product cert or audited manufacturer evidence, verified brand/facility cert | <= 10 |
| product | registry sku/product_line cert or batch COA | >= 11, up to 15 |

Label-text GMP / FDA-registration wording and manufacturing region no longer score.
Analytic projection (formula reproduces 15,106/15,106 stored scores first): catalog mean
8.21 -> 8.24; unknown 6.09 -> 6.00; claim/brand 8.66 -> 8.00; manufacturing 9.34 -> 9.86;
product 13.04 -> 14.64.

Pass-2 packet vs bfac09a1 (`--packet pass2`): batch COA +5.0, registry cert +0.67, label cert
claim +1.0, brand/facility cert -1.0, label GMP only -0.67, unknown with reputation -1.0; all
dose groups and every control group unmoved; 0 unexpected. Ten archetype ideal fixtures move
verification 11 -> 15 (each has a verified registry cert); only total, tier and the
verification pillar changed; every ideal still outscores its failure pair.
