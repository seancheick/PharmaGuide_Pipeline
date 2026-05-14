# UNII Backfill — Deferred Entries (Sprint 2 closure)

**Created:** 2026-05-14 (Sprint 2 close)
**Owner:** Sean Cheick
**Status:** Sprint 2 complete; this file catalogs what was deliberately
deferred and the policy that governs future backfills.

## Policy in force (set during Sprint 2)

> **UNII backfill requires real-world DSLD consensus, not just FDA-name
> exactness.**
>
> An FDA-cache name match alone is insufficient evidence to anchor an
> entry's `external_ids.unii`. The bar is:
>
> 1. FDA cache match (exact on standard_name OR an alias), **AND**
> 2. **≥5 DSLD products** consensus tagging that ingredient name with the
>    same UNII across at least 2 brands (the more the better)
>
> When only one of those signals is present, the entry is **deferred
> for one-by-one review**, not auto-applied.
>
> **Alt-UNII cases** (more than one candidate UNII surfaces during the
> proposal) ALWAYS require manual identity review before apply,
> regardless of signal strength. The script flags these with the
> `alternate_uniis_seen` field in the proposal evidence block.
>
> **Class concepts** (Vitamin K, prebiotics, collagen, etc.) NEVER get a
> single-form UNII backfilled at the class level. They use a `cui_note`
> documenting the class structure; form-level UNIIs go in `forms[]` when
> verified individually.

This policy is encoded in the script's confidence tiers:
- **HIGH**: FDA match + ≥5 DSLD consensus → auto-eligible
- **MEDIUM**: only one signal → deferred for one-by-one review
- **LOW**: weak signals (≥1 brand, no FDA exact) → deferred

The pre-apply regression guard (also added during Sprint 2) refuses any
apply that would introduce a new `SAME_UNII_DIFFERENT_NAMES` critical
finding, regardless of confidence tier.

## What shipped (7 backfills)

Each entry below was applied + committed atomically + verified by the
audit:

| Entry | UNII | Signal strength |
|---|---|---|
| `other:PII_TRICALCIUM_PHOSPHATE` | `K4C08XP666` | FDA exact on standard_name + 176 products / 8 brands |
| `other:OI_RIBOFLAVIN_COLORANT` | `TLM2976OFR` | FDA alias + 1297 products / 15 brands |
| `other:OI_ROSE_HIPS_INACTIVE` | `3TNW8D08V3` | FDA alias + 11 products / 2 brands |
| `botanical:acerola_cherry` | `XDD2WEC9L5` | FDA alias + 22 products / 4 brands |
| `iqm:5_htp` | `9181P3OI6N` | 58 products / 6 brands (no FDA exact) |
| `iqm:d_aspartic_acid` | `4SR0Q8YD1X` | 18 products / 4 brands |
| `other:PII_PURIFIED_FISH_OIL` | `XGF7L72M0F` | 20 products / 4 brands |

Plus 1 governance annotation:
- `iqm:vitamin_k` — `cui_note` added documenting intentional class-level
  no-UNII (mirrors prebiotics + collagen pattern)

## Deferred — Tier C (12 entries, FDA-exact + zero DSLD usage)

These entries have FDA-cache exact name matches (the species/strain
names ARE the FDA canonical) but zero products in the current DSLD
staging tree disclose them. **Not rejected** — the FDA identity is
real. They're held because the new policy requires real-world product
corroboration before anchoring them.

Reviewer's next-touch checklist:
1. Confirm the supplement-grade product class matches the FDA UNII
   (some species have whole-plant vs leaf vs root variants with
   different UNIIs — the dry-run only returns one).
2. Cross-check with another source (PubChem, ChEMBL) if the entry is
   a chemical compound; with USDA / EPPO / ITIS if it's a botanical.
3. Apply individually with `--apply --entry-ids <ID>` and verify the
   pre-apply guard remains SAFE.

| Entry (file) | Proposed UNII | FDA canonical match | Notes |
|---|---|---|---|
| `alaria_esculenta` (botanical) | `EJ9JK8J58D` | "ALARIA ESCULENTA" | Seaweed; uncommon in catalogs |
| `collard_greens` (botanical) | `PVL385313S` | "COLLARD GREENS" | Brassica oleracea var. acephala |
| `ecklonia_kurome` (botanical) | `802YF989GT` | "ECKLONIA KUROME" | Brown algae |
| `ecklonia_radiata` (botanical) | `QVY0X8DRIA` | "ECKLONIA RADIATA" | Brown algae |
| `leek` (botanical) | `RCU76P419D` | "LEEK" | Allium ampeloprasum |
| `lima_bean` (botanical) | `112YH1ZMX2` | "LIMA BEAN" | Phaseolus lunatus |
| `tamarind` (botanical) | `2U9H66X7VX` | "TAMARIND" | Tamarindus indica |
| `kluyveromyces_marxianus` (iqm) | `0N7WQ9T9ZQ` | "KLUYVEROMYCES MARXIANUS" | Yeast |
| `lactobacillus_crispatus` (iqm) | `QX2H2M2084` | "LACTOBACILLUS CRISPATUS" | Probiotic strain |
| `lactobacillus_jensenii` (iqm) | `2DNC474OP6` | "LACTOBACILLUS JENSENII" | Probiotic strain |
| `lactococcus_lactis` (iqm) | `F1A0PSN10V` | "LACTOCOCCUS LACTIS" | Probiotic strain |
| `leuconostoc_mesenteroides` (iqm) | `2FC65L33PK` | "LEUCONOSTOC MESENTEROIDES" | Probiotic strain |

(All 12 were applied then reverted in Sprint 2 with explicit
"held pending 1-by-1 review" rationale. See commits `f654e5a` →
`a105e0b`.)

## Deferred — Yellow-flag alt-UNII cases (2 entries)

Multiple candidate UNIIs surfaced during proposal generation. Either
the FDA cache has source-form variants (broccoli sprout vs sprout
extract, etc.) or the script's alias expansion hit multiple
authoritative entries. **Cannot auto-apply** — needs human identity
verification.

| Entry | Primary proposed | Alt UNII surfaced | Resolution needed |
|---|---|---|---|
| `botanical:broccoli_sprout` | `128UH9LOAE` | `TRV7Y4GE8Q` | Which one is the supplement-grade form? Likely both are correct for different products (sprout vs sprout extract). |
| `botanical:japanese_knotweed` | `7TRV45YZF7` | `1VDG5Y5HS6` | Polygonum cuspidatum has root-vs-whole-plant variants. Need to confirm which the entry covers. |

## Deferred — Other medium-confidence singles (4 entries)

Single-brand or low-product DSLD signals. Held because cross-brand
consensus is the safer corroboration:

| Entry | Proposed UNII | Signal | Notes |
|---|---|---|---|
| `iqm:lactobacillus_bulgaricus` | `HU1W4L947H` | 52 products / **2 brands** | Heavy concentration in Garden_of_life — single-source risk |
| `iqm:sophora_japonica` | `644C3CSB6E` | 15 products / **1 brand** (Thorne) | Single-brand risk |
| `other:PII_DIASTASE` | `A370TYK9KO` | 15 products / 1 brand (GNC) | Single-brand risk |
| `other:PII_XYLANASE` | `S2MZZ5DR1O` | 11 products / 1 brand (GNC) | Single-brand risk |

## Deferred — Tier D low-confidence (4 entries)

| Entry | Proposed UNII | Signal |
|---|---|---|
| `standardized_botanicals:olive_leaf` | `MJ95C3OH47` | 5 products / 3 brands, no FDA |
| `standardized_botanicals:rosehip` | `3TNW8D08V3` | 6 products / 1 brand, no FDA |
| `iqm:saccharomyces_boulardii` | `978D8U419H` | 5 products / 2 brands, no FDA |

(plus 33 low-confidence proposals from the dry-run report not yet
itemized here.)

## Blocked by regression guard (6 entries)

These each had a candidate UNII that would have introduced a new
`SAME_UNII_DIFFERENT_NAMES` critical finding. The guard correctly
refused. They need either an exoneration allowlist entry OR a
de-collision fix BEFORE they're considered for apply.

| Entry | Proposed UNII | Would collide with |
|---|---|---|
| `other:NHA_CALCIUM_CASEINATE` | `48268V50D5` | `iqm:casein`, `other:PII_MICELLAR_CASEIN` |
| `standardized_botanicals:olive_leaf_extract` | `MJ95C3OH47` | `botanical:olive_leaf_powder` |
| `standardized_botanicals:rosehip` (when paired with applied OI_ROSE_HIPS_INACTIVE) | `3TNW8D08V3` | `botanical:rose_hips` |
| `botanical:chili_pepper` | `X72Z47861V` | `other:OI_PAPRIKA_EXTRACT` (different Capsicum cultivars) |
| `standardized_botanicals:citrus_bergamot_extract` | `39W1PKE3JI` | `botanical:bergamot_essential_oil` |
| `standardized_botanicals:coffeeberry` / `neurofactor` | `HOX6BEK27Q` | `iqm:coffee_fruit`, `botanical:coffee_fruit` |

## Suggested next sprints

The user proposed two paths; both are viable and not mutually exclusive:

1. **Full-catalog rebuild with the new UNII-first matcher.** Run
   `clean → enrich → coverage_gate → score → build_final_db` across all
   21 brands so the live pipeline output picks up all Sprint 1.x + 2
   improvements (Tier-0 UNII matching, alternateNames fallback,
   ledger attribution, 7 new backfilled UNIIs). After verification,
   sync to Supabase so the Flutter app reflects the corrected scoring.
   This is the user-visible win.

2. **Manual review sprint for deferred Tier C + yellow-flag entries.**
   Walk the 12 Tier C + 2 yellow-flag + 4 single-brand + 4 Tier D
   entries one at a time with API verification (FDA, PubChem, etc.).
   Apply the ones that pass clinician/scientist sign-off. This converts
   the deferred backlog into more concrete UNIIs over time.

(2) is cheaper and more incremental; (1) ships the Sprint 1.x + 2
matcher improvements to users. Recommended order: (1) first to deliver
user-visible value, then (2) to grind down the deferred queue.
