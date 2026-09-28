#!/usr/bin/env python3
"""
Pull yesterday's traffic from GoatCounter and email a short summary.
Run by GitHub Actions on a daily schedule (.github/workflows/daily-traffic-email.yml).

Fetch yesterday and the previous seven complete UTC days independently.
Counts are page or event visits, not unique people across the whole site.
See https://www.goatcounter.com/help/sessions for the counting definition.
The API includes both endpoint hours, so an exclusive midnight end is sent
as the preceding 23:00 hour. Paginated page counts provide both the total
and top pages; /stats/total is a fallback if the page-list route returns 404.
An unavailable count is never reported as zero.

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
from dataclasses import dataclass
from datetime import date, datetime, timedelta, timezone
from email.message import EmailMessage
from time import sleep

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
    if val:
        val = val.strip()
    if not val:
        print(f"[fatal] env var {name} not set")
        sys.exit(1)
    return val


def iso_hour(d: date) -> str:
    """Midnight UTC of `d` as an hour-rounded RFC3339 timestamp."""
    return datetime(d.year, d.month, d.day, tzinfo=timezone.utc).strftime(
        "%Y-%m-%dT%H:%M:%SZ")


def range_params(start: date, end: date) -> dict:
    """Translate [start, end) into GoatCounter's inclusive hourly bounds."""
    if start >= end:
        raise ValueError("Report start must be before end")
    last_hour = datetime(end.year, end.month, end.day, tzinfo=timezone.utc) - timedelta(hours=1)
    return {"start": iso_hour(start), "end": last_hour.strftime("%Y-%m-%dT%H:%M:%SZ")}


def api_get(code: str, token: str, path: str, params: dict) -> dict:
    # These documented routes have returned unexpected 404s. Retry briefly,
    # but retain a persistent 404 as an error, never as an empty traffic day.
    for attempt in range(3):
        r = SESSION.get(
            f"https://{code}.goatcounter.com/api/v0/{path}",
            params=params,
            headers={"Authorization": f"Bearer {token}",
                     "Content-Type": "application/json",
                     "Accept": "application/json"},
            timeout=20,
        )
        if r.status_code != 404 or path not in {"stats/hits", "stats/total"} or attempt == 2:
            break
        sleep(2 ** attempt)
    if not r.ok:  # surface the response body to make failures diagnosable
        raise requests.HTTPError(
            f"{r.status_code} {r.reason} for {r.url}\n{r.text[:300]}", response=r)
    data = r.json()
    if not isinstance(data, dict):
        raise requests.RequestException("GoatCounter returned an invalid response object")
    return data


def valid_count(value) -> bool:
    return type(value) is int and value >= 0


def hit_summary(code: str, token: str, start: date, end: date,
                top_n: int = 5) -> tuple[int, list]:
    """Return (total visits, top pages) over the half-open range [start, end)."""
    excluded_path_ids = []
    seen_path_ids = set()
    hits = []
    total = 0

    while True:
        params = {**range_params(start, end), "limit": 100}
        if excluded_path_ids:
            params["exclude_paths"] = ",".join(map(str, excluded_path_ids))

        data = api_get(code, token, "stats/hits", params)
        if "hits" not in data or type(data.get("more")) is not bool:
            raise requests.RequestException("GoatCounter returned an invalid page-list response")
        batch = data["hits"]
        # Go encodes a nil slice as null when there are no results.
        if batch is None:
            batch = []
        if not isinstance(batch, list):
            raise requests.RequestException("GoatCounter returned an invalid page list")
        if not batch and (not valid_count(data.get("total"))
                          or data["total"] != 0 or data["more"]):
            raise requests.RequestException("GoatCounter returned an inconsistent empty page list")
        for hit in batch:
            if (not isinstance(hit, dict) or not isinstance(hit.get("path"), str)
                    or not valid_count(hit.get("count"))
                    or type(hit.get("path_id")) is not int or hit["path_id"] <= 0):
                raise requests.RequestException("GoatCounter returned an invalid page count")
            if hit["path_id"] in seen_path_ids:
                raise requests.RequestException("GoatCounter pagination returned a repeated path")
            seen_path_ids.add(hit["path_id"])
        hits.extend(batch)
        # Use the exact same counts displayed for top pages. The API's summary
        # total can differ with chart/timezone settings; path counts are the
        # database counts for the requested interval.
        total += sum(h["count"] for h in batch)

        if not data.get("more", False):
            break

        batch_ids = [h["path_id"] for h in batch]
        if not batch_ids:
            raise requests.RequestException(
                "GoatCounter pagination indicated more results but returned no path IDs")
        excluded_path_ids.extend(batch_ids)
        sleep(0.3)  # Hosted API permits four requests per second.

    pages = sorted(
        ((h.get("path", "?"), h.get("count", 0)) for h in hits),
        key=lambda page: (-page[1], page[0]),
    )[:top_n]
    return total, pages


@dataclass
class PeriodSummary:
    total: int | None = None
    pages: list | None = None
    error: str | None = None


def period_summary(code: str, token: str, start: date, end: date) -> PeriodSummary:
    """Return verified counts, or a clearly unavailable result on failure."""
    try:
        total, pages = hit_summary(code, token, start, end)
        return PeriodSummary(total, pages)
    except requests.RequestException as error:
        if error.response is None or error.response.status_code != 404:
            return PeriodSummary(error=str(error))
        hits_error = str(error)

    # The separately documented totals route does not depend on page-list
    # pagination. A successful fallback cannot provide top-page rankings.
    try:
        data = api_get(code, token, "stats/total", range_params(start, end))
        if not valid_count(data.get("total")):
            raise requests.RequestException("GoatCounter returned an invalid total count")
        return PeriodSummary(data["total"])
    except requests.RequestException as error:
        return PeriodSummary(error=f"{hits_error}\nTotals fallback also failed: {error}")


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

    today = datetime.now(timezone.utc).date()  # exclusive end, independent of host timezone
    yesterday = today - timedelta(days=1)
    week_ago = today - timedelta(days=7)
    day = period_summary(code, token, yesterday, today)
    sleep(0.3)
    week = period_summary(code, token, week_ago, today)
    incomplete = day.total is None or week.total is None
    if incomplete:
        subject = f"[rjacobucci.com] {yesterday:%a %b %d}: traffic report incomplete"
    else:
        subject = f"[rjacobucci.com] {yesterday:%a %b %d}: {day.total} visits"

    def count_text(total):
        return "unavailable" if total is None else str(total)

    lines = [
        f"Traffic for {yesterday:%A, %B %d, %Y} (UTC):",
        f"  Visits yesterday:   {count_text(day.total)}",
        f"  Visits last 7 days: {count_text(week.total)}",
        f"  Seven-day window:   {week_ago:%Y-%m-%d} through {yesterday:%Y-%m-%d} (UTC)",
        "",
    ]
    if day.pages:
        lines.append("Top pages / events yesterday:")
        lines += [f"  {count:>4}  {path}" for path, count in day.pages]
        lines.append("")
    elif day.pages is None:
        lines += ["Top pages / events yesterday: unavailable from GoatCounter.", ""]
    if incomplete:
        lines += ["Unavailable counts are not zero visits.", ""]
    for label, summary in [("Yesterday", day), ("Last 7 days", week)]:
        if summary.error:
            lines += [f"{label}: {summary.error}", ""]
    lines += [f"Dashboard: https://{code}.goatcounter.com",
              "Visits are counted per page or tracked event, not as unique people across the site.",
              f"Generated: {datetime.now(timezone.utc).isoformat()}"]
    send_email(user, pw, to, subject, "\n".join(lines))
    print(f"[ok] emailed to {to}: {subject}")
    return 1 if incomplete else 0


if __name__ == "__main__":
    sys.exit(main())
