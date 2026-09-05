#!/usr/bin/env bash
# يثبّت جدولة تلقائية (launchd) لتشغيل البوت كل 30 دقيقة حتى بعد إعادة تشغيل
# الجهاز — بديل أنظف من crontab على macOS.
#
#   cd ~/Documents/bloom-economy-news-bot
#   bash install_schedule.sh

set -euo pipefail
PROJECT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
PLIST_NAME="com.bloomeconomy.newsbot.plist"
DEST="$HOME/Library/LaunchAgents/${PLIST_NAME}"

mkdir -p "$HOME/Library/LaunchAgents"
sed "s|__PROJECT_DIR__|${PROJECT_DIR}|g" "${PROJECT_DIR}/${PLIST_NAME}" > "$DEST"

launchctl unload "$DEST" 2>/dev/null || true
launchctl load "$DEST"

echo "[+] تم تثبيت الجدولة — سيعمل البوت كل 30 دقيقة تلقائياً (حتى بعد إعادة التشغيل)."
echo "[*] لمتابعة السجلات: tail -f ${PROJECT_DIR}/bot.log"
echo "[*] لإيقاف الجدولة لاحقاً: launchctl unload ${DEST}"
