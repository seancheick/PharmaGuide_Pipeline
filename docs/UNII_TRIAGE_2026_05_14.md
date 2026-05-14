# UNII Data-Quality Triage — 2026-05-14

## Context

Generated as Sprint 2 prep for the UNII-first matching implementation
(see `~/.claude/plans/goofy-foraging-neumann.md`). The
`audit_unii_data_quality.py` script with FDA cache + CUI exoneration
identified 21 SAME_UNII_DIFFERENT_NAMES findings — entries across our
reference DBs sharing the same FDA UNII but with materially different
`standard_name`s and no exoneration signal.

Once UNII becomes Tier-0 in the matcher, a wrong UNII becomes much more
dangerous than a wrong alias because it can override name/context. This
document triages every finding to bug or not-bug, with FDA-cache evidence,
so we don't ship UNII-first matching on top of identity bugs.

## Pre-Sprint-1 blocker rule (per user direction 2026-05-14)

> No SAME_UNII_DIFFERENT_NAMES critical finding may remain in the
> audit's post-exoneration output unless:
> 1. It is in the explicit exoneration allowlist
>    (`scripts/data/unii_exoneration_allowlist.json`),
> 2. It includes rationale,
> 3. It includes FDA canonical name,
> 4. It has a regression test
>    (`scripts/tests/test_unii_exoneration_allowlist.py`).
>
> Sprint 1 (UNII-first matching) may not ship until this rule is
> satisfied — i.e., either zero critical findings remain, or every
> remaining critical finding has explicit allowlist coverage with
> the four required fields.

## Audit baseline

- Source report: `reports/unii_data_quality_20260514_075416.md`
- 21 critical SAME_UNII_DIFFERENT_NAMES findings
- 34 exonerated by FDA cache / CUI (legitimate synonyms — see allowlist)

## Triage method

For each finding:
1. Look up the UNII in `fda_unii_cache.json::unii_to_name` — that's the
   FDA's canonical name for that substance
2. Compare against each entry's `standard_name` and the chemical/botanical
   meaning of the entry
3. If FDA's canonical disagrees with one of the entries, that entry has
   a wrong UNII → **BUG**
4. If FDA's canonical agrees with all entries' meanings (same compound,
   different names) → **NOT A BUG** (legitimate cross-file synonym)

When FDA cache has no generic / class-level UNII for an entry that is
itself a generic/class concept, the entry should be **`governed_null`**
rather than carrying a nearby specific UNII (per user direction).

## Verdict summary

| Verdict | Count | Action |
|---|---|---|
| Bug — governed_null fix | 7 | One atomic commit each |
| Bug — wrong UNII, replace with verified correct UNII | 3 | One atomic commit each |
| Not a bug — same compound, different names/contexts | 11 | Add to exoneration allowlist with rationale + FDA canonical |

## Detail — Bugs requiring fix (10)

### Governed-null fixes (7)

For each: set `external_ids` to `{}` and add `cui_status: governed_null`
plus a `cui_note` explaining why no single UNII applies.

| # | UNII (current, wrong) | FDA canonical | Bug entry | Why governed_null is right |
|---|---|---|---|---|
| 1 | `3NXW29V3WO` | HYPROMELLOSES (HPMC) | `other_ingredients.json::OI_CAPSULE_GENERIC` | Generic "Capsule" can be gelatin, HPMC, pullulan, etc. No single UNII covers the class. |
| 2 | `89NA02M4RX` | PECTIN | `ingredient_quality_map.json::prebiotics` | "Prebiotics" is an ingredient CLASS (inulin, FOS, GOS, pectin, beta-glucan, etc.). Pectin is one prebiotic — parent shouldn't carry a child's UNII. |
| 3 | `OP1R32D61U` | MICROCRYSTALLINE CELLULOSE | `other_ingredients.json::PII_VEGETABLE_CELLULOSE` | "Vegetable Cellulose" is generic. FDA cache has no generic "cellulose" UNII — only specific forms (MCC, powdered, hydroxypropyl-, etc.). |
| 4 | `331KBJ17RK` | CANOLA OIL | `other_ingredients.json::PII_CANOLA_SOURCE_DESCRIPTOR` | A pure source-descriptor entry. FDA cache has no "canola" descriptor UNII (only canola oil, brassica napus whole). Descriptors should not anchor identity to a specific oil product. |
| 5 | `817L1N4CKP` | MALIC ACID | `other_ingredients.json::NHA_MALATE_GENERIC` | Generic "Malate" is ambiguous between malate ions, malate salts, and malic acid forms. FDA cache has no generic malate UNII — only specific salts (calcium malate, etc.) and the acid form. |
| 6 | `2G86QN327L` | GELATIN, UNSPECIFIED | `ingredient_quality_map.json::collagen` | This UNII is FDA's identifier for gelatin (denatured collagen). FDA cache has no generic "collagen" UNII — only source-specific (bovine type I, marine, human placenta, etc.). Per user direction: govern-null rather than blindly assign a nearby protein UNII. Score specific collagen forms separately later. |
| 7 | `8617Z5FMF6` | WHEY | `ingredient_quality_map.json::milk_basic_protein` | MBP is a class/fraction of basic isoelectric proteins from milk (lactoferrin, lactoperoxidase, etc.) — NOT whey protein. Not present in FDA cache as a discrete entry. Per user direction: govern-null. |

### Correct-UNII replacement fixes (3)

For each: replace the wrong UNII with the FDA-verified correct one.

| # | Current UNII (wrong) | Correct UNII | FDA canonical for correct | Bug entry | Why the fix |
|---|---|---|---|---|---|
| 8 | `CT03BSA18U` (SAMBUCUS NIGRA FLOWERING TOP) | `BQY1UBX046` | EUROPEAN ELDERBERRY | `ingredient_quality_map.json::elderberry` | Reclassified from "possible" to "likely" per user direction: part-specific botanical mismatch is exactly what UNII-first amplifies. IQM:elderberry refers to the fruit, not flowering tops. |
| 9 | `CT03BSA18U` (SAMBUCUS NIGRA FLOWERING TOP) | `BQY1UBX046` | EUROPEAN ELDERBERRY | `botanical_ingredients.json::elderberries` | Same as above — plural form of the fruit, not flowering tops. (`elder_blossom` correctly stays on the flowering-top UNII.) |
| 10 | `S2D77IH61R` (FRANGULA ALNUS BARK) | `KD27950XHY` | RHAMNUS CATHARTICA BARK | `botanical_ingredients.json::buckthorn_bark` | Buckthorn (Rhamnus cathartica) and Frangula (Frangula alnus, "alder buckthorn") are different plant species. (`frangula_bark` correctly stays on the Frangula UNII.) |

## Detail — Not bugs (exoneration allowlist, 11)

These are intentional cross-file modeling of the same FDA-cataloged
substance. Sprint 1's priority order (IQM > standardized > botanical >
other) resolves all of them correctly at runtime. They go into the
**exoneration allowlist** with rationale + FDA canonical name + regression
test coverage.

| # | UNII | FDA canonical | Entries | Rationale (exoneration reason) |
|---|---|---|---|---|
| 11 | `3OWL53L36A` | MANNITOL | `PII_PARTECK`, `PII_PEARLITOL` | Both branded mannitol excipients (Parteck = Merck, Pearlitol = Roquette) |
| 12 | `3VMW64U790` | CISSUS QUADRANGULARIS WHOLE | `winged_treebine`, `cissus_quadrangularis` | Common (winged treebine) vs Latin (Cissus quadrangularis) name for the same plant |
| 13 | `50JZ5Z98QY` | MARITIME PINE | `pine_bark_extract` ×2, `pycnogenol` | All maritime pine bark extract (Pycnogenol is the Horphag-branded form) |
| 14 | `5EVU04N5QU` | CITRUS AURANTIUM DULCIS (ORANGE) FRUIT POWDER | `orange`, `NHA_ORANGE_CRYSTALS`, `NHA_ORANGE_FLAVOR` | All derived from the same FDA-cataloged orange fruit powder |
| 15 | `714783Y9Z0` | SALVIA MILTIORRHIZA WHOLE | `danshen`, `salvia_miltiorrhiza` | Common Chinese name (Danshen) vs Latin (Salvia miltiorrhiza) |
| 16 | `7797M4CPPA` | N,N-DIMETHYLGLYCINE | `dimethyl_glycine` (IQM), `OI_DIMETHYLGLYCINE` (other) | Same compound, IQM is active-scoring entry, other is inactive-recognition entry. Different roles, single chemistry. |
| 17 | `A1ST9M22TO` | KAEMPFERIA PARVIFLORA WHOLE | `kaempferia_parviflora` (IQM), `black_ginger` (botanical) | Latin name (Kaempferia parviflora) vs common name (Black Ginger) for the same plant |
| 18 | `C5529G5JPQ` | GINGER | 6 ginger-related entries across all files | All Zingiber officinale, intentional separate modeling for scoring context (raw, extract, powder, flavor) |
| 19 | `G199I91G4B` | CONJUGATED LINOLEIC ACID | `cla` (IQM), `OI_CLA_OIL_INACTIVE` (other) | Same compound, two roles (active scoring vs inactive recognition) |
| 20 | `K48IKT5321` | CLOVE | `cloves` (botanical), `PII_CLOVE_POWDER` (other) | Same spice (Syzygium aromaticum), two contexts |
| 21 | `T538276W1L` | ISATIS TINCTORIA WHOLE | `isatis` (IQM), `woad` (botanical) | Latin name (Isatis tinctoria) vs common name (Woad) for the same plant |

NOTE: `PQ6CK8PD0R` (ASCORBIC ACID) — `vitamin_c` (IQM) + `OI_ASCORBIC_ACID_PRESERVATIVE` (other) is also exonerated (same compound, two roles) — included in allowlist as the 12th entry for completeness even though it's not in the audit's critical bucket (it had a substring relationship that pre-empted the critical classification).

## Action plan (12 atomic commits)

### Phase 1: Audit infrastructure (1 commit)
1. **Commit A**: audit script + triage doc + exoneration allowlist + test

### Phase 2: governed-null fixes (7 commits, simplest first)
2. **Commit B**: `OI_CAPSULE_GENERIC` → governed_null
3. **Commit C**: `IQM:prebiotics` → governed_null
4. **Commit D**: `PII_VEGETABLE_CELLULOSE` → governed_null
5. **Commit E**: `PII_CANOLA_SOURCE_DESCRIPTOR` → governed_null
6. **Commit F**: `NHA_MALATE_GENERIC` → governed_null
7. **Commit G**: `IQM:collagen` → governed_null
8. **Commit H**: `IQM:milk_basic_protein` → governed_null

### Phase 3: correct-UNII replacements (3 commits)
9. **Commit I**: `IQM:elderberry` → BQY1UBX046
10. **Commit J**: `botanical:elderberries` → BQY1UBX046
11. **Commit K**: `botanical:buckthorn_bark` → KD27950XHY

### Phase 4: gate verification (re-run audit)
After all 10 data fixes, re-run `audit_unii_data_quality.py` and confirm
critical count is 0 (or all remaining are in the exoneration allowlist).

### Phase 5: Sprint 1 (separate from this triage)
Implement UNII-first matching per the plan now that the data baseline
is clean.
