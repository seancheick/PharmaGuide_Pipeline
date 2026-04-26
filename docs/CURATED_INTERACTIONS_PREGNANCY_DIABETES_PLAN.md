# Curated Interactions — Pregnancy + Diabetes Expansion Plan

**Document version:** 1.0.0
**Date:** 2026-04-26
**Owner:** next Claude Code session, with Sean reviewing
**Goal:** grow the curated interaction database from 109 → ~129 entries, focusing on the two clinical areas with the highest user-impact: pregnancy and diabetes management.

---

## TL;DR for the next session

You're picking up curated-interactions authoring work. The pipeline has 109 verified entries today. Sean wants 20 more entries (12 pregnancy, 8 diabetes) added carefully — one entry at a time, each with live PMID + UMLS verification. Every entry must survive `bash scripts/rebuild_interaction_db.sh` (live API mode) with zero errors and zero warnings. **Do NOT batch-add entries.** Do them one-at-a-time, commit after each, push when the user gives the word.

If you finish the 20, do not invent more without asking. Sean's stated cadence: "until we're solid enough to add more."

---

## Why this matters

Today's coverage:
- **Pregnancy:** 1 entry (`DSI_OC_SJW`) — a near-zero coverage area with high liability.
- **Diabetes:** 10 entries — decent coverage, but missing some major-prevalence pairs (chromium + sulfonylureas, niacin + diabetes meds, cinnamon + sulfonylureas).

PharmaGuide is a clinical tool. Pregnancy is the highest-stakes safety area in the entire app — getting a pregnancy interaction wrong is a defect that can cause real harm. Diabetes pairs are routine in the user base (≈30M Americans on diabetes meds; many also take supplements). Both areas were chosen because:

1. **High user-impact** (large affected population).
2. **Well-documented in literature** (NIH ODS, LiverTox, DailyMed all have authoritative sources — easy to PMID-verify).
3. **Stable consensus** (less likely to need re-authoring as evidence shifts).

---

## Where to author

**File:** `scripts/data/curated_interactions/curated_interactions_v1.json`

Look at any existing `DSI_*` or `DDI_*` entry to mirror the JSON shape. Required fields (per `INTERACTION_DB_SPEC.md` §10.1):

```jsonc
{
  "id": "DSI_<UPPER_SNAKE>",                  // unique, document the kind
  "type": "Med-Sup",                          // or Sup-Med, Sup-Sup, Med-Food, etc.
  "agent1_name": "Warfarin",
  "agent1_id": "11289",                       // RXCUI for drugs / class:X for classes
  "agent2_name": "Vitamin K",
  "agent2_id": "C0042839",                    // CUI for supplements
  "agent2_canonical_id": "vitamin_k",         // matches IQM key
  "severity": "Major",                        // Contraindicated|Major|Moderate|Minor
  "interaction_effect_type": "Inhibitor",     // Inhibitor|Enhancer|Additive|Neutral
  "mechanism": "<one paragraph, layperson-readable>",
  "management": "<actionable advice, what the user should do>",
  "source_urls": [
    "https://ods.od.nih.gov/factsheets/...",
    "https://www.ncbi.nlm.nih.gov/books/NBK..."
  ],
  "source_pmids": ["12345678"],
  "verification": {
    "verified_at": "2026-MM-DD",
    "verified_by": "claude-code-session",
    "evidence_basis": "review",               // rct|review|case_report|mechanism
    "clinical_confidence": "high"             // high|moderate|low
  }
}
```

---

## Authoring checklist (per entry — DO NOT SKIP STEPS)

### Step 1 — Identify the pair
Pick the next entry from the queue below. Check it doesn't already exist:

```bash
python3 -c "
import json
d = json.load(open('scripts/data/curated_interactions/curated_interactions_v1.json'))
for e in d['interactions']:
    if 'vitamin a' in (e.get('agent1_name','')+e.get('agent2_name','')).lower():
        print(e['id'], '←', e['type'])
"
```

If it exists, skip and move to the next entry.

### Step 2 — Find the canonical citation
Search PubMed for the seminal evidence:
- For pregnancy interactions: look for **NIH ODS Fact Sheet** + **LiverTox** + the meta-analysis or seminal RCT.
- For diabetes interactions: look for **Cochrane review** or **systematic review** when available, otherwise the well-cited mechanistic study.

Use the WebFetch tool to OPEN the abstract and confirm the article matches the claim. **Do not author until the PMID is content-verified.** This is the rule the previous session learned the hard way (Tyramine had a phantom CUI; Valerian was authored as the discontinued obesity drug "Redux"). Existence of a PMID does not mean it's about your topic.

### Step 3 — Verify identifiers via live APIs

**Drug RXCUI** (RxNorm):
```bash
curl -s "https://rxnav.nlm.nih.gov/REST/rxcui/<RXCUI>/properties.json"
```
Confirm the returned `name` matches your `agent1_name` (or `agent2_name`).

**Supplement / food CUI** (UMLS):
```python
import os, urllib.request, ssl, json, sys
sys.path.insert(0, 'scripts')
import env_loader
key = os.environ['UMLS_API_KEY']
url = f'https://uts-ws.nlm.nih.gov/rest/content/current/CUI/<CUI>?apiKey={key}'
print(json.loads(urllib.request.urlopen(url).read())['result'])
```
Confirm the `name` is what you expect (NOT a withdrawn drug, NOT a homonym).

**Drug class** (`class:statins` etc.):
The 28 supported classes are in `scripts/data/drug_classes.json`. If your entry needs a class that's not there, you must author the class first (separate task — don't sneak it into an interaction entry).

### Step 4 — IQM canonical_id mapping (supplements only)
For supplement-side entries, look up the CUI in `scripts/data/ingredient_quality_map.json` and pick the matching `canonical_id` (the top-level key whose `cui` field matches). Set `agent2_canonical_id` (or `agent1_canonical_id`) accordingly. If the supplement isn't in IQM, fix that FIRST — interaction without canonical_id won't surface in stack-based checks.

### Step 5 — Author mechanism + management

**Mechanism** (1 paragraph, layperson-readable):
- Explain the why in plain language a smart non-clinician can follow
- Cite the mechanism (CYP3A4 inhibition, displaces albumin binding, etc.) but explain it
- 2-4 sentences max
- Match the cited paper — don't claim more than the evidence shows

**Management** (1 paragraph, actionable):
- What the user should DO, not what they shouldn't worry about
- Specific timing windows when relevant ("separate by 2 hours")
- Lab monitoring suggestions when appropriate ("INR weekly for 4 weeks")
- "Talk to your doctor" is fine but not the only advice

### Step 6 — Severity assignment

Use the project's 4-tier draft vocabulary (gets normalized to the 5-tier Flutter enum):

| Draft severity | Use when |
|---|---|
| `Contraindicated` | Co-use is forbidden. Real harm risk if combined. |
| `Major` | Real risk; avoid unless monitored by a clinician. |
| `Moderate` | Caution; combine with monitoring. |
| `Minor` | Theoretical or low-impact; awareness only. |

**Pregnancy-specific calibration:**
- Teratogenic/embryotoxic at supplemental doses → `Contraindicated`
- Strong human signal but reversible → `Major`
- Theoretical or animal-only → `Caution` (don't over-warn)
- Always lean toward clinical conservatism in pregnancy.

### Step 7 — Source URLs + PMIDs

**Source URLs:** at minimum one authoritative free source. Acceptable:
- `https://ods.od.nih.gov/factsheets/...`
- `https://www.ncbi.nlm.nih.gov/books/NBK...` (LiverTox / NIH Bookshelf)
- `https://medlineplus.gov/...`
- `https://www.fda.gov/...`
- `https://dailymed.nlm.nih.gov/...`

**Source PMIDs:** include every PMID you content-verified in Step 2.

### Step 8 — Validate the build

```bash
cd /Users/seancheick/Downloads/dsld_clean
bash scripts/rebuild_interaction_db.sh
```

Read the audit report:
```bash
python3 -c "import json; d=json.load(open('scripts/interaction_db_output/interaction_audit_report.json')); print(f'errors={d[\"errors\"]} warnings={d[\"warnings\"]}')"
```

**Acceptance: 0 errors, 0 warnings.** If you see anything, do not commit — fix the entry first.

### Step 9 — Commit

One entry = one commit. Atomic. Easy to revert if Sean spots a problem in review.

```bash
git add scripts/data/curated_interactions/curated_interactions_v1.json
git commit -m "interactions: <area> — <pair> (<severity>)"
```

Example messages:
- `interactions: pregnancy — vitamin A retinol teratogenicity (contraindicated)`
- `interactions: diabetes — chromium + sulfonylureas hypoglycemia (caution)`

### Step 10 — Repeat

Move to the next entry in the queue. Do NOT batch.

---

## Pregnancy queue (12 entries)

| # | id | severity | agent1 (drug/condition) | agent2 (supplement) | priority |
|---|---|---|---|---|---|
| P1 | `DSI_PREG_VITA_RETINOL` | Contraindicated | Pregnancy (`condition:pregnancy`) | Vitamin A retinol >10,000 IU | **HIGH** — well-documented teratogen |
| P2 | `DSI_PREG_BLACK_COHOSH_T1` | Contraindicated | Pregnancy 1st trimester | Black cohosh | HIGH — uterotonic + hepatotoxicity |
| P3 | `DSI_PREG_DONG_QUAI` | Contraindicated | Pregnancy | Dong quai | HIGH — uterine stimulant |
| P4 | `DSI_PREG_VITE_HIGH` | Avoid | Pregnancy | Vitamin E >400 IU/day | MED — contested cardiac signal |
| P5 | `DSI_PREG_GOLDENSEAL` | Avoid | Pregnancy | Goldenseal (berberine) | HIGH — bilirubin displacement |
| P6 | `DSI_PREG_FISHOIL_HIGH` | Caution | Pregnancy near term | Fish oil >3g/day | MED — bleeding risk |
| P7 | `DSI_PREG_GINGER_HIGH_T1` | Caution | Pregnancy 1st trimester | Ginger >1g/day | MED — theoretical bleeding |
| P8 | `DSI_PREG_SAW_PALMETTO` | Caution | Pregnancy | Saw palmetto | MED — hormonal activity |
| P9 | `DSI_PREG_GINKGO` | Caution | Pregnancy | Ginkgo biloba | MED — bleeding risk |
| P10 | `DSI_PREG_DHEA` | Caution | Pregnancy | DHEA | LOW — hormonal |
| P11 | `DSI_PREG_GARLIC_HIGH` | Monitor | Late pregnancy | Garlic supplement | LOW — bleeding |
| P12 | `DSI_PREG_ECHINACEA` | Monitor | Pregnancy | Echinacea | LOW — insufficient data |

**Implementation note for P1-P12:** The "pregnancy" side is a *condition*, not a drug or supplement. The current schema uses `Med-Sup` for drug↔supplement. For pregnancy, you'll need to either:
1. Use a new type `Cond-Sup` (Condition-Supplement) and add support in `verify_interactions.py`. **This is an architectural change — discuss with Sean before proceeding.**
2. Treat pregnancy as a synthetic "agent" with a placeholder ID like `cond:pregnancy` (similar to `class:statins`). Less invasive, but requires schema extension.

**Recommended:** start with **P1 (Vitamin A retinol)** as a test case to settle the schema question with Sean before doing the rest.

**Authoritative sources** (use for all pregnancy entries):
- NIH ODS Pregnancy & Lactation: https://ods.od.nih.gov/factsheets/list-all/
- LiverTox: https://www.ncbi.nlm.nih.gov/books/NBK547852/
- ACOG Committee Opinions on supplements in pregnancy
- Drugs.com pregnancy categories (now retired but still cited)

---

## Diabetes queue (8 entries)

| # | id | severity | agent1 (med) | agent2 (supplement) | priority |
|---|---|---|---|---|---|
| D1 | `DSI_NIACIN_DIABETES_MEDS` | Avoid | class:diabetes_meds | Niacin >500mg | **HIGH** — worsens insulin resistance |
| D2 | `DSI_CINNAMON_SULFONYLUREAS` | Caution | class:sulfonylureas* | Cinnamon supplement | HIGH — additive hypoglycemia |
| D3 | `DSI_BITTERMELON_INSULIN` | Caution | Insulin (RXCUI 5856) | Bitter melon | MED — additive hypoglycemia |
| D4 | `DSI_GYMNEMA_INSULIN` | Caution | Insulin | Gymnema | MED — additive hypoglycemia |
| D5 | `DSI_CHROMIUM_SULFONYLUREAS` | Caution | class:sulfonylureas | Chromium | MED — additive hypoglycemia |
| D6 | `DSI_GINSENG_SULFONYLUREAS` | Caution | class:sulfonylureas | Ginseng | MED — additive hypoglycemia |
| D7 | `DSI_METFORMIN_MAGNESIUM_TIMING` | Monitor | Metformin | Magnesium | LOW — absorption interference (PMID:33546143) |
| D8 | `DSI_METFORMIN_B12_DEPLETION` | Monitor | Metformin (chronic) | Vitamin B12 | LOW — well-known depletion (PMID:23733888) |

\* `class:sulfonylureas` is not in `scripts/data/drug_classes.json` today. You may need to add it first via RxClass API:
```bash
curl -s "https://rxnav.nlm.nih.gov/REST/rxclass/classMembers.json?classId=N0000175706&relaSource=ATC"
```
Members include glipizide, glyburide, glimepiride. Once authored in `drug_classes.json`, your D2/D5/D6 entries can reference it.

**Authoritative sources** (use for all diabetes entries):
- ADA Standards of Medical Care: https://diabetesjournals.org/care/issue/49/Supplement_1
- NIH ODS: https://ods.od.nih.gov/factsheets/list-all/
- Cochrane reviews on specific supplements (chromium, cinnamon — both have current Cochrane entries)
- Clinical Pharmacology drug interaction database

---

## Anti-patterns to avoid (lessons from prior session)

1. **Don't author multiple entries before validating.** Each entry needs to round-trip through `rebuild_interaction_db.sh` cleanly. Doing 5 at once and then debugging 5 simultaneous failures is misery.

2. **Don't trust a CUI just because it parses.** UMLS revealed C0728749 was "Redux" (a withdrawn diet drug), not Valerian. C3256843 was "grapefruit peel extract", not whole grapefruit. **Always content-verify the CUI's `name` field via UMLS API.**

3. **Don't author management text generically.** "Talk to your doctor" alone is useless. Specific timing, monitoring, dose ceiling — that's what users actually need.

4. **Don't claim more than the cited paper proves.** If the source says "association suggested", don't write "causes hypoglycemia". Match the evidence strength.

5. **Don't put pregnancy in `Sup-Sup` or `Med-Sup` types.** It's a condition. Talk to Sean about schema before authoring.

6. **Don't over-warn.** A `Contraindicated` for everything in pregnancy is unhelpful — users will just turn off pregnancy mode entirely. Reserve `Contraindicated` for truly forbidden combinations. Most pregnancy interactions are `Caution` or `Monitor`.

---

## When you're done

After all 20 entries land:

```bash
# Verify the bulk addition
bash scripts/rebuild_interaction_db.sh
python3 -c "
import json, sqlite3
d = json.load(open('scripts/interaction_db_output/interaction_audit_report.json'))
print(f'audit: errors={d[\"errors\"]} warnings={d[\"warnings\"]}')
con = sqlite3.connect('scripts/interaction_db_output/interaction_db.sqlite')
print(f'total interactions: {con.execute(\"SELECT COUNT(*) FROM interactions\").fetchone()[0]}')
"
```

Expected output:
```
audit: errors=0 warnings=0
total interactions: 156    # was 136 + 20 new
```

Then push to release:

```bash
bash scripts/release_full.sh           # full release through Flutter
git push origin main                   # push pipeline
cd "/Users/seancheick/PharmaGuide ai"
git add assets/db/
git commit -m "chore(catalog): bundle catalog + interaction +20 (pregnancy/diabetes coverage)"
git push origin main
```

---

## Out of scope for this session

- Adding new types beyond `Med-Sup`, `Sup-Med`, `Sup-Sup`, `Med-Med`, `Med-Food`, `Food-Med` (talk to Sean).
- Editing `drug_classes.json` (other than `class:sulfonylureas` if D2/D5/D6 require it — and only after verifying members via RxClass API).
- Adding curated entries outside pregnancy / diabetes scope. Sean's stated cadence: solid first, expand later.
- Anything in the Flutter repo. The interaction DB ships as a bundled asset; if Flutter needs a new render style, that's a separate sprint.

---

## Pointer back to authoritative spec

Full architectural detail lives in `docs/INTERACTION_DB_SPEC.md` v2.2.0. That doc is the source of truth for:
- The 10 verifier checks
- The two-tier data model (curated + research_pairs)
- Severity normalization (4-tier draft → 5-tier Flutter enum)
- The atomic publish flow (working dir → dist/ → Flutter)

Read §6.2 before you start authoring — it's the contract every entry must satisfy.
