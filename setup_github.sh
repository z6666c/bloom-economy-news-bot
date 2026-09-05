#!/usr/bin/env bash
# سكربت مساعد لإنشاء مستودع GitHub ورفع هذا المشروع إليه دفعة واحدة.
# شغّله من Terminal الحقيقي على جهازك (وليس من داخل أي بيئة معزولة):
#
#   cd ~/Documents/bloom-economy-news-bot
#   bash setup_github.sh
#
# سيطلب منك التوكن أثناء التشغيل بدل كتابته داخل الملف لحمايته.

set -euo pipefail

REPO_NAME="bloom-economy-news-bot"
VISIBILITY="public"   # غيّرها إلى "private" إن رغبت بمستودع خاص

read -rsp "الصق GitHub Personal Access Token ثم اضغط Enter: " GH_TOKEN
echo

echo "[*] التحقق من التوكن..."
USER_JSON=$(curl -sS -H "Authorization: token ${GH_TOKEN}" https://api.github.com/user)
GH_USER=$(echo "$USER_JSON" | python3 -c "import sys,json; print(json.load(sys.stdin).get('login',''))")

if [ -z "$GH_USER" ]; then
  echo "[-] فشل التحقق من التوكن. تأكد من صلاحيته (repo scope) وحاول مجدداً."
  exit 1
fi
echo "[+] تم التحقق بنجاح — الحساب: $GH_USER"

echo "[*] إنشاء المستودع $REPO_NAME على GitHub..."
CREATE_RESPONSE=$(curl -sS -X POST https://api.github.com/user/repos \
  -H "Authorization: token ${GH_TOKEN}" \
  -H "Accept: application/vnd.github+json" \
  -d "{\"name\":\"${REPO_NAME}\",\"private\":$( [ "$VISIBILITY" = "private" ] && echo true || echo false )}")

if echo "$CREATE_RESPONSE" | grep -q '"name already exists on this account"'; then
  echo "[*] المستودع موجود مسبقاً على حسابك — سيتم الرفع إليه مباشرة."
elif echo "$CREATE_RESPONSE" | python3 -c "import sys,json; d=json.load(sys.stdin); sys.exit(0 if d.get('id') else 1)" 2>/dev/null; then
  echo "[+] تم إنشاء المستودع بنجاح."
else
  echo "[-] استجابة غير متوقعة من GitHub:"
  echo "$CREATE_RESPONSE"
  exit 1
fi

echo "[*] تهيئة git ورفع الملفات..."
if [ ! -d .git ]; then
  git init
  git branch -M main
fi
git add .
git commit -m "Initial commit: BloomEconomy news bot" || echo "[*] لا توجد تغييرات جديدة للالتزام بها."

git remote remove origin 2>/dev/null || true
git remote add origin "https://${GH_TOKEN}@github.com/${GH_USER}/${REPO_NAME}.git"
git push -u origin main

# إزالة التوكن من رابط الريموت بعد الرفع مباشرة لعدم بقائه محفوظاً على القرص
git remote set-url origin "https://github.com/${GH_USER}/${REPO_NAME}.git"

echo
echo "[+] تم! رابط المستودع: https://github.com/${GH_USER}/${REPO_NAME}"
echo "[!] يُنصح بإلغاء التوكن الآن من: https://github.com/settings/tokens"
