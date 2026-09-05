#!/usr/bin/env bash
# يرفع أي تعديلات جديدة على المشروع إلى نفس مستودع GitHub الموجود.
# شغّله من Terminal الحقيقي على جهازك:
#
#   cd ~/Documents/bloom-economy-news-bot
#   bash push_update.sh "رسالة الالتزام (اختياري)"

set -euo pipefail
cd "$(dirname "${BASH_SOURCE[0]}")"

COMMIT_MSG="${1:-Update BloomEconomy news bot}"

if [ ! -d .git ]; then
  echo "[-] لا يوجد مستودع git هنا بعد. شغّل setup_github.sh أولاً."
  exit 1
fi

git add -A
if git diff --cached --quiet; then
  echo "[*] لا توجد تغييرات جديدة للرفع."
  exit 0
fi
git commit -m "$COMMIT_MSG"

# إن كان رابط الريموت لا يحتوي توكن (الحالة الطبيعية بعد أول رفع)، سيحاول
# git استخدام بيانات الاعتماد المحفوظة على جهازك. إن طلب منك اسم مستخدم/كلمة
# مرور ولم تكن متأكداً، استخدم "Personal Access Token" ككلمة مرور.
git push

echo "[+] تم رفع التحديثات بنجاح."
