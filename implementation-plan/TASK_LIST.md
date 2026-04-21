# Task List

## Active workstreams

1. Broaden Gmail query and pre-filter behavior so more application emails reach Gemini.
2. Improve first-run onboarding and explain Gmail OAuth for new users.
3. Add spreadsheet-friendly application export.
4. Correct monthly analytics and platform distribution rendering.
5. Add centered chart lightbox support and modernize chart styling.
6. Improve responsiveness across the affected dashboard pages/components.
7. Add targeted tests and update documentation.

## Execution order

1. Pipeline breadth changes
2. Onboarding and run controls
3. Export implementation
4. Analytics correctness fixes
5. Chart lightbox and UI refresh
6. Responsive cleanup
7. Tests, docs, and CI validation

## Notes

- Preserve the existing multi-user Supabase + orchestrator + tracker architecture.
- Do not reintroduce unread-only Gmail fetching.
- Keep Gemini as the final job-relevance classifier while filters stay intentionally broad.
