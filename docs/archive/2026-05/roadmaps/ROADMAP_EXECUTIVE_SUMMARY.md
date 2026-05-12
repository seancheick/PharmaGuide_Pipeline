# PharmaGuide Master Roadmap — Executive Summary

**Version:** 1.0.0  
**Date:** 2026-04-07  
**For:** Sean Cheick  

---

## 📊 Quick Status

| Component | Status | Details |
|-----------|--------|---------|
| **Pipeline** | ✅ READY | 3-stage (Clean → Enrich → Score), 3065+ tests passing |
| **Data Quality** | ✅ READY | 180K products, 563 IQM parents, 143 banned ingredients |
| **Export Contract** | ✅ FROZEN | SQLite schema v1.2.3, detail blobs, manifest |
| **Supabase** | ✅ LIVE | Schema v2.0.0, storage bucket configured, RLS active |
| **Sync Script** | ✅ OPERATIONAL | `sync_to_supabase.py` tested and working |
| **Flutter App** | 🔨 READY TO START | All specs frozen, roadmap complete |

---

## 🎯 Timeline: 8-10 Weeks to TestFlight

```
Week 1-2   │ Phase 1: Foundation         │ 🔨 NEXT UP
           │ App opens, DB loads, theme  │
───────────┼─────────────────────────────┼──────────────────
Week 2-4   │ Phase 2: Core Scan Loop     │ 🔜 BLOCKED BY P1
           │ Barcode → clinical breakdown│
───────────┼─────────────────────────────┼──────────────────
Week 4-5   │ Phase 3: Stack & Home       │ 🔜 BLOCKED BY P2
           │ Stack management, search    │
───────────┼─────────────────────────────┼──────────────────
Week 5-6   │ Phase 4: AI Chat & Profile  │ 🔜 BLOCKED BY P3
           │ AI pharmacist + health data │
───────────┼─────────────────────────────┼──────────────────
Week 6-8   │ Phase 5: Polish & TestFlight│ 🔜 BLOCKED BY P4
           │ Production-ready, submitted │
───────────┼─────────────────────────────┼──────────────────
Week 8-10  │ Phase 6: Production Harden  │ 🔜 BLOCKED BY P5
           │ Analytics, crash reporting  │
```

---

## 🏗️ Architecture Overview

**Hybrid SQLite + Supabase (Approach A)**

```
┌──────────────────────────────────────┐
│  Flutter App (iOS/Android)           │
├──────────────────────────────────────┤
│  Layer 1: Local SQLite (Instant)     │
│  ├─ pharmaguide_core.db (180K rows)  │  ← Bundled with app
│  │  - products_core (61 columns)     │  ← OTA background updates
│  │  - products_fts (search)          │
│  │  - reference_data (JSON tables)   │
│  │  - export_manifest (version)      │
│  └─ user_data.db (read-write)        │  ← Created on first launch
│     - product_detail_cache           │  ← Never overwritten by OTA
│     - user_profile (health data)     │
│     - user_stacks_local              │
│     - user_favorites                 │
│     - user_scan_history              │
├──────────────────────────────────────┤
│  Layer 2: Supabase (On-Demand)       │
│  ├─ Auth (Google, Apple, Email, Anon)│
│  ├─ Detail Blobs (hashed paths)      │  ← Fetch on product view
│  ├─ User Stack Sync (tombstones)     │  ← Offline-first, async sync
│  ├─ Usage Tracking (RPC limits)      │  ← 20 scans/5 AI per day
│  └─ AI Proxy (Gemini Edge Function)  │  ← Server-side API key
└──────────────────────────────────────┘
```

**Why This Architecture?**
- **Instant offline access:** SQLite = no network required for scan/search
- **Privacy-first:** Health profile never leaves device
- **Scalable:** Detail blobs only fetched when needed (save bandwidth)
- **Simple:** Weekly OTA updates via full-file replacement (no binary diffs)

---

## 📋 Phase 1 Kickoff (Week 1-2)

**Immediate Actions (Next 3 Days):**

1. ✅ **Review this roadmap** — Read `docs/PHARMAGUIDE_MASTER_ROADMAP.md` (1800 lines, complete sprint breakdown)
2. 🔨 **Create Flutter project:**
   ```bash
   flutter create PharmaGuide_ai --org com.pharmaguide
   cd PharmaGuide_ai
   ```

3. 🔨 **Set up CLAUDE.md** — Copy from roadmap, add Supabase keys
4. 🔨 **Configure pubspec.yaml** — 30+ dependencies listed in Appendix A
5. 🔨 **Bundle DB:** Copy `scripts/final_db_output/pharmaguide_core.db` → `assets/db/`
6. 🔨 **Create theme:** `lib/theme/app_theme.dart` with all color tokens
7. 🔨 **Set up drift schema:** `reference_db.dart` + `user_db.dart`

**Phase 1 Exit Criteria:**
- App opens on iOS simulator
- 5 tabs navigate (Home, Scan, Stack, Chat, Profile)
- SQLite loads 180K products
- Supabase client connects
- `flutter test` passes 15+ unit tests

**Duration:** 10-14 days

---

## 🚀 Key Features by Phase

### Phase 1: Foundation
- ✅ Navigation (5 tabs with floating bar)
- ✅ Theme system (light/dark mode, all design tokens)
- ✅ SQLite setup (drift, bundled DB)
- ✅ Supabase integration (auth, manifest check)
- ✅ Reusable widgets (buttons, cards, score ring)
- ✅ ScoreFitCalculator (unit tested)

### Phase 2: Core Scan Loop
- ✅ Barcode scanning (camera, permissions, haptic)
- ✅ Product lookup (UPC collision handling)
- ✅ B0 safety gate (critical warning screen)
- ✅ Result screen (5 pillar cards, condition alerts)
- ✅ Detail blob loading (hashed paths, cache)
- ✅ Add to stack (timing/supply selection)
- ✅ Scan limits (10 guest / 20 signed-in)

### Phase 3: Stack & Home
- ✅ Stack management (CRUD, swipe to delete)
- ✅ Home screen (hero card, recent scans)
- ✅ Search (FTS5, autocomplete, filters)
- ✅ Offline detection (banners, graceful degradation)
- ✅ DB version checker (OTA background updates)

### Phase 4: AI Chat & Profile
- ✅ AI chat (Gemini proxy, 5 messages/day limit)
- ✅ Health profile (conditions, meds, goals)
- ✅ Personalized scoring (score_fit_20 on-device)
- ✅ Condition alerts (interaction flagging)
- ✅ Auth (Google, Apple, Email sign-in)

### Phase 5: Polish & TestFlight
- ✅ Error states (all 11 edge cases)
- ✅ Dark mode (WCAG AA compliant)
- ✅ Haptic feedback audit
- ✅ Performance optimization (no jank)
- ✅ TestFlight submission
- ✅ Internal beta testing

---

## 📝 Critical Success Factors

### ✅ Do's
1. **Follow the 10 Hard Rules** (see `CLAUDE.md`)
2. **Test before merging** — 80% coverage target
3. **Use drift for SQLite** — compile-time safety
4. **Bundle DB by default** — instant first launch
5. **Parse reference_data once** — at startup only
6. **Network failure = allow scan** — never block user

### ❌ Don'ts
1. **Don't edit package files manually** — use package managers
2. **Don't skip parser smoke tests** — test all detail blob types
3. **Don't show raw error codes** — user-friendly messages only
4. **Don't sync health profile to cloud** — local-only in MVP
5. **Don't overwrite user_data.db** — OTA touches reference DB only
6. **Don't re-parse reference_data** — singleton provider pattern

---

## 📦 Deliverables

### Code Artifacts
- Flutter app source code (`PharmaGuide_ai` repo)
- CLAUDE.md (AI pair programmer contract)
- Test suite (unit, widget, integration)
- CI/CD pipeline (GitHub Actions or Codemagic)

### Documentation
- `PHARMAGUIDE_MASTER_ROADMAP.md` (full 1800-line roadmap)
- `PHARMAGUIDE_MASTER_ROADMAP_PHASE3.md` (Stack & Home details)
- `PHARMAGUIDE_MASTER_ROADMAP_PHASE4.md` (AI & Profile details)
- `PHARMAGUIDE_MASTER_ROADMAP_PHASE5.md` (Polish & TestFlight)
- API documentation (Supabase Edge Function)

### Deployment
- iOS TestFlight build (internal beta)
- Android Play Store internal track (parallel)
- Supabase Edge Function (ai-pharmacist)

---

## 🎬 Next Steps

**This Week:**
1. Review full roadmap: `docs/PHARMAGUIDE_MASTER_ROADMAP.md`
2. Set up Flutter dev environment (`flutter doctor`)
3. Create project + configure dependencies
4. Write CLAUDE.md (copy from roadmap template)
5. Bundle pharmaguide_core.db from pipeline output

**Week 1 Milestones:**
- [ ] Day 1-2: Project setup + CLAUDE.md
- [ ] Day 3-4: Theme + navigation
- [ ] Day 5-7: Database setup (drift schema, bundled DB)
- [ ] Day 8-10: Supabase integration
- [ ] Day 11-14: Widgets + tests

**Sprint Cadence:**
- Daily standup at 9am
- Pair programming for complex flows
- Code review before merging to main
- Weekly demo every Friday

---

## 📞 Questions or Blockers?

If you need clarification on any phase, reference the detailed breakdown in:
- **Full Roadmap:** `docs/PHARMAGUIDE_MASTER_ROADMAP.md` (Phase 1-2 fully detailed)
- **Build Design:** `docs/superpowers/specs/2026-03-29-flutter-app-build-design.md`
- **UX Spec:** `scripts/PharmaGuide Flutter MVP Dev.md` (v5.3, 33 pages)
- **Data Contract:** `scripts/FLUTTER_DATA_CONTRACT_V1.md`
- **Export Schema:** `scripts/FINAL_EXPORT_SCHEMA_V1.md`

---

**Status:** 🟢 Ready to execute  
**Owner:** Sean Cheick  
**Created:** 2026-04-07  
**Last Updated:** 2026-04-07  

Let's build! 🚀
