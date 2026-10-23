# Ten holds and submission accuracy audit — October 23, 2026

Owner: `build_final_db::_warning_only_identity_labels` — evidence: export callers, source inventory and correction registry inspection. Will NOT create: chemical identities, quality ratings, public fields or an alternative scorer.

The ten quality holds remain justified. Products213846,297638,328818,337851 contain literal cystine without a reviewed canonical quality owner;78327 prints an acetylated-cystine name inconsistent with structured NAC. Product241969 has conflicting vitamin D units,27807/802 conflicting molybdenum amounts/DV,19598/271115 undisclosed blend-member amounts. Existing original-label/chemical receipts remain in the October22 zero-pillar audit. Unknowns must remain explicit.

213846 previously failed blob export because immutable API inventory says Alpha-Glucan Oligosaccharide while its verified official label correction says L-Cystine. The existing export correspondence owner now verifies applied correction provenance against the current curated registry. Original inventory remains intact, quality remains withheld and unrelated/unverified substitutions still fail.

A paired raw Clean→Enrich→Score replay of all ten holds and true cysteine/NAC controls201101/329943 found zero changed records. Export acceptance and negative provenance guards are checked separately through actual blob construction. Private immutable inputs and captures live in `~/pg_quality/holds_submissions_20261023/`.

All five awaiting approved submissions pass the real importer/cleaner: active and inactive identities resolve, including corrected rice hulls/HPMC and blend/conjunction parsing. Creatine20kcal retained. No materialization or pipeline run occurred.

All15 photos of newly transcribed S08–S12 were inspected against server reviews:

| Alias | Accuracy finding |
|---|---|
| S08 | Printed tablet incorrectly saved as Capsule; biotin5000mcg/16667%DV, milk and120servings verified. |
| S09 | Remove inferred daily frequency; retain printed secondary800mcg folic acid alongside1334mcgDFE. Other printed amounts verified. |
| S10 | Visible melatonin3mg label, directions, milk and100servings match. |
| S11 |335mg blend species embedded in name, no children; actual cleaner yields zero active ingredients. Proposal retains eight undosed children and total30billionCFU minimum at manufacture. Titanium dioxide (For Color) now reaches its existing inactive-policy assessment through the shared descriptor fallback. No quality-map identity is invented for this safety-only material. Exact matching remains first; composition-bearing parentheses are protected. Native raw corpus search found zero occurrences of the newly supported literal suffix; the affected real submission is probed separately. |
| S12 | Missing/partial inactive list, statements and carbohydrate<1g; combined blend members. Actual importer rejects missing text. Full inactive list and start of directions cut off in photos; clearer side panel required. |

The canonical save guard refused reviewer-owned S08/S09 edits. S11 ownership refusal independently confirmed. No reviewer attestations, extraction drafts or saved reviews were overwritten. Accurate proposals and full private probes remain under `~/pg_submissions/`; review corrections and S12 retake remain open. Server READY is a consistency check, not proof of photo accuracy.

Validation and integration receipts will be recorded after the combined candidate completes.

Actual candidate blob construction succeeds for all12 captured products: ten not_scored with null pillars, two scored controls. This checks current-exporter compatibility with both baseline and candidate captures; the historical refusal is separately established by the fail-first213846 regression.

Final real S11 replay on runtime b1affed6 adds exactly the existing moderate titanium-dioxide watchlist warning and retains all three previous excipient warnings. Existing EU clean-label policy is warning-only; no US ban is imposed. Quality remains withheld. Per-source final twelve-product replay is unchanged at Clean/Enrich/Score,33raw canaries pass, and fresh-context review accepts exact-before-purpose fallback plus strict correction/UNII/path provenance guards. Earlier local attempts lacked ignored artifact mounts and are not passes; final mounted validation is recorded below when complete. Superseded CI runs were cancelled, never counted as passes.

Final validation: runtime b1affed693afb3d94d97c5c630a86e4e3f6f27b8 passed whole-fast CI39911578742 (23,335passed,192declaredskips; four groups and all skip guards green), local546passed/24optional-service skips,33rawcanaries. Final twelve-product paired replay has zero changed Clean/Enrich/Score records. Source-equivalent later commits contain documentation only. No pipeline or release ran; new submission corrections/retake remain open.
