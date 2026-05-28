#!/usr/bin/env python3
"""
Fallback citation fetcher: Semantic Scholar API + Scholar scrape (last resort).
Soft-fails (exit 0) when nothing is found, so the workflow doesn't emit a red X.
"""
import os
import re
import sys
import time
from datetime import datetime

import requests
from bs4 import BeautifulSoup

# Reuse the targets / sync logic from the primary script
from update_citations_scholar import SYNC_TARGETS, sync_files, current_count_from_config

AUTHOR_NAME = "Ross Jacobucci"
SCHOLAR_ID  = "K7_cclwAAAAJ"


def from_semantic_scholar(name: str) -> int | None:
    try:
        r = requests.get(
            "https://api.semanticscholar.org/graph/v1/author/search",
            params={"query": name, "limit": 5},
            timeout=30,
        )
        r.raise_for_status()
        data = r.json().get("data") or []
        if not data:
            return None
        author_id = data[0]["authorId"]
        r = requests.get(
            f"https://api.semanticscholar.org/graph/v1/author/{author_id}",
            params={"fields": "name,citationCount"},
            timeout=30,
        )
        r.raise_for_status()
        return int(r.json().get("citationCount") or 0) or None
    except Exception as e:
        print(f"[semantic] error: {e}")
        return None


def from_scholar_scrape(scholar_id: str) -> int | None:
    url = f"https://scholar.google.com/citations?user={scholar_id}&hl=en"
    headers = {
        "User-Agent": "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) "
                      "AppleWebKit/537.36 (KHTML, like Gecko) Chrome/121.0.0.0 Safari/537.36"
    }
    try:
        time.sleep(3)
        r = requests.get(url, headers=headers, timeout=30)
        if r.status_code != 200:
            print(f"[scrape] status {r.status_code}")
            return None
        soup = BeautifulSoup(r.text, "html.parser")
        cells = soup.select("table#gsc_rsb_st td.gsc_rsb_std")
        if cells:
            txt = cells[0].get_text(strip=True).replace(",", "")
            return int(txt) if txt.isdigit() else None
    except Exception as e:
        print(f"[scrape] error: {e}")
    return None


def main() -> int:
    print(f"[main] {datetime.now().isoformat()} fallback citation fetch")
    current = current_count_from_config()
    print(f"[main] current count in _config.yml: {current:,}")

    sources = [
        ("Semantic Scholar", lambda: from_semantic_scholar(AUTHOR_NAME)),
        ("Google Scholar scrape", lambda: from_scholar_scrape(SCHOLAR_ID)),
    ]
    best = None
    for label, fn in sources:
        print(f"[main] trying {label}...")
        try:
            v = fn()
            if v:
                print(f"[main]   -> {v:,}")
                # Take the largest credible number across sources
                if best is None or v > best:
                    best = v
        except Exception as e:
            print(f"[main]   error: {e}")

    if not best:
        print("[main] no count from any source; soft-fail (exit 0).")
        return 0

    if best < current:
        print(f"[main] best ({best:,}) < current ({current:,}); skipping.")
        return 0

    changed = sync_files(best)
    print(f"[main] changed: {changed}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
