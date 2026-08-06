# V4 evidence-coverage triage

This is the Phase 5, score-neutral triage of the fresh released catalog
`2026.08.06.092521`. It does not edit evidence data, scoring configuration, or
product scores.

## Fresh-catalog result

- Stage 3 contains **4,388** unique zero-Evidence rows.
- The released catalog contains **4,112** unique zero-Evidence products.
- **276** Stage-3 rows are not selected into the released catalog.
- There are no duplicate Stage-3 zero-Evidence IDs.
- Every released zero-Evidence product has both Stage-3 and detail-blob context.

The released products currently split into:

| Audit bucket | Products | Meaning |
|---|---:|---|
| `evidence_exists_identity_or_linkage_failed` | 170 | The shipped active identity exactly matches an existing, structured, score-eligible human-evidence record, but that evidence did not reach the score. This includes null-effect evidence because the production scorer deliberately applies a reduced 0.25 multiplier to it; negative-effect evidence remains zero-credit. This is a review queue, not permission to award points automatically. |
| `reference_or_mechanism_only` | 11 | The only matched record is a reference/non-clinical record and correctly earns no clinical-evidence credit. |
| `external_literature_review_required` | 3,931 | The repository alone cannot distinguish truly absent evidence from missing knowledge-base coverage. No conclusion is inferred. |

No products have yet been assigned to `evidence_truly_absent`,
`evidence_exists_knowledge_base_missing`, or
`evidence_exists_product_not_comparable` by a clinical reviewer. Those
decisions require content-verified sources in
`scripts/audits/v4_evidence_coverage_review_decisions.json`.

## Highest-priority research groups

The first external-review groups by the approved prioritization method are
L-carnitine (75 products), isoleucine/BCAA-shaped products (59), glutamine
(53), L-lysine (43), CLA (61), and ginkgo (42). The largest existing-evidence
linkage group is acetyl-L-carnitine/ALCAR (26).

The priority number is only a work-ordering aid:

```text
catalog prevalence proxy
× evidence likely exists
× identity reliability
× current Evidence is zero
× proximity to a configured tier boundary
```

Product scan telemetry is not available, so catalog prevalence is explicitly
used as a proxy. The priority number never changes a score.

## Artifacts

- `summary.json` — machine-readable counts, inputs, fingerprints, and grouped
  queues. Product rows live only in the CSV to avoid duplicating several
  megabytes in version control.
- `products.csv` — one row per released zero-Evidence product.
- `review_groups.csv` — grouped research queue ordered by priority.

## Reproduce

```bash
/Users/seancheick/.pyenv/versions/3.13.3/bin/python3 \
  scripts/audits/v4_evidence_coverage_triage.py \
  --catalog-db scripts/dist/pharmaguide_core.db \
  --scored-root scripts/products \
  --detail-blobs-dir scripts/dist/detail_blobs \
  --evidence-db scripts/data/backed_clinical_studies.json \
  --scoring-config scripts/scoring_v4/config/quality_score.json \
  --review-decisions scripts/audits/v4_evidence_coverage_review_decisions.json \
  --output-dir scripts/reports/v4_evidence_coverage_triage
```

Calibration remains frozen. Evidence records must not be added merely to raise
scores; every recovery must pass identity, form, dose, population, and
source-content review.
