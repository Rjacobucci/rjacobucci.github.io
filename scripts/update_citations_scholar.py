#!/usr/bin/env python3
"""
Fetch Google Scholar citation count and sync it across _config.yml, _pages/about.md,
and _pages/publications.md.

Exit codes:
  0  - success OR soft-fail (no citation found; workflow should not be marked red)
  1  - reserved (currently unused; soft-fail policy enforced by GitHub Actions step)
"""
import os
import random
import re
import sys
import time
from datetime import datetime

import requests
from bs4 import BeautifulSoup

SCHOLAR_ID = "K7_cclwAAAAJ"
USER_AGENTS = [
    "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/121.0.0.0 Safari/537.36",
    "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/121.0.0.0 Safari/537.36",
    "Mozilla/5.0 (X11; Linux x86_64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/121.0.0.0 Safari/537.36",
    "Mozilla/5.0 (Windows NT 10.0; Win64; x64; rv:122.0) Gecko/20100101 Firefox/122.0",
]

# Files that display the citation count
SYNC_TARGETS = [
    # (path, regex with one capture group around the number, replacement template)
    ("_config.yml",
     r'(bio\s*:\s*"[^"]*?)(\d{1,3}(?:,\d{3})*|\d+)\+? citations',
     r'\g<1>{count:,}+ citations'),
    ("_pages/about.md",
     r'(\*\*)(\d{1,3}(?:,\d{3})*|\d+)(\+\*\* research citations)',
     r'\g<1>{count:,}\g<3>'),
    ("_pages/publications.md",
     r'(\*\*)(\d{1,3}(?:,\d{3})*|\d+)(\+ citations\*\*)',
     r'\g<1>{count:,}\g<3>'),
]


def fetch_scholar(scholar_id: str, max_retries: int = 3) -> int | None:
    url = f"https://scholar.google.com/citations?user={scholar_id}&hl=en"
    session = requests.Session()
    for attempt in range(1, max_retries + 1):
        headers = {
            "User-Agent": random.choice(USER_AGENTS),
            "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8",
            "Accept-Language": "en-US,en;q=0.5",
            "Connection": "keep-alive",
        }
        try:
            delay = random.uniform(3, 7)
            print(f"[scholar] attempt {attempt} after {delay:.1f}s delay")
            time.sleep(delay)
            r = session.get(url, headers=headers, timeout=30)
            print(f"[scholar] status {r.status_code}")
            if r.status_code == 429:
                time.sleep(30)
                continue
            r.raise_for_status()
            soup = BeautifulSoup(r.text, "html.parser")
            cells = soup.select("table#gsc_rsb_st td.gsc_rsb_std")
            if cells:
                txt = cells[0].get_text(strip=True).replace(",", "")
                if txt.isdigit():
                    return int(txt)
        except requests.RequestException as e:
            print(f"[scholar] request error: {e}")
            time.sleep(attempt * 10)
        except Exception as e:
            print(f"[scholar] unexpected error: {e}")
    return None


def current_count_from_config(path: str = "_config.yml") -> int:
    with open(path, encoding="utf-8") as f:
        c = f.read()
    m = re.search(r'bio\s*:\s*"[^"]*?(\d{1,3}(?:,\d{3})*|\d+)\+? citations', c)
    return int(m.group(1).replace(",", "")) if m else 0


def sync_files(new_count: int) -> list[str]:
    """Update every target file. Returns list of changed paths."""
    changed = []
    for path, pattern, repl_tmpl in SYNC_TARGETS:
        if not os.path.exists(path):
            print(f"[sync] missing: {path}")
            continue
        with open(path, encoding="utf-8") as f:
            old = f.read()
        new = re.sub(pattern, repl_tmpl.format(count=new_count), old)
        if new != old:
            with open(path, "w", encoding="utf-8") as f:
                f.write(new)
            changed.append(path)
            print(f"[sync] updated {path}")
        else:
            print(f"[sync] no change in {path}")
    return changed


def main() -> int:
    print(f"[main] {datetime.now().isoformat()} scholar_id={SCHOLAR_ID}")
    current = current_count_from_config()
    print(f"[main] current count in _config.yml: {current:,}")

    new_count = fetch_scholar(SCHOLAR_ID)
    if not new_count:
        print("[main] no count fetched; soft-fail (exit 0).")
        return 0

    print(f"[main] fetched {new_count:,} citations")

    # Only update when the new number is at least as large as the current one.
    # Scholar can briefly under-report; ignore decreases.
    if new_count < current:
        print(f"[main] fetched count is lower than current ({current:,}); skipping.")
        return 0

    changed = sync_files(new_count)
    print(f"[main] changed: {changed}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
