# Ingredient-row key census — 2026-09-25 (report only)

**Question:** can the undeclared-key check in `audit_contract_sync.py` (which already fails on
undeclared *top-level* blob keys) be extended to ingredient rows?

**Answer: not yet.** On the shipped build (`scripts/dist`, db_version 2026.09.22.201915,
15,310 blobs):

| Surface | Rows | Declared keys | Undeclared keys |
|---|---|---|---|
| Top-level blob keys | — | `BLOB_TOP_LEVEL` | **0** (already gated) |
| `ingredients[]` | 78,877 | 24 (`ACTIVE_CONTRACT`) | **51**, on every row |
| `inactive_ingredients[]` | 83,130 | 14 (`INACTIVE_CONTRACT`) | **27**, on every row |

A gate turned on today would fail every product. The row contracts only declare the fields the
emit-rate audit tracks, not the shipped row shape. No gate was added (as agreed: census only).

Reproduce: `python3 scripts/audits/ingredient_row_key_census_20260925/census.py`

## Parallel names and fields nobody reads (the "two brains" signal)

The Flutter readers were checked with `rg -l "[\"']<key>[\"']" "/Users/seancheick/PharmaGuide ai/lib"`.
Every key below is still emitted, per `scripts/build_final_db.py`.

| Key(s) | Flutter files reading it | Reading |
|---|---|---|
| `mapped`, `is_mapped` | 0, 0 | Twins, both unread by the app |
| `forms` / `extracted_forms` | 0 / 1 | Twins; the app reads only `extracted_forms` |
| `safety_hits` / `safety_flags` | 0 / 1 | Twins; the app reads only `safety_flags` |
| `normalized_value` / `normalized_amount` | 0 / 2 | Twins; the app reads only `normalized_amount` |
| `harmful_notes` / `notes` | 0 / many | `harmful_notes` unread by the app |
| `standardName` / `standard_name` | 2 / 14 | camelCase twin; one app filter reads both as a fallback |
| `matched_form` / `matched_forms` | 1 / 1 | Both read by `profile_gate_summary_filter.dart` |

Zero Flutter references is **evidence, not proof** (AGENTS.md "Dead code and fields"). Before
removing anything, also check the reviewer console, the dashboard, Supabase consumers, the core DB
projection and the tests.

## Next step (separate task)

1. Classify each twin (false dual brain / one policy many consumers / two policies one topic).
2. Delete the proven-dead names from the export and the app together.
3. Declare the surviving row shape in `ACTIVE_CONTRACT` / `INACTIVE_CONTRACT`.
4. Only then extend the undeclared-key check to rows, so a future `score_new`-style twin fails the
   release.
