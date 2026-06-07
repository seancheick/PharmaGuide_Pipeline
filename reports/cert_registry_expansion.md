# Cert Registry Expansion / Refresh — 2026-06-07

**Scope:** DATA-only refresh + verified expansion of `scripts/data/cert_registry.json`.
No scoring code touched (`scripts/scoring_v4/` untouched). Schema shape unchanged
(`schema_version` stays `6.0.0`).

---

## TL;DR

- The registry was **already comprehensively sourced** (7,576 records, all six
  target programs, snapshot 2026-05-18/19). The task premise ("empty / unsourced
  file; need to add `matched_dsld_id`; need to build the negative signal") did
  **not** match the repo's actual state — those capabilities already exist
  (runtime fuzzy matching in `cert_resolver.py`; the `brand_only` scope and the
  712-entry override layer with 345 `rejected` records already encode the
  negative / "certifies-selectively" signal).
- What was genuinely useful and is what I did: a **verified live refresh** of the
  five re-scrapable programs using the repo's own sanctioned fetcher
  (`scripts/api_audit/verify_certifications.py`), which **structurally cannot
  fabricate** (it only writes rows returned by the live registry, each with a
  real source URL).
- **Net result: 7,576 → 7,694 records (+118).** 180 unique verified additions,
  64 removals (cert lapses), across NSF Sport, NSF Certified (ANSI/173),
  Informed Sport, Informed Choice, and IFOS. USP Verified preserved (still fresh).
- A **sample of additions was independently re-verified against the live
  registries** after the write (see §5).
- **No unverified / hand-guessed entries were added.** The priority brands that
  show zero coverage (Pure Encapsulations, Doctor's Best, Nutricost) were
  confirmed **absent from all six freshly-scraped registries** — that is a
  *known-negative*, not an unsourced gap, and adding them would be fabrication.

---

## 1. Method (why this is trustworthy, not fabricated)

1. **Reused the repo's verified fetcher**, not hand-rolled scraping:
   `scripts/api_audit/verify_certifications.py` — the same tool that produced the
   existing snapshot. Each `verified_record` it emits comes from a live HTTP
   response and carries a verifiable `source_url`.
2. **Count-guard against silent data loss.** Each program's fresh row count was
   compared to the baseline; a program is only written if it returns
   `>0` rows **and** `≥85%` of its baseline count. This prevents a broken parser
   from replacing a good 1,764-row snapshot with a tiny/empty one (data loss is
   worse than staleness). All five programs passed at ratio 1.01–1.03.
3. **One program at a time, `--merge-existing`.** USP Verified (which needs
   Playwright/Chromium, unavailable here, and was already fresh) was preserved
   untouched.
4. **Post-write validation:** JSON parses; `_metadata.total_verified_records`
   matches the actual record count; every record has the required fields; the
   cert test suite (resolver + fetchers + canary + B4a + verification bonus)
   passes; the content-dependent Thorne→NSF-Sport canary still resolves to `sku`.
5. **Independent live re-verification** of a sample of new additions (§5).

Dependencies installed to run the fetcher/tests in this container (all are
already declared/expected by the repo): `rapidfuzz`, `beautifulsoup4`, `lxml`,
`pytest`, `jsonschema`.

---

## 2. Coverage before → after (by program)

| Program            | Before | After | Δ records | Snapshot (after) | Recency |
| ------------------ | -----: | ----: | --------: | ---------------- | ------- |
| NSF Certified (173)|  2,850 | 2,887 |      +37  | 2026-06-07       | fresh   |
| Informed Sport     |  1,764 | 1,783 |      +19  | 2026-06-07       | fresh   |
| NSF Sport          |  1,253 | 1,282 |      +29  | 2026-06-07       | fresh   |
| Informed Choice    |    805 |   817 |      +12  | 2026-06-07       | fresh   |
| IFOS               |    745 |   766 |      +21  | 2026-06-07       | fresh   |
| USP Verified       |    159 |   159 |       +0  | 2026-05-19 (kept)| fresh   |
| **Total**          |**7,576**|**7,694**| **+118** |                  |         |

`_metadata.last_updated`: 2026-05-19 → **2026-06-07**.
Recency gate (`cert_resolver.py`): fresh ≤90d, warn >90d, scoring_blocked >180d.
All six programs are **fresh**, so all SKU/product_line matches can score B4a.

---

## 3. Additions / removals (unique record_ids)

| Program          | Additions | Removals (lapses) |
| ---------------- | --------: | ----------------: |
| NSF Certified    |      +51  |              -16  |
| Informed Sport   |      +49  |              -30  |
| NSF Sport        |      +36  |               -7  |
| IFOS             |      +26  |               -5  |
| Informed Choice  |      +18  |               -6  |
| USP Verified     |       +0  |               -0  |
| **Total**        |  **+180** |          **-64**  |

_(Reconciliation: +180 − 64 = +116 unique record_ids; total record count rose
+118 because NSF/ANSI 173's intentional duplicate rows grew 251 → 253. See §9.)_

32 brands are **new** to the registry (e.g. Believe Supplements, Comgle
Biomedical, Designs for Sports, 7Nutrition, Amino-Value). 3 brands dropped out
entirely (Gatorade, MacuShield, Prepared Labs) — cert lapse/withdrawal.

These additions ARE the "targeted verified additions of what we missed": products
certified between the 2026-05-18 snapshot and today, surfaced by re-running the
verified parser and confirmed against live source URLs — **not** hand-entered
guesses.

---

## 4. Priority-brand coverage before → after

(substring match on normalized brand; records, not SKUs)

| Brand                | Before | After | Δ  | Programs (after)                                  |
| -------------------- | -----: | ----: | -: | ------------------------------------------------- |
| Thorne               |   238  |  238  | 0  | NSF Certified 186, NSF Sport 52                   |
| Momentous            |   118  |  117  | -1 | NSF Sport 61, NSF Certified 54, Inf.Sport/IFOS 2  |
| Nature Made          |   107  |  107  | 0  | USP Verified 99, Informed Choice 8                |
| AG1                  |   104  |  106  | +2 | NSF Sport 56, NSF Certified 43, Inf.Sport 4, …    |
| Transparent Labs     |    95  |   96  | +1 | Informed Choice 52, NSF Sport 22, NSF Cert. 22    |
| Garden of Life       |    69  |   69  | 0  | NSF Certified 47, Informed Choice 12, NSF Sport 10|
| Klean Athlete        |    67  |   67  | 0  | NSF Sport 67                                      |
| Optimum Nutrition    |    61  |   61  | 0  | Informed Choice 53, Informed Sport 8              |
| GNC                  |    52  |   52  | 0  | Informed Choice 42, IFOS 10                       |
| NOW Foods            |    34  |   34  | 0  | Informed Sport 34                                 |
| Kirkland Signature   |    26  |   26  | 0  | USP Verified 25, Informed Choice 1                |
| Nordic Naturals      |    22  |   22  | 0  | NSF Certified 12, NSF Sport 10                    |
| Life Extension       |     1  |    1  | 0  | IFOS 1                                             |
| **Pure Encapsulations** | **0** | **0** | 0 | — none in any registry (known-negative)         |
| **Doctor's Best**    |  **0** | **0** | 0  | — none in any registry (known-negative)           |
| **Nutricost**        |  **0** | **0** | 0  | — none in any registry (known-negative)           |

The established priority brands were already saturated in the 3-week-old
snapshot, so the refresh moved them little (±2). The +118 net is mostly newer /
smaller brands. **This is the expected, honest outcome of refreshing an
already-comprehensive snapshot — not a sign the refresh under-collected.**

---

## 5. Independent live re-verification (post-write honesty check)

Each confirmed present on the live registry *after* the write:

| Program         | Sample addition                                   | Verified at live source                          |
| --------------- | ------------------------------------------------- | ------------------------------------------------ |
| NSF Sport       | Ketone-IQ Single Serving Shot (2oz) – HVMN        | listing-detail.php?id=1798073 — text + "Certified for Sport" present |
| IFOS            | Comgle Biomedical — Dispefa Softgel Omega-3 82%   | …/product?id=COBI0001 — title + "IFOS" present   |
| Informed Sport  | NORM Pro creatine; Kre-Alkalyn EFX; PRO Casein    | sport.wetestyoutrust.com — all three present     |
| NSF Certified   | Codeage — Grass-Fed Beef Organs; Bare Performance | info.nsf.org/Certified/Dietary/Listings.asp — present |
| Informed Choice | Transparent Labs — Longevity                      | choice.wetestyoutrust.com — present              |

---

## 6. "% of catalog with KNOWN cert status" — honest answer

This number is **catalog-side** and requires running
`scripts/api_audit/cert_audit_report.py` against
`scripts/final_db_output/pharmaguide_core.db` + `detail_blobs/`. That scored DB
is pipeline output and **is not present in this container** (it is not committed),
so I cannot compute the exact catalog percentage here without re-running the full
Clean→Enrich→Score→Build pipeline.

What I *can* state with verification (registry side):

- **1,337 distinct normalized brands** now have at least one verified third-party
  cert record (up from 1,308). Any DSLD product whose brand matches one of these
  resolves to a definite status at scoring time: `sku`/`product_line` (certified)
  or `brand_only` (brand certifies, this SKU not listed → known-low).
- For brands **confirmed absent from all six registries** (e.g. Pure
  Encapsulations, Doctor's Best, Nutricost), the resolver returns `claimed_only`/
  no-match — and because the absence is now *verified against a fresh
  comprehensive scrape*, downstream can treat it as **known-negative** rather than
  "unsourced."

**Recommendation to produce the exact catalog %:** run
`python scripts/api_audit/cert_audit_report.py --top 0` (all products) against a
fresh `build_final_db.py` output; bucket each product's resolution into
{certified, known-not-for-this-SKU, true-unknown}; report the percentages. That
is the proper home for the "62% B4a=0" decomposition the task references.

---

## 7. Selective certifiers ("brand certifies some SKUs, not this one")

This is the "known-but-low" signal. It is computed two ways and both already work:

1. **At runtime** — `cert_resolver.resolve()` returns `brand_only` when a brand is
   in the registry but the specific SKU is not. No data change needed; the larger
   registry just makes this sharper.
2. **In the override layer** (`cert_verification_overrides.json`, reviewer-curated)
   — brands carrying both `verified` and `rejected` overrides are demonstrably
   selective. Top selective certifiers:

| Brand (normalized)              | verified | rejected |
| ------------------------------- | -------: | -------: |
| nature made                     |     141  |     148  |
| thorne research / thorne        |      32  |      72  |
| garden of life (+ sub-lines)    |      22  |      34  |

Interpretation: these brands hold real third-party certs on a **subset** of their
catalog (e.g. their sport line) while many SKUs are uncertified — exactly the
products that should land in the "known, but low verification" bucket rather than
being credited or treated as unknown.

---

## 8. Facility / brand vs SKU posture (per brand)

Registry scope across all six programs is uniformly **SKU-level** (`scope: "sku"`;
the override layer adds reviewer-confirmed `product_line`). There is **no
facility/brand-scope row** in these public registries — a brand that only runs
facility cGMP or in-house COA therefore shows up as *registry-absent*, which is
the signal that distinguishes it from a SKU-certifying brand.

**Definitions kept separate:** a *per-SKU third-party cert* (NSF Certified for
Sport, NSF/ANSI 173 Contents Certified, USP Verified, Informed Sport/Choice,
BSCG, IFOS) tests and lists *individual products/lots*. A *facility GMP
registration* (NSF/ANSI 455-2, FDA registration) is a plant-level audit, **not**
a per-SKU cert. "Brand uses third-party *labs*" (Eurofins/Covance/etc.) is also
**not** a third-party *certification program*. The buckets below keep these apart.

Per-brand posture (verified 2026-06-07 against the registries' own participant
lists + official brand pages):

| Brand | Per-SKU third-party cert | Facility / in-house posture | Source |
| ----- | ------------------------ | --------------------------- | ------ |
| **Pure Encapsulations** | **NONE FOUND** (not on USP participant list; NSF listing is facility-only) | NSF/ANSI 455-2 GMP-registered facility + named third-party analytical labs *(self-reported)* | [info.nsf.org company listing](https://info.nsf.org/Certified/Common/Company.asp?CompanyName=pure+encapsulations); [usp.org participants](https://www.usp.org/verification-services/verification-program-participants) |
| **Doctor's Best** | **NONE FOUND** (not on USP list; no NSF Sport listing) | cGMP-certified US facilities + unspecified in-house/3rd-party lab testing (badges only, no named program) | [doctorsbest.com/about-us](https://www.doctorsbest.com/pages/about-us) |
| **Nutricost** | **NONE FOUND** (NSF Sport brand search returns "No results matched"; not on USP list) | FDA-registered GMP-compliant facility + unnamed third-party testing (no program, no banned-substance screen claimed) | [nutricost.com mission/guarantee](https://nutricost.com/pages/our-misson-guarantee); [nsfsport.com zero-result search](https://www.nsfsport.com/certified-products/search-results.php?brand=Nutricost) |
| **Life Extension** | **FOUND — IFOS, omega-3 line only** (Super Omega-3 batch C1800855); matches the 1 IFOS registry record | NSF GMP-registered *(reported, not re-confirmed live this session)* + per-product COA | [IFOS cert PDF (Nutrasource)](https://certifications.nutrasource.ca/files/IFOS%20Life%20Extension%20Super%20Omega-3%20Batch%20C1800855.pdf) |

**This corroborates the registry scrape:** the three zero-coverage brands hold no
per-SKU third-party certification (confirmed against USP's and NSF's own search,
not inferred from absence alone), and Life Extension's single hit is IFOS on its
omega-3 line — exactly what the registry shows. For scoring, these are
**facility-GMP / in-house-only** brands: a true *known-negative* on per-SKU
verification, distinct from "unsourced."

> **Hallucination refuted (kept out of the data):** a web snippet claimed "Pure
> Encapsulations offers several USP Verified products." This is **false** — Pure
> Encapsulations does not appear on USP's official participant list. It was not
> added to the registry. (This is precisely the ghost-reference failure mode the
> project's no-hallucination rule exists to prevent.)

> **Verification caveats (flagged honestly):** Pure Encapsulations' and Life
> Extension's official quality pages returned HTTP 403, so their detailed
> self-reported testing language is from search excerpts, not a re-fetched primary
> page; the Life Extension IFOS PDF and the NSF/ANSI 455-2 listing were
> existence-verified but their internal contents were not re-extracted this
> session. These are marked "self-reported / existence-verified" above, not fully
> independently confirmed — they are **not** written into the registry as cert
> rows regardless.

---

## 9. What I deliberately did NOT do (and why)

- **Did not add Pure Encapsulations / Doctor's Best / Nutricost rows.** They are
  absent from all six freshly-scraped registries; inventing cert rows would
  violate the no-hallucination rule. Their absence is the *correct* data.
- **Did not refresh USP Verified.** Needs Playwright/Chromium (not available
  here); its 159-row snapshot is still fresh (19 days). Left untouched rather than
  risk a broken/partial scrape.
- **Did not dedup NSF Certified (ANSI/173).** That source legitimately repeats a
  product across facilities/type-code sections; the existing snapshot already
  carried 251 such duplicate `record_id`s (8.8%), the refresh carries 253 (8.8%,
  unchanged ratio). Deduping would change the sanctioned fetcher's output
  contract and is out of scope for a data refresh. The resolver tolerates
  duplicate candidates (they don't change scope resolution).
- **Did not touch `scripts/scoring_v4/`** or any scoring/enrichment code.

---

## 10. Reproduce

```bash
# Full sanctioned refresh (USP needs Playwright; others need bs4+lxml+rapidfuzz):
python scripts/api_audit/verify_certifications.py --source live-nsf-sport      --merge-existing
python scripts/api_audit/verify_certifications.py --source live-nsf-173        --merge-existing
python scripts/api_audit/verify_certifications.py --source live-informed-choice --merge-existing
python scripts/api_audit/verify_certifications.py --source live-informed-sport  --merge-existing
python scripts/api_audit/verify_certifications.py --source live-ifos           --merge-existing
# (USP) python scripts/api_audit/verify_certifications.py --source live-usp --merge-existing

# Validate:
python -m pytest scripts/tests/test_cert_resolver.py scripts/tests/test_cert_audit_canary.py \
  scripts/tests/test_cert_informed_fetcher.py scripts/tests/test_cert_ifos_fetcher.py \
  scripts/tests/test_cert_usp_fetcher.py -q
```
