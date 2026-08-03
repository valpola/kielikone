# Supabase results backend

Replaces the Google Sheets endpoint for quiz results. Motivation: Apps Script
writes were succeeding while the *response* was lost (verified: rows reported as
`HTTP 404` / `timed out` were present in the sheet), so every retry appended a
duplicate — a batch of 10 answers produced 11 duplicate rows. A
`unique (client_event_id)` constraint makes the retry a no-op instead, and
`answered_at > …` replaces re-reading the whole 718 KB history.

## 1) Create the project

1. Sign up at supabase.com (free tier is far more than enough).
2. New project; pick the region nearest you (eu-north / eu-central for Finland).
3. Wait for it to provision, then open **Project Settings → API** and copy:
   - **Project URL** (`https://<ref>.supabase.co`)
   - **anon public** key (this one is safe to publish; access is controlled by RLS)

## 2) Run this in the SQL editor

Replace `APP_SECRET_HERE` with the secret in
`resources/access_keys/supabase_app_secret.txt` (gitignored).

```sql
create table public.results (
  id              bigserial primary key,
  client_event_id text        not null unique,
  word_id         text        not null,
  mode            text        not null,
  correct         boolean     not null,
  answered_at     timestamptz not null,
  created_at      timestamptz not null default now()
);

create index results_answered_at_idx on public.results (answered_at);

alter table public.results enable row level security;

-- The anon key is public, so the app must also present a secret header.
-- It is entered once in the app and kept in localStorage, never in the repo.
create policy results_insert on public.results
  for insert to anon
  with check (
    current_setting('request.headers', true)::json->>'x-app-secret' = 'APP_SECRET_HERE'
  );

create policy results_select on public.results
  for select to anon
  using (
    current_setting('request.headers', true)::json->>'x-app-secret' = 'APP_SECRET_HERE'
  );
```

## Correcting mistakes

Making the log strictly append-only was the wrong call: mis-grades happen (wrong
button), and they used to be fixed by editing the sheet. So a delete policy is
needed as well — run this too:

```sql
create policy results_delete on public.results
  for delete to anon
  using (
    current_setting('request.headers', true)::json->>'x-app-secret'
      = 'APP_SECRET_HERE'
    and answered_at > now() - interval '7 days'
  );
```

The 7-day window is a deliberate compromise: recent mistakes are fixable from
the app, while a leaked secret still cannot erase years of history. Anything
older remains editable from the dashboard, exactly as the sheet was.

**A PostgREST trap worth knowing:** a `DELETE` that matches no rows — including
when *no policy permits it* — returns `204`, as though it had worked. Always send
`Prefer: return=representation` and count the returned rows. The app does this;
a bare status check reported false success during testing.

## 3) Tell me the Project URL + anon key

I then: verify the policies with curl, import the existing history, switch the
client over, and repoint `scripts/stats_analysis.py`.

## How duplicates become impossible

Inserts are sent with `Prefer: resolution=ignore-duplicates`, so a retry of an
event that already landed hits the unique constraint and is ignored — success is
reported, no second row. The client already generates `client_event_id` for every
answer; the Sheets script simply discarded it.
