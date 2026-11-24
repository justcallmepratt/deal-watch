import os
import sys
import unittest
from datetime import date

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

import dealwatch  # noqa: E402

TODAY = date(2026, 11, 24)


def row(**overrides):
    base = {
        "item": "Thing", "price": "50", "regular_price": "60",
        "source_url": "https://example.com/thing", "seen_on": "2026-11-24",
        "expires_on": "", "wishlist": "no",
    }
    base.update(overrides)
    return base


class ReviewTests(unittest.TestCase):
    def test_small_saving_is_kept_but_quiet(self):
        result = dealwatch.review([row()], TODAY)
        self.assertEqual(len(result["kept"]), 1)
        self.assertEqual(result["alerts"], [])

    def test_wishlist_item_alerts_even_with_small_saving(self):
        result = dealwatch.review([row(wishlist="yes")], TODAY)
        self.assertEqual(len(result["alerts"]), 1)

    def test_hundred_dollars_off_alerts(self):
        result = dealwatch.review([row(price="900", regular_price="1000")], TODAY)
        self.assertEqual(len(result["alerts"]), 1)

    def test_thirty_percent_off_alerts(self):
        result = dealwatch.review([row(price="7", regular_price="10")], TODAY)
        self.assertEqual(len(result["alerts"]), 1)

    def test_expired_deal_is_removed(self):
        result = dealwatch.review([row(expires_on="2026-11-23")], TODAY)
        self.assertEqual(result["kept"], [])
        self.assertEqual(len(result["removed"]), 1)

    def test_deal_ending_today_is_still_listed(self):
        result = dealwatch.review([row(expires_on="2026-11-24")], TODAY)
        self.assertEqual(len(result["kept"]), 1)

    def test_stale_price_is_removed(self):
        result = dealwatch.review([row(seen_on="2026-11-20")], TODAY)
        self.assertEqual(result["kept"], [])

    def test_three_day_old_price_is_still_listed(self):
        result = dealwatch.review([row(seen_on="2026-11-21")], TODAY)
        self.assertEqual(len(result["kept"]), 1)

    def test_no_source_link_is_rejected(self):
        result = dealwatch.review([row(source_url="")], TODAY)
        self.assertEqual(result["rejected"], [("Thing", "no source link")])

    def test_no_price_is_rejected_not_estimated(self):
        result = dealwatch.review([row(price="")], TODAY)
        self.assertEqual(result["rejected"], [("Thing", "no price")])

    def test_missing_regular_price_means_no_saving_claimed(self):
        result = dealwatch.review([row(regular_price="")], TODAY)
        self.assertEqual(result["kept"][0].saving_usd, 0.0)
        self.assertEqual(result["alerts"], [])

    def test_sorted_by_dollars_saved(self):
        rows = [row(item="small"), row(item="big", price="100", regular_price="400")]
        result = dealwatch.review(rows, TODAY)
        self.assertEqual([d.item for d in result["kept"]], ["big", "small"])


if __name__ == "__main__":
    unittest.main()
