#!/usr/bin/env python3
"""
Pull yesterday's traffic from GoatCounter and email a one-line summary.
Designed to be run by GitHub Actions on a daily schedule.

Required env vars:
  GOATCOUNTER_CODE        e.g. "jacobucci" (subdomain at *.goatcounter.com)
  GOATCOUNTER_API_TOKEN   API token from GoatCounter (Settings -> API)
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


def env(name: str) -> str:
    val = os.environ.get(name)
    if not val:
        print(f"[fatal] env var {name} not set")
        sys.exit(1)
    return val


def fetch_yesterday(code: str, token: str) -> dict:
    """Return dict with pageviews + visitors for yesterday (UTC)."""
    yesterday = date.today() - timedelta(days=1)
    start = yesterday.isoformat()
    end = yesterday.isoformat()
    url = f"https://{code}.goatcounter.com/api/v0/stats/total"
    r = requests.get(
        url,
        params={"start": start, "end": end},
        headers={"Authorization": f"Bearer {token}"},
        timeout=20,
    )
    r.raise_for_status()
    data = r.json()
    return {
        "date": yesterday,
        "pageviews": data.get("total", 0),
        "visitors": data.get("total_unique", 0),
    }


def fetch_recent(code: str, token: str, days: int = 7) -> dict:
    """Return dict with last-N-day totals for context."""
    end = date.today() - timedelta(days=1)
    start = end - timedelta(days=days - 1)
    url = f"https://{code}.goatcounter.com/api/v0/stats/total"
    r = requests.get(
        url,
        params={"start": start.isoformat(), "end": end.isoformat()},
        headers={"Authorization": f"Bearer {token}"},
        timeout=20,
    )
    r.raise_for_status()
    data = r.json()
    return {
        "days": days,
        "pageviews": data.get("total", 0),
        "visitors": data.get("total_unique", 0),
    }


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

    try:
        y = fetch_yesterday(code, token)
        w = fetch_recent(code, token, 7)
    except requests.RequestException as e:
        body = f"GoatCounter API call failed: {e}\nGenerated at {datetime.now(timezone.utc).isoformat()}"
        send_email(user, pw, to, "[rjacobucci.com] traffic report — API error", body)
        return 0  # don't fail the workflow

    subject = f"[rjacobucci.com] {y['date']:%a %b %d}: {y['visitors']} visitors / {y['pageviews']} pageviews"
    body = (
        f"Traffic for {y['date']:%A, %B %d, %Y} (UTC):\n"
        f"  Visitors:  {y['visitors']:>4}\n"
        f"  Pageviews: {y['pageviews']:>4}\n"
        f"\n"
        f"Last 7 days:\n"
        f"  Visitors:  {w['visitors']:>4}\n"
        f"  Pageviews: {w['pageviews']:>4}\n"
        f"\n"
        f"Dashboard: https://{code}.goatcounter.com\n"
        f"Generated: {datetime.now(timezone.utc).isoformat()}\n"
    )
    send_email(user, pw, to, subject, body)
    print(f"[ok] emailed to {to}: {subject}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
