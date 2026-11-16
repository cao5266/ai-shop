#!/usr/bin/env bash
# 还原加密备份。需要能解密的私钥，所以通常在你自己的机器上执行，不在服务器上。
#
# 解密后查看内容（不还原）：
#   ./scripts/restore_encrypted.sh backups/aishops-xxx.sql.gz.gpg - | head
# 还原到某个数据库：
#   RESTORE_CMD="psql postgresql://user:pass@host/dbname" ./scripts/restore_encrypted.sh backups/aishops-xxx.sql.gz.gpg
# age 备份用 AGE_IDENTITY 指定私钥文件：AGE_IDENTITY=~/age-key.txt ./scripts/restore_encrypted.sh ...age
set -euo pipefail
file="${1:?用法：restore_encrypted.sh 备份文件 [-]}"
if [ -f "$file.sha256" ] && [ "$(sha256sum "$file" | awk '{print $1}')" != "$(cat "$file.sha256")" ]; then
  echo "错误：校验和不一致，备份文件可能损坏" >&2; exit 1
fi
case "$file" in
  *.age) dec=(age -d -i "${AGE_IDENTITY:?请用 AGE_IDENTITY 指定 age 私钥文件}") ;;
  *.gpg) dec=(gpg --batch -d) ;;
  *) echo "错误：只支持 .age / .gpg" >&2; exit 1 ;;
esac
if [ "${2:-}" = "-" ]; then
  "${dec[@]}" < "$file" | gunzip
else
  : "${RESTORE_CMD:?请用 RESTORE_CMD 指定还原命令，例如 psql postgresql://...}"
  "${dec[@]}" < "$file" | gunzip | bash -c "$RESTORE_CMD"
fi
