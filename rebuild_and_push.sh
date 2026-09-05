#!/usr/bin/env bash
# يعيد بناء الموقع فوراً من الأخبار الموجودة حالياً (بدون انتظار خبر جديد)
# — مفيد بعد أي تحديث في التصميم — ثم يرفع النتيجة إلى GitHub مباشرة.
#
# الاستخدام: bash rebuild_and_push.sh

set -euo pipefail
cd "$(dirname "${BASH_SOURCE[0]}")"

if [ -f "venv/bin/activate" ]; then
  # shellcheck disable=SC1091
  source venv/bin/activate
fi

python3 rebuild_site.py

if [ -d ".git" ]; then
  git add -A
  if ! git diff --cached --quiet; then
    git commit -m "Rebuild site: design update" >/dev/null 2>&1 || true
    git push && echo "[+] تم رفع الموقع المُحدَّث إلى GitHub." \
      || echo "[!] تعذّر الرفع — تأكد من اتصال الإنترنت وحاول: git push"
  else
    echo "[*] لا يوجد تغيير جديد في الموقع بعد إعادة البناء."
  fi
fi
