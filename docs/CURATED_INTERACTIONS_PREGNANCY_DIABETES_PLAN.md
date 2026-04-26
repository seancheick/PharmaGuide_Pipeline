# Pregnancy + Diabetes Coverage Expansion Plan

**Document version:** 2.0.0
**Date:** 2026-04-26
**Supersedes:** v1.0.0 (which conflated the two interaction systems)
**Owner:** next Claude Code session, with Sean reviewing
**Status:** plan only — no edits applied; ready for sequential authoring

---

## TL;DR for the next session

PharmaGuide has **two distinct interaction systems**, each with its own
data file, evaluation timing, and Flutter consumer. v1 of this doc put
all pregnancy/diabetes work into one system; v2 corrects that.

**System A — Per-product condition flags (already does most of this work):**
- File: `scripts/data/ingredient_interaction_rules.json` (129 rules today)
- Evaluated at **pipeline time** during enrichment.
- Tagged by `condition_id` (pregnancy, diabetes, lactation, …) and
  `drug_class_id` (statins, anticoagulants, …). **Dose-aware.**
- Flutter renders via `interaction_warnings.dart`, filtered against the
  user's profile conditions.
- **Pregnancy: 28 rules. Diabetes: 17 rules. Lactation: 4 rules.**

**System B — Pairwise stack interactions (already shipping, smaller scope):**
- File: `scripts/data/curated_interactions/curated_interactions_v1.json` (109 entries)
- Evaluated at **Flutter runtime** when a stack changes.
- Drug↔supp / supp↔supp / drug↔drug pairs.
- Flutter queries via `stack_interaction_checker.dart` against the
  bundled `interaction_db.sqlite`.

**Your work this session:** add 33 System A rules (most coverage gain) +
5 System B pair-interaction entries. **Stop after these.** Sean explicitly
gated further expansion on "until we're solid enough."

---

## Architecture refresher (read first)

```
                       INGREDIENT RULES SYSTEM (A)              CURATED PAIRS SYSTEM (B)
                       ────────────────────────                 ────────────────────────
INPUT              ingredient_interaction_rules.json       curated_interactions_v1.json
QUESTION           "Risky for users WITH this condition?"  "Risky if user takes BOTH X and Y?"
EVALUATED          pipeline time (during enrichment)       Flutter runtime (on stack change)
DOSE-AWARE?        Yes — dose_thresholds with comparator   Light — dose_threshold_text string
PROFILE-AWARE?     Yes — condition_id, drug_class_id       No — uses stack composition
LIVES IN           detail_blob.warnings[]                  interaction_db.sqlite (bundled)
FLUTTER CONSUMER   interaction_warnings.dart               stack_interaction_checker.dart
TODAY              129 rules                                109 pairs
```

If you're unsure which system a new entry belongs to, ask:

- **"Does this require the user to be taking SOMETHING SPECIFIC ELSE?"**
  YES → System B (pair). NO → System A (per-condition).

- **"Is this just 'don't take this if you have X condition'?"** → System A.

- **"Is this 'don't take A and B together'?"** → System B.

- **"Is this dose-dependent?"** → either system; System A has a richer
  threshold model.

---

# Section 1 — System A expansion (33 rules)

## 1A — How to author one System A rule

Open `scripts/data/ingredient_interaction_rules.json`. Each rule looks
like this (real example — Vitamin A + pregnancy with dose threshold):

```jsonc
{
  "id": "RULE_IQM_VITAMIN_A_PREGNANCY_DOSE",
  "subject_ref": {
    "db": "ingredient_quality_map",       // or "banned_recalled_ingredients" or "botanical_ingredients"
    "canonical_id": "vitamin_a"
  },
  "condition_rules": [
    {
      "condition_id": "pregnancy",
      "severity": "caution",               // base severity if no dose threshold met
      "evidence_level": "established",
      "mechanism": "<one paragraph, layperson-readable>",
      "action": "<actionable advice>",
      "sources": ["https://ods.od.nih.gov/...", "https://pubmed.ncbi.nlm.nih.gov/..."]
    }
  ],
  "drug_class_rules": [],                  // (empty if not relevant)
  "dose_thresholds": [
    {
      "scope": "condition",
      "target_id": "pregnancy",
      "comparator": ">=",
      "value": 10000,
      "unit": "IU",
      "basis": "per_day",                  // quantity × max_servings_per_day
      "severity_if_met": "contraindicated",
      "severity_if_not_met": "caution"
    }
  ],
  "pregnancy_lactation": {                 // optional dedicated block
    "lactation_severity": "caution",
    "notes": "<lactation-specific notes>"
  },
  "last_reviewed": "2026-MM-DD",
  "review_owner": "claude-code-session"
}
```

**Three rule types — pick the right `subject_ref.db`:**

| Rule subject | Use db | Example |
|---|---|---|
| Active supplement ingredient (vitamin, mineral, AA, common botanical) | `ingredient_quality_map` | `vitamin_a`, `licorice`, `curcumin` |
| Already-banned/recalled substance | `banned_recalled_ingredients` | `BANNED_EPHEDRA`, `BANNED_PENNYROYAL` |
| Botanical not modeled in IQM but tracked | `botanical_ingredients` | `ginkgo_biloba_leaf`, `blue_cohosh`, `white_mulberry` |

**Authoring checklist (per rule):**

1. **Pick a rule from the queues below** (priority HIGH → LOW)
2. **Verify the subject exists** in the right data file:
   ```bash
   python3 -c "
   import json
   d = json.load(open('scripts/data/<DB_FILE>.json'))
   print('FOUND' if '<canonical_id>' in (d if isinstance(d, dict) else {x.get('id') for x in d.get('botanical_ingredients', [])}) else 'NOT FOUND')"
   ```
3. **If subject is missing** (new IQM parent / new banned entry / new
   botanical): author the parent FIRST as its own atomic commit. Then
   come back for the interaction rule. Never co-mingle.
4. **Find the canonical citation** via PubMed; content-verify the abstract
   matches your claim.
5. **Author mechanism + action** — layperson-readable, actionable, match
   the cited evidence.
6. **Add `dose_thresholds`** if the literature gives you a numeric line.
   Skip if the evidence is qualitative ("avoid in pregnancy").
7. **Add `pregnancy_lactation` block** when both apply — saves a duplicate
   `condition_id: lactation` rule.
8. **Run the pipeline locally** to verify the rule fires:
   ```bash
   bash batch_run_all_datasets.sh --skip-release --targets <a-test-brand>
   ```
   Then inspect a known affected product's enriched JSON for the new
   alert.
9. **Run pytest** — schema tests should pass.
   ```bash
   python3 -m pytest scripts/tests/test_ingredient_quality_map_schema.py \
                     scripts/tests/test_pipeline_regressions.py
   ```
10. **Commit atomically**:
    ```bash
    git commit -m "rules: pregnancy — licorice high-dose preterm-labor risk"
    ```

## 1B — Pregnancy queue (14 rules)

**Existing coverage today (28 rules — DON'T duplicate):** 7-keto DHEA,
ephedra, yohimbe, banned CBD, blue cohosh, mugwort, rue, butterbur,
feverfew, aloe vera, black cohosh, dong quai, goldenseal, st johns wort,
wild yam, chasteberry, senna, cascara sagrada, chinese skullcap, black
seed oil, ginseng, vitamin A, vitamin C, vitamin E, iodine, caffeine,
5-HTP.

**Proposed additions (would expand 28 → 42):**

| # | Priority | Severity | Subject DB | canonical_id | Dose? | Basis |
|---|---|---|---|---|---|---|
| 1 | **HIGH** | avoid | IQM | `licorice` | ✓ | Strandberg 2002 (PMID:12450910) — high-dose causes preterm labor + cortisol disruption |
| 2 | **HIGH** | contraindicated | banned_recalled† | `pennyroyal` | — | Classic abortifacient + hepatotoxin; FDA enforcement history |
| 3 | **HIGH** | contraindicated | banned_recalled† | `tansy` | — | Thujone toxicity; abortifacient |
| 4 | **HIGH** | avoid | IQM | `saw_palmetto` | — | Anti-androgen — fetal genitourinary development concern |
| 5 | **HIGH** | contraindicated | banned_recalled† | `bitter_orange` | — | Synephrine = ephedra-class sympathomimetic |
| 6 | MED | caution | IQM | `curcumin` | ✓ | High-dose uterine stimulation (PMID:30744609) |
| 7 | MED | caution | botanical | `ginkgo_biloba_leaf` | ✓ | Bleeding risk near term + theoretical placental effect |
| 8 | MED | monitor | IQM | `vitamin_d` | ✓ | High-dose hypercalcemia — fetal cardiac concerns at >4000IU/day |
| 9 | MED | avoid | IQM | `dhea` | — | Hormonal — covered as 7-keto BANNED but plain DHEA gap |
| 10 | MED | caution | IQM | `holy_basil` | — | Anti-fertility historical use — pregnancy gap |
| 11 | LOW | monitor | IQM | `maca` | — | Hormonal effects — limited pregnancy data |
| 12 | LOW | caution | <add to IQM> | `dim` | — | Estrogen modulator — limited safety data |
| 13 | LOW | monitor | IQM | `resveratrol` | — | Limited pregnancy safety data |
| 14 | LOW | monitor | IQM | `nac` | ✓ | High-dose limited pregnancy data |

†**banned_recalled_ingredients prerequisite:** items 2/3/5 don't exist in
that DB today. Author them as banned entries FIRST (separate commit), then
add the interaction rule. The pattern matches existing
`BANNED_EPHEDRA` / `BANNED_YOHIMBE` entries — see those for the schema.

## 1C — Diabetes queue (8 rules)

**Existing coverage today (17 rules — DON'T duplicate):** aloe vera,
alpha lipoic acid, berberine, bitter melon, chromium, cinnamon, fenugreek,
fiber (glucomannan), ginseng, gymnema, psyllium, vanadyl sulfate, niacin,
tribulus, black seed oil, stinging nettle, olive leaf.

**Proposed additions (would expand 17 → 25):**

| # | Priority | Severity | Subject DB | canonical_id | Dose? | Basis |
|---|---|---|---|---|---|---|
| 1 | MED | monitor | IQM | `magnesium` | ✓ | Modulates insulin sensitivity at high dose |
| 2 | MED | monitor | IQM | `vitamin_d` | — | Emerging evidence on insulin sensitivity |
| 3 | MED | caution | IQM | `garlic` | ✓ | High-dose additive hypoglycemia |
| 4 | MED | caution | IQM | `inositol` | — | Used for PCOS insulin resistance; additive lowering |
| 5 | MED | monitor | <see note> | `niacinamide` | — | Distinct from niacin — different metabolic profile |
| 6 | LOW | caution | <needs IQM> | `banaba` | — | Corosolic acid alpha-glucosidase inhibitor claim |
| 7 | LOW | caution | botanical | `white_mulberry` | — | Alpha-glucosidase inhibitor (mulberry leaf) |
| 8 | LOW | monitor | IQM | `l_carnitine` | — | Emerging insulin-sensitivity evidence |

**Niacinamide note:** check whether IQM has a `niacinamide` form on the
`vitamin_b3_niacin` parent. If yes, this rule's `subject_ref` may need
form-specific routing; talk to Sean about whether System A supports
form-level rules (it currently keys by parent canonical_id).

**Banaba note:** not in IQM or botanical DB. Either skip (low priority)
or author the IQM parent first.

## 1D — Lactation queue (11 rules)

**Existing coverage today (4 rules — VERY thin):** fenugreek (galactagogue
note), vitamin B6 (high-dose), sage (lactation suppression), wild yam.

Lactation is your sparsest condition coverage. Most pregnancy concerns
transfer to lactation, often with similar but not identical severity.
**Recommended approach: extend each existing pregnancy rule with a
`pregnancy_lactation` block** rather than creating standalone lactation
rules. The block schema:

```jsonc
"pregnancy_lactation": {
  "lactation_severity": "avoid",
  "lactation_evidence": "probable",
  "lactation_notes": "Anthranoid laxatives transfer to milk — infant diarrhea risk."
}
```

**Standalone rules where pregnancy doesn't already exist or severity
differs significantly:**

| # | Priority | Lactation Severity | Subject | Basis |
|---|---|---|---|---|
| 1 | HIGH | contraindicated | banned (BANNED_EPHEDRA) | Sympathomimetic in milk |
| 2 | HIGH | avoid | IQM `yohimbe` | Sympathomimetic in milk |
| 3 | HIGH | avoid | IQM `aloe_vera` | Laxative anthranoids transfer |
| 4 | HIGH | avoid | IQM `black_cohosh` | Hormonal — limited milk data |
| 5 | HIGH | contraindicated | botanical `blue_cohosh` | Cardiotoxic alkaloids |
| 6 | HIGH | caution (high-dose only) | IQM `vitamin_a` | Retinol transfers to milk; reuse existing dose threshold |
| 7 | HIGH | monitor (high-dose only) | IQM `caffeine` | Transfers — infant effects at high maternal dose |
| 8 | MED | avoid | IQM `cascara_sagrada` | Anthranoids transfer — infant diarrhea |
| 9 | MED | caution | IQM `senna` | Minimal transfer but laxative effect on infant |
| 10 | MED | avoid | IQM `chasteberry` | May suppress prolactin (LactMed) |
| 11 | MED | caution | IQM `st_johns_wort` | CNS-active in milk; LactMed Lower-risk |

**For #1-#11, prefer extending the existing pregnancy rule with a
`pregnancy_lactation` block over creating a duplicate `condition_id:
lactation` entry.** Keeps the rule count smaller and the maintenance
surface tighter. Only create a standalone `condition_id: lactation`
rule when the lactation guidance differs SIGNIFICANTLY from pregnancy
guidance for the same supplement.

---

# Section 2 — System B expansion (5 entries)

## 2A — How to author one System B entry

Open `scripts/data/curated_interactions/curated_interactions_v1.json`.
Each entry is one drug-supp / supp-supp / drug-drug pair (full schema
in `INTERACTION_DB_SPEC.md` §10.1). Process is unchanged from the
prior plan doc — see `INTERACTION_DB_SPEC.md` for the full 10-step
authoring checklist. Highlights:

1. Verify all CUIs / RXCUIs via live UMLS / RxNorm — never trust an ID
   that hasn't been content-checked. (See the ghost-CUI sweep in commit
   `783632f` for what happens when you skip this.)
2. One entry per atomic commit.
3. Run `bash scripts/rebuild_interaction_db.sh` after each addition;
   the audit report must show 0 errors and 0 warnings.

## 2B — Diabetes pair queue (5 entries)

The previous v1 of this doc had 8 diabetes entries; investigation
showed 3 of them are properly System A condition rules (already in the
queue above). The remaining 5 are **true pair interactions** — they
require both ingredients to be in the user's stack:

| # | Priority | id | severity | type | a1 (med) | a2 (supp) | basis |
|---|---|---|---|---|---|---|---|
| 1 | **HIGH** | `DSI_NIACIN_DIABETES_MEDS_RX` | avoid | Med-Sup | `class:diabetes_meds`* | Niacin >500mg | Worsens insulin resistance — bidirectional |
| 2 | **HIGH** | `DSI_CINNAMON_SULFONYLUREAS` | caution | Med-Sup | `class:sulfonylureas`† | Cinnamon supplement | Additive hypoglycemia |
| 3 | MED | `DSI_BITTERMELON_INSULIN_PAIR` | caution | Med-Sup | Insulin (RXCUI 5856) | Bitter melon | Additive hypoglycemia |
| 4 | MED | `DSI_GYMNEMA_INSULIN_PAIR` | caution | Med-Sup | Insulin (RXCUI 5856) | Gymnema sylvestre | Additive hypoglycemia |
| 5 | MED | `DSI_METFORMIN_B12_DEPLETION` | monitor | Med-Sup | Metformin (RXCUI 6809) | Vitamin B12 | Long-term metformin depletes B12 (PMID:23733888) |

\* `class:diabetes_meds` already exists in `drug_classes.json` ✓
† `class:sulfonylureas` does NOT exist in `drug_classes.json`. Author it
first via RxClass API:
```bash
curl -s "https://rxnav.nlm.nih.gov/REST/rxclass/classMembers.json?classId=N0000175706&relaSource=ATC" \
  | python3 -m json.tool
```
Members include glipizide (RXCUI 4821), glyburide (RXCUI 4815), glimepiride
(RXCUI 25789), tolbutamide (RXCUI 10633). Add as new entry in
`scripts/data/drug_classes.json`, commit, then proceed to entries 2 above.

## 2C — Pregnancy pair queue (1 entry — already exists)

Pregnancy is fundamentally a **condition**, not a stack agent. The only
genuine pregnancy-pair entry is the **existing** `DSI_OC_SJW` (oral
contraceptive + St. John's Wort), which is correctly drug↔supp shaped.

**Do not add more pregnancy entries to System B.** Everything else lives
in System A.

---

# Section 3 — Verification & ship

After all 33 + 5 = 38 entries land:

```bash
# 1. Run the pipeline against a small test brand to verify rules fire
bash batch_run_all_datasets.sh --skip-release --targets Olly

# 2. Inspect a known affected product
python3 -c "
import json, glob
for path in glob.glob('scripts/products/output_Olly_enriched/enriched/*.json'):
    p = json.load(open(path))
    profile = p.get('interaction_profile', {})
    if profile.get('condition_summary', {}).get('pregnancy'):
        print(path, '→ pregnancy alerts:', len(profile['ingredient_alerts']))
        break
"

# 3. Rebuild interaction DB + verify clean
bash scripts/rebuild_interaction_db.sh
python3 -c "
import json
d = json.load(open('scripts/interaction_db_output/interaction_audit_report.json'))
print(f'errors={d[\"errors\"]} warnings={d[\"warnings\"]}')
"
# Expected: errors=0 warnings=0

# 4. Run full pytest
python3 -m pytest scripts/tests/ --ignore=scripts/tests/test_verify_interactions_live.py -q

# 5. Full release
bash scripts/release_full.sh

# 6. Push pipeline
git push origin main

# 7. Push Flutter bundle
cd "/Users/seancheick/PharmaGuide ai"
git add assets/db/
git commit -m "chore(catalog): bundle catalog + interaction +5 (diabetes pair coverage)"
git push origin main
```

---

# Out of scope

- Adding new condition_ids beyond pregnancy/lactation/diabetes/etc.
  defined in `clinical_risk_taxonomy` (talk to Sean — schema change).
- Adding new types beyond what's in `INTERACTION_DB_SPEC.md` §10.1.
- Authoring `class:sglt2_inhibitors`, `class:glp1_agonists`,
  `class:dpp4_inhibitors` (newer diabetes drug classes — useful but
  not required for this 33+5 expansion).
- Re-running supp.ai's extractive pipeline. The corpus is from
  2021-10-24; gaps in current literature exist but should be patched
  via curated entries (this plan), not by reverse-engineering supp.ai's
  NER models.
- The 4 unstaged Flutter files (Sprint 27.7 work) — committed as
  `c16ae46`, already shipped.

---

# Authoritative source list

For pregnancy:
- NIH ODS Pregnancy/Lactation: https://ods.od.nih.gov/factsheets/list-all/
- LactMed (lactation database): https://www.ncbi.nlm.nih.gov/books/NBK501922/
- LiverTox: https://www.ncbi.nlm.nih.gov/books/NBK547852/
- ACOG Committee Opinions: https://www.acog.org/clinical/clinical-guidance/committee-opinion
- Briggs Drugs in Pregnancy and Lactation (textbook reference, not a URL)

For diabetes:
- ADA Standards of Medical Care: https://diabetesjournals.org/care/issue/49/Supplement_1
- NIH ODS Diabetes-relevant fact sheets
- Cochrane reviews (chromium, cinnamon both have current Cochrane entries)
- Clinical Pharmacology drug interaction database (commercial — verify
  with primary literature)

For RXCUI / drug class:
- RxNav: https://lhncbc.nlm.nih.gov/RxNav/APIs/RxNormAPIs.html
- RxClass: https://lhncbc.nlm.nih.gov/RxNav/APIs/RxClassAPIs.html

---

# Spec pointers

- `docs/INTERACTION_DB_SPEC.md` v2.2.0 — full architecture for System B
  (curated pairs). Read §6.2 (verifier checks) and §10.1 (entry schema)
  before authoring System B entries.
- `scripts/data/ingredient_interaction_rules.json` `_metadata` block
  — schema version + last-reviewed conventions for System A.
- `scripts/SAFETY_DATA_PATH_C_PLAN.md` — pipeline safety-copy contract
  (alert_headline / alert_body / informational_note authoring rules).
- `lib/features/product_detail/widgets/interaction_warnings.dart`
  — Flutter consumer for System A (read-only reference; no changes needed).
- `lib/services/stack/stack_interaction_checker.dart` — Flutter consumer
  for System B (read-only reference; no changes needed).

---

# Honest risk register

| Risk | Likelihood | Impact | Mitigation |
|---|---|---|---|
| Wrong subject_ref.db chosen | Med | Low (rule no-ops silently) | Schema check + pipeline test verifies rule fires on known product |
| Severity over-coding (everything contraindicated) | Med | High (UX — users disable warnings) | Reserve `contraindicated` for true forbidden combinations; default to `caution` or `monitor` |
| Severity under-coding (real risks downgraded) | Low | Very high (clinical) | Match source guideline severity; lean conservative when sources disagree |
| Dose threshold authored wrong unit | Low | High (false negative) | Always content-verify the unit in the cited paper before authoring |
| Rule duplicates existing coverage | Low | Low (duplicate alert) | Audit list above is current as of 2026-04-26 — re-run audit before authoring |
| New IQM/banned/botanical parent needed but skipped | Med | Med (rule can't fire) | Author the parent FIRST as its own commit; then add the rule |
