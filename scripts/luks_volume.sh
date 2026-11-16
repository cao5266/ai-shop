#!/usr/bin/env bash
# 用 LUKS 给 Postgres 数据卷加密（文件做底，不需要额外磁盘）。需要 root 和 cryptsetup。
# 注意：这份脚本没有在开发机上实测（开发机没有 root 与 cryptsetup），上线前请先在测试机走一遍。
#
#   sudo ./scripts/luks_volume.sh create 20G     # 首次：创建加密卷并挂载（会询问口令）
#   sudo ./scripts/luks_volume.sh open           # 重启后：输入口令解锁并挂载
#   sudo ./scripts/luks_volume.sh close          # 卸载并上锁
# 然后在 .env 里设置 PGDATA_PATH=/srv/aishops-secure/pgdata，再 docker compose up -d
#
# 取舍：口令要在每次开机后手动输入（或用你自己的密钥托管方案）。把口令明文放服务器上等于没加密。
# 这种加密防的是：磁盘、快照、云盘被整体拿走。服务器运行中被入侵时，挂载状态下数据是可读的。
set -euo pipefail
IMG="${LUKS_IMG:-/srv/aishops-secure.img}"
MAP="${LUKS_NAME:-aishops_secure}"
MNT="${LUKS_MNT:-/srv/aishops-secure}"
PG_UID="${PG_UID:-70}"   # postgres:alpine 镜像里 postgres 用户的 uid
cmd="${1:-}"
case "$cmd" in
  create)
    size="${2:-20G}"
    [ -e "$IMG" ] && { echo "错误：$IMG 已存在，拒绝覆盖" >&2; exit 1; }
    truncate -s "$size" "$IMG"; chmod 600 "$IMG"
    cryptsetup luksFormat --type luks2 "$IMG"
    cryptsetup open "$IMG" "$MAP"
    mkfs.ext4 -L aishops "/dev/mapper/$MAP"
    mkdir -p "$MNT"; mount "/dev/mapper/$MAP" "$MNT"
    mkdir -p "$MNT/pgdata"; chown "$PG_UID:$PG_UID" "$MNT/pgdata"; chmod 700 "$MNT/pgdata"
    echo "完成。.env 设置 PGDATA_PATH=$MNT/pgdata"
    ;;
  open)
    cryptsetup open "$IMG" "$MAP"; mkdir -p "$MNT"; mount "/dev/mapper/$MAP" "$MNT"
    echo "已挂载 $MNT"
    ;;
  close)
    umount "$MNT"; cryptsetup close "$MAP"; echo "已上锁"
    ;;
  *) echo "用法：$0 create [大小] | open | close" >&2; exit 2 ;;
esac
