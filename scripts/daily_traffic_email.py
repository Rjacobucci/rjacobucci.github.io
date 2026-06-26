#!/usr/bin/env python3
"""
Pull yesterday's traffic from GoatCounter and email a short summary.
Run by GitHub Actions on a daily schedule (.github/workflows/daily-traffic-email.yml).

Note: GoatCounter reports *visits* (sessions); it has no separate
unique-visitor metric in /stats/total. See https://www.goatcounter.com/help/sessions

GoatCounter's stats endpoints expect start/end as date-times rounded to the hour,
and treat the range as half-open [start, end). We therefore query a single day as
[day 00:00Z, next-day 00:00Z) rather than start == end (a zero-width range, which
can 404).

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
        headers={"Authorization": f"Bearer {token}"},
        timeout=20,
    )
    if not r.ok:  # surface the response body to make failures diagnosable
        raise requests.HTTPError(
            f"{r.status_code} {r.reason} for {r.url}\n{r.text[:500]}", response=r)
    return r.json()


def visits(code: str, token: str, start: date, end: date) -> int:
    """Total visits over the half-open range [start 00:00Z, end 00:00Z)."""
    data = api_get(code, token, "stats/total",
                   {"start": iso_hour(start), "end": iso_hour(end)})
    return data.get("total", 0)


def top_pages(code: str, token: str, start: date, end: date, n: int = 5) -> list:
    """[(path, visits), ...] over the half-open range [start, end)."""
    data = api_get(code, token, "stats/hits",
                   {"start": iso_hour(start), "end": iso_hour(end), "limit": n})
    return [(h.get("path", "?"), h.get("count", 0)) for h in data.get("hits", [])]


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
    today     = date.today()              # exclusive end of "yesterday"
    week_ago  = yesterday - timedelta(days=6)

    # Fetch each metric independently so one bad call doesn't sink the report.
    errors = []
    def safe(fn, default):
        try:
            return fn()
        except requests.RequestException as e:
            errors.append(str(e))
            return default

    v_day  = safe(lambda: visits(code, token, yesterday, today), None)
    v_week = safe(lambda: visits(code, token, week_ago, today), None)
    pages  = safe(lambda: top_pages(code, token, yesterday, today), [])

    if v_day is None and v_week is None:
        body = ("GoatCounter API calls failed:\n" + "\n\n".join(errors) +
                f"\n\nGenerated at {datetime.now(timezone.utc).isoformat()}")
        send_email(user, pw, to, "[rjacobucci.com] traffic report — API error", body)
        return 0  # don't fail the workflow

    fmt = lambda v: "  n/a" if v is None else f"{v:>5}"
    subject = f"[rjacobucci.com] {yesterday:%a %b %d}: {v_day if v_day is not None else '?'} visits"
    lines = [
        f"Traffic for {yesterday:%A, %B %d, %Y} (UTC):",
        f"  Visits yesterday:  {fmt(v_day)}",
        f"  Visits last 7 days:{fmt(v_week)}",
        "",
    ]
    if pages:
        lines.append("Top pages yesterday:")
        lines += [f"  {count:>4}  {path}" for path, count in pages]
        lines.append("")
    if errors:
        lines += ["Note: some metrics could not be fetched:", *errors, ""]
    lines += [f"Dashboard: https://{code}.goatcounter.com",
              f"Generated: {datetime.now(timezone.utc).isoformat()}"]
    send_email(user, pw, to, subject, "\n".join(lines))
    print(f"[ok] emailed to {to}: {subject}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
