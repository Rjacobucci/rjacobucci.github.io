import json
import smtplib
import unittest
from datetime import date, datetime, timezone
from unittest.mock import call, patch

import requests

from scripts import daily_traffic_email as report


def response(status=200, payload=None):
    result = requests.Response()
    result.status_code = status
    result.reason = "OK" if status == 200 else "API error"
    result.url = "https://rjacobucci.goatcounter.com/api/v0/stats/hits"
    result._content = json.dumps(payload).encode("utf-8")
    return result


def http_error(status=404):
    return requests.HTTPError(f"HTTP {status}", response=response(status))


def hit(path_id=1, path="/", count=2):
    return {"path_id": path_id, "path": path, "count": count}


class ReportTestCase(unittest.TestCase):
    def setUp(self):
        self.start, self.end = date(2026, 9, 20), date(2026, 9, 21)
        # Guard every test against accidental network traffic.
        self.http = self.enterContext(patch.object(
            report.SESSION, "get", side_effect=AssertionError("Unexpected HTTP request")))
        self.pause = self.enterContext(patch.object(report, "sleep"))


class RangeTests(ReportTestCase):
    def test_exclusive_midnight_becomes_previous_hour(self):
        self.assertEqual(
            {"start": "2026-09-20T00:00:00Z", "end": "2026-09-20T23:00:00Z"},
            report.range_params(self.start, self.end))

    def test_week_crosses_year_without_including_next_midnight(self):
        self.assertEqual(
            {"start": "2026-12-25T00:00:00Z", "end": "2026-12-31T23:00:00Z"},
            report.range_params(date(2026, 12, 25), date(2027, 1, 1)))

    def test_leap_day(self):
        self.assertEqual("2028-02-29T23:00:00Z",
                         report.range_params(date(2028, 2, 29), date(2028, 3, 1))["end"])

    def test_empty_or_reversed_ranges_are_rejected(self):
        for start, end in [(self.start, self.start), (self.end, self.start)]:
            with self.subTest(start=start, end=end), self.assertRaises(ValueError):
                report.range_params(start, end)


class ApiGetTests(ReportTestCase):
    def test_request_preserves_auth_headers_and_range(self):
        self.http.side_effect = [response(payload={"total": 3})]
        params = report.range_params(self.start, self.end)
        self.assertEqual({"total": 3}, report.api_get("rjacobucci", "test-token", "stats/total", params))
        self.http.assert_called_once_with(
            "https://rjacobucci.goatcounter.com/api/v0/stats/total", params=params,
            headers={"Authorization": "Bearer test-token", "Content-Type": "application/json",
                     "Accept": "application/json"}, timeout=20)
        self.pause.assert_not_called()

    def test_transient_404_is_retried_on_both_statistics_routes(self):
        for route in ["stats/hits", "stats/total"]:
            with self.subTest(route=route):
                self.http.reset_mock()
                self.pause.reset_mock()
                self.http.side_effect = [response(404), response(payload={"total": 3})]
                self.assertEqual({"total": 3}, report.api_get("rjacobucci", "token", route, {}))
                self.assertEqual(2, self.http.call_count)
                self.pause.assert_called_once_with(1)

    def test_persistent_404_has_bounded_retries_and_retains_response(self):
        self.http.side_effect = [response(404), response(404), response(404)]
        with self.assertRaises(requests.HTTPError) as error:
            report.api_get("rjacobucci", "token", "stats/hits", {})
        self.assertEqual(3, self.http.call_count)
        self.assertEqual([call(1), call(2)], self.pause.call_args_list)
        self.assertEqual(404, error.exception.response.status_code)
        self.assertFalse(error.exception.response)  # Error responses are falsey.

    def test_unrelated_route_404_is_not_retried(self):
        self.http.side_effect = [response(404)]
        with self.assertRaises(requests.HTTPError):
            report.api_get("rjacobucci", "token", "me", {})
        self.http.assert_called_once()
        self.pause.assert_not_called()

    def test_client_errors_are_not_retried(self):
        for status in [400, 401, 403]:
            with self.subTest(status=status):
                self.http.reset_mock()
                self.http.side_effect = [response(status)]
                with self.assertRaises(requests.HTTPError):
                    report.api_get("rjacobucci", "token", "stats/hits", {})
                self.http.assert_called_once()
        self.pause.assert_not_called()

    def test_non_object_json_is_rejected(self):
        for payload in [None, [], 0, "not statistics"]:
            with self.subTest(payload=payload):
                self.http.side_effect = [response(payload=payload)]
                with self.assertRaises(requests.RequestException):
                    report.api_get("rjacobucci", "token", "stats/hits", {})

    def test_invalid_json_is_an_api_failure(self):
        invalid = response()
        invalid._content = b"<html>temporary failure</html>"
        self.http.side_effect = [invalid]
        with self.assertRaises(requests.RequestException):
            report.api_get("rjacobucci", "token", "stats/hits", {})


class HitSummaryTests(ReportTestCase):
    def summarize(self, payload):
        with patch.object(report, "api_get", return_value=payload):
            return report.hit_summary("rjacobucci", "token", self.start, self.end)

    def test_positive_page_counts_override_zero_summary_field(self):
        self.assertEqual((3, [("/", 2), ("/publications", 1)]), self.summarize({
            "hits": [hit(), hit(2, "/publications", 1)], "total": 0, "more": False}))

    def test_pagination_includes_all_counts_and_global_top_pages(self):
        batches = [
            {"hits": [hit(10, "/", 4), hit(11, "/publications", 1)], "total": 0, "more": True},
            {"hits": [hit(12, "/cv", 2)], "total": 0, "more": True},
            {"hits": [hit(13, "/work", 5)], "total": 0, "more": False},
        ]
        with patch.object(report, "api_get", side_effect=batches) as api_get:
            total, pages = report.hit_summary("rjacobucci", "token", self.start, self.end, top_n=2)
        self.assertEqual(12, total)
        self.assertEqual([("/work", 5), ("/", 4)], pages)
        self.assertNotIn("exclude_paths", api_get.call_args_list[0].args[3])
        self.assertEqual("10,11", api_get.call_args_list[1].args[3]["exclude_paths"])
        self.assertEqual("10,11,12", api_get.call_args_list[2].args[3]["exclude_paths"])
        for invocation in api_get.call_args_list:
            self.assertEqual("stats/hits", invocation.args[2])
            self.assertEqual("2026-09-20T23:00:00Z", invocation.args[3]["end"])
            self.assertEqual(100, invocation.args[3]["limit"])

    def test_tied_counts_sort_by_path(self):
        self.assertEqual((4, [("/a", 2), ("/z", 2)]), self.summarize({
            "hits": [hit(1, "/z", 2), hit(2, "/a", 2)], "total": 4, "more": False}))

    def test_empty_or_null_hits_with_explicit_zero_are_valid(self):
        for batch in [[], None]:
            with self.subTest(batch=batch):
                self.assertEqual((0, []), self.summarize({"hits": batch, "total": 0, "more": False}))

    def test_empty_or_null_hits_cannot_hide_positive_or_missing_total(self):
        for batch in [[], None]:
            for total in [3, None, -1, True, "0"]:
                with self.subTest(batch=batch, total=total), self.assertRaises(requests.RequestException):
                    self.summarize({"hits": batch, "total": total, "more": False})
            with self.subTest(batch=batch, total="missing"), self.assertRaises(requests.RequestException):
                self.summarize({"hits": batch, "more": False})

    def test_malformed_page_lists_fail_instead_of_reporting_zero(self):
        payloads = [{}, {"error": "unavailable"}, {"hits": {}, "more": False},
                    {"hits": [], "total": 0}, {"hits": [], "total": 0, "more": "false"}]
        for payload in payloads:
            with self.subTest(payload=payload), self.assertRaises(requests.RequestException):
                self.summarize(payload)

    def test_invalid_page_records_are_rejected(self):
        invalid_hits = [None, {}, hit(count=-1), hit(count=True), hit(count="2"),
                        hit(count=1.5), hit(path=None), hit(path_id=0),
                        hit(path_id=True), hit(path_id="1")]
        for invalid in invalid_hits:
            with self.subTest(hit=invalid), self.assertRaises(requests.RequestException):
                self.summarize({"hits": [invalid], "total": 0, "more": False})

    def test_duplicate_path_ids_within_batch_are_rejected(self):
        with self.assertRaises(requests.RequestException):
            self.summarize({"hits": [hit(), hit()], "total": 4, "more": False})

    def test_repeated_pagination_stops_without_double_counting(self):
        batches = [
            {"hits": [hit()], "total": 2, "more": True},
            {"hits": [hit()], "total": 2, "more": True},
        ]
        with patch.object(report, "api_get", side_effect=batches) as api_get:
            with self.assertRaises(requests.RequestException):
                report.hit_summary("rjacobucci", "token", self.start, self.end)
        self.assertEqual(2, api_get.call_count)

    def test_more_without_any_path_ids_is_rejected(self):
        for batch in [[], None]:
            with self.subTest(batch=batch), self.assertRaises(requests.RequestException):
                self.summarize({"hits": batch, "total": 0, "more": True})


class PeriodSummaryTests(ReportTestCase):
    def test_successful_hit_summary_does_not_call_fallback(self):
        with patch.object(report, "hit_summary", return_value=(3, [("/", 3)])), \
                patch.object(report, "api_get") as api_get:
            result = report.period_summary("rjacobucci", "token", self.start, self.end)
        self.assertEqual(report.PeriodSummary(3, [("/", 3)]), result)
        api_get.assert_not_called()

    def test_404_uses_total_not_total_utc_and_marks_pages_unavailable(self):
        with patch.object(report, "hit_summary", side_effect=http_error()), \
                patch.object(report, "api_get", return_value={"total": 12, "total_utc": 0}) as api_get:
            result = report.period_summary("rjacobucci", "token", self.start, self.end)
        self.assertEqual(report.PeriodSummary(12), result)
        api_get.assert_called_once_with("rjacobucci", "token", "stats/total", {
            "start": "2026-09-20T00:00:00Z", "end": "2026-09-20T23:00:00Z"})

    def test_second_page_404_discards_partial_counts_and_rankings(self):
        replies = [{"hits": [hit(count=2)], "total": 2, "more": True}, http_error(), {"total": 8}]
        with patch.object(report, "api_get", side_effect=replies) as api_get:
            result = report.period_summary("rjacobucci", "token", self.start, self.end)
        self.assertEqual(report.PeriodSummary(8), result)
        self.assertEqual("1", api_get.call_args_list[1].args[3]["exclude_paths"])
        self.assertEqual("stats/total", api_get.call_args_list[2].args[2])
        self.assertEqual({"start", "end"}, set(api_get.call_args_list[2].args[3]))

    def test_zero_total_fallback_is_a_valid_count(self):
        with patch.object(report, "hit_summary", side_effect=http_error()), \
                patch.object(report, "api_get", return_value={"total": 0}):
            self.assertEqual(report.PeriodSummary(0),
                             report.period_summary("rjacobucci", "token", self.start, self.end))

    def test_non_404_failures_do_not_use_fallback(self):
        for error in [http_error(400), http_error(401), http_error(403),
                      requests.Timeout("timeout"), requests.RequestException("invalid data")]:
            with self.subTest(error=str(error)), \
                    patch.object(report, "hit_summary", side_effect=error), \
                    patch.object(report, "api_get") as api_get:
                result = report.period_summary("rjacobucci", "token", self.start, self.end)
                self.assertIsNone(result.total)
                self.assertIsNone(result.pages)
                self.assertEqual(str(error), result.error)
                api_get.assert_not_called()

    def test_invalid_fallback_count_remains_unavailable(self):
        for payload in [{}, {"total_utc": 4}, {"total": None}, {"total": "4"},
                        {"total": -1}, {"total": True}, {"total": 1.5}]:
            with self.subTest(payload=payload), \
                    patch.object(report, "hit_summary", side_effect=http_error()), \
                    patch.object(report, "api_get", return_value=payload):
                result = report.period_summary("rjacobucci", "token", self.start, self.end)
                self.assertIsNone(result.total)
                self.assertIn("HTTP 404", result.error)
                self.assertIn("invalid total count", result.error)

    def test_both_routes_failing_preserves_both_errors(self):
        with patch.object(report, "hit_summary", side_effect=http_error()), \
                patch.object(report, "api_get", side_effect=requests.Timeout("totals timeout")):
            result = report.period_summary("rjacobucci", "token", self.start, self.end)
        self.assertIsNone(result.total)
        self.assertIn("HTTP 404", result.error)
        self.assertIn("totals timeout", result.error)


class MainTests(ReportTestCase):
    def setUp(self):
        super().setUp()
        self.now = datetime(2027, 1, 1, 0, 15, tzinfo=timezone.utc)
        self.clock = self.enterContext(patch.object(report, "datetime", wraps=datetime))
        self.clock.now.return_value = self.now
        self.local_date = self.enterContext(patch.object(report, "date", wraps=date))
        self.local_date.today.return_value = date(2026, 12, 31)
        values = {"GOATCOUNTER_CODE": "rjacobucci", "GOATCOUNTER_API_TOKEN": "test-token",
                  "GMAIL_USER": "sender@example.com", "GMAIL_APP_PASSWORD": "test-password",
                  "DAILY_EMAIL_TO": "recipient@example.com"}
        self.enterContext(patch.object(report, "env", side_effect=values.__getitem__))
        self.email = self.enterContext(patch.object(report, "send_email"))
        self.enterContext(patch("builtins.print"))

    def test_queries_day_and_whole_week_independently_using_utc_date(self):
        results = [report.PeriodSummary(3, [("/", 2), ("/publications", 1)]), report.PeriodSummary(12, [])]
        with patch.object(report, "period_summary", side_effect=results) as summary:
            self.assertEqual(0, report.main())
        self.assertEqual([
            call("rjacobucci", "test-token", date(2026, 12, 31), date(2027, 1, 1)),
            call("rjacobucci", "test-token", date(2026, 12, 25), date(2027, 1, 1)),
        ], summary.call_args_list)
        self.local_date.today.assert_not_called()
        self.assertTrue(all(item == call(timezone.utc) for item in self.clock.now.call_args_list))
        self.email.assert_called_once()
        self.assertIn("3 visits", self.email.call_args.args[3])
        body = self.email.call_args.args[4]
        self.assertIn("2026-12-25 through 2026-12-31 (UTC)", body)
        self.assertIn("Visits last 7 days: 12", body)
        self.assertIn("Top pages / events yesterday:", body)

    def test_failed_day_keeps_successful_week_without_false_zero(self):
        results = [report.PeriodSummary(error="day API failed"), report.PeriodSummary(8, [])]
        with patch.object(report, "period_summary", side_effect=results) as summary:
            self.assertEqual(1, report.main())
        self.assertEqual(2, summary.call_count)
        self.email.assert_called_once()
        self.assertIn("incomplete", self.email.call_args.args[3])
        body = self.email.call_args.args[4]
        self.assertIn("Visits yesterday:   unavailable", body)
        self.assertIn("Visits last 7 days: 8", body)
        self.assertIn("day API failed", body)
        self.assertIn("Top pages / events yesterday: unavailable", body)
        self.assertNotIn("Visits yesterday:   0", body)

    def test_failed_week_keeps_yesterday_and_top_pages(self):
        results = [report.PeriodSummary(2, [("/", 2)]), report.PeriodSummary(error="week API failed")]
        with patch.object(report, "period_summary", side_effect=results):
            self.assertEqual(1, report.main())
        body = self.email.call_args.args[4]
        self.assertIn("Visits yesterday:   2", body)
        self.assertIn("Visits last 7 days: unavailable", body)
        self.assertIn("Top pages / events yesterday:\n     2  /", body)

    def test_both_periods_failing_sends_one_incomplete_email(self):
        with patch.object(report, "period_summary", return_value=report.PeriodSummary(error="API failed")):
            self.assertEqual(1, report.main())
        self.email.assert_called_once()
        self.assertIn("incomplete", self.email.call_args.args[3])
        self.assertIn("Unavailable counts are not zero visits.", self.email.call_args.args[4])

    def test_successful_zero_is_not_marked_unavailable(self):
        with patch.object(report, "period_summary", return_value=report.PeriodSummary(0, [])):
            self.assertEqual(0, report.main())
        self.assertIn("0 visits", self.email.call_args.args[3])
        body = self.email.call_args.args[4]
        self.assertIn("Visits yesterday:   0", body)
        self.assertIn("Visits last 7 days: 0", body)
        self.assertNotIn("unavailable", body.lower())

    def test_zero_from_totals_fallback_is_valid_but_pages_unavailable(self):
        with patch.object(report, "period_summary", return_value=report.PeriodSummary(0)):
            self.assertEqual(0, report.main())
        self.assertIn("0 visits", self.email.call_args.args[3])
        self.assertNotIn("incomplete", self.email.call_args.args[3])
        self.assertIn("Top pages / events yesterday: unavailable", self.email.call_args.args[4])

    def test_smtp_failure_is_not_reported_as_success(self):
        self.email.side_effect = smtplib.SMTPException("mail unavailable")
        with patch.object(report, "period_summary", return_value=report.PeriodSummary(0, [])):
            with self.assertRaises(smtplib.SMTPException):
                report.main()


if __name__ == "__main__":
    unittest.main()
