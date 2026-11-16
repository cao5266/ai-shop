#!/bin/bash
set -euo pipefail
APP_DIR=$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)
ROOT_DIR=$(dirname "$APP_DIR")
REPORT_DIR=${AI_SHOPS_REPORT_DIR:-$ROOT_DIR/crawler/reports}
PYTHON=${AI_SHOPS_PYTHON:-$APP_DIR/.venv/bin/python}
export PYTHONPATH="$APP_DIR${PYTHONPATH:+:$PYTHONPATH}"
mkdir -p "$REPORT_DIR"
exec 9>"$REPORT_DIR/.daily.lock"
flock -n 9 || { echo '已有每日采集运行中'; exit 1; }
"$PYTHON" -m crawler.run --input "${AI_SHOPS_INPUT:-$ROOT_DIR/shops.json}" --output "$REPORT_DIR" "$@"
DAY=$(TZ=Asia/Shanghai date +%F)
if [ ! -s "$REPORT_DIR/$DAY.json" ]; then
  echo '当日全量文件不存在，停止推送' >&2
  exit 1
fi
if [ "${AI_SHOPS_SKIP_PUSH:-0}" != 1 ]; then
  "$PYTHON" -m crawler.export_import "$REPORT_DIR/$DAY.json" "$REPORT_DIR/$DAY-import.json"
  if bash "$ROOT_DIR/deploy/push_update.sh" "$REPORT_DIR/$DAY-import.json"; then
    echo '线上导入：成功' >> "$REPORT_DIR/$DAY.md"
  else
    echo '线上导入：失败，请检查推送日志并重试导入当日 JSON。' >> "$REPORT_DIR/$DAY.md"
    exit 1
  fi
fi
