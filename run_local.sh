#!/usr/bin/env bash
# 本地后台运行（读取 .env.local 中的 DATABASE_URL；没有则回退 SQLite）
cd "$(dirname "$0")"
[ -f .env.local ] && set -a && . ./.env.local && set +a
exec .venv/bin/uvicorn backend.main:app --host 0.0.0.0 --port "${PORT:-8000}"
