#!/bin/bash
# 有界、分块、可重试部署；默认发布 git HEAD，可显式指定已提交版本。
set -euo pipefail
APP_DIR=${AI_SHOPS_APP_DIR:-$(cd "$(dirname "$0")/.." && pwd)}
KEY=${AI_SHOPS_SSH_KEY:-$HOME/.ssh/aishops.pem}
HOST=${AI_SHOPS_SSH_HOST:-ubuntu@101.34.76.198}
REMOTE=${AI_SHOPS_REMOTE_DIR:-/opt/ai_shops}
REF=${AI_SHOPS_DEPLOY_REF:-HEAD}
COMMIT=$(git -C "$APP_DIR" rev-parse "$REF^{commit}")
[[ "$REMOTE" =~ ^/[a-zA-Z0-9_/-]+$ ]] || exit 2
SSH=(-i "$KEY" -o BatchMode=yes -o IdentitiesOnly=yes -o StrictHostKeyChecking=accept-new -o ConnectTimeout=10 -o ServerAliveInterval=5 -o ServerAliveCountMax=3)
run_remote() { timeout --kill-after=5 "$1" ssh "${SSH[@]}" "$HOST" "$2"; }
tmp=$(mktemp -d /tmp/opencode/aishops-release.XXXXXX)
trap 'rm -rf "$tmp"' EXIT
echo "发布提交 $COMMIT"
run_remote 25 'echo SSH连接正常; df -h /opt/ai_shops'
timeout 20 git -C "$APP_DIR" archive --format=tar.gz -o "$tmp/release.tar.gz" "$COMMIT"
hash=$(sha256sum "$tmp/release.tar.gz"); hash=${hash%% *}
timeout 10 split -b 131072 -d -a 4 "$tmp/release.tar.gz" "$tmp/part-"
stage="/tmp/aishops-release-$COMMIT"
run_remote 25 "mkdir -p '$stage/parts'; echo 分块目录已就绪"
parts=("$tmp"/part-*)
i=0
for part in "${parts[@]}"; do
  i=$((i+1)); name=${part##*/}
  digest=$(sha256sum "$part"); digest=${digest%% *}
  ok=0
  for attempt in 1 2 3; do
    echo "上传分块 $i/${#parts[@]}，尝试 $attempt：$name"
    if timeout --kill-after=5 35 scp -O -l 512 "${SSH[@]}" "$part" "$HOST:$stage/parts/$name" &&
       run_remote 25 "echo '$digest  $stage/parts/$name' | sha256sum -c -"; then ok=1; break; fi
    echo "分块失败，重新连接"
  done
  [ "$ok" = 1 ] || { echo '连续失败，停止发布'; exit 1; }
done
echo '合并、校验并同步已提交源码'
run_remote 60 "set -e; cat '$stage'/parts/part-* > '$stage/release.tar.gz'; echo '$hash  $stage/release.tar.gz' | sha256sum -c -; mkdir -p '$stage/source'; tar -xzf '$stage/release.tar.gz' -C '$stage/source'; rsync -a --delete --exclude '.env' --exclude 'incoming/' --exclude 'backups/' --exclude 'logs/' --exclude 'bin/' --exclude 'shots/' '$stage/source/' '$REMOTE/'; echo 源码同步完成"
echo '重建并启动容器（最长240秒）'
run_remote 250 "set -e; cd '$REMOTE'; timeout 240 docker compose up -d --build; docker compose ps; echo '$COMMIT' > logs/deployed_commit"
echo '检查健康状态与数据库记录'
run_remote 30 "set -e; curl -fsS --max-time 10 http://127.0.0.1:8000/healthz; cd '$REMOTE'; docker compose exec -T db psql -U aishops -d aishops -Atc 'select id,status,shops_in_batch from crawl_runs order by id; select count(*) from shops; select count(*) from listings;'; cat logs/deployed_commit"
echo "发布成功：$COMMIT"
