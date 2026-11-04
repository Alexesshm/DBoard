"""Regression tests for WB FBS placed-order collection and monitoring aggregation."""
import os
import sys
import unittest
from datetime import date
from unittest.mock import patch

sys.dont_write_bytecode = True
sys.path.insert(0, os.path.dirname(__file__))

import fetch_wb_data
import prepare_dashboard_data


class FetchWbFbsOrdersTests(unittest.TestCase):
    def test_fetch_pages_and_deduplicates_tasks(self):
        pages = [
            {"orders": [{"id": 101, "article": "A"}, {"id": 102, "article": "B"}], "next": 200},
            {"orders": [{"id": 102, "article": "B"}, {"id": 103, "article": "A"}], "next": 300},
            {"orders": [], "next": 0},
        ]
        seen_params = []

        def fake_fetch(url, params, headers, endpoint_name):
            self.assertEqual(endpoint_name, "fbs-orders")
            seen_params.append(params)
            return pages.pop(0)

        fixed_now = fetch_wb_data.datetime(2026, 11, 4, 12, tzinfo=fetch_wb_data.timezone.utc)
        with patch.object(fetch_wb_data, "fetch_with_retry", side_effect=fake_fetch):
            rows = fetch_wb_data.fetch_wb_fbs_orders(days=30, now=fixed_now)

        self.assertEqual([r["id"] for r in rows], [101, 102, 103])
        self.assertEqual([p["next"] for p in seen_params], [0, 200, 300])
        self.assertEqual(seen_params[0]["limit"], 1000)
        self.assertGreater(seen_params[0]["dateTo"], seen_params[0]["dateFrom"])
        self.assertLessEqual(seen_params[0]["dateTo"] - seen_params[0]["dateFrom"], 31 * 24 * 60 * 60)
        self.assertEqual(seen_params[0]["dateFrom"], 1791158400)

    def test_invalid_response_is_not_treated_as_empty_history(self):
        with patch.object(fetch_wb_data, "fetch_with_retry", return_value=[]):
            self.assertIsNone(fetch_wb_data.fetch_wb_fbs_orders())


class AggregateWbFbsOrdersTests(unittest.TestCase):
    def test_counts_created_tasks_once_by_article_and_seller_warehouse(self):
        orders = [
            {"id": 1, "createdAt": "2026-11-04T09:00:00Z", "article": "A", "warehouseId": 10},
            {"id": 1, "createdAt": "2026-11-04T09:00:00Z", "article": "A", "warehouseId": 10},
            # A later cancelled/refused task still counts: status is not filtered.
            {"id": 2, "createdAt": "2026-11-03T09:00:00Z", "article": "A", "warehouseId": 10,
             "status": "declined_by_client"},
            {"id": 3, "createdAt": "2026-11-01T09:00:00Z", "article": "B", "warehouseId": 20},
            {"id": 4, "createdAt": "2026-10-15T09:00:00Z", "article": "A", "warehouseId": 10},
        ]
        warehouses = {"10": "Мой склад 1", "20": "Мой склад 2"}
        by_3d = prepare_dashboard_data.aggregate_wb_fbs_order_placements(
            orders, warehouses, date(2026, 11, 2), date(2026, 11, 4)
        )
        by_7d = prepare_dashboard_data.aggregate_wb_fbs_order_placements(
            orders, warehouses, date(2026, 10, 29), date(2026, 11, 4)
        )
        by_30d = prepare_dashboard_data.aggregate_wb_fbs_order_placements(
            orders, warehouses, date(2026, 10, 6), date(2026, 11, 4)
        )

        self.assertEqual([(p["article"], p["count"]) for p in by_3d], [("A", 2)])
        self.assertEqual(sum(p["count"] for p in by_7d), 3)
        self.assertEqual(sum(p["count"] for p in by_30d), 4)
        # Exactly one task created at the 3-day boundary is included.
        boundary = prepare_dashboard_data.aggregate_wb_fbs_order_placements(
            orders, warehouses, date(2026, 11, 1), date(2026, 11, 1)
        )
        self.assertEqual([(p["article"], p["count"]) for p in boundary], [("B", 1)])
        self.assertEqual(by_3d[0]["by_warehouse"][0]["name"], "Мой склад 1")
        self.assertTrue(all(row["source"] == "fbs" for p in by_30d for row in p["by_warehouse"]))


if __name__ == "__main__":
    unittest.main()
