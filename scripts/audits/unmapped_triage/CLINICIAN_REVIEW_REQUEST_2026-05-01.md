# Clinician Review Request — 2026-05-01

**To:** Dr. Pham (clinical reviewer)
**From:** PharmaGuide data team
**Subject:** Items requiring clinical sign-off from the unmapped ingredients audit
**Reference:** `scripts/audits/unmapped_triage/REMAINING_UNMAPPED_TEAM_GUIDE.md`

---

We just finished a 17-commit pass through 204 unmapped supplement ingredients. **Most are now resolved.** The items below either touch clinical safety or require your specialty judgment we can't confidently make from API data alone.

For each item we tell you (1) what it is, (2) what we tentatively did or chose to defer, (3) the specific question for you. Your call goes into the entry's `confidence_level` and locks it.

---

## 🩺 PRIORITY 1 — Probiotic strain safety review (4 items)

These are oral-cavity Streptococcus strains marketed as **BLIS-branded** probiotics (BLIS Technologies, NZ). Genus Streptococcus contains both probiotic and pathogenic species, so we cannot bulk-approve. Please verify each strain's documented safety profile before we add IQM entries.

| Strain | Marketing claim | Concern | Source product example |
|---|---|---|---|
| **S. rattus JH145™** | Oral health probiotic | S. rattus is dental-caries-associated; need confirmation JH145 is a non-cariogenic engineered/selected strain | BLIS oral-health blends |
| **S. uberis KJ2™** | Oral health probiotic | S. uberis is **historically a bovine mastitis pathogen**; need strict strain-level safety data for KJ2 in human use | BLIS oral-health blends |
| **S. oralis JH145™** | Oral health probiotic | S. oralis is a normal oral commensal but some strains opportunistic in immunocompromised; verify JH145 is a documented probiotic strain | BLIS oral-health blends |
| **S. oralis KJ3™** | Oral health probiotic | Same as above | BLIS oral-health blends |

**Also previously flagged (still pending):**
- **Enterococcus faecium** — VRE risk; some strains are gut probiotics, others nosocomial pathogens. Need strain-level approval.

**What we need from you:**
- Approve / Reject each strain for IQM inclusion
- If approved, indicate `bio_score` and `confidence_level` (`verified` if literature-backed, `inferred` if cautious-conservative)
- If rejected, we'll flag in `banned_recalled_ingredients.json` notes so future products listing them surface for review

---

## 🩺 PRIORITY 2 — SPM mapping policy validation (please verify)

We provisionally mapped **Resolvins**, **Protectins**, **Resolvin D5**, **Protectin DX** as **aliases on the existing 17-HDHA SPM precursor form** in the `omega_3` IQM parent.

**Our reasoning:**
- Most products labeling "Resolvins" / "Protectins" actually contain SPM **precursors** (HDHA, HEPE), not the actual short-lived endogenous resolvins. Stubbs et al. analysis cited in the existing entry supports this.
- Treating label claims as omega-3 precursor content avoids overclaiming.

**What we need from you:**
- Confirm this is clinically appropriate, OR
- Approve creating separate IQM entries for the 4 named compounds (Resolvin D5 has PubChem CID 24932575; Protectin DX has CID 11968800) with their own `bio_score` reflecting actual SPM bioactivity vs. precursor activity

**Commit reference:** `0e74c8e` (the alias addition is on form `17-hydroxy-docosahexaenoic acid (17-HDHA)` in `omega_3`)

---

## 🩺 PRIORITY 3 — Generic Algae Protein scoring (please validate conservatism)

We created a new IQM parent `algae_protein` for label-only listings without source disambiguation (Spirulina vs Chlorella vs Schizochytrium vs mixed).

**Our conservative choices:**
- `bio_score: 5` (low-moderate, reflecting source uncertainty)
- `score: 8` / `absorption: 0.2` range
- `confidence_level: "inferred"`
- Notes flag PMID:39610880 — chlorella whole-cell near-zero amino acid bioavailability — to anchor the conservative end

**What we need from you:**
- Confirm `bio_score=5` is appropriate for "source unspecified algae protein", OR
- Adjust to a different default (e.g., bio_score=7 if you assume commercial usage skews toward better-absorbed spirulina)
- Confirm the note text about chlorella whole-cell PK is accurate

**Commit reference:** `0e74c8e`

---

## 🩺 PRIORITY 4 — New botanical/IQM entries created this audit (please spot-check)

We created 9 new botanical entries and 1 new IQM parent during the strict-chemistry audit. Each has an API-verified UMLS CUI and (where available) UNII. Please spot-check the **clinical descriptions** in the `notes` field to make sure nothing overclaims:

| Entry | Latin | CUI | UNII | Concern to verify |
|---|---|---|---|---|
| `yangmei` (NEW) | Myrica rubra | C1688280 | — | Is the bioactive profile note (anthocyanins/cyanidin-3-glucoside/ellagic acid/myricetin) accurate? |
| `tu_fu_ling` (NEW) | Smilax glabra | C2810601 | — | TCM "clears damp-heat" indication wording — is this how you'd phrase it for a Western consumer app? |
| `sarsaparilla_honduran` (NEW) | Smilax officinalis | C3388298 | KDX23MP2GS | Should this be merged with `sarsaparilla` (Smilax ornata) commercially, or kept distinct as we have it? |
| `horse_gram` (NEW) | Macrotyloma uniflorum | C1477450 | 379916QREU | Ayurvedic kulthi/kulattha indication note — reasonable? |
| `butternut_squash` (NEW) | Cucurbita moschata | C0996747 | 6D4613H8ZL | Carotenoid/lutein/zeaxanthin profile — accurate? |
| `chamomile_essential_oil` (NEW) | Matricaria chamomilla | C0109265 | SA8AR2W4ER | Bioactives note (chamazulene, alpha-bisabolol, farnesene) accurate? |
| `bergamot_essential_oil` (NEW) | Citrus bergamia | C0105754 | 39W1PKE3JI | Photosensitivity caution from bergaptene — should this be elevated to a B1 safety penalty rather than just a note? |
| `nutmeg_essential_oil` (NEW) | Myristica fragrans | C0301248 | Z1CLM48948 | Myristicin/elemicin psychoactivity note — is the "≥5g whole nutmeg" threshold correct for safety messaging? |
| `geranium_essential_oil` (NEW) | Pelargonium graveolens | C0304136 | 3K0J1S7QGC | Multi-species genus note — ok? |
| `algae_protein` IQM (NEW) | (multi-source) | C0600607 | — | See PRIORITY 3 above |

**What we need from you:**
- For each, either ✅ (descriptions clinically accurate) or 📝 with proposed wording change
- Bergamot specifically: do furocoumarins warrant B1 penalty in supplement form, or only topical?
- Nutmeg specifically: confirm "≥5g whole nutmeg" psychoactive threshold

**Commits:** `4efa6be` (Myrica), `ba8fbe3` (audit batch), `295520a` (butternut), `e4eb91e` (EOs), `0e74c8e` (algae)

---

## 🩺 PRIORITY 5 — Source/form ambiguity policy

We have 1 unresolved item where we can't decide without your input:

**Glucosamine Salt** — products listing this without specifying HCl vs sulfate.

- HCl form has different bio_score and clinical evidence than sulfate form
- Strict same-compound rule says we shouldn't bulk-alias to one or the other

**What we need from you:**
- (A) Clinician policy: default to `glucosamine sulfate` (more clinically studied), or
- (B) Default to `glucosamine_hcl`, or
- (C) Leave unmapped pending product-specific verification

---

## 🩺 PRIORITY 6 — Branded blend headers (~20 items) — per-product child-disclosure check

Products with branded blends like "Wheybolic Protein Complex" (8×), "Lean Muscle Support", "N.O. Pump Charger", "Hardcore Test Amplifier", "Elite Pump Factor", "Hyper-Thermogenic Trigger", "Joint & Skin Support", "Advanced Power Maximizer", "Anabolic Muscle Primer", "Sustained Protein Blend", "PM Metabolic Optimizer", "Skin Structure & Antioxidant Support", "Thermo-Metabolic Activator", "Brain & Circulatory Support", and similar.

**This is mostly a data/parsing task** (verify against DSLD raw JSON whether each product discloses children rows or treats it as opaque), **but we wanted you to weigh in** on:

- Should we default to **opaque-blend treatment** (B5 transparency penalty fires) when a brand blend has no disclosed children, even if it's a recognizable trade name?
- Or should we maintain a curated allowlist of "known headers with verified children disclosed elsewhere on the label"?

Per existing memory `project_blend_classifier_4state.md`, we lean toward the schema-aware classifier (DSLD `category: "blend"` + `quantity.unit: "NP"` + `nestedRows`). But brand headers like "Wheybolic" might benefit from being on a curated header list.

---

## Workflow once you respond

For each item you approve:
1. We add the entry / alias / classification with `confidence_level: "verified"`
2. We document your sign-off in the entry's `clinician_review_notes` field
3. Atomic commit with reference to your review

For rejections:
1. We add to `banned_recalled` notes (if safety-relevant) or skip
2. Keep flagged in unmapped triage for product-specific decisions

---

## Reference files (in repo)

- `scripts/audits/unmapped_triage/REMAINING_UNMAPPED_TEAM_GUIDE.md` — full team guide with all 8 decision categories
- `scripts/audits/unmapped_triage/remaining_unmapped_2026-05-01.json` — machine-readable list of remaining items
- `scripts/audits/unmapped_triage/BLEND_HANDLING_POLICY.md` — 4-state classifier spec
- Recent commits 4efa6be, ba8fbe3, 556a5ae, 820749c, 295520a, 78fe738, 30bde6a, 0c9460f, f2e7af3, e4eb91e, 9c8409d, 0e74c8e — all carry detailed reasoning in commit messages

Reply with priorities ordered however works best for your time. Probiotic strain safety (Priority 1) is the most time-sensitive since those products are already in the pipeline.
