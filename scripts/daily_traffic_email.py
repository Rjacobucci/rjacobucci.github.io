#!/usr/bin/env python3
"""
Email site-wide visitor sessions and a separate page-visit breakdown.
Run by GitHub Actions on a daily schedule (.github/workflows/daily-traffic-email.yml).

Every page sends the same __sitewide_session event. With GoatCounter's
Sessions setting enabled, this event is counted once per visitor session
across the site. No persistent browser identifier is added. A returning
visitor can start a new session; this is not a count of distinct people.

Report the latest 24 and 168 complete UTC hours, not yesterday's calendar
date. GoatCounter includes both endpoint hours, so send end minus one hour.
Session totals always filter to the shared event; never substitute the sum
of page visits. Exclude the shared event from the top-page breakdown.
New session data begins at deployment and cannot be backfilled.

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
from datetime import datetime, timedelta, timezone
from email.message import EmailMessage
from time import sleep

import requests
from requests.adapters import HTTPAdapter
from urllib3.util.retry import Retry

SITEWIDE_SESSION_EVENT = "__sitewide_session"

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


def iso_hour(value: datetime) -> str:
    """Format an explicit, hour-aligned UTC instant without dropping its hour."""
    if value.utcoffset() is None:
        raise ValueError("Report times must include a timezone")
    value = value.astimezone(timezone.utc)
    if value.minute or value.second or value.microsecond:
        raise ValueError("Report times must be rounded to the hour")
    return value.strftime("%Y-%m-%dT%H:%M:%SZ")


def range_params(start: datetime, end: datetime) -> dict:
    """Translate [start, end) into GoatCounter's inclusive hourly bounds."""
    start_text = iso_hour(start)
    iso_hour(end)  # Validate before subtracting the final hour.
    # Do arithmetic in UTC: local-time subtraction is ambiguous at DST folds.
    start = start.astimezone(timezone.utc)
    end = end.astimezone(timezone.utc)
    if start >= end:
        raise ValueError("Report start must be before end")
    return {"start": start_text, "end": iso_hour(end - timedelta(hours=1))}


def report_windows(now: datetime) -> tuple[datetime, datetime, datetime]:
    """Return (24-hour start, seven-day start, exclusive end)."""
    if now.utcoffset() is None:
        raise ValueError("Report times must include a timezone")
    end = now.astimezone(timezone.utc).replace(minute=0, second=0, microsecond=0)
    return end - timedelta(hours=24), end - timedelta(days=7), end


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
        if r.status_code != 404 or path not in {"paths", "stats/hits", "stats/total"} or attempt == 2:
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


def find_session_path_id(code: str, token: str) -> int | None:
    """Find the shared event, distinguishing not-yet-installed from zero visits."""
    # The docs say ID order, but paths.List.sql orders by path, path_id while
    # its cursor filters by ID. Do not require increasing IDs or advance that
    # cursor: doing so can skip the counter on a larger site.
    # https://github.com/arp242/goatcounter/blob/main/db/query/paths.List.sql
    data = api_get(code, token, "paths", {"limit": 200, "after": 0})
    if "paths" not in data or type(data.get("more")) is not bool:
        raise requests.RequestException("GoatCounter returned an invalid path list")
    paths = data["paths"]
    if paths is None:
        paths = []
    if not isinstance(paths, list) or (not paths and data["more"]):
        raise requests.RequestException("GoatCounter returned an invalid path list")
    seen = set()
    session_id = None
    for path in paths:
        if (not isinstance(path, dict) or type(path.get("id")) is not int
                or path["id"] <= 0 or not isinstance(path.get("path"), str)):
            raise requests.RequestException("GoatCounter returned an invalid path record")
        if path["id"] in seen:
            raise requests.RequestException("GoatCounter returned a repeated path ID")
        seen.add(path["id"])
        if path["path"] == SITEWIDE_SESSION_EVENT:
            if path.get("event") is not True:
                raise requests.RequestException("The site-wide session counter is not an event")
            if session_id is not None:
                raise requests.RequestException("GoatCounter returned multiple session counters")
            session_id = path["id"]
    if session_id is not None or not data["more"]:
        return session_id

    # A truncated list cannot establish that the event is absent. Resolve it
    # by exact name using recent hits instead. The API's default date range
    # includes the current hour, allowing discovery just after installation.
    # This query discovers an ID only; report totals still use explicit ranges.
    sleep(0.3)
    data = api_get(code, token, "stats/hits", {
        "path_by_name": "true", "include_paths": SITEWIDE_SESSION_EVENT, "limit": 1,
    })
    if "hits" not in data or data.get("more") is not False:
        raise requests.RequestException("GoatCounter returned an invalid session lookup")
    hits = data["hits"]
    if hits is None:
        hits = []
    if not isinstance(hits, list) or len(hits) > 1:
        raise requests.RequestException("GoatCounter returned an invalid session lookup")
    if not hits:
        if not valid_count(data.get("total")) or data["total"] != 0:
            raise requests.RequestException("GoatCounter returned an inconsistent session lookup")
        raise requests.RequestException(
            "Could not verify the site-wide session counter: the path list is truncated "
            "and the counter has no recent recorded sessions. This is not a zero count.")
    hit = hits[0]
    if (not isinstance(hit, dict) or hit.get("path") != SITEWIDE_SESSION_EVENT
            or hit.get("event") is not True or type(hit.get("path_id")) is not int
            or hit["path_id"] <= 0 or not valid_count(hit.get("count"))):
        raise requests.RequestException("GoatCounter returned an invalid session lookup")
    return hit["path_id"]


def hit_summary(code: str, token: str, start: datetime, end: datetime,
                top_n: int = 5, *, include_path_id: int | None = None) -> tuple[int, list]:
    """Fetch one event's count, or page visits with the shared counter excluded."""
    if include_path_id is not None and (not valid_count(include_path_id) or include_path_id == 0):
        raise ValueError("A positive path ID is required")
    excluded_path_ids = []
    seen_path_ids = set()
    hits = []
    total = 0

    while True:
        params = {**range_params(start, end), "limit": 100}
        if include_path_id is not None:
            params["include_paths"] = str(include_path_id)
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
            if include_path_id is not None and hit["path_id"] != include_path_id:
                raise requests.RequestException("GoatCounter returned an unrequested path")
            seen_path_ids.add(hit["path_id"])
        visible_batch = [h for h in batch
                         if include_path_id is not None or h["path"] != SITEWIDE_SESSION_EVENT]
        hits.extend(visible_batch)
        # Use the exact same counts displayed for top pages. The API's summary
        # total can differ with chart/timezone settings; path counts are the
        # database counts for the requested interval.
        total += sum(h["count"] for h in visible_batch)

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


def period_summary(code: str, token: str, start: datetime, end: datetime,
                   *, include_path_id: int) -> PeriodSummary:
    """Return only the shared event's session count, never global page totals."""
    try:
        total, pages = hit_summary(code, token, start, end, include_path_id=include_path_id)
        return PeriodSummary(total, pages)
    except requests.RequestException as error:
        if error.response is None or error.response.status_code != 404:
            return PeriodSummary(error=str(error))
        hits_error = str(error)

    # The separately documented totals route does not depend on page-list
    # pagination. A successful fallback cannot provide top-page rankings.
    try:
        params = {**range_params(start, end), "include_paths": str(include_path_id)}
        data = api_get(code, token, "stats/total", params)
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

    generated = datetime.now(timezone.utc)
    day_start, week_start, end = report_windows(generated)
    try:
        session_id = find_session_path_id(code, token)
        if session_id is None:
            raise requests.RequestException(
                "Site-wide session tracking has not recorded its first event. "
                "Publish the updated website and allow new visits to be collected; "
                "historical page totals cannot be converted into visitor sessions.")
    except requests.RequestException as error:
        day = PeriodSummary(error=str(error))
        week = PeriodSummary(error=str(error))
    else:
        sleep(0.3)
        day = period_summary(code, token, day_start, end, include_path_id=session_id)
        sleep(0.3)
        week = period_summary(code, token, week_start, end, include_path_id=session_id)

    # Page visits are a different metric and remain useful if the session
    # counter is not yet published or either of its requests fails.
    sleep(0.3)
    try:
        page_total, pages = hit_summary(code, token, day_start, end)
        page_summary = PeriodSummary(page_total, pages)
    except requests.RequestException as error:
        page_summary = PeriodSummary(error=str(error))

    incomplete = day.total is None or week.total is None
    if incomplete:
        subject = "[rjacobucci.com] last 24 hours: visitor report incomplete"
    else:
        subject = f"[rjacobucci.com] {day.total} visitor sessions in the last 24 hours"

    def count_text(total):
        return "unavailable" if total is None else str(total)

    lines = [
        "Site-wide visitor sessions:",
        f"  Last 24 hours: {count_text(day.total)}",
        f"  Last 7 days:   {count_text(week.total)}",
        "",
        f"24-hour window: {day_start:%Y-%m-%d %H:%M} to {end:%Y-%m-%d %H:%M} UTC",
        f"7-day window:   {week_start:%Y-%m-%d %H:%M} to {end:%Y-%m-%d %H:%M} UTC",
        "Windows use complete hours; the current partial hour is excluded.",
        "",
    ]
    if page_summary.pages:
        lines.append("Top pages / events in the 24-hour window (page/event visits, not visitors):")
        lines += [f"  {count:>4}  {path}" for path, count in page_summary.pages]
        lines.append("")
    elif page_summary.pages is None:
        lines += ["Top pages / events: unavailable from GoatCounter.", ""]
    if incomplete:
        lines += ["Unavailable counts are not zero visitor sessions.", ""]
    for label, summary in [("Last 24 hours", day), ("Last 7 days", week),
                           ("Top pages / events", page_summary)]:
        if summary.error:
            lines += [f"{label}: {summary.error}", ""]
    lines += [f"Dashboard: https://{code}.goatcounter.com",
              "",
              "A session browsing several pages counts once. These are sessions first recorded",
              "in each window, not distinct people or every session active during that window.",
              "GoatCounter's session recognition expires after roughly 8 hours of inactivity;",
              "a later return may count again. Keep GoatCounter's Sessions setting enabled.",
              "",
              "This metric starts when the updated website is published; no historical backfill.",
              "Allow 24 hours for a full daily window and 7 days for a full weekly window.",
              f"Generated: {generated.isoformat()}"]
    send_email(user, pw, to, subject, "\n".join(lines))
    print(f"[ok] emailed to {to}: {subject}")
    return 1 if incomplete else 0


if __name__ == "__main__":
    sys.exit(main())
