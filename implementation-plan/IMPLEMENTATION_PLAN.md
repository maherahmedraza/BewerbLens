# Pipeline Breadth, Export, and Dashboard Modernization Plan

## Problem

BewerbLens currently risks under-detecting job-related emails because the pre-filter path is restrictive before Gemini classification. At the same time, the product needs a clearer Gmail onboarding story for new users, better export options, corrected analytics visuals, and a more modern responsive dashboard.

## Objectives

1. Maximize one-time email discovery without regressing the multi-user pipeline architecture.
2. Keep read emails eligible for ingestion and classification.
3. Make Gmail onboarding and first-run behavior clear for new users.
4. Add efficient application export for Excel and Google Sheets workflows.
5. Fix analytics correctness and chart rendering issues, including a centered chart lightbox.
6. Refresh responsiveness, chart palette, and dashboard presentation while preserving existing data flows.
7. Raise confidence with targeted test coverage and documentation updates.

## Approach

### 1. Broaden pipeline capture before Gemini classification

- Audit the Gmail search query and pre-filter stages together.
- Reduce false negatives by widening search keywords and temporarily softening user filter enforcement for maximum-discovery runs.
- Preserve the current read + unread behavior and keep Gemini as the final relevance decision-maker.
- Ensure defaults for new users are broad enough to establish a reliable detection baseline before later optimization.

### 2. Improve new-user Gmail onboarding and run initiation

- Reuse the existing Gmail OAuth flow in the dashboard rather than introducing manual Gmail API key entry.
- Make the product explain that the backend uses the shared Gemini key while each user connects Gmail through OAuth.
- Ensure the UI makes it obvious how a newly connected user can queue their first processing run.

### 3. Add export workflows for applications

- Extend the applications experience with an export path suited for spreadsheet tools.
- Prefer a format and delivery mechanism that works cleanly in Excel and Google Sheets, and present it as a polished action in the UI.

### 4. Fix analytics and chart usability

- Correct monthly application aggregation if the current chart is deriving counts from the wrong fields or date normalization.
- Fix platform pie layout so large platform counts or longer labels do not clip the chart.
- Add a centered chart modal/lightbox for focused viewing.
- Introduce a more modern, consistent chart palette and evaluate a Sankey-style pipeline visualization where it fits the current data model.

### 5. Improve responsive layout quality

- Remove brittle inline layout patterns.
- Tighten component behavior on smaller screens and improve chart/table overflow handling.

### 6. Validate, document, and prepare CI-safe delivery

- Update automated tests around filters, onboarding/export surfaces, and analytics transformations.
- Refresh documentation to explain broad-capture behavior, Gmail OAuth onboarding, and export capabilities.
- Finish with repository lint/build/test coverage needed for a clean CI path.

## Assumptions

- “Popup a chart in the middle of the screen” means a centered modal/lightbox for enlarged chart viewing.
- “Save skills to a skills folder” will be implemented as reusable implementation notes captured during the work.
- The maximum-discovery phase should bias toward sending more candidate emails to Gemini instead of aggressively pruning them with user-defined filters.

## Risks and Notes

- Broadening capture increases Gmail API and Gemini usage, so usage metrics and user-facing explanations should remain accurate.
- Export functionality should avoid bypassing RLS or introducing service-role access into the frontend.
- Analytics fixes must align with existing Supabase views or server routes instead of inventing duplicate business logic.
