#!/bin/bash
# ============================================================================
# migrate_to_ab.sh
#
# 把当前 OPi Zero 2W 的运行系统迁移到一张新 32G TF 卡，做成 A/B 工业级 OTA
# 启动卡。完成后关机拔旧卡，把新卡插到 mmcblk0 主卡槽即可正常启动。
#
# 新卡分区布局（GPT-style 经过 sfdisk 转换为 MBR）：
#   /dev/sda1  256MiB  ext4  LABEL=boot      ← u-boot 找 boot.scr 的地方
#   /dev/sda2   10GiB  ext4  LABEL=rootfs-A  ← 主 rootfs（active）
#   /dev/sda3   10GiB  ext4  LABEL=rootfs-B  ← 备用 rootfs（OTA 写入这里）
#   /dev/sda4    剩余  ext4  LABEL=data      ← overlay 数据 + OTA 临时下载区
#
# A/B 切换机制：改 boot 分区里的 orangepiEnv.txt 中的 rootdev=UUID=...
# u-boot 默认行为会扫描第一个含 boot.scr 的分区，正好命中 sda1。
#
# 用法：
#   sudo bash /home/orangepi/migrate_to_ab.sh
# ============================================================================

set -e
set -o pipefail

# ------- 配置（如有改动只改这里）-----
NEW_DEV=/dev/sda          # 新 TF 卡（USB 读卡器接上后的设备名）
SRC_DEV=/dev/mmcblk0      # 当前主卡（仅用来 dd 拷 u-boot bootloader）
PART_A_GIB=10             # A 分区大小 GiB
PART_B_GIB=10             # B 分区大小 GiB
# -------------------------------------

# 颜色输出
RED='\033[0;31m'; GRN='\033[0;32m'; YEL='\033[1;33m'; NC='\033[0m'
log()  { echo -e "${GRN}[$(date +%H:%M:%S)] $*${NC}"; }
warn() { echo -e "${YEL}[$(date +%H:%M:%S)] WARN: $*${NC}"; }
die()  { echo -e "${RED}[$(date +%H:%M:%S)] ERROR: $*${NC}"; exit 1; }

# 必须 root
[[ "$EUID" -eq 0 ]] || die "请用 sudo 运行: sudo bash $0"

# ============================================================================
# Stage 0: 安全检查
# ============================================================================
log "========================================="
log " Stage 0: 安全检查"
log "========================================="

[[ -b "$NEW_DEV" ]] || die "$NEW_DEV 不存在，确认 USB 读卡器已插上"
[[ -b "$SRC_DEV" ]] || die "$SRC_DEV 不存在（当前主卡设备）"

SIZE_BYTES=$(blockdev --getsize64 "$NEW_DEV")
SIZE_GIB=$((SIZE_BYTES / 1024 / 1024 / 1024))
[[ $SIZE_GIB -ge 28 && $SIZE_GIB -le 35 ]] \
    || die "$NEW_DEV 大小异常: ${SIZE_GIB}GiB（预期 28-35）。请检查是否搞错设备！"
log "✓ $NEW_DEV 大小 ${SIZE_GIB}GiB，合理"

# 别误把当前 rootfs 卡当目标
CUR_ROOT_DEV=$(findmnt -no SOURCE /)
[[ "$NEW_DEV" == "$CUR_ROOT_DEV"* ]] && die "$NEW_DEV 是当前 rootfs 设备，禁止操作！"

# 卸载新卡可能已挂载的分区
if mount | grep -qE "^${NEW_DEV}[0-9]+ "; then
    warn "$NEW_DEV 有挂载，自动卸载"
    umount "${NEW_DEV}"* 2>/dev/null || true
    sleep 1
fi

echo
warn "即将清空 $NEW_DEV (${SIZE_GIB}GiB) 的所有数据，无法撤销！"
echo "当前 rootfs 是 $CUR_ROOT_DEV (不会被动)"
echo
read -rp "确认请输入 'yes' 继续: " CONFIRM
[[ "$CONFIRM" == "yes" ]] || die "用户取消"

# ============================================================================
# Stage 1: 拷贝 u-boot bootloader（前 8 MiB raw 区）
# ============================================================================
log "========================================="
log " Stage 1: 拷贝 u-boot bootloader (8 MiB)"
log "========================================="
dd if="$SRC_DEV" of="$NEW_DEV" bs=1M count=8 conv=fsync status=none
log "✓ u-boot SPL/bin 已写入 $NEW_DEV 前 8 MiB"

# ============================================================================
# Stage 2: 重做分区表
# ============================================================================
log "========================================="
log " Stage 2: 创建分区表"
log "========================================="

# 注意：dd 已覆盖前 8MB，包含原 MBR。sfdisk 重建 MBR（前 512 字节），不影响
# 8KB 偏移之后的 SPL/u-boot.bin
sfdisk "$NEW_DEV" <<EOF
label: dos
1MiB,256MiB,L,*
,${PART_A_GIB}GiB,L
,${PART_B_GIB}GiB,L
,,L
EOF
partprobe "$NEW_DEV"
sleep 2

log "✓ 分区表完成:"
lsblk "$NEW_DEV"

# ============================================================================
# Stage 3: 格式化 4 个分区
# ============================================================================
log "========================================="
log " Stage 3: 格式化分区"
log "========================================="
mkfs.ext4 -F -L "boot"     "${NEW_DEV}1" >/dev/null 2>&1
mkfs.ext4 -F -L "rootfs-A" "${NEW_DEV}2" >/dev/null 2>&1
mkfs.ext4 -F -L "rootfs-B" "${NEW_DEV}3" >/dev/null 2>&1
mkfs.ext4 -F -L "data"     "${NEW_DEV}4" >/dev/null 2>&1
log "✓ 4 个分区格式化完成"

BOOT_UUID=$(blkid -s UUID -o value "${NEW_DEV}1")
A_UUID=$(blkid -s UUID -o value "${NEW_DEV}2")
B_UUID=$(blkid -s UUID -o value "${NEW_DEV}3")
DATA_UUID=$(blkid -s UUID -o value "${NEW_DEV}4")
log "  BOOT UUID = $BOOT_UUID"
log "  A    UUID = $A_UUID"
log "  B    UUID = $B_UUID"
log "  DATA UUID = $DATA_UUID"

# ============================================================================
# Stage 4: 挂载到 /mnt/new/
# ============================================================================
log "========================================="
log " Stage 4: 挂载分区"
log "========================================="
mkdir -p /mnt/new/{boot,A,B,data}
mount "${NEW_DEV}1" /mnt/new/boot
mount "${NEW_DEV}2" /mnt/new/A
mount "${NEW_DEV}3" /mnt/new/B
mount "${NEW_DEV}4" /mnt/new/data
log "✓ 已挂载到 /mnt/new/{boot,A,B,data}"

# ============================================================================
# Stage 5: 拷贝 /boot 内容到新 boot 分区
# ============================================================================
log "========================================="
log " Stage 5: 拷贝 /boot → 新 boot 分区"
log "========================================="
cp -a /boot/. /mnt/new/boot/
BOOT_SIZE=$(du -sh /mnt/new/boot/ | cut -f1)
log "✓ /boot 拷贝完成（占用 $BOOT_SIZE）"

# ============================================================================
# Stage 6: rsync 整个 rootfs 到 A 分区（5-15 分钟）
# ============================================================================
log "========================================="
log " Stage 6: rsync rootfs → A 分区"
log "========================================="
log "(预计 5-15 分钟，根据数据量和卡速度。看进度别中断。)"

rsync -axHAX --info=progress2 \
    --exclude=/boot \
    --exclude=/proc \
    --exclude=/sys \
    --exclude=/dev \
    --exclude=/tmp \
    --exclude=/run \
    --exclude=/mnt \
    --exclude=/media \
    --exclude=/var/log.hdd \
    --exclude=/var/cache/apt/archives \
    --exclude=/lost+found \
    --exclude=/home/orangepi/rootfs-backup.tar.gz \
    --exclude=/home/orangepi/migrate_to_ab.sh \
    / /mnt/new/A/

log "✓ rsync 完成"

# A 分区里建必要的挂载点（空目录）
mkdir -p /mnt/new/A/{boot,proc,sys,dev,tmp,run,mnt,media,data}

# ============================================================================
# Stage 7: 配置 A 分区 fstab + boot 分区 orangepiEnv.txt
# ============================================================================
log "========================================="
log " Stage 7: 配置 fstab 和 orangepiEnv.txt"
log "========================================="

# 写 A 的 fstab
cat > /mnt/new/A/etc/fstab <<EOF
# /etc/fstab — 由 migrate_to_ab.sh 生成
UUID=$A_UUID    /     ext4  defaults,noatime,commit=600,errors=remount-ro  0 1
UUID=$BOOT_UUID /boot ext4  defaults,noatime  0 2
UUID=$DATA_UUID /data ext4  defaults,noatime  0 2
tmpfs  /tmp  tmpfs  defaults,nosuid  0 0
EOF
log "✓ /mnt/new/A/etc/fstab 已写"

# 写 boot 分区的 orangepiEnv.txt（指向 A，保留原其他配置）
cat > /mnt/new/boot/orangepiEnv.txt <<EOF
verbosity=1
bootlogo=true
console=both
disp_mode=1920x1080p60
overlay_prefix=sun50i-h616
rootdev=UUID=$A_UUID
rootfstype=ext4
EOF
log "✓ /mnt/new/boot/orangepiEnv.txt 已写（active=A）"

# 在 data 分区建 OTA 目录骨架
mkdir -p /mnt/new/data/ota/{download,backup,log}
log "✓ data 分区建好 OTA 目录骨架"

# 把 active 标识也写到 data 分区，给后续 OTA Agent 用
echo "A" > /mnt/new/data/ota/active.txt
log "✓ data 分区写入 active.txt = A"

# ============================================================================
# Stage 8: sync + umount + 报告
# ============================================================================
log "========================================="
log " Stage 8: sync + 卸载"
log "========================================="
sync
umount /mnt/new/boot /mnt/new/A /mnt/new/B /mnt/new/data
log "✓ 全部卸载，可以安全拔卡"

cat <<SUMMARY

============================================================
 ✅ 迁移完成
============================================================

新卡分区 UUID:
  BOOT = $BOOT_UUID
  A    = $A_UUID    ← 当前 active
  B    = $B_UUID    ← OTA 备用（空）
  DATA = $DATA_UUID

下一步:
  1. sudo poweroff
  2. 拔出当前主 SD 卡（mmcblk0 卡槽）
  3. 把新卡从 USB 读卡器取出，插到 mmcblk0 主卡槽
  4. 上电
  5. ssh orangepi@10.20.31.230
  6. lsblk 应该看到 mmcblk0p1/p2/p3/p4 四个分区
  7. df -h / 应该显示在 mmcblk0p2 (rootfs-A) 上
  8. cat /proc/cmdline 看 root=UUID=$A_UUID

如果新卡不能 boot 救命:
  - 关机 → 把旧卡插回主卡槽 → 上电 → 系统照常工作
  - 旧卡上的备份 tar 也还在 /home/orangepi/rootfs-backup.tar.gz

============================================================
SUMMARY
