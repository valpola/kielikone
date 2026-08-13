#!/usr/bin/env python3
"""Integration test for the sync path, against the real Supabase project.

Runs as the **test** user, whose secret is in
resources/access_keys/supabase_test_secret.txt (gitignored). Row-level security
keeps that user's rows separate from anyone else's, so this never touches real
practice history — and the test refuses to run if the secret does not resolve to
the test user, so a misplaced production secret cannot make it write real rows.

Covers the things that actually went wrong in production and that the offline
tests cannot reach: duplicate suppression, incremental reads, and the delete that
reports success when it deleted nothing.

Skips cleanly when the secret is absent or the network is down, so it is safe in
`make test`.
"""

import json
import sys
import urllib.error
import urllib.request
from datetime import UTC, datetime, timedelta
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
KEYS = ROOT / "resources" / "access_keys"
MARKER = "selftest-sync"  # word_id used for every row this test creates

failures: list[str] = []


def skip(reason: str) -> int:
    print(f"SKIP  supabase sync test: {reason}")
    return 0


def check(name: str, ok: bool, detail: str = "") -> None:
    if ok:
        print(f"  ok    {name}")
    else:
        failures.append(f"  FAIL  {name}" + (f"\n        {detail}" if detail else ""))


def read(path: Path) -> str:
    return path.read_text(encoding="utf-8").strip() if path.exists() else ""


class Client:
    def __init__(self, url: str, anon: str, secret: str) -> None:
        self.url = url.rstrip("/")
        self.headers = {
            "apikey": anon,
            "Authorization": f"Bearer {anon}",
            "x-app-secret": secret,
            "Content-Type": "application/json",
        }

    def call(self, method: str, path: str, body=None, extra: dict | None = None):
        request = urllib.request.Request(
            self.url + path,
            method=method,
            data=json.dumps(body).encode() if body is not None else None,
            headers={**self.headers, **(extra or {})},
        )
        with urllib.request.urlopen(request, timeout=30) as response:
            raw = response.read().decode().strip()
            # lower-cased: PostgREST sends "Content-Range", and a plain dict would
            # otherwise make the lookup case-sensitive
            headers = {key.lower(): value for key, value in response.headers.items()}
            return response.status, headers, (json.loads(raw) if raw else None)


def main() -> int:
    url, anon, secret = (
        read(KEYS / "supabase_url.txt"),
        read(KEYS / "supabase_anon_key.txt"),
        read(KEYS / "supabase_test_secret.txt"),
    )
    if not (url and anon and secret):
        return skip("no test credentials in resources/access_keys/")

    client = Client(url, anon, secret)
    try:
        _, _, who = client.call("POST", "/rest/v1/rpc/current_app_user", {})
    except urllib.error.URLError as error:
        return skip(f"cannot reach Supabase ({error.reason})")

    # Refuse to write unless this really is the test user.
    if who != "test":
        return skip(f"secret resolves to {who!r}, not the test user — refusing to write")
    print(f"Running as {who!r} against {url}\n")

    def purge() -> None:
        client.call(
            "DELETE",
            f"/rest/v1/results?word_id=eq.{MARKER}",
            extra={"Prefer": "return=representation"},
        )

    purge()
    stamp = datetime.now(UTC).replace(microsecond=0)
    older = (stamp - timedelta(hours=2)).isoformat()
    newer = stamp.isoformat()
    event_id = f"{MARKER}-{stamp.timestamp():.0f}"

    def post(client_event_id: str, answered_at: str, correct: bool = True):
        return client.call(
            "POST",
            "/rest/v1/results?on_conflict=client_event_id",
            {
                "client_event_id": client_event_id,
                "word_id": MARKER,
                "mode": "en-tr",
                "correct": correct,
                "answered_at": answered_at,
            },
            extra={"Prefer": "resolution=ignore-duplicates,return=minimal"},
        )

    def count() -> int:
        _, headers, _ = client.call(
            "GET",
            f"/rest/v1/results?select=id&word_id=eq.{MARKER}",
            extra={"Range-Unit": "items", "Range": "0-0", "Prefer": "count=exact"},
        )
        return int(headers.get("content-range", "*/0").split("/")[-1])

    try:
        post(event_id, older)
        check("an answer can be written", count() == 1, f"count={count()}")

        # The duplicate bug: a retry whose response was lost must not add a row.
        post(event_id, older)
        post(event_id, older)
        check("retrying the same client_event_id adds nothing", count() == 1, f"count={count()}")

        post(f"{event_id}-b", newer)
        check("a distinct event does add a row", count() == 2, f"count={count()}")

        # Incremental read: the app asks only for what it has not seen.
        _, _, rows = client.call(
            "GET",
            f"/rest/v1/results?select=answered_at,word_id,mode,correct&word_id=eq.{MARKER}"
            f"&answered_at=gt.{urllib.parse.quote(older)}&order=answered_at.asc",
        )
        check("an incremental read excludes what was already seen", len(rows) == 1, f"rows={rows}")

        _, _, rows = client.call(
            "GET",
            f"/rest/v1/results?select=answered_at,word_id,mode,correct&word_id=eq.{MARKER}"
            "&order=answered_at.asc",
        )
        check(
            "rows come back in the shape the app expects",
            len(rows) == 2 and set(rows[0]) == {"answered_at", "word_id", "mode", "correct"},
            f"rows={rows}",
        )

        # The incremental read keys on answered_at, so a row inserted with a
        # timestamp older than the newest one held is invisible to it — a queued
        # answer syncing late. The app notices via the row count and re-reads
        # everything; this pins the behaviour that makes that necessary.
        backdated = (stamp - timedelta(hours=6)).isoformat()
        post(f"{event_id}-late", backdated)
        _, _, missed = client.call(
            "GET",
            f"/rest/v1/results?select=answered_at&word_id=eq.{MARKER}"
            f"&answered_at=gt.{urllib.parse.quote(newer)}&order=answered_at.asc",
        )
        check(
            "a back-dated row is invisible to an incremental read",
            len(missed) == 0,
            f"rows={missed}",
        )
        check(
            "but the total reveals it, which is what triggers the full re-read",
            count() == 3,
            f"count={count()}",
        )
        _, _, everything = client.call(
            "GET",
            f"/rest/v1/results?select=answered_at&word_id=eq.{MARKER}&order=answered_at.asc",
        )
        check("a full read finds it", len(everything) == 3, f"rows={everything}")

        # A correction is a delete plus an insert, because the table grants no
        # update. That leaves the row count untouched, and the reinserted row
        # keeps its original answered_at so it stays below the incremental
        # watermark too — both of the app's other signals miss it. Only the
        # newest created_at moves, which is why the app tracks it as well. One
        # such edit stayed invisible on a real device and the practice batch kept
        # offering a word that had been answered right.
        def watermark() -> str:
            _, _, rows = client.call(
                "GET", "/rest/v1/results?select=created_at&order=created_at.desc&limit=1")
            return rows[0]["created_at"] if rows else ""

        before_count, before_mark = count(), watermark()
        _, _, gone = client.call(
            "DELETE", f"/rest/v1/results?client_event_id=eq.{event_id}-late",
            extra={"Prefer": "return=representation"})
        check("the row to correct was really removed", len(gone) == 1, f"deleted={gone}")
        old = gone[0]
        post(f"{event_id}-late", old["answered_at"], correct=True)
        check(
            "a correction leaves the row count unchanged",
            count() == before_count,
            f"before={before_count} after={count()}",
        )
        _, _, still_missed = client.call(
            "GET",
            f"/rest/v1/results?select=answered_at&word_id=eq.{MARKER}"
            f"&answered_at=gt.{urllib.parse.quote(newer)}&order=answered_at.asc",
        )
        check(
            "and stays below the incremental watermark",
            len(still_missed) == 0,
            f"rows={still_missed}",
        )
        check(
            "but the newest created_at moves, which is what reveals it",
            watermark() > before_mark,
            f"before={before_mark} after={watermark()}",
        )

        # Undo. A DELETE matching nothing also returns 204, so the app counts the
        # returned rows instead of trusting the status.
        _, _, deleted = client.call(
            "DELETE",
            f"/rest/v1/results?client_event_id=eq.{event_id}",
            extra={"Prefer": "return=representation"},
        )
        check("undo deletes the row and reports it", len(deleted or []) == 1, f"returned={deleted}")

        _, _, deleted = client.call(
            "DELETE",
            f"/rest/v1/results?client_event_id=eq.{event_id}",
            extra={"Prefer": "return=representation"},
        )
        check(
            "deleting an already-deleted row reports nothing deleted",
            len(deleted or []) == 0,
            "this is the 204-on-no-match trap: status alone would look like success",
        )

        # RLS: a wrong secret must see nothing, not everything.
        stranger = Client(url, anon, "definitely-not-a-real-secret")
        _, _, who_else = stranger.call("POST", "/rest/v1/rpc/current_app_user", {})
        _, _, visible = stranger.call("GET", "/rest/v1/results?select=id&limit=5")
        check(
            "a wrong app secret is nobody and sees nothing",
            not who_else and not visible,
            f"identity={who_else!r} rows={visible!r}",
        )
    finally:
        purge()
        check("test rows cleaned up", count() == 0)

    print()
    if failures:
        print("\n".join(failures))
        print(f"\n{len(failures)} check(s) failed.")
        return 1
    print("Supabase sync test passed.")
    return 0


if __name__ == "__main__":
    sys.exit(main())
