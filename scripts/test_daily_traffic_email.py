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


if __name__ == "__main__":
    unittest.main()
