import copy
import unittest
from sqlalchemy import create_engine, select, func
from sqlalchemy.orm import Session
from backend.models import Base, Listing, ListingPriceHistory
from backend.importer import import_data
from .normalize import classify, specification, listing, representative_rank


class PipelineTests(unittest.TestCase):
    def test_specs_keep_duration_quota_delivery_separate(self):
        self.assertNotEqual(specification('Cursor 年卡 成品号')['key'], specification('Cursor 月卡 成品号')['key'])
        self.assertNotEqual(specification('Muse 10亿token 成品号')['key'], specification('Muse 1亿token 成品号')['key'])
        self.assertIsNone(specification('Muse 10亿token 质保30天')['duration'])
        self.assertEqual(classify('【官网正价直充】Plus 官方充值30天'), 'ChatGPT Plus')
        self.assertIsNone(classify('Gmail 谷歌邮箱'))
        for title in ['Netflix Premium 4K 独享 30天 全保', 'MiniMax M Plan Go月度会员', 'Grok 普号', 'Cursor 接🐎', 'Codex 注册号', 'Gemini 接码', 'Grok+Cursor 三合一 Plus 月卡']:
            self.assertIsNone(classify(title), title)
        self.assertEqual(classify('X(推特）蓝标会员'), 'X会员')
        self.assertIsNone(specification('Muse 10亿token 质保一个月')['duration'])
        plus = {'product': 'Grok Plus', 'spec': specification('Grok Plus 月卡 充值'), 'n_prices': 2}
        ultra = {'product': 'Grok Ultra', 'spec': specification('Grok Ultra 年卡 充值'), 'n_prices': 100}
        self.assertLess(representative_rank(plus), representative_rank(ultra))

    def test_history_idempotence_price_change_and_failed_crawl(self):
        engine = create_engine('sqlite://')
        Base.metadata.create_all(engine)
        row = listing('Cursor 月卡 成品号', '12.50', 'https://example.org/goods/1')
        row.update(listing_key='test', observed_at='2026-11-16T00:00:00+00:00')
        data = {'shops': [{'shop_key': 'example.org', 'primary_url': 'https://example.org',
                           'crawl': {'status': 'success', 'complete': True}, 'listings': [row]}]}
        with Session(engine) as s:
            import_data(s, data)
            import_data(s, data)
            self.assertEqual(s.scalar(select(func.count(Listing.id))), 1)
            self.assertEqual(s.scalar(select(func.count(ListingPriceHistory.id))), 1)
            row['price'] = '15'
            import_data(s, data)
            self.assertEqual(s.scalar(select(func.count(ListingPriceHistory.id))), 2)
            failed = copy.deepcopy(data)
            failed['shops'][0].update(crawl={'status': 'failed'}, listings=[])
            import_data(s, failed)
            self.assertTrue(s.scalar(select(Listing)).active)
            empty = copy.deepcopy(data)
            empty['shops'][0].update(crawl={'status': 'empty', 'complete': True}, listings=[])
            import_data(s, empty)
            self.assertFalse(s.scalar(select(Listing)).active)


if __name__ == '__main__': unittest.main()
