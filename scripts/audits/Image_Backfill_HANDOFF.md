# Image Backfill Handoff — Professional Product Photos

> **Status:** Plan approved by user. Ready to implement.
> **Owner of next session:** the agent that picks this up.
> **Goal:** Replace ugly DSLD label PDF renders with professional bottle shots from Barcode Lookup API. Keep DSLD renders as a fallback. Wire the new images into the Flutter app.
> **Budget approved:** $99 (one month of Barcode Lookup Starter, then cancel).
> **Repos involved:** `dsld_clean` (this repo, Python) + `PharmaGuide ai` (Flutter app at `/Users/seancheick/PharmaGuide ai`).

---

## 1. Background — why we're doing this

PharmaGuide currently has two image sources running in production:

1. **OpenFoodFacts API** (live lookup, free, ~20–40% supplement coverage, varying quality)
2. **DSLD PDF page-1 render** (`scripts/extract_product_images.py`) — rasterizes the FDA-on-file label PDF into a 600×~250 WebP. Gets ~98% coverage but produces *unfolded label panel images* — readable but unprofessional. Aspect ratio is awkward (landscape strip), users don't recognize their bottle from it.

The user has seen apps like **Yuka, Suppco, Cronometer, MyFitnessPal** displaying clean studio bottle shots and asked how to match that quality without paying enterprise fees.

**How Yuka actually does it (not a shortcut you can replicate):**
- GS1 / GDSN brand-supplied feeds (enterprise pricing, ~$$$$/year)
- 50M+ users contributing photos for 8+ years
- Brands actively send official assets to Yuka because Yuka's score affects sales
- Curation team replacing user photos with brand-official ones over time

**What's realistic for PharmaGuide right now:**
- Pay for one month of Barcode Lookup ($99) → backfill ~5,000 products with pro images
- Cache them in Supabase Storage forever
- Cancel the subscription

**Why Barcode Lookup specifically:**
- We tested it with the user's demo key on 5 real supplements: 4/5 returned clean studio bottle shots on a CDN with `cache-control: max-age=31536000`. Image quality matches Yuka's bar.
- Sample images saved at `/tmp/bcl_test/*.jpg` if `/tmp` hasn't been cleared. (If gone, just rerun a query to verify.)
- Cheaper than SerpAPI ($75/mo for 5K = $0.015/call vs. $99 for 5K = $0.0198/call). SerpAPI has slightly better coverage but Barcode Lookup is good enough for the price difference.

The user explicitly approved Barcode Lookup over SerpAPI and UPC Item DB.

---

## 2. Current state — where things are

### 2.1 Pipeline side (this repo, `dsld_clean`)

| File | Role | Status |
|---|---|---|
| `scripts/extract_product_images.py` | Renders DSLD PDFs → `<dsld_id>.webp` | **Patched in last session** with retry/UA/backoff. Working. |
| `scripts/build_final_db.py` | Calls `backfill_image_thumbnails()` (line ~4098) to set `products_core.image_thumbnail_url = product-images/<dsld_id>.webp` | Working but the column is currently NULL because the build hasn't been re-run since the patch. |
| `scripts/sync_to_supabase.py` | Uploads `product_images/*.webp` to Supabase Storage bucket `product-images/` | Working. |

**Database:** `./assets/db/pharmaguide_core.db`
- 7,982 products total
- **5,687 have valid 12-13 digit UPCs** (`upc_sku` column) — this is what we feed Barcode Lookup
- 7,982 have a DSLD PDF URL (`image_url` ending in `.pdf`)
- 0 currently have `image_thumbnail_url` populated (build not re-run since cleanup)

### 2.2 Flutter side (`/Users/seancheick/PharmaGuide ai`)

**Image-display code (read these in this order):**

1. `lib/core/widgets/product_image.dart` — top-level widget. Calls `productImageResolverProvider`. Falls back to `BrandedPlaceholder` (colored square with brand initial).

2. `lib/services/product_image_resolver.dart` — **this is the one to modify.** Current priority chain:
   ```
   1. user_data.db local cache (product_image_cache table)
   2. OpenFoodFacts API by UPC
   3. → null → BrandedPlaceholder
   ```

3. `lib/data/database/tables/products_core_table.dart:30` — `image_thumbnail_url` column already exists in the schema. **Bug we found:** the resolver does NOT currently read this column. The DSLD label renders sitting in the Supabase bucket are never shown. Worth confirming with the Flutter dev whether this is intentional or a missed wire-up. Either way, the new plan needs the resolver to read both `image_thumbnail_url` (DSLD render) AND a new pro-image URL.

### 2.3 What images exist where

- **Supabase Storage bucket `product-images/`** — currently has DSLD-rendered WebPs from earlier pipeline runs. Don't delete.
- **Supabase Storage bucket `product-images-pro/`** — DOES NOT EXIST YET. Create it as part of this work.
- **Local `scripts/dist/` directory** — was cleaned up by the user between sessions. The DSLD-render pipeline output is currently not on disk locally. If you need it, rerun `extract_product_images.py` (cache at `/tmp/dsld_pdf_cache/` may also be cleared).

---

## 3. The plan — three phases

### Phase 1 — Build the backfill script (Python, this repo)

Create `scripts/backfill_pro_images.py`. Behavior:

```
Inputs:
  --db-path        : path to pharmaguide_core.db
  --output-dir     : local working dir for downloaded images
  --supabase-url   : from .env (SUPABASE_URL)
  --supabase-key   : from .env (SUPABASE_SERVICE_ROLE_KEY) — needed for bucket write
  --bcl-api-key    : from .env (BARCODE_LOOKUP_API_KEY)
  --max-calls      : default 4900 (leaves 100 headroom in 5K Starter quota)
  --priority-brands: optional comma-separated list to query first
  --resume         : skip products that already have a pro image

For each product in pharmaguide_core.db with a valid UPC:
  1. Skip if product-images-pro/<dsld_id>.webp already exists in Supabase
     (use HEAD request — don't waste an API call)
  2. Skip if we've burned --max-calls already this run
  3. Call: GET https://api.barcodelookup.com/v3/products?barcode=<upc>&key=<key>
  4. If response has products[0].images[] non-empty:
     a. Pick the largest image URL (HEAD request to compare Content-Length)
     b. Download it
     c. Open with Pillow, convert to RGB if needed
     d. Resize: max 600px on longest side, preserve aspect ratio
        (NO white-bg padding — preserves original quality)
     e. Save as WebP quality 85
     f. Upload to Supabase bucket product-images-pro/<dsld_id>.webp
  5. Log result (hit / miss / error) to backfill_report.json
  6. Sleep 1.2s between calls (Starter is 50/min, this stays well under)
  7. Honor 429 Retry-After if returned

Output:
  scripts/dist/pro_images/<dsld_id>.webp     (local copy, mirror of bucket)
  scripts/dist/backfill_report.json          (full audit trail)
  scripts/dist/backfill_report.txt           (human-readable summary)
```

**Critical implementation details:**

- **Retry/backoff:** copy the pattern from `extract_product_images.py:64` (the patched `download_pdf` function). Retryable status codes: `{429, 500, 502, 503, 504}`. Honor `Retry-After` header.
- **User-Agent:** `"PharmaGuide-DataPipeline/1.0 (+https://github.com/seancheick/dsld_clean)"`
- **Atomic writes:** write to `.tmp` then `os.replace()` — same as the DSLD script.
- **Quota safety:** read remaining quota from response headers if Barcode Lookup exposes them (`X-RateLimit-Remaining` is the common name; check their actual header in the first response). If not available, count locally and stop at `max-calls`.
- **Idempotent:** running twice should not double-spend API calls. Check Supabase first before calling the API.

**Priority queue order (do this for cost efficiency):**
1. Products with `brand_name IN ('Garden of Life', 'NOW Foods', 'NOW', 'Nature Made', 'Thorne', 'Pure Encapsulations', 'Nordic Naturals', 'Solgar', 'Jarrow', 'Doctor's Best', 'Optimum Nutrition')` — highest hit rate based on our 5-product test (4/5 of these brands hit).
2. Then everything else by `dsld_id ASC`.
3. Skip products with no UPC entirely (they can't be looked up).

**Test ahead of full run:**
- Run with `--max-calls 50` first, verify report shows expected hit rate, sample images look good visually.
- Then run with full `--max-calls 4900`.

### Phase 2 — Update Flutter resolver

File: `/Users/seancheick/PharmaGuide ai/lib/services/product_image_resolver.dart`

**New priority chain (replaces current):**

```
1. user_data.db local cache (existing — keep TTL logic)
2. Supabase product-images-pro/<dsld_id>.webp  ← NEW (highest priority real image)
3. OpenFoodFacts API by UPC                    ← existing live fallback
4. Supabase product-images/<dsld_id>.webp      ← NEW (DSLD render fallback)
5. → null → BrandedPlaceholder                 ← existing
```

**Implementation notes for the Flutter dev:**

- The Supabase bucket URL pattern is `${supabaseUrl}/storage/v1/object/public/product-images-pro/${dsldId}.webp` (assuming the bucket is set to public read access — confirm with backend before assuming).
- **Don't make a network call to verify the file exists** before returning the URL. Just return the URL and let `CachedNetworkImage` handle 404 → `errorWidget`. Keeps the resolver fast.
- For step 4 (DSLD fallback), the same pattern applies: `${supabaseUrl}/storage/v1/object/public/product-images/${dsldId}.webp`.
- Consider adding a "tier" field to the cache so we can tell whether the cached URL is pro/OFF/DSLD/none. Useful for upgrade flows later (e.g., if a pro image becomes available after a DSLD fallback was cached, we want to evict the DSLD one).

The Flutter dev was already pinged in the previous session about a different feature (`functional_roles[]` rendering — see `scripts/audits/functional_roles/FLUTTER_HANDOFF.md`). This is a separate, parallel piece of work.

### Phase 3 — Run, verify, document

1. User pays for Barcode Lookup Starter ($99/month, 5,000 calls).
2. Add `BARCODE_LOOKUP_API_KEY` to `.env`.
3. Create the `product-images-pro` Supabase bucket (public read, authenticated write). Confirm bucket name with user — they may want a different name.
4. Run `python3 scripts/backfill_pro_images.py --max-calls 50` — smoke test.
5. Visually verify ~10 random WebPs from the test batch in Finder. Quality should match `/tmp/bcl_test/*.jpg` from previous session.
6. Run full backfill `python3 scripts/backfill_pro_images.py --max-calls 4900`.
7. Review `backfill_report.txt`:
   - Expected hit rate: 60–80% based on 5-product test
   - Total images uploaded: should be 3,000–4,500
   - Any error patterns?
8. Update `products_core.image_thumbnail_url` for products that got pro images (or leave unchanged — Flutter resolver builds the URL pattern itself, doesn't strictly need this column updated).
9. Run `sync_to_supabase.py` to push any DB changes if needed.
10. Verify in Flutter app: scan a Garden of Life product, should see the pro image immediately.
11. **User cancels the Barcode Lookup subscription.**
12. Update this handoff doc with actual numbers (hit rate, brands covered, gaps remaining).

---

## 4. Cost & quota analysis

| Plan | Cost | Calls | Calls/min | What it covers |
|---|---|---|---|---|
| Demo | $0 | 50/month, 50/min | 50/min | Useless — already burned 5 in testing |
| **Starter** | **$99/mo** | **5,000** | **50/min** | **~5,000 of our 5,687 UPC products** ✅ recommended |
| Advanced | $249/mo | 25,000 | unstated | Overkill for one-time backfill |

**5,687 UPC-having products vs 5,000 quota:**
- Hit rate test (n=5): 80%
- Expected hits at full scale: 4,500 products with pro images
- Misses: ~1,200 products (mostly older GNC SKUs, niche brands)
- Products with no UPC: 2,295 — these stay on DSLD fallback forever

**Two-month strategy if hit rate disappoints:**
- Month 1: $99 → cover top brands (5,000 calls)
- Month 2: $99 → second pass on misses with brand+name search instead of barcode (Barcode Lookup also supports search queries)
- Total: $198 max

**Don't go beyond two months.** After that, the marginal coverage isn't worth it. Long-tail products will stay on DSLD fallback.

---

## 5. Open questions for next session

Before writing code, the next agent should confirm with the user:

1. **Bucket name:** is `product-images-pro` the right Supabase bucket name? Or should it overwrite `product-images/`? (Recommendation: keep them separate so DSLD fallback is preserved, but ask.)
2. **Image dimensions:** 600px max on longest side, preserve aspect ratio, no padding. Confirm? (Some apps force 600×600 with white background for grid consistency. We're not doing that based on user feedback that DSLD landscape strips were "fine, just use them as-is.")
3. **WebP quality:** 85 (vs. 80 for DSLD renders) — slightly higher because these are pro photos worth preserving. Confirm.
4. **Resolver wire-up:** does the user want the Flutter dev to do this in parallel, or wait for backfill to complete first? (Recommendation: wait — gives us a known-good dataset to test against.)
5. **The Flutter resolver bug:** the current resolver doesn't read `products_core.image_thumbnail_url`. Is this intentional? If yes, why? If no, who fixes it?

---

## 6. Files to read at session start

In this order, before writing any code:

1. **This file** — `scripts/audits/image_backfill/HANDOFF.md` (you're reading it)
2. `scripts/extract_product_images.py` — copy the retry/backoff pattern from here
3. `scripts/sync_to_supabase.py` — see how Supabase Storage uploads are done elsewhere (around line 504 `upload_product_images`)
4. `scripts/build_final_db.py:4098` — `backfill_image_thumbnails()` for reference on how `image_thumbnail_url` is currently set
5. `/Users/seancheick/PharmaGuide ai/lib/services/product_image_resolver.dart` — Flutter side, full file is short

Do NOT re-read these unless modifying them:
- `lib/core/widgets/product_image.dart` (already analyzed, just orchestration)
- `lib/data/database/tables/products_core_table.dart` (just confirms column exists)

---

## 7. Test data — verify with real UPCs

When testing the script, use this set first (mix of expected hits and misses based on our prior test):

| dsld_id | brand | UPC | Expected |
|---|---|---|---|
| 1000 | GNC | 048107058432 | MISS (older SKU) |
| 1002 | GNC | 048107070496 | HIT |
| 173708 | Garden of Life | 658010112383 | HIT |
| 204501 | Garden of Life | 658010117425 | HIT |
| 233619 | Garden of Life | 658010113878 | HIT (high-res, ~680 KB original) |

Sample API call format (curl):
```bash
curl -s "https://api.barcodelookup.com/v3/products?barcode=658010112383&key=$BARCODE_LOOKUP_API_KEY"
```

Response shape (relevant fields only):
```json
{
  "products": [
    {
      "title": "Garden of Life FYI Restore...",
      "brand": "Garden Of Life",
      "category": "Health & Beauty > ...",
      "images": ["https://images.barcodelookup.com/1034/10348585-1.jpg"]
    }
  ]
}
```

Empty `images: []` = miss. Multiple URLs = pick the largest.

---

## 8. Definition of done

- [ ] `scripts/backfill_pro_images.py` exists, has tests in `scripts/tests/test_backfill_pro_images.py`
- [ ] Smoke test (50 calls) passes with visually verified images
- [ ] Full run completes; `backfill_report.txt` shows ≥60% hit rate
- [ ] All pro images uploaded to Supabase `product-images-pro/`
- [ ] Flutter resolver updated to use new priority chain (or handed to Flutter dev)
- [ ] User confirms in-app: scan a Garden of Life product, sees pro image
- [ ] User cancels Barcode Lookup subscription
- [ ] This handoff doc updated with actual final numbers

---

## 9. What NOT to do

- ❌ Do NOT delete the existing `product-images/` Supabase bucket — that's the DSLD fallback.
- ❌ Do NOT hardcode the Barcode Lookup API key. Use `.env`.
- ❌ Do NOT call the API for products without UPCs. Wasted calls.
- ❌ Do NOT exceed `--max-calls 4900` in a single month. Quota is hard-capped at 5,000.
- ❌ Do NOT use the demo key (50/month) for the real run — it's already at 45/50 remaining and will block.
- ❌ Do NOT rehost images via hotlink to `images.barcodelookup.com`. Download once, store in Supabase. (URLs there have 1-year cache headers but are not guaranteed permanent.)
- ❌ Do NOT generate AI images as a fallback. Clinical product, fake bottles = fraud risk.
- ❌ Do NOT scrape Amazon/iHerb. ToS violations, captchas, fragile.

---

## 10. Reference — what we explored and rejected

| Option | Why rejected |
|---|---|
| SerpAPI Google Shopping ($75/mo) | Slightly better coverage but ~$25 more for marginal gain |
| UPC Item DB ($20/mo) | Lower image quality than Barcode Lookup, mixed thumbnails |
| Amazon Product Advertising API | Requires active Associates account with sales; image rights restrict to "alongside Amazon link" |
| iHerb scraping | Cloudflare + bot detection; not feasible without paid proxies |
| GS1 Data Hub | Enterprise pricing, out of budget |
| Brand press-kit outreach | Best long-term but slow (~2 weeks for top 20 brands); good Phase 2 follow-up after this backfill |
| User-submitted photos | Best long-term ($0, fully licensed); requires building a photo-submission flow in Flutter — separate initiative |
| Hotlinking images.barcodelookup.com URLs | URL rot risk; 1-year cache header is good but not permanent |

---

## 11. Memory entries to consider creating after this ships

- `project_image_backfill_complete.md` — what we did, hit rate, cost, what's still on DSLD fallback
- `feedback_image_quality_priorities.md` — user prefers pro studio shots over DSLD label renders, willing to pay one-time fee for quality
- `reference_barcode_lookup_api.md` — quota, pricing tiers, image CDN behavior, what worked and didn't

Don't create these now. Create them after the work is verified done.

---

**End of handoff.** Next agent: read this top to bottom, ask the user the open questions in Section 5, then build Phase 1.
