-- Pronunciation audio, kept in the database rather than in the repo.
--
-- The recordings come from Google Translate's undocumented translate_tts
-- endpoint. Using them personally is one thing; publishing them from a static
-- site on GitHub Pages would be redistribution, so they must not be committed.
-- This table keeps them behind the same gate that already protects `results`.
--
-- Why a table and not Supabase Storage: Storage authorises with Supabase Auth
-- JWTs and never sees the `x-app-secret` header this app sends, so its RLS
-- cannot express "the person holding my app secret". PostgREST does see it,
-- which means an ordinary table reuses the existing login with no new
-- machinery — no Edge Function, no service key in the client.
--
-- Size: ~2000 clips, mean 8.4 KB, ~23 MB once base64-encoded. The client
-- fetches one word at a time and caches it on the device, so a phone only ever
-- downloads the words it actually meets.
--
-- Run this in the Supabase SQL editor. Check the two policies against the ones
-- on `results` first and match them — the helper is named here as
-- current_app_user() because that is the RPC the app already calls, but the
-- existing policies are the authority on how a request is identified.

create table if not exists public.pron_audio (
  word        text primary key,
  mp3_b64     text        not null,
  engine      text        not null default 'google',
  created_at  timestamptz not null default now()
);

alter table public.pron_audio enable row level security;

-- Read: anyone holding a valid app secret. Without one this returns nothing,
-- and the app falls back to speaking the word with the device's own voice.
create policy pron_audio_select on public.pron_audio
  for select
  using (public.current_app_user() is not null);

-- Write: the same gate, so scripts/upload_pron_audio.py can fill the table
-- using the anon key plus the app secret, exactly as the quiz posts results.
create policy pron_audio_insert on public.pron_audio
  for insert
  with check (public.current_app_user() is not null);
