#!/usr/bin/env python3
"""
Pull yesterday's traffic from GoatCounter and email a short summary.
Run by GitHub Actions on a daily schedule (.github/workflows/daily-traffic-email.yml).

Note: GoatCounter reports *visits*; it has no separate unique-visitor metric.
See https://www.goatcounter.com/help/sessions

All report values come from /stats/hits. GoatCounter's /stats/total endpoint has
returned misleading 404 responses even when /stats/hits contains traffic. Using
one endpoint for totals and page rankings keeps the report internally
consistent. Results are paginated so totals include more than the first 100
paths if necessary.

Required env vars:
  GOATCOUNTER_CODE        e.g. "rjacobucci" (subdomain at *.goatcounter.com)
  GOATCOUNTER_API_TOKEN   GoatCounter API token (Settings -> API, "read statistics")
  GMAIL_USER              gmail address used to send (must have App Password)
  GMAIL_APP_PASSWORD      16-char Google App Password
  DAILY_EMAIL_TO          recipient address
"""
import os
import smtplib
import sys
from datetime import date, datetime, timedelta, timezone
from email.message import EmailMessage

import requests
from requests.adapters import HTTPAdapter
from urllib3.util.retry import Retry

SESSION = requests.Session()
SESSION.mount("https://", HTTPAdapter(max_retries=Retry(
    total=4, connect=4, read=4, backoff_factor=2,
    status_forcelist=[429, 500, 502, 503, 504],
    allowed_methods=["GET"])))


def env(name: str) -> str:
    val = os.environ.get(name)
    if not val:
        print(f"[fatal] env var {name} not set")
        sys.exit(1)
    return val


def iso_hour(d: date) -> str:
    """Midnight UTC of `d` as an hour-rounded RFC3339 timestamp."""
    return datetime(d.year, d.month, d.day, tzinfo=timezone.utc).strftime(
        "%Y-%m-%dT%H:%M:%SZ")


def api_get(code: str, token: str, path: str, params: dict) -> dict:
    r = SESSION.get(
        f"https://{code}.goatcounter.com/api/v0/{path}",
        params=params,
        headers={"Authorization": f"Bearer {token}",
                 "Content-Type": "application/json"},  # required by GoatCounter API
        timeout=20,
    )
    if not r.ok:  # surface the response body to make failures diagnosable
        raise requests.HTTPError(
            f"{r.status_code} {r.reason} for {r.url}\n{r.text[:300]}", response=r)
    return r.json()


def hit_summary(code: str, token: str, start: date, end: date,
                top_n: int = 5) -> tuple[int, list]:
    """Return (total visits, top pages) over the half-open range [start, end)."""
    excluded_path_ids = []
    hits = []
    total = 0

    while True:
        params = {
            "start": iso_hour(start),
            "end": iso_hour(end),
            "limit": 100,
        }
        if excluded_path_ids:
            params["exclude_paths"] = ",".join(map(str, excluded_path_ids))

        data = api_get(code, token, "stats/hits", params)
        batch = data.get("hits", [])
        hits.extend(batch)
        total += data.get("total", sum(h.get("count", 0) for h in batch))

        if not data.get("more", False):
            break

        batch_ids = [h.get("path_id") for h in batch if h.get("path_id")]
        if not batch_ids:
            raise requests.RequestException(
                "GoatCounter pagination indicated more results but returned no path IDs")
        excluded_path_ids.extend(batch_ids)

    pages = sorted(
        ((h.get("path", "?"), h.get("count", 0)) for h in hits),
        key=lambda page: (-page[1], page[0]),
    )[:top_n]
    return total, pages


def send_email(user: str, pw: str, to: str, subject: str, body: str) -> None:
    msg = EmailMessage()
    msg["Subject"] = subject
    msg["From"] = user
    msg["To"] = to
    msg.set_content(body)
    with smtplib.SMTP_SSL("smtp.gmail.com", 465, timeout=20) as s:
        s.login(user, pw)
        s.send_message(msg)


def main() -> int:
    code  = env("GOATCOUNTER_CODE")
    token = env("GOATCOUNTER_API_TOKEN")
    user  = env("GMAIL_USER")
    pw    = env("GMAIL_APP_PASSWORD")
    to    = env("DAILY_EMAIL_TO")

    yesterday = date.today() - timedelta(days=1)
    today     = date.today()              # exclusive end
    week_ago  = yesterday - timedelta(days=6)

    errors = []
    def safe(fn, default):
        try:
            return fn()
        except requests.RequestException as e:
            errors.append(str(e))
            return default

    week = safe(lambda: hit_summary(code, token, week_ago, today, top_n=0), None)
    day = safe(lambda: hit_summary(code, token, yesterday, today), None)

    if week is None or day is None:
        body = ("GoatCounter API call failed:\n" + "\n\n".join(errors) +
                f"\n\nGenerated at {datetime.now(timezone.utc).isoformat()}")
        send_email(user, pw, to, "[rjacobucci.com] traffic report — API error", body)
        return 0  # don't fail the workflow

    v_week, _ = week
    v_day, pages = day

    subject = f"[rjacobucci.com] {yesterday:%a %b %d}: {v_day} visits"
    lines = [
        f"Traffic for {yesterday:%A, %B %d, %Y} (UTC):",
        f"  Visits yesterday:  {v_day:>5}",
        f"  Visits last 7 days:{v_week:>5}",
        "",
    ]
    if pages:
        lines.append("Top pages yesterday:")
        lines += [f"  {count:>4}  {path}" for path, count in pages]
        lines.append("")
    lines += [f"Dashboard: https://{code}.goatcounter.com",
              f"Generated: {datetime.now(timezone.utc).isoformat()}"]
    send_email(user, pw, to, subject, "\n".join(lines))
    print(f"[ok] emailed to {to}: {subject}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
