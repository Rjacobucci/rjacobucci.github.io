import json
import smtplib
import unittest
from datetime import datetime, timedelta, timezone
from unittest.mock import call, patch
from zoneinfo import ZoneInfo

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
        self.start = datetime(2026, 9, 20, tzinfo=timezone.utc)
        self.end = datetime(2026, 9, 21, tzinfo=timezone.utc)
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
            report.range_params(datetime(2026, 12, 25, tzinfo=timezone.utc),
                                datetime(2027, 1, 1, tzinfo=timezone.utc)))

    def test_leap_day(self):
        self.assertEqual("2028-02-29T23:00:00Z",
                         report.range_params(datetime(2028, 2, 29, tzinfo=timezone.utc),
                                             datetime(2028, 3, 1, tzinfo=timezone.utc))["end"])

    def test_nonmidnight_rolling_windows_preserve_hour_and_exclude_partial_hour(self):
        now = datetime(2026, 10, 28, 13, 32, 15, 999, tzinfo=timezone.utc)
        start, week_start, end = report.report_windows(now)
        self.assertEqual(datetime(2026, 10, 28, 13, tzinfo=timezone.utc), end)
        self.assertEqual(timedelta(hours=24), end - start)
        self.assertEqual(timedelta(hours=168), end - week_start)
        self.assertEqual({"start": "2026-10-27T13:00:00Z", "end": "2026-10-28T12:00:00Z"},
                         report.range_params(start, end))

    def test_rolling_windows_cross_year(self):
        start, week_start, end = report.report_windows(datetime(2027, 1, 1, 13, 45, tzinfo=timezone.utc))
        self.assertEqual(datetime(2026, 12, 31, 13, tzinfo=timezone.utc), start)
        self.assertEqual(datetime(2026, 12, 25, 13, tzinfo=timezone.utc), week_start)
        self.assertEqual(datetime(2027, 1, 1, 13, tzinfo=timezone.utc), end)

    def test_dst_fall_back_still_uses_24_elapsed_hours(self):
        now = datetime(2026, 11, 1, 1, 35, tzinfo=ZoneInfo("America/Chicago"), fold=1)
        start, week_start, end = report.report_windows(now)
        self.assertEqual(datetime(2026, 11, 1, 7, tzinfo=timezone.utc), end)
        self.assertEqual(timedelta(hours=24), end - start)
        self.assertEqual(timedelta(hours=168), end - week_start)

    def test_timezone_offset_is_converted_before_flooring(self):
        now = datetime(2026, 10, 28, 19, 10, tzinfo=timezone(timedelta(hours=5, minutes=30)))
        self.assertEqual(datetime(2026, 10, 28, 13, tzinfo=timezone.utc), report.report_windows(now)[2])

    def test_local_end_at_dst_fold_subtracts_one_elapsed_hour(self):
        start = datetime(2026, 10, 31, 7, tzinfo=timezone.utc)
        end = datetime(2026, 11, 1, 1, tzinfo=ZoneInfo("America/Chicago"), fold=1)
        self.assertEqual("2026-11-01T06:00:00Z", report.range_params(start, end)["end"])

    def test_naive_and_unaligned_times_are_rejected(self):
        with self.assertRaises(ValueError):
            report.report_windows(datetime(2026, 10, 28, 13))
        for invalid in [datetime(2026, 10, 28, 13), self.start + timedelta(minutes=1),
                        self.start + timedelta(seconds=1), self.start + timedelta(microseconds=1)]:
            with self.subTest(value=invalid), self.assertRaises(ValueError):
                report.iso_hour(invalid)

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

    def test_transient_404_is_retried_on_known_reporting_routes(self):
        for route in ["stats/hits", "stats/total", "paths"]:
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


class SessionPathTests(ReportTestCase):
    def test_unordered_ids_find_marker_on_one_page(self):
        # GoatCounter's SQL orders by path, path_id, despite documentation
        # describing ID order. A later alphabetic path can have a smaller ID.
        payload = {"paths": [{"id": 90, "path": "/", "event": False},
                             {"id": 4, "path": "/work", "event": False},
                             {"id": 2, "path": report.SITEWIDE_SESSION_EVENT, "event": True}],
                   "more": False}
        with patch.object(report, "api_get", return_value=payload) as api_get:
            self.assertEqual(2, report.find_session_path_id("rjacobucci", "token"))
        api_get.assert_called_once_with("rjacobucci", "token", "paths", {"limit": 200, "after": 0})

    def test_marker_in_truncated_page_needs_no_further_requests(self):
        payload = {"paths": [{"id": 8, "path": report.SITEWIDE_SESSION_EVENT, "event": True}],
                   "more": True}
        with patch.object(report, "api_get", return_value=payload) as api_get:
            self.assertEqual(8, report.find_session_path_id("rjacobucci", "token"))
        api_get.assert_called_once()

    def test_absent_event_is_none_not_zero(self):
        for paths in [None, [], [{"id": 1, "path": "/"}],
                      [{"id": 20, "path": "/a"}, {"id": 1, "path": "/b"}]]:
            with self.subTest(paths=paths), patch.object(report, "api_get", return_value={"paths": paths, "more": False}) as api_get:
                self.assertIsNone(report.find_session_path_id("rjacobucci", "token"))
                api_get.assert_called_once()

    def test_marker_must_be_an_event(self):
        for event in [None, False, "true", 1]:
            payload = {"paths": [{"id": 1, "path": report.SITEWIDE_SESSION_EVENT, "event": event}], "more": False}
            with self.subTest(event=event), patch.object(report, "api_get", return_value=payload):
                with self.assertRaises(requests.RequestException):
                    report.find_session_path_id("rjacobucci", "token")

    def test_malformed_path_lists_fail(self):
        payloads = [{}, {"paths": {}, "more": False}, {"paths": [], "more": "false"},
                    {"paths": None, "more": True}, {"paths": [], "more": True},
                    {"paths": [None], "more": False},
                    {"paths": [{"path": "/"}], "more": False},
                    {"paths": [{"id": True, "path": "/"}], "more": False},
                    {"paths": [{"id": 0, "path": "/"}], "more": False},
                    {"paths": [{"id": -1, "path": "/"}], "more": False},
                    {"paths": [{"id": "1", "path": "/"}], "more": False},
                    {"paths": [{"id": 1, "path": None}], "more": False}]
        for payload in payloads:
            with self.subTest(payload=payload), patch.object(report, "api_get", return_value=payload):
                with self.assertRaises(requests.RequestException):
                    report.find_session_path_id("rjacobucci", "token")

    def test_duplicate_path_ids_are_rejected(self):
        payload = {"paths": [{"id": 2, "path": "/a"}, {"id": 2, "path": "/b"}], "more": False}
        with patch.object(report, "api_get", return_value=payload) as api_get:
            with self.assertRaises(requests.RequestException):
                report.find_session_path_id("rjacobucci", "token")
        api_get.assert_called_once()

    def test_truncated_listing_uses_exact_name_not_an_unsafe_id_cursor(self):
        replies = [
            {"paths": [{"id": 90, "path": "/a"}, {"id": 20, "path": "/b"}], "more": True},
            {"hits": [{**hit(2, report.SITEWIDE_SESSION_EVENT, 3), "event": True}],
             "total": 3, "more": False},
        ]
        with patch.object(report, "api_get", side_effect=replies) as api_get:
            self.assertEqual(2, report.find_session_path_id("rjacobucci", "token"))
        # Do not constrain ID discovery to completed report hours. API defaults
        # include the current hour, allowing discovery of a newly recorded event.
        self.assertEqual([
            call("rjacobucci", "token", "paths", {"limit": 200, "after": 0}),
            call("rjacobucci", "token", "stats/hits", {
                "path_by_name": "true", "include_paths": report.SITEWIDE_SESSION_EVENT, "limit": 1}),
        ], api_get.call_args_list)

    def test_empty_named_lookup_is_unknown_not_zero_or_missing(self):
        for hits in [None, []]:
            replies = [{"paths": [{"id": 90, "path": "/a"}], "more": True},
                       {"hits": hits, "total": 0, "more": False}]
            with self.subTest(hits=hits), patch.object(report, "api_get", side_effect=replies) as api_get:
                with self.assertRaisesRegex(requests.RequestException, "Could not verify"):
                    report.find_session_path_id("rjacobucci", "token")
                self.assertEqual(2, api_get.call_count)

    def test_invalid_named_discovery_is_rejected(self):
        valid = {**hit(8, report.SITEWIDE_SESSION_EVENT, 3), "event": True}
        invalid_hits = [None, {}, {**valid, "path": "/"}, {**valid, "event": False},
                        {**valid, "event": 1}, {**valid, "event": "true"},
                        {**valid, "path_id": 0}, {**valid, "path_id": -1},
                        {**valid, "path_id": True}, {**valid, "path_id": "8"},
                        {**valid, "count": -1}, {**valid, "count": True},
                        {**valid, "count": "3"}, {k: v for k, v in valid.items() if k != "count"}]
        payloads = [{"hits": [h], "total": 3, "more": False} for h in invalid_hits]
        payloads += [{}, {"hits": {}, "more": False},
                     {"hits": [valid], "more": True}, {"hits": [valid], "more": "false"},
                     {"hits": [valid]}, {"hits": [valid, valid], "more": False},
                     {"hits": [], "total": 5, "more": False}, {"hits": [], "more": False}]
        for payload in payloads:
            replies = [{"paths": [{"id": 90, "path": "/a"}], "more": True}, payload]
            with self.subTest(payload=payload), patch.object(report, "api_get", side_effect=replies):
                with self.assertRaises(requests.RequestException):
                    report.find_session_path_id("rjacobucci", "token")

    def test_named_discovery_request_failure_remains_unavailable(self):
        replies = [{"paths": [{"id": 90, "path": "/a"}], "more": True},
                   requests.Timeout("discovery timed out")]
        with patch.object(report, "api_get", side_effect=replies) as api_get:
            with self.assertRaisesRegex(requests.RequestException, "discovery timed out"):
                report.find_session_path_id("rjacobucci", "token")
        self.assertEqual(2, api_get.call_count)


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

    def test_shared_marker_is_excluded_from_ranking_but_used_for_pagination(self):
        replies = [
            {"hits": [hit(8, report.SITEWIDE_SESSION_EVENT, 100)], "total": 100, "more": True},
            {"hits": [hit(2, "/work", 3), hit(3, "404: /missing", 1)], "total": 4, "more": False},
        ]
        with patch.object(report, "api_get", side_effect=replies) as api_get:
            total, pages = report.hit_summary("rjacobucci", "token", self.start, self.end)
        self.assertEqual((4, [("/work", 3), ("404: /missing", 1)]), (total, pages))
        self.assertEqual("8", api_get.call_args_list[1].args[3]["exclude_paths"])

    def test_filtered_query_counts_only_requested_event(self):
        payload = {"hits": [hit(8, report.SITEWIDE_SESSION_EVENT, 4)], "total": 999, "more": False}
        with patch.object(report, "api_get", return_value=payload) as api_get:
            total, _ = report.hit_summary("rjacobucci", "token", self.start, self.end, include_path_id=8)
        self.assertEqual(4, total)
        self.assertEqual("8", api_get.call_args.args[3]["include_paths"])

    def test_filtered_query_rejects_unrequested_path(self):
        payload = {"hits": [hit(9, "/work", 40)], "total": 40, "more": False}
        with patch.object(report, "api_get", return_value=payload):
            with self.assertRaises(requests.RequestException):
                report.hit_summary("rjacobucci", "token", self.start, self.end, include_path_id=8)

    def test_invalid_filter_id_fails_before_request(self):
        for path_id in [0, -1, True, "8", 1.5]:
            with self.subTest(path_id=path_id), self.assertRaises(ValueError):
                report.hit_summary("rjacobucci", "token", self.start, self.end, include_path_id=path_id)
        self.http.assert_not_called()


class PeriodSummaryTests(ReportTestCase):
    def summarize(self):
        return report.period_summary("rjacobucci", "token", self.start, self.end, include_path_id=8)

    def test_successful_hit_summary_does_not_call_fallback(self):
        with patch.object(report, "hit_summary", return_value=(3, [])) as hits, \
                patch.object(report, "api_get") as api_get:
            result = self.summarize()
        self.assertEqual(report.PeriodSummary(3, []), result)
        hits.assert_called_once_with("rjacobucci", "token", self.start, self.end, include_path_id=8)
        api_get.assert_not_called()

    def test_filter_is_required(self):
        with self.assertRaises(TypeError):
            report.period_summary("rjacobucci", "token", self.start, self.end)

    def test_404_uses_total_not_total_utc_and_marks_pages_unavailable(self):
        with patch.object(report, "hit_summary", side_effect=http_error()), \
                patch.object(report, "api_get", return_value={"total": 12, "total_utc": 0}) as api_get:
            result = self.summarize()
        self.assertEqual(report.PeriodSummary(12), result)
        api_get.assert_called_once_with("rjacobucci", "token", "stats/total", {
            "start": "2026-09-20T00:00:00Z", "end": "2026-09-20T23:00:00Z", "include_paths": "8"})

    def test_second_page_404_discards_partial_counts_and_rankings(self):
        replies = [{"hits": [hit(8, report.SITEWIDE_SESSION_EVENT, 2)], "total": 2, "more": True},
                   http_error(), {"total": 8}]
        with patch.object(report, "api_get", side_effect=replies) as api_get:
            result = self.summarize()
        self.assertEqual(report.PeriodSummary(8), result)
        self.assertEqual("8", api_get.call_args_list[1].args[3]["exclude_paths"])
        self.assertEqual("stats/total", api_get.call_args_list[2].args[2])
        self.assertEqual({"start", "end", "include_paths"}, set(api_get.call_args_list[2].args[3]))
        for invocation in api_get.call_args_list:
            self.assertEqual("8", invocation.args[3]["include_paths"])

    def test_zero_total_fallback_is_a_valid_count(self):
        with patch.object(report, "hit_summary", side_effect=http_error()), \
                patch.object(report, "api_get", return_value={"total": 0}):
            self.assertEqual(report.PeriodSummary(0),
                             self.summarize())

    def test_non_404_failures_do_not_use_fallback(self):
        for error in [http_error(400), http_error(401), http_error(403),
                      requests.Timeout("timeout"), requests.RequestException("invalid data")]:
            with self.subTest(error=str(error)), \
                    patch.object(report, "hit_summary", side_effect=error), \
                    patch.object(report, "api_get") as api_get:
                result = self.summarize()
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
                result = self.summarize()
                self.assertIsNone(result.total)
                self.assertIn("HTTP 404", result.error)
                self.assertIn("invalid total count", result.error)

    def test_both_routes_failing_preserves_both_errors(self):
        with patch.object(report, "hit_summary", side_effect=http_error()), \
                patch.object(report, "api_get", side_effect=requests.Timeout("totals timeout")):
            result = self.summarize()
        self.assertIsNone(result.total)
        self.assertIn("HTTP 404", result.error)
        self.assertIn("totals timeout", result.error)


class MainTests(ReportTestCase):
    def setUp(self):
        super().setUp()
        self.now = datetime(2027, 1, 1, 13, 15, tzinfo=timezone.utc)
        self.clock = self.enterContext(patch.object(report, "datetime", wraps=datetime))
        self.clock.now.return_value = self.now
        values = {"GOATCOUNTER_CODE": "rjacobucci", "GOATCOUNTER_API_TOKEN": "test-token",
                  "GMAIL_USER": "sender@example.com", "GMAIL_APP_PASSWORD": "test-password",
                  "DAILY_EMAIL_TO": "recipient@example.com"}
        self.enterContext(patch.object(report, "env", side_effect=values.__getitem__))
        self.lookup = self.enterContext(patch.object(report, "find_session_path_id", return_value=8))
        self.pages = self.enterContext(patch.object(report, "hit_summary", return_value=(100, [("/", 100)])))
        self.email = self.enterContext(patch.object(report, "send_email"))
        self.enterContext(patch("builtins.print"))

    def test_queries_rolling_day_and_week_independently_with_single_lookup(self):
        results = [report.PeriodSummary(3), report.PeriodSummary(12)]
        with patch.object(report, "period_summary", side_effect=results) as summary:
            self.assertEqual(0, report.main())
        end = datetime(2027, 1, 1, 13, tzinfo=timezone.utc)
        self.assertEqual([
            call("rjacobucci", "test-token", end - timedelta(hours=24), end, include_path_id=8),
            call("rjacobucci", "test-token", end - timedelta(days=7), end, include_path_id=8),
        ], summary.call_args_list)
        self.clock.now.assert_called_once_with(timezone.utc)
        self.lookup.assert_called_once_with("rjacobucci", "test-token")
        self.pages.assert_called_once_with("rjacobucci", "test-token", end - timedelta(hours=24), end)
        self.email.assert_called_once()
        self.assertIn("3 visitor sessions in the last 24 hours", self.email.call_args.args[3])
        body = self.email.call_args.args[4]
        self.assertIn("2026-12-31 13:00 to 2027-01-01 13:00 UTC", body)
        self.assertIn("2026-12-25 13:00 to 2027-01-01 13:00 UTC", body)
        self.assertIn("Last 7 days:   12", body)
        self.assertIn("page/event visits, not visitors", body)
        self.assertNotIn("100 visitor sessions", body)
        self.assertIn("no historical backfill", body)

    def test_failed_day_keeps_successful_week_without_false_zero(self):
        results = [report.PeriodSummary(error="day API failed"), report.PeriodSummary(8, [])]
        with patch.object(report, "period_summary", side_effect=results) as summary:
            self.assertEqual(1, report.main())
        self.assertEqual(2, summary.call_count)
        self.email.assert_called_once()
        self.assertIn("incomplete", self.email.call_args.args[3])
        body = self.email.call_args.args[4]
        self.assertIn("Last 24 hours: unavailable", body)
        self.assertIn("Last 7 days:   8", body)
        self.assertIn("day API failed", body)
        self.assertIn("Top pages / events in the 24-hour window", body)
        self.assertNotIn("Last 24 hours: 0", body)
        self.assertNotIn("Last 24 hours: 100", body)

    def test_failed_week_keeps_yesterday_and_top_pages(self):
        results = [report.PeriodSummary(2, [("/", 2)]), report.PeriodSummary(error="week API failed")]
        with patch.object(report, "period_summary", side_effect=results):
            self.assertEqual(1, report.main())
        body = self.email.call_args.args[4]
        self.assertIn("Last 24 hours: 2", body)
        self.assertIn("Last 7 days:   unavailable", body)
        self.assertIn("   100  /", body)

    def test_both_periods_failing_sends_one_incomplete_email(self):
        with patch.object(report, "period_summary", return_value=report.PeriodSummary(error="API failed")):
            self.assertEqual(1, report.main())
        self.email.assert_called_once()
        self.assertIn("incomplete", self.email.call_args.args[3])
        self.assertIn("Unavailable counts are not zero visitor sessions.", self.email.call_args.args[4])

    def test_successful_zero_is_not_marked_unavailable(self):
        with patch.object(report, "period_summary", return_value=report.PeriodSummary(0, [])):
            self.assertEqual(0, report.main())
        self.assertIn("0 visitor sessions", self.email.call_args.args[3])
        body = self.email.call_args.args[4]
        self.assertIn("Last 24 hours: 0", body)
        self.assertIn("Last 7 days:   0", body)
        self.assertNotIn("unavailable", body.lower())

    def test_zero_from_totals_fallback_keeps_independent_page_breakdown(self):
        with patch.object(report, "period_summary", return_value=report.PeriodSummary(0)):
            self.assertEqual(0, report.main())
        self.assertIn("0 visitor sessions", self.email.call_args.args[3])
        self.assertNotIn("incomplete", self.email.call_args.args[3])
        self.assertIn("Top pages / events in the 24-hour window", self.email.call_args.args[4])
        self.assertIn("   100  /", self.email.call_args.args[4])

    def test_missing_first_event_is_unavailable_even_with_page_traffic(self):
        self.lookup.return_value = None
        with patch.object(report, "period_summary") as summary:
            self.assertEqual(1, report.main())
        summary.assert_not_called()
        self.pages.assert_called_once()
        body = self.email.call_args.args[4]
        self.assertIn("Last 24 hours: unavailable", body)
        self.assertIn("Last 7 days:   unavailable", body)
        self.assertIn("has not recorded its first event", body)
        self.assertIn("   100  /", body)
        self.assertNotIn("Last 24 hours: 0", body)
        self.assertNotIn("100 visitor sessions", body)

    def test_failed_marker_lookup_still_fetches_top_pages(self):
        self.lookup.side_effect = requests.Timeout("path lookup failed")
        with patch.object(report, "period_summary") as summary:
            self.assertEqual(1, report.main())
        summary.assert_not_called()
        self.pages.assert_called_once()
        self.assertIn("path lookup failed", self.email.call_args.args[4])
        self.assertIn("   100  /", self.email.call_args.args[4])

    def test_failed_top_page_query_does_not_erase_valid_sessions(self):
        self.pages.side_effect = requests.Timeout("pages failed")
        with patch.object(report, "period_summary", side_effect=[report.PeriodSummary(3), report.PeriodSummary(12)]):
            self.assertEqual(0, report.main())
        body = self.email.call_args.args[4]
        self.assertIn("Last 24 hours: 3", body)
        self.assertIn("Last 7 days:   12", body)
        self.assertIn("Top pages / events: unavailable", body)
        self.assertIn("pages failed", body)

    def test_smtp_failure_is_not_reported_as_success(self):
        self.email.side_effect = smtplib.SMTPException("mail unavailable")
        with patch.object(report, "period_summary", return_value=report.PeriodSummary(0, [])):
            with self.assertRaises(smtplib.SMTPException):
                report.main()


class ReportIntegrationTests(ReportTestCase):
    def test_unordered_path_response_produces_filtered_24_hour_report(self):
        # Exercise real lookup, aggregation, and email formatting together;
        # only HTTP, environment, time, and email delivery are replaced.
        self.http.side_effect = [
            response(payload={"paths": [
                {"id": 90, "path": "/", "event": False},
                {"id": 20, "path": "/work", "event": False},
                {"id": 2, "path": report.SITEWIDE_SESSION_EVENT, "event": True}], "more": False}),
            response(payload={"hits": [hit(2, report.SITEWIDE_SESSION_EVENT, 3)], "total": 0, "more": False}),
            response(payload={"hits": [hit(2, report.SITEWIDE_SESSION_EVENT, 12)], "total": 0, "more": False}),
            response(payload={"hits": [hit(90, "/", 10), hit(20, "/work", 4),
                                       hit(2, report.SITEWIDE_SESSION_EVENT, 3)], "total": 17, "more": False}),
        ]
        values = {"GOATCOUNTER_CODE": "rjacobucci", "GOATCOUNTER_API_TOKEN": "test-token",
                  "GMAIL_USER": "sender@example.com", "GMAIL_APP_PASSWORD": "test-password",
                  "DAILY_EMAIL_TO": "recipient@example.com"}
        with patch.object(report, "datetime", wraps=datetime) as clock, \
                patch.object(report, "env", side_effect=values.__getitem__), \
                patch.object(report, "send_email") as email, patch("builtins.print"):
            clock.now.return_value = datetime(2026, 10, 28, 19, 17, tzinfo=timezone.utc)
            self.assertEqual(0, report.main())

        self.assertEqual(4, self.http.call_count)
        params = [invocation.kwargs["params"] for invocation in self.http.call_args_list]
        self.assertEqual({"limit": 200, "after": 0}, params[0])
        self.assertEqual({"start": "2026-10-27T19:00:00Z", "end": "2026-10-28T18:00:00Z",
                          "include_paths": "2", "limit": 100}, params[1])
        self.assertEqual({"start": "2026-10-21T19:00:00Z", "end": "2026-10-28T18:00:00Z",
                          "include_paths": "2", "limit": 100}, params[2])
        self.assertNotIn("include_paths", params[3])
        email.assert_called_once()
        self.assertIn("3 visitor sessions in the last 24 hours", email.call_args.args[3])
        body = email.call_args.args[4]
        self.assertIn("Last 24 hours: 3", body)
        self.assertIn("Last 7 days:   12", body)
        self.assertIn("2026-10-27 19:00 to 2026-10-28 19:00 UTC", body)
        self.assertIn("    10  /", body)
        self.assertIn("     4  /work", body)
        self.assertNotIn(report.SITEWIDE_SESSION_EVENT, body)
        self.assertNotIn("unavailable", body)


if __name__ == "__main__":
    unittest.main()
