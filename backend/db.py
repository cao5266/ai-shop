import os
from sqlalchemy import create_engine, inspect, text
from sqlalchemy.orm import sessionmaker

DEFAULT_URL = "sqlite:///" + os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), "data", "dev.sqlite3")


def normalize_url(url: str) -> str:
    # 兼容 postgres:// 与 postgresql:// 写法，统一走 psycopg3 驱动
    if url.startswith("postgres://"):
        url = "postgresql://" + url[len("postgres://"):]
    if url.startswith("postgresql://"):
        url = "postgresql+psycopg://" + url[len("postgresql://"):]
    return url


DATABASE_URL = normalize_url(os.environ.get("DATABASE_URL") or DEFAULT_URL)
engine = create_engine(DATABASE_URL, pool_pre_ping=True, future=True)
SessionLocal = sessionmaker(engine, expire_on_commit=False)

# 字段加密后密文更长，旧库里这些列需要放宽为 text（Postgres）。幂等，每次启动只检查。
WIDEN = [("shops", "shop_key"), ("shops", "domain"), ("shops", "all_urls"), ("x_posts", "author"),
         ("promoter_accounts", "username")]


def widen_columns():
    if engine.dialect.name != "postgresql":
        return
    insp = inspect(engine)
    with engine.begin() as c:
        for table, col in WIDEN:
            if table not in insp.get_table_names():
                continue
            info = next((x for x in insp.get_columns(table) if x["name"] == col), None)
            if info is not None and info["type"].__class__.__name__.upper() != "TEXT":
                c.execute(text(f'ALTER TABLE {table} ALTER COLUMN {col} TYPE text USING {col}::text'))


def init_db():
    from .models import Base
    Base.metadata.create_all(engine)
    widen_columns()
