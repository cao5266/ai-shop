"""数据库表结构（SQLAlchemy 2.0）。SQLite 与 PostgreSQL 通用。"""
from __future__ import annotations
import datetime as dt
from sqlalchemy import (BigInteger, Boolean, DateTime, ForeignKey, Index, Integer, JSON, Numeric,
                        String, Text, UniqueConstraint)
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.orm import DeclarativeBase, Mapped, mapped_column

JSONType = JSON().with_variant(JSONB(), "postgresql")
PK = BigInteger().with_variant(Integer(), "sqlite")  # SQLite 仅 INTEGER 主键可自增


def utcnow() -> dt.datetime:
    return dt.datetime.now(dt.timezone.utc)


class Base(DeclarativeBase):
    pass


class CrawlRun(Base):
    """每次导入（= 每次采集结果入库）一条记录。"""
    __tablename__ = "crawl_runs"
    id: Mapped[int] = mapped_column(PK, primary_key=True, autoincrement=True)
    started_at: Mapped[dt.datetime] = mapped_column(DateTime(timezone=True), default=utcnow)
    finished_at: Mapped[dt.datetime | None] = mapped_column(DateTime(timezone=True))
    status: Mapped[str] = mapped_column(String(16), default="running")  # running/success/failed
    source_file: Mapped[str | None] = mapped_column(String(500))
    file_sha256: Mapped[str | None] = mapped_column(String(64), index=True)
    source_generated_at: Mapped[str | None] = mapped_column(String(100))  # 采集端写的 generated_at 原文
    scope: Mapped[dict | None] = mapped_column(JSONType)                  # 采集范围/局限说明
    shops_in_batch: Mapped[int] = mapped_column(Integer, default=0)
    shops_new: Mapped[int] = mapped_column(Integer, default=0)
    shops_updated: Mapped[int] = mapped_column(Integer, default=0)
    prices_new: Mapped[int] = mapped_column(Integer, default=0)
    prices_changed: Mapped[int] = mapped_column(Integer, default=0)
    posts_new: Mapped[int] = mapped_column(Integer, default=0)
    error: Mapped[str | None] = mapped_column(Text)


class Shop(Base):
    __tablename__ = "shops"
    id: Mapped[int] = mapped_column(PK, primary_key=True, autoincrement=True)
    shop_key: Mapped[str] = mapped_column(String(400), unique=True)
    name: Mapped[str] = mapped_column(String(400))
    domain: Mapped[str] = mapped_column(String(255), index=True)
    platform_type: Mapped[str] = mapped_column(String(50), index=True)
    primary_url: Mapped[str] = mapped_column(Text)
    final_url: Mapped[str | None] = mapped_column(Text)
    all_urls: Mapped[list | None] = mapped_column(JSONType)
    http_code: Mapped[str | None] = mapped_column(String(10))
    page_status: Mapped[str | None] = mapped_column(Text)
    page_readable: Mapped[bool] = mapped_column(Boolean, default=False)
    page_products: Mapped[str | None] = mapped_column(Text)
    entity_titles: Mapped[str | None] = mapped_column(Text)
    n_posts: Mapped[int] = mapped_column(Integer, default=0, index=True)
    n_accounts: Mapped[int] = mapped_column(Integer, default=0)
    example_post_url: Mapped[str | None] = mapped_column(Text)
    notes: Mapped[str | None] = mapped_column(Text)
    risk_level: Mapped[str] = mapped_column(String(4), default="中", index=True)  # 高/中/低
    min_price: Mapped[float | None] = mapped_column(Numeric(12, 2), index=True)   # 冗余字段，导入时算好
    first_seen_at: Mapped[dt.datetime] = mapped_column(DateTime(timezone=True))
    last_seen_at: Mapped[dt.datetime] = mapped_column(DateTime(timezone=True))
    first_seen_run_id: Mapped[int] = mapped_column(ForeignKey("crawl_runs.id"))
    last_seen_run_id: Mapped[int] = mapped_column(ForeignKey("crawl_runs.id"))


class Product(Base):
    __tablename__ = "products"
    id: Mapped[int] = mapped_column(PK, primary_key=True, autoincrement=True)
    name: Mapped[str] = mapped_column(String(100), unique=True)
    family: Mapped[str | None] = mapped_column(String(50))
    sort_order: Mapped[int] = mapped_column(Integer, default=999)


class ShopProduct(Base):
    __tablename__ = "shop_products"
    shop_id: Mapped[int] = mapped_column(ForeignKey("shops.id", ondelete="CASCADE"), primary_key=True)
    product_id: Mapped[int] = mapped_column(ForeignKey("products.id"), primary_key=True)
    first_seen_at: Mapped[dt.datetime] = mapped_column(DateTime(timezone=True))
    last_seen_at: Mapped[dt.datetime] = mapped_column(DateTime(timezone=True))


class Price(Base):
    """某店某报价的「当前」状态；变动历史见 price_history。"""
    __tablename__ = "prices"
    __table_args__ = (UniqueConstraint("shop_id", "source", "price_key"),
                      Index("ix_prices_product", "product_id", "amount"))
    id: Mapped[int] = mapped_column(PK, primary_key=True, autoincrement=True)
    shop_id: Mapped[int] = mapped_column(ForeignKey("shops.id", ondelete="CASCADE"), index=True)
    product_id: Mapped[int | None] = mapped_column(ForeignKey("products.id"))
    source: Mapped[str] = mapped_column(String(8))          # post=X 帖文案；page=店铺页面
    price_key: Mapped[str] = mapped_column(String(200))     # 去重键：标签（重复则加 #2…）；页面价格用金额文本
    label: Mapped[str] = mapped_column(String(200), default="")
    amount: Mapped[float] = mapped_column(Numeric(12, 2))
    currency: Mapped[str] = mapped_column(String(3), default="CNY")
    first_seen_at: Mapped[dt.datetime] = mapped_column(DateTime(timezone=True))
    last_seen_at: Mapped[dt.datetime] = mapped_column(DateTime(timezone=True))
    last_run_id: Mapped[int] = mapped_column(ForeignKey("crawl_runs.id"))


class PriceHistory(Base):
    """仅在首次出现或金额变化时追加一行。"""
    __tablename__ = "price_history"
    id: Mapped[int] = mapped_column(PK, primary_key=True, autoincrement=True)
    price_id: Mapped[int] = mapped_column(ForeignKey("prices.id", ondelete="CASCADE"), index=True)
    amount: Mapped[float] = mapped_column(Numeric(12, 2))
    observed_at: Mapped[dt.datetime] = mapped_column(DateTime(timezone=True))
    crawl_run_id: Mapped[int] = mapped_column(ForeignKey("crawl_runs.id"))


class XPost(Base):
    """kind: ref=仅有帖子 ID；example=示例帖（有链接与作者）；sample=抽样文案（无 ID）。"""
    __tablename__ = "x_posts"
    __table_args__ = (UniqueConstraint("shop_id", "uid"),)
    id: Mapped[int] = mapped_column(PK, primary_key=True, autoincrement=True)
    shop_id: Mapped[int] = mapped_column(ForeignKey("shops.id", ondelete="CASCADE"), index=True)
    uid: Mapped[str] = mapped_column(String(100))           # post_id 或 txt:<hash>
    post_id: Mapped[str | None] = mapped_column(String(32))
    url: Mapped[str | None] = mapped_column(Text)
    author: Mapped[str | None] = mapped_column(String(100))
    text: Mapped[str | None] = mapped_column(Text)
    kind: Mapped[str] = mapped_column(String(8), default="ref")
    first_seen_at: Mapped[dt.datetime] = mapped_column(DateTime(timezone=True))
    last_seen_at: Mapped[dt.datetime] = mapped_column(DateTime(timezone=True))
    last_run_id: Mapped[int] = mapped_column(ForeignKey("crawl_runs.id"))


class PromoterAccount(Base):
    __tablename__ = "promoter_accounts"
    shop_id: Mapped[int] = mapped_column(ForeignKey("shops.id", ondelete="CASCADE"), primary_key=True)
    username: Mapped[str] = mapped_column(String(100), primary_key=True)
    post_count: Mapped[int | None] = mapped_column(Integer)
    created_year: Mapped[int | None] = mapped_column(Integer)
    followers: Mapped[int | None] = mapped_column(Integer)
    first_seen_at: Mapped[dt.datetime] = mapped_column(DateTime(timezone=True))
    last_seen_at: Mapped[dt.datetime] = mapped_column(DateTime(timezone=True))


class RiskFlag(Base):
    __tablename__ = "risk_flags"
    __table_args__ = (UniqueConstraint("shop_id", "detail"),)
    id: Mapped[int] = mapped_column(PK, primary_key=True, autoincrement=True)
    shop_id: Mapped[int] = mapped_column(ForeignKey("shops.id", ondelete="CASCADE"), index=True)
    code: Mapped[str] = mapped_column(String(30))     # shared_account/topup/no_warranty/matrix/unstable/other
    label: Mapped[str] = mapped_column(String(40))    # 短标签
    severity: Mapped[str] = mapped_column(String(4))  # 高/中/提示
    detail: Mapped[str] = mapped_column(Text)         # 采集端原文
    active: Mapped[bool] = mapped_column(Boolean, default=True)
    first_seen_at: Mapped[dt.datetime] = mapped_column(DateTime(timezone=True))
    last_seen_at: Mapped[dt.datetime] = mapped_column(DateTime(timezone=True))


class ShopSnapshot(Base):
    """每次导入时每家店的关键指标快照，用于看趋势。"""
    __tablename__ = "shop_snapshots"
    __table_args__ = (UniqueConstraint("shop_id", "crawl_run_id"),)
    id: Mapped[int] = mapped_column(PK, primary_key=True, autoincrement=True)
    shop_id: Mapped[int] = mapped_column(ForeignKey("shops.id", ondelete="CASCADE"), index=True)
    crawl_run_id: Mapped[int] = mapped_column(ForeignKey("crawl_runs.id"), index=True)
    n_posts: Mapped[int] = mapped_column(Integer)
    n_accounts: Mapped[int] = mapped_column(Integer)
    http_code: Mapped[str | None] = mapped_column(String(10))
    risk_level: Mapped[str] = mapped_column(String(4))


class Listing(Base):
    __tablename__ = "listings"
    __table_args__ = (UniqueConstraint("shop_id", "listing_key"),)
    id: Mapped[int] = mapped_column(PK, primary_key=True, autoincrement=True)
    shop_id: Mapped[int] = mapped_column(ForeignKey("shops.id"), index=True)
    product_id: Mapped[int | None] = mapped_column(ForeignKey("products.id"), index=True)
    listing_key: Mapped[str] = mapped_column(String(64))
    title: Mapped[str] = mapped_column(Text)
    price: Mapped[float] = mapped_column(Numeric(14, 4))
    currency: Mapped[str] = mapped_column(String(8), default="CNY")
    url: Mapped[str] = mapped_column(Text)
    category: Mapped[str | None] = mapped_column(Text)
    image: Mapped[str | None] = mapped_column(Text)
    spec: Mapped[dict] = mapped_column(JSONType)
    spec_key: Mapped[str] = mapped_column(String(32), index=True)
    stock: Mapped[str | None] = mapped_column(String(100))
    sales: Mapped[str | None] = mapped_column(String(100))
    risk: Mapped[str] = mapped_column(String(8))
    source_url: Mapped[str] = mapped_column(Text)
    active: Mapped[bool] = mapped_column(Boolean, default=True)
    observed_at: Mapped[dt.datetime] = mapped_column(DateTime(timezone=True))
    last_run_id: Mapped[int] = mapped_column(ForeignKey("crawl_runs.id"))


class ListingPriceHistory(Base):
    __tablename__ = "listing_price_history"
    id: Mapped[int] = mapped_column(PK, primary_key=True, autoincrement=True)
    listing_id: Mapped[int] = mapped_column(ForeignKey("listings.id"), index=True)
    price: Mapped[float] = mapped_column(Numeric(14, 4))
    currency: Mapped[str] = mapped_column(String(8))
    observed_at: Mapped[dt.datetime] = mapped_column(DateTime(timezone=True))
    crawl_run_id: Mapped[int] = mapped_column(ForeignKey("crawl_runs.id"))


class ShopCrawlResult(Base):
    __tablename__ = "shop_crawl_results"
    id: Mapped[int] = mapped_column(PK, primary_key=True, autoincrement=True)
    shop_id: Mapped[int] = mapped_column(ForeignKey("shops.id"), index=True)
    crawl_run_id: Mapped[int] = mapped_column(ForeignKey("crawl_runs.id"))
    result: Mapped[dict] = mapped_column(JSONType)
