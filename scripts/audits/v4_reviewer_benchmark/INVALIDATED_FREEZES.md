# Invalidated reviewer benchmark freezes

## `2026-08-06-v4`

Invalidated on 2026-08-06 after an engineering inspection displayed the CSV
header and first two rows of `SEALED_HOLDOUT_KEY.csv` to the calibration
analyst. No scoring parameter changed and no reviewer response existed, but
the exposure violated the one-shot holdout restriction. The generated files
remain recoverable from Git history for incident audit only and must not be
used for review, development, calibration, validation, or reporting.

## `2026-08-06-v5`

Invalidated before use on 2026-08-06. Neither baseline key was opened and no
reviewer was registered, but protocol 1.0.0 did not require the same three
reviewers to rate every product. That design could not support the promised
two-way random-effects absolute-agreement ICC. Generated files remain local
for incident audit only and must not be used.

## Active replacement

Freeze `2026-08-06-v6`, protocol 1.1.0, supersedes both invalidated freezes.
Its fixed three-reviewer panel, per-reviewer order, registry, response lock,
analysis implementation, and holdout candidate-lock requirements are
fingerprinted in its manifest.
