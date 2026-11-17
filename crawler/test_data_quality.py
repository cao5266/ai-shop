import unittest
from types import SimpleNamespace

from backend.api_v4 import product_price_fields, spec_groups
from .data_quality import assess_listing, canonicalize_codex
from .normalize import specification


class MergeAndApiContractTests(unittest.TestCase):
    def test_periods_group_unknown_and_common_variants(self):
        for title, expected in (("Plus 1月代充", "1月"), ("Plus 月卡", "1月"),
                                ("Plus 30天", "1月"), ("Pro 季卡", "3月"),
                                ("Pro 年付", "1年"), ("Claude 成品号", None)):
            with self.subTest(title=title):
                self.assertEqual(specification(title, "ChatGPT Plus")["duration"], expected)

    def test_codex_tiers_merge_and_credit_packs_stay_separate(self):
        go = specification("Codex Go 官方充值月卡", "Codex")
        plus = specification("Codex Plus 官方代充 30天", "Codex")
        pro = specification("Codex Pro 200x 官方代充月卡", "Codex")
        credits = specification("Codex 250额度充值", "Codex")
        self.assertEqual(canonicalize_codex("Codex", "Codex Go", go)[0], "ChatGPT Go")
        self.assertEqual(canonicalize_codex("Codex", "Codex Plus", plus)[0], "ChatGPT Plus")
        self.assertEqual(canonicalize_codex("Codex", "Codex Pro 200", pro)[0], "ChatGPT Pro")
        self.assertIsNone(canonicalize_codex("Codex", "Codex 250额度", credits)[0])

    def test_price_floor_flags_without_deleting_source_evidence(self):
        result = assess_listing("shop", "Shop Name", "ChatGPT Plus 月卡代充", 1,
                                "ChatGPT Plus", {"tier": ["plus"], "duration": "1月", "delivery": "代充"})
        self.assertFalse(result["keep"])
        self.assertTrue(result["price_anomaly"])
        self.assertIsNotNone(result["price_anomaly_reason"])

    def test_direct_api_grouping_keeps_shop_name_public_id_and_price_consistency(self):
        rows = [SimpleNamespace(product_id=1, product_name="Cursor", shop_id=7,
                 shop_name="Example Shop", shop_key="secret/path", shop_domain="example.test",
                 title="Cursor Pro 1月代充", price=100.0, currency="CNY",
                 spec=specification("Cursor Pro 1月代充", "Cursor"), url="https://example.test/a"),
                SimpleNamespace(product_id=1, product_name="Cursor", shop_id=8,
                 shop_name="Another Shop", shop_key="other/path", shop_domain="other.test",
                 title="Cursor Pro 月卡直充", price=110.0, currency="CNY",
                 spec=specification("Cursor Pro 月卡直充", "Cursor"), url="https://other.test/a")]
        groups = spec_groups(rows)
        self.assertEqual(len(groups), 1)
        self.assertEqual(groups[0]["lowest_price"], 100.0)
        self.assertEqual(groups[0]["lowest_shop"], {"name": "Example Shop", "public_shop_id": "7"})
        fields = product_price_fields(groups, "Cursor")
        self.assertEqual(fields["starting_price"], fields["entry_price"])
        self.assertEqual(fields["entry_spec"]["key"], groups[0]["key"])

    def test_chatgpt_pro_entry_cannot_be_selected_from_plus_tier(self):
        base = {"currency": "CNY", "delivery": "代充", "period": "1月", "lowest_shop": {"name": "Shop", "public_shop_id": "1"},
                "shop_count": 1, "listing_count": 1, "spec": {"region": [], "promotion": []}}
        groups = [dict(base, key="plus", label="1月 / plus / 代充", tier="plus", lowest_price=99),
                  dict(base, key="pro100", label="1月 / pro100 / 代充", tier="pro100", lowest_price=618)]
        fields = product_price_fields(groups, "ChatGPT Pro")
        self.assertEqual(fields["starting_price"], 618)
        self.assertEqual(fields["entry_spec"]["key"], "pro100")


if __name__ == "__main__":
    unittest.main()
