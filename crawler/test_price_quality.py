import unittest

from .price_quality import LOW_PRICE_MEDIAN_RATIO, assess_price_group, obvious_price_issue


class PriceQualityTests(unittest.TestCase):
    def test_relative_low_price_is_flagged_against_same_spec_median(self):
        rows = [(100, "Cursor Pro 月卡代充"), (110, "Cursor Pro 月卡代充"),
                (120, "Cursor Pro 月卡代充"), (105, "Cursor Pro 月卡代充"),
                (115, "Cursor Pro 月卡代充"), (1, "Cursor Pro Pro 月卡代充")]
        result = assess_price_group(rows)
        self.assertEqual(len(result), 6)
        self.assertTrue(result[-1].startswith("低于同规格中位数"))
        self.assertIsNone(result[0])
        self.assertGreater(LOW_PRICE_MEDIAN_RATIO, 0)

    def test_shared_offers_are_not_globally_marked_as_bad_prices(self):
        self.assertIsNone(obvious_price_issue("Cursor Plus 月卡拼车共享车位"))
        reasons = assess_price_group([(100, "Cursor Plus 月卡代充"),
                                      (110, "Cursor Plus 月卡代充"),
                                      (105, "Cursor Plus 月卡代充"),
                                      (90, "Cursor Plus 月卡代充"),
                                      (95, "Cursor Plus 月卡代充"),
                                      (1, "Cursor Plus 月卡拼车共享车位")])
        self.assertIsNotNone(reasons[-1])
        self.assertEqual(len(reasons), 6)

    def test_configured_cny_floor_and_shop_specific_channel_are_flagged(self):
        self.assertIsNotNone(assess_price_group([(0.7, "Muse Token")])[-1])
        self.assertIsNone(obvious_price_issue("plus成品号-upi渠道-ic邮箱"))
        from .data_quality import assess_listing
        result = assess_listing("shop", "shop", "ChatGPT Plus 月卡代充", 1, "ChatGPT Plus",
                                {"tier": ["plus"], "delivery": "代充", "duration": "1月"})
        self.assertTrue(result["price_anomaly"])
        self.assertIn("底价", result["price_anomaly_reason"])
        self.assertIsNone(assess_price_group([(0.7, "small USD item")], currency="USD")[-1])


if __name__ == "__main__":
    unittest.main()
