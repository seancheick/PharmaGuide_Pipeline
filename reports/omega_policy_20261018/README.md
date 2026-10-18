# Bounded omega policy — October 18, 2026

Sean approved this bounded scoring-policy batch before implementation. No corpus run, release, catalog rebuild, baseline recapture or Flutter publication is included.

## Owner check and policy

Owner: `scripts/scoring_v4/modules/omega_dose.py::score_dose` and `quality_score.json` own Dose points; `evidence_resolver::resolve_omega_evidence_standard` owns the shared purpose/population decision and Evidence applicability; `normalization::omega_molecular_form_disclosures` owns form language for enrichment and scoring. Evidence: source-of-truth matrix, callers, public scored-artifact regressions and frozen label replay. Will NOT create another scorer, purpose resolver, normalizer, public field/status, clinical registry or personal-dose recommendation.

- Ordinary-adult explicit EPA+DHA: proportional reference contribution to 250 mg per declared Facts-panel serving, capped at 20 Dose points. Fish/krill/algal carrier mass does not count.
- Prenatal: proportional additional-DHA reference contribution to 200 mg, capped at 20. EPA never substitutes, including when clinical Evidence remains held. A shared prenatal determination selects this comparison; it does not clear population/identity/preparation Evidence holds.
- Explicit triglyceride-lowering purpose retains its existing clinical dose curve. The 2 g and 4 g references remain in the rubric. These are not the ordinary-adult nutritional plateau or a claim of prescription equivalence.
- Child-only targetGroups and Junior/Jr titles use the existing child-population hold. Adult-plus-child targets remain eligible under their existing adult context; userGroups Daily Value metadata does not select purpose. Eleven previously missed child labels lose inappropriate adult Evidence credit.
- Marketing purpose alone cannot prove treatment-evidence applicability. The clinical `triglyceride_strong` record is retained; a label claim keeps the ordinary reviewed Evidence score and sources.
- Form parsing requires affirmative molecular-form wording. Blood-lipid prose and MCT carrier descriptions cannot award form credit. Genuine labels and mixed-form ambiguity are preserved at the shared owner.

## Source basis

[EFSA 2010 dietary reference opinion](https://www.efsa.europa.eu/en/efsajournal/pub/1461) supports adult total-intake AI 250 mg EPA+DHA and an additional 100–200 mg DHA during pregnancy/lactation. PharmaGuide's choice of the upper additional-DHA reference and proportional quality credit is an approved scoring convention, not a universal supplement prescription or a complete pregnancy nutrition assessment. [NIH ODS](https://ods.od.nih.gov/factsheets/Omega3FattyAcids-HealthProfessional/) distinguishes these from established US nutrient DRIs; do not label this an EPA/DHA RDA or attribute a 200–300 mg supplement target to ACOG.

[EU authorized health-claim conditions](https://eur-lex.europa.eu/legal-content/EN/TXT/?uri=consolidation%3A2012R0432%2F20240819_0110010) and [AHA 2019 prescription omega-3 guidance](https://professional.heart.org/en/science-news/omega-3-fatty-acids-for-the-management-of-hypertriglyceridemia/top-things-to-know) distinguish the 2 g triglyceride-maintenance claim and 4 g prescription treatment context. Higher intake earns no extra ordinary nutritional Dose credit. Existing maximum-daily exposure warnings and UL logic remain separate.

## Validation design

Baseline main `60d8ea0e2`; runtime candidate `1521486e4e406dc43aa2c0ba70a4958106fa3076`, engine 4.7.0/config 1.28.0. Three atomic behavioral commits: Dose policy, Evidence boundary, shared form parsing.

All 715 stored omega inputs were selected from the prior 15,426-input census and their 58 source-file hashes rechecked. Both clean committed checkouts score the same frozen 715 inputs. Separately, 1,712 frozen raw labels cover all raw-available omega products, every triglyceride-containing raw label in the frozen source inventory, and the existing 174-label regression controls. The one submitted omega without a DSLD raw counterpart is measured in the stored cohort; this is not a claim that its photo/raw submission was reprocessed.

The raw replay captures Clean → Enrich → Score → detail blob. Every record hash is verified, every differing JSON path is enumerated, and numerical/safety/status/route changes are reviewed by shared cause. Whole-catalog regeneration remains explicitly outside this task. Earlier captures invalidated by review corrections are excluded from acceptance.

Fail-first checks cover tiny/sub-reference doses, the adult plateau, prenatal EPA substitution, prenatal Evidence holds, serving-frequency independence, marketing-derived Evidence, real-label form inflation, repeated triglyceride prose, real plus MCT disclosure, coordinated mixed forms, and carrier term variants. Existing valid title assertions remain intact. The focused Dose/Evidence slice passes 97 tests; final parser/affected consumer slice passes 37 tests; broader owner discovery ran 344 cases (two obsolete config pins corrected with focused passing tests). Counts overlap and are not a unique total.

Independent fresh-context review reproduced and closed the repeated-token form issue and validated the prenatal-held correction. Its corpus string census covers 297 distinct triglyceride-containing surfaces. The final audit additionally caught 11 child-only target labels receiving adult reference credit; four failing public-boundary cases reproduced the gap, then all nine population/format controls passed. The shared purpose-owner fix preserves five real mixed adult/child controls and both Baby & Me prenatal holds. The two CI failures were an obsolete 70 mg fixture (now 5.6 Dose, total 46.5; other fields unchanged) and genuine Natural Triglycerides title detection. Their owner/consumer slice passes 130 tests. Final measured-delta signoff and combined CI/local results are recorded below.

## Results

| Measurement | Final result |
|---|---|
| Frozen raw capture | 1,712/1,712, exit 0, source unchanged |
| Clean records | 0 changed |
| Enriched records | 9 explained molecular-form corrections |
| Raw score movers | 418 unique: 403 Dose, 11 Evidence, 8 Formulation, 6 Transparency (overlap) |
| Stored omega score movers | 415/715: 404 Dose, 11 Evidence; 300 numerically unchanged |
| Safety/status/route and source-identity checks | No differences in compared safety, scoring status, route, identity readiness, completeness or daily-exposure payloads |
| Assessment completion | 4 explained partial → complete changes; no points awarded |
| Raw canaries | 33/33 unchanged |
| Local rung | 546 passed, 24 declared optional live-service skips; skip guard passed |
| Whole-fast CI | [39159536620](https://github.com/seancheick/PharmaGuide_Pipeline/actions/runs/39159536620): 21,108 passed, 192 declared skips; all four skip guards passed |

All scored/blob hashes change because engine/config provenance changes; this does not mean all scores change. The 11 child Evidence corrections are 206027, 213952, 223218, 224620, 26332, 28632, 313920, 337869, 65759, 65775 and 74246. They retain their prior held-context Dose curve rather than receiving the adult nutritional plateau.

The four assessment corrections are 220343, 220662, 223405 and 223408. Named combined EPA+DHA identity is complete before and after; individual amounts are NP. Child applicability replaces the old amount-derived Evidence reason. Zero Evidence, unchanged Dose, complete identity readiness and the `omega_aggregate_epa_dha_evidence` soft-missing flag are retained. The existing assessment owner explicitly considers an applicability-unestablished conclusion complete. No genuine identity hold is cleared.

The real-label claim-injection probe 11609 originally gained Formulation 9.3 → 12.2, Evidence 10.4 → 20 and Transparency 6.8 → 10.9 from one marketing sentence. The candidate leaves all three identical. Dose changes 20 → 6 when that sentence selects the existing clinical-purpose curve, as intended; quality-score and safety statuses remain unchanged.

The canonical all-path comparison and both raw/stored shadow checks pass: zero taxonomy, verdict, safety or coverage shifts. Independent final signoff is recorded in review_summary.md. Earlier rejected/interrupted captures and failed CI runs are excluded from acceptance. This receipt covers source integration, not a regenerated catalog or a release.

## Reproduction and retained evidence

Durable local root: `/Users/seancheick/pg_quality/omega_policy_20261018/`. Retain `frozen_raw`, raw `manifest.json`, frozen stored input batch, `baseline.jsonl` and `accepted.jsonl` with record directories and metadata, stored before/after scores, all-path comparison, shadow checks, final analysis and test logs. Compact source/input manifests and receipts are committed here. Full captures are too large for the source repository.

Use `scripts/audits/quality_redesign/replay.py snapshot --full --blob` with the recorded checkout, frozen input root and manifest; `compare --all-paths` enumerates differences. Use `audit_source_of_truth_contract.py shadow-diff` on extracted raw scored records and stored scored batches. Use `scripts/test.sh fast` with the named changed/consumer files, `scripts/test.sh local`, and `freeze_contract_snapshots.py --check --raw-root <frozen-raw>`.

The capture retains the existing harness worker `PYTHONHASHSEED=0` for baseline comparability. Dropping that pin and recapturing the harness baseline remains the explicitly deferred post-corpus follow-up; this receipt does not claim to close it.

The existing 33 raw canaries pass without fixture changes. Production outputs, stage manifests and harness baseline are not restamped. The next corpus run remains an explicit operator step after integration; fresh artifact/release validation is still required before shipping.
