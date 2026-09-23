# Creatine alias move and cleaner form-name precedence

Reviewed 2026-09-22 (Claude, continuing Codex's preserved patch).

## Data change

Six aliases that do not establish hydration chemistry (`creatine powder`, `micronized creatine`,
`creatine supplement`, `creatine powder supplement`, `micronized creatine supplement`,
`creatine, micronized`) moved from `creatine monohydrate` to the existing
`creatine monohydrate ((unspecified))` form. Explicit monohydrate, Creapure and HCl mappings are
unchanged. The unspecified form's consumer note and `absorption` text no longer assert monohydrate;
its own notes already record that an unspecified creatine may be monohydrate, HCl or another salt.
No score values changed.

## Cleaner fix

`_build_enhanced_indices` let a generated variant of `creatine monohydrate ((unspecified))` overwrite
the literal form name `creatine monohydrate`. `register_form` now gives a literal **form name**
precedence over generated variants within one parent, order-independently.

Codex's first draft gave the same precedence to exact **aliases**. Its whole-lookup diff moved 102
keys across ~40 parents, because many IQM forms declare bare parent names as aliases
(`vitamin b12` on cyanocobalamin, `flaxseed` on flaxseed oil, `caffeine` on caffeine anhydrous).
Last-writer order had masked those declarations; unmasking them would silently assign specific forms
to generic labels. Aliases therefore keep last-writer order. Those generic aliases on specific forms
are a separate per-entry data review, not part of this patch.

## Whole-lookup diff (35,959 keys, vs the alias-only snapshot)

`/tmp/pg_quality/creatine-after-guard-lookups.json` vs `creatine-alias-only-lookups.json`: 45 keys.

- `forms_lookup` changed for 3 keys, each to its literal form name: `creatine monohydrate`,
  `borage seed oil`, `pantothenic acid`.
- 42 keys keep `forms_lookup` and only bring `ingredient_context_lookup` into agreement with it
  (previously the context pointed at a different form than the forms lookup did).
- Context only feeds `context_include/exclude` disambiguation. Of 10 forms with such rules, one key is
  affected: `msm` label forms now resolve to `msm (methylsulfonylmethane) (unspecified)` instead of
  returning the raw text after failed disambiguation. Parent mapping is unchanged.

Parent mapping was probed unchanged for MSM, creatine variants, B12, K2, B5, borage and CoQ10.

## Tests

`test_cleaner_exact_form_precedence.py` fails 2/4 against the pre-fix normalizer and passes with it;
the synthetic fixtures now extend the real registry (the earlier setup failures came from replacing
it and losing mandatory `bromelain` targets). Focused run
`scripts/test.sh fast -k "normaliz or creatine or iqm or ingredient_quality or alias or cleaner or form_precedence"`:
2419 passed, 5 skipped.

Corpus impact still needs the regeneration step; the Thorne/GNC/BulkSupplements scan (37 candidate
rows) is not a full-corpus count.
