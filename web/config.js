const APP_CONFIG = {
  // Results are stored in Supabase (Postgres + PostgREST). The publishable key
  // is public by design; access is granted by the row-level security policies,
  // which additionally require the app secret entered once in the app and kept
  // in localStorage. unique(client_event_id) makes a retried write a no-op, so
  // a lost response can no longer produce a duplicate row.
  supabaseUrl: "https://fzlztsasmovicflapqvw.supabase.co",
  supabaseKey: "sb_publishable_vYave1hiR297p0q4eTAaQQ_Q2BpwZoE",
  // Legacy Google Sheets endpoint. No longer written to or read by the app;
  // kept so scripts/migrate_results_to_supabase.py can still reach the archive.
  resultsEndpoint:
    "https://script.google.com/macros/s/AKfycbzqqBARcy912PQ_65gQosYS1kqbTzY0thxbS5h4XHzsbXLeMe1v9WV1FxpVUvI8ZQQW/exec",
  // Comments are filed as GitHub issues on this repo (public), labelled below.
  // The write token is entered once in-app and kept in localStorage only.
  commentRepo: "valpola/kielikone",
  commentLabel: "vocab-comment",
  cacheBust: "20260803-7",
};
