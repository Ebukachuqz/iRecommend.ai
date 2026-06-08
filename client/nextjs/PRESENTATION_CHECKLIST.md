# iRecommend SaaS Presentation Checklist

## Start Services

- From project root, start the unified backend on port 8000:
  `uvicorn app.api.main:app --reload --port 8000`
- Start the Next.js app:
  `cd client/nextjs`
  `npm run dev`

## Database And Environment

- Confirm `client/nextjs/.env.local` is copied from `.env.local.example`.
- Confirm Supabase URL and anon key are set for Next.js.
- Confirm backend Supabase and Groq environment variables are set.
- Run `client/nextjs/supabase/migrations/001_saas_tables.sql` in Supabase SQL editor if SaaS tables are missing.
- Run `app/saas/sql/001_csv_upload_processing_summary.sql` and `app/saas/sql/002_product_extra_fields.sql` if patching an older database.

## Public Playground

- Confirm `/playground` loads demo users from the prototype API.
- Confirm Playground review simulation works.
- Confirm Playground recommendations work.

## Merchant Flow

- Confirm signup works with Supabase Auth.
- Confirm login routes users with organisations to `/dashboard`.
- Confirm new users without organisations route to `/onboarding`.
- Confirm sample review CSV upload works and polling completes.
- Confirm dashboard shows generated personas.
- Confirm customer profile pages render analyst-style persona briefings.

## Product Launch Simulator

- Confirm optional product catalog CSV upload works.
- Confirm catalog products appear in the simulator dropdown.
- Confirm manual product entry works without a catalog.
- Confirm live simulation works with 3 customers by default.
- Confirm live simulation error state shows retry and sample fallback.
- Confirm "Load sample result" works instantly and is clearly labeled as sample data.
- Confirm JSON download works after results are shown.

## Visual Safety

- Open the landing page, Playground, onboarding, dashboard, customers, customer profile, upload, and simulator pages at 1280px width.
- Confirm no content overflows horizontally.
- Confirm all primary buttons and links are visible.
- Confirm no dark mode or unrelated pages appear in the demo flow.
