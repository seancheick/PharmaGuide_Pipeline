# PharmaGuide Master Roadmap — Pipeline to Production

**Version:** 2.0.0 (Updated with v1.3.0 Export Schema Enhancements)
**Date:** 2026-04-07
**Status:** ✅ COMPLETE Pipeline + 🔨 Ready for Flutter Implementation
**Owner:** Sean Cheick

---

## 📊 Executive Summary

This is the **single source of truth** for PharmaGuide development from data pipeline to production mobile app. The project consists of two major components:

1. **Python Pipeline** (Clean → Enrich → Score → Export) — ✅ COMPLETE
2. **Flutter Mobile App** (Offline-first, clinical-grade scoring) — 🔨 READY TO BUILD

**Target Timeline:** 8-10 weeks from Flutter kickoff to TestFlight beta.

---

## 🎯 Current State (2026-04-07)

### ✅ Phase 0: Pipeline Infrastructure (COMPLETE)

| Component              | Status         | Version       | Details                                                     |
| ---------------------- | -------------- | ------------- | ----------------------------------------------------------- |
| **Data Pipeline**      | ✅ COMPLETE    | v3.1.0        | 3-stage processing (Clean → Enrich → Score)                 |
| **Test Suite**         | ✅ PASSING     | 3065+ tests   | 81 test files, 100% critical path coverage                  |
| **Data Quality**       | ✅ VALIDATED   | Schema v5.1.0 | 563 IQM parents, 143 banned/recalled, 115 harmful additives |
| **Export Schema**      | ✅ FROZEN      | **v1.3.0**    | **87 columns (up from 65), 22 new optimization fields**     |
| **Supabase Setup**     | ✅ LIVE        | Schema v2.0.0 | Storage bucket configured, RLS policies active              |
| **Sync Script**        | ✅ OPERATIONAL | -             | `sync_to_supabase.py` tested and working                    |
| **Profile Validation** | ✅ COMPLETE    | -             | All 7 profile fields validated against schemas              |

### 🚀 Export Schema v1.3.0 Enhancements (NEW — 2026-04-07)

**Added 22 new columns to optimize Flutter performance:**

1. **Stack Interaction (5 cols):** `ingredient_fingerprint`, `key_nutrients_summary`, `contains_stimulants/sedatives/blood_thinners`
2. **Social Sharing (4 cols):** `share_title`, `share_description`, `share_highlights`, `share_og_image_url`
3. **Search & Filter (8 cols):** `primary_category`, `secondary_categories`, 5× `contains_*` flags, `key_ingredient_tags`
4. **Goal Matching (2 cols):** `goal_matches`, `goal_match_confidence`
5. **Dosing Guidance (2 cols):** `dosing_summary`, `servings_per_container`
6. **Allergen Summary (1 col):** `allergen_summary`

**Performance Impact:**

- **Stack safety check:** 20-50x faster (no network calls, uses `ingredient_fingerprint`)
- **Social sharing:** 50x faster (instant metadata from `share_*` fields)
- **Category filtering:** 20-40x faster (indexed `contains_*` flags)
- **Overall:** ~80% reduction in detail blob fetches for common UI actions

**Documentation:**

- `scripts/EXPORT_SCHEMA_V1.3.0_CHANGELOG.md` — Technical changelog
- `scripts/FLUTTER_V1.3.0_INTEGRATION_GUIDE.md` — Flutter code examples
- `scripts/FINAL_EXPORT_SCHEMA_V1.md` — Complete schema reference (v1.3.0)

### 🎯 Target State (8-10 Weeks from Flutter Start)

- **iOS TestFlight:** Production-ready app, 8-sprint roadmap complete
- **Android Beta:** Same codebase, Google Play internal track
- **Architecture:** Hybrid SQLite (local 105MB) + Supabase (detail blobs, auth, OTA updates)
- **Key Flows:** Profile setup → Barcode scan → FitScore → Stack management → Social sharing
- **Performance:** <100ms stack checking, <10ms social share, instant category filtering

---

## 🏗️ PART 1: PIPELINE ARCHITECTURE (COMPLETE ✅)

### Pipeline Overview

PharmaGuide's data pipeline is a **3-stage ETL system** that processes raw NIH DSLD data into evidence-based quality scores:

```
┌─────────────────────────────────────────────────────────────┐
│  STAGE 1: CLEAN (clean_dsld_data.py)                        │
├─────────────────────────────────────────────────────────────┤
│  • Input: Raw DSLD JSON (~180K products)                    │
│  • Output: Normalized JSON (standardized fields)            │
│  • Functions: Text normalization, deduplication, validation │
└─────────────────────────────────────────────────────────────┘
                          ↓
┌─────────────────────────────────────────────────────────────┐
│  STAGE 2: ENRICH (enrich_supplements_v3.py)                 │
├─────────────────────────────────────────────────────────────┤
│  • Input: Cleaned JSON                                      │
│  • Output: Enriched JSON (matched, classified, verified)    │
│  • Functions: Ingredient matching (563 IQM parents),        │
│              Clinical evidence matching (197 studies),       │
│              Synergy cluster detection (54 clusters),        │
│              Interaction rule evaluation (45 rules),         │
│              Allergen flagging (17 allergens),               │
│              Harmful additive detection (115 substances)     │
│  • Databases: 34 reference JSON files (schema v5.1.0)       │
└─────────────────────────────────────────────────────────────┘
                          ↓
┌─────────────────────────────────────────────────────────────┐
│  STAGE 3: SCORE (score_supplements.py)                      │
├─────────────────────────────────────────────────────────────┤
│  • Input: Enriched JSON                                     │
│  • Output: Scored JSON (80-point quality score)             │
│  • Sections:                                                │
│    - A: Ingredient Quality (max 25 pts)                     │
│    - B: Safety & Purity (max 30 pts)                        │
│    - C: Clinical Evidence (max 20 pts)                      │
│    - D: Brand Trust (max 5 pts)                             │
│  • Verdict: BLOCKED > UNSAFE > MODERATE > REVIEW >          │
│             RECOMMENDED (deterministic precedence)           │
└─────────────────────────────────────────────────────────────┘
                          ↓
┌─────────────────────────────────────────────────────────────┐
│  STAGE 4: EXPORT (build_final_db.py) — v1.3.0               │
├─────────────────────────────────────────────────────────────┤
│  • Input: Scored JSON                                       │
│  • Output:                                                  │
│    1. pharmaguide_core.db (SQLite, 87 columns, 105MB)      │
│    2. detail_blobs/{dsld_id}.json (per-product details)    │
│    3. export_manifest.json (version metadata)              │
│  • NEW v1.3.0: 22 optimization columns for Flutter         │
│    (ingredient_fingerprint, share_metadata, etc.)          │
└─────────────────────────────────────────────────────────────┘
                          ↓
┌─────────────────────────────────────────────────────────────┐
│  STAGE 5: SYNC (sync_to_supabase.py)                        │
├─────────────────────────────────────────────────────────────┤
│  • Upload pharmaguide_core.db to Supabase Storage           │
│  • Upload detail blobs to Supabase Storage                  │
│  • Update export_manifest table                             │
│  • OTA updates: Flutter app checks manifest for new DB      │
└─────────────────────────────────────────────────────────────┘
```

### Key Pipeline Stats (Production Data)

- **Total Products:** ~180,000 dietary supplements
- **Ingredient Quality Map:** 563 IQM parent ingredients
- **Banned/Recalled:** 143 ingredients (FDA-tracked)
- **Harmful Additives:** 115 substances with penalty scoring
- **Clinical Studies:** 197 evidence-backed ingredients (all PMID-linked)
- **Synergy Clusters:** 54 validated combinations
- **Interaction Rules:** 45 rules (14 conditions × 9 drug classes)
- **Allergens:** 17 regulatory allergens (FDA FALCPA + EU Annex II)
- **Test Coverage:** 3065+ tests across 81 test files

### Reference Data Files (34 total, schema v5.1.0)

| File                               | Size                    | Purpose                                               |
| ---------------------------------- | ----------------------- | ----------------------------------------------------- |
| `ingredient_quality_map.json`      | Largest                 | Quality scoring for 563 IQM parents                   |
| `banned_recalled_ingredients.json` | 143 entries             | Regulatory safety disqualifications                   |
| `harmful_additives.json`           | 115 entries             | Penalty scoring for harmful additives                 |
| `backed_clinical_studies.json`     | 197 entries             | Clinical evidence bonus points (PMID-backed)          |
| `allergens.json`                   | 17 entries              | Allergen classification (Big 8 + supplement-specific) |
| `rda_optimal_uls.json`             | 47 nutrients            | Dosing adequacy benchmarks (age/sex-specific)         |
| `user_goals_to_clusters.json`      | 18 goals                | Goal-to-cluster mappings for E2a scoring              |
| `clinical_risk_taxonomy.json`      | 14 conditions + 9 drugs | Interaction taxonomy for E2c scoring                  |
| `synergy_cluster.json`             | 54 clusters             | Ingredient synergy bonuses                            |
| `manufacturer_violations.json`     | 67 brands               | Brand trust penalties                                 |
| + 24 more reference files          | -                       | See `scripts/DATABASE_SCHEMA.md`                      |

### Scoring System (v3.2.0)

**80-Point Quality Score (Sections A-D):**

- **A: Ingredient Quality (max 25):** Bioavailability, premium forms, delivery, absorption
- **B: Safety & Purity (max 30):** Banned/recalled gate, contaminants, allergens, dose safety
- **C: Clinical Evidence (max 20):** PMID-backed studies, evidence strength
- **D: Brand Trust (max 5):** Manufacturer reputation, certifications

**20-Point FitScore (Section E — Computed on-device in Flutter):**

- **E1: Dosage Appropriateness (max 7):** Age/sex-specific RDA/UL validation
- **E2a: Goal Alignment (max 2):** Match synergy clusters to user goals
- **E2b: Age Appropriateness (max 3):** Nutrient dosing vs age group
- **E2c: Medical Compatibility (max 8):** Condition/drug interaction checking

**Final Score:** `(A+B+C+D+E) × 100 / 100 = 0-100 scale`

**Verdicts:** BLOCKED (banned/recalled) > UNSAFE (harmful) > MODERATE (caution) > REVIEW (missing data) > RECOMMENDED (safe + effective)

**Configuration:** `scripts/config/scoring_config.json` (100+ tunable parameters)

---

## 🚀 PART 2: FLUTTER APP DEVELOPMENT (8 SPRINTS, 16 WEEKS)

### Architecture Decision Record

**Selected:** **Approach A — SQLite-Core + Supabase-Detail (Hybrid)**

| Component                           | Storage                                                 | Update Pattern                                | Rationale                                                         |
| ----------------------------------- | ------------------------------------------------------- | --------------------------------------------- | ----------------------------------------------------------------- |
| **Core DB** (`pharmaguide_core.db`) | Bundled with app + OTA background download              | Weekly full-file replacement                  | 90MB, 180K products, instant offline access                       |
| **Detail Blobs**                    | Supabase Storage (hashed, shared paths)                 | On-demand fetch + local cache                 | ~40KB per product, LRU cache in `user_data.db`                    |
| **User Profile**                    | Local SQLite (`user_data.db`)                           | Never synced to cloud (MVP)                   | Privacy-first, instant access, no PHI in cloud                    |
| **User Stack**                      | Local SQLite (source of truth) + Supabase (sync target) | Write-first local, async sync with tombstones | Offline editing, last-write-wins conflict resolution              |
| **Auth & Usage**                    | Supabase (RLS + RPC)                                    | Real-time via `increment_usage` RPC           | 20 scans/5 AI messages per day (signed-in), 10 scans/3 AI (guest) |

**Why not Approach B (Full PostgreSQL)?**

- No server-side search needed (FTS5 local is instant)
- No real-time subscriptions required (weekly data updates)
- Offline-first is non-negotiable for health/supplement scanning

**Why not Approach C (Edge Functions + Deltas)?**

- Over-engineering for 180K products
- Binary diff complexity not worth it for weekly updates
- Full-file replacement is simple, testable, and atomic

---

## Critical Path Dependencies

```
MILESTONE 0: Pre-Flutter Infrastructure (Complete ✅)
├── Pipeline data quality audit ✅
├── Export schema upgraded to v1.3.0 ✅ (22 new optimization columns)
├── Profile setup validated against schemas ✅ (7 fields, exact ID mappings)
├── Supabase schema deployed (v2.0.0) ✅
├── sync_to_supabase.py operational ✅
└── Documentation complete ✅ (v1.3.0 changelog, Flutter integration guide)

SPRINT 0: Profile Setup & Foundation (Week 1-2) 🔨
├── Requires: Supabase project URL + anon key
├── Blocks: All subsequent sprints
└── Deliverable: Profile setup complete, app opens, 5 tabs navigate, SQLite loads

SPRINT 1: Database & Services (Week 3-4) 🔨
├── Requires: Sprint 0 complete + pharmaguide_core.db bundled
├── Blocks: Search, scan, stack (all need DB access)
└── Deliverable: SQLite + Supabase integration, reference data bundled, core services

SPRINT 2: Product Catalog & Search (Week 5-6) 🔨
├── Requires: Sprint 1 complete + real product data loaded
├── Blocks: Scan (needs search), stack (needs product cards)
└── Deliverable: Search, category filters (v1.3.0 optimized), product cards with goal badges

SPRINT 3: Product Detail & FitScore (Week 7-8) 🔨
├── Requires: Sprint 2 complete + detail blobs in Supabase
├── Blocks: Stack (needs detail view), social sharing
└── Deliverable: Full detail screen, FitScore engine (E1-E2c), interaction warnings

SPRINT 4: FitScore Engine (Week 9-10) 🔨
├── Requires: Sprint 3 complete + profile data exists
├── Blocks: Stack (needs personalized scores)
└── Deliverable: E1, E2a, E2b, E2c calculators, combined FitScore

SPRINT 5: Stack Management & Interaction Checking (Week 11-12) 🔨
├── Requires: Sprint 4 complete + FitScore working
├── Blocks: Social sharing (needs stack context)
└── Deliverable: Stack CRUD, multi-product safety check (v1.3.0 fingerprints), stack health score

SPRINT 6: Social Sharing (Week 13) 🔨
├── Requires: Sprint 5 complete
├── Blocks: None
└── Deliverable: Share button, Instagram templates (v1.3.0 metadata), deep links

SPRINT 7: Settings & Profile Management (Week 14) 🔨
├── Requires: Sprint 6 complete
├── Blocks: None
└── Deliverable: Edit profile, privacy settings, data export, re-compute FitScores

SPRINT 8: Polish & TestFlight (Week 15-16) 🔨
├── Requires: Sprint 7 complete + all flows working
├── Blocks: Public launch
└── Deliverable: Production-ready, TestFlight submitted, internal beta
└── Deliverable: Analytics, crash reporting, performance optimization
```

---

## Phase Breakdown

### **Phase 0: Infrastructure Validation (Week 0 — PRE-FLIGHT)**

**Status:** ✅ **COMPLETE**  
**Goal:** Verify all data contracts, test sync script, validate Supabase connectivity

#### Checklist:

- [x] Run `python3 -m pytest scripts/tests/` — 3065+ tests pass
- [x] Run `python3 scripts/build_all_final_dbs.py` — generates `pharmaguide_core.db`
- [x] Run `python3 scripts/db_integrity_sanity_check.py` — schema v5.0/5.1 valid
- [x] Run `python3 scripts/sync_to_supabase.py <build_output_dir> --dry-run` — preview upload
- [x] Run `python3 scripts/sync_to_supabase.py <build_output_dir>` — full sync to Supabase
- [x] Verify Supabase Storage: `pharmaguide_core.db` + detail blobs accessible via public URL
- [x] Query `export_manifest` table: `SELECT * FROM export_manifest WHERE is_current = true;`
- [x] Download test detail blob: `curl https://omayamxacvacrnvdvzhr.supabase.co/storage/v1/object/public/pharmaguide/shared/details/sha256/{hash[0:2]}/{hash}.json`

#### Acceptance Criteria:

- Export manifest has valid `checksum`, `db_version`, `product_count`
- At least 1000 detail blobs uploaded to Storage
- `pharmaguide_core.db` downloadable and opens in SQLite browser
- All RLS policies active, `increment_usage` RPC callable

---

### **Phase 1: Flutter Foundation (Week 1-2)**

**Status:** 🔨 **NEXT UP**  
**Goal:** App opens, 5 tabs navigate, theme matches spec, SQLite data loads, Supabase connected

#### Sprint 1.1: Project Setup (Days 1-2)

**Deliverables:**

1. **Create Flutter project:**

   ```bash
   flutter create PharmaGuide_ai --org com.pharmaguide
   cd PharmaGuide_ai
   ```

2. **Configure `pubspec.yaml`** with dependencies (see Appendix A for full list):
   - Core: `flutter_riverpod ^2.5.0`, `drift ^2.18.0`, `supabase_flutter ^2.5.0`
   - UI: `google_fonts ^6.2.0`, `lucide_icons`, `shimmer ^3.0.0`
   - Utilities: `mobile_scanner ^5.0.0`, `hive_flutter ^1.1.0`, `go_router ^14.0.0`

3. **Create `CLAUDE.md`** (critical — this is your AI pair programmer's contract):

   ```markdown
   # PharmaGuide Flutter Development Guide

   ## Hard Rules (Non-Negotiable)

   1. `app_theme.dart` is the ONLY place for colors, text styles, shadows
   2. Use `drift` over raw `sqflite` — compile-time safety required
   3. Field name is `notes` NOT `reference_notes` (pipeline contract)
   4. Condition/drug_class chips MUST match exact taxonomy IDs (14 + 9)
   5. `score_quality_80` can be NULL — always null-guard
   6. Parse `reference_data` JSON ONCE at startup, never re-parse
   7. Image URLs may be PDFs — check before rendering
   8. Health profile NEVER syncs to cloud (MVP)
   9. NOT_SCORED products: show "Not Scored", no ring animation
   10. B0 safety gate is non-negotiable — block immediately

   ## Supabase Configuration

   - Project URL: `https://omayamxacvacrnvdvzhr.supabase.co`
   - Anon Key: [from .env — never commit]
   - RLS: `(SELECT auth.uid())` pattern for user-owned rows

   ## Data Contract

   - Schema: `scripts/FINAL_EXPORT_SCHEMA_V1.md`
   - Flutter Contract: `scripts/FLUTTER_DATA_CONTRACT_V1.md`
   - UX Spec: `scripts/PharmaGuide Flutter MVP Dev.md` (v5.3)

   ## Commands

   - Run tests: `flutter test`
   - Analyze: `flutter analyze`
   - Generate code: `flutter pub run build_runner build --delete-conflicting-outputs`
   ```

4. **Bundle `pharmaguide_core.db`:**
   - Copy from `scripts/final_db_output/pharmaguide_core.db` → `assets/db/`
   - Add to `pubspec.yaml`:
     ```yaml
     flutter:
       assets:
         - assets/db/pharmaguide_core.db
     ```

**Acceptance:**

- `flutter doctor` shows no critical issues
- `flutter run` on iOS simulator opens blank app
- CLAUDE.md readable by AI assistant

---

#### Sprint 1.2: Theme & Navigation (Days 3-4)

**Deliverables:**

1. **Create `lib/theme/app_theme.dart`** — SINGLE source of truth for ALL design tokens:

   ```dart
   class AppTheme {
     // Brand Colors (Light Mode)
     static const Color brandPrimary = Color(0xFF0A7D6F);  // Teal
     static const Color brandSecondary = Color(0xFF1A936F); // Sea Green

     // Score Colors (WCAG AA compliant — v5.3 audit applied)
     static const Color scoreExcellent = Color(0xFF047857); // 90-100
     static const Color scoreGood = Color(0xFF65A30D);      // 75-89
     static const Color scoreFair = Color(0xFFD97706);      // 60-74
     static const Color scorePoor = Color(0xFFDC2626);      // <60

     // Verdict Colors
     static const Color verdictSafe = Color(0xFF10B981);
     static const Color verdictCaution = Color(0xFFFBBF24);
     static const Color verdictUnsafe = Color(0xFFEF4444);
     static const Color verdictBlocked = Color(0xFF991B1B);

     // Text Styles (Inter font)
     static const TextStyle heading1 = TextStyle(
       fontFamily: 'Inter',
       fontSize: 28,
       fontWeight: FontWeight.w700,
       letterSpacing: -0.5,
     );

     // ... [see spec Section 2 for complete token list]
   }
   ```

2. **Create `lib/router/app_router.dart`** with GoRouter:

   ```dart
   final appRouter = GoRouter(
     initialLocation: '/home',
     routes: [
       ShellRoute(
         builder: (context, state, child) => FloatingTabBar(child: child),
         routes: [
           GoRoute(path: '/home', builder: (ctx, state) => HomeScreen()),
           GoRoute(path: '/scan', builder: (ctx, state) => ScanScreen()),
           GoRoute(path: '/stack', builder: (ctx, state) => StackScreen()),
           GoRoute(path: '/chat', builder: (ctx, state) => ChatScreen()),
           GoRoute(path: '/profile', builder: (ctx, state) => ProfileScreen()),
         ],
       ),
     ],
   );
   ```

3. **Build `lib/shared/widgets/floating_tab_bar.dart`:**
   - 5 tabs: Home, Scan, Stack, Chat, Profile
   - Scan button elevated (+8dp shadow, 56dp diameter)
   - Frosted glass effect (blur + 80% opacity white background)
   - Lucide icons for each tab
   - Labels on all tabs (accessibility + discoverability)

**Acceptance:**

- Tap 5 tabs, each shows placeholder screen
- Theme colors match spec exactly (use color picker to verify)
- Navigation preserves state on tab switch

---

#### Sprint 1.3: Database Setup (Days 5-7)

**Deliverables:**

1. **Create drift schema in `lib/data/local/drift/`:**

   **`reference_db.dart`** (read-only, bundled):

   ```dart
   @DriftDatabase(tables: [ProductsCore, ProductsFts, ReferenceData, ExportManifest])
   class ReferenceDatabase extends _$ReferenceDatabase {
     ReferenceDatabase() : super(_openConnection());

     @override
     int get schemaVersion => 1;
   }

   class ProductsCore extends Table {
     IntColumn get dsldId => integer().named('dsld_id')();
     TextColumn get upcSku => text().named('upc_sku').nullable()();
     TextColumn get productName => text().named('product_name')();
     TextColumn get brand => text()();
     RealColumn get scoreQuality80 => real().named('score_quality_80').nullable()();
     TextColumn get verdict => text()();
     // ... [see FINAL_EXPORT_SCHEMA_V1.md for all 61 columns]

     @override
     Set<Column> get primaryKey => {dsldId};
   }
   ```

   **`user_db.dart`** (read-write, created on first launch):

   ```dart
   @DriftDatabase(tables: [
     ProductDetailCache,
     UserProfile,
     UserScanHistory,
     UserStacksLocal,
     UserFavorites,
   ])
   class UserDatabase extends _$UserDatabase {
     UserDatabase() : super(_openConnection());

     @override
     int get schemaVersion => 1;
   }
   ```

2. **Generate code:**

   ```bash
   flutter pub run build_runner build --delete-conflicting-outputs
   ```

3. **Create `lib/data/local/db_asset_loader.dart`:**

   ```dart
   Future<void> loadBundledDb() async {
     final appDir = await getApplicationDocumentsDirectory();
     final dbPath = path.join(appDir.path, 'pharmaguide_core.db');

     // Copy bundled DB on first launch
     if (!File(dbPath).existsSync()) {
       final ByteData data = await rootBundle.load('assets/db/pharmaguide_core.db');
       await File(dbPath).writeAsBytes(data.buffer.asUint8List());
     }
   }
   ```

4. **Create reference data provider `lib/providers/reference_data_provider.dart`:**

   ```dart
   @riverpod
   Future<ReferenceDataCache> referenceData(ReferenceDataProviderRef ref) async {
     final db = ref.watch(referenceDatabaseProvider);
     final manifest = await db.select(db.exportManifest).getSingle();

     // Parse JSON tables from reference_data column
     final taxonomyJson = jsonDecode(manifest.clinicalRiskTaxonomy);
     final interactionRulesJson = jsonDecode(manifest.interactionRules);
     // ...

     return ReferenceDataCache(
       taxonomy: ClinicalRiskTaxonomy.fromJson(taxonomyJson),
       interactionRules: InteractionRules.fromJson(interactionRulesJson),
       // ...
     );
   }
   ```

**Acceptance:**

- Breakpoint in `main()` shows `pharmaguide_core.db` loaded with 180K rows
- Query `SELECT COUNT(*) FROM products_core` returns expected count
- `reference_data` JSON parses without errors
- drift code generation completes without warnings

---

#### Sprint 1.4: Supabase Integration (Days 8-10)

**Deliverables:**

1. **Create `lib/data/remote/supabase_service.dart`:**

   ```dart
   class SupabaseService {
     static final client = Supabase.instance.client;

     Future<void> initialize() async {
       await Supabase.initialize(
         url: 'https://omayamxacvacrnvdvzhr.supabase.co',
         anonKey: const String.fromEnvironment('SUPABASE_ANON_KEY'),
       );

       // Auto-create anon session on first launch
       if (client.auth.currentSession == null) {
         await client.auth.signInAnonymously();
       }
     }
   }
   ```

2. **Create auth state provider:**

   ```dart
   @riverpod
   Stream<AuthState> authState(AuthStateRef ref) {
     return Supabase.instance.client.auth.onAuthStateChange;
   }
   ```

3. **Test Supabase connectivity:**

   ```dart
   // In main()
   final manifest = await Supabase.instance.client
     .from('export_manifest')
     .select()
     .eq('is_current', true)
     .single();

   print('Connected to Supabase! DB version: ${manifest['db_version']}');
   ```

**Acceptance:**

- App launches and auto-signs in anonymously
- Console shows "Connected to Supabase! DB version: {version}"
- Auth state provider emits session change events

---

#### Sprint 1.5: Foundational Widgets & Tests (Days 11-14)

**Deliverables:**

1. **Create reusable widgets in `lib/shared/widgets/`:**
   - `primary_button.dart` — Brand color, 48dp height, loading state
   - `score_ring.dart` — Animated circular progress, color by score
   - `score_badge.dart` — Pill shape, verdict color, "SAFE"/"CAUTION"/etc
   - `shimmer_card.dart` — Loading skeleton
   - `app_bottom_sheet.dart` — Rounded corners, drag indicator

2. **Create `ScoreFitCalculator` in `lib/services/score_fit_calculator.dart`:**

   ```dart
   class ScoreFitCalculator {
     FitScoreResult calculate({
       required double? scoreQuality80,
       required SectionBreakdown breakdown,
       required HealthProfile? profile,
       required ReferenceDataCache referenceData,
     }) {
       if (profile == null) return FitScoreResult.locked();

       // E1: Dosage adequacy (0-7 pts)
       final e1 = _calculateDosageAdequacy(breakdown, profile);

       // E2a: Goal alignment (0-2 pts)
       final e2a = _calculateGoalAlignment(breakdown, profile, referenceData);

       // E2b: Age appropriateness (0-3 pts)
       final e2b = _calculateAgeAppropriate(breakdown, profile);

       // E2c: Medical interaction check (0-8 pts)
       final e2c = _calculateMedicalFit(breakdown, profile, referenceData);

       final scoreFit20 = e1 + e2a + e2b + e2c;
       final scoreCombined100 = ((scoreQuality80 ?? 0) + scoreFit20) * 1.25;

       return FitScoreResult(
         scoreFit20: scoreFit20,
         scoreCombined100: scoreCombined100.clamp(0, 100),
         chips: _generateChips(e1, e2a, e2b, e2c),
       );
     }
   }
   ```

3. **Write unit tests in `test/services/score_fit_calculator_test.dart`:**

   ```dart
   void main() {
     group('ScoreFitCalculator', () {
       test('returns locked state when no profile', () {
         final result = ScoreFitCalculator().calculate(
           scoreQuality80: 75.0,
           breakdown: mockBreakdown,
           profile: null,
           referenceData: mockReferenceData,
         );

         expect(result.isLocked, true);
         expect(result.scoreFit20, 0);
       });

       test('calculates fit score for pregnancy + omega-3', () {
         final profile = HealthProfile(
           conditions: ['pregnancy'],
           age: 28,
           goals: ['heart_health'],
         );

         final result = ScoreFitCalculator().calculate(
           scoreQuality80: 80.0,
           breakdown: omegaBreakdown,
           profile: profile,
           referenceData: mockReferenceData,
         );

         expect(result.scoreFit20, greaterThan(15)); // EPA/DHA bonus
         expect(result.chips, contains(contains('Omega-3')));
       });

       // Add 10+ test cases covering all sub-scores
     });
   }
   ```

4. **Create parser smoke tests in `test/data/parsers_test.dart`:**

   ```dart
   void main() {
     test('parses SAFE detail blob from fixture', () async {
       final json = await loadFixture('detail_blob_safe.json');
       final blob = DetailBlob.fromJson(jsonDecode(json));

       expect(blob.dsldId, isNotNull);
       expect(blob.ingredients, isNotEmpty);
       expect(blob.warnings, isNotEmpty);
     });

     test('parses BLOCKED detail blob with B0 gate', () async {
       final json = await loadFixture('detail_blob_blocked.json');
       final blob = DetailBlob.fromJson(jsonDecode(json));

       expect(blob.sectionBreakdown.safetyPurity.sub.b0BlockingReason, isNotNull);
     });

     test('handles PDF image URL gracefully', () {
       final product = ProductsCore(imageUrl: 'https://example.com/label.pdf');
       expect(product.imageUrl.endsWith('.pdf'), true);
       // Widget should show placeholder, not crash
     });
   }
   ```

**Acceptance:**

- `flutter test` runs 15+ tests, all pass
- ScoreFitCalculator handles null profile, pregnancy conditions, age ranges
- Parser tests verify JSON deserialization for all verdict types
- Widgets render without errors in widget tests

---

**Phase 1 Exit Criteria:**

- ✅ App opens on iOS simulator
- ✅ 5 tabs navigate with state preservation
- ✅ Theme colors match spec (verified with color picker)
- ✅ SQLite loads 180K products from bundled DB
- ✅ Supabase client connects and fetches manifest
- ✅ Reference data parses once at startup
- ✅ ScoreFitCalculator unit tests pass
- ✅ Parser smoke tests pass for all detail blob types
- ✅ `flutter analyze` shows 0 errors

**Estimated Duration:** 10-14 days (2 weeks)

---

### **Phase 2: Core Scan Loop (Week 2-4)**

**Status:** 🔜 **BLOCKED BY PHASE 1**
**Goal:** Scan a barcode, see full clinical breakdown with real pipeline data

#### Sprint 2.1: Camera & Barcode Detection (Days 15-17)

**Deliverables:**

1. **Create `lib/features/scan/scan_screen.dart`:**

   ```dart
   class ScanScreen extends ConsumerStatefulWidget {
     @override
     ConsumerState<ScanScreen> createState() => _ScanScreenState();
   }

   class _ScanScreenState extends ConsumerState<ScanScreen> {
     MobileScannerController controller = MobileScannerController();

     @override
     Widget build(BuildContext context) {
       return Scaffold(
         body: Stack(
           children: [
             MobileScanner(
               controller: controller,
               onDetect: (capture) => _onBarcodeDetected(capture),
             ),
             Center(child: ScannerBracket()), // Animated bracket
             Positioned(
               top: 60,
               right: 20,
               child: IconButton(
                 icon: Icon(LucideIcons.flashlight),
                 onPressed: controller.toggleTorch,
               ),
             ),
             Positioned(
               bottom: 40,
               child: TextButton(
                 onPressed: () => _showManualEntrySheet(),
                 child: Text('Enter Code Manually'),
               ),
             ),
           ],
         ),
       );
     }

     Future<void> _onBarcodeDetected(BarcodeCapture capture) async {
       final barcode = capture.barcodes.firstOrNull;
       if (barcode == null) return;

       // Pause camera
       controller.stop();

       // Haptic feedback
       HapticFeedback.heavyImpact();

       // Show success banner
       ScaffoldMessenger.of(context).showSnackBar(
         SnackBar(
           content: Text('Product Identified'),
           backgroundColor: AppTheme.brandPrimary,
           duration: Duration(milliseconds: 1500),
         ),
       );

       // Look up product
       await _lookupProduct(barcode.rawValue);
     }
   }
   ```

2. **Create animated scanner bracket in `lib/features/scan/widgets/scanner_bracket.dart`:**

   ```dart
   class ScannerBracket extends StatefulWidget {
     @override
     _ScannerBracketState createState() => _ScannerBracketState();
   }

   class _ScannerBracketState extends State<ScannerBracket>
       with SingleTickerProviderStateMixin {
     late AnimationController _controller;

     @override
     void initState() {
       super.initState();
       _controller = AnimationController(
         duration: Duration(seconds: 2),
         vsync: this,
       )..repeat(reverse: true);
     }

     @override
     Widget build(BuildContext context) {
       return AnimatedBuilder(
         animation: _controller,
         builder: (context, child) {
           return CustomPaint(
             painter: BracketPainter(progress: _controller.value),
             size: Size(280, 280),
           );
         },
       );
     }
   }
   ```

3. **Handle permissions in `lib/features/scan/scan_permission_handler.dart`:**

   ```dart
   class ScanPermissionHandler {
     Future<PermissionStatus> requestCameraPermission() async {
       final status = await Permission.camera.request();

       if (status.isDenied) {
         // Show dialog: "Camera access required to scan barcodes"
       } else if (status.isPermanentlyDenied) {
         // Show dialog: "Open Settings to grant camera permission"
         await openAppSettings();
       }

       return status;
     }
   }
   ```

**Acceptance:**

- Camera opens on Scan tab
- Scanner bracket animates smoothly
- Flash toggle works
- Scanning a barcode triggers haptic + banner
- Permission denied state shows helpful dialog

---

#### Sprint 2.2: Product Lookup & B0 Gate (Days 18-20)

**Deliverables:**

1. **Create product lookup service in `lib/providers/product_provider.dart`:**

   ```dart
   @riverpod
   Future<ProductLookupResult> lookupByUpc(
     LookupByUpcRef ref,
     String upc,
   ) async {
     final db = ref.watch(referenceDatabaseProvider);

     // Query products_core with deterministic ordering
     final products = await (db.select(db.productsCore)
           ..where((p) => p.upcSku.equals(upc))
           ..orderBy([
             (p) => OrderingTerm(
                   expression: p.productStatus.equalsValue('active'),
                   mode: OrderingMode.desc,
                 ),
             (p) => OrderingTerm.desc(p.scoreQuality80),
             (p) => OrderingTerm.asc(p.dsldId),
           ])
           ..limit(2))
         .get();

     if (products.isEmpty) {
       return ProductLookupResult.notFound(upc);
     }

     // Handle UPC collision (1:N relationship)
     if (products.length > 1) {
       final scoreDiff = (products[0].scoreQuality80 ?? 0) -
                         (products[1].scoreQuality80 ?? 0);
       if (scoreDiff.abs() < 5) {
         return ProductLookupResult.ambiguous(products);
       }
     }

     return ProductLookupResult.found(products.first);
   }
   ```

2. **Create B0 warning screen in `lib/features/scan/b0_warning_screen.dart`:**

   ```dart
   class B0WarningScreen extends StatelessWidget {
     final ProductsCore product;

     @override
     Widget build(BuildContext context) {
       // Double-pulse haptic
       HapticFeedback.vibrate();
       Future.delayed(Duration(milliseconds: 200), () {
         HapticFeedback.vibrate();
       });

       return Scaffold(
         body: SafeArea(
           child: Padding(
             padding: EdgeInsets.all(24),
             child: Column(
               children: [
                 // Red circle with X icon (no score ring)
                 Container(
                   width: 120,
                   height: 120,
                   decoration: BoxDecoration(
                     shape: BoxShape.circle,
                     color: AppTheme.verdictBlocked,
                   ),
                   child: Icon(
                     LucideIcons.xCircle,
                     size: 64,
                     color: Colors.white,
                   ),
                 ),
                 SizedBox(height: 24),

                 // Critical warning card
                 Card(
                   color: AppTheme.verdictBlocked.withOpacity(0.1),
                   child: Padding(
                     padding: EdgeInsets.all(20),
                     child: Column(
                       children: [
                         Text(
                           'CRITICAL WARNING',
                           style: AppTheme.heading2.copyWith(
                             color: AppTheme.verdictBlocked,
                           ),
                         ),
                         SizedBox(height: 12),
                         Text(
                           product.blockingReason ?? 'This product is unsafe',
                           textAlign: TextAlign.center,
                           style: AppTheme.body1,
                         ),
                       ],
                     ),
                   ),
                 ),

                 Spacer(),

                 // Actions
                 PrimaryButton(
                   label: 'Report This Product',
                   onPressed: () => _reportProduct(context),
                 ),
                 SizedBox(height: 12),
                 OutlineButton(
                   label: 'Scan Another Product',
                   onPressed: () => Navigator.pop(context),
                 ),
               ],
             ),
           ),
         ),
       );
     }
   }
   ```

3. **Implement scan limit enforcement in `lib/services/scan_limit_service.dart`:**

   ```dart
   class ScanLimitService {
     Future<ScanLimitResult> checkAndIncrement({
       required bool isSignedIn,
       required String? userId,
     }) async {
       if (!isSignedIn) {
         // Guest mode: use Hive counter
         final box = await Hive.openBox('guest_scan_count');
         final count = box.get('count', defaultValue: 0) as int;

         if (count >= 10) {
           return ScanLimitResult.exceeded(limit: 10, isGuest: true);
         }

         await box.put('count', count + 1);
         return ScanLimitResult.allowed(scansRemaining: 10 - count - 1);
       } else {
         // Signed-in: use increment_usage RPC
         try {
           final result = await Supabase.instance.client
             .rpc('increment_usage', params: {
               'p_user_id': userId,
               'p_type': 'scan',
             });

           final scansToday = result['scans_today'] as int;
           final limitExceeded = result['limit_exceeded'] as bool;

           if (limitExceeded) {
             return ScanLimitResult.exceeded(limit: 20, isGuest: false);
           }

           return ScanLimitResult.allowed(scansRemaining: 20 - scansToday);
         } catch (e) {
           // Network failure fallback: allow scan, use Hive counter
           final box = await Hive.openBox('fallback_scan_count');
           final count = box.get('count', defaultValue: 0) as int;
           await box.put('count', count + 1);

           return ScanLimitResult.allowed(scansRemaining: null); // Unknown
         }
       }
     }
   }
   ```

**Acceptance:**

- Scanning a valid UPC returns product from SQLite
- Scanning a banned product (B0 gate) shows critical warning screen
- Scan limit enforced: 10 for guest, 20 for signed-in
- Network failure during limit check allows scan (doesn't block user)
- UPC collision shows chooser UI if scores are close

---

#### Sprint 2.3: Result Screen & Detail Blob Loading (Days 21-25)

**Deliverables:**

1. **Create result screen in `lib/features/scan/result_screen.dart`:**

   ```dart
   class ResultScreen extends ConsumerWidget {
     final ProductsCore product;

     @override
     Widget build(BuildContext context, WidgetRef ref) {
       final detailBlob = ref.watch(detailBlobProvider(product.dsldId));
       final healthProfile = ref.watch(healthProfileProvider);

       return Scaffold(
         body: CustomScrollView(
           slivers: [
             // Hero section
             SliverToBoxAdapter(
               child: _buildHeroSection(product, healthProfile),
             ),

             // Profile tease banner (if no profile)
             if (healthProfile.value == null)
               SliverToBoxAdapter(
                 child: ProfileTeaseBanner(),
               ),

             // Verdict banner
             SliverToBoxAdapter(
               child: VerdictBanner(verdict: product.verdict),
             ),

             // Condition alert banner (if interaction_summary matches profile)
             if (healthProfile.value != null)
               SliverToBoxAdapter(
                 child: _buildConditionAlert(product, healthProfile.value!),
               ),

             // 5 Pillar Smart Cards (accordion)
             detailBlob.when(
               data: (blob) => _buildPillarCards(blob, product),
               loading: () => _buildShimmerCards(),
               error: (err, stack) => _buildOfflineState(),
             ),

             // Add to Stack button
             SliverToBoxAdapter(
               child: Padding(
                 padding: EdgeInsets.all(24),
                 child: PrimaryButton(
                   label: 'Add to Stack',
                   onPressed: () => _showAddToStackSheet(context),
                 ),
               ),
             ),
           ],
         ),
       );
     }

     Widget _buildHeroSection(ProductsCore product, AsyncValue<HealthProfile?> profile) {
       return Container(
         padding: EdgeInsets.all(24),
         child: Column(
           children: [
             // Product image (check for PDF first!)
             if (product.imageUrl?.endsWith('.pdf') == true)
               _buildPdfPlaceholder()
             else
               CachedNetworkImage(
                 imageUrl: product.imageUrl ?? '',
                 height: 200,
                 placeholder: (context, url) => ShimmerCard(height: 200),
                 errorWidget: (context, url, error) => _buildImageError(),
               ),

             SizedBox(height: 16),

             // Product name + brand
             Text(product.productName, style: AppTheme.heading1),
             Text(product.brand, style: AppTheme.subtitle1),

             SizedBox(height: 24),

             // Score ring + grade + percentile
             profile.when(
               data: (p) => _buildScoreRing(product, p),
               loading: () => CircularProgressIndicator(),
               error: (_, __) => _buildScoreRing(product, null),
             ),
           ],
         ),
       );
     }

     Widget _buildConditionAlert(ProductsCore product, HealthProfile profile) {
       // Parse interaction_summary_hint from product
       final hint = product.interactionSummaryHint != null
           ? jsonDecode(product.interactionSummaryHint!)
           : null;

       if (hint == null) return SizedBox.shrink();

       // Check if user profile conditions/meds intersect with hint
       final userConditions = profile.conditions.toSet();
       final userDrugClasses = profile.drugClasses.toSet();

       final matchedConditions = (hint['condition_summary'] as List? ?? [])
           .where((id) => userConditions.contains(id))
           .toList();

       final matchedDrugs = (hint['drug_class_summary'] as List? ?? [])
           .where((id) => userDrugClasses.contains(id))
           .toList();

       if (matchedConditions.isEmpty && matchedDrugs.isEmpty) {
         return SizedBox.shrink();
       }

       return Container(
         margin: EdgeInsets.all(16),
         padding: EdgeInsets.all(16),
         decoration: BoxDecoration(
           color: AppTheme.verdictCaution.withOpacity(0.1),
           borderRadius: BorderRadius.circular(12),
           border: Border.all(color: AppTheme.verdictCaution),
         ),
         child: Row(
           children: [
             Icon(LucideIcons.alertTriangle, color: AppTheme.verdictCaution),
             SizedBox(width: 12),
             Expanded(
               child: Column(
                 crossAxisAlignment: CrossAxisAlignment.start,
                 children: [
                   Text(
                     'Condition Alert',
                     style: AppTheme.heading3.copyWith(
                       color: AppTheme.verdictCaution,
                     ),
                   ),
                   Text(
                     'This product may interact with your health profile.',
                     style: AppTheme.body2,
                   ),
                 ],
               ),
             ),
             TextButton(
               onPressed: () {
                 // Scroll to Card 3 (Clinical Evidence)
                 // Will show full interaction warnings after detail blob loads
               },
               child: Text('View Details'),
             ),
           ],
         ),
       );
     }
   }
   ```

2. **Create detail blob service in `lib/data/remote/detail_blob_service.dart`:**

   ```dart
   @riverpod
   Future<DetailBlob> detailBlob(DetailBlobRef ref, String dsldId) async {
     final userDb = ref.watch(userDatabaseProvider);

     // Check cache first
     final cached = await (userDb.select(userDb.productDetailCache)
           ..where((c) => c.dsldId.equals(dsldId)))
         .getSingleOrNull();

     if (cached != null && _isCacheValid(cached)) {
       return DetailBlob.fromJson(jsonDecode(cached.detailJson));
     }

     // Fetch from Supabase Storage
     final referenceDb = ref.watch(referenceDatabaseProvider);
     final product = await (referenceDb.select(referenceDb.productsCore)
           ..where((p) => p.dsldId.equals(int.parse(dsldId))))
         .getSingle();

     final blobHash = product.detailBlobSha256;
     if (blobHash == null) {
       throw Exception('No detail blob available for this product');
     }

     // Derive hashed path: /shared/details/sha256/{hash[0:2]}/{hash}.json
     final hashPrefix = blobHash.substring(0, 2);
     final blobUrl = 'https://omayamxacvacrnvdvzhr.supabase.co/storage/v1/object/'
         'public/pharmaguide/shared/details/sha256/$hashPrefix/$blobHash.json';

     final response = await http.get(Uri.parse(blobUrl));

     if (response.statusCode != 200) {
       throw Exception('Failed to fetch detail blob: ${response.statusCode}');
     }

     final json = jsonDecode(response.body);

     // Cache in user DB
     await userDb.into(userDb.productDetailCache).insert(
       ProductDetailCacheCompanion.insert(
         dsldId: dsldId,
         detailJson: response.body,
         cachedAt: DateTime.now(),
         source: 'supabase',
         detailVersion: json['blob_version'] ?? 1,
       ),
       mode: InsertMode.insertOrReplace,
     );

     return DetailBlob.fromJson(json);
   }
   ```

3. **Create 5 pillar cards in `lib/features/scan/widgets/pillar_cards/`:**

   **`card_1_ingredient_quality.dart`:**

   ```dart
   class Card1IngredientQuality extends StatelessWidget {
     final DetailBlob blob;
     final ProductsCore product;

     @override
     Widget build(BuildContext context) {
       final section = blob.sectionBreakdown.ingredientQuality;

       return PillarCard(
         title: 'Ingredient Quality',
         score: section.score,
         maxScore: section.max,
         children: [
           // Ingredient list
           ...blob.ingredients.map((ing) => IngredientRow(ingredient: ing)),

           // Premium form badges
           if (section.sub.premiumFormCount > 0)
             Row(
               children: [
                 Icon(LucideIcons.award, size: 16, color: AppTheme.brandPrimary),
                 SizedBox(width: 8),
                 Text('${section.sub.premiumFormCount} Premium Forms'),
               ],
             ),

           // Delivery tier
           if (section.sub.deliveryTier != null)
             DeliveryBadge(tier: section.sub.deliveryTier!),

           // Probiotic breakdown (if applicable)
           if (section.sub.probioticBreakdown?.applicable == true)
             ProbioticBreakdown(breakdown: section.sub.probioticBreakdown!),

           // Omega-3 breakdown (if applicable)
           if (section.sub.omega3Breakdown?.applicable == true)
             Omega3Breakdown(breakdown: section.sub.omega3Breakdown!),
         ],
       );
     }
   }
   ```

   **`card_2_safety_purity.dart`:**

   ```dart
   class Card2SafetyPurity extends StatelessWidget {
     final DetailBlob blob;
     final ProductsCore product;

     @override
     Widget build(BuildContext context) {
       final section = blob.sectionBreakdown.safetyPurity;

       return PillarCard(
         title: 'Safety & Purity',
         score: section.score,
         maxScore: section.max,
         children: [
           // Certification badges
           if (product.thirdPartyCerts != null && product.thirdPartyCerts!.isNotEmpty)
             Wrap(
               spacing: 8,
               children: product.thirdPartyCerts!.split(',')
                   .map((cert) => CertBadge(cert: cert.trim()))
                   .toList(),
             ),

           // Proprietary blend warning
           if (section.sub.hasProprietaryBlend == true)
             WarningRow(
               icon: LucideIcons.alertCircle,
               text: 'Contains proprietary blend (exact doses hidden)',
               severity: 'caution',
             ),

           // Harmful additives
           ...blob.warnings.whereType<HarmfulAdditiveWarning>().map((warning) {
             return ExpansionTile(
               leading: Icon(LucideIcons.alertTriangle, color: AppTheme.verdictCaution),
               title: Text(warning.additiveName),
               subtitle: Text(warning.mechanism ?? 'May be harmful'),
               children: [
                 if (warning.notes != null)
                   Padding(
                     padding: EdgeInsets.all(16),
                     child: Text(warning.notes!),
                   ),
                 if (warning.populationWarnings != null)
                   ...warning.populationWarnings!.map((pop) =>
                     Chip(label: Text(pop)),
                   ),
               ],
             );
           }),

           // Allergens
           if (product.allergenTags != null && product.allergenTags!.isNotEmpty)
             AllergenList(allergens: product.allergenTags!.split(',')),

           // B7 dose safety (if exceeded UL)
           if (section.sub.b7Penalty > 0)
             WarningRow(
               icon: LucideIcons.shieldAlert,
               text: 'Exceeds safe upper limit for some ingredients',
               severity: 'warning',
             ),
         ],
       );
     }
   }
   ```

   **`card_3_clinical_evidence.dart`:**

   ```dart
   class Card3ClinicalEvidence extends StatelessWidget {
     final DetailBlob blob;

     @override
     Widget build(BuildContext context) {
       final section = blob.sectionBreakdown.evidenceResearch;

       return PillarCard(
         title: 'Clinical Evidence',
         score: section.score,
         maxScore: section.max,
         children: [
           // Sub-clinical dose warning
           if (section.sub.hasSubClinicalDose == true)
             WarningRow(
               icon: LucideIcons.info,
               text: 'Some ingredients below clinically effective dose',
               severity: 'info',
             ),

           // Interaction warnings (sealed class)
           ...blob.warnings.whereType<InteractionWarning>().map((warning) {
             return warning.when(
               condition: (conditionId, summary, doseThreshold) => ConditionWarningCard(
                 conditionId: conditionId,
                 summary: summary,
                 doseThreshold: doseThreshold,
               ),
               drugClass: (drugClassId, summary, doseThreshold) => DrugWarningCard(
                 drugClassId: drugClassId,
                 summary: summary,
                 doseThreshold: doseThreshold,
               ),
             );
           }),

           // Study badges
           if (section.matchedEntries > 0)
             Row(
               children: [
                 Icon(LucideIcons.flaskConical, size: 16, color: AppTheme.brandPrimary),
                 SizedBox(width: 8),
                 Text('${section.matchedEntries} Clinically Backed Ingredients'),
               ],
             ),

           // Ingredient points breakdown
           ...section.ingredientPoints.entries.map((entry) =>
             Text('${entry.key}: ${entry.value} pts'),
           ),
         ],
       );
     }
   }
   ```

   **`card_4_brand_trust.dart`:**

   ```dart
   class Card4BrandTrust extends StatelessWidget {
     final DetailBlob blob;
     final ProductsCore product;

     @override
     Widget build(BuildContext context) {
       final section = blob.sectionBreakdown.brandTrust;

       return PillarCard(
         title: 'Brand Trust',
         score: section.score,
         maxScore: section.max,
         children: [
           // Manufacturer violation override
           if (section.sub.manufacturerViolationOverride == true)
             WarningRow(
               icon: LucideIcons.alertOctagon,
               text: 'Manufacturer has FDA violations',
               severity: 'warning',
             ),

           // Boolean rows
           BooleanRow(
             label: 'GMP Certified',
             value: product.isGmpCertified,
           ),
           BooleanRow(
             label: 'Made in USA',
             value: product.madeInUsa,
           ),

           // Product status
           Row(
             children: [
               Text('Status: ', style: AppTheme.body2),
               Chip(
                 label: Text(product.productStatus ?? 'Unknown'),
                 backgroundColor: product.productStatus == 'active'
                     ? AppTheme.brandPrimary.withOpacity(0.1)
                     : Colors.grey.withOpacity(0.1),
               ),
             ],
           ),
         ],
       );
     }
   }
   ```

   **`card_5_personal_match.dart`:**

   ```dart
   class Card5PersonalMatch extends ConsumerWidget {
     final ProductsCore product;
     final DetailBlob blob;

     @override
     Widget build(BuildContext context, WidgetRef ref) {
       final profile = ref.watch(healthProfileProvider);
       final referenceData = ref.watch(referenceDataProvider);

       return profile.when(
         data: (p) {
           if (p == null) {
             return PillarCard(
               title: 'Personal Match',
               isLocked: true,
               children: [
                 Text('Set up your health profile to see personalized fit score'),
                 SizedBox(height: 16),
                 OutlineButton(
                   label: 'Complete Profile',
                   onPressed: () => context.go('/profile'),
                 ),
               ],
             );
           }

           final fitResult = ScoreFitCalculator().calculate(
             scoreQuality80: product.scoreQuality80,
             breakdown: blob.sectionBreakdown,
             profile: p,
             referenceData: referenceData.value!,
           );

           return PillarCard(
             title: 'Personal Match',
             score: fitResult.scoreFit20,
             maxScore: 20,
             children: [
               ...fitResult.chips.map((chip) => Chip(label: Text(chip))),

               if (fitResult.missingFields.isNotEmpty)
                 Column(
                   crossAxisAlignment: CrossAxisAlignment.start,
                   children: [
                     SizedBox(height: 16),
                     Text('Complete your profile for more insights:'),
                     ...fitResult.missingFields.map((field) =>
                       Text('• $field', style: AppTheme.body2),
                     ),
                   ],
                 ),
             ],
           );
         },
         loading: () => PillarCard(
           title: 'Personal Match',
           children: [CircularProgressIndicator()],
         ),
         error: (_, __) => PillarCard(
           title: 'Personal Match',
           children: [Text('Error loading profile')],
         ),
       );
     }
   }
   ```

4. **Create "Add to Stack" bottom sheet in `lib/features/scan/widgets/add_to_stack_sheet.dart`:**

   ```dart
   class AddToStackSheet extends HookConsumerWidget {
     final ProductsCore product;

     @override
     Widget build(BuildContext context, WidgetRef ref) {
       final selectedTiming = useState<String>('AM');
       final selectedSupply = useState<int>(30);

       return AppBottomSheet(
         title: 'Add to Stack',
         child: Column(
           crossAxisAlignment: CrossAxisAlignment.start,
           children: [
             // Product preview
             Row(
               children: [
                 CachedNetworkImage(
                   imageUrl: product.imageUrl ?? '',
                   width: 60,
                   height: 60,
                 ),
                 SizedBox(width: 12),
                 Expanded(
                   child: Column(
                     crossAxisAlignment: CrossAxisAlignment.start,
                     children: [
                       Text(product.productName, style: AppTheme.heading3),
                       Text(product.brand, style: AppTheme.subtitle2),
                     ],
                   ),
                 ),
               ],
             ),

             SizedBox(height: 24),

             // Timing selection
             Text('When do you take it?', style: AppTheme.heading3),
             SizedBox(height: 12),
             Wrap(
               spacing: 8,
               children: ['AM', 'PM', 'Both', 'As Needed'].map((timing) {
                 final isSelected = selectedTiming.value == timing;
                 return ChoiceChip(
                   label: Text(timing),
                   selected: isSelected,
                   onSelected: (selected) {
                     if (selected) selectedTiming.value = timing;
                   },
                 );
               }).toList(),
             ),

             SizedBox(height: 24),

             // Supply count
             Text('Supply Count', style: AppTheme.heading3),
             SizedBox(height: 12),
             Wrap(
               spacing: 8,
               children: [30, 60, 90, 120].map((count) {
                 final isSelected = selectedSupply.value == count;
                 return ChoiceChip(
                   label: Text('$count days'),
                   selected: isSelected,
                   onSelected: (selected) {
                     if (selected) selectedSupply.value = count;
                   },
                 );
               }).toList(),
             ),

             SizedBox(height: 32),

             // Add button
             PrimaryButton(
               label: 'Add to Stack',
               onPressed: () async {
                 await ref.read(stackProvider.notifier).addProduct(
                   dsldId: product.dsldId.toString(),
                   timing: selectedTiming.value,
                   supplyCount: selectedSupply.value,
                 );

                 Navigator.pop(context);

                 // Show success checkmark
                 ScaffoldMessenger.of(context).showSnackBar(
                   SnackBar(
                     content: Row(
                       children: [
                         Icon(LucideIcons.checkCircle, color: Colors.white),
                         SizedBox(width: 12),
                         Text('Added to Stack'),
                       ],
                     ),
                     backgroundColor: AppTheme.brandPrimary,
                     duration: Duration(seconds: 2),
                   ),
                 );
               },
             ),
           ],
         ),
       );
     }
   }
   ```

**Acceptance:**

- Scanning a product shows full result screen with hero, verdict, and 5 pillar cards
- Detail blob fetches from Supabase Storage using hashed path
- Detail blob caches in `product_detail_cache` table
- Offline mode shows header + "Detail unavailable offline" banner
- Condition alert banner appears when `interaction_summary_hint` matches user profile
- "Add to Stack" flow works end-to-end with timing/supply selection
- PDF image URLs show placeholder instead of crashing
- NOT_SCORED products show "Not Scored" badge, no ring animation

---

**Phase 2 Exit Criteria:**

- ✅ Scan any supplement barcode on real device
- ✅ See full clinical breakdown with real pipeline data
- ✅ B0 gate blocks unsafe products with critical warning
- ✅ Detail blob loads from Supabase Storage
- ✅ 5 pillar cards render with all sub-sections
- ✅ Add to stack flow completes successfully
- ✅ Scan limits enforced (10 guest / 20 signed-in)
- ✅ Offline mode gracefully degrades

**Estimated Duration:** 10-14 days (2 weeks)

---

### **Phase 3: Stack & Home (Week 4-5)**

**Status:** 🔜 **BLOCKED BY PHASE 2**
**Goal:** Stack management, home screen, search, offline detection

See `docs/PHARMAGUIDE_MASTER_ROADMAP_PHASE3.md` for full details.

---

### **Phase 4: AI Chat & Profile (Week 5-6)**

**Status:** 🔜 **BLOCKED BY PHASE 3**
**Goal:** AI pharmacist + personalized health profile + condition alerts

See `docs/PHARMAGUIDE_MASTER_ROADMAP_PHASE4.md` for full details.

---

### **Phase 5: Polish & TestFlight (Week 6-8)**

**Status:** 🔜 **BLOCKED BY PHASE 4**
**Goal:** Production-ready for TestFlight submission

See `docs/PHARMAGUIDE_MASTER_ROADMAP_PHASE5.md` for full details.

---

## Risk Mitigation & Decision Log

### High-Risk Areas

| Risk                         | Mitigation                                                                                            | Owner       |
| ---------------------------- | ----------------------------------------------------------------------------------------------------- | ----------- |
| **DB swap corruption**       | Atomic swap: stage → verify checksum → rename → reopen. Rollback on failure. Test with bad checksums. | Flutter Dev |
| **Detail blob cache growth** | LRU eviction + max size (500MB). Release version invalidation.                                        | Flutter Dev |
| **Search UI jank**           | Debounce 300ms + LIMIT 50 + latest-query-wins pattern.                                                | Flutter Dev |
| **Taxonomy drift**           | Load `clinical_risk_taxonomy` at startup. Fail fast in debug if UI chips don't map.                   | Flutter Dev |
| **Edge Function costs**      | Rate limit (5 AI messages/day free), input validation, timeout handling. Monitor usage.               | Backend Dev |
| **First-time DB download**   | Bundle DB with app (default). OTA download is fallback if build size > 200MB.                         | DevOps      |

### Decision Log

| Date       | Decision                                        | Rationale                                                              |
| ---------- | ----------------------------------------------- | ---------------------------------------------------------------------- |
| 2026-04-02 | Use `drift` over raw `sqflite`                  | Compile-time safety, type-safe queries, better DX                      |
| 2026-04-02 | Bundle DB by default, OTA as fallback           | Instant first-launch experience, OTA for weekly updates only           |
| 2026-04-02 | Split DBs (`reference_db` + `user_db`)          | OTA never touches user data, simpler backup/restore                    |
| 2026-04-02 | Use `flutter_downloader` for OTA                | Handles 90MB+ files, survives app kill, progress tracking              |
| 2026-04-02 | Use `Riverpod 2.x` (not 3.x yet)                | 3.x is too new (beta), 2.x is stable and well-documented               |
| 2026-04-02 | Hive for guest counters, Supabase for signed-in | Hive is simple for ephemeral data, Supabase for server-enforced limits |
| 2026-04-02 | Network failure allows scan                     | Never block user on Supabase RPC failure, fall back to Hive            |
| 2026-04-07 | Phase 1-5 sprint breakdown                      | Match build design doc, add detailed acceptance criteria per sprint    |

---

## Appendix A: Full Dependency List

```yaml
dependencies:
  flutter:
    sdk: flutter

  # State Management
  flutter_riverpod: ^2.5.0
  riverpod_annotation: ^2.3.0
  flutter_hooks: ^0.20.5

  # Database
  drift: ^2.18.0
  sqlite3_flutter_libs: ^0.5.0

  # Backend
  supabase_flutter: ^2.5.0

  # Local Storage
  hive_flutter: ^1.1.0
  path_provider: ^2.1.0

  # Networking
  http: ^1.2.0
  connectivity_plus: ^6.0.0

  # Navigation
  go_router: ^14.0.0

  # UI Components
  google_fonts: ^6.2.0
  lucide_icons: ^0.1.0
  shimmer: ^3.0.0
  cached_network_image: ^3.3.0

  # Barcode Scanning
  mobile_scanner: ^5.0.0

  # Permissions
  permission_handler: ^11.3.0

  # Utilities
  url_launcher: ^6.3.0
  share_plus: ^7.2.0
  app_links: ^6.1.0

  # Notifications
  flutter_local_notifications: ^17.0.0

  # Downloads
  flutter_downloader: ^1.11.6

  # Splash Screen
  flutter_native_splash: ^2.3.0

  # Analytics & Crash Reporting
  firebase_core: ^2.24.0
  firebase_analytics: ^10.7.0
  firebase_crashlytics: ^3.4.0

  # Auth
  google_sign_in: ^6.1.0
  sign_in_with_apple: ^5.0.0

  # JSON Serialization
  freezed_annotation: ^2.4.1
  json_annotation: ^4.9.0

dev_dependencies:
  flutter_test:
    sdk: flutter

  # Code Generation
  build_runner: ^2.4.0
  drift_dev: ^2.18.0
  riverpod_generator: ^2.4.0
  freezed: ^2.4.1
  json_serializable: ^6.8.0

  # Linting
  flutter_lints: ^4.0.0
```

---

## Appendix B: Supabase Edge Function (AI Proxy)

**Deploy separately in Supabase project:**

```typescript
// supabase/functions/ai-pharmacist/index.ts
import { serve } from "https://deno.land/std@0.168.0/http/server.ts";
import { GoogleGenerativeAI } from "npm:@google/generative-ai@0.1.1";

const GEMINI_API_KEY = Deno.env.get("GEMINI_API_KEY")!;
const genAI = new GoogleGenerativeAI(GEMINI_API_KEY);

serve(async (req) => {
  // CORS
  if (req.method === "OPTIONS") {
    return new Response("ok", { headers: corsHeaders });
  }

  try {
    const { messages, system_prompt } = await req.json();

    // Input validation
    if (!messages || !Array.isArray(messages)) {
      return new Response(
        JSON.stringify({ error: "Invalid request: messages array required" }),
        { status: 400, headers: { "Content-Type": "application/json" } },
      );
    }

    if (messages.length > 50) {
      return new Response(
        JSON.stringify({ error: "Too many messages in history" }),
        { status: 400, headers: { "Content-Type": "application/json" } },
      );
    }

    // Call Gemini 2.5 Flash-Lite
    const model = genAI.getGenerativeModel({ model: "gemini-2.5-flash-lite" });

    const chat = model.startChat({
      history: messages.map((msg) => ({
        role: msg.role === "user" ? "user" : "model",
        parts: [{ text: msg.content }],
      })),
      generationConfig: {
        maxOutputTokens: 500,
        temperature: 0.7,
      },
    });

    const result = await chat.sendMessage(
      messages[messages.length - 1].content,
    );
    const response = await result.response;

    return new Response(
      JSON.stringify({
        message: response.text(),
        model: "gemini-2.5-flash-lite",
      }),
      { headers: { "Content-Type": "application/json" } },
    );
  } catch (error) {
    return new Response(JSON.stringify({ error: error.message }), {
      status: 500,
      headers: { "Content-Type": "application/json" },
    });
  }
});

const corsHeaders = {
  "Access-Control-Allow-Origin": "*",
  "Access-Control-Allow-Headers":
    "authorization, x-client-info, apikey, content-type",
};
```

**Deploy command:**

```bash
supabase functions deploy ai-pharmacist --no-verify-jwt
```

---

## Appendix C: Testing Strategy

### Unit Tests (Target: 80% coverage)

- **ScoreFitCalculator:** All sub-score paths (E1, E2a, E2b, E2c)
- **DetailBlob parsing:** All warning types, null handling, malformed JSON
- **ProductLookupService:** UPC collision, not found, B0 gate
- **ScanLimitService:** Guest/signed-in, network failure fallback

### Widget Tests

- **Reusable widgets:** PrimaryButton, ScoreRing, ScoreBadge
- **Pillar cards:** Render with mock data, expansion behavior
- **Forms:** Profile chip selection, stack timing/supply

### Integration Tests

- **Cold start → scan → result:** Mock Supabase blob fetch
- **DB swap:** Staging file, checksum verification, atomic rename, rollback
- **Offline mode:** SQLite queries work, detail fetch fails gracefully
- **Auth flow:** Anon → sign in → sign out

### Manual QA Checklist (Phase 5)

- [ ] Scan 10 different products (SAFE, CAUTION, UNSAFE, NOT_SCORED, BLOCKED)
- [ ] Add to stack, edit timing, delete with swipe
- [ ] Search for products by name/brand
- [ ] Chat with AI (5 message limit)
- [ ] Set up health profile (conditions, meds, goals)
- [ ] Dark mode toggle
- [ ] Offline mode (airplane mode)
- [ ] DB version update (mock new manifest)
- [ ] Permission denied states (camera, notifications)
- [ ] Deep link: `pharmaguide://product/15123`

---

## Next Steps

**Immediate Actions (This Week):**

1. ✅ Review this roadmap with team
2. 🔨 Create Flutter project (`flutter create PharmaGuide_ai`)
3. 🔨 Set up CLAUDE.md with hard rules
4. 🔨 Configure `pubspec.yaml` with all dependencies
5. 🔨 Bundle `pharmaguide_core.db` from pipeline output
6. 🔨 Create `app_theme.dart` with all design tokens
7. 🔨 Set up drift schema for `reference_db` and `user_db`

**Sprint 1 Kickoff (Week 1):**

- Daily standup at 9am
- Pair programming sessions for complex flows (scan loop, detail blob loading)
- Code review before merging to `main`
- Weekly demo every Friday

**Communication:**

- Slack: #pharmaguide-dev for daily updates
- GitHub Issues: Tag with `phase-1`, `phase-2`, etc
- Notion: Sprint planning board

---

**Version:** 1.0.0
**Last Updated:** 2026-04-07
**Owner:** Sean Cheick
**Reviewers:** [TBD]
