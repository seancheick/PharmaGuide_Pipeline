# ADR — Add `contamination_recall` as a 5th `ban_context` value

**Status:** Proposed — deferred to a future round
**Proposed by:** Dr. Pham (clinical review round 1, 2026-04-17)
**Accepted by:** pending
**Related files:**
- `scripts/data/banned_recalled_ingredients.json`
- `scripts/validate_safety_copy.py` (VALID_BAN_CONTEXTS set)
- `scripts/SAFETY_DATA_PATH_C_PLAN.md`

---

## Context

The current `ban_context` enum has 4 values:

| Value | Meaning |
|---|---|
| `substance` | The molecule itself is controlled/illegal |
| `adulterant_in_supplements` | Legitimate prescription drug found undeclared in supplements |
| `watchlist` | FDA warning letters, emerging concern |
| `export_restricted` | Restricted outside US, legal here |

During Dr. Pham's round-1 authoring of all 143 entries, she identified
a class that **none of these describes cleanly**: product-level
contamination recalls. Examples in the current data:

- Gold Star (contaminant-recalled)
- Hydroxycut (found laced with sibutramine)
- Jack3d (contained DMAA)
- OxyElite Pro (hepatotoxic contaminants)
- Purity (undeclared stimulants)
- ReBoost (contaminant recall)
- Rheumacare (contaminant recall)
- Rosabella Moringa (contaminant recall)
- Live it Up (contaminant recall)

For authoring round 1 she classified these as `substance` — the
closest fit — and flagged this as "worth a future ADR." She's right.

## Problem

`substance` means "the molecule is controlled." But for these entries:

- The **product** was recalled, not the molecule
- The **undeclared contaminant** is usually itself a separately-
  catalogued `adulterant_in_supplements` entry (sibutramine, DMAA, etc.)
- The user concern is *"this branded product was caught contaminated"*,
  not *"this chemistry is illegal"*

Classifying as `substance` overstates the regulatory weight on the
product name and duplicates the risk signal already carried by the
adulterant entry for the actual contaminant.

Classifying as `adulterant_in_supplements` misdirects — the product
IS the supplement, there's no "legitimate prescription" separator
to draw.

Classifying as `watchlist` is also wrong — these are actively recalled
products with completed FDA enforcement actions, not emerging concerns.

## Proposal

Add `contamination_recall` as the 5th `ban_context` value.

```python
VALID_BAN_CONTEXTS = {
    "substance",
    "adulterant_in_supplements",
    "watchlist",
    "export_restricted",
    "contamination_recall",  # NEW
}
```

### Semantic definition

> The entry is a **branded product** that was recalled after being
> found to contain one or more undeclared contaminants. The contaminant
> itself typically has its own `adulterant_in_supplements` entry; this
> entry exists so the product name matches in the app and the user
> sees "this product was recalled" separately from "this molecule is
> banned."

### Flutter copy rule

When `ban_context == "contamination_recall"`:

- **Banner:** Recall-framing, not substance-framing
  - "<product> was recalled after testing positive for <contaminant>"
- **Body:** Describe what was found, when the action was taken, and
  that the product is no longer authorized
- **Never:** "Stop and consult your doctor" (that's adulterant/substance
  copy — contamination-recall products shouldn't be in circulation)

### Validator rule additions

- `safety_warning` MUST mention a regulatory verb (`recalled`,
  `withdrawn`, `removed from market`, `FDA enforcement`) — the context
  is an administrative action, not a chemistry hazard
- MAY contain the name of the undeclared contaminant (often sibutramine,
  DMAA, etc.) — cross-referencing is allowed and clinically useful

## Migration plan

1. Extend the enum in `validate_safety_copy.py`
2. Dr. Pham reviews the ~10 entries currently marked `substance` that
   are actually contamination recalls:
   - `RECALLED_GOLDSTAR`, `RECALLED_HYDROXYCUT`, `RECALLED_JACK3D`,
     `RECALLED_OXYELITE`, `RECALLED_PURITY`, `RECALLED_REBOOST`,
     `RECALLED_RHEUMACARE`, `RECALLED_ROSABELLA_MORINGA`,
     `RECALLED_LIVEITUP`
   - Candidate list discovery: `grep -l "RECALLED_" + "status: recalled"`
3. Bump schema `5.2.0 → 5.3.0` on banned_recalled
4. Author/refine `safety_warning` copy on each to match the new
   contract (most entries will need only minor wording shifts)
5. Update Flutter render contract to branch on
   `ban_context == "contamination_recall"` → recall-voiced banner
6. Tests: new validator rules + Flutter rendering cases
7. Update `SAFETY_DATA_PATH_C_PLAN.md` §Ban-context matrix

## Non-goals for this ADR

- Handling product-level recalls that AREN'T contamination (e.g.,
  labeling violations, packaging defects) — those are genuinely
  different and out of scope here
- Merging with the separate `product_status: recalled` field — that
  signals DSLD-level product status and stays orthogonal

## Status

**Deferred.** Dr. Pham's round-1 classification as `substance` is
acceptable stopgap. This ADR captures the idea so it doesn't get lost
between sessions. Revisit after depletion + interaction-rules
authoring lands.
