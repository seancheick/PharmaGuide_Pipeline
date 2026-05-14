# Phase 2 Impact Report — Graduated `total_deduction_cap` Proposal

> **Status:** ANALYSIS ONLY. Phase 2 of [docs/handoff/2026-05-13_deduction_expl_proposal.md](2026-05-13_deduction_expl_proposal.md). Phase 1 (additive — 3 new codes + pediatric modifier) shipped 2026-05-14 in commit `4321137`. This document does NOT change [scripts/data/manufacture_deduction_expl.json](../../scripts/data/manufacture_deduction_expl.json) — it produces the impact report Sean asked for so he can decide whether to apply the graduated cap, and at what value.

---

## TL;DR

- **Current state:** 82 distinct manufacturers, all in *Trusted* (55, 67%) or *Acceptable* (27, 33%). **Zero** manufacturers in *Concerning* or *High Risk*. The static -25 cap is keeping repeat drug-spikers in the same band as quality-issue manufacturers.
- **Repeat Class-I actors today:** exactly **1** — Pure Vitamins and Natural Supplements, LLC (3 concurrent Class I sildenafil/tadalafil recalls in 2026, raw deduction -69 capped at -25 → score 75 *Acceptable*).
- **The middle tier (-35 for 2 Class-I in 3yr) is purely forward-looking** — zero manufacturers hit this bucket today.
- **Recommendation:** **`-50` cap for 3+ Class-I in 3 years.** It puts Pure Vitamins on the *Concerning/High-Risk* boundary (score 50) — symbolically aligned with the 3-Class-I severity, without being draconian. Lower values (-40, -45) feel like half-measures given the egregiousness of the pattern.

---

## 1. Current score distribution (cap = -25)

| Band | Score window | Count | % |
|---|---|---:|---:|
| **Trusted** | ≥ 85 | 55 | 67.1% |
| **Acceptable** | 70–84 | 27 | 32.9% |
| **Concerning** | 50–69 | 0 | 0.0% |
| **High Risk** | ≤ 49 | 0 | 0.0% |

**Total:** 82 distinct manufacturers.

**Observation:** the floor at -25 means *no* current manufacturer can score below 75 regardless of how severe their violation record is. Pure Vitamins LLC has -69 in raw deductions (three -23 Class-I undeclared-drug recalls on the same day) — clipped to -25, they land at 75.

---

## 2. Class-I-in-3-years distribution

| Class-I count | Manufacturer count |
|---:|---:|
| 0 | 32 |
| 1 | 49 |
| 2 | **0** |
| 3+ | **1** |

**Distribution is bimodal.** Most manufacturers have 0 or 1 Class-I violations in the last 3 years. The "2 in 3yr" middle tier is empty today; the "3+ in 3yr" tier has exactly Pure Vitamins. The cap design needs to acknowledge that the *2-Class-I* tier is purely forward-looking — it's a deterrent threshold, not a tier with current population.

---

## 3. Simulated impact — three candidate cap values

All three schemes apply the same `-35` cap to manufacturers with `2 Class-I in 3yr` (the middle tier). They differ only at `3+ Class-I in 3yr`. Since no manufacturer has exactly 2 today, the only band movement under any scheme is Pure Vitamins LLC.

### Scheme A: `-40` for 3+ Class-I

| Band | Count | Δ from current |
|---|---:|---:|
| Trusted | 55 | 0 |
| Acceptable | 26 | **-1** |
| Concerning | 1 | **+1** |
| High Risk | 0 | 0 |

Pure Vitamins LLC: score 75 → **60** (`Acceptable` → `Concerning`).

### Scheme B: `-45` for 3+ Class-I

| Band | Count | Δ from current |
|---|---:|---:|
| Trusted | 55 | 0 |
| Acceptable | 26 | **-1** |
| Concerning | 1 | **+1** |
| High Risk | 0 | 0 |

Pure Vitamins LLC: score 75 → **55** (`Acceptable` → `Concerning`).

### Scheme C: `-50` for 3+ Class-I

| Band | Count | Δ from current |
|---|---:|---:|
| Trusted | 55 | 0 |
| Acceptable | 26 | **-1** |
| Concerning | 1 | **+1** |
| High Risk | 0 | 0 |

Pure Vitamins LLC: score 75 → **50** (`Acceptable` → `Concerning`, on the boundary to `High Risk`).

**All three schemes produce identical band distributions today.** The only difference is *how far* Pure Vitamins moves within `Concerning`.

---

## 4. Manufacturer band-change table

```
Manufacturer                                   CI/3y rawDed  cur  -40  -45  -50  Band path
─────────────────────────────────────────────────────────────────────────────────────────
Pure Vitamins and Natural Supplements, LLC      3   -69.0   75   60   55   50   Accept → Concern (all schemes)
```

**One manufacturer moves bands under any of the three schemes.** No other manufacturer is affected by the graduated cap — they all have ≤1 Class-I in 3 years and are unaffected by the new tiers.

---

## 5. To push Pure Vitamins LLC into `High Risk` band would require...

If the framework's design intent is that 3+ Class-I drug-spike recalls *can* land a manufacturer in High Risk (≤49), the cap needs to be **at most -51** (giving score 49). My read is this is NOT what Sean wants — violations alone shouldn't determine the whole trust outcome, since brand-side positives (transparency, third-party testing, longevity) live in other scoring sections.

The graduated cap should signal "this is a serious pattern" without forcing the entire trust score below the rejection threshold from violations alone.

---

## 6. Recommendation: `-50`

The three schemes are quantitatively similar today (all move Pure Vitamins to `Concerning`), so the choice is symbolic — what message does the cap send to a 3-recall manufacturer?

| Cap | Pure Vitamins score | Position in Concerning | Message |
|---:|---:|---|---|
| -40 | 60 | mid-band | "noticed, but still recoverable" |
| -45 | 55 | mid-low | "serious — needs corrective action" |
| **-50** | **50** | **boundary** | **"one more incident drops you into High Risk"** |

**My recommendation: -50.** Reasons:

1. **Boundary signaling.** Score 50 sits exactly at the *Concerning/High-Risk* line. A 4th Class-I would (under any continued-violations modifier — separate framework decision) push them over. The cap creates a "cliff edge" warning.

2. **Preserves the principle that brand-side positives matter.** -50 doesn't auto-tank to High Risk — it floors the violations contribution, leaving room for other scoring sections to contribute. -55 or lower would force `High Risk` regardless of brand-side data, which feels overreaching for a violation-only signal.

3. **Symmetry with the -25 default.** The proposed structure becomes `-25 / -35 / -50` — each step *doubles* the prior gap (10pt step then 15pt step). That cadence reads as "each tier is meaningfully more severe than the last." `-40` or `-45` produces less satisfying step sizes (`-10 / -15` or `-10 / -20`).

4. **Forward-looking deterrent.** Pure Vitamins is currently the only 3+ Class-I manufacturer. If 2026-27 brings more, -50 is the right anchor — it's punitive without being closer to a rejection band than violations alone justify.

---

## 7. Other items to revisit if/when Phase 2 lands

These are NOT recommendations to change Phase 2 — they're items that surfaced during the analysis and might be worth a separate proposal later:

1. **Reclassification of existing `CRI_UNDRUG` entries to `CRI_GLP1` / `CRI_ANABOLIC`.** Phase 1 added the new codes but did not retroactively reclassify the 37 existing `CRI_UNDRUG` entries. None of those entries are GLP-1 or anabolic today, but a sweep should be scheduled.

2. **`HIGH_MULT_CII` (Multiple Class II) and `MOD_CIII_MULT` modifiers are unused** but are auto-detected by the `repeat_violation` modifier in `fda_manufacturer_violations_sync.py`. Worth deciding if the explicit code adds value or can be retired (currently kept per Sean's "no retire" directive).

3. **Score-threshold review.** With graduated caps making `Concerning` non-empty, the verbal text of the `Concerning` band (`"Display warning - recent or multiple violations"`) might need a polish pass to match Dr Pham voice. Today the band has no occupants so the copy hasn't been user-tested.

4. **Modeling `2 Class-I in 3yr` deterrent strength.** Zero manufacturers occupy this tier today; the `-35` cap exists purely as a forward-looking threshold. Worth a follow-up after 6-12 months of sync runs to see if the tier gets populated.

---

## 8. If you approve `-50`

The implementation is ~30 lines and one commit:

1. Patch `scripts/data/manufacture_deduction_expl.json`:
   - Add `total_deduction_cap_graduated` block alongside `total_deduction_cap`
   - Bump `_metadata.version` to `2.2` + `last_updated` to today
   - Document the cap structure in `_metadata.version_history`

2. Update `scripts/api_audit/fda_manufacturer_violations_sync.py`:
   - In `recalculate_all_entries`, replace the static `-25` cap with a lookup that picks the appropriate cap based on the manufacturer's Class-I-in-3yr count
   - Add helper `_resolve_cap_for_manufacturer(manufacturer, all_entries, deduction_expl)`

3. Extend `scripts/tests/test_manufacture_deduction_expl_contract.py`:
   - Pin the graduated cap structure (-25 / -35 / -50)
   - Pin that `_metadata.version >= 2.2`

4. Update [.claude/skills/fda-weekly-sync/SKILL.md](../../.claude/skills/fda-weekly-sync/SKILL.md):
   - Document the new cap math for future sync runs

**Estimated impact:**
- 1 manufacturer (Pure Vitamins LLC) moves bands: `Acceptable (75)` → `Concerning (50)`
- All other 81 manufacturers unchanged
- All schema/strict-validator tests stay green (additive)

---

## 9. If you want a different cap value

Just replace `-50` with the chosen value in the implementation steps above. The impact analysis (section 3) shows the three candidate values all produce the same band distribution today; the choice is about message-strength signal, not population movement. My case for `-50` is in section 6, but `-45` is a defensible compromise if you want softer messaging.

Awaiting decision.
