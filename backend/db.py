import os
from sqlalchemy import create_engine
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


def init_db():
    from .models import Base
    Base.metadata.create_all(engine)
