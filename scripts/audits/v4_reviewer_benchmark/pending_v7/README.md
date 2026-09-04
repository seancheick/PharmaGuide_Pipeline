# Pending inputs for benchmark freeze v7

**Historical staging notes; workflow guidance superseded 2026-09-04.** Use
[the owner protocol](../PROTOCOL.md) and [the reviewer workflow](../REVIEWER_WORKFLOW.md)
for the current draft engineering contract. Catalog versions, panel status and
operational instructions below record the earlier preparation, not a fresh
state check. The reviewer brief and clinical/statistical decisions remain
unratified; this notice does not authorize distribution or opening either key.

Nothing here is in force. These are the prerequisites that must be settled
**before** v7 is cut, staged outside `scripts/reports/v4_reviewer_benchmark_2026_08_06_v6/`
so the v6 freeze stays byte-intact for audit.

| File | What it is | Who completes it |
|---|---|---|
| `AMENDMENT_1.1.1_DRAFT.md` | Four proposed protocol changes, A1 a hard blocker | statistician + clinical owner |
| `reviewer_registry.DRAFT.csv` | The registry protocol §"Reviewer eligibility" requires **before assignment** | you + each reviewer |

## Why v6 cannot be distributed

1. **The protocol contradicts itself** — reviewers are owed a document that
   discloses the sample design the same document forbids them seeing. See
   amendment A1. No wording of v6 is sendable.
2. **`reviewer_registry.csv` does not exist.** Only the header-only template is
   in the freeze. `ANALYSIS_SPEC.json` requires
   `licensed_clinical_reviewers_required: 2`, unverifiable without it, and the
   registry is the only authoritative home for the reviewer→slot binding that
   ICC(A,1)/ICC(A,3) depend on.
3. **The frozen catalog no longer exists.** v6 pins
   `db_version 2026.08.06.092521`; production is now `2026.08.06.215457` and
   092521 was removed by storage cleanup. The engine contract is unchanged
   (`1.1.4` / `1.0.5-b7-single-source` / `v4` / `4.2.0`, config sha `2c007207…`
   all still match), so only the catalog fingerprint drifted — but a baseline
   pinned to a deleted release is not defensible.

4. **The v6 packets carry 23 false dose instructions.** `build_review_doc.py`
   inferred "X is the TOTAL; do NOT add the entries after it" from arithmetic
   coincidence — whether the next 2-3 amounts happened to sum — with no identity
   evidence, so it paired `Leucine` with `Isoleucine + Valine` (a 2:1:1 ratio
   guarantees the sum) and `GABA` with `Theanine + Rhodiola`. 30 notes reached
   every reviewer; 23 were false. Fixed 2026-08-07: the freeze now resolves the
   relationship from the label's own row nesting and the document only renders
   it. **v7 must be cut with the fixed freeze** — the packet gains
   `parent_index` / `constituent_child_indexes`, and without them the note
   correctly falls to zero (check the `total-vs-forms:` count that
   `build_review_doc.py` prints). Per-reviewer, per-product manifest:
   `../CONTAMINATION_v6_rollup_notes.csv`. PHAM's returned answers include 23
   rows exposed to a false note; how they are treated is a protocol decision for
   the statistician and clinical owner, not a code change.

## Cut v7 as late as possible

Freeze immediately before distribution, not before recruitment. Cutting now and
shipping another catalog next week just burns a version, exactly as happened to
v4 and v5.

```
finish correctness work
  ↓
build candidate catalog          ← scoring / evidence / catalog changes STOP here
  ↓
registry populated + amendment ratified + reviewers trained
  ↓
cut v7 against that exact release
  ↓
distribute the same day
```

## Panel

Three fixed reviewers, each rating all 120, at least two licensed
pharmacist / physician / RD, conflict-free across all 41 brands. Slot 1 is
provisionally PHAM (PharmD). Slots 2 and 3 are open.

A non-licensed reviewer may hold at most one slot and must be disclosed as such
in the final report — it changes what the benchmark measures from "expert human
consensus" to "mixed panel", which is a legitimate design but not the same
claim.

## Standing prohibition

Do not open `development_baseline_key.csv` or `SEALED_HOLDOUT_KEY.csv`. Freeze
v4 was destroyed by displaying two rows of the holdout key to the calibration
analyst. The two-stage opening contract in protocol §"Blinding" is the control
that makes the whole exercise credible.
