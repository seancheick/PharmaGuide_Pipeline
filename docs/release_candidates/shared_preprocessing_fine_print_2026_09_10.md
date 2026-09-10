# What the shared preparation step costs 6pt print

Measured 2026-09-10 on pipeline `7dc43f6b`, app `edc2a9c`. Source-only: no
model was qualified, no production photograph was processed, extraction stays
disabled.

## Why this measurement exists

Every candidate extractor reads the *same* prepared bytes. That makes
`photo_prep` a common-mode surface: if preparation has already destroyed a
dose row, both candidates miss the same row, they agree with each other, and
the benchmark records that agreement as confirmation. No comparison between
candidates can reveal it, because neither can see what preparation removed.

So the question is not "which reader is better" but "what is already gone
before either reader looks". Tool:
`scripts/submission_review/extraction/print_fidelity.py`. It renders a
Supplement Facts panel rasterised at genuine 6pt — never rendered large and
scaled down — places it in a frame of a stated capture geometry, and reads the
same render before and after preparation with the same engine. It calls the
real `prepare_bundle`; a second copy of the resize-and-encode rules would have
measured a fiction.

## The finding that changed the picture

**The server is not where resolution is lost. The phone is.**

`_sanitizeProductSubmissionPhoto` in the app's
`lib/services/product_submission_photo_service.dart` re-encodes every
submission photo through `FlutterImageCompress.compressWithList(minWidth:
2400, minHeight: 2400, quality: 90)` before a byte is uploaded. A 3024×4032
capture arrives as 2400×3200. A 48MP capture arrives as 2400×3200. All of the
extra sensor resolution a user's newer phone could contribute is discarded on
the device, and the server's own ceilings never engage:

| Capture | Sanitised by the app | `photo_prep` resizes? | Refused? |
|---|---|---|---|
| 12MP phone 4:3 (3024×4032) | 2400×3200 | no | no |
| 12MP phone 16:9 (3024×5376) | 2400×4267 | **yes**, to 2304×4096 | no |
| 24MP camera (4000×6000) | 2400×3600 | no | no |
| 48MP phone (6048×8064) | 2400×3200 | no | no |
| 48MP phone, **unsanitised** | — | — | **yes, `unsupported_evidence`** |
| 24MP camera, **unsanitised** | — | **yes**, to 4096 | no |

`MAX_EDGE = 4096` and `MAX_PIXELS = 40_000_000` therefore almost never fire on
a real submission today. The one exception is a 16:9 still: the phone caps its
short side at 2400, which puts the long side at 4267, and the server then
shrinks it a second time to 2304×4096 — a further 4% off the width, on top of
what the device already removed. Otherwise they fire only for a client that
uploads what the camera produced — a future web path, or a changed picker. A 48MP frame is 48.8
million pixels and is refused outright rather than read badly. That coupling
is now pinned by a test: relax the app's sanitiser and the server starts
refusing photographs.

## What preparation itself costs

Production chain (phone sanitise → `prepare_bundle`), 12MP portrait capture,
6pt body type, RapidOCR. "in" is what the server received; "out" is what it
sent to the adapter. `span` is the fraction of the frame's width the panel
fills; `em px` is the height of one em in the pixels the server was handed.

| span | em px | in: lines / digits | out: lines / digits |
|---|---|---|---|
| 0.20 | 16.7 | 100% / 100% | 100% / 100% |
| 0.22 | 18.3 | 93% / 88% | 93% / 88% |
| 0.24 | 20.0 | 100% / 100% | 100% / 100% |
| 0.25 | 20.8 | 100% / 100% | **93% / 88%** |
| 0.26 | 21.7 | 100% / 100% | 100% / 100% |
| 0.27 | 22.5 | 93% / 88% | 93% / 88% |
| 0.30 | 25.0 | 100% / 100% | 100% / 100% |
| 0.35–0.90 | 29–75 | 100% / 100% | 100% / 100% |

Above roughly 25 pixels per em, preparation is transparent: identical readings
in and out, at identical pixel dimensions. Between about 18 and 23 pixels per
em, one row — `Magnesium (as magnesium bisglycinate) 100 mg 24%`, the longest
declaration on the panel — is a coin flip. It is already lost on the input at
0.22, 0.23 and 0.27. At 0.25 the input holds it and the server's re-encode is
what loses it: same 3200px dimensions in and out, 139,298 bytes down to
135,938, and a dose gone.

**Raising the JPEG quality is not the fix.** At the same geometry the row
stays lost at q88, q90 and q92 and returns only at q95, and one span either
side of it q95 does not help at all. The lever is resolution, not quality.

The failure mode matters more than the rate: the row does not come back
garbled, it comes back **absent**. A missing magnesium row reads as a product
that does not contain magnesium. `run_checks` cannot see it — there is nothing
to compare against — and `verify_grounding` cannot see it either, because
grounding asks whether a claim can be located, not whether a printed row went
unclaimed.

## Limits of this measurement — read before quoting a number

- **The render is synthetic and clean.** No lens blur, no sensor noise, no
  camera JPEG, no curvature, no glare, no off-axis text. Real photographs are
  worse at every rung. These figures are an **upper bound on legibility**, not
  a floor. The trustworthy signal is the *difference* between the "in" and
  "out" columns and the geometry table above, not the absolute percentages.
- **Recall is not monotone in resolution.** 12.5 px/em read 100% while 18.3
  px/em dropped a row, because the engine rescales its own detection input.
  Do not read a threshold off this table.
- **One engine, one font, one panel.** RapidOCR, Arial, fourteen lines. A
  different engine may sit on a different knife edge.
- **The device step is a model.** `device_encode` mirrors the Dart call's two
  constants; it is not that code running. If the app's sanitiser changes, this
  model must change with it.

## What follows

1. **Capture UX is the lever.** The panel needs to fill roughly a third of the
   frame's width for the fine print to survive with margin. The capture
   checklist already tells the user which panel to shoot; it does not yet tell
   them to fill the frame with it, and nothing measures whether they did.
2. **The 2400px short side is now a load-bearing number.** It is the binding
   constraint on every extraction, it was chosen for upload size, and it is
   set in the app rather than in the extraction contract.
3. **Do not spend the quality constant.** q88 → q95 buys nothing at the
   geometries where rows are actually lost, and costs about 10% more bytes on
   every photograph.
4. **The benchmark must report per-field**, because this failure is confined
   to one dose row out of fourteen lines: an aggregate accuracy of 93% hides a
   100% loss on that product's magnesium content.

## Receipts

- `scripts/test.sh fast -k print_fidelity`: **9 passed, 1 skipped** (the
  skipped case is the OCR measurement, opted into with
  `PG_RUN_OCR_FIDELITY_TESTS=1`).
- `PG_RUN_OCR_FIDELITY_TESTS=1 scripts/test.sh fast -k "print_fidelity and
  operating_point"`: **1 passed**.
- Sweeps above: `python3 -m scripts.submission_review.extraction.print_fidelity
  --frames phone-12mp --fractions …`, and the same with `--no-device-step`
  for the unsanitised rows.
