# 🚀 PharmaGuide Flutter App — START HERE

**Date:** 2026-04-07  
**Status:** 🟢 ALL SYSTEMS GO — Ready to Build  
**Owner:** Sean Cheick

---

## 📋 **What You Have**

✅ **Mature Data Pipeline** — 3065+ tests passing, 180K products ready  
✅ **Frozen Specifications** — Export schema v1.2.3, Flutter data contract v1  
✅ **Live Backend** — Supabase schema v2.0.0 deployed, storage configured  
✅ **Complete Roadmap** — 8-week sprint plan from zero to TestFlight  
✅ **2026 Tech Stack** — Flutter 3.41, Riverpod 3.0, health integrations ready  
✅ **Condition Safety System** — 3-tier warning engine for medical interactions  

---

## 🎯 **What You're Building**

**PharmaGuide** — The first clinical-grade supplement analysis app with:

- 📱 **Instant barcode scanning** → clinical breakdown in <3 seconds
- 🧬 **180K supplement database** — offline-first, no network required
- ⚕️ **Medical-grade safety** — B0 gate blocks unsafe products immediately
- 🔍 **3-tier interaction warnings** — condition/drug/supplement interactions
- 📊 **Stack health scoring** — quality score - interaction penalties
- 🤖 **AI pharmacist** — personalized guidance based on your health profile
- 🏥 **EHR integration** — import medications from Epic/Cerner
- ⌚ **Wearables sync** — Apple Health, Oura, Whoop
- 📤 **Social sharing** — stack reports, product discoveries, Instagram stories

**Target:** TestFlight in 8 weeks

---

## 📚 **Read These Documents (In Order)**

### **1. Executive Summary** (5 min read)
**File:** `docs/ROADMAP_EXECUTIVE_SUMMARY.md`  
**Purpose:** One-page overview of the project, timeline, and key features

### **2. Tech Stack** (15 min read)
**File:** `docs/TECH_STACK_2026.md`  
**Purpose:** Complete `pubspec.yaml`, architecture decisions, health integrations

### **3. Implementation Guide** (30 min read)
**File:** `docs/FINAL_IMPLEMENTATION_GUIDE.md`  
**Purpose:** Condition rules database, Day 1 action plan, FAQ

### **4. Master Roadmap** (1 hour read)
**File:** `docs/PHARMAGUIDE_MASTER_ROADMAP.md`  
**Purpose:** Full 8-week sprint breakdown with code examples (Phase 1-2 detailed)

### **5. UX Specification** (reference as needed)
**File:** `scripts/PharmaGuide Flutter MVP Dev.md`  
**Purpose:** Screen flows, interaction patterns, accessibility requirements (v5.3, 33 pages)

### **6. Data Contracts** (reference as needed)
**Files:**
- `scripts/FINAL_EXPORT_SCHEMA_V1.md` — SQLite schema (61 columns)
- `scripts/FLUTTER_DATA_CONTRACT_V1.md` — Dart shapes for each screen

---

## ⚡ **Quick Start (2.5 Hours)**

### **Step 1: Create Project** (30 min)

```bash
flutter create pharmaguide --org com.pharmaguide
cd pharmaguide
```

### **Step 2: Copy Dependencies** (15 min)

Open `docs/TECH_STACK_2026.md` and copy the complete `pubspec.yaml` dependencies section.

```bash
flutter pub get
```

### **Step 3: Bundle Database** (10 min)

```bash
mkdir -p assets/db
cp scripts/final_db_output/pharmaguide_core.db assets/db/

# Add to pubspec.yaml:
flutter:
  assets:
    - assets/db/pharmaguide_core.db
```

### **Step 4: Create Structure** (45 min)

```bash
mkdir -p lib/{theme,router,data/local/drift,providers,services}
mkdir -p lib/features/{home,scan,stack,chat,profile}

# Create CLAUDE.md (see Implementation Guide for template)
touch CLAUDE.md
```

### **Step 5: Run** (5 min)

```bash
flutter run
# Should open blank app with no errors
```

---

## 📅 **8-Week Timeline**

| Week | Phase | Goal | Status |
|------|-------|------|--------|
| 1-2 | Foundation | App opens, DB loads, theme set | 🔨 START HERE |
| 2-4 | Core Scan | Barcode → clinical breakdown | 🔜 After Phase 1 |
| 4-5 | Stack & Home | Stack management, search | 🔜 After Phase 2 |
| 5-6 | AI & Profile | AI chat, health profile | 🔜 After Phase 3 |
| 6-8 | Polish | Dark mode, TestFlight submit | 🔜 After Phase 4 |

---

## 🎨 **Design Philosophy**

**Yuka-Inspired:** Simple, fast, effective  
**Medical-Grade:** Safety over everything  
**No Gamification:** This is serious health software  
**Offline-First:** Works on airplane mode  
**Privacy-First:** Health data never leaves device (MVP)

---

## ✅ **What's Already Done**

1. ✅ Pipeline processes 180K products with 3065+ tests
2. ✅ Supabase deployed with RLS, manifest table, detail blobs
3. ✅ Export schema frozen (v1.2.3)
4. ✅ Condition rules database schema defined
5. ✅ Social sharing mockups ready
6. ✅ Product submission flow designed
7. ✅ Mood tracker approach finalized (supplement-linked)

---

## 🚨 **Important Decisions Already Made**

**Architecture:** Hybrid SQLite + Supabase (Approach A) — NOT full PostgreSQL  
**State Management:** Riverpod 3.0 — NOT Bloc or Provider  
**Database:** Drift — NOT raw sqflite  
**Networking:** Dio — NOT http package  
**Animations:** flutter_animate — NOT Rive (performance)  
**Health Profile:** Local-only (MVP) — NOT synced to cloud  
**Test Launch:** 1000-5000 products — NOT full 180K yet  

**Do NOT change these without reviewing the decision log in TECH_STACK_2026.md**

---

## 🔗 **External Resources**

- **Flutter 3.41 Docs:** https://flutter.dev/docs
- **Riverpod 3.0 Guide:** https://riverpod.dev/docs/whats_new
- **Drift Documentation:** https://drift.simonbinder.eu/
- **Supabase Flutter:** https://supabase.com/docs/guides/getting-started/quickstarts/flutter
- **FHIR R4 Spec:** https://hl7.org/fhir/R4/
- **Open Wearables API:** https://docs.openwearables.io/

---

## 💡 **Pro Tips**

1. **Read the roadmap first** — Don't skip ahead to coding
2. **Follow the hard rules** — They exist for clinical safety reasons
3. **Test on real devices** — Especially for health integrations
4. **Start small (1000 products)** — Scale to 180K after beta feedback
5. **Use CLAUDE.md** — Your AI pair programmer needs this context
6. **Commit atomic changes** — One feature per commit
7. **Run tests before PRs** — `flutter test` must pass

---

## 🎯 **Your First Week Goals**

**By End of Week 1:**
- ✅ Flutter project created
- ✅ Dependencies installed
- ✅ App opens on simulator
- ✅ 5 tabs navigate
- ✅ SQLite query returns 1 product
- ✅ Supabase client connects
- ✅ Theme colors match spec

**By End of Week 2:**
- ✅ Reference data parses once at startup
- ✅ ScoreFitCalculator unit tests pass
- ✅ Reusable widgets render (button, card, ring)
- ✅ Parser smoke tests pass
- ✅ `flutter analyze` shows 0 errors

**After Week 2, you're ready for Phase 2 (Core Scan Loop)**

---

## 📞 **Need Help?**

1. **Read FAQ** in `docs/FINAL_IMPLEMENTATION_GUIDE.md`
2. **Check roadmap** for detailed examples
3. **Review CLAUDE.md** for hard rules
4. **Ask in context** — reference which document/phase

---

## 🚀 **Ready to Build?**

**Start with:** `docs/ROADMAP_EXECUTIVE_SUMMARY.md`  
**Then:** Follow Day 1 Action Plan in `docs/FINAL_IMPLEMENTATION_GUIDE.md`  
**Then:** Execute Phase 1 from `docs/PHARMAGUIDE_MASTER_ROADMAP.md`

**You have everything you need. Let's build! 🎉**

---

**Version:** 1.0.0  
**Status:** 🟢 **GO!**  
**Owner:** Sean Cheick  
**Last Updated:** 2026-04-07
