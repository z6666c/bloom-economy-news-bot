#!/usr/bin/env bash
# تشغيل دورة واحدة من البوت (فحص + نشر) ثم رفع أي تحديث للموقع الساكن إلى
# GitHub تلقائياً (بأمان — لا يفشل التشغيل إن تعذّر الرفع). مصمم للاستدعاء
# من crontab أو launchd. يسجّل المخرجات في bot.log داخل نفس المجلد.

set -euo pipefail
cd "$(dirname "${BASH_SOURCE[0]}")"

# استخدم بيئة افتراضية إن وُجدت، وإلا استخدم بايثون النظام
if [ -f "venv/bin/activate" ]; then
  # shellcheck disable=SC1091
  source venv/bin/activate
fi

python3 news_bot.py --once

# رفع تلقائي لتحديثات الموقع الساكن (docs/) إن وُجد مستودع git مهيّأ ومُعدّ
# مسبقاً عبر finish_setup.sh — فشل الرفع هنا لا يوقف الجدولة، فقط يُسجَّل.
if [ -d ".git" ]; then
  git add -A
  if ! git diff --cached --quiet; then
    git commit -m "Auto-update: $(date '+%Y-%m-%d %H:%M')" >/dev/null 2>&1 || true
    git push >/dev/null 2>&1 && echo "[*] تم رفع تحديث الموقع تلقائياً." \
      || echo "[!] تعذّر الرفع التلقائي هذه المرة (سيُعاد المحاولة في الدورة القادمة)."
  fi
fi
