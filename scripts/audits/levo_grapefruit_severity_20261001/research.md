# Levothyroxine and grapefruit pair severities — evidence packet, 2026-10-01

Status: **decided and applied 2026-10-01.** Sean chose Option A (caution everywhere) and approved every
factual correction. Ledger row D27 (resolved), follow-up Q50. Branch `claude/levo-grapefruit-severity`.

## Result per entry

| Entry | Before | After |
|---|---|---|
| `DSI_LEVOTHYROXINE_CALCIUM` | Major (avoid); "by up to 40%" | Moderate (caution); "by about 20–25% when taken together" |
| `DSI_LEVOTHYROXINE_IRON` | Major (avoid) | Moderate (caution) |
| `DSI_LEVOTHYROXINE_MAGNESIUM` | cites ODS fact sheet; "2–4 hours" | cites PMID 41221788, 10193669, generic label; "at least 4 hours"; mechanism states the trial result |
| `DSI_STATINS_GRAPEFRUIT` | "avoid" for all three statins | per-statin text from the three labels; label URLs added; severity unchanged |
| `RULE_IQM_CALCIUM` thyroid sub-rule | probable | established; SYNTHROID label, PMID 21595516, 11716045 added |
| `RULE_IQM_IRON_HYPERTENSION` thyroid sub-rule | probable | established; SYNTHROID label added |
| `RULE_IQM_MAGNESIUM_HYPERTENSION` thyroid sub-rule | cites ODS fact sheet | cites PMID 41221788, 10193669, generic label; mechanism states the trial result |
| `timing_thyroid_med_magnesium_separate` | established; fda_label; blocker citation_not_content_verified | probable; clinical_study; blocker interval_not_supported_by_cited_source; still unpublished |

Checks: `data_batch.py check --expect` on all three files (exactly these 8 entries changed);
`verify_interaction_rules_citations.py --strict --changed-since origin/main` PASS;
`verify_all_citations_content.py --changed-since origin/main` 7/7 match; rebuilt interaction DB
(staged, not imported) shows calcium, iron and magnesium + levothyroxine as caution in both the
curated pairs and the profile rules. Release note: the staged DB still reads version 1.0.12 with new
content, so the release must bump `scripts/config/interaction_db_release.json`.

## Found while applying (queued as Q50, not changed)

The ODS magnesium fact sheet (read in full 2026-10-01) mentions neither lithium nor thyroid. In
`RULE_IQM_MAGNESIUM_HYPERTENSION`, the `lithium` sub-rule (monitor, established, "separate by 2
hours") cites only that page, and the `kidney_disease` sub-rule (avoid, established) cites a
kidney.org page about potassium. Both need their own source review. The website's "magnesium +
lithium" example was withdrawn for this reason.

Found while checking website examples against production data: the same supplement–drug pair
carries different severities or instructions in different owners. Owners involved:

- `scripts/data/ingredient_interaction_rules.json` (schema 6.3.0): profile rules, shipped in detail
  blobs and evaluated on the phone when the profile has the drug class. Product page / For You card.
- `scripts/data/curated_interactions/curated_interactions_v1.json` (schema 1.2.5): drug-specific
  pairs, normalized by `api_audit/verify_interactions.py::SEVERITY_MAP` (Major→avoid,
  Moderate→caution) into the interaction DB. Stack screen and pre-add check.
- `scripts/data/timing_rules.json` (schema 6.0.0): timing guidance card.

App severity labels (`app:lib/core/constants/severity.dart`): avoid = "Not recommended",
caution = "Use caution". Bundled DB checked: `app:assets/db/interaction_db.sqlite`, version 1.0.12.

## E1. Calcium + levothyroxine — severity conflict

| Owner | Entry | Severity | Evidence | Instruction |
|---|---|---|---|---|
| Profile rules | `RULE_IQM_CALCIUM` / drug `thyroid_medications` | caution | probable | separate ≥ 4 h |
| Curated pairs | `DSI_LEVOTHYROXINE_CALCIUM` | Major → **avoid** (bundled DB: avoid) | established | ≥ 4 h |
| Timing | `timing_calcium_iron_thyroid_separate` | — | established | ≥ 4 h |
| Depletion | `DEP_LEVOTHYROXINE_CALCIUM` (verified) | moderate | — | ≥ 4 h |

**What a user sees today:** a levothyroxine user with a calcium product in the stack gets
"Not recommended" from the stack check and "Use caution" on the product page, for the same pair.

**Sources read:**
- SYNTHROID label, DailyMed setid 1e11ad30-1041-4520-10b0-8f9d30d30fcc, effective 2024-02-20.
  Section 7 table: phosphate binders "(e.g., calcium carbonate, ferrous sulfate ...) may bind to
  levothyroxine. Administer SYNTHROID at least 4 hours apart from these agents." Section 17: iron
  and calcium supplements and antacids decrease absorption; do not take within 4 hours.
  The label manages the interaction by separation; it does not say to avoid the combination.
- Zamfirescu 2011, Thyroid, PMID 21595516 (cited by the curated pair): 500 mg elemental calcium
  as carbonate, citrate or acetate reduced levothyroxine absorption "by about 20%-25%"; calls the
  effect "modest"; advises separation.
- Singh 2001, Thyroid, PMID 11716045 (cited by the timing rule): 2.0 g calcium as carbonate cut
  peak absorption from 83.7% to 57.9% of the dose (about 31% relative) in 7 volunteers.

**Defect besides severity:** the curated mechanism says absorption falls "by up to 40%"; its own
source says 20–25%, and the strongest dose read (2 g) gives about 31%. Unsupported number.

**Proposal (needs Sean):** one severity in both files.
- **Option A (recommended): caution, evidence established, everywhere.** Matches the label's
  management (separate, don't stop), keeps the pair actionable ("Review"), and the timing card
  still gives the 4-hour instruction. Effect: the stack check moves from "Not recommended" to
  "Use caution" for levothyroxine + calcium. Calcium is in most multivitamins, so "Not
  recommended" for the most common thyroid combination is also an alert-fatigue risk.
- Option B: avoid everywhere. The product page would then also show "Not recommended" and the
  For You card hides goal fit for every calcium-containing product a thyroid user scans.
- Either way: replace "up to 40%" with the sourced figures.

## E2. Iron + levothyroxine — same conflict (sibling, same decision)

| Owner | Entry | Severity | Evidence |
|---|---|---|---|
| Profile rules | `RULE_IQM_IRON_HYPERTENSION` / drug `thyroid_medications` | caution | probable |
| Curated pairs | `DSI_LEVOTHYROXINE_IRON` | Major → **avoid** (bundled DB: avoid) | established |
| Timing | `timing_thyroid_med_iron_separate` | — | established, ≥ 4 h |

Sources: same SYNTHROID label (ferrous sulfate, at least 4 hours apart); Campbell 1992, Ann
Intern Med, PMID 1443969, "Ferrous sulfate reduces thyroxine efficacy in patients with
hypothyroidism" (cited by the profile rule). Proposal: follow the E1 decision.

Other levothyroxine pairs checked and left alone: zinc (rule caution, no curated pair), soy and
coffee (curated caution, no conflict).

## E3. Magnesium + levothyroxine — wrong citation and interval mismatch (severities agree)

| Owner | Entry | Severity | Evidence | Instruction | Cited source |
|---|---|---|---|---|---|
| Profile rules | `RULE_IQM_MAGNESIUM_HYPERTENSION` / drug `thyroid_medications` | caution | probable | ≥ 4 h | ODS magnesium fact sheet |
| Curated pairs | `DSI_LEVOTHYROXINE_MAGNESIUM` | Moderate → caution | moderate | "2–4 hours" | ODS magnesium fact sheet |
| Timing | `timing_thyroid_med_magnesium_separate` | — | **established** | ≥ 4 h | generic levothyroxine label |

**Sources read:**
- NIH ODS Magnesium Health Professional fact sheet (updated January 6, 2026), read in full in the
  browser: **no mention of levothyroxine or thyroid.** Both entries cite a page that does not
  support the claim.
- Generic levothyroxine label, DailyMed setid 3e77de84-6f59-40ac-a1a4-7bfe30387823 (effective
  2023-12-12): names only "Antacids (e.g., aluminum & magnesium hydroxides, simethicone)" via
  reduced gastric acidity; "Monitor patients appropriately". Magnesium supplements are not named.
- Attinger 2025 (ThyroMag), Clin Transl Sci, PMID 41221788: randomized crossover, 15 healthy
  adults. Magnesium aspartate cut thyroxine AUC by 12% (significant); magnesium citrate by 7%
  (not significant). Authors: "magnesium reduces the absorption of levothyroxine"; smaller than
  other divalent cations; advise separation. States magnesium had never been studied before.
- Mersebach 1999, Pharmacol Toxicol, PMID 10193669: two case reports (aluminum hydroxide;
  magnesium oxide laxative) with raised TSH that fell after stopping; in vitro adsorption with
  Al/Mg hydroxide and Mg carbonate, none with magnesium oxide alone.

**Proposal (factual corrections, no severity change):**
- Re-cite both entries to PMID 41221788 and PMID 10193669 (plus the label for antacids); drop the
  ODS fact sheet as the source for this sub-rule.
- One interval everywhere: at least 4 hours (the label's interval for magnesium-containing
  antacids; the rule and timing data already say 4 hours). Curated "2–4 hours" has no source.
- Evidence level: probable in all three (one small PK trial plus case reports). The timing rule's
  "established" over-grades the evidence for magnesium supplements.

## E4. Grapefruit + statins — text overstates one label, citation argues the opposite

`DSI_STATINS_GRAPEFRUIT`: Moderate → caution, class-level (statins), `alert_style`
`food_advisory_note`. The app shows it only as a calm "Good to know" note to statin users
(`app:lib/services/stack/stack_interaction_checker.dart::checkMedicationFoodAdvisories`; display
severity informational, `app:lib/core/models/interaction_result.dart`). No profile rule or timing
rule exists for grapefruit.

**Sources read (DailyMed SPL, current):**
- Simvastatin, setid 3f6fad0b-0278-433f-86db-761b673a5803 (effective 2026-08-31): "Avoid
  grapefruit juice when taking simvastatin."
- Atorvastatin, setid d57720ab-9f83-4da9-a57f-0d55e00a605c (effective 2026-09-22): "Avoid intake
  of large quantities of grapefruit juice, more than 1.2 liters daily."
- Lovastatin, setid 9438d8a0-ca5b-4676-aab9-d0241ccff6c9 (effective 2026-07-23): grapefruit juice
  increases myopathy risk; double-strength juice raised lovastatin AUC 15-fold, one glass of
  single-strength about 1.9-fold.
- Lee 2016, Am J Med, PMID 26299317 (the entry's only PMID): concludes "Grapefruit juice should not
  be contraindicated in people taking statins." It supports a moderate tier, not the "avoid" text.

**Defects:** `management` says avoid with simvastatin, atorvastatin and lovastatin, and
`practical_guidance` says skip grapefruit on all three; the atorvastatin label limits this to more
than 1.2 L a day. The bundled DB also stores `agent2_canonical_id` empty for this row
(`identity.interaction.normalize_interaction_canonical_id` drops "grapefruit"); harmless for the
medication-triggered food note, recorded only.

**Proposal (no severity change):** keep class-level Moderate shown as a food note; rewrite
`management`, `note_body` and `practical_guidance` per statin from the three labels; add the three
label URLs as sources and keep PMID 26299317 as context. Website: show grapefruit as what the app
shows (a food note), or quote the simvastatin label for the simvastatin example.

## Gate gap found on the way

`scripts/api_audit/verify_interaction_rules_citations.py` content-checks only PubMed, PMC and
Bookshelf ids (`PMID_RE`, `BOOK_RE`). ODS fact-sheet and DailyMed URLs are never read, so the
magnesium–thyroid citation passed the strict gate while not mentioning levothyroxine. Belongs to
roadmap item 1.8 (citation governance).

## After Sean decides

One `/data-fix` batch: failing regressions first (one severity per pair across owners, no
"up to 40%", magnesium sources and interval, grapefruit per-statin text), explicit patch per entry
through `scripts/data_batch.py`, `check --expect` on the changed keys, strict citation gate and the
content verifier on the changed entries, `scripts/test.sh fast` on the interaction tests, rebuild
the interaction DB and confirm the bundled rows. No catalog score moves (the scorer does not read
interaction alerts); warning severities do move for thyroid users if Option A or B is chosen.

## Q50 resolved (Sean, 2026-10-01)

**Magnesium x lithium (`RULE_IQM_MAGNESIUM_HYPERTENSION` / drug `lithium`): retired.** It said
monitor, established, "may reduce lithium absorption; separate by 2 hours", citing only the ODS
magnesium fact sheet, which never mentions lithium. Sources read:
- Lithium carbonate label, DailyMed setid b839ff4b-f62d-41ab-a823-550a756d58ec (Hikma, effective
  2026-08-16): drug interactions list diuretics, NSAIDs, RAS antagonists, metronidazole,
  serotonergic agents and antipsychotics; no magnesium or antacid interaction.
- Goode 1984, Clin Pharm, PMID 6428800: crossover in 6 healthy men, lithium carbonate 300 mg with
  30 mL Al/Mg hydroxide antacid: no significant change in peak, AUC or absorption rate;
  "Concurrent administration of antacids and lithium carbonate should not affect lithium blood
  concentrations."
No source supports the warning and the only human study contradicts it, so Sean chose removal. Do
not re-add without new evidence. The separate psyllium x lithium rule (PMID 1968148) is unaffected.

**Magnesium x kidney disease (`condition` `kidney_disease`, avoid, established): re-sourced.** It
cited https://www.kidney.org/atoz/content/potassium (a potassium page). The current ODS magnesium
sheet (updated 2026-01-06) no longer discusses renal toxicity in its text. New sources, each read:
- Aal-Hamad 2023, Medicina, PMID 37512002 (review): hypermagnesemia is potentially
  life-threatening (respiratory, cardiovascular, neuromuscular complications, coma); high-risk
  groups include impaired renal function and magnesium-containing medicines or supplements.
- Mori 2019, J Clin Biochem Nutr, PMID 31379418: 193 daily magnesium-oxide users; CKD grade 4 and
  dose were associated with hypermagnesemia (supports the action's eGFR < 30).
- Wakai 2019, J Pharm Health Care Sci, PMID 30805197: 320 patients on magnesium oxide; eGFR
  <= 55.4 mL/min, BUN, dose >= 1,650 mg/day and duration were independent risk factors.
- Milk of Magnesia Drug Facts, DailyMed setid 8cc7d52a-8fc3-4f52-9e50-b15613ddd02c (effective
  2026-09-14): "Ask a doctor before use if you have kidney disease".
Mechanism text rewritten to these sources (the unsourced "cardiac arrest" and "doses safe in
healthy adults" phrases removed). Severity, action and alert copy unchanged.

## Codex source audit: calcium and iron label repair (2026-10-01)

Owner: `scripts/data/curated_interactions/curated_interactions_v1.json` — evidence: both
`DSI_LEVOTHYROXINE_CALCIUM` and `DSI_LEVOTHYROXINE_IRON` retained the old label URL;
the profile counterparts already cite the real SYNTHROID label. Will NOT create: another
interaction owner or review registry.

Per-entry live review: the calcium and iron pair source URL with DailyMed setid
`f4f5a9a4-b4db-4b9f-908b-c0be9a0e5b20` redirects to `/dailymed/index.cfm`, with title
`DailyMed` and no prescribing information. Each URL is replaced with
`1e11ad30-1041-4520-10b0-8f9d30d30fcc`, independently read live: SYNTHROID levothyroxine,
updated February 20, 2024, names calcium carbonate and ferrous sulfate and specifies at
least 4-hour separation. Calcium PMID 21595516 and iron PMID 20554088 independently
match their interventions and absorption/thyroid-control outcomes. Severity, timing,
mechanism, identity, clinical confidence and numerical policy are unchanged for both entries.

Regression first: 2 failing checks reproduced the dead source. Exact `data_batch check`
since `e7445fd2`: only `interactions/DSI_LEVOTHYROXINE_CALCIUM` and
`interactions/DSI_LEVOTHYROXINE_IRON`, 2 changed entries / 0 problems.
Changed-entry citation content verifier: 2/2 MATCH, no mismatch. Focused reconciliation,
magnesium and data-batch modules: 226 passed. Full fast checkpoint is deferred to the
integrator's combined candidate; this atomic source-only fix does not claim release validation.
No DB rebuild, upload or publication was performed.

## Codex source audit: grapefruit timing scope (2026-10-01)

Owner: `curated_interactions_v1.json::DSI_STATINS_GRAPEFRUIT.management` — evidence:
its newly generalized timing sentence and live PMID 26299317 abstract. Will NOT create:
a new food-advisory owner or numeric policy.

The unqualified sentence that taking "the statin" hours apart reduces the interaction
incorrectly includes atorvastatin. The cited abstract distinguishes simvastatin/lovastatin
(about 260% increase together versus about 90% when 12 hours apart) from atorvastatin
(about 80% increase whenever taken). Replaced only that sentence with statin-specific
scope and an explicit reminder that spacing does not replace the label precautions.
Independently read all three live DailyMed labels: simvastatin avoid grapefruit juice;
atorvastatin advises avoiding quantities above 1.2 liters/day; lovastatin describes raised
exposure and myopathy risk. Severity and food-note behavior remain unchanged.

Regression first: 1 failing scoped-timing check. Exact `data_batch check` since
`1ee2a0c6`: only `interactions/DSI_STATINS_GRAPEFRUIT`, 1 changed entry / 0 problems.
Changed-entry content verifier: PMID 26299317 MATCH. Focused reconciliation, magnesium
and data-batch modules: 227 passed. Integrator owns the final combined full-fast checkpoint;
this receipt does not claim catalog or interaction-DB publication.
