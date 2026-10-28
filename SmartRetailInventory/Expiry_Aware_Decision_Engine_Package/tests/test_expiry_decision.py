"""Small database-free checks for the expiry decision rules."""

import unittest
from datetime import date, timedelta

from expiry_decision import _classify_product


class ExpiryDecisionTests(unittest.TestCase):
    def base_row(self, **changes):
        row = {
            "product_id": 1,
            "name": "Test item",
            "category": "Grocery",
            "supplier": "Test supplier",
            "supplier_contact": "—",
            "stock": 100,
            "expiry_date": date.today() + timedelta(days=10),
            "days_to_expiry": 10,
            "units_sold": 0,
            "sale_days": 0,
        }
        row.update(changes)
        return row

    def test_expired_stock_is_blocked_from_recommendation(self):
        result = _classify_product(self.base_row(days_to_expiry=-1))
        self.assertEqual(result["decision_label"], "EXPIRED — DO NOT SELL")

    def test_missing_expiry_is_flagged(self):
        result = _classify_product(self.base_row(expiry_date=None, days_to_expiry=None))
        self.assertEqual(result["decision_label"], "EXPIRY DATE MISSING")

    def test_sparse_sales_history_is_low_confidence(self):
        result = _classify_product(self.base_row(days_to_expiry=10, units_sold=2, sale_days=1))
        self.assertEqual(result["confidence"], "Low")
        self.assertEqual(result["decision_label"], "REVIEW BEFORE REORDER")

    def test_expected_unsold_stock_calculation(self):
        # 90 units / 90 days = 1 unit/day; 10 days left -> 10 expected sales.
        result = _classify_product(self.base_row(stock=100, units_sold=90, sale_days=30, days_to_expiry=10))
        self.assertEqual(result["expected_sales_before_expiry"], 10.0)
        self.assertEqual(result["expected_unsold"], 90.0)


if __name__ == "__main__":
    unittest.main()
