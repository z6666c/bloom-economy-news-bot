#!/usr/bin/env bash
# يفعّل تشغيل البوت تلقائياً عبر GitHub Actions — بحيث يستمر نشر الأخبار كل
# 30 دقيقة حتى لو كان جهازك مُطفأً بالكامل، لأن التشغيل يحدث على خوادم
# GitHub نفسها وليس على جهازك.
#
# ماذا يفعل هذا السكربت بالضبط:
#   1) يرفع ملف الجدولة .github/workflows/news-bot.yml إلى GitHub.
#   2) يضيف مفتاح OpenAI (من .env المحلي) كـ "Secret" سري داخل إعدادات
#      المستودع على GitHub تلقائياً عبر واجهة GitHub API (بدون الحاجة لفتح
#      المتصفح ولصقه يدوياً) — يبقى مشفّراً ولا يظهر لأحد حتى لك بعد الحفظ.
#   3) يشغّل أول تجربة فورية للتأكد أن كل شيء يعمل.
#
# ملاحظة مهمة: التوكن المستخدم هنا يجب أن يملك صلاحية "workflow" بالإضافة
# إلى "repo" (لأن GitHub يرفض رفع/تعديل ملفات .github/workflows بتوكن لا
# يملك هذه الصلاحية تحديداً، حتى لو كان يملك صلاحية repo الكاملة). إن كنت
# غير متأكد، أنشئ توكناً جديداً من https://github.com/settings/tokens مع
# تفعيل الصلاحيتين معاً.
#
# الاستخدام:
#   bash setup_github_actions.sh ghp_xxxxxxxxxxxx
#   bash setup_github_actions.sh                    # أو بدون توكن، وسيُطلب منك لصقه

set -euo pipefail
cd "$(dirname "${BASH_SOURCE[0]}")"

REPO_NAME="bloom-economy-news-bot"

if [ "${1:-}" != "" ]; then
  GH_TOKEN="$1"
else
  echo "الصق GitHub Personal Access Token (بصلاحيتي repo و workflow):"
  read -rsp "> " GH_TOKEN
  echo
fi

echo "[*] التحقق من التوكن..."
USER_HEADERS=$(curl -sS -D - -o /tmp/gh_user_body.$$ -H "Authorization: token ${GH_TOKEN}" https://api.github.com/user)
GH_USER=$(python3 -c "import json; print(json.load(open('/tmp/gh_user_body.$$')).get('login',''))")
rm -f "/tmp/gh_user_body.$$"
if [ -z "$GH_USER" ]; then
  echo "[-] فشل التحقق من التوكن. تأكد من صلاحيته وحاول مجدداً."
  exit 1
fi
echo "[+] تم التحقق بنجاح — الحساب: $GH_USER"

if ! echo "$USER_HEADERS" | grep -qi 'x-oauth-scopes:.*workflow'; then
  echo "[!] تنبيه: لم أستطع تأكيد أن التوكن يملك صلاحية 'workflow'."
  echo "    إن فشل رفع ملف الجدولة أدناه، أنشئ توكناً جديداً من"
  echo "    https://github.com/settings/tokens بصلاحيتي repo و workflow معاً."
fi

# --- 1) رفع ملفات GitHub Actions ---
echo "[*] رفع ملفات الجدولة إلى GitHub..."
git add -A
if git diff --cached --quiet; then
  echo "[*] لا توجد تغييرات جديدة للرفع."
else
  git commit -m "Add GitHub Actions scheduled workflow"
fi
git push "https://${GH_TOKEN}@github.com/${GH_USER}/${REPO_NAME}.git" main
git remote set-url origin "https://github.com/${GH_USER}/${REPO_NAME}.git"
echo "[+] تم رفع ملفات الجدولة بنجاح."

# --- 2) إضافة OPENAI_API_KEY كـ Secret سري تلقائياً ---
if [ ! -f ".env" ] || ! grep -q '^OPENAI_API_KEY=' .env; then
  echo "[-] لم أجد OPENAI_API_KEY في .env — أضِفه يدوياً من:"
  echo "    https://github.com/${GH_USER}/${REPO_NAME}/settings/secrets/actions"
else
  OPENAI_KEY_VALUE=$(grep '^OPENAI_API_KEY=' .env | head -1 | cut -d'=' -f2-)

  python3 -c "import nacl" 2>/dev/null \
    || python3 -m pip install --quiet --user pynacl 2>/dev/null \
    || python3 -m pip install --quiet --break-system-packages pynacl 2>/dev/null \
    || true

  echo "[*] إضافة OPENAI_API_KEY كـ Secret سري في إعدادات المستودع..."
  if python3 - "$GH_TOKEN" "$GH_USER" "$REPO_NAME" "$OPENAI_KEY_VALUE" <<'PY'
import sys, json, urllib.request
from base64 import b64encode
from nacl import encoding, public

token, owner, repo, secret_value = sys.argv[1:5]
api = f"https://api.github.com/repos/{owner}/{repo}/actions/secrets"
headers = {"Authorization": f"token {token}", "Accept": "application/vnd.github+json"}

req = urllib.request.Request(f"{api}/public-key", headers=headers)
with urllib.request.urlopen(req) as r:
    key_data = json.load(r)

pk = public.PublicKey(key_data["key"].encode("utf-8"), encoding.Base64Encoder())
sealed_box = public.SealedBox(pk)
encrypted = b64encode(sealed_box.encrypt(secret_value.encode("utf-8"))).decode("utf-8")

body = json.dumps({"encrypted_value": encrypted, "key_id": key_data["key_id"]}).encode("utf-8")
req = urllib.request.Request(
    f"{api}/OPENAI_API_KEY",
    data=body,
    headers={**headers, "Content-Type": "application/json"},
    method="PUT",
)
with urllib.request.urlopen(req) as r:
    print(f"[+] تم حفظ OPENAI_API_KEY بنجاح (HTTP {r.status}).")
PY
  then
    :
  else
    echo "[-] تعذّرت الإضافة التلقائية — أضِف المفتاح يدوياً من:"
    echo "    https://github.com/${GH_USER}/${REPO_NAME}/settings/secrets/actions"
    echo "    اسم الـ Secret: OPENAI_API_KEY"
  fi
fi

# --- 3) تشغيل أول تجربة فورية ---
echo "[*] تشغيل أول دورة تجريبية عبر GitHub Actions..."
curl -sS -o /dev/null -w "  (HTTP %{http_code})\n" -X POST \
  "https://api.github.com/repos/${GH_USER}/${REPO_NAME}/actions/workflows/news-bot.yml/dispatches" \
  -H "Authorization: token ${GH_TOKEN}" \
  -H "Accept: application/vnd.github+json" \
  -d '{"ref":"main"}'

echo
echo "================================================================"
echo "تم التفعيل ✅"
echo "تابع التشغيل والسجلات من هنا:"
echo "  https://github.com/${GH_USER}/${REPO_NAME}/actions"
echo "================================================================"
echo
echo "[!] الآن لديك مصدران يمكنهما تشغيل البوت: جدولة GitHub (لا تحتاج جهازك"
echo "    مطلقاً) وجدولة launchd على جهازك. لتفادي أي تعارض أو نشر مزدوج،"
echo "    يُنصح بإيقاف الجدولة المحلية بعد التأكد أن GitHub Actions يعمل"
echo "    بنجاح (تحقق من رابط Actions أعلاه أولاً)، بالأمر التالي:"
echo "    launchctl unload ~/Library/LaunchAgents/com.bloomeconomy.newsbot.plist"
