#!/usr/bin/env python3
"""Print vocab-comment issues filed from the quiz app.

Comments are filed as GitHub issues on the public kielikone repo (title prefix
"[note]", label "vocab-comment"). The repo is public, so no auth is needed to
read them.

Usage:
  python3 scripts/fetch_comments.py            # open (unhandled) comments
  python3 scripts/fetch_comments.py --all       # include closed (handled) ones
  python3 scripts/fetch_comments.py --json       # raw JSON
"""
import json
import sys
import urllib.request

REPO = "valpola/kielikone"
TITLE_PREFIX = "[note]"


def fetch_issues(state):
    issues = []
    page = 1
    while True:
        url = (
            f"https://api.github.com/repos/{REPO}/issues"
            f"?state={state}&per_page=100&page={page}"
        )
        req = urllib.request.Request(
            url,
            headers={
                "Accept": "application/vnd.github+json",
                "User-Agent": "kielikone-comments",
            },
        )
        with urllib.request.urlopen(req, timeout=30) as resp:
            batch = json.loads(resp.read().decode())
        if not batch:
            break
        issues.extend(batch)
        if len(batch) < 100:
            break
        page += 1
    # drop PRs (the issues endpoint includes them) and non-comment issues; also
    # filter on each issue's own state, since the list endpoint can lag briefly
    # after a close and still return a just-closed issue for state=open.
    return [
        i
        for i in issues
        if "pull_request" not in i
        and str(i.get("title", "")).startswith(TITLE_PREFIX)
        and (state == "all" or i.get("state") == state)
    ]


def main():
    state = "all" if "--all" in sys.argv else "open"
    issues = fetch_issues(state)
    if "--json" in sys.argv:
        print(json.dumps(issues, ensure_ascii=False, indent=2))
        return
    if not issues:
        print(f"No {state} vocab comments.")
        return
    print(f"{len(issues)} {state} comment(s):\n")
    for i in issues:
        print(f"#{i['number']}  [{i['state']}]  {i['created_at']}")
        print(f"  {i['title']}")
        for line in str(i.get("body") or "").splitlines():
            print(f"    {line}")
        print(f"  {i['html_url']}\n")
    # Repeated at the end on purpose. GitHub lists newest first, so piping this
    # through `tail` hides the most recent notes — which is how six of them went
    # unread while the count at the top scrolled away.
    print(f"— {len(issues)} {state} comment(s): {', '.join('#'+str(i['number']) for i in issues)}")


if __name__ == "__main__":
    main()
