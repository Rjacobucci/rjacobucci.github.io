import unittest
from datetime import date
from unittest.mock import patch

from scripts import daily_traffic_email as report


class HitSummaryTests(unittest.TestCase):
    def setUp(self):
        self.start = date(2026, 9, 20)
        self.end = date(2026, 9, 21)

    def test_total_and_top_pages_come_from_same_response(self):
        response = {
            "hits": [
                {"path_id": 1, "path": "/", "count": 2},
                {"path_id": 2, "path": "/publications", "count": 1},
            ],
            "total": 3,
            "more": False,
        }

        with patch.object(report, "api_get", return_value=response) as api_get:
            total, pages = report.hit_summary(
                "rjacobucci", "token", self.start, self.end)

        self.assertEqual(3, total)
        self.assertEqual([("/", 2), ("/publications", 1)], pages)
        self.assertEqual("stats/hits", api_get.call_args.args[2])

    def test_pagination_is_included_in_total_and_ranking(self):
        responses = [
            {
                "hits": [
                    {"path_id": 10, "path": "/", "count": 4},
                    {"path_id": 11, "path": "/publications", "count": 1},
                ],
                "total": 5,
                "more": True,
            },
            {
                "hits": [
                    {"path_id": 12, "path": "/cv", "count": 2},
                ],
                "total": 2,
                "more": False,
            },
        ]

        with patch.object(report, "api_get", side_effect=responses) as api_get:
            total, pages = report.hit_summary(
                "rjacobucci", "token", self.start, self.end, top_n=2)

        self.assertEqual(7, total)
        self.assertEqual([("/", 4), ("/cv", 2)], pages)
        second_params = api_get.call_args_list[1].args[3]
        self.assertEqual("10,11", second_params["exclude_paths"])

    def test_empty_range_returns_zero(self):
        response = {"hits": [], "total": 0, "more": False}

        with patch.object(report, "api_get", return_value=response):
            total, pages = report.hit_summary(
                "rjacobucci", "token", self.start, self.end)

        self.assertEqual(0, total)
        self.assertEqual([], pages)


class SevenDaySummaryTests(unittest.TestCase):
    def test_sums_daily_queries_and_reuses_final_day_for_top_pages(self):
        start = date(2026, 9, 18)
        end = date(2026, 9, 25)
        daily_results = [
            (1, [("/day-1", 1)]),
            (2, [("/day-2", 2)]),
            (3, [("/day-3", 3)]),
            (4, [("/day-4", 4)]),
            (5, [("/day-5", 5)]),
            (6, [("/day-6", 6)]),
            (3, [("/", 2), ("/publications", 1)]),
        ]

        with patch.object(report, "hit_summary", side_effect=daily_results) as hits:
            period, final_day, pages = report.seven_day_summary(
                "rjacobucci", "token", start, end, pause_seconds=0)

        self.assertEqual(24, period)
        self.assertEqual(3, final_day)
        self.assertEqual([("/", 2), ("/publications", 1)], pages)
        self.assertEqual(7, hits.call_count)
        self.assertEqual(start, hits.call_args_list[0].args[2])
        self.assertEqual(end, hits.call_args_list[-1].args[3])


if __name__ == "__main__":
    unittest.main()
