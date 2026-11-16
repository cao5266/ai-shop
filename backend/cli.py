"""命令行：python -m backend.cli init-db | import FILE [--force] | runs | gen-key | encrypt-existing [--dry-run] | verify-encryption"""
import argparse
import sys

from sqlalchemy import select

from .db import SessionLocal, init_db, DATABASE_URL
from .importer import import_file
from .models import CrawlRun


def main():
    ap = argparse.ArgumentParser(prog="backend.cli")
    sub = ap.add_subparsers(dest="cmd", required=True)
    sub.add_parser("init-db", help="创建表（已存在则跳过）")
    p = sub.add_parser("import", help="导入一批采集 JSON（首次导入与每日增量同一入口）")
    p.add_argument("file")
    p.add_argument("--force", action="store_true", help="文件内容与已导入过的相同时仍强制导入")
    sub.add_parser("runs", help="列出最近的 crawl_runs")
    sub.add_parser("gen-key", help="生成一个 FIELD_ENCRYPTION_KEY")
    p = sub.add_parser("encrypt-existing", help="把库里现有的明文敏感字段加密（幂等）")
    p.add_argument("--dry-run", action="store_true", help="只统计，不修改")
    sub.add_parser("verify-encryption", help="检查敏感列是否还有明文（应全为 0）")
    a = ap.parse_args()
    if a.cmd == "gen-key":
        from .fieldcrypt import generate_key
        print(generate_key())
        return
    init_db()
    if a.cmd == "encrypt-existing":
        from .encrypt_existing import run
        for k, (total, todo) in run(a.dry_run).items():
            print(f"{k}: 共 {total} 行，{'需加密' if a.dry_run else '已加密'} {todo} 行")
        return
    if a.cmd == "verify-encryption":
        from .encrypt_existing import verify
        res = verify()
        for k, n in res.items():
            print(f"{k}: 明文 {n} 行")
        sys.exit(1 if any(res.values()) else 0)
    if a.cmd == "init-db":
        print("OK 表已就绪：", DATABASE_URL.split("@")[-1])
    elif a.cmd == "import":
        with SessionLocal() as s:
            try:
                r = import_file(s, a.file, force=a.force)
            except ValueError as e:
                print("错误：", e, file=sys.stderr)
                sys.exit(2)
            print(f"crawl_run #{r.id} 成功：批内店铺 {r.shops_in_batch}，新增店铺 {r.shops_new}，"
                  f"更新店铺 {r.shops_updated}，新增报价 {r.prices_new}，报价变动 {r.prices_changed}，新增帖子 {r.posts_new}")
    elif a.cmd == "runs":
        with SessionLocal() as s:
            for r in s.scalars(select(CrawlRun).order_by(CrawlRun.id.desc()).limit(20)):
                print(r.id, r.status, r.finished_at, r.source_generated_at, f"batch={r.shops_in_batch} new={r.shops_new}")


if __name__ == "__main__":
    main()
