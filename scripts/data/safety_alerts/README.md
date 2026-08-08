# Safety alerts — the fast lane

One file per verified regulatory event, named `SA_YYYY_NNNN.json`. Every record is
**human-approved before publication.** The FDA sync may create a draft; it may never publish one.

## What this is not

It is **not** a view of `banned_recalled_ingredients.json`. That file answers *"which substances are
prohibited"* — a long-lived reference table with no product identity, no FDA class, and recall
history going back to 2009. An alert answers a different question: *"which verified regulatory event
just happened, and to whom."* Sourcing alerts from the reference table would fire a seventeen-year-old
recall at every user on first install.

The reference table still drives the catalog's BLOCKED verdict on its own schedule. These are two
lanes, and they do not substitute for each other.

## Two lanes, one direction of authority

| | fast lane (this) | slow lane (catalog) |
|---|---|---|
| cadence | minutes | weekly/monthly |
| says | "stop taking this" | BLOCKED verdict, score suppression, search exclusion |

**This lane may only add state, never subtract it.** Retracting an alert clears *its own* signal and
nothing else — a catalog BLOCKED verdict survives until the catalog's separately reviewed data
changes. If you need to un-block a product, that is a `banned_recalled_ingredients.json` change and a
catalog rebuild, not a retraction here.

## Authoring

Validate before committing:

```bash
python3 -c "import sys; sys.path.insert(0,'scripts'); import json, glob; from safety_alerts import validate_feed; print(validate_feed([json.load(open(f)) for f in glob.glob('scripts/data/safety_alerts/SA_*.json')]))"
```

### Fields that trip people up

**`revision` — records are immutable.** Never edit a published record. Found a typo in the headline?
Ship `revision: 2`. The manifest names the latest revision per `alert_id`; a lower or unknown
revision is ignored by clients, never applied.

**`fda_class` is conditional, not required.** Classified recalls carry it when the official source
provides one. Ingredient bans usually do not — DEA scheduling actions, import alerts and
warning-letter enforcement have no recall class, and inventing one is worse than leaving it null.
What *is* required on every record: `authority`, `source_url` (https, the official record), and
`evidence_verified_at`.

**`scope` takes exactly one dimension.** `ingredient_canonical_ids` for a ban, `dsld_ids` for a
recall. **Brand scope is not supported in v1** — without an exact normalized brand identity it
degrades into runtime fuzzy matching, which is how an alert condemns the wrong product.

**`resolved_dsld_ids` is not just push targeting.** It is the signed, publication-time applicability
set, resolved against `catalog_snapshot_version`. A user's device may hold an older catalog that
cannot resolve the newly banned substance at all — canonical matching alone would silently miss them.
The resolved set is authoritative; ingredient matching is a second confirmation. This is what lets a
ban work *before* the catalog rebuild. A published alert with an empty resolved set fails validation.

**`lots` is display-only.** We do not know the user's lot, and we never will unless they tell us. A
lot-scoped alert lists the affected lots and says *"check your bottle"* — it must never claim a match.
Nothing in the matcher reads this field.

**`jurisdiction` is not decoration.** A ban in one market is not a universal consumer instruction.

**`effective_date` vs `published_at`.** `effective_date` is when the regulatory action took effect
(from the official record); `published_at` is when we shipped the alert. An alert whose
`effective_date` is in the future does not fire yet.

## Consumer copy

`headline` / `body` / `action`, risk-matched, and different per event type:

- **ingredient ban** — *"this product contains a prohibited substance"*
- **product recall** — *"this bottle may be affected — check your lot against the list"*

Never *"your lot matched."* Never soften a ban into a suggestion. See
`feedback_pharmaguide_safety_voice`: under-warning is the more expensive failure, but a warning the
user cannot act on is not a warning.

## Status lifecycle

```
draft ──(human verifies identity, scope, wording, source)──> published ──> retracted
```

`draft` may have an empty `resolved_dsld_ids`; resolution happens at publication. Class I raises
draft priority and review urgency — it does **not** bypass review. FDA does not publish every recall
to its public alert page, so automated collection is not sufficient publication authority.
