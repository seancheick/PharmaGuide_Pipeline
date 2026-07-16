# PharmaGuide Pipeline Maintenance Schedule

> Owner: Sean Cheick Baradji | Last verified: 2026-07-16

This schedule separates data collection, clinical review, code verification,
and release. External reports create review queues; they never become curated
clinical truth automatically.

## Operating rules

1. Verify identity and claim content, not merely identifier existence.
2. Prefer primary FDA/NIH/NLM/GSRS/ClinicalTrials sources.
3. Make one reviewed data/code change at a time with a regression test.
4. Use the shared project Python runtime for audit tools.
5. Run tests only through `scripts/test.sh`.
6. Publish only through snapshot + release owners.
7. Never let an automated reviewer edit and commit safety data unattended.

For audit commands in this document, initialize the pinned runtime once:

```bash
source scripts/python_env.sh
```

## Schedule at a glance

| Frequency | Work | Blocking standard |
|---|---|---|
| Weekly | FDA/DEA signal collection and review | Every unresolved signal is reviewed or remains explicitly open |
| Weekly | Manufacturer enforcement review | Exact/approved manufacturer identity and applicability verified |
| Monthly | CAERS refresh/review | New material signals reviewed; no automated causality claim |
| Monthly | Citation content verification | Zero ghost references in changed/released scope |
| Monthly | UNII/identity quality review | Exact GSRS identity or governed null; no forced broad match |
| Quarterly | RDA/UL and regulatory reference audit | Primary-source values, units, group, and stamp parity verified |
| Quarterly | Interaction/evidence discovery | Candidates remain non-production until content review |
| Quarterly | IQM alias/species/collision audit | No unsafe cross-identity alias introduced |
| Before release | Full strict pipeline + candidate snapshot + release gates | All intended products and artifacts pass |
| After release | Manifest, Supabase, Flutter, and retention review | Published versions/checksums align |

## Weekly

### 1. FDA and DEA regulatory signals

```bash
bash scripts/run_fda_sync.sh
```

Optional wider lookback:

```bash
bash scripts/run_fda_sync.sh --days 30
```

The command is report-only and writes a timestamped
`scripts/fda_sync_report_*.json`.

- Exit 0: no new/stale records require review.
- Exit 3: report succeeded and review is required.
- Exit 1/2: operational or argument failure.

For every candidate:

1. Open its linked primary FDA/DEA source.
2. Verify whether it is a substance, a product-specific recall, or irrelevant.
3. Verify aliases, status, recall scope, dates, US applicability, and whether a
   historical action is still active.
4. Check existing curated entries before adding anything.
5. Add a focused data regression before changing
   `banned_recalled_ingredients.json`.
6. Run the banned/recalled audit and relevant fast tests.
7. Review the diff and metadata before approval.

The collector does not modify or commit the curated database.

### 2. Manufacturer enforcement signals

Start in report/dry-run mode supported by the current tool:

```bash
"$PG_PYTHON" scripts/api_audit/fda_manufacturer_violations_sync.py --help
```

Review every proposed manufacturer match. A warning letter for a similarly
named company must not penalize an unrelated brand. Only normalized exact or
approved-family aliases may affect scoring.

Verification:

```bash
scripts/test.sh fast -k manufacturer
```

## Monthly

### 3. CAERS adverse-event signals

```bash
"$PG_PYTHON" scripts/api_audit/ingest_caers.py --help
```

Refresh only through a supported explicit option. Compare the resulting signal
distribution to the previous reviewed artifact. CAERS is surveillance evidence,
not proof of causality; unusual growth, identity collisions, and reporting-
bias changes require review before scoring data moves.

```bash
scripts/test.sh fast -k caers
```

### 4. Citation content verification

```bash
"$PG_PYTHON" scripts/api_audit/verify_all_citations_content.py
"$PG_PYTHON" scripts/api_audit/verify_backed_studies_citations.py
"$PG_PYTHON" scripts/api_audit/verify_interaction_rules_citations.py
```

Any mismatch is blocking in the affected release scope. Read the title,
abstract/full context, population, intervention, comparator, outcome, and
species. Replace a wrong PMID one claim at a time; never batch-substitute IDs.

### 5. UNII and canonical identity quality

```bash
"$PG_PYTHON" scripts/api_audit/build_unii_cache.py --help
"$PG_PYTHON" scripts/api_audit/verify_unii.py --help
"$PG_PYTHON" scripts/api_audit/audit_unii_data_quality.py --help
"$PG_PYTHON" scripts/api_audit/audit_unii_same_tier_conflicts.py --help
```

An exact GSRS synonym may be accepted after content verification. Ingredient
families, blends, tissues, or source extracts that lack one exact GSRS
substance keep a governed null instead of a misleading UNII.

```bash
scripts/test.sh fast -k unii
```

### 6. Notes and safety-language alignment

```bash
"$PG_PYTHON" scripts/api_audit/audit_notes_alignment.py --all
"$PG_PYTHON" scripts/api_audit/audit_safety_oneliner_tone.py
"$PG_PYTHON" scripts/api_audit/audit_standardname_safety_separation.py
```

Structured fields own logic; prose must explain them and must not create an
extra matcher or stronger clinical claim.

## Quarterly

### 7. RDA/AI/UL references

```bash
"$PG_PYTHON" scripts/api_audit/verify_rda_uls.py --help
"$PG_PYTHON" scripts/audit_rda_ul_reference_stamps.py --products-dir scripts/products
```

Verify value, unit, demographic group, source version, supplemental-only basis,
and form lineage. Special folate review must preserve these rules:

- adequacy uses minimum/recommended exposure
- safety uses maximum exposure
- explicit folinic DFE may support adequacy without a folic-acid UL
- bare mcg folinic/folinate/leucovorin is adequacy-unknown and not scoreable
- absent/inconsistent `%DV` does not authorize a conversion
- unknown folate lineage is reviewable, not guessed

### 8. Clinical evidence discovery

```bash
"$PG_PYTHON" scripts/api_audit/discover_clinical_evidence.py --help
"$PG_PYTHON" scripts/api_audit/verify_clinical_trials.py --help
"$PG_PYTHON" scripts/api_audit/audit_clinical_evidence_strength.py --help
```

Discovery output is a candidate queue. Before any production entry, verify NCT
and PMID content, population, dose/form, endpoints, status, enrollment, and
whether results actually support the scored claim.

### 9. Interaction sources and drug classes

```bash
"$PG_PYTHON" scripts/api_audit/mine_drug_label_interactions.py --help
"$PG_PYTHON" scripts/api_audit/verify_interactions.py --help
```

Passing mentions, excipient references, and adjacent ingredients are not
interactions. New rules require a source-backed mechanism/clinical warning,
exact supplement identity, tested drug-class references, and Flutter schema
coordination when a new user-selectable class is introduced.

### 10. IQM identity and alias health

```bash
"$PG_PYTHON" scripts/api_audit/audit_alias_accuracy.py
"$PG_PYTHON" scripts/api_audit/audit_species_alignment.py
"$PG_PYTHON" scripts/api_audit/iqm_identifier_sweep.py --help
```

Token overlap is a review hint, never safe auto-identity. Check salts, isomers,
species, source botanicals, marker compounds, brand tokens, and shared aliases.

```bash
scripts/test.sh fast -k "ingredient_quality_map or alias or identity"
```

### 11. External bioactivity and botanical enrichment

```bash
"$PG_PYTHON" scripts/api_audit/enrich_chembl_bioactivity.py --help
"$PG_PYTHON" scripts/api_audit/enrich_botanicals.py --help
"$PG_PYTHON" scripts/api_audit/verify_botanical_composition.py --help
```

These tools generate enrichment candidates. Pharmaceutical bioactivity,
animal-only PK, traditional use, and ingredient-composition claims must not be
promoted into human clinical effectiveness without appropriate evidence.

## Before every release

### 12. Code and data review

- Confirm the intended branch/commit.
- Review all clinical/reference-data diffs.
- Confirm every identifier is content-verified.
- Confirm no deprecated `/80` export field is reintroduced.
- Confirm scoring config changes have behavioral tests.
- Confirm expected per-product changes are named.

### 13. Test profiles

During development:

```bash
scripts/test.sh fast
```

Before release:

```bash
scripts/test.sh release
scripts/test.sh full
```

Do not substitute direct pytest invocations; the runner owns Python 3.13 and
the heavy-test profiles.

### 14. Pipeline and candidate snapshot

Full corpus and release:

```bash
bash batch_run_all_datasets.sh
```

If compute outputs are already current:

```bash
bash scripts/rebuild_dashboard_snapshot.sh
bash scripts/release_full.sh
```

Targeted work defaults to pipeline-only and must be reviewed before the
snapshot/release commands.

### 15. Artifact review

Required review includes:

- product count and contract quarantine count
- zero systemic contract failures
- per-product score/status/verdict/module/pillar deltas
- banned/recalled and regional applicability changes
- allergen and RDA/UL changes
- mapped/unmatched counts and classification routes
- export manifest/version/checksum consistency
- absence of deprecated `/80` fields

The scoring snapshot can be re-frozen only after this review.

### 16. Release gates

`release_full.sh` owns and orders publication gates. Do not run Supabase sync or
copy Flutter DB files manually to work around a failure. Fix the first failing
gate and rerun release; current steps auto-skip by freshness/checksum.

## After release

### 17. Verify distribution alignment

Confirm:

- release process exited zero
- Supabase sync completed or was intentionally skipped/dry-run
- Flutter bundle parity passed or Flutter was intentionally skipped
- catalog and interaction manifest versions/checksums match
- the local Flutter bundle commit is reviewed and pushed deliberately
- cleanup did not report an unresolved alignment problem

### 18. Retain evidence

Keep the timestamped batch summary, release audit records, reviewed scoring
snapshot change, and relevant external-source report. Archive or remove stale
temporary research after the batch ships so it cannot become implementation
truth.

## Incident triggers

Run the relevant maintenance work immediately, outside the cadence, when:

- FDA/DEA issues a material supplement action
- a citation or identifier is challenged
- score/verdict distribution shifts unexpectedly
- mapped coverage or product count drops
- a stage manifest reports unowned/stale files
- catalog/Flutter/Supabase checksums diverge
- a new schema/config version lands
- a clinical source changes its recommendation or labeling convention

Clinical accuracy outranks schedule. Keep unresolved evidence visible and
blocked instead of filling gaps with assumptions.
