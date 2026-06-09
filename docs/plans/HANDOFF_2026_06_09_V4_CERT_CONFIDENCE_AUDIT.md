# Handoff — V4 Cert Fairness, Confidence, and Score Audit

Date: 2026-06-09

Repo: `/Users/seancheick/Downloads/dsld_clean`

Audience: Claude / next agent continuing pipeline scoring work.

## Current State

Codex completed a targeted V4 scoring audit/fix focused on:

- omega verification fairness
- claim-only certification scoring
- Friend of the Sea / sustainability-cert treatment
- cross-brand certification leakage
- confidence metadata being too harsh or stale
- final catalog score sanity checks

No Flutter changes were made in this pass. Flutter repo `/Users/seancheick/PharmaGuide ai` was clean at the end of the session.

No Supabase sync or Flutter import was run. The final pipeline release command intentionally used:

```bash
bash scripts/release_full.sh --skip-supabase --skip-flutter --skip-product-images
```

## Product/Clinical Policy Decisions

### Friend of the Sea / MSC / GOED

Do not award V4 verification/trust points for these as quality certs.

Reason: Friend of the Sea / MSC / GOED are sustainability, sourcing, or trade/industry-positioning signals. They are not equivalent to SKU/product-line potency, purity, contaminant, banned-substance, or label-accuracy verification.

Recommended handling:

- show as sustainability/sourcing badges if desired
- do not count toward B4a / verification pillar
- do not imply GMP
- do not raise confidence by themselves

### IFOS / USP / NSF Certified for Sport

These remain quality/testing signals when product/SKU/product-line registry evidence matches the brand/product.

### Product-label quality cert claims

Added small provisional credit for product-label asserted quality cert claims:

- `label_asserted_product = 2 pts`
- confidence is `moderate`, not `high`
- generic unnamed `third-party tested` still does not get quality cert points

This is intentionally not full credit. It prevents unfairly penalizing products whose label clearly claims a known quality cert but the registry data is incomplete, while keeping the distinction between claimed and independently matched.

## External Sources Checked

Primary/current web sources were used because cert program definitions can change:

- Friend of the Sea omega standard: `https://friendofthesea.org/sustainable-standards-and-certifications/sustainable-omega-3-oil/`
- IFOS by Nutrasource: `https://www.nutrasource.ca/certifications-by-nutrasource/international-fish-oil-standards-ifos/`
- USP Verified: `https://www.usp.org/verification-services/verified-mark`
- NSF Certified for Sport: `https://www.nsfsport.com/our-mark.php`

## Root Causes Found

### 1. Cross-brand cert leakage

`cert_resolver.py` could accept fuzzy brand matches that were too loose. Examples of the bad pattern:

- CVS products inheriting NSF Sport SKU evidence from unrelated `LTH`
- vitafusion products inheriting unrelated `VITAL...`
- GNC Pro Performance style strings matching unrelated registry products

Fixes:

- tightened resolver brand matching to exact/token-subset logic
- added scoring-layer guards in both generic and omega trust so stale enriched artifacts cannot score mismatched certs
- added confidence guard so mismatched certs do not raise verification confidence
- reran targeted brand refresh for affected brands
- reran final full score pass for all 27 brands

Final audit:

```text
cross_brand_verified_cert_rows 0
```

### 2. Claim-only certs were too binary

Before this pass, known quality certs found only on the label were effectively all-or-nothing. That made scoring too harsh when registry data was incomplete.

Fixes:

- `label_asserted_product` scope gets small credit
- quality score copy distinguishes claimed cert from independently verified cert
- confidence says `cert_label_asserted_product` or `cert_claimed_only_no_registry_match` as appropriate

### 3. Confidence metadata lagged behind V4 module evidence

V4 modules can recover/scaffold evidence internally:

- DRI/nutrition-authority evidence floor for essential nutrients
- backed-clinical-study recovery
- collagen evidence recovery/profile
- probiotic native clinical strain evidence

But `scoring_v4/confidence.py` only looked at raw `product.evidence_data.clinical_matches`, so products could have meaningful V4 evidence score and public copy like "Some human research..." while confidence still said low/no evidence.

Fix:

- confidence now reads module evidence metadata for explicit v4-owned evidence paths
- no scored evidence still stays low
- module-owned evidence becomes moderate, not high

Final impact:

- high-score/low-confidence products dropped from 9 to 1
- remaining high-score/low-confidence product is legitimate: Garden of Life probiotic with low ingredient identity confidence, proprietary blend opacity, and missing per-strain CFU

## Files Changed

Core:

- `scripts/cert_resolver.py`
- `scripts/enrich_supplements_v3.py`
- `scripts/scoring_v4/modules/generic_trust.py`
- `scripts/scoring_v4/modules/omega_trust.py`
- `scripts/scoring_v4/confidence.py`
- `scripts/scoring_v4/quality_score.py`
- `scripts/scoring_v4/export_adapter.py`
- `scripts/build_final_db.py`

Data/config:

- `scripts/data/cert_claim_rules.json`
- `scripts/data/omega_rubric.json`
- `scripts/scoring_v4/config/quality_score.json`

Tests:

- `scripts/tests/test_build_final_db.py`
- `scripts/tests/test_cert_label_asserted_enrichment.py`
- `scripts/tests/test_cert_resolver.py`
- `scripts/tests/test_v4_confidence_p14.py`
- `scripts/tests/test_v4_gate_canary_diversity.py`
- `scripts/tests/test_v4_generic_trust_p134.py`
- `scripts/tests/test_v4_omega_trust_p164.py`
- `scripts/tests/test_v4_quality_score.py`

## Verification Already Run

Focused:

```bash
python3 -m pytest scripts/tests/test_v4_confidence_p14.py
```

Result:

```text
15 passed
```

Full V4:

```bash
python3 -m pytest scripts/tests/test_v4_*.py
```

Result:

```text
1389 passed, 11 skipped
```

Brand rescoring:

```bash
bash batch_run_all_datasets.sh --stages score --skip-release
```

Result:

```text
Passed: 27
```

Release gate:

```bash
bash scripts/release_full.sh --skip-supabase --skip-flutter --skip-product-images
```

Result:

```text
Full release pipeline completed
all strict gates passed
```

Final catalog:

```text
scripts/dist/pharmaguide_core.db
product_count = 9270
catalog checksum = 9a854f82c5dedf30c0cef922f160432b57929e68c9d8696df705ca4a56670396
```

Final score audit:

```text
products: 9270
confidence:
  moderate: 6144
  low: 3027
  high: 15
  blocked_by_safety_gate: 84
score bands:
  <60: 2016
  60-74: 4606
  75-84: 2122
  85-89: 324
  90+: 118
  none: 84
high_score_low_conf: 1
omega_85_low_conf: 0
cross_brand_verified_cert_rows: 0
```

Known single high-score/low-confidence product:

```text
DSLD 83155
Garden of Life Dr. Formulated Probiotics — Once Daily Women's
score: 85.8
confidence: low
reason: ingredient identity confidence below 80%, partial proprietary blend opacity, per-strain CFU not disclosed
```

This appears legitimate and should not be softened without a probiotic-specific identity audit.

## Important Notes for Next Agent

### Do not re-add Friend of the Sea as verification

If the user asks whether Friend of the Sea should get points, the current decision is:

- no B4a / verification points
- possible sustainability badge only

### Do not treat `cert_claimed_only_no_registry_match` as high confidence

Claim-only certs can help fairness, but they remain unresolved.

### Cross-brand cert guard is intentionally duplicated

There is protection in the resolver and in scoring modules. This is deliberate because stale enriched artifacts can still exist.

### Supabase and Flutter import were not done

If asked to ship this catalog:

1. Review git diff.
2. Commit pipeline changes.
3. Run release with Supabase/Flutter intentionally enabled, or import Flutter manually.
4. Verify Flutter app reads the new catalog.

Do not claim this catalog is live in app/Supabase yet.

## Suggested Next Deep Dives

### 1. Probiotic identity confidence

Remaining high-score/low-confidence case is probiotic identity. Investigate whether low identity confidence is accurate or caused by strain/species parsing gaps.

Start with:

```bash
python3 - <<'PY'
import json
from pathlib import Path
blob=json.loads(Path('scripts/dist/detail_blobs/83155.json').read_text())
for k in ['ingredient_quality_data','probiotic_data','v4_confidence_detail','v4_score_explanation']:
    print('\\n', k, json.dumps(blob.get(k), indent=2)[:5000])
PY
```

Questions:

- Are low-confidence strain/species rows actual ambiguity?
- Are zero-dose/non-contributory probiotic rows unfairly lowering identity?
- Does the app need to display "strong score, lower confidence due to strain identity/CFU opacity"?

### 2. `missing_conversion` warnings

Coverage gates still report many `missing_conversion` issues, especially GNC. These did not block scoring, but they are worth a focused audit.

Questions:

- Are warnings mostly non-RDA botanical/excipient units?
- Are any vitamins/minerals with UL/RDA affected?
- Are missing conversions silently lowering dose confidence or score?

Useful reports:

- `scripts/products/output_GNC_enriched/reports/coverage_report.json`
- other `scripts/products/output_*_enriched/reports/coverage_report.json`

### 3. Cert claimed-only false positives

Audit products receiving `label_asserted_product` to ensure they are true label cert claims, not marketing text.

Suggested script:

```bash
python3 - <<'PY'
import json
from pathlib import Path
for path in Path('scripts/dist/detail_blobs').glob('*.json'):
    blob=json.loads(path.read_text())
    certs=blob.get('verified_cert_programs') or []
    hits=[c for c in certs if c.get('scope') == 'label_asserted_product']
    if hits:
        print(path.stem, blob.get('brand_name') or blob.get('brandName'), blob.get('product_name') or blob.get('productName'), hits[:3])
PY
```

### 4. Score distribution by product type

The global distribution looks plausible, but do cohort-level checks:

- omega
- probiotics
- botanicals
- collagen
- multivitamin/prenatal
- sports/protein

Look for:

- high scores with weak transparency
- low scores for known premium products
- too many 90+ in a cohort
- known weak gummies above strong products

### 5. Public copy alignment

Score explanation and confidence are now more aligned, but verify UI copy:

- "Some human research..." should not pair with "low confidence because no evidence" anymore.
- claimed certs should say "label claims..." or equivalent, not "independently verified."
- sustainability badges should not read like purity/testing verification.

### 6. Commit boundary

At handoff creation time, changes were not committed. Before commit:

```bash
git diff --check
git status --short
python3 -m pytest scripts/tests/test_v4_*.py
```

`git diff --check` already passed once after these edits.

## Last Known Repo State

Pipeline repo had 19 changed files from this work before this handoff file was added.

Flutter repo was clean.

Do not revert unrelated work. The generated `scripts/dist` and `scripts/final_db_output` were refreshed by the release/snapshot process.
