#!/usr/bin/env bash
# سكربت واحد شامل يكمل كل ما تبقّى: يرفع آخر التحديثات إلى GitHub، يفعّل
# الموقع المجاني عبر GitHub Pages، ويهيّئ الرفع التلقائي المستقبلي (بدون
# طلب التوكن كل مرة) حتى يعمل التحديث التلقائي عبر الجدولة (install_schedule.sh)
# دون تدخل يدوي لاحقاً.
#
# شغّله من Terminal الحقيقي على جهازك بإحدى طريقتين:
#
#   bash finish_setup.sh ghp_xxxxxxxxxxxx     # التوكن كجزء من الأمر مباشرة (موصى به — يتجنب مشاكل اللصق)
#   bash finish_setup.sh                      # أو بدون توكن، وسيُطلب منك لصقه تفاعلياً

set -euo pipefail
cd "$(dirname "${BASH_SOURCE[0]}")"

REPO_NAME="bloom-economy-news-bot"

if [ "${1:-}" != "" ]; then
  GH_TOKEN="$1"
else
  echo "الصق GitHub Personal Access Token (نفسه أو توكن جديد بصلاحية repo):"
  read -rsp "> " GH_TOKEN
  echo
fi

echo "[*] التحقق من التوكن..."
USER_JSON=$(curl -sS -H "Authorization: token ${GH_TOKEN}" https://api.github.com/user)
GH_USER=$(echo "$USER_JSON" | python3 -c "import sys,json; print(json.load(sys.stdin).get('login',''))")
if [ -z "$GH_USER" ]; then
  echo "[-] فشل التحقق من التوكن. تأكد من صلاحيته (repo scope) وحاول مجدداً."
  exit 1
fi
echo "[+] تم التحقق بنجاح — الحساب: $GH_USER"

# --- 1) تهيئة git ورفع أي تعديلات جديدة ---
if [ ! -d .git ]; then
  git init
  git branch -M main
fi
git add -A
if git diff --cached --quiet; then
  echo "[*] لا توجد تغييرات جديدة للالتزام بها."
else
  git commit -m "Update BloomEconomy news bot"
fi

if ! git remote get-url origin >/dev/null 2>&1; then
  # المستودع قد لا يكون موجوداً بعد — أنشئه (يتجاهل الخطأ إن كان موجوداً مسبقاً)
  curl -sS -X POST https://api.github.com/user/repos \
    -H "Authorization: token ${GH_TOKEN}" \
    -H "Accept: application/vnd.github+json" \
    -d "{\"name\":\"${REPO_NAME}\",\"private\":false}" > /dev/null
  git remote add origin "https://github.com/${GH_USER}/${REPO_NAME}.git"
fi

echo "[*] رفع الملفات إلى GitHub..."
git push "https://${GH_TOKEN}@github.com/${GH_USER}/${REPO_NAME}.git" main
git remote set-url origin "https://github.com/${GH_USER}/${REPO_NAME}.git"
echo "[+] تم الرفع بنجاح."

# --- 2) تفعيل GitHub Pages من فرع main / مجلد docs ---
echo "[*] تفعيل الموقع عبر GitHub Pages..."
PAGES_CREATE=$(curl -sS -o /dev/null -w "%{http_code}" -X POST \
  "https://api.github.com/repos/${GH_USER}/${REPO_NAME}/pages" \
  -H "Authorization: token ${GH_TOKEN}" \
  -H "Accept: application/vnd.github+json" \
  -d '{"source":{"branch":"main","path":"/docs"}}')

if [ "$PAGES_CREATE" = "201" ] || [ "$PAGES_CREATE" = "204" ]; then
  echo "[+] تم تفعيل GitHub Pages."
elif [ "$PAGES_CREATE" = "409" ]; then
  echo "[*] الموقع مفعّل مسبقاً — سيُحدَّث تلقائياً مع كل رفع."
else
  echo "[-] استجابة غير متوقعة عند تفعيل Pages (HTTP $PAGES_CREATE) — قد تحتاج تفعيلها يدوياً من:"
  echo "    https://github.com/${GH_USER}/${REPO_NAME}/settings/pages"
fi

SITE_URL="https://${GH_USER}.github.io/${REPO_NAME}/"

# --- 3) حفظ بيانات الاعتماد محلياً للرفع التلقائي المستقبلي (دون تدخل يدوي) ---
git config credential.helper osxkeychain 2>/dev/null || true
printf 'protocol=https\nhost=github.com\nusername=%s\npassword=%s\n\n' "$GH_USER" "$GH_TOKEN" \
  | git credential approve 2>/dev/null || true

# --- 4) تحديث SITE_BASE_URL في .env إن وُجد ---
if [ -f ".env" ]; then
  if grep -q '^SITE_BASE_URL=' .env; then
    sed -i.bak "s|^SITE_BASE_URL=.*|SITE_BASE_URL=${SITE_URL}|" .env && rm -f .env.bak
  else
    echo "SITE_BASE_URL=${SITE_URL}" >> .env
  fi
  echo "[+] تم تحديث SITE_BASE_URL في .env"
fi

echo
echo "================================================================"
echo "تم الانتهاء بنجاح ✅"
echo "رابط المستودع : https://github.com/${GH_USER}/${REPO_NAME}"
echo "رابط الموقع    : ${SITE_URL}"
echo "(قد يستغرق ظهور الموقع لأول مرة بضع دقائق بعد التفعيل)"
echo "================================================================"
echo
echo "[!] هذا التوكن محفوظ الآن في Keychain جهازك ويُستخدم للرفع التلقائي كل"
echo "    30 دقيقة — لا تُلغِه إلا إذا كنت تريد إيقاف الرفع التلقائي أو انتهت صلاحيته."
