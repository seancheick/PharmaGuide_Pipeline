# Fix Sprint 03 — drug-class resolution defects (diuretics, PPI, enzyme-inducing AEDs)

Reviewer: `lead_clinician_fix_sprint_03` · 2026-07-24

Scope: the class-resolution defects carried forward from Sprint 2's
`audit_report.md` ("the same drug-class-resolver gap as Sprint 3 — diuretics /
antacids / anticonvulsants"). This is a **pipeline taxonomy/data** change plus
DB/artifact regeneration — not new Flutter resolver logic. The app already
resolves *all* class memberships from the pipeline-generated `drug_class_map`
(class → member_rxcuis, 1→many) in the bundled interaction SQLite.

**Governing rule (from PM handoff):** do NOT blanket-repoint records that share a
coarse class. Several diuretic and anticonvulsant records are drug- or
subclass-specific and must be handled in later entry-specific audits.

---

## Operating brief (reconstructed — the working chat was lost)

The prior working session that produced batches 01–02 and fix sprints 01–02 is
gone from the searchable transcript store. The **work** is fully preserved in
git (`#5`–`#8`), `scripts/audits/{batch_01,batch_02,fix_sprint_01,fix_sprint_02}/`,
and `scripts/tests/test_med_nutrient_*`. This file re-establishes the durable
reasoning so no chat is needed to continue.

Completed and merged: A1 (unified clinical signal layer), B1.1 (med–nutrient
runtime semantics + identity), B1.2 (versioned artifact + publication policy),
content batches 01–02, fix sprints 01–02. Cross-repo content hash after Sprint 2:
`sha256:12f7597461fd5c94…`. `class:corticosteroids` is already systemic-only
(the earlier inhaled/systemic-mix concern was overstated).

Publication policy: only `verified` entries display/persist/notify;
`unverified` shows a temporary migration state; `needs_revision`/`rejected` are
suppressed. Sprint 3 does **not** promote entries to `verified` — it corrects
taxonomy so that, once verified, the entries fire safely. Do not rename
`verified` → `publication_ready` during the active audit cycle.

---

## Verified data reality (checked against the live files + RxNorm, not assumed)

`scripts/data/drug_classes.json` (schema 1.0.0) — `classes[id] = {display_name,
description, member_rxcuis[], member_names[], rxclass_id, atc_codes[]}`;
`member_rxcuis`/`member_names` are positionally parallel. `build_interaction_db.py`
emits one `drug_class_map` row per class, so a new class ships automatically once
added here. `drug_class_vocab.json` is a **separate, locked 30-entry user-facing
picker** — pharmacology classes added to `drug_classes.json` do NOT go there.

`medication_depletions.json` — the 6 diuretic / 6 antacid / 7 anticonvulsant
entries and the class each currently points to:

| Family | class currently → | entries |
|--------|-------------------|---------|
| Diuretics | `class:diuretics` (31 members, **incl. 8 potassium-sparing**) | potassium, magnesium, zinc, calcium, thiamine, folate |
| Antacids | `class:antacids` ("PPIs and antacids") | B12, magnesium, calcium, iron, vitamin C, zinc |
| Anticonvulsants | `class:anticonvulsants` (40 members) | vitamin D, calcium, folate, B12, vitamin K, biotin, L-carnitine |

`class:proton_pump_inhibitors` (5 members: esomeprazole, lansoprazole,
omeprazole, pantoprazole, rabeprazole) and `class:antacids` (neutralising
products) already exist and are distinct. `class:thiazide_diuretics` and
`class:potassium_sparing_diuretics` already exist; **no** `class:loop_diuretics`
or combined loop+thiazide class exists yet.

### ⚠️ Landmine found: `class:thiazide_diuretics` has 3 wrong RXCUIs

Its `member_rxcuis` is misaligned with `member_names`. RxNorm-verified:

| name row | rxcui in thiazide class | rxcui actually is | correct rxcui |
|----------|-------------------------|-------------------|---------------|
| cicletanine | `302285` | **conivaptan** | `21914` |
| methyclothiazide | `6774` | **mersalyl** | `6860` |
| quinethazone | `9997` | **spironolactone** | `59743` |

So `class:thiazide_diuretics` currently resolves **spironolactone (9997)** and
**conivaptan (302285)** — a potassium-sparing agent and an aquaretic — in the
shipped `drug_class_map`. The schema test only checks `len(rxcuis)==len(names)`,
never that `rxcui[i]` matches `name[i]`, which is why it survived. Latent for
depletions today (no depletion entry points at `class:thiazide_diuretics`), but
real. **Fix built from the verified master `class:diuretics` list, never from
this class.** Corrected in a separate atomic commit + an alignment regression.

---

## Sprint 3 dispositions

### 1. Diuretics → potassium / magnesium  (Step 1, this sprint)

`class:diuretics` mixes loop, thiazide, and potassium-sparing drugs. Firing
potassium-loss advice on spironolactone / eplerenone / amiloride / triamterene is
a **hyperkalemia hazard**. Both target entries' authored mechanisms already
describe loop + thiazide only, so the repoint matches the content.

Create `class:loop_and_thiazide_diuretics` — loop + thiazide/thiazide-like only,
sourced from the RxNorm-verified master `class:diuretics`, explicitly excluding
every potassium-sparing agent, the vaptans, theobromine, and obsolete mersalyl.
Members (21, sorted by name): bendroflumethiazide, bumetanide, chlorothiazide,
chlorthalidone, cicletanine, clopamide, cyclopenthiazide, cyclothiazide,
furosemide, hydrochlorothiazide, hydroflumethiazide, indapamide, mefruside,
methyclothiazide, metolazone, piretanide, polythiazide, quinethazone, torsemide,
trichlormethiazide, xipamide.

Repoint **only** `DEP_DIURETICS_POTASSIUM` and `DEP_DIURETICS_MAGNESIUM`.
Fix copy: "Potassium-sparing foods" → "Potassium-rich foods" in the potassium
recommendation.

**Do NOT touch** these in Step 1 (deferred to later entry-specific audits — they
stay on `class:diuretics`, which keeps them firing for loop/thiazide agents while
the deferred K-sparing exposure is a pre-existing, not newly-introduced, state):
- `DEP_DIURETICS_FOLATE` — **triamterene-specific** (a potassium-sparing folate
  antagonist). Must eventually point to *triamterene itself*, NOT the whole
  potassium-sparing class.
- `DEP_DIURETICS_CALCIUM` — loop-specific (loops are calciuric; thiazides retain
  calcium — opposite sign, so this cannot ride the combined class).
- `DEP_DIURETICS_THIAMINE` — primarily furosemide-specific.
- `DEP_DIURETICS_ZINC` — needs its own evidence/scope audit.

### 2. Antacids → PPI  (B12, magnesium)

`class:antacids` is direct neutralising products (Ca/Al/Mg salts). PPI-associated
B12 malabsorption and hypomagnesemia are directionally wrong on it.
`class:proton_pump_inhibitors` already exists. Repoint **only**
`DEP_ANTACIDS_VITAMINB12` and `DEP_ANTACIDS_MAGNESIUM` → `class:proton_pump_inhibitors`.
Do NOT auto-move calcium/iron/vitamin C/zinc (different evidence + class scope).
Magnesium citation: PMID is real and on-topic but the author/journal label is
wrong → classify **misattributed_citation** (not ghost).

### 3. Anticonvulsants → vitamin D

Create `class:enzyme_inducing_antiseizure_medications` (phenytoin, carbamazepine,
phenobarbital, primidone; evaluate oxcarbazepine separately, do not auto-include).
Repoint **only** `DEP_ANTICONVULSANTS_VITAMIND`. Do NOT move the others; in
particular biotin and L-carnitine are **valproate-specific** and valproate is an
enzyme *inhibitor* — it must never enter an enzyme-*inducing* class.

---

## Permanent regressions (this sprint)

`test_medication_depletions.py::test_class_refs_exist_in_drug_classes` already
checks existence. Strengthen to the PM's contract — for every class referenced by
`medication_depletions.json`: exists · has ≥1 member · resolves ≥1 RxCUI · is
emitted to `drug_class_map` in the built SQLite · resolvable by the app bridge.
Negative membership: no potassium-sparing agent in `loop_and_thiazide_diuretics`;
no direct antacid in `proton_pump_inhibitors`; no valproate in
`enzyme_inducing_antiseizure_medications`. Positive resolution: furosemide +
hydrochlorothiazide → combined diuretic class; omeprazole/pantoprazole → PPI;
phenytoin/carbamazepine → enzyme-inducing AED. Plus a name↔rxcui alignment guard
so the thiazide landmine cannot recur.

## Citation defect taxonomy (audit reporting)

`ghost_citation` (PMID/URL unrelated) · `placeholder_source` (generic source,
not the specific relationship) · `misattributed_citation` (real & relevant source,
wrong author/title/journal label) · `weak_evidence` (related but doesn't support
the claim strength).

## Rebuild + ship (steps 5–6)

Rebuild interaction SQLite + med–nutrient artifact, regenerate the Flutter
bundled fallback, repin the content hash (`test_medication_depletions_artifact.py`)
and cross-repo parity, then open **separate** pipeline and app PRs. Full
affected-test run before each PR.
