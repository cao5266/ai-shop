#!/bin/bash
# 经 GitHub 发布：本机把指定提交推到仓库（SSH 走服务器中转），
# 服务器 git pull 后在本机同步到运行目录并重建容器。
# 不在跨境链路上 rsync/scp 整份代码。不会覆盖 .env、incoming/、backups/、logs/、bin/。
set -euo pipefail
APP_DIR=${AI_SHOPS_APP_DIR:-$(cd "$(dirname "$0")/.." && pwd)}
KEY=${AI_SHOPS_SSH_KEY:-$HOME/.ssh/aishops.pem}
HOST=${AI_SHOPS_SSH_HOST:-ubuntu@101.34.76.198}
REMOTE=${AI_SHOPS_REMOTE_DIR:-/opt/ai_shops}
SRC=${AI_SHOPS_SRC_DIR:-/opt/ai_shops-src}
GITHUB_KEY=${AI_SHOPS_GITHUB_KEY:-$HOME/.ssh/aishop_github}
REF=${AI_SHOPS_DEPLOY_REF:-HEAD}
BRANCH=${AI_SHOPS_REMOTE_BRANCH:-main}

COMMIT=$(git -C "$APP_DIR" rev-parse "${REF}^{commit}")
[[ "$REMOTE" =~ ^/[a-zA-Z0-9_/-]+$ ]] || exit 2
[[ "$SRC" =~ ^/[a-zA-Z0-9_/-]+$ ]] || exit 2

SSH=(-i "$KEY" -o BatchMode=yes -o IdentitiesOnly=yes -o StrictHostKeyChecking=accept-new \
  -o ConnectTimeout=15 -o ServerAliveInterval=15 -o ServerAliveCountMax=8)
run_remote() { timeout --kill-after=10 "$1" ssh "${SSH[@]}" "$HOST" "$2"; }

echo "发布提交 $COMMIT"
run_remote 25 'echo SSH连接正常; df -h / | awk "NR==1||/\/$/"'

if git -C "$APP_DIR" remote get-url github >/dev/null 2>&1; then
  remote=github
else
  remote=origin
fi

echo "推送到 GitHub（经服务器中转） $remote $COMMIT:$BRANCH"
export GIT_SSH_COMMAND="ssh -i $GITHUB_KEY -o IdentitiesOnly=yes -o StrictHostKeyChecking=accept-new -o ProxyCommand='ssh -i $KEY -o BatchMode=yes -o IdentitiesOnly=yes -W %h:%p $HOST'"
timeout --kill-after=15 180 git -C "$APP_DIR" push "$remote" "$COMMIT:refs/heads/$BRANCH"

echo "服务器拉取 $SRC"
ok=0
for attempt in 1 2 3; do
  echo "git pull 尝试 $attempt"
  if run_remote 600 "set -e
    cd '$SRC'
    GIT_SSH_COMMAND='ssh -i \$HOME/.ssh/aishop_github -o IdentitiesOnly=yes -o StrictHostKeyChecking=accept-new -o ConnectTimeout=20' \
      git pull --ff-only origin '$BRANCH'
    git rev-parse HEAD
    test \"\$(git rev-parse HEAD)\" = '$COMMIT'
  "; then
    ok=1
    break
  fi
  echo "拉取失败，准备重试"
  sleep 8
done
[ "$ok" = 1 ] || { echo "服务器 git pull 失败或提交不是 $COMMIT"; exit 1; }

echo "本机同步源码到 $REMOTE（排除 .env incoming backups logs bin .git）"
run_remote 60 "set -e
  test -f '$REMOTE/.env'
  grep -q '^FIELD_ENCRYPTION_KEY=.\+' '$REMOTE/.env'
  grep -q '^API_SIGNING_SECRET=.\+' '$REMOTE/.env'
  rsync -a --delete \
    --exclude '.env' --exclude 'incoming/' --exclude 'backups/' --exclude 'logs/' --exclude 'bin/' --exclude '.git' \
    '$SRC/' '$REMOTE/'
  echo 源码同步完成
"

echo "重建并启动容器（首次构建可能较久，限时 14 分钟）"
run_remote 900 "set -e
  cd '$REMOTE'
  timeout --kill-after=20 840 docker compose build
  timeout --kill-after=15 120 docker compose up -d
  docker compose ps
  mkdir -p logs
  echo '$COMMIT' > logs/deployed_commit
"

echo "检查健康状态与数据量"
run_remote 50 "set -e
  ok=0
  for i in 1 2 3 4 5 6 7 8 9 10 11 12; do
    if curl -fsS --max-time 5 http://127.0.0.1:8000/healthz; then echo; ok=1; break; fi
    sleep 3
  done
  [ \"\$ok\" = 1 ]
  cd '$REMOTE'
  docker compose exec -T db psql -U aishops -d aishops -Atc 'select count(*) from shops; select count(*) from listings;'
  cat logs/deployed_commit
"
echo "发布成功：$COMMIT"
