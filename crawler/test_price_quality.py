import unittest

from .price_quality import LOW_PRICE_MEDIAN_RATIO, assess_price_group, obvious_price_issue


class PriceQualityTests(unittest.TestCase):
    def test_relative_low_price_is_flagged_against_same_spec_median(self):
        rows = [(100, "Cursor Pro 月卡代充"), (110, "Cursor Pro 月卡代充"),
                (120, "Cursor Pro 月卡代充"), (1, "Cursor Pro 月卡代充")]
        result = assess_price_group(rows)
        self.assertEqual(len(result), 4)
        self.assertTrue(result[-1].startswith("低于同规格中位数"))
        self.assertIsNone(result[0])
        self.assertGreater(LOW_PRICE_MEDIAN_RATIO, 0)

    def test_non_comparable_listing_is_flagged_but_not_removed(self):
        self.assertIn("共享", obvious_price_issue("Cursor Plus 月卡拼车共享车位"))
        reasons = assess_price_group([(100, "Cursor Plus 月卡代充"),
                                      (110, "Cursor Plus 月卡代充"),
                                      (105, "Cursor Plus 月卡代充"),
                                      (1, "Cursor Plus 月卡拼车共享车位")])
        self.assertIsNotNone(reasons[-1])
        self.assertEqual(len(reasons), 4)

    def test_configured_cny_floor_and_shop_specific_channel_are_flagged(self):
        self.assertIsNotNone(assess_price_group([(0.7, "Muse Token")])[-1])
        self.assertIsNotNone(obvious_price_issue("plus成品号-upi渠道-ic邮箱"))
        self.assertIsNone(assess_price_group([(0.7, "small USD item")], currency="USD")[-1])


if __name__ == "__main__":
    unittest.main()
