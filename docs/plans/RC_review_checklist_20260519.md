# RC review checklist — 2026-05-19

Sequenced review for the non-production release candidate built by
`PYTHON=python3.13 bash batch_run_all_datasets.sh --skip-release`.
Snapshot for score-delta comparison: `scripts/final_db_output.preRC_20260519T013812Z/`.

Stop on first red. Production sync only after every section passes.

---

## 1. Pipeline completion sanity

Before any audit:

- [ ] `scripts/products/reports/batch_run_summary_*.txt` — last line says `SUCCESS` for all 21 brands. Any brand in red = halt, fix, rerun. Per-brand failure logs in `scripts/products/reports/`.
- [ ] `scripts/dist/RELEASE_NOTES.md` regenerated (timestamp matches now).
- [ ] `scripts/dist/pharmaguide_core.db` and `scripts/final_db_output/pharmaguide_core.db` both exist and have similar mtimes.
- [ ] `scripts/dist/export_manifest.json` — `product_count` is in the 8,000-9,000 range (drift outside that = investigate).

---

## 2. Audit gates

Run from `scripts/`. Each must pass (GREEN / OK / 0 critical issues):

```bash
python3 db_integrity_sanity_check.py
python3 audit_raw_to_final.py
python3 audit_contract_sync.py final_db_output
python3 audit_inactive_safety.py
python3 coverage_gate.py final_db_output/pharmaguide_core.db
python3 coverage_gate_functional_roles.py final_db_output/pharmaguide_core.db
python3 enrichment_contract_validator.py products
```

Watch for:

- [ ] `audit_contract_sync.py` GREEN on every v1.5.0 / v1.6.x emit-rate field. YELLOW is recoverable; RED stops sync.
- [ ] `audit_raw_to_final.py` finding-code counts vs canary baseline (`reports/RC_raw_to_final.json` from previous run is a useful comparator).
- [ ] `audit_inactive_safety.py` — banned-in-inactives all carry safety signal; unknown-role counter ≤ baseline.
- [ ] `coverage_gate.py` — IQM coverage, functional roles coverage at or above thresholds.
- [ ] `enrichment_contract_validator.py` — no missing required fields on any blob.

---

## 3. Cert label-vs-registry audit (re-run on fresh blobs)

```bash
python3 api_audit/cert_label_registry_audit.py
```

Expected (from pre-RC analysis on shipped blobs):

| Program | Pre-RC % zero | RC expected | Notes |
|---|---:|---:|---|
| USP Verified | 75.3% | 70-80% | Slight drop if more SKUs resolve under new resolver guards |
| NSF Sport | 76.7% | 70-80% | Most claims still brand_only |
| NSF Certified | 51.1% | 45-55% | NSF/ANSI 173 has broadest brand coverage |
| Informed Choice | 44.1% | 40-50% | needs_review was 38.8% — should drop now that overrides triaged |
| Informed Sport | 50% (n=2) | TBD | Detection broader post-P0.1d — count may jump |

- [ ] Total `% real verify` across all programs ≥ 18% (was ~17% pre-RC).
- [ ] No program shows >85% `claimed_only` (would suggest regex over-firing).

---

## 4. 35-canary review

Run the canary coverage test against the fresh DB:

```bash
python3 -m pytest scripts/tests/test_v4_canary_coverage.py -v
```

All 15 coverage tests must pass. Then walk the 35 canaries manually using
`scripts/data/canary_products.json` as the spec:

### Anchor canaries (cert P0.1b/P0.1d behavior — must verify exactly)

| DSLD | Brand / Product | v3 shipped score | Expected RC outcome |
|---|---|---:|---|
| 253169 | Doctor's Best CoQ10 100mg | 65.2 | USP claimed_only (not in registry), B4a=0. Score may drop slightly (lost provisional +2). |
| 298074 | Thorne Mg Bisglycinate | 72.6 | NSF Sport + NSF/ANSI 173 both sku, B4a=12. USP stays claimed_only (mfg-only). Score ~unchanged. |
| 15906 | Thorne Basic Prenatal | 70.1 | Thorne brand in NSF Sport but this SKU NOT → brand_only, B4a=0. P0.1b anchor. |
| 274081 | GoL prenatal probiotic | 45.6 | NSF Certified needs_review → pending override → B4a=0 today. |
| 327776 | SR Omega-3 1055mg | 63.7 | IFOS matched "Lemon Flavor" but DSLD name omits flavor → needs_review → B4a=0. |
| 268690 | SR Whey | 70.3 | Informed Sport sku → B4a=8 (Informed Choice brand_only at 0). |
| 325587 | TL Creatine HMB | 85.2 | Informed Choice sku → B4a=8. High-end calibration anchor. |
| 255449 | Goli Ashwagandha gummies | 62.5 | BSCG label_asserted (no scraper yet) → B4a=2. |
| 274376 | Legion Whey+ | 68.1 | Labdoor non-B4a routing → B4a=0. supp_type=targeted + "Whey" name → sports_active B5 class. |

### B5 router canaries (post-P0.2 + Codex's generic-override priority)

| DSLD | Expected B5 class | Why |
|---|---|---|
| 173888 / 173918 | multi_or_prenatal | GoL Men's / Women's Multi — supp_type=specialty, primary_category=multivitamin, fallback fires |
| 178559 | multi_or_prenatal | Spring Valley Kids Gummy — supp_type=multivitamin direct |
| 306381 | sports_active | Nutricost PRE Pre-Workout — supp_type=multivitamin but sports keyword wins (priority 2) |
| 211334 | sports_active | GNC BCAA Gummy — BCAA keyword |
| 268690 | sports_active | SR Whey — whey keyword (regex extended to catch this) |
| 274376 | sports_active | Legion Whey+ — whey keyword |
| 74124 | generic | Nordic Prenatal DHA — primary_category=omega-3 → generic-override (NOT multi_or_prenatal despite name) |
| 184411 | generic | PE Digestive Enzymes Ultra — name has "Enzymes" → generic-override |
| 211448 | generic | Equate Glucosamine Chondroitin MSM — name keywords → generic-override |
| 1643, 178346, 274081 | probiotic | supp_type=probiotic |
| Others (single nutrient / omega / herbal / etc.) | generic | default fallback |

### Score deltas to verify

- [ ] **No canary moves > ±15 points** from its v3_shipped_score without explanation.
- [ ] **No canary changes verdict** (SAFE → CAUTION etc.) without a documented edge_case justifying it.
- [ ] **BLOCKED canaries (16012, 16072, 211448)** stay BLOCKED with score=null.
- [ ] **POOR canaries (178346, 184411)** stay POOR or recover into SAFE band (acceptable improvement).

---

## 5. Top movers (catalog-wide)

Run score-delta:

```bash
python3 api_audit/score_delta_report.py \
  --old ../scripts/final_db_output.preRC_20260519T013812Z \
  --new final_db_output \
  --output ../reports/RC_score_delta_20260519
```

(Confirm flag names match `score_delta_report.py --help` — flags may differ.)

### Expected mover patterns

**Up-movers (gain B4a from newly-verified SKUs):**
- Nature Made products that match USP registry → +8 B4a (was 0 or +5 in v3)
- Brands with Informed Sport SKUs (TL, SR, Legion, etc.) → +8 B4a
- Brand-name products in NSF Sport / NSF/ANSI 173 that weren't credited before
- Expected: ~500-700 products gain B4a, most in +2 to +8 range

**Down-movers (lose v3 cert overcredit):**
- Products with manufacturer-injected USP/Informed claims (v3 stacked +5 each) → -10 to -15 B4a
- Products with label-text USP-grade-ingredient claims (Doctor's Best, GNC, etc.) → -2 to -5 (lost P0.1d provisional)
- IFOS-claimed omega products where flavor mismatch sends to needs_review → -2 (lost provisional)
- Expected: ~1,500-2,000 products lose B4a, most in -5 to -12 range

### Watch for

- [ ] Top 50 up-movers — every one should be explainable by a registry SKU match.
- [ ] Top 50 down-movers — every one should be explainable by lost cert overcredit (mfg injection / unverified label).
- [ ] **Verdict transitions:** flag any SAFE → CAUTION (regression risk) or CAUTION → SAFE (calibration drift).
- [ ] **Average score change:** expect mean Δ in the range -2 to -5 (v3 had cert overcredit; v4 corrects downward). If mean Δ is positive at scale, investigate.
- [ ] **B5 multiplier impact:** count of products with B5 penalty change >2 points — most should be either probiotics (penalty dropped 60%) or sports/multivit (penalty rose 30-50%).

---

## 6. Spot-check the two pending_review entries

From Codex's override triage:

- DSLD 274081 GoL Dr. Formulated Probiotics Once Daily Prenatal → NSF Certified pending_review (registry has "Prenatal and Postnatal Daily Care" — likely same line but name drift)
- DSLD ??? GoL Sport Organic Plant-Based Energy + Focus Blackberry → Informed Choice pending_review

Confirm both still score B4a=0 in the RC (verifying the fail-closed contract on pending entries).

---

## 7. Go / no-go for production sync

After everything above is green:

✅ Audit gates GREEN
✅ Cert label-vs-registry audit within expected % ranges
✅ All 15 canary coverage tests pass
✅ No canary moves > ±15 without justification
✅ No unexpected verdict regressions in top-100 movers
✅ Mean score delta in -2 to -5 range
✅ Two pending_review entries still scored 0

→ **Production sync candidate.** Decision is human (Sean), not automatic. The score-delta report + the
`reports/RC_score_delta_20260519/` outputs are the artifact to review before kicking the
release (`batch_run_all_datasets.sh` without `--skip-release`).

---

## Notes

- `scripts/final_db_output.preRC_20260519T013812Z/` is the score-delta baseline. Keep it until production sync lands.
- If anything fails, the snapshot lets us roll back: `cp -a scripts/final_db_output.preRC_*/  scripts/final_db_output/`.
- Decision-log entry for this RC review should land in [SCORING_V4_PROPOSAL.md](SCORING_V4_PROPOSAL.md) §23 after sync (or after no-go).
