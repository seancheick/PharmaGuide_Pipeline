# PharmaGuide Pipeline Dashboard UX Refresh Design

**Date:** 2026-04-09  
**Status:** Proposed  
**Owner:** Codex  
**Related:** `docs/superpowers/specs/2026-03-31-pipeline-dashboard-design.md`, `scripts/dashboard/app.py`, `scripts/dashboard/INSTRUCTIONS.md`

## Goal

Redesign the PharmaGuide Pipeline Dashboard into a modern executive analytics UI that serves three jobs at once:

1. release readiness and operator triage
2. executive health and status reporting
3. product and market intelligence exploration

The redesign must keep the dashboard read-only, improve navigation and clarity, make timestamps human-readable, and explicitly show where each tab's data comes from.

## Why This Refresh Is Needed

The current dashboard is functionally broad, but the UI communicates too little context:

- it feels like a default Streamlit app instead of a decision cockpit
- navigation is flat, so operational and analytical tasks feel mixed together
- timestamps are raw ISO strings such as `2026-04-09T16:26:05.733827Z`
- the dashboard currently blends older export data from `scripts/final_db_output/` with newer pipeline activity from `scripts/products/` without making that distinction obvious

That last issue is especially important. The current workspace proves the data planes are not the same timeline:

- export snapshot data is from March 30, 2026
- batch and dataset activity are from April 9, 2026

The UI must make that separation explicit so users trust what they are reading.

## Confirmed Data Sources

The redesign is based on the current loader behavior in `scripts/dashboard/data_loader.py`.

### Release Snapshot

Used for released/exported/scored truth:

- `scripts/final_db_output/pharmaguide_core.db`
- `scripts/final_db_output/export_manifest.json`
- `scripts/final_db_output/export_audit_report.json`
- `scripts/final_db_output/detail_index.json`
- `scripts/final_db_output/detail_blobs/*.json`

### Pipeline Activity

Used for recent processing status and failures:

- `scripts/products/logs/processing_state.json`
- `scripts/products/logs/batch_*_log.txt`

### Dataset Outputs

Used for per-dataset freshness and intermediate report activity:

- `scripts/products/output_*`
- optional `reports/*.json` inside each output directory

## Design Direction

### Chosen Direction

Modern executive analytics UI.

This should feel:

- premium
- calm
- high-clarity
- trustworthy
- useful for both operators and leadership

It should not feel:

- like a generic developer admin panel
- like a default Streamlit form app
- like a noisy neon analytics dashboard

## Brand Translation

The dashboard should use the PharmaGuide social brand kit, adapted for an internal analytics surface.

### Color Use

- `Slate 900` for the main chrome, headings, and strong anchors
- `Teal 500` and `Teal 600` for navigation, active states, accents, and source chips
- `Teal 50` for supporting surfaces such as freshness and source panels
- `Slate 100` for subtle section backgrounds and dividers
- `Emerald 500` for positive/healthy/ready
- `Amber 500` for caution/stale/review
- `Red` for blockers, failures, banned substances, and recalls

`Cyan 400` should be used sparingly, if at all, because too much cyan makes the UI feel generic and dated.

### Typography

- `Source Serif 4` for primary page headings and the top-level dashboard identity
- `Plus Jakarta Sans` for navigation, subheads, cards, KPI labels, and section headers
- `Inter` for body text, metadata, helper text, captions, and tables

## Information Architecture

The flat navigation should be replaced by grouped navigation:

- `Command Center`
- `Release`
  - Product Inspector
  - Release Diff
- `Pipeline`
  - Pipeline Health
  - Observability
  - Batch Diff
- `Quality`
  - Data Quality
- `Intelligence`
  - Intelligence Dashboard

### Command Center

A new landing page should summarize:

- release snapshot freshness
- pipeline freshness
- dataset freshness
- top alerts
- release gate status
- operator shortcuts into problem areas
- intelligence shortcuts into high-value insights

This page is the "first place to look" and should reduce the need to click through multiple tabs just to understand overall state.

## Global Layout

Every page should use a shared structure.

### Top Header

Persistent top header title:

`PharmaGuide Pipeline Dashboard`

The header should also show:

- current overall status
- last export time
- last pipeline activity time
- stale-state warning if export data is older than pipeline activity

### Left Navigation Rail

The left rail should include:

- grouped sections
- stronger active-state styling
- short descriptive labels
- optional issue dots or small status indicators for problem views

### Main Content

Each page should start with:

- page title
- one-sentence explanation of what the page answers
- source chips
- freshness summary
- optional warning if the page mixes data planes

Then:

- KPI strip
- charts
- tables
- diagnostics or drill-downs

### Right Side Panel

Every page should include a right-side context panel with:

- `Data Sources`
- `Freshness`
- `How To Read This Page`
- `Related Views`

Some views should also include a short operator note, for example:

- "This page combines release snapshot metrics with current pipeline log activity."
- "This page reads from the release DB, not live dataset outputs."

## Data Clarity Rules

Every page must visibly identify its data plane using source chips or badges:

- `Release Snapshot`
- `Pipeline Logs`
- `Dataset Outputs`

If a page uses more than one, that should be obvious immediately.

### Freshness Rules

The dashboard should display three freshness concepts separately:

- `Last export`
- `Last batch activity`
- `Latest dataset activity`

If export data is older than pipeline activity, show a warning such as:

`Release snapshot is older than current pipeline activity. Some views show shipped data, while others show newer processing activity.`

## Date and Time Formatting

Raw ISO timestamps should not be shown in the UI unless inside raw-detail drill-downs.

### Preferred Display Format

Use human-readable formats like:

`Thursday, April 9, 2026 at 1:01:20 PM`

### Compact Format

For dense tables or cards:

`Apr 9, 2026 1:01 PM`

### Timezone Rule

When a timestamp affects interpretation, include timezone or convert consistently to the local environment timezone.

The UI should not make users decode strings like `2026-04-09T16:26:05.733827Z`.

## Page-Level Source Strategy

### Command Center

Sources:

- release manifest
- export audit
- processing state
- batch logs
- dataset output activity

Purpose:

- give one screen for overall readiness and recent activity

### Product Inspector

Sources:

- release DB
- detail blobs
- source path lookup into `scripts/products/output_*` where available

Purpose:

- inspect one product and understand score, safety, and completeness

### Pipeline Health

Sources:

- export manifest
- export audit
- batch logs
- processing state
- discovered artifacts in products/build folders

Purpose:

- answer whether the release is healthy and whether the last pipeline run is trustworthy

### Data Quality

Sources:

- release DB
- dataset output reports
- unmapped and fallback artifacts
- scoring config

Purpose:

- diagnose not-scored products, unmapped hotspots, fallback problems, coverage, and safety patterns

### Observability

Sources:

- export manifest and audit
- batch logs
- build history
- release DB
- detail blob analytics

Purpose:

- track integrity, failures, drift, bottlenecks, sync/storage status, and unusual patterns

### Release Diff

Sources:

- current and prior build roots
- release manifests
- release DBs

Purpose:

- compare releases and identify meaningful score or verdict changes

### Batch Diff

Sources:

- batch log history

Purpose:

- compare recent processing runs and identify dataset-level status changes

### Intelligence

Sources:

- release DB
- detail blobs

Purpose:

- surface top products, best forms, ingredient usage, high-risk ingredient patterns, brand consistency, and scoring drivers

## UX Principles

The redesign should follow these rules:

- lead with the answer before the detail
- never show a chart or table without context above it
- make the source of each number visible
- reduce timestamp ambiguity
- prefer grouped scanning over endless vertical blocks
- use whitespace and typography to create hierarchy rather than more borders
- preserve analytical depth without requiring users to already know the codebase

## Implementation Scope

This redesign should focus on:

- app shell
- navigation structure
- shared visual language
- shared page header component
- shared source/freshness side panel
- timestamp formatting utilities
- clearer top-level home page / command center

It does not require changing the underlying data model beyond what is needed to expose source and freshness metadata cleanly to the UI.

## Rollout Sequence

This redesign should not be implemented as a one-shot rewrite. The rollout order must be:

1. shared shell primitives
2. shared page metadata contract and date formatting utilities
3. new grouped navigation and header chrome
4. new Command Center landing page
5. page-by-page migration of existing views onto the new shell
6. docs, screenshots, and final visual verification

### MVP Cut Line

The minimum acceptable first landing is:

- new app shell
- grouped navigation
- human-readable timestamps
- shared source/freshness page header
- one working `Command Center`
- at least one migrated operational page and one migrated analytical page proving the pattern

Full completion requires all pages to use the new shell and metadata pattern.

## Shared Page Metadata Contract

Every page should declare a single metadata block that drives its header and context panel.

### Required Fields

- `page_title`
- `page_summary`
- `data_planes`
- `source_paths`
- `freshness_fields`
- `mixed_plane_warning`
- `related_views`
- `usage_notes`

### Semantics

- `data_planes`: one or more of `Release Snapshot`, `Pipeline Logs`, `Dataset Outputs`
- `source_paths`: exact file or directory roots used by the page
- `freshness_fields`: ordered timestamps shown in the header and side panel
- `mixed_plane_warning`: optional warning text when the page mixes timelines
- `related_views`: quick links to the next most relevant pages
- `usage_notes`: short instructions for how to read the page

This metadata must be shared and rendered consistently rather than implemented ad hoc inside each page.

## Deep-Link Compatibility

The refresh must preserve current deep-link behavior or replace it with a fully documented equivalent.

### Required Behaviors

- `?view=` links must continue to open the targeted page
- `?dsld_id=` links for the Product Inspector must continue to work
- the redesign must not break existing operator instructions that depend on page-level URL entry

If navigation grouping changes the internal route model, the app must still accept the existing query-param contract and map it to the new structure.

## Right-Side Context Panel Fallback

The preferred design is a right-side context panel on desktop-width layouts.

Because Streamlit layout behavior can constrain persistent side rails, the acceptable fallback order is:

1. fixed right column on desktop
2. collapsible right-column expander on narrower layouts
3. below-the-fold context block immediately after the page header if width is constrained

The page is not compliant if context is omitted entirely. Source, freshness, and usage guidance must always remain visible somewhere in the page structure.

## Risks

- Streamlit layout constraints may require pragmatic compromises on the right-side panel behavior
- some pages mix sources in ways that need careful wording to avoid misleading users
- multi-build visual features remain limited by the currently available workspace artifacts

## Verification Expectations

The redesign is only complete when:

1. all pages use the new navigation and header model
2. timestamps display in readable human form
3. each page clearly shows where its data comes from
4. the difference between release snapshot data and current pipeline activity is visually obvious
5. the dashboard is easier to scan and explain to a new engineer or operator
6. the existing dashboard test suite still passes

## Approval Summary

Approved interactively on 2026-04-09 with these choices:

- design direction: modern executive analytics UI
- goals: release readiness, executive reporting, and product intelligence all in scope
- persistent title: `PharmaGuide Pipeline Dashboard`
- side context panels on all pages
- human-readable date formatting
- explicit data-source labeling on each page
