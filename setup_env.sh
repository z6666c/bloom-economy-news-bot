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
read -rp "رابط موقع ووردبريس (https://example.com): " WP_BASE_URL
read -rp "اسم مستخدم ووردبريس: " WP_USERNAME
read -rsp "WordPress Application Password: " WP_APP_PASSWORD; echo
read -rp "حالة النشر publish/draft [publish]: " POST_STATUS
POST_STATUS=${POST_STATUS:-publish}
read -rp "الفاصل الزمني بالدقائق (لوضع التشغيل المستمر فقط) [30]: " POLL_INTERVAL_MINUTES
POLL_INTERVAL_MINUTES=${POLL_INTERVAL_MINUTES:-30}

cat > .env <<EOF
OPENAI_API_KEY=${OPENAI_API_KEY}
OPENAI_MODEL=${OPENAI_MODEL}
WP_BASE_URL=${WP_BASE_URL}
WP_USERNAME=${WP_USERNAME}
WP_APP_PASSWORD=${WP_APP_PASSWORD}
POST_STATUS=${POST_STATUS}
POLL_INTERVAL_MINUTES=${POLL_INTERVAL_MINUTES}
EOF

chmod 600 .env
echo "[+] تم إنشاء .env بنجاح (صلاحيات القراءة مقصورة عليك فقط)."
echo "[*] لتجربة البوت الآن: python3 news_bot.py --once"
