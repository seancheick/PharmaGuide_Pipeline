# Evidence ledger

One entry per asserted claim: claim, exact command, output excerpt. Unproven = NOT ESTABLISHED.

## Phase 0 — ground truth

| # | Claim | Command | Output |
|---|---|---|---|
| L1 | Pipeline HEAD 391b87c5 on main, tree clean | `git status --short; git rev-parse HEAD` | `391b87c5199527f3a3b157c0fed9d2003d7eb232`, no status lines |
| L2 | origin/main is dde22dab; HEAD is 2 unpushed commits ahead (a7351548, 391b87c5) | `git ls-remote origin refs/heads/main; git log --oneline dde22dab..HEAD` | `dde22dab… refs/heads/main`; 2 lines |
| L3 | Flutter main = origin/main = d71e47f5, clean, 2 stashes | `git -C "~/PharmaGuide ai" rev-parse HEAD origin/main; git status --short; git stash list` | d71e47f5 ×2; 0 status lines; 2 stashes |
| L4 | 413 commits on main since 2026-09-24 (379 non-merge, 34 merges); last pre-window commit 7b031050 | `git rev-list --count --since=2026-09-24 main; git log --merges --since=2026-09-24 --format=%h main \| wc -l; git log -1 --before=2026-09-24 --format=%h main` | 413; 34; 7b031050 |
| L5 | Window footprint 663 files, +99,025 −90,667 | `git diff --stat 7b031050..HEAD \| tail -1` | as stated |
| L6 | No corpus artifact at HEAD: newest scored file 2026-09-22; live catalog generated 2026-09-22T20:19Z, 15,310 products; candidate 0d4d59a6 has 13,530 | `ls -lt scripts/products/*_scored/scored/*.json \| head -1; python3 … dist/export_manifest.json; sqlite3 products_core count` | Sep 22 13:52; product_count 15310; 13530 |
| L7 | Graphify built at 7b511ab1 (2026-05-30), 1,991 commits behind HEAD | `python3 -c "…graph.json built_at_commit"; git rev-list --count 7b511ab1..HEAD` | 7b511ab1; 1991 |
| L8 | Candidate verdicts SAFE 10293 / POOR 2130 / CAUTION 1034 / BLOCKED 73; live SAFE 11857 / POOR 2056 / CAUTION 1327 / BLOCKED 70 | `select verdict,count(*) from products_core group by 1` on both DBs (read-only URI) | as stated |
| L9 | Sample: 143 raw labels frozen, all present in the raw corpus (0 missing named ids) | `python3 ~/pg_quality/rr_20260928/select_sample.py` | `selected 143`, `missing from raw (named): []` |
| L10 | Pre-window worktree at 7b031050 created under ~/pg_quality/rr_20260928/wt_7b031050 | `git worktree add --detach …; git -C … rev-parse HEAD` | 7b031050db6d… |
| L11 | Fast suite at HEAD 391b87c5: 17,752 passed, 41 skipped, 0 failed (18 min, 2 workers) | `nohup bash scripts/test.sh fast > ~/pg_quality/rr_20260928/fast_head_391b87c5.log` | `17752 passed, 41 skipped, 1 warning in 1096.39s` |
| L12 | Corpus scan of BCAA ratio evidence classes (15,414 labels): notes 21 (14 instantized-named), row name 3, statements 60, product name 29, no ratio on row 154 rows/132 products | `python3` scan → `~/pg_quality/rr_20260928/bcaa_ratio_corpus_scan.json` | counts as stated |
| L13 | IQM parent ceilings: 655 parents, 373 with a ceiling, 265 with best eligible form ≤ 11; riboflavin/B6/phosphorus ceiling 10 → bio 8 scores 12/15 | `$PG_PYTHON` probe of `scoring_reference_resolver.parent_best_form_quality` over `ingredient_quality_map.json` | `parents 655 with ceiling 373`, `... <=11: 265`, `('vitamin_b2_riboflavin', 12.0)` |
| L14 | Vitamin A carotene rows by unit: iu 521, mcg 518, mcg rae 150, mg 5, np 3, mcg dfe 3, mg rae 3; g/mg rows: 206312, 299069, 213472, 200745, 200725 | corpus python scan | as stated |
| L15 | B12 IQM form bio_scores pre-window (7b031050): sublingual methyl 11, methyl 8, adenosyl 8, hydroxo 8, cyano sublingual 9, cyano 10, unspecified 9; HEAD: every named form 15, unspecified 14; commits 70a24eee, 7dbd1447, 2be4e59d have empty bodies | `git show 7b031050:scripts/data/ingredient_quality_map.json \| python3 …`; `git log -1 --format=%B <sha>` | as stated |

## Phase 0/1 — replay and probes

| # | Claim | Command | Output |
|---|---|---|---|
| L16 | HEAD snapshot: 143/143 captured, 0 errors; route/status: generic 58 scored, sports 26, multi 18 (+6 not_scored), fiber 9, omega 7, probiotic 5 (+1 suppressed), b_complex 4, generic 4 suppressed + 4 not_scored, sports 1 not_scored | `replay.py snapshot --checkout <main> … --out head.jsonl --workers 4` | `143/143 products captured`; census script |
| L17 | Pre-window snapshot (7b031050): 143/143, 0 errors | same with `--checkout ~/pg_quality/rr_20260928/wt_7b031050` | `143/143 products captured` |
| L18 | HEAD vs candidate 0d4d59a6 (115 joined): mean +0.05, median 0, 1 product with abs delta ≥ 2; HEAD vs live 09-22 (127 joined): mean −1.08, median +0.4, 82 with abs delta ≥ 2; 12 sample products scored at HEAD are absent from the candidate | join script (`head_join.json`) | as stated |
| L19 | Pre-window → HEAD: 127 scored in both; 17 unchanged, 63 up, 47 down; mean −0.93, median 0.0; 51 with abs delta ≥ 5, 11 with ≥ 10; 11 newly not_scored (all `disclosed_form_unmapped`), 6 route changes (5 fiber→generic, 1 generic→omega) | `replay.py compare …`; `delta_rows.json` | as stated |
| L20 | Evidence went >0 → 0 on 12 sample products; 7 carry `clinical_review_not_covered` at HEAD (were `evaluated_applicable`) | census over head/prewindow jsonl | list in FINDINGS RR-05 |
| L21 | Candidate blobs (13,457 scored): evidence display `not_yet_reviewed` with 0 points: 309; `applicability_unestablished` with 0: 2,740; etc. | census over `~/PharmaGuide_release_candidates/candidate_20260927_0d4d59a6/dist/detail_blobs/*.json` | table in RR-05 |
| L22 | HEAD probe (34 labels): BCAA readings match a7351548 (row-note labels read `bcaa 2:1:1` 15; instantized-named read `instantized bcaas` 15; 31148/59952 unspecified 10; BulkSupplements amino-only labels have no BCAA row); a dosed blend header also emits an `l_leucine` anchor with the header's whole mass | `row_probe.py` → `probe/row_probe_head.json` | RR-04 |
| L23 | `group_bcaa` reads the first row per canonical → child leucine wins; 270253 `bcaa_at_least_5_g_ratio_complete` | `sed -n 160,200p scripts/scoring_v4/modules/sports_helpers.py`; head.jsonl dose metadata | as stated |
| L24 | 233404 at HEAD: scored 40.4, generic, Formulation 0 (`A1_bio_score` 0.0, `botanical_profile_applied`, `weak_or_unidentified_botanical −4`) with 5 scorable rows bio 3/5/10/5/9; FiberSmart row maps to IQM `fiber` → `resistant dextrin` (aliases added 2026-09-27) | probe batch 2; IQM alias grep | RR-06 / C-6 |
| L25 | App tiers: `quality_tier` authoritative; `legacyTierForScore` fallback thresholds 95/90/80/70/55 equal the pipeline `tiers` config | `sed -n 130,150p lib/core/scoring/score_tier.dart`; `quality_score.json` tiers | equal |
| L26 | App bundles catalog 2026.09.22.201915 (schema 2.5.0, scoring 4.4.0, config checksum d70f38bb…, interaction DB 1.0.12) | `assets/db/export_manifest.json` | as stated |
| L27 | 213472 label PDF did not render in the audit browser (blank viewer, no text) | `navigate` + `get_page_text` | NOT ESTABLISHED |
| L28 | Panel routes at HEAD: 18 multi/prenatal + 4 B-complex scored products carry `evidence_result_state None` / `display_state not_yet_reviewed` with positive Evidence; pre-window the same 22 were `evaluated_applicable/assessed`; candidate blobs: 1,553 positive + not_yet_reviewed | head/prewindow census (script in RR-11) | as stated |
| L29 | Botanical probe: 233404 `is_botanical_product True`, primary "FiberSmart Resistant Starch" (`fiber`), `a1_assessment (8.71, 5)`, formulation 0.0 with `weak_or_unidentified_botanical −4`; 282638 botanical (recognized, 8.0); 243271 not botanical | `botanical_probe.py 233404,243271,282638` | `probe/botanical_probe.json` |
| L30 | Cleaner-only runs at HEAD and 7b031050: 311733 "Chloride" and 269317 "2:1:1 BCAA" land in `display_ingredients` + `label_source_rows` only, both arms | script in this session (normalizer only) | identical |
| L31 | Corpus: 369 products with a dosed top-level Chloride row; 235 with a dosed Header-group row (226 "Calories") | raw scan | as stated |
| L32 | Row conservation over 61 probed labels: exclusions are nutrition facts, merged serving columns, form-expanded blend headers; 1 combined-name probiotic row lost (297614); 3 two-deep probiotic rows re-added by the enricher (282638) | `conservation_rowlevel.json` | D.3 |
| L33 | Adequacy basis: `exposure.py` benchmark uses `high` (max); enricher adequacy `per_day_min`, UL `per_day_max`; omega/botanical minimum; GLOSSARY says minimum; TASK2 says maximum | quoted lines in RR-03 | as stated |
| L34 | Safety completeness flag read only inside gate_safety.py | `rg -n ingredient_assessment_complete scripts lib` | 8 hits, all gate_safety.py |
| L35 | 34 of 68 BLOB_TOP_LEVEL keys have no literal read in the app; audit/dashboard readers exist for most | grep loop | H |
