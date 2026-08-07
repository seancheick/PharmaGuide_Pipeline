# Protocol amendment 1.1.1 — DRAFT, NOT RATIFIED

**Status:** proposed · **Supersedes:** nothing yet · **Applies to:** the next
benchmark freeze (v7), never retroactively to `2026-08-06-v6`

Protocol 1.1.0 §"Deviations, exclusions, and audit trail" states that any change
after a freeze creates a new benchmark version. These four items are therefore
staged here rather than edited into the v6 directory. **None of them is in
force until a statistician and the clinical owner sign below.**

Three were found by adversarial review of the reviewer-facing materials; one is
a protocol self-contradiction that blocks distribution outright.

---

## A1 · Reviewer-facing brief substitutes for delivering PROTOCOL.md

**The contradiction.** Protocol §"Blinding and artifact handling" says reviewers
receive "this protocol". The same section forbids reviewers from seeing "the
development/holdout and core/challenge assignments" — which the protocol
discloses in §"Frozen sample": the 96/24 split, and that challenge products were
selected for catalog safety caution, zero Evidence, low confidence, and tier-
boundary proximity.

**Sending the protocol as written unblinds the reviewer.** A reviewer who knows
24 products are a sealed holdout and that challenge items cluster on safety and
zero-evidence can infer cohort membership from the products themselves.

**Proposed.** Reviewers receive a derived brief carrying every rating concept,
range, anchor, procedure step, and obligation, with the sample-design sections
omitted. The brief becomes a fingerprinted freeze artifact. Protocol
§"Blinding" changes "this protocol" to "the reviewer brief for this freeze".

**Risk if rejected:** distribution stays blocked. There is no version of the
current protocol that can be sent to a reviewer without breaching its own
blinding rule.

---

## A2 · `protocol_deviation` excludes missing label facts

**The problem.** Protocol §"Deviations" lists "missing label facts" as a
recordable deviation. `ANALYSIS_SPEC.json` sets
`primary_requires_no_protocol_deviation: true`, so any non-empty deviation
**mechanically removes that product from the primary analysis for all three
reviewers**.

Our own extraction defects are visible to reviewers in the frozen sample: 14
products with a zero ingredient quantity, 10 with a missing unit, 7 with a
servings-per-day below 1. A conscientious reviewer logs each one. Under the
current wiring that silently deletes up to ~26 of 120 products — and the cause
would be *our* data quality, not any reviewer misconduct.

**Proposed.** `protocol_deviation` becomes a closed enum for events that
compromise the *rating*: `none` · `saw_engine_score` · `conflict_discovered` ·
`source_access_failure` · `other`. Data-quality observations route to the
existing first-class `label_facts_sufficient = no` plus `rationale`, and do not
trigger exclusion.

This does not weaken the exclusion rule — it stops a reviewer's diligence about
our defects from being scored as their protocol breach.

**Risk if rejected:** expect a materially smaller analysable sample, with the
loss concentrated in exactly the products whose label data is weakest.

---

## A3 · `source_citations_json` accepts delimited plain text

**The problem.** The column name implies JSON. Asking a clinician to hand-author
JSON in a spreadsheet cell will produce malformed rows, and
`source_citation_required: true` must remain machine-checkable.

**Proposed.** Freeze the parse rule: semicolon-delimited, one source per entry,
each a bare PMID (`PMID 12345678`), a DOI, or an official URL. Whitespace
trimmed; empty entries dropped. Column name unchanged so the frozen header still
matches. Analysis parses on `;`.

**Risk if rejected:** either citation completeness cannot be evaluated
mechanically, or reviewers must hand-write JSON — both worse.

---

## A4 · Fixed dosing rule for defective servings-per-day

**The problem.** 7 sampled products carry a `min_servings_per_day` below 1 —
one is 0.044, a known pipeline defect where the field was computed as the
reciprocal of the serving size in grams (filed separately). Two of the seven are
*also* a labeled range, so a "rate the maximum serving" rule returns "0.66
servings per day", which is not an instruction.

Leaving each reviewer to invent an assumption makes their dose ratings
incomparable to each other **and** to the engine — the disagreement would be
manufactured by instruction rather than observed.

**Proposed.** For any product whose servings-per-day renders below 1, all
reviewers assume **1 serving per day**, record it in `rationale`, and set
`assessment_confidence = low`. This rule outranks the maximum-serving rule for
ranged products. The 7 IDs are listed in the v7 manifest so the analyst can
report their dose deltas as sensitivity-only.

**Preferred alternative:** fix the pipeline defect and re-cut v7 against a
catalog where the field is correct, making A4 unnecessary. A4 stands only if the
freeze must precede that fix.

---

## Sign-off — required before any packet is distributed

| Role | Name | Date | Decision |
|---|---|---|---|
| Statistician | | | ratify / reject / amend |
| Clinical owner | | | ratify / reject / amend |

On ratification: assign a freeze ID, fingerprint this file into that manifest,
and record the superseded protocol version. **A1 is a hard blocker; A2–A4 are
strongly recommended but a documented rejection is a legitimate outcome, so long
as it is recorded here rather than resolved silently in the brief.**
