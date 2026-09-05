#!/usr/bin/env bash
# سكربت تفاعلي لإنشاء ملف .env بأمان — يُشغَّل من جهازك مباشرة، والقيم
# تُكتب محلياً فقط على قرصك ولا تُرسل لأي مكان آخر.
#
#   cd ~/Documents/bloom-economy-news-bot
#   bash setup_env.sh

set -euo pipefail
cd "$(dirname "${BASH_SOURCE[0]}")"

if [ -f ".env" ]; then
  read -rp ".env موجود مسبقاً — هل تريد استبداله؟ (y/N): " OVERWRITE
  if [[ ! "$OVERWRITE" =~ ^[Yy]$ ]]; then
    echo "تم الإلغاء — لم يتغيّر شيء."
    exit 0
  fi
fi

read -rsp "OpenAI API Key (sk-...): " OPENAI_API_KEY; echo
read -rp "OpenAI Model [gpt-4o-mini]: " OPENAI_MODEL
OPENAI_MODEL=${OPENAI_MODEL:-gpt-4o-mini}

echo
echo "--- الموقع الإخباري (القناة الافتراضية — مجاني عبر GitHub Pages) ---"
read -rp "اسم الموقع [BloomEconomy — أخبار اقتصادية]: " SITE_TITLE
SITE_TITLE=${SITE_TITLE:-"BloomEconomy — أخبار اقتصادية"}

echo
echo "--- ووردبريس (اختياري) ---"
read -rp "هل لديك موقع ووردبريس تريد النشر فيه أيضاً؟ (y/N): " WANT_WP
ENABLE_WORDPRESS=false
WP_BASE_URL=""
WP_USERNAME=""
WP_APP_PASSWORD=""
POST_STATUS="publish"
if [[ "$WANT_WP" =~ ^[Yy]$ ]]; then
  ENABLE_WORDPRESS=true
  read -rp "رابط موقع ووردبريس (https://example.com): " WP_BASE_URL
  read -rp "اسم مستخدم ووردبريس: " WP_USERNAME
  read -rsp "WordPress Application Password: " WP_APP_PASSWORD; echo
  read -rp "حالة النشر publish/draft [publish]: " POST_STATUS
  POST_STATUS=${POST_STATUS:-publish}
fi

read -rp "الفاصل الزمني بالدقائق (لوضع التشغيل المستمر فقط) [30]: " POLL_INTERVAL_MINUTES
POLL_INTERVAL_MINUTES=${POLL_INTERVAL_MINUTES:-30}
read -rp "نسبة التشابه لاعتبار خبرين متكررين (0-1) [0.6]: " DUP_THRESHOLD
DUP_THRESHOLD=${DUP_THRESHOLD:-0.6}

echo
echo "--- تليجرام (اختياري) ---"
read -rp "هل تريد تفعيل النشر إلى تليجرام الآن؟ (y/N): " WANT_TG
ENABLE_TELEGRAM=false
TELEGRAM_BOT_TOKEN=""
TELEGRAM_CHAT_ID=""
if [[ "$WANT_TG" =~ ^[Yy]$ ]]; then
  ENABLE_TELEGRAM=true
  read -rsp "Telegram Bot Token (من @BotFather): " TELEGRAM_BOT_TOKEN; echo
  read -rp "Telegram Chat ID (معرّف القناة/المجموعة): " TELEGRAM_CHAT_ID
fi

echo
echo "--- إشعارات الفشل (اختياري) ---"
read -rp "هل تريد تفعيل إشعارات الفشل عبر تليجرام؟ (y/N): " WANT_NOTIFY
ENABLE_NOTIFICATIONS=false
TELEGRAM_ADMIN_CHAT_ID=""
if [[ "$WANT_NOTIFY" =~ ^[Yy]$ ]]; then
  ENABLE_NOTIFICATIONS=true
  if [ "$ENABLE_TELEGRAM" != "true" ]; then
    read -rsp "Telegram Bot Token (من @BotFather): " TELEGRAM_BOT_TOKEN; echo
  fi
  read -rp "معرّف محادثتك الخاصة لاستقبال التنبيهات (Chat ID): " TELEGRAM_ADMIN_CHAT_ID
fi

cat > .env <<EOF
OPENAI_API_KEY=${OPENAI_API_KEY}
OPENAI_MODEL=${OPENAI_MODEL}

ENABLE_STATIC_SITE=true
SITE_TITLE=${SITE_TITLE}
SITE_BASE_URL=

ENABLE_WORDPRESS=${ENABLE_WORDPRESS}
WP_BASE_URL=${WP_BASE_URL}
WP_USERNAME=${WP_USERNAME}
WP_APP_PASSWORD=${WP_APP_PASSWORD}
POST_STATUS=${POST_STATUS}

POLL_INTERVAL_MINUTES=${POLL_INTERVAL_MINUTES}
DUPLICATE_SIMILARITY_THRESHOLD=${DUP_THRESHOLD}
DUPLICATE_WINDOW_HOURS=48

ENABLE_TELEGRAM=${ENABLE_TELEGRAM}
TELEGRAM_BOT_TOKEN=${TELEGRAM_BOT_TOKEN}
TELEGRAM_CHAT_ID=${TELEGRAM_CHAT_ID}

ENABLE_NOTIFICATIONS=${ENABLE_NOTIFICATIONS}
TELEGRAM_ADMIN_CHAT_ID=${TELEGRAM_ADMIN_CHAT_ID}

# منصة X — تبقى معطّلة حتى تكون جاهزاً؛ فعّلها لاحقاً بتغيير ENABLE_X إلى true
# وتعبئة المفاتيح الأربعة أدناه، ثم: pip install tweepy
ENABLE_X=false
X_API_KEY=
X_API_SECRET=
X_ACCESS_TOKEN=
X_ACCESS_SECRET=
EOF

chmod 600 .env
echo "[+] تم إنشاء .env بنجاح (صلاحيات القراءة مقصورة عليك فقط)."
echo "[*] لتجربة البوت الآن: python3 news_bot.py --once"
