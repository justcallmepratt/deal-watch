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


class ReliabilityTests(unittest.TestCase):
    def test_cheap_item_needs_no_reliability_check(self):
        result = dealwatch.review([row(price="50", regular_price="60")], TODAY)
        self.assertEqual(len(result["kept"]), 1)

    def test_unchecked_pricey_item_with_small_saving_is_removed(self):
        result = dealwatch.review([row(price="150", regular_price="170")], TODAY)
        self.assertEqual(result["kept"], [])
        self.assertIn("reliability not checked", result["removed"][0][1])

    def test_good_record_pricey_item_is_kept(self):
        result = dealwatch.review(
            [row(price="150", regular_price="170", reliability="good, long-term test 2025")], TODAY)
        self.assertEqual(len(result["kept"]), 1)
        self.assertEqual(result["kept"][0].reliability, "good")

    def test_mixed_record_kept_only_for_a_large_saving(self):
        small = row(item="small", price="150", regular_price="170", reliability="mixed")
        large = row(item="large", price="150", regular_price="300", reliability="mixed")
        result = dealwatch.review([small, large], TODAY)
        self.assertEqual([d.item for d in result["kept"]], ["large"])

    def test_unchecked_wishlist_item_is_kept(self):
        result = dealwatch.review(
            [row(price="150", regular_price="170", wishlist="yes")], TODAY)
        self.assertEqual(len(result["alerts"]), 1)

    def test_recall_is_removed_even_from_the_wishlist(self):
        result = dealwatch.review(
            [row(price="20", wishlist="yes", reliability="recall 2025, cpsc.gov")], TODAY)
        self.assertEqual(result["kept"], [])
        self.assertIn("poor record", result["removed"][0][1])

    def test_unknown_rating_text_is_never_read_as_good(self):
        self.assertEqual(dealwatch.reliability_rating("probably fine"), "not checked")
        self.assertEqual(dealwatch.reliability_rating("reliability not checked"), "not checked")
        self.assertEqual(dealwatch.reliability_rating(""), "not checked")
        self.assertEqual(dealwatch.reliability_rating("Known defect in hinge"), "poor")
        self.assertEqual(dealwatch.reliability_rating("Defect: hinge cracks"), "poor")


class BuiltToLastTests(unittest.TestCase):
    def test_claim_with_a_reason_counts(self):
        result = dealwatch.review(
            [row(built_to_last="yes", built_to_last_why="lifetime warranty")], TODAY)
        self.assertTrue(result["kept"][0].built_to_last)
        self.assertEqual(result["notes"], [])

    def test_bare_claim_is_cleared_and_noted(self):
        result = dealwatch.review([row(built_to_last="yes")], TODAY)
        self.assertFalse(result["kept"][0].built_to_last)
        self.assertEqual(len(result["notes"]), 1)


class SourcesDisagreeTests(unittest.TestCase):
    def test_big_disagreement_blocks_the_alert(self):
        result = dealwatch.review([row(wishlist="yes", other_price="100")], TODAY)
        self.assertEqual(len(result["kept"]), 1)
        self.assertEqual(result["alerts"], [])
        self.assertEqual(len(result["check"]), 1)

    def test_small_disagreement_still_alerts(self):
        result = dealwatch.review([row(wishlist="yes", other_price="52")], TODAY)
        self.assertEqual(len(result["alerts"]), 1)
        self.assertEqual(result["check"], [])


class OldSheetTests(unittest.TestCase):
    def test_sheet_without_new_columns_still_works(self):
        old = row()
        for key in dealwatch.OPTIONAL_FIELDS:
            old.pop(key, None)
        result = dealwatch.review([old], TODAY)
        self.assertEqual(len(result["kept"]), 1)


if __name__ == "__main__":
    unittest.main()
