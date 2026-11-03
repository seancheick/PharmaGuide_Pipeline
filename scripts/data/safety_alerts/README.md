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

**`resolved_dsld_ids` is not just push targeting.** It is the frozen, publication-time applicability
set, resolved against `catalog_snapshot_version`. A user's device may hold an older catalog that
cannot resolve the newly banned substance at all — canonical matching alone would silently miss them.
The resolved set is authoritative; ingredient matching is a second confirmation. This is what lets a
ban work *before* the catalog rebuild. A published alert with an empty resolved set fails validation.

**`lots` is display-only.** We do not know the user's lot, and we never will unless they tell us. A
lot-scoped alert lists the affected lots and says *"check your bottle"* — it must never claim a match.
Nothing in the matcher reads this field.

**`jurisdiction` is not decoration.** A ban in one market is not a universal consumer instruction.

**`consumer_disposition` is authored, never inferred by the app.** A reviewer selects `block` or
`review` alongside the source-backed copy. That prevents a client release from silently upgrading or
downgrading the meaning of a regulatory event.

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

## Interaction rules: `interaction_rule`

The interaction DB reaches phones slowly. This event carries a rule correction to the people it
affects on their next connection. **Matching happens only on the device**, against the medications
and profile the user has on their phone. Nothing about either is ever sent to us, and this repo has
no way of knowing who matches: `applies_to` here always answers no, and push is skipped for this event.

It adds one object to the record. `body` is the reason and `action` the management, so neither is
repeated:

```json
"interaction": {
  "rule_id": "DSI_...",
  "rule_fingerprint": "sha256:...",
  "ingredient_name": "as the user reads it",
  "medication_name": "as the user reads it",
  "medication_ids": ["class:doacs", "11289"],
  "severity": "contraindicated",
  "evidence_level": "established"
}
```

A rule for pregnancy, lactation or a condition targets a profile instead of medications. Replace
`medication_name` and `medication_ids` with the rule's own gate and a label for the notice:

```json
"profile_context": "Pregnancy",
"profile_gate": {
  "gate_type": "profile_flag",
  "requires": {"conditions_any": [], "drug_classes_any": [], "profile_flags_any": ["pregnant"]},
  "excludes": {"conditions_any": [], "drug_classes_any": [], "profile_flags_any": [],
               "product_forms_any": [], "nutrient_forms_any": []},
  "dose": null
}
```

The gate must require someone, and can't use a dose or exclude a form: the device evaluates it from
the profile alone, without a product in hand.

**`medication_ids` are exact identities:** `class:*` ids, RxCUIs or profile drug-class ids, in the
vocabulary of the rule itself. List each form you need, because the device does no clinical
crosswalk. A display name would silently match nobody, so validation refuses one.

**`consumer_disposition` follows severity:** `block` for `contraindicated`, otherwise `review`.

**This lane still only adds.** An alert can warn sooner or more strongly than the DB on the phone. It
can't take back a stricter warning the phone already shows.

**Old builds never see this event.** Builds up to 1.0.0+23 reject a whole feed on an event type they
don't know, and a fresh install would then have no alerts at all. So `build_safety_alerts.py --stage`
keeps rules out of `safety_alerts.json`, the file the release row's `feed_path` names and the only
one the dispatcher reads. Rules go in `safety_alerts_extended.json`, which `manifest.extended_feed`
names for builds that know the key. With no rule alerts active, a release is what it always was.

## Publishing a rule correction: the gate

`scripts/rule_change_gate.py` runs before any release. It compares the candidate interaction DB with
the one the app's pin names, and refuses a material change that has no cover:

| Change | Needs |
|---|---|
| Medication x supplement, or a pregnancy, lactation or condition rule, at `avoid` or `contraindicated`: new, raised into that tier, or now applies to different people | A published, live `interaction_rule` alert. An attestation is not a notification |
| Any other hard rule change: reworded, re-graded, lowered or removed | The alert, or an attestation |
| A lower tier raised | The alert, or an attestation |
| A hard medication x medication, supplement x supplement, food or dose rule | An attestation. An alert can't express these |
| New or reworded rules below `avoid`, timestamps, source lists | Nothing |

Get the value to put in `rule_fingerprint`:

```bash
python3 scripts/rule_change_gate.py --fingerprint RULE_KEY --candidate scripts/dist/interaction_db.sqlite
```

Keys are the interaction `id`, or for ingredient rules `RULE_ID#drug_class:<id>`,
`RULE_ID#condition:<id>`, `RULE_ID#dose:<index>` or `RULE_ID#pregnancy_lactation`.

An attestation goes in `rule_change_attestations.json`. It records a person's decision that no user
notice is needed, and it only covers that exact version of the rule (`removed:<fingerprint of the removed rule>` for a removal):

```json
{"attestations": [
  {"rule_key": "...", "rule_fingerprint": "sha256:...", "reason": "...", "reviewer": "...", "date": "YYYY-MM-DD"}
]}
```

## Status lifecycle

```
draft ──(human verifies identity, scope, wording, source)──> published ──> retracted
```

`draft` may have an empty `resolved_dsld_ids`; resolution happens at publication. Class I raises
draft priority and review urgency — it does **not** bypass review. FDA does not publish every recall
to its public alert page, so automated collection is not sufficient publication authority.

## When a ban can't wait on rule review

A ban or recall reaches phones through `run_safety_alert_publish.sh`, which never waits on the gate.
Only a catalog carrying it can be held up. If unrelated rule review is the only thing holding it, add
a dated entry to `rule_gate_emergency_overrides.json` and run
`release_full.sh --emergency-catalog --skip-flutter`:

```json
{"overrides": [{"alert_id": "SA_2026_0001", "revision": 1, "reason": "why this can't wait",
                "approved_by": "who decided", "date": "YYYY-MM-DD"}]}
```

The alert must be a ban or recall already live, and the entry counts only on its date. The app pin
doesn't move, so the interaction DB stays gated. Blobs carry rule text and tiers, in warnings and in
`interaction_summary`, so the gate still refuses if a blob shows a held change, or if a held rule was
removed or lowered, which no blob can disprove:
sign that change off, or hold that rule edit back and rebuild. The entry and
`rule_gate_emergency_report.json` record what went out ahead of review.
