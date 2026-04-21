# Broad Capture and Dashboard Delivery Notes

## Reusable skills captured in this implementation

1. **Broaden email discovery safely**
   - Expand Gmail query terms before touching classifier behavior.
   - Avoid Gmail-side sender exclusions when the product goal is maximum recall.
   - If discovery quality matters more than pre-filter efficiency, bypass restrictive include/exclude filters temporarily and let Gemini perform the final relevance decision.

2. **Fix analytics at the application layer when database views lag reality**
   - When existing SQL views encode the wrong business meaning, derive chart data from authenticated application records on the server.
   - For monthly application charts, count submissions from `date_applied`, then derive outcome counts from `status_history` timestamps so later status changes do not rewrite the original submission month.

3. **Make export features spreadsheet-friendly without extra infrastructure**
   - A UTF-8 BOM CSV route is enough to support both Excel and Google Sheets cleanly.
   - Keep export generation on the authenticated server route so RLS remains the enforcement boundary.

4. **Improve chart usability as datasets grow**
   - Collapse long-tail pie slices into `Other`.
   - Replace crowded chart legends with custom responsive legend lists.
   - Add a centered modal/lightbox so users can inspect charts without rebuilding the page layout.

5. **Clarify multi-user onboarding**
   - Keep Gemini server-side and shared.
   - Connect Gmail per user with OAuth.
   - Explain the flow in-product: Profile for connection, Settings for first backfill, Applications for export/review.
