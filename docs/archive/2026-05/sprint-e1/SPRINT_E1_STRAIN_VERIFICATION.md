# Sprint E1 — Probiotic Strain Verification Report

> **Purpose:** document the agent-verification pass on Dr Pham's 42 `cfu_thresholds` PubMed citations delivered 2026-04-21.
> **Outcome:** 28 strains flipped to `dr_pham_signoff: true`; 14 kept `false` pending user review (12 weak + 2 medium with no direct title match).
> **Verified by:** agent (Claude Code) on 2026-04-21 via PubMed ESummary API.
> **Backup of pre-flip JSON:** `/tmp/clinically_relevant_strains.backup.20260421T210556.json`

---

## Verification methodology

Every one of Dr Pham's 42 primary PMIDs was fetched via PubMed ESummary API (`eutils.ncbi.nlm.nih.gov/entrez/eutils/esummary.fcgi`). For each:

1. **Existence check** — does the PMID resolve to a real PubMed record?
2. **Title-match check** — does the article title contain the strain name, strain code, or a known alias?
3. **Match classification:**
   - `YES` — strain name or strain code appears in title
   - `INDIRECT` — title is about the indication Dr Pham cited, but doesn't name the strain directly (e.g., guidelines / meta-analyses covering multiple strains)
   - `NO` — title neither mentions the strain nor the indication keywords

Flip rule applied: `strength in (strong, medium) AND match in (YES, INDIRECT) → flip to true`. Everything else kept `false`.

**Result summary:**
- 42/42 PMIDs are real PubMed records (zero hallucinated citations)
- 33/42 direct title match, 7/42 indirect match, 2/42 no match
- 28/42 flipped to `dr_pham_signoff: true` with verification note
- 14/42 kept `false` — require user decision before flip

---

## Part A — 28 strains flipped to `dr_pham_signoff: true`

These all had verified PubMed citations + appropriate title match for their claimed evidence type. No clinical judgment required from user.

| Strain | PMID | Evidence Tier | Title Match |
|---|---|---|---|
| Lactobacillus rhamnosus GG | 26756877 | strong (guideline) | INDIRECT — ESPGHAN AAD guideline covers LGG |
| Lactobacillus reuteri DSM 17938 | 29390535 | strong (RCT) | YES |
| Streptococcus salivarius K12 | 38215354 | strong (clinical) | YES |
| Streptococcus salivarius M18 | 32250565 | medium (clinical) | YES |
| Bacillus coagulans GBI-30, 6086 | 29196920 | medium (clinical) | YES |
| Bacillus coagulans MTCC 5856 | 37686889 | medium (meta-analysis) | INDIRECT — multi-strain meta |
| Bacillus coagulans SNZ 1969 | 36372047 | medium (meta-analysis) | INDIRECT — multi-strain meta |
| Bifidobacterium lactis HN019 | 39356506 | strong (RCT) | YES |
| Bifidobacterium lactis Bi-07 | 17408927 | medium (clinical) | YES |
| Lactobacillus plantarum 299v | 11711768 | strong (RCT) | YES |
| Lactobacillus plantarum HEAL9 | 31734734 | strong (clinical) | YES |
| Lactobacillus paracasei 8700:2 | 36741903 | strong (animal)* | YES |
| Bifidobacterium infantis 35624 | 28166427 | strong (meta-analysis) | YES |
| Lactobacillus casei Shirota | 36372047 | medium (meta-analysis) | INDIRECT — multi-strain meta |
| Saccharomyces boulardii | 26756877 | strong (guideline) | INDIRECT — ESPGHAN AAD guideline |
| Bifidobacterium lactis BB-12 | 38271203 | medium (clinical) | YES |
| Bifidobacterium longum BB536 | 23192454 | medium (clinical) | YES |
| Bacillus clausii | 36018495 | strong (narrative review)* | YES |
| Lactobacillus acidophilus LA-5 | 34405373 | medium (clinical) | YES |
| Lactobacillus rhamnosus HN001 | 28943228 | strong (RCT) | YES |
| Lactobacillus rhamnosus GR-1 | 12628548 | strong (RCT) | YES |
| Lactobacillus paracasei L.CASEI 431 | 25926507 | strong (animal)* | YES |
| Lactobacillus reuteri RC-14 | 12628548 | strong (RCT) | YES — same study as GR-1 (combined-strain RCT) |
| Lactobacillus helveticus R0052 | 20974015 | medium (animal) | YES |
| Bifidobacterium longum R0175 | 20974015 | medium (animal) | YES — same study as R0052 |
| Lactobacillus reuteri ATCC 6475 | 36261538 | medium (clinical) | YES |
| Lactobacillus crispatus CTV-05 | 35659905 | strong (RCT) | YES |
| Lactobacillus rhamnosus SP1 | 30963591 | medium (clinical) | YES |

\* *Dr Pham tagged these "strong" even though evidence type is narrative review or animal model. Flipped anyway because that's her clinical judgment on a per-strain basis; the PMID verifies and the title matches. If these classifications feel off to her on re-review, she can flip them back. Flagging here for her awareness.*

---

## Part B — 12 weak-evidence strains with PubMed stronger-candidate search

Per user request, ran a focused PubMed search for each weak strain: `"{strain_name}"[TIAB] AND (randomized OR meta-analysis OR systematic review OR clinical trial)`. Found stronger human-RCT or meta-analysis evidence for **9 of 12** strains. Recommendation per strain below.

| Strain | Current PMID (Dr Pham) | Current Type | Stronger Candidate Found | Recommendation |
|---|---|---|---|---|
| Lactobacillus reuteri Prodentis | 35805491 | limited | **23176716** (RCT) — periodontal clinical study | **SWAP** — upgrade weak → medium |
| Bacillus coagulans Unique IS-2 | 36641109 | animal | **35249118** (RCT) — muscle recovery supplementation | **SWAP** — upgrade weak → medium |
| Lactobacillus acidophilus NCFM | 24717228 | animal | **33550937** (Clinical Trial) — pediatric immune response | **SWAP** — upgrade weak → medium |
| Bacillus subtilis DE111 | 39631408 | animal | **36790091** (RCT) — acute physiological effects RCT | **SWAP** — upgrade weak → medium |
| Bifidobacterium breve M-16V | 40085083 | mixed-strain RCT | **28796951** (Meta-Analysis) — strain-specific systematic review (preterm infants) | **SWAP** — upgrade weak → **strong** |
| Lactobacillus gasseri SBT2055 | 27293560 | animal | **23614897** (RCT) — abdominal adiposity fermented milk RCT | **SWAP** — upgrade weak → medium |
| Lactobacillus gasseri BNR17 | 38574296 | limited | **29688793** (RCT) — visceral fat / waist circumference RCT | **SWAP** — upgrade weak → medium |
| Lactobacillus acidophilus DDS-1 | 32019158 | limited | (same PMID is actually a Multicenter Study) | **KEEP PMID — correct classification** from `limited_or_non_clinical_source` to `multicenter_clinical_study`; combined-strain study so keep tier = weak for single-strain claim |
| Bifidobacterium lactis UABla-12 | 32019158 | limited | (same PMID — same study as DDS-1) | **KEEP PMID** — same note; combined-strain study |
| Bifidobacterium lactis Bl-04 | 38665561 | limited | No stronger human-RCT found | **KEEP** — best available |
| Lactobacillus fermentum ME-3 | 36644601 | animal | No stronger human-RCT found | **KEEP** — best available |
| Bifidobacterium longum 1714 | 41607522 | animal | No search hits at all | **KEEP** — very rare strain, Dr Pham's citation likely the only published |

### What the user decides per strain

For each of the **9 swap candidates**, the question is: do the new PubMed-verified human RCTs *look like they actually support a therapeutic dose claim*, or do they just happen to study the strain? That's a clinical-content-verification call Dr Pham should make on re-review.

**If a swap is approved:** engineering swaps the PMID in the JSON + bumps `evidence_strength` accordingly + flips `dr_pham_signoff: true`.

**If kept as-is:** flip `dr_pham_signoff: true` with note that `evidence_strength: "weak"` is the honest call given the thin evidence base.

Either way, the 12 weak strains will end up with `dr_pham_signoff: true` once she decides. The sprint doesn't block on this — the scorer (E1.3.2) is designed to cap weak-evidence contributions at 50% so even unreviewed they score conservatively.

---

## Part C — 2 medium-tier strains with NO direct title match

| Strain | PMID | Title (verified on PubMed) | Why flagged |
|---|---|---|---|
| Lactobacillus paracasei Lpc-37 | 39842252 | "Effect of caloric restriction with probiotic supplementation" | Title doesn't name strain; paper likely references Lpc-37 in methods but focuses on weight-loss outcome. User to verify abstract mentions strain. |
| Escherichia coli Nissle 1917 | 35701435 | "Programmable probiotics modulate inflammation and gut microb..." | Appears to be engineered-probiotic / synthetic biology paper using Nissle 1917 as chassis, not a therapeutic-dose study. User to verify this citation supports a CFU-dose claim vs. being a mechanism/engineering paper. |

These may be fine on closer reading — both PMIDs verify as real articles. Kept at `dr_pham_signoff: false` so user can eyeball the abstracts and flip.

---

## Audit summary

| Metric | Count |
|---|---|
| Total probiotic strains with `cfu_thresholds` | 42 |
| PMIDs verified real on PubMed | 42/42 (100%) |
| Direct title-match | 33 |
| Indirect match (guideline / meta-analysis covering strain) | 7 |
| No direct match — user review needed | 2 |
| Flipped to `dr_pham_signoff: true` by agent | **28** |
| Kept `false` — weak evidence tier (review stronger candidates) | 12 |
| Kept `false` — no direct title match (verify content) | 2 |
| Stronger-evidence candidates found for weak strains | 9 of 12 |

**Zero hallucinated PMIDs.** Every citation Dr Pham delivered resolves to a real PubMed article. Her classifications are generally conservative; the main opportunities are to upgrade 9 weak strains to stronger citations where PubMed surfaced better evidence.

---

## Recommended next actions for the user (~30 min)

1. **Review Part C (2 strains)** — read the abstracts on PubMed, confirm strain is discussed. Takes ~5 min. Flip sign-off if clean; leave false if not.
2. **Review Part B (12 strains, focus on the 9 swap candidates)** — for each, decide swap-or-keep based on clinical relevance. Takes ~20 min.
3. **Flip `dr_pham_signoff: true` on the 12 weak strains** after Part B review (with or without PMID swap).
4. **(Optional) Loop Dr Pham** — for the 3 asterisked Part A strains where she tagged narrative/animal "strong", ask her whether she wants to re-classify or keep; her call.

All 4 actions can be done by editing `scripts/data/clinically_relevant_strains.json` directly, or delegate back to the agent with specific swap instructions.

---

## Addendum — Clinical validation pass (added 2026-04-21 per clinical-reviewer feedback)

Title match is a necessary-but-not-sufficient check. After the clinical reviewer flagged that "title match ≠ clinical relevance," a second validation pass was run against abstracts (not just titles) for the 14 non-flipped strains + the 9 stronger-candidate swaps.

### 4-question framework (applied to abstracts)

For each citation:

1. **Q1 Strain explicit** — is the specific strain code (not just genus/species) named in the abstract?
2. **Q2 Outcome relevant** — does the abstract discuss the claimed `indication_primary`?
3. **Q3 Human clinical** — is this a human trial (RCT / clinical / meta-analysis) vs. animal / in-vitro?
4. **Q4 Dose mentioned** — is a specific CFU dose quantified in the abstract?

Scoring: 4/4 → `high`, 3/4 → `moderate`, ≤2 → `weak`.

Results now live on every non-flipped strain in `clinically_relevant_strains.json` under `evidence.clinical_validation` + `evidence.clinical_support_level`.

### Findings

| Count | Distribution |
|---|---|
| 14 current citations validated | **all scored `weak`** (0 high, 0 moderate) |
| 7 swap candidates validated (2 EFetch-missing) | 5 scored `moderate`, 2 scored `weak` |
| Abstracts where dose is quantified (Q4) | **2/21 (~10%)** — abstract-only dose detection is inherently limited; full-text would do better |

### Why everything scored weak at abstract level

- **Q4 (dose)** fails almost universally. Abstracts summarize outcomes, not always doses. This is a known limitation of abstract-only validation. Full-text PDF review would likely lift several strains to `moderate`.
- **Q1 (strain explicit)** fails when abstracts use species names or shorthand rather than the strain code (e.g. "L. rhamnosus" instead of "Lactobacillus rhamnosus GG").
- **Q3 (human clinical)** honestly flags animal-model studies as NO.

### What this means for the swap decisions

The 5 moderate-scoring swap candidates are **legitimate upgrades** over the current weak-citation PMIDs. Even though they don't hit `high`, moving weak → moderate is a real evidence-quality gain.

| Strain | Recommend | Reason |
|---|---|---|
| L. reuteri Prodentis | **SWAP** → PMID 23176716 | Current scores weak (no outcome match); swap scores moderate (3/4) |
| B. coagulans Unique IS-2 | **SWAP** → PMID 35249118 | Current weak (animal, no outcome match); swap moderate (3/4 RCT) |
| B. breve M-16V | **SWAP** → PMID 28796951 | Current weak (mixed-strain fever study); swap is a strain-specific systematic review, moderate (3/4) |
| L. gasseri SBT2055 | **SWAP** → PMID 23614897 | Current weak (animal); swap moderate RCT (3/4) |
| L. gasseri BNR17 | **SWAP** → PMID 29688793 | Current weak (limited); swap moderate RCT (3/4) |
| L. acidophilus NCFM | **KEEP** | Swap candidate also scored weak (3/4 but no Q1) — no net improvement |
| B. subtilis DE111 | **KEEP** | Same — swap also weak at abstract level |
| B. lactis Bl-04 | **KEEP** | No stronger candidate existed |
| L. fermentum ME-3 | **KEEP** | No stronger candidate existed |
| B. longum 1714 | **KEEP** | No stronger candidate existed |
| L. acidophilus DDS-1 / B. lactis UABla-12 | **KEEP PMID, RE-TAG** | Same multi-strain study; keep PMID, reclassify `type: "multicenter_clinical_study"` instead of `limited_or_non_clinical_source` |

### Recommendation on `dr_pham_signoff` for the 14

**Do NOT auto-flip any of them** based on this pass — all 14 score `weak` at abstract-level validation. Options per strain for Dr Pham or user review:

- **Keep `dr_pham_signoff: false` + honest `clinical_support_level: weak`** — scorer caps contribution at 50% per E1.3.2 design; product still scored, just conservatively
- **Or flip to true AFTER a full-text review** confirms dose + outcome alignment, and upgrade `clinical_support_level` to `moderate`/`high` based on that read

Either way, no change to the pipeline code is needed. The scorer respects `clinical_support_level` automatically.

### Permanent invariant added to Sprint E1

E1.3.2 now requires the `clinical_validation` block + `clinical_support_level` on every strain before the scorer will use its thresholds. See sprint doc.

---

## Future clinical-grade improvements (post-Sprint-E1 backlog)

Per clinical-reviewer's 2026-04-21 follow-up ("clinically defensible, production-ready at grade A — here's what would get us to A+"). These are **not sprint blockers** — they're roadmap items captured so they don't get lost.

### FCI-1 — Split `weak` into `weak_data_gap` vs `weak_evidence`

**Why it matters:** currently `weak` collapses two different clinical realities:

- **`weak_data_gap`** — abstract didn't quote the dose (Q4 NO), but the study may actually be strong at full-text level. This is a *data-retrieval limitation*, not a *clinical limitation*.
- **`weak_evidence`** — the study is genuinely thin: animal-only, narrative review, wrong population, or surrogate endpoints. This is a *real limitation* that should cap scoring harder.

**Change:**
```json
"clinical_support_level": "high | moderate | weak_data_gap | weak_evidence"
```

Scorer tiers: `high` = 100% / `moderate` = 75% / `weak_data_gap` = 65% / `weak_evidence` = 40%.

**Effort:** ~0.5 day. Belongs in Phase 5 observability or an E2 follow-up sprint.

### FCI-2 — Structural `is_single_strain_study` flag

**Why it matters:** multi-strain RCTs can't cleanly attribute an outcome to any single strain. E.g., Dr Pham's `L. acidophilus DDS-1` + `B. lactis UABla-12` share PMID 32019158 — a combined-strain study. The current classification is manual.

**Change:**
```json
"evidence": {
  ...,
  "is_single_strain_study": true | false,
  "study_strain_count": 1 | 2 | ...
}
```

Scorer rule: if `is_single_strain_study == false`, automatically downgrade single-strain-attributed tier by one level.

**Effort:** ~1 day. Needs Dr Pham input on which studies are single-strain vs. combined.

### FCI-3 — `population_generalizable` guardrail on moderate+ tiers

**Why it matters:** a "moderate" citation can still mislead if it's on a niche population (e.g. only geriatric IBD patients) and our product is sold to general consumers.

**Change:**
```json
"evidence": {
  ...,
  "population_generalizable": true | false,
  "population_notes": "mixed adults 18-65 | elderly only | pregnancy | pediatric | ..."
}
```

Scorer rule: if `population_generalizable == false`, cap contribution at 60% of tier even when `clinical_support_level == moderate` or `high`.

**Effort:** ~1 day. Dr Pham authoring input per citation.

### FCI-4 — Full-text dose extraction (the 10x unlock)

**Why it matters:** abstracts almost never quote CFU doses (Q4 NO in ~90% of our sample). Full-text PDFs do. This is the single biggest upgrade available — moves many strains weak_data_gap → moderate, moderate → high.

**Change:** add `scripts/api_audit/probiotic_fulltext_dose_extraction.py` that:
1. Fetches full-text PDFs where open-access
2. Regex-scans Methods section for CFU dose patterns
3. Populates `evidence.studied_dose_cfu` and `evidence.dose_alignment: "aligned | underdosed | overdosed | unknown"`
4. Feeds `clinical_validation.q4_dose_mentioned` with full-text-verified answer

**Effort:** ~1–2 weeks. Needs PDF-fetching infrastructure (unpaywall API or similar), regex-tuning per journal format, handling of paywalled studies.

**Expected impact:** lift ~30% of weak citations to moderate when the dose was in full text but not abstract. True evidence-quality upgrade, not just taxonomy tidying.

### Grade trajectory

Per clinical-reviewer evaluation:
- Pre-validation: A- (operational, not yet clinician-grade)
- Post-validation (current state): **A (clinically defensible, production-ready)**
- With FCI-1/2/3/4 shipped: A+ (competitive moat)

**Sprint E1 ships at grade A.** FCI-1 through FCI-4 are Phase 5 / follow-up sprint scope. None block Sprint E1 kickoff or public-beta readiness; they extend the "trust moat" post-launch.

---

## Addendum 2 — Clinical-reviewer verdicts on the 5 proposed swaps (2026-04-21, late)

After the 4-question validation report, the clinical reviewer did a full-text read on each proposed swap. API-verified via PubMed EFetch on 2026-04-21. Verdicts captured in `evidence.stronger_candidate.reviewer_verdict` on each strain.

### Final swap decisions

| Strain | Swap Candidate PMID | Reviewer Verdict | API Confirms? | Action on kickoff |
|---|---|---|---|---|
| L. reuteri Prodentis | 23176716 | **SWAP APPROVED** — RCT, periodontal, statistically significant | ✅ `statistically significant` in abstract | Execute swap; `clinical_support_level` → moderate |
| B. coagulans Unique IS-2 | 35249118 | **SWAP APPROVED** — RCT, 2B CFU dose | ✅ `2 billion CFU` in abstract | Execute swap; `clinical_support_level` → moderate |
| B. breve M-16V | 28796951 | **SWAP REVERSED** — systematic review concludes "very low" quality, "no significant benefits" | ✅ `very low` AND `no significant` both present in abstract | Keep current PMID 40085083; stay weak |
| L. gasseri SBT2055 | 23614897 | **SWAP APPROVED** — RCT, abdominal adiposity reduction | ✅ RCT pubtype confirmed | Execute swap; `clinical_support_level` → moderate |
| L. gasseri BNR17 | 29688793 | **SWAP APPROVED** — RCT, visceral fat in obese adults | ✅ RCT pubtype confirmed | Execute swap; `clinical_support_level` → moderate |

**Net result:** 4 swaps confirmed, 1 swap reversed.

### Why the B. breve M-16V reversal matters

The abstract-only 4-question framework **wrongly upgraded** this strain from weak → moderate. It correctly detected that the PMID is a strain-specific systematic review (Q1-Q3 = YES) but missed that the review's *conclusion* is negative. This is exactly the gap the reviewer flagged: *"Finding an RCT ≠ better evidence automatically."* Abstract conclusions are often not captured by per-signal extraction.

Encoded as `stronger_candidate.reviewer_verdict: "REVERSED"` with note explaining the reasoning. This creates an audit trail for future reviewers/agents: the 4-question framework passed, but a full-text read overruled it. Good evidence for FCI-4 (full-text extraction) prioritization.

### Reviewer's KEEP notes on 3 additional strains

| Strain | Reviewer note | Encoded on |
|---|---|---|
| L. acidophilus NCFM | Often studied in multi-strain blends, rarely strong solo. Keep weak. | `evidence.clinical_reviewer_note` |
| B. lactis Bl-04 | Same — multi-strain context. Keep weak. | `evidence.clinical_reviewer_note` |
| B. subtilis DE111 | Swap candidate (PMID 36790091) is niche ileostomy population — not generalizable. Keep. | `evidence.clinical_reviewer_note` |

### One correction to the reviewer

The reviewer cited **PMID 25727267** as additional supporting evidence for L. reuteri Prodentis (claimed peri-implant mucositis RCT). API verification on 2026-04-21 shows PMID 25727267 is actually *"Health- and vegetative-based effect screening values for ethylene"* — a chemistry paper in *Chemico-biological interactions*, not a probiotic study. Likely a typo or copy-paste error on the reviewer's end.

The primary swap PMID 23176716 is independently API-verified and sufficient for the swap. Flagged on `_metadata.reviewer_note_2026_04_21` in the JSON so it doesn't get forgotten next cycle.

### What this means for Sprint E1 execution

At Sprint E1 kickoff (E1.3.2), the 4 approved swaps execute as a small data-file PR:

1. Swap 4 PMIDs on the named strains
2. Update `evidence_strength`: weak → medium
3. Update `clinical_support_level`: weak → moderate
4. Set `dr_pham_signoff: true` on those 4 (reviewer-approved)
5. Leave B. breve M-16V untouched (keep PMID, keep weak)
6. Leave the 7 other weak strains untouched (keep `dr_pham_signoff: false`, keep weak)
7. Leave the 2 no-match medium strains pending Dr Pham's final abstract read

Net post-kickoff state: **32 signed-off (28 + 4 newly-approved), 10 pending** (7 weak + 2 no-match + 1 M-16V reversal).

---

_Generated 2026-04-21 by strain-verification pass during Sprint E1 planning. Clinical validation addendum added after clinical-reviewer feedback. Future-improvements section added after clinical-reviewer's nuance pass. Final reviewer verdicts applied 2026-04-21 (late) after full-text read on the 5 proposed swaps._
