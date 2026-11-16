import datetime as dt
import json
import os
import unittest
from decimal import Decimal
from unittest.mock import patch

from fastapi import FastAPI
from fastapi.testclient import TestClient
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from sqlalchemy.pool import StaticPool
from types import SimpleNamespace

from . import api_v4
from .models import Base, CrawlRun, Listing, Product, Shop, ShopCrawlResult, ShopProduct
from .secure import secure_ctx


class _TestContext:
    def seal(self, value):
        return value


class CatalogApiTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.engine = create_engine("sqlite://", connect_args={"check_same_thread": False}, poolclass=StaticPool)
        Base.metadata.create_all(cls.engine)
        cls.factory = sessionmaker(cls.engine, expire_on_commit=False)
        now = dt.datetime.now(dt.timezone.utc)
        with cls.factory() as s:
            run = CrawlRun(started_at=now, finished_at=now, status="success", shops_in_batch=1)
            s.add(run)
            s.flush()
            product = Product(name="Cursor", sort_order=1)
            muse = Product(name="Muse", sort_order=2)
            x_member = Product(name="X会员", sort_order=3)
            s.add_all([product, muse, x_member])
            s.flush()
            shop = Shop(shop_key="example.test", name="Example", domain="example.test", platform_type="test",
                        primary_url="https://example.test", n_posts=0, n_accounts=0, risk_level="中",
                        first_seen_at=now, last_seen_at=now, first_seen_run_id=run.id, last_seen_run_id=run.id)
            s.add(shop)
            s.flush()
            second = Shop(shop_key="lowest.test", name="Lowest shop", domain="lowest.test", platform_type="test",
                          primary_url="https://lowest.test", n_posts=0, n_accounts=0, risk_level="中",
                          first_seen_at=now, last_seen_at=now, first_seen_run_id=run.id, last_seen_run_id=run.id)
            s.add(second)
            s.flush()
            blocked = Shop(shop_key="captcha.test", name="Verification shop", domain="captcha.test", platform_type="test",
                           primary_url="https://captcha.test", n_posts=0, n_accounts=0, risk_level="中",
                           first_seen_at=now, last_seen_at=now, first_seen_run_id=run.id, last_seen_run_id=run.id)
            s.add(blocked)
            s.flush()
            cls.blocked_shop_id = blocked.id
            s.add(ShopCrawlResult(shop_id=blocked.id, crawl_run_id=run.id,
                                  result={"status": "failed", "retry_result": "需验证，暂无报价",
                                          "reason": "Page.goto https://captcha.test/private Call log: internal diagnostics"}))
            literal = Shop(shop_key="literal.test", name="Literal%_Store", domain="literal.test", platform_type="test",
                           primary_url="https://literal.test", n_posts=0, n_accounts=0, risk_level="低",
                           first_seen_at=now, last_seen_at=now, first_seen_run_id=run.id, last_seen_run_id=run.id)
            s.add(literal)
            s.flush()
            for i in range(105):
                if i == 0:
                    spec = {"key": "monthly-plus", "label": "1月 / plus / 代充", "duration": "30天", "tier": ["PLUS"],
                            "quota": ["10 亿 TOKEN"], "region": [], "delivery": "直充", "incomplete": False}
                elif i == 1:
                    spec = {"key": "month-card-plus", "label": "月卡 / plus / 代充", "duration": "月卡", "tier": ["plus"],
                            "quota": ["10亿token"], "region": [], "delivery": "代充", "incomplete": False}
                else:
                    spec = {"key": f"spec-{i}", "label": f"规格 {i}", "duration": "1月", "tier": ["pro"],
                            "quota": [f"{i} tokens"], "region": [], "delivery": "代充", "incomplete": False}
                s.add(Listing(shop_id=shop.id, product_id=product.id, listing_key=f"listing-{i}",
                              title=f"Cursor Pro 规格 {i}", price=Decimal(i + 10), currency="CNY",
                              url=f"https://example.test/goods/{i}", category="AI", spec=spec,
                              spec_key=f"spec-{i}", risk="中", source_url="https://example.test",
                              active=True, observed_at=now, last_run_id=run.id))
            s.add(Listing(shop_id=second.id, product_id=product.id, listing_key="listing-alias-low",
                          title="Cursor Plus 月卡代充", price=Decimal("5"), currency="CNY",
                          url="https://lowest.test/goods/alias", category="AI",
                          spec={"duration": "1个月", "tier": ["plus"], "quota": ["10亿 TOKEN"], "region": [],
                                "delivery": "充值", "incomplete": False}, spec_key="alias-extra", risk="中",
                          source_url="https://lowest.test", active=True, observed_at=now, last_run_id=run.id))
            for listing_key, price, title in [("listing-alias-outlier", "0.5", "Cursor Plus 月卡代充"),
                                               ("listing-alias-car-share", "1", "Cursor Plus 月卡拼车共享车位")]:
                s.add(Listing(shop_id=shop.id, product_id=product.id, listing_key=listing_key,
                              title=title, price=Decimal(price), currency="CNY",
                              url=f"https://example.test/{listing_key}", category="AI",
                              spec={"duration": "1月", "tier": ["plus"], "quota": ["10亿token"], "region": [],
                                    "delivery": "代充", "incomplete": False}, spec_key=listing_key, risk="中",
                              source_url="https://example.test", active=True, observed_at=now, last_run_id=run.id))
            s.add(Listing(shop_id=shop.id, product_id=product.id, listing_key="mismatch-chatgpt",
                          title="ChatGPT 登录教程（非 Cursor 商品）", price=Decimal("0.5"), currency="CNY",
                          url="https://example.test/tutorial", category="AI", spec={"duration": "1月", "tier": ["plus"],
                          "quota": [], "region": [], "delivery": "代充", "incomplete": False}, spec_key="mismatch",
                          risk="低", source_url="https://example.test", active=True, observed_at=now, last_run_id=run.id))
            s.add(Listing(shop_id=blocked.id, product_id=product.id, listing_key="blocked-low",
                          title="Cursor Plus 月卡代充", price=Decimal("0.1"), currency="CNY",
                          url="https://captcha.test/goods", category="AI", spec={"duration": "1月", "tier": ["plus"],
                          "quota": ["10亿token"], "region": [], "delivery": "代充", "incomplete": False}, spec_key="blocked",
                          risk="低", source_url="https://captcha.test", active=True, observed_at=now, last_run_id=run.id))
            for product_row, label, price in [(muse, "Muse Token 1月成品号", "18"),
                                              (x_member, "X会员 1月兑换码", "28")]:
                s.add(Listing(shop_id=shop.id, product_id=product_row.id, listing_key=f"{label}-listing",
                              title=label, price=Decimal(price), currency="CNY", url=f"https://example.test/{product_row.name}",
                              category="AI", spec={"duration": "1月", "tier": ["plus"], "quota": [], "region": [],
                              "delivery": "成品号" if product_row is muse else "兑换码", "incomplete": False},
                              spec_key=f"{product_row.name}-spec", risk="中", source_url="https://example.test",
                              active=True, observed_at=now, last_run_id=run.id))
                s.add(ShopProduct(shop_id=shop.id, product_id=product_row.id, first_seen_at=now, last_seen_at=now))
            s.add(ShopProduct(shop_id=shop.id, product_id=product.id, first_seen_at=now, last_seen_at=now))
            s.commit()
        cls.app = FastAPI()
        cls.app.include_router(api_v4.router)
        cls.app.dependency_overrides[secure_ctx] = lambda: _TestContext()
        cls.session_patch = patch.object(api_v4, "SessionLocal", cls.factory)
        cls.session_patch.start()
        cls.client = TestClient(cls.app)

    @classmethod
    def tearDownClass(cls):
        cls.client.close()
        cls.session_patch.stop()
        cls.engine.dispose()

    def test_catalog_specs_pages_with_default_and_maximum_page_size(self):
        first = self.client.get("/api/v4/catalog/Cursor/specs").json()
        self.assertEqual(first["n_specs"], 104)
        self.assertEqual(first["page"], 1)
        self.assertEqual(first["page_size"], 50)
        self.assertEqual(first["total_pages"], 3)
        self.assertEqual(len(first["specs"]), 50)

        second = self.client.get("/api/v4/catalog/Cursor/specs?page=2&page_size=100").json()
        self.assertEqual(second["page_size"], 100)
        self.assertEqual(second["total_pages"], 2)
        self.assertEqual(len(second["specs"]), 4)
        alias = next(x for x in first["specs"] if x["tier"] == "plus")
        self.assertEqual(alias["period"], "1月")
        self.assertEqual(alias["delivery"], "代充")
        self.assertEqual(alias["lowest_price"], 5.0)
        self.assertEqual(alias["lowest_shop"], {"name": "Lowest shop", "public_shop_id": "2"})
        self.assertEqual(alias["shop_count"], 2)
        self.assertEqual(alias["listing_count"], 5)
        self.assertNotIn("shop_key", alias["lowest_shop"])

    def test_tools_endpoint_is_paginated_and_entry_key_matches_specs(self):
        first = self.client.get("/api/v4/tools/Cursor").json()
        self.assertEqual(first["page_size"], 50)
        self.assertEqual(first["total"], 104)
        self.assertEqual(first["total_pages"], 3)
        self.assertEqual(len(first["specs"]), 50)
        second = self.client.get("/api/v4/tools/Cursor?page=2&page_size=100").json()
        self.assertEqual(len(second["specs"]), 4)
        self.assertEqual(second["total"], 104)
        self.assertEqual(self.client.get("/api/v4/tools/Cursor?page=0").status_code, 422)
        self.assertEqual(self.client.get("/api/v4/tools/Cursor?page_size=101").status_code, 422)
        catalog = self.client.get("/api/v4/catalog/Cursor/specs?page_size=100").json()
        self.assertIn(first["entry_spec"]["key"], {x["key"] for x in catalog["specs"]})

    def test_catalog_paginates_cached_groups_without_rebuilding_each_page(self):
        api_v4._cache.clear()
        with patch.object(api_v4, "spec_groups", wraps=api_v4.spec_groups) as grouping:
            first = self.client.get("/api/v4/catalog/Cursor/specs?page=1&page_size=1").json()
            second = self.client.get("/api/v4/catalog/Cursor/specs?page=2&page_size=1").json()
        self.assertEqual(len(first["specs"]), 1)
        self.assertEqual(len(second["specs"]), 1)
        self.assertEqual(first["n_specs"], second["n_specs"])
        self.assertEqual(grouping.call_count, 1)

    def test_home_tool_and_catalog_share_price_and_entry_spec(self):
        home = self.client.get("/api/v4/home").json()
        with self.factory() as s:
            self.assertEqual(len(home["tools"]), len(api_v4.groups_of(s)))
        for name in ("Cursor", "Muse", "X会员"):
            with self.subTest(product=name):
                home_item = next(x for x in home["tools"] if x["name"] == name)
                detail = self.client.get(f"/api/v4/tools/{name}").json()
                catalog = self.client.get(f"/api/v4/catalog/{name}/specs?page_size=100").json()
                self.assertEqual(home_item["starting_price"], detail["starting_price"])
                self.assertEqual(home_item["starting_price"], catalog["starting_price"])
                self.assertEqual(home_item["price"], detail["price"])
                self.assertEqual(home_item["entry_spec"], detail["entry_spec"])
                self.assertEqual(home_item["entry_price"], detail["entry_price"])
                self.assertEqual(home_item["entry_shop_count"], detail["entry_shop_count"])
                self.assertEqual(detail["starting_price"], min(x["lowest_price"] for x in catalog["specs"]))
                self.assertEqual(detail["specs"][0]["lowest_shop"].keys(), {"name", "public_shop_id"})

    def test_outlier_prices_are_retained_marked_and_excluded_from_lowest(self):
        detail = self.client.get("/api/v4/tools/Cursor").json()
        alias = next(g for g in detail["specs"] if g["tier"] == "plus")
        self.assertEqual(alias["lowest_price"], 5.0)
        offers = self.client.get(f"/api/v4/tools/Cursor/offers?spec={alias['key']}&size=30").json()
        flagged = [x for x in offers["items"] if x["price_anomaly"]]
        self.assertGreaterEqual(len(flagged), 2)
        self.assertTrue(all(x["price"] not in (5.0,) for x in flagged))
        self.assertEqual(sum(x["lowest"] for x in offers["items"]), 1)

    def test_home_contains_full_product_directory_including_empty_products(self):
        body = self.client.get("/api/v4/home").json()
        with self.factory() as s:
            self.assertEqual(len(body["tools"]), len(api_v4.groups_of(s)))
        self.assertIn("Copilot", {x["name"] for x in body["tools"]})
        self.assertIn("X会员", {x["name"] for x in body["tools"]})
        self.assertEqual(next(x for x in body["tools"] if x["name"] == "Copilot")["status"], "暂无报价")
        self.assertEqual(self.client.get("/api/v4/catalog/Copilot/specs").status_code, 200)

    def test_periods_normalize_and_missing_periods_share_one_bucket(self):
        cases = [
            ({"duration": "30天"}, "1月"), ({"duration": "月卡"}, "1月"),
            ({"duration": "3个月"}, "3月"), ({"duration": "一年"}, "1年"),
            ({"duration": "90天"}, "3月"), ({"duration": "终身"}, "永久"),
            ({"duration": "5次卡"}, "5次"), ({}, "未注明周期"),
        ]
        for spec, expected in cases:
            with self.subTest(spec=spec):
                row = SimpleNamespace(spec=spec, title="Claude Pro", product_id=1, currency="CNY")
                self.assertEqual(api_v4._normalized_spec(row)["period"], expected)
        row = SimpleNamespace(spec={}, title="AI-gemini pro 学生认证可得12个月一次卡", product_id=1, currency="CNY")
        self.assertEqual(api_v4._normalized_spec(row)["period"], "1年")
        a = SimpleNamespace(spec={"tier": ["pro"], "delivery": "代充"}, title="Codex Pro 100", product_id=1, currency="CNY")
        b = SimpleNamespace(spec={"tier": ["pro"], "delivery": "直充"}, title="Codex Pro 100 官方", product_id=1, currency="CNY")
        self.assertEqual(api_v4._normalized_spec(a)["key"], api_v4._normalized_spec(b)["key"])

    def test_gemini_listing_is_not_counted_as_claude_pro(self):
        from crawler.normalize import comparison_exclusion
        reason = comparison_exclusion("Gemini Ultra 5x/20x 成品账号", "Claude Pro", {"delivery": "成品号"}, 1)
        self.assertTrue(reason)

    def test_catalog_specs_rejects_out_of_range_parameters(self):
        self.assertEqual(self.client.get("/api/v4/catalog/Cursor/specs?page=0").status_code, 422)
        self.assertEqual(self.client.get("/api/v4/catalog/Cursor/specs?page_size=101").status_code, 422)
        self.assertEqual(self.client.get("/api/v4/catalog/Cursor/specs?page_size=0").status_code, 422)

    def test_tool_note_is_public_status_without_internal_sources(self):
        response = self.client.get("/api/v4/tools/Cursor")
        self.assertEqual(response.status_code, 200)
        body = response.json()
        self.assertEqual(body["note"], api_v4.PRODUCT_NOTES["Cursor"]["status"])
        payload = json.dumps(body, ensure_ascii=False)
        self.assertNotIn("reason", body)
        self.assertNotIn("urls", payload)
        self.assertNotIn("loranai.top", payload)
        self.assertNotIn("16688.com.cn", payload)

    def test_shop_detail_returns_fixed_crawl_status_without_reason(self):
        response = self.client.get(f"/api/v4/shops/{self.blocked_shop_id}")
        self.assertEqual(response.status_code, 200)
        body = response.json()
        self.assertEqual(body["crawl_status"], "需验证")
        payload = json.dumps(body, ensure_ascii=False)
        self.assertNotIn("reason", payload)
        self.assertNotIn("Call log", payload)
        self.assertNotIn("https://captcha.test/private", payload)

    def test_shop_search_escapes_percent_and_underscore(self):
        self.assertEqual(self.client.get("/api/v4/shops?q=%25").json()["total"], 1)
        self.assertEqual(self.client.get("/api/v4/shops?q=_").json()["total"], 1)


if __name__ == "__main__":
    unittest.main()
