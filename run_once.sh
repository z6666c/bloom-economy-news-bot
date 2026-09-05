#!/usr/bin/env bash
# تشغيل دورة واحدة من البوت (فحص + نشر) ثم الخروج — مصمم للاستدعاء من
# crontab أو launchd على جهازك. يسجّل المخرجات في bot.log داخل نفس المجلد.

set -euo pipefail
cd "$(dirname "${BASH_SOURCE[0]}")"

# استخدم بيئة افتراضية إن وُجدت، وإلا استخدم بايثون النظام
if [ -f "venv/bin/activate" ]; then
  # shellcheck disable=SC1091
  source venv/bin/activate
fi

python3 news_bot.py --once
