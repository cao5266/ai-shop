#!/usr/bin/env bash
# 加密备份：pg_dump | gzip | age 或 gpg，明文不落盘。保留最近 7 份。
#
# 用法（在 app 目录，服务器上）：
#   BACKUP_AGE_RECIPIENT=age1xxxx  ./scripts/backup_encrypted.sh     # 用 age 公钥
#   BACKUP_GPG_RECIPIENT=ID        ./scripts/backup_encrypted.sh     # 用 gpg 公钥
# 公钥加密：服务器上只有公钥，没有能解密的私钥；私钥请保存在你自己的电脑或密码管理器里。
#
# 可覆盖的环境变量：
#   BACKUP_DIR   备份目录，默认 ./backups
#   DUMP_CMD     导出命令，默认 docker compose exec -T db pg_dump -U aishops aishops
#   KEEP         保留份数，默认 7
set -euo pipefail
cd "$(dirname "$0")/.."
DIR="${BACKUP_DIR:-./backups}"
KEEP="${KEEP:-7}"
DUMP_CMD="${DUMP_CMD:-docker compose exec -T db pg_dump -U ${POSTGRES_USER:-aishops} ${POSTGRES_DB:-aishops}}"
umask 077
mkdir -p "$DIR"
stamp=$(date +%F-%H%M%S)

if [ -n "${BACKUP_AGE_RECIPIENT:-}" ]; then
  command -v age >/dev/null || { echo "错误：没有安装 age" >&2; exit 1; }
  out="$DIR/aishops-$stamp.sql.gz.age"; enc=(age -r "$BACKUP_AGE_RECIPIENT")
elif [ -n "${BACKUP_GPG_RECIPIENT:-}" ]; then
  command -v gpg >/dev/null || { echo "错误：没有安装 gpg" >&2; exit 1; }
  out="$DIR/aishops-$stamp.sql.gz.gpg"
  enc=(gpg --batch --yes --trust-model always --encrypt -r "$BACKUP_GPG_RECIPIENT")
else
  echo "错误：请设置 BACKUP_AGE_RECIPIENT 或 BACKUP_GPG_RECIPIENT（拒绝生成明文备份）" >&2; exit 1
fi

tmp="$out.tmp"
trap 'rm -f -- "$tmp"' EXIT
# pipefail：任何一步失败都会让整条命令失败，不会留下一份看似正常的空备份
bash -c "$DUMP_CMD" | gzip -9 | "${enc[@]}" > "$tmp"
[ -s "$tmp" ] || { echo "错误：备份文件为空" >&2; exit 1; }
mv "$tmp" "$out"
trap - EXIT
sha256sum "$out" | awk '{print $1}' > "$out.sha256"
echo "备份完成：$out ($(du -h "$out" | awk '{print $1}'))"

# 只保留最近 $KEEP 份
ls -1t "$DIR"/aishops-*.sql.gz.* 2>/dev/null | grep -v '\.sha256$' | tail -n +"$((KEEP + 1))" | while read -r f; do
  rm -f -- "$f" "$f.sha256"
done
