
PharmaGuide
Flutter MVP — Developer Specification
Version 5.1  |  Pipeline Contract Aligned
B&Br Technology  ·  Confidential

March 2026

Data Contract Changelog
Date	Change	Impact
2026-03-18	interaction_summary added to detail blob (condition_summary + drug_class_summary)	New Condition Alert Banner on scan result. Profile condition/medication chips must map to exact taxonomy IDs.
2026-03-18	dose_threshold_evaluation added to interaction warnings	Interaction warnings can now show dose-specific context (e.g. "600mcg exceeds 200mcg/day pregnancy limit").
2026-03-18	score_bonuses/score_penalties enriched with type, source, category, mechanism	Enables richer Pros and Considerations UI. See Section 6.10.
2026-03-18	reference_data.interaction_rules grew to ~95KB (45 rules)	Adjust memory budget for startup parse. Still well within limits.
2026-03-18	clinical_risk_taxonomy: 14 conditions, 9 drug classes	Profile chips must map exactly to these IDs. Any mismatch breaks interaction flagging.
2026-03-18	harmful_additive warnings now carry reference_notes and mechanism	Card 2 can show richer additive detail (why it's harmful, not just that it is).
2026-03-18	Section E (dose adequacy) for omega-3 products	Folded into quality score. Show as sub-row in Card 1 for omega-3 products only.
 
Section 1 — Project Overview & Architecture

What We Are Building
PharmaGuide is a premium health-tech Flutter app: scan supplement barcodes, get instant clinical-grade safety scores, manage a personal stack, and chat with an AI Pharmacist. Built fast, privacy-first, and premium from day one.

PIPELINE DELTA — Changed from previous spec version
v5 MAJOR CHANGE: Data architecture updated to match the frozen pipeline contract (Export Schema v1.2.0).
Primary scan/search data source is now local SQLite (pharmaguide_core.db), NOT direct Supabase queries.
Supabase is used ONLY for: detail blobs, user stack/auth data, AI proxy, DB version checks.
Score sub-section maxima corrected: /25 /30 /20 /5 (not /25 /35 /15 /5 as in prior versions).
FitScore (personal 20pts) is now formally named score_fit_20. Computed on-device. Never stored in DB.
Interaction summary added to scan result for instant condition flagging (MVP: banner only).

Tech Stack
Frontend	Flutter (iOS + Android) — Impeller rendering engine enabled
Local DB	SQLite via drift (RECOMMENDED over raw sqflite) — pharmaguide_core.db ships with app. Primary data source.
Local Cache DB	Same SQLite file: product_detail_cache, user_profile, user_stacks, scan_history tables
Remote Auth/Data	Supabase Auth (Google, Apple, Email, Anon) + detail blob storage + user sync
State Mgmt	Riverpod 2.0+ with @riverpod generator. Mandatory. No Bloc.
Scoring	score_quality_80 from SQLite. score_fit_20 computed on-device via ScoreFitCalculator.
AI Chat	Gemini 2.5 Flash-Lite via Supabase Edge Function proxy. Verify current free tier limits before launch.
Animations	Rive — scanner bracket, score ring, success states.
Fonts	Inter (Google Fonts package)

Data Architecture — Hybrid SQLite + Supabase
The Two-Layer Data Model
Layer 1 — Local SQLite (pharmaguide_core.db):
  Ships bundled with the app (or downloaded on first launch if too large).
  Contains: products_core (~180k products), products_fts, reference_data, export_manifest.
  Instant offline access for scan lookups and search. No network required.
  Updated in background when pipeline produces a new export version.

Layer 2 — Supabase (remote):
  Detail blobs: one JSON per product ({dsld_id}.json). Fetched on first product view, cached locally.
  User data: Supabase Auth, user_sync_data (stack, profile backup for signed-in users).
  AI proxy: Supabase Edge Function wrapping Gemini API.
  DB version check: app reads export_manifest on launch, compares to Supabase manifest.

Scoring Architecture
Score Fields and Their Sources
score_quality_80 — Pipeline precomputed. Stored in products_core SQLite. Max 80 pts.
score_100_equivalent — Derived convenience field (score_quality_80 / 80 * 100). Also in SQLite.
score_fit_20 — NEVER in DB. Computed on-device by ScoreFitCalculator using user_profile + reference_data.
score_combined_100 — (score_quality_80 + score_fit_20) * 100/100. Computed on-device.

Sub-section scores (from products_core, used in accordion cards):
  score_ingredient_quality  — max 25
  score_safety_purity       — max 30  (NOTE: was listed as /35 in prior spec — pipeline is authoritative)
  score_evidence_research   — max 20  (NOTE: was listed as /15 in prior spec — corrected)
  score_brand_trust         — max 5

Display logic:
  No profile: show score_100_equivalent. Label: "Base Quality Score".
  Profile exists: show score_combined_100. Label: "Your Match Score".
  NOT_SCORED products: show "Not Scored" — NEVER show 0 or null.

Freemium Limits
Scan Limits by Auth State
Guest: 3 scans lifetime — tracked in Hive (guest_scan_count). No SharedPreferences.
Signed In (free): 10 scans/day. Tracked in Supabase user_usage table.
AI Chat: 5 messages/day for free users. Tracked in Supabase user_usage.
Client check (Hive/Riverpod) gates UI. Supabase enforces server-side for signed-in users.

Supabase Tables (Remote Only)
user_stacks	id, user_id, dsld_id, dosage, timing, supply_count, added_at
user_usage	id, user_id, scans_today, ai_messages_today, reset_date
pending_products	id, user_id, upc, product_name, brand, image_url, status, submitted_at
💡 user_profiles is NOT a Supabase table. Health/fit data lives in local SQLite user_profile table. Never synced to cloud in MVP.
 
Section 2 — Global Design System

Color Palette
Primary Brand	#0D9B8A  — buttons, active states, score rings
Brand Light	#E6F7F5  — tinted info boxes, tease banners
Background	#FAFAFA  — page background (never pure white)
Card Surface	#FFFFFF  — cards, modals, sheets
Heading Text	#1A1A1A  — never pure #000000
Body Text	#374151
Muted / Labels	#6B7280
Dividers	#E5E7EB
Score Green	#10B981  — score >= 70 / positive flags
Score Yellow	#F59E0B  — score 40-69 / warnings
Score Red	#EF4444  — score < 40 / critical flags
Score Orange	#F97316  — sub-clinical dose / moderate clinical warnings

Typography — Inter
Display / Hero	Inter Bold, 32sp
Page Title	Inter Bold, 24sp
Section Header	Inter SemiBold, 18sp
Body	Inter Regular, 14sp
Caption	Inter Regular, 12sp, #6B7280
Button	Inter SemiBold, 15sp
Code / Tech	Courier New, 13sp — for raw label text display only

Spacing & Grid
Base Grid	8dp — all spacing is multiples of 8
Page Padding	16dp horizontal, 16dp vertical
Card Padding	16dp all sides
Card Radius	16dp
Button Radius	12dp
Sheet Radius	24dp top corners only
Chip Radius	20dp

Shadows — One Style Only
BoxShadow(
  color: Color(0x1A000000),
  blurRadius: 20,
  offset: Offset(0, 4),
)
// No other shadow variants. No harsh or dark shadows anywhere.

Motion & Haptics
•	Score ring: Rive animation, count-up from 0 to final score, 900ms ease-in-out.
•	Scanner bracket: Rive, 3 states — idle (static), scanning (pulse), success (green fill + checkmark).
•	Bottom sheets: slide up 280ms ease-out.
•	Accordion cards: AnimatedSize for expand/collapse. Chevron rotates 180deg.
•	Successful scan haptic: HapticFeedback.heavyImpact().
•	B0 critical warning haptic: HapticFeedback.vibrate() double pulse.
•	Primary button tap: HapticFeedback.lightImpact().

Modal / Sheet Rules
•	NEVER use showDialog() or AlertDialog for any user-facing interaction.
•	ALWAYS use showModalBottomSheet() with rounded top corners (radius 24dp).
•	Sheets must have a drag handle: 4x36dp rounded pill, #E5E7EB, centered top.
•	Sticky action buttons inside sheets fixed to bottom with safe area padding.

Animations — Rive
•	Use Rive for: scanner bracket, score ring, success checkmarks, empty state illustrations.
•	For simple transitions (sheet open, tab switch): Flutter AnimationController.
•	Do NOT use Lottie. Rive is faster on Flutter Impeller.

State Management — Riverpod 2.0+
// All providers use @riverpod annotation.
@riverpod
Future<ScanCardData?> productByUpc(ProductByUpcRef ref, String upc) async {
  return ref.read(localDbRepoProvider).fetchProductByUpc(upc);
}

// AsyncValue in UI:
// productAsync.when(
//   loading: () => ShimmerCard(),
//   error: (e, _) => ErrorToast(message: e.toString()),
//   data: (p) => ScanResultScreen(product: p),
// )
 
Section 3 — Authentication & Freemium Logic

Auth Providers
•	Google Sign-In (google_sign_in + Supabase OAuth)
•	Apple Sign-In (sign_in_with_apple — REQUIRED for iOS App Store)
•	Email + Password (Supabase Auth built-in)
•	Anonymous Guest (Supabase anon session — no sign-in required to open app)

Auth Flow — First Launch
1.	App opens. Check for existing Supabase session.
2.	If none: create anonymous Supabase session silently (no prompt).
3.	User can scan up to 3 times as guest. Tracked in Hive guest_scan_count.
4.	On 3rd scan: show sign-up bottom sheet (not a blocking page).
5.	On sign-in: migrate anonymous scan history to authenticated user ID.

User State Enum
enum UserState {
  guest,        // Anon session. 3 lifetime scans from Hive.
  freeUser,     // Signed in. 10 scans/day, 5 AI msgs/day.
  premiumUser,  // Future. Unlimited.
}

Freemium Enforcement
Scan Limit Logic
Guest: Hive guest_scan_count. If >= 3 show upgrade sheet.
Do NOT use SharedPreferences. Hive is the only local KV store.
Free user: query Supabase user_usage (scans_today, reset_date).
If scans_today >= 10 AND reset_date = today: show upgrade sheet.
Increment AFTER successful score fetch, not on barcode read.
Supabase RLS validates server-side for signed-in users.

Scan Limit Sheet UI
•	Title: "You've hit your daily limit"
•	Guest subtext: "Sign in for 10 free scans per day."
•	Free user subtext: "Upgrade to PharmaGuide Pro for unlimited scans."
•	Guest CTA: "Sign In — It's Free" (primary brand color)
•	Free user CTA: "Explore Pro" (leads to coming-soon screen — no paywall yet)
•	"Maybe Later" text button (muted)
 
Section 4 — Navigation: Floating Tab Bar

Overview
Custom floating nav bar above the bottom safe area. Frosted glass background (BackdropFilter blur). Subtle top shadow. Floats with 16dp margin on all sides — does NOT sit flush with the edge.

Implementation
Stack(
  children: [
    Positioned.fill(child: _currentTab),
    Positioned(bottom: 16, left: 16, right: 16, child: FloatingTabBar()),
  ],
)

ClipRRect(
  borderRadius: BorderRadius.circular(24),
  child: BackdropFilter(
    filter: ImageFilter.blur(sigmaX: 20, sigmaY: 20),
    child: Container(
      decoration: BoxDecoration(
        color: Colors.white.withOpacity(0.85),
        borderRadius: BorderRadius.circular(24),
        boxShadow: [BoxShadow(color: Color(0x1A000000), blurRadius: 20, offset: Offset(0, 4))],
      ),
    ),
  ),
)

Tab Items
State	Trigger	Design / Content	Dev Notes
Home	Index 0	House icon. Active: filled brand. Inactive: outline grey.	—
Stack	Index 1	Layers icon. Active: filled brand. Inactive: outline grey.	—
Scan	Index 2	56dp circular button, brand color BG, white icon. Elevated above bar via Transform.translate(offset: Offset(0,-8)).	Primary CTA — must feel prominent.
AI Chat	Index 3	Chat bubble icon. Active: filled brand. Inactive: outline grey.	—
Profile	Index 4	Person icon. Active: filled brand. Inactive: outline grey.	—
💡 Labels visible ONLY for active tab (animated fade-in). Inactive: icon only. Keeps bar compact.
 
Section 5 — Home Tab

Screen Layout
6.	Header (greeting + connectivity status)
7.	Search Bar
8.	Hero Card (two states)
9.	Recent Scans Carousel
10.	Daily AI Insight Card
Bottom padding: 100dp for floating tab bar.

5.1 — Header
Top Left	"Good morning," — Inter Regular 14sp, grey. "[First Name]" — Inter Bold 28sp, charcoal.
Top Right	Connectivity: online = hidden. Offline = grey cloud-off icon 20dp.
Offline tap	Bottom sheet: "You're offline. Scanning and AI chat require internet. Your stack is available."

5.2 — Search Bar
Style	Full-width, 48dp height, background #F3F4F6, radius 12dp, no border.
Icons	Left: search icon 20dp grey. Right: microphone icon.
Placeholder	"Search supplements or medications..."
On tap	Navigate to SearchScreen. Uses local SQLite FTS (products_fts table). Instant results.

5.3 — Hero Card
State A: New User (Zero Stack)
Onboarding Hero Card
Teal-to-green gradient background. No score ring.
Caption: "Welcome to PharmaGuide".
Headline: "Let's build your health stack."
Subtext: "Scan your first supplement to get started."
CTA button (white, brand text): "Scan First Product" — navigates to Scan tab.

State B: Active User
Active Hero Card
Same gradient. 80dp Rive score ring left. Right column white text:
  "X products in stack"
  "Interaction risk: Low / Moderate / High"
  "X meds scheduled today"
Ring color: green >= 70, yellow 40-69, red < 40.
Tap: navigates to Stack tab.

5.4 — Recent Scans Carousel
Header	"Recent Scans" + "View All" (brand color right)
Layout	Horizontal ListView with snap. Item width 140dp.
Card	White card, radius 12dp, shadow. Product image 80x80dp. Name (2 lines max). Score badge.
Score Badge	Pill: colored BG, white score. Bottom-right of image.
NOT_SCORED	Show "Not Scored" badge (grey) instead of score. Never show 0.
PDF image	If image_url ends in .pdf: show placeholder illustration, not a broken image.
Empty	Dashed border card: "Scan something to see it here."

5.5 — Daily AI Insight
Style	White card, radius 12dp, shadow. Sparkle icon (brand color) left.
Content	One AI-generated tip. Personalized if user_profile has data. Generic fallback if not.
Cache	New tip each app open. Cached 24h. Do not call AI on every home screen render.
 
Section 6 — Scan Tab

6.1 — Camera View
Package	mobile_scanner
Overlay	Rive bracket: 3 states — idle (white static), scanning (pulse), success (green + checkmark).
Controls	Top-left: back/close. Top-right: flash toggle. Bottom-center: "Enter Code Manually" text btn.
No lasers	No animated scan lines. Rive bracket only.

6.2 — Permission Handling
State	Trigger	Design / Content	Dev Notes
First launch	Tab opened	OS native camera permission dialog.	permission_handler package.
Granted	User approves	Camera activates immediately.	—
Denied	User denies	Bottom sheet: lock icon + "Camera access needed." + "Enable in Settings" + "Enter Code Manually".	openAppSettings().

6.3 — Scan Flow (Happy Path)
11.	Camera detects UPC/EAN barcode.
12.	Haptic: HapticFeedback.heavyImpact(). Rive bracket success state.
13.	Pause camera.
14.	Green banner slides from top: "Product Identified" — auto-dismiss 1.5s.
15.	Check scan limit (Section 3). If over limit: show limit sheet. Stop.
16.	Query LOCAL SQLite products_core WHERE upc_sku = ?. Instant. No network.
17.	Handle UPC collision: if COUNT(*) > 1 for this UPC, apply deterministic ordering (active first, highest score_quality_80, lowest dsld_id). Show chooser if still ambiguous.
18.	If verdict = BLOCKED or UNSAFE: navigate to B0 Critical Warning screen (Section 6.4). Stop.
19.	If user_profile has health data: run ScoreFitCalculator.calculate() locally.
20.	Run instant condition check via interaction_summary from detail blob IF already cached. Show condition banner if flagged (Section 6.5.4).
21.	Slide up full Result Screen.
22.	In background: check product_detail_cache. If not cached and online: fetch {dsld_id}.json from Supabase, cache, then hydrate accordion cards.

6.4 — B0 Gate: Critical Warning Screen
B0 Gate fires when: verdict = BLOCKED or verdict = UNSAFE
Standard score ring: HIDDEN.
5-pillar accordion cards: HIDDEN.

Score ring replaced by solid red circle (100dp):
  Center: X icon (white, 40dp). No number. No animation.
  Label below: "BLOCKED" or "UNSAFE" — Inter Bold 16sp red.

Critical Warning card (full-width, bg #FEF2F2, border #EF4444):
  "CRITICAL WARNING" — Inter Bold 18sp red + warning icon 32dp.
  "Severity:" + blocking_reason value from products_core (e.g. "banned_ingredient").
  Full warning detail from warnings[] where type = banned_substance or recalled_ingredient.
  "Do not use this product. Consult your healthcare provider."

Sticky buttons: "Report This Product" (red filled) + "Scan Another Product" (outline).
Haptic: double pulse vibration.
⚠️  Never show score, grade, or any positive UI element when B0 fires. Safety overrides design.

6.5 — Result Screen: Full Clinical Breakdown
6.5.1 — Screen Layout
23.	Hero Section — sticky top
24.	Verdict Banner — full-width color strip
25.	Condition Alert Banner — if user conditions intersect interaction_summary (new)
26.	5 Pillar Smart Cards — scrollable accordion
27.	Sticky Action Buttons — fixed bottom

6.5.2 — Hero Section (Sticky)
Design
Product image 72x72dp, radius 8dp. Handle PDF URLs: if image_url ends in .pdf, show placeholder.
Product name Inter Bold 18sp. Brand Inter Regular 13sp grey.
Verified checkmark (green, if verdict = SAFE and has_banned_substance = false).

Rive Score Ring (100dp):
  NOT_SCORED: show "Not Scored" text. No ring animation.
  No profile: count-up to score_100_equivalent. Label "Base Quality Score" grey.
  Profile exists: count-up to score_combined_100. Label "Your Match Score" brand color.
  Ring color: green >= 70, yellow 40-69, red < 40.
  Show grade word below ring: Exceptional / Excellent / Good / Fair / Below Avg / Low / Very Poor.

Percentile chip (if percentile_top_pct is not null):
  e.g. "Top 12% in Multivitamins" — small teal chip below grade.

Profile Tease Banner (no profile only):
  Brand-light box. Lock icon + "Is this right for YOU?"
  "Add your health goals to unlock your Personal Match Score."
  Tappable: navigates to Profile health context.

Discontinued / Off-Market Badge (if product_status != active):
  Orange pill badge: "Discontinued" or "Off Market" + discontinued_date if present.

6.5.3 — Verdict Banner
SAFE	Green #D1FAE5. "Passes all safety checks."
CAUTION	Yellow #FEF3C7. "Review flagged items below."
POOR	Orange #FFF7ED. "Low quality — review before use."
UNSAFE	Red #FEE2E2. "Safety concerns detected."
NOT_SCORED	Grey #F3F4F6. "Insufficient data to score this product."

6.5.4 — Condition Alert Banner (NEW)
Instant Condition Flagging via interaction_summary
Read interaction_summary from the detail blob (if cached). Do not re-compute from warnings[].
Intersect interaction_summary.condition_summary.keys with user_profile.conditions.

If intersection is non-empty: show a prominent orange banner ABOVE the accordion cards.
  Icon: warning triangle.
  Title: "Flagged for your health conditions".
  Body: list of flagged condition names + highest_severity for each.
  Example: "Pregnancy — Contraindicated: Contains Vitamin A Palmitate above safe threshold."
  CTA: "View Details" — expands Card 3 (Clinical Evidence) and auto-scrolls to interaction warnings.

If no intersection: banner is hidden.

Code pattern (from Flutter Data Contract v1):
final summary = blob['interaction_summary'];
if (summary != null) {
  // Check user health CONDITIONS (pregnancy, diabetes, hypertension, etc.)
  final userConditions = userProfile.conditions; // {'pregnancy', 'diabetes'}
  final flaggedConditions = userConditions.intersection(
    Set<String>.from((summary['condition_summary'] as Map?)?.keys ?? [])
  );
  for (final condition in flaggedConditions) {
    final info = summary['condition_summary'][condition];
    // info['highest_severity'] = "contraindicated"
    // info['ingredients'] = ["Vitamin A Palmitate"]
    // info['actions'] = ["Do not use preformed Vitamin A..."]
    showConditionBanner(condition, info);
  }

  // Check user MEDICATIONS (anticoagulants, hypoglycemics, statins, etc.)
  final userDrugClasses = userProfile.drugClasses; // {'anticoagulants', 'hypoglycemics'}
  final flaggedDrugs = userDrugClasses.intersection(
    Set<String>.from((summary['drug_class_summary'] as Map?)?.keys ?? [])
  );
  for (final drugClass in flaggedDrugs) {
    final info = summary['drug_class_summary'][drugClass];
    // info['highest_severity'] = "avoid"
    // info['ingredients'] = ["Omega-3 Fish Oil"]
    // info['actions'] = ["May enhance anticoagulant effect..."]
    showMedicationBanner(drugClass, info);
  }
}

6.6 — The 5 Pillar Smart Cards
Tappable accordion rows. Default: all collapsed. Header always visible. Tap to expand/collapse inline via AnimatedSize. Sub-score pill color: green >= 80% of max, yellow 50-79%, red < 50%.

Card 1 — Ingredient Quality  (score_ingredient_quality / 25)
Data sources: products_core + detail blob section_breakdown.ingredient_quality
Collapsed header: "Ingredient Quality" + sub-score pill (e.g. "22/25").

Expanded content:
  "Active Ingredients" list from ingredients[]:
    Each row: ingredient name. If in premium_forms or bio_score >= 10: green "Premium Form" badge.
    If bio_score < 5: grey "Standard Form" badge.
    Show dosage + unit if present (e.g. "400 mg").
    Raw label text shown in small monospace caption below name.

  Delivery System row:
    delivery_tier from section_breakdown or formulation_detail.
    Tier 1 (Liposomal/Nanoemulsion): green badge.
    Tier 2 (Enteric/Time-release): blue badge.
    Tier 3 (Standard): grey badge.

  Probiotic Excellence (show only if probiotic_detail present):
    Teal badge "Probiotic Excellence".
    Below: CFU count + strain count from probiotic_detail.

  Omega-3 Dose Adequacy (show only for omega-3 products with Section E data):
    If section_scores.E_dose_adequacy.applicable = true:
      Blue info row: dose_band label (e.g. "AHA Cardiovascular Dose") + per_day_mid_mg value.
      Sub-text: "EPA: Xmg + DHA: Ymg per serving = Zmg/day combined."
    This data is folded into the quality score but displayed here for transparency.

Card 2 — Safety & Purity  (score_safety_purity / 30)
Data sources: products_core boolean columns + detail blob warnings[] + compliance_detail
Collapsed header: "Safety & Purity" + sub-score pill.
If has_harmful_additives or has_allergen_risks: card header shows small warning dot.

"The Good" section — show only TRUE certifications:
  Green pill: "Vegan Certified" if is_vegan = 1.
  Green pill: "Gluten-Free" if is_gluten_free = 1.
  Green pill: "NSF GMP Certified" if cert_programs contains "NSF_GMP".
  Green pill: "Batch Traceability" if compliance_detail.batch_traceability = true.

"Flagged Items" section — show only if flags present:
  Proprietary blend warning (yellow row) if proprietary_blend_detail.present = true:
    "Opacity Penalty: Contains proprietary blends. Exact dosages are hidden."
  Harmful additives (red rows with X) from warnings[] where type = harmful_additive.
    Show: title + mechanism_of_harm + population_warnings.
  Allergen rows (yellow with warning icon) from warnings[] where type = allergen.
    Show: title + supplement_context + prevalence chip.

Card 3 — Clinical Evidence  (score_evidence_research / 20)
Data sources: detail blob evidence_data + warnings[] type=interaction/drug_interaction
Collapsed header: "Clinical Evidence" + sub-score pill.
If condition alert fired: card border pulses (brand color) and auto-expands.

SUB_CLINICAL_DOSE warning (orange card at top, if any ingredient flagged):
  "Sub-Clinical Dose Detected".
  "One or more ingredients are below the minimum effective dose in clinical research."
  List affected ingredient names.

Interaction / Drug Interaction warnings from warnings[]:
  Each row: severity badge + title + action text.
  Severity badges: Contraindicated (red), Caution (yellow), Monitor (orange), Established (blue).
  evidence_level chip: "Established", "Probable", "Theoretical".
  Citation link if sources[] is non-empty.

  Dose Threshold Context (if doseThresholdEvaluation is present on the warning):
    Show below the action text in a muted info box:
    "This warning applies because the serving contains [product_dose] [unit],
     which [exceeds/is below] the [threshold_value] [unit]/day limit for [condition]."
    Example: "Serving has 3000mcg Vitamin A (retinol), exceeding the 3000mcg/day UL for pregnancy."
    Only show when threshold_met = true. If threshold_met = false, the base severity applies silently.

Clinical Matches from evidence_data:
  Study type badges: RCT (dark blue), Systematic Review (purple), Meta-Analysis (teal), Observational (grey).
  "View Studies" text button: opens bottom sheet listing study descriptions.

Card 4 — Brand Trust  (score_brand_trust / 5)
Data sources: products_core + manufacturer_detail + warnings[] type=status
MANUFACTURER_VIOLATION check first (from score_penalties or manufacturer_detail):
  If present: card header bg #FEE2E2, border #EF4444, sub-score pill red.
  Expanded: red row "Manufacturer Violation" + violation detail text.

Boolean rows (checkmark green / X red):
  "Trusted Manufacturer" — is_trusted_manufacturer
  "Third-Party Tested"   — has_third_party_testing
  "Full Disclosure"      — has_full_disclosure
  Rows from manufacturer_detail if present.

Product status warning (if product_status != active):
  Warning row from warnings[] where type = status.
  Show: discontinued date or off-market label.

Card 5 — Your Personal Match
Data source: LOCAL SQLite user_profile + reference_data + ScoreFitCalculator output. Never from Supabase.
Collapsed header: "Your Personal Match" + adjustment chip ("+X" green / "-X" red / dash if no profile).

State A — No profile (Locked):
  Lock icon + "Unlock Your Match".
  Expanded: "Complete your health profile to see personal goal alignment, condition safety, and dosage fit."
  CTA: "Set Up My Profile" navigates to Profile tab.

State B — Profile exists:
  FitScoreResult.chips rendered from ScoreFitCalculator.
  Positive chip (green): e.g. "Aligns with Sleep goal".
  Warning chip (yellow): e.g. "Approaching Upper Limit for Vitamin A".
  Negative chip (red): e.g. "Contains Dairy (your allergen)".
  Condition chip (red): e.g. "Caution: Hypertension — sympathomimetic ingredient".
  Max 4 chips visible. "+X more" expands inline.
  If chips empty but profile exists: "No personal conflicts detected."

IMPORTANT: missingFields from FitScoreResult:
  If profile is partial, show: "Complete your profile for a full match score." with missing field names.

6.7 — Sticky Action Buttons
Primary	"Add to Stack" — full-width, brand color, 52dp, radius 12dp.
Secondary	"Ask AI Pharmacist" — full-width, outlined, same sizing.
B0 state	"Report This Product" (red filled) + "Scan Another" (outline).

6.8 — Post-Scan: Add to Stack Flow
28.	"Add to Stack" tapped. Rive success checkmark + "Added to Stack" banner.
29.	Single bottom sheet: "Set a Schedule?" — AM / PM / Custom chips.
30.	Same sheet animates to: "Track your supply?" — 30 / 60 / 90 / 120 chips.
31.	"All Set!" Rive checkmark. Sheet auto-dismisses after 1s.
💡 One sheet. Animated transitions. Not multiple sheets.

6.9 — Manual Entry & Not Found
•	Manual: bottom sheet, text field, search. Triggers same SQLite lookup + B0 + result flow.
•	Not found in SQLite: try Supabase search. Still not found: "Product Not Found" sheet.
•	"Submit Product" form writes to Supabase pending_products table.

6.10 — Payload Reference (Detail Blob)
The detail blob {dsld_id}.json maps to the 5 cards as follows. If a key is absent or null, hide that UI element — never render empty rows.
// Fetch from Supabase, cache in product_detail_cache SQLite table.
// blob_version field — compare to local to decide re-fetch.
{
  "dsld_id": string,
  "blob_version": number,

  // Card 1
  "ingredients": [{ name, standardName, standard_name, bio_score,
                     form, dosage, dosage_unit, notes, is_harmful,
                     is_banned, is_allergen, safety_hits }],
  "section_breakdown": {
    "ingredient_quality": { "score", "max", "sub": { "probiotic_breakdown": {} } },
    "safety_purity": { "score", "max" },    // max 30
    "evidence_research": { "score", "max", "matched_entries" }, // max 20
    "brand_trust": { "score", "max" },       // max 5
    "violation_penalty": number
  },

  // Card 2
  "inactive_ingredients": [{
    name: string,
    category: string,
    is_additive: bool,
    is_harmful: bool,
    reference_notes: string?,     // NOTE: field is "reference_notes" not "notes" — from harmful_additives.json
    mechanism: string?,           // mechanism_of_harm from reference data (why it's harmful)
    population_warnings: string?,
    common_uses: string?
  }],
  "compliance_detail": { "batch_traceability": bool },
  "certification_detail": {},
  "proprietary_blend_detail": { "present": bool },

  // Card 3
  "evidence_data": { "clinical_matches": [{study_type, description}] },
  "rda_ul_data": { ... },

  // Card 4
  "manufacturer_detail": { "trusted": bool, "third_party": bool, "region": string },

  // Condition + medication flagging (Section 6.5.4)
  "interaction_summary": {
    "condition_summary": {
      "[condition_id]": {          // e.g. "pregnancy", "diabetes", "hypertension"
        "highest_severity": string, // "contraindicated" | "avoid" | "caution" | "monitor"
        "count": number,
        "ingredients": string[],   // ingredient names that triggered
        "actions": string[]        // actionable guidance per ingredient
      }
    },
    "drug_class_summary": {
      "[drug_class_id]": {         // e.g. "anticoagulants", "hypoglycemics"
        "highest_severity": string,
        "count": number,
        "ingredients": string[],
        "actions": string[]
      }
    }
  },

  // Score explainability (Pros / Considerations sections)
  "score_bonuses": [{
    label: string,              // e.g. "Synergy Bonus: Calcium + Vitamin D"
    score: number,              // point value (e.g. 2.0)
    type: string,               // "synergy" | "absorption_enhancer" | "probiotic" | "delivery" | "certification"
    source: string              // reference or mechanism description
  }],
  "score_penalties": [{
    label: string,              // e.g. "Harmful Additive: Titanium Dioxide"
    score: number,              // negative magnitude (e.g. -2.0)
    ingredient: string,         // ingredient name that triggered
    severity: string,           // "critical" | "high" | "moderate" | "low"
    reason: string,             // why it's penalized
    category: string,           // "harmful_additive" | "proprietary_blend" | "allergen" | "watchlist"
    mechanism: string?          // mechanism_of_harm if available
  }],

  // Warnings (polymorphic)
  "warnings": [
    // type: banned_substance | recalled_ingredient | high_risk_ingredient |
    //        watchlist_substance | harmful_additive | allergen |
    //        interaction | drug_interaction | dietary | status
  ]
}
 
Section 7 — AI Pharmacist Tab

7.1 — Proactive Empty State
Design
AI icon (sparkle, brand color 40dp) centered.
Title: "How can I help you today?" Inter Bold 22sp.
Disclaimer (always visible): "Educational info only — not medical advice." 12sp grey italic.

Three large prompt buttons (stacked, 16dp gap, full-width, 56dp, card style):
  No stack data: static prompts:
    "Guide to supplement timing"
    "Tips for better energy"
    "Understanding interaction risks"

  Stack data exists: dynamic stack-aware prompts (read from user_stacks):
    e.g. "Analyze my Magnesium timing"
    e.g. "Is my Omega-3 safe with NSAIDs?"

Tapping a button starts chat with that prompt pre-filled and sent.

7.2 — Active Chat Interface
Disclaimer	Pinned above first message. Always visible.
User bubbles	Right-aligned. Brand color BG. White text. Radius 16dp flat bottom-right.
AI bubbles	Left-aligned. #F3F4F6 BG. Dark text. Radius 16dp flat bottom-left.
Typing indicator	Three-dot animation. Show immediately while awaiting response.
Input	Rounded input, grey BG, send icon (brand color, active only when text present).

7.3 — Quick Prompt Chips
•	Horizontal scroll row above keyboard.
•	Context-aware from user_stacks. Generic if no stack.
•	Tap sends immediately — no confirm step.

7.4 — AI Message Limit
5 messages/day for free users
Track in Supabase user_usage.ai_messages_today.
When limit hit: replace input with banner.
Banner: "You've used your 5 free messages today." CTA: "Explore Pro."
Previous messages remain readable.

7.5 — Offline State
•	If offline: replace input area with grey banner: "Offline — AI chat requires internet."
•	Previous chat history (from local Hive chat_history box) remains viewable.

7.6 — AI Integration
Gemini 2.5 Flash-Lite — Supabase Edge Function Proxy
Model: gemini-2.5-flash-lite.
NOTE: Google AI free tier limits change frequently. Verify current limits at https://ai.google.dev/pricing before launch. As of March 2026: ~1,000 RPD / 15 RPM on free tier. If using paid API via Supabase Edge Function, limits depend on your billing plan.
Proxy is a Supabase Edge Function. API key server-side only. Never in app binary.
Proxy receives: { messages: [...], system_prompt: string }.
Upgrade path: route complex queries to Pro later via model routing layer.

7.7 — System Prompt Builder
String buildSystemPrompt(HealthProfile? profile, List<StackItem> stack) {
  return """
You are an AI Pharmacist for PharmaGuide, a health technology app.
Provide educational information about supplements and medications.
You are NOT a licensed pharmacist. You CANNOT provide medical advice.
Always recommend consulting a healthcare provider for medical decisions.

User health context:
- Goals: ${profile?.goals ?? "not specified"}
- Conditions: ${profile?.conditions ?? "not specified"}
- Allergies: ${profile?.allergies ?? "not specified"}
- Current stack: ${stack.map((s) => s.name).join(", ")}

Keep responses under 150 words. Plain language. Never diagnose.
""";
}
 
Section 8 — My Stack Tab

8.1 — Stack Summary Card
Design
Same teal gradient as Home Hero.
70dp Rive score ring + grade label.
Headline: "[Low/Moderate/High] Interaction Risk".
Subtext: "X products  ·  X interactions found".
"View Alerts" button (white outlined): filters list to show only flagged items.

8.2 — My Stack / Wishlist Tabs
•	Two sub-tabs: "My Stack" (active) | "Wishlist".
•	Underline tab indicator, brand color. Inactive: grey text.
•	Wishlist: same card design — saved products not yet added to stack.

8.3 — Stack Item Card
Height	72dp
Left	48x48dp product image, radius 8dp. PDF image: placeholder.
Center	Product name Inter SemiBold 14sp. Below: "Xmg · AM/PM" grey 12sp.
Right	Score badge + risk icon if flagged.
NOT_SCORED	Show "Not Scored" badge instead of score.
Risk icon	Yellow warning if CAUTION/POOR. Red if UNSAFE.
Swipe right	Delete — red BG, trash icon. Snackbar undo.
Tap	Opens edit sheet: dosage, timing, supply count.

8.4 — Empty Stack State
•	Illustration: empty pillbox.
•	"Your stack is empty." + "Add supplements to track interactions."
•	CTA: "Scan a Product" navigates to Scan tab.
 
Section 9 — Profile Tab

9.1 — Privacy Header
Design
Shield/lock icon, brand color, 48dp, centered.
Headline: "Privacy-First Design." Inter Bold 22sp.
Subtext: "Your detailed health data is encrypted on your device. You control what gets synced."
(Accurate: health profile in local SQLite. Auth email is in Supabase — not contradicted by wording.)

9.2 — Auth State
State	Trigger	Design / Content	Dev Notes
Guest	No session	"Sign in to sync data and unlock more scans." + Sign In button.	Opens Auth bottom sheet.
Signed in	Session exists	Avatar (initials), name/email, "Sign Out" text btn.	Confirm sign-out via sheet.

9.3 — My Health Context
Each row opens a chip-selection bottom sheet. CRITICAL: chip values must map exactly to condition_id and drug_class_id values from the pipeline taxonomy (Flutter Data Contract v1, Section 8).

Condition Chips — condition_id mapping
Pregnancy	condition_id: pregnancy
Lactation/Breastfeeding	condition_id: lactation
Trying to Conceive	condition_id: ttc
Hypertension	condition_id: hypertension
Heart Disease	condition_id: heart_disease
Diabetes/Blood Sugar	condition_id: diabetes
High Cholesterol	condition_id: high_cholesterol
Liver Disease	condition_id: liver_disease
Kidney Disease	condition_id: kidney_disease
Thyroid Condition	condition_id: thyroid_disorder
Autoimmune	condition_id: autoimmune
Epilepsy/Seizures	condition_id: seizure_disorder
Bleeding Disorders	condition_id: bleeding_disorders
Upcoming Surgery	condition_id: surgery_scheduled

Medication Chips — drug_class_id mapping
Blood Thinners	drug_class_id: anticoagulants
Antiplatelet Agents	drug_class_id: antiplatelets
NSAIDs	drug_class_id: nsaids
Blood Pressure Meds	drug_class_id: antihypertensives
Diabetes Medications	drug_class_id: hypoglycemics
Thyroid Medications	drug_class_id: thyroid_medications
Sedatives / Sleep Aids	drug_class_id: sedatives
Immunosuppressants	drug_class_id: immunosuppressants
Statins / Cholesterol	drug_class_id: statins

⚠️  Pregnancy, TTC, and Lactation are THREE separate conditions with distinct clinical risks. Do not merge them. Users may select more than one.

9.4 — Health Goals
Goals map to user_goals_to_clusters.json in reference_data. Standard chips: Energy, Sleep, Immunity, Weight, Heart Health, Athletic Performance, Stress Relief.

9.5 — Settings
Notifications	Toggle. Uses flutter_local_notifications for daily med reminders.
Theme	Sheet: Light / Dark / System.
Help & Support	In-app WebView or mailto.
Privacy Policy	WebView.
App Version	Static. "PharmaGuide v1.0.0". Non-tappable, muted.
💡 Store all health context in local SQLite user_profile table. Never send to Supabase in MVP.
 
Section 10 — Data Layer & Scoring

10.1 — Local SQLite Tables
pharmaguide_core.db — ships with app (or first-launch download)
products_core     — ~180k products. Primary scan/search data. Instant offline.
products_fts      — Full-text search index (FTS5 with porter stemmer).
reference_data    — rda_optimal_uls (~199KB), interaction_rules (~95KB, 45 rules),
                    clinical_risk_taxonomy (~8KB, 14 conditions + 9 drug classes),
                    user_goals_clusters (~11KB).
                    Total ~313KB. Parse ALL at app startup. Hold in memory. Do not re-parse per view.
export_manifest   — db_version, pipeline_version, generated_at, checksum.

App-side tables (added locally, never in pipeline export):
product_detail_cache — dsld_id PK, detail_json TEXT, cached_at, source, detail_version.
user_profile          — goals, conditions, drug_classes, allergies, age, sex.
user_favorites        — dsld_id, added_at.
user_scan_history     — dsld_id, scanned_at.
user_stacks           — dsld_id, dosage, timing, supply_count, added_at.

10.2 — SQLite Queries
Barcode Lookup
-- Primary UPC lookup
SELECT * FROM products_core
WHERE upc_sku = ?
ORDER BY
  CASE product_status WHEN 'active' THEN 0 ELSE 1 END,
  score_quality_80 DESC,
  dsld_id
LIMIT 1;

-- If COUNT(*) > 1 for UPC: apply above ordering but show chooser UI if top 2 scores are close.

-- FTS fallback (product name search)
SELECT p.* FROM products_core p
JOIN products_fts f ON p.rowid = f.rowid
WHERE products_fts MATCH ?;

Filter Queries
-- High-scored vegan products
SELECT * FROM products_core
WHERE is_vegan = 1 AND score_quality_80 > 56  -- 56/80 = 70/100
ORDER BY score_quality_80 DESC;

-- Gluten-free multivitamins
SELECT * FROM products_core
WHERE is_gluten_free = 1 AND supplement_type = 'multivitamin';

-- Products with allergen risks
SELECT * FROM products_core WHERE has_allergen_risks = 1;

10.3 — Detail Blob Loading Flow
32.	Show product header instantly from products_core (SQLite).
33.	Check product_detail_cache for dsld_id.
34.	If cached: parse detail_json, check blob_version vs cached detail_version. If version mismatch, re-fetch.
35.	If not cached + online: fetch {dsld_id}.json from Supabase -> save to product_detail_cache -> render.
36.	If not cached + offline: show header only. "Detail unavailable offline" banner.
💡 Show shimmer skeleton for accordion cards while detail loads. Never block the hero section.

10.4 — DB Version Update Flow
37.	App launches. Read export_manifest from local SQLite.
38.	If online: check Supabase for current db_version + checksum.
39.	If newer version available: download in background. Never block the user.
40.	Apply new DB when download complete. Continue with current DB if update fails.

10.5 — ScoreFitCalculator (on-device personalization)
Replaces ScorePersonalizer from prior spec versions. Formally aligned to pipeline FitScoreResult.
Location: lib/services/score_fit_calculator.dart

Inputs:
  - double score_quality_80 (from products_core)
  - Map<String, dynamic> breakdown (from detail blob)
  - HealthProfile? localProfile (from SQLite user_profile)
  - reference_data (already parsed in memory at startup)

Output: FitScoreResult {
  double scoreFit20         // 0-20
  double scoreCombined100   // (score_quality_80 + scoreFit20) * 100/100
  double maxPossible        // depends on which profile fields are filled
  double dosageAppropriate  // E1: 0-7 (from rda_optimal_uls reference)
  double goalMatch          // E2a: 0-2
  double ageAppropriate     // E2b: 0-3
  double medicalCompat      // E2c: 0-8 (from interaction_rules reference)
  List<String> missingFields // ["age", "conditions"] — show profile completion CTA
  String displayText        // "85/96 (88.5%) - Complete profile for full scoring"
  List<ScoreChip> chips     // UI chips for Card 5
}
// Call after SQLite product fetch + detail blob hydration:
final healthProfile = ref.read(healthProfileProvider); // reads from SQLite user_profile
final refData = ref.read(referenceDataProvider);       // pre-parsed at startup
final fitResult = ScoreFitCalculator.calculate(
  scoreQuality80: product.scoreQuality80,
  breakdown: detailBlob.sectionBreakdown,
  profile: healthProfile,
  referenceData: refData,
);
// fitResult.scoreCombined100 -> display score (if profile exists)
// fitResult.chips            -> Card 5 chip list
// fitResult.missingFields    -> profile completion CTA
⚠️  score_fit_20 and score_combined_100 are NEVER stored in the DB or pipeline output. Always computed fresh from current profile state.

10.6 — Implementation Notes (from Flutter Data Contract v1)
Mixed naming in ingredient JSON — use @JsonKey
// The detail blob uses BOTH camelCase and snake_case on the same ingredient.
// This is intentional — they come from different pipeline stages.
// DO NOT normalize. Use explicit @JsonKey annotations:
@JsonKey(name: 'standardName')
final String standardName;      // label-parsed (camelCase)

@JsonKey(name: 'standard_name')
final String standardNameIqm;   // IQM-resolved (snake_case)

Warnings are polymorphic — use sealed class
sealed class Warning {
  String get type;
  String get severity;
  String get title;
  String get detail;
  String get source;
}

class BannedSubstanceWarning extends Warning { String? date; String? clinicalRisk; }
class HarmfulAdditiveWarning extends Warning  { String? mechanismOfHarm; List<String>? populationWarnings; }
class AllergenWarning extends Warning          { String? supplementContext; String? prevalence; }
class InteractionWarning extends Warning       { String? action; String? evidenceLevel; List<String>? sources; Map<String, dynamic>? doseThresholdEvaluation; }
class DrugInteractionWarning extends Warning   { String? action; String? evidenceLevel; List<String>? sources; Map<String, dynamic>? doseThresholdEvaluation; }
class DietaryWarning extends Warning           { }
class StatusWarning extends Warning            { }

score_quality_80 can be NULL
•	Products with verdict = NOT_SCORED have score_quality_80 = NULL, grade = NULL.
•	Every score display path needs a null guard.
•	Show "Not Scored" or equivalent. NEVER show 0.

diabetes_friendly / hypertension_friendly default false
•	When dietary sensitivity data is absent, these default to 0 (false) — cautious/safe default.
•	false does NOT mean "confirmed not friendly" — it means "insufficient data."
•	UI should distinguish between "not friendly" (explicit data) and "unknown" (data absent).
•	Check whether dietary_sensitivity_detail is populated in detail blob before showing a hard "not friendly" label.
 
Section 11 — Error States & Edge Cases

Scanner Error States
State	Trigger	Design / Content	Dev Notes
Slow detail load	Detail fetch > 3s	Shimmer skeleton on accordion cards. Hero shows from SQLite immediately.	shimmer package.
Fetch timeout	No response > 8s	Dismiss shimmer. Toast: "Unable to fetch product details." Show header only.	—
Damaged barcode	Partial scan	Camera continues. No feedback until clean read.	mobile_scanner handles.
Not in SQLite	No UPC match	Try Supabase product search. If still not found: "Product Not Found" sheet.	—
Supabase fetch fails	Network error	Toast: "Unable to fetch product details." Show header from SQLite. Score from products_core still displays.	—
NOT_SCORED	verdict = NOT_SCORED	Show "Not Scored" badge. No ring animation. Accordion cards shimmer-hidden.	Never show 0.
PDF image	image_url ends .pdf	Show placeholder illustration. Do not attempt to render PDF as image.	—
UPC collision	COUNT(*) > 1	Use deterministic ordering. If top results are very different products, show a simple chooser sheet.	—

Auth Error States
State	Trigger	Design / Content	Dev Notes
Sign-in failed	OAuth error	Toast: "Sign-in failed. Please try again."	—
Session expired	Supabase 401	Silently refresh token. If fails: sign out + show sign-in sheet.	Handle in auth listener.
Email exists	Duplicate	Toast: "An account with this email already exists. Try signing in."	—

General Rules
•	NEVER show raw error codes or stack traces to users.
•	Minor errors: Toast (auto-dismiss). Actionable errors: Bottom Sheet.
•	Log errors to Supabase error_logs table: user_id, error_code, timestamp.
 
Section 12 — Build Checklist

Implementation Notes Before Starting

Why drift over raw sqflite:
  drift generates typed Dart classes from SQL schemas. This catches contract drift (wrong column name,
  wrong type) at COMPILE TIME instead of runtime. Given this is medical safety data, the extra type
  safety is worth the 1-day setup cost. drift also gives you reactive queries (Stream<List<Product>>)
  which pairs perfectly with Riverpod's AsyncValue pattern.

Sample detail blob for development:
  Request a real exported detail blob JSON (e.g. Thorne Basic Nutrients dsld_id=182215) from the
  data team before starting Phase 2. Having a real blob file lets you build and test all 5 accordion
  cards against actual data shapes. Do NOT build card UI against made-up test data — the field names,
  nesting, and null patterns will differ.

MVP scope boundaries:
  IN SCOPE: Scan, 5-pillar result cards, stack management, AI chat, profile with condition/medication
  chips, condition alert banner, wishlist (add/remove only).
  POST-MVP (do not build now): Full Analysis deep-dive report, wishlist compatibility checks
  (interaction analysis between wishlist items and current stack), genetic insights, trend analysis,
  "What If" scenario engine, premium paywall/subscription.

Phase 1 — Foundation (Week 1–2)
•	Flutter project: Inter font, theme.dart (ALL colors, styles, shadows — single source of truth).
•	SQLite setup: drift (recommended). pharmaguide_core.db bundled or first-launch download.
•	App-side SQLite tables: product_detail_cache, user_profile, user_scan_history, user_stacks, user_favorites.
•	Hive setup: guest_scan_count box (freemium), chat_history box.
•	Supabase client: Auth providers (Google, Apple, Email, Anon).
•	Riverpod 2.0+ with @riverpod generator. All providers established.
•	Parse ALL reference_data JSON at app startup. Hold in memory via singleton provider.
•	ScoreFitCalculator written and unit-tested before UI work.
•	Floating tab bar built. All 5 tabs scaffold.
•	Reusable widget library: PrimaryButton, OutlineButton, AppCard, ScoreRing (Rive), ScoreBadge, ShimmerCard.

Phase 2 — Core Scan Loop (Week 2–4)
💡 Budget 2 full weeks. Clinical breakdown UI is substantial.
•	Scan tab: camera, permission handling, Rive bracket (3 states).
•	Barcode -> SQLite lookup. Handle UPC collisions. Handle NOT_SCORED.
•	B0 Gate: if verdict = BLOCKED/UNSAFE, render Critical Warning screen (Section 6.4).
•	ScoreFitCalculator.calculate() called after SQLite fetch + detail hydration.
•	Hero section: Rive score ring. Sticky. Handles NOT_SCORED, PDF image_url, percentile chip.
•	Verdict banner: maps verdict to SAFE/CAUTION/POOR/UNSAFE/NOT_SCORED colors.
•	Condition Alert Banner: interaction_summary intersection with user conditions (Section 6.5.4).
•	5 accordion cards as reusable ScoringCard widget (AnimatedSize expand/collapse).
•	Card 1: ingredient list, premium form badges, delivery tier, probiotic badge.
•	Card 2: cert badges (show only TRUE), proprietary blend warning, harmful additives, allergens.
•	Card 3: sub-clinical dose warning, interaction warnings (sealed class polymorphic), study badges.
•	Card 4: boolean rows, manufacturer violation red override, product status warning.
•	Card 5: locked state (no profile) vs dynamic chips from ScoreFitCalculator.chips.
•	Add to Stack flow: single sheet, animated transitions.
•	Scan limit enforcement: Hive (guest), Supabase (free user). Both enforced.

Phase 3 — Stack & Home (Week 4–5)
•	Stack tab: summary card, smart item cards, swipe-to-delete, edit sheet.
•	Home tab: header, search (SQLite FTS), hero card both states, carousel (PDF placeholder handling), AI insight.
•	Offline detection (connectivity_plus). Banners per tab. SQLite always available offline.
•	DB version check on launch. Background update if newer pipeline export available.

Phase 4 — AI Chat & Profile (Week 5–6)
•	Gemini proxy Edge Function deployed (Supabase).
•	AI chat: proactive empty state (static + dynamic stack-aware prompts).
•	Active chat interface, typing indicator, quick chips.
•	System prompt builder reads SQLite user_profile + Riverpod stack provider.
•	AI message limit (5/day) via Supabase user_usage.
•	Profile tab: privacy header, condition/medication/goal chips (exact condition_id mapping).
•	Auth section: guest CTA vs signed-in display.

Phase 5 — Polish & Edge Cases (Week 6–7)
•	All error states: Section 11. No raw errors ever shown to users.
•	Shimmer skeletons on all loading states (detail cards, carousel, stack list).
•	Haptic feedback audit: all key interactions.
•	Performance audit: no jank on tab switch, sheet open, score animation.
•	Dark mode: theme.dart already supports via ThemeMode.system.
•	TestFlight / Play Console internal track submission.

Hard Rules — Do Not Violate
1. theme.dart is the ONLY place colors, text styles, and shadows are defined.
2. Server-side scan limits are non-negotiable. Supabase RLS enforces for signed-in users.
3. No Edge Function for scoring. ScoreFitCalculator is Dart, local, instant.
4. The Gemini proxy Edge Function IS required. API key never in app binary.
5. score_quality_80 can be NULL. Every display path must null-guard. Never show 0.
6. Condition chip values MUST match pipeline condition_id/drug_class_id exactly. Any mismatch breaks interaction flagging.
7. Parse reference_data JSON ONCE at startup. Never re-parse on every product view.
8. Products with NOT_SCORED verdict: show "Not Scored". Never a score ring.
9. image_url may be a PDF link. Always check before rendering as image.
10. Health profile (user_profile SQLite) never syncs to Supabase in MVP.
💡 Pipeline seed data requirement: products_core must have at least 100 products with fully populated breakdown JSON before Phase 2 scan testing can begin. Coordinate with data team.
