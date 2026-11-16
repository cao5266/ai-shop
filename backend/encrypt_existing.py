"""把库里现有的明文敏感字段加密（幂等：已加密的行跳过）。

python -m backend.cli encrypt-existing [--dry-run]
需要先设置 FIELD_ENCRYPTION_KEY。建议先停止导入任务并备份。
"""
from __future__ import annotations
from sqlalchemy import text

from . import fieldcrypt as fc
from .db import engine, init_db

# (表, 主键列, 列, 加密方式)
TARGETS = [
    ("shops", ["id"], "shop_key", "det"), ("shops", ["id"], "domain", "det"),
    ("shops", ["id"], "primary_url", "rand"), ("shops", ["id"], "final_url", "rand"),
    ("shops", ["id"], "all_urls", "rand"), ("shops", ["id"], "example_post_url", "rand"),
    ("shops", ["id"], "notes", "rand"),
    ("listings", ["id"], "url", "rand"), ("listings", ["id"], "source_url", "rand"), ("listings", ["id"], "image", "rand"),
    ("x_posts", ["id"], "url", "rand"), ("x_posts", ["id"], "author", "rand"), ("x_posts", ["id"], "text", "rand"),
    ("promoter_accounts", ["shop_id", "username"], "username", "det"),
]


def run(dry_run: bool = False) -> dict:
    if not fc.enabled():
        raise SystemExit("请先设置 FIELD_ENCRYPTION_KEY（python -m backend.cli gen-key 可生成）")
    init_db()
    report = {}
    with engine.begin() as c:
        for table, pk, col, mode in TARGETS:
            f = fc.enc_det if mode == "det" else fc.enc
            cols = ", ".join(pk + ([col] if col not in pk else []))
            rows = c.execute(text(f"SELECT {cols} FROM {table} WHERE {col} IS NOT NULL AND CAST({col} AS TEXT) <> ''")).mappings().all()
            todo = []
            for r in rows:
                v = r[col]
                v = v if isinstance(v, str) else __import__("json").dumps(v, ensure_ascii=False)
                if v.startswith((fc.P_RAND, fc.P_DET)):
                    continue
                todo.append((r, f(v)))
            report[f"{table}.{col}"] = (len(rows), len(todo))
            if dry_run:
                continue
            for r, new in todo:
                where = " AND ".join(f"{k} = :pk_{k}" for k in pk)
                params = {f"pk_{k}": r[k] for k in pk}
                params["new"] = new
                c.execute(text(f"UPDATE {table} SET {col} = :new WHERE {where}"), params)
    return report


def verify() -> dict:
    """统计每个目标列里仍是明文的行数（应全部为 0）。"""
    out = {}
    with engine.connect() as c:
        for table, pk, col, mode in TARGETS:
            n = c.execute(text(
                f"SELECT count(*) FROM {table} WHERE {col} IS NOT NULL AND CAST({col} AS TEXT) <> '' "
                f"AND CAST({col} AS TEXT) NOT LIKE 'enc1:%' AND CAST({col} AS TEXT) NOT LIKE 'encd:%'")).scalar()
            out[f"{table}.{col}"] = n
    return out
