#!/usr/bin/env python3
"""
منصة الأخبار الاقتصادية المؤتمتة بالذكاء الاصطناعي (BloomEconomy News Bot)
----------------------------------------------------------------------------
يراقب هذا السكربت مجموعة من خلاصات RSS الاقتصادية، يعيد صياغة وترجمة الأخبار
الجديدة إلى العربية عبر OpenAI، ثم ينشرها تلقائياً كمقالات في موقع ووردبريس.

التشغيل:
    python news_bot.py            # تشغيل مستمر بحلقة لا نهائية (حسب POLL_INTERVAL_MINUTES)
    python news_bot.py --once     # تنفيذ دورة واحدة فقط ثم الخروج (مناسب لجدولة cron)
"""

import argparse
import base64
import json
import logging
import os
import sys
import time
from typing import Optional, Tuple

import feedparser
import requests
from openai import OpenAI

from config import Config, HISTORY_FILE, load_config

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(message)s",
    datefmt="%Y-%m-%d %H:%M:%S",
)
log = logging.getLogger("bloom_economy_bot")

MAX_ENTRIES_PER_FEED = 3
PUBLISH_DELAY_SECONDS = 5
REQUEST_TIMEOUT_SECONDS = 20


# ==============================================================================
# إدارة سجل المقالات المنشورة سابقاً (لتفادي التكرار)
# ==============================================================================
def get_processed_ids() -> list:
    if os.path.exists(HISTORY_FILE):
        try:
            with open(HISTORY_FILE, "r", encoding="utf-8") as f:
                return json.load(f)
        except (json.JSONDecodeError, OSError) as e:
            log.warning("تعذّرت قراءة سجل المنشورات (%s) — سيُعاد إنشاؤه.", e)
            return []
    return []


def record_processed_id(history: list, entry_id: str) -> None:
    if entry_id in history:
        return
    history.append(entry_id)
    tmp_path = HISTORY_FILE + ".tmp"
    with open(tmp_path, "w", encoding="utf-8") as f:
        json.dump(history, f, ensure_ascii=False, indent=2)
    os.replace(tmp_path, HISTORY_FILE)  # كتابة ذرية لتفادي تلف الملف عند الانقطاع


# ==============================================================================
# المعالجة بالذكاء الاصطناعي: إعادة الصياغة والترجمة
# ==============================================================================
SYSTEM_PROMPT = (
    "أنت محرر اقتصادي أول ومترجم صحفي مالي. "
    "مهمتك إعادة صياغة وترجمة الأخبار بدقة مالية شديدة وبلغة عربية فصحى رصينة "
    "تتبع أسلوب الهرم المقلوب. يجب إخراج الرد بصيغة JSON حصرية."
)

USER_PROMPT_TEMPLATE = """
قم بإعادة صياغة وترجمة الخبر الاقتصادي التالي وفق المعايير:
1. صغ عنواناً إخبارياً عربياً جديداً بالكامل، جذاباً وموجزاً ودقيقاً بالأرقام.
2. اكتب المقال باللغة العربية الفصحى:
   - ابدأ بفقرة تمهيدية بارزة توضح الحدث وأثره المالي فوراً.
   - اكتب فقرتين للتفاصيل وسياق السوق.
   - لخص التداعيات الرئيسية في قائمة نقطية.
3. التزم الصرامة التامة في دقة الأرقام والنسب والعملات وأسماء الشركات.
4. استخدم وسوم HTML فقط داخل المحتوى (<p>, <ul>, <li>, <strong>) دون إضافة
   وسم <html> أو <body> أو علامات ماركداون.

الخبر:
العنوان الأصلي: {title}
المحتوى الخام: {raw_text}

أخرج الناتج بصيغة JSON مطابقة تماماً للمخطط التالي:
{{
  "title": "العنوان العربي المقترح",
  "html_body": "محتوى المقال بوسوم HTML"
}}
"""

SOURCE_BOX_TEMPLATE = """
<div style="background:#f8f9fa; border-right:4px solid #0056b3; padding:15px; margin-top:30px; border-radius:4px; font-family:sans-serif; line-height:1.6;">
    <p style="margin:0; font-size:14px; color:#333;">
        <strong>توثيق المصدر:</strong> تم نقل وتدقيق هذا التقرير استناداً للمعلومات
        المنشورة لدى <strong>{source_name}</strong>. للاطلاع على التقرير الأصلي الكامل
        <a href="{source_url}" target="_blank" rel="nofollow noopener" style="color:#0056b3; text-decoration:underline;">اضغط هنا</a>.
    </p>
</div>
"""


def process_content_with_ai(
    client: OpenAI, model: str, title: str, raw_text: str, source_name: str, source_url: str
) -> Tuple[Optional[str], Optional[str]]:
    user_prompt = USER_PROMPT_TEMPLATE.format(title=title, raw_text=raw_text)
    try:
        response = client.chat.completions.create(
            model=model,
            response_format={"type": "json_object"},
            messages=[
                {"role": "system", "content": SYSTEM_PROMPT},
                {"role": "user", "content": user_prompt},
            ],
            temperature=0.2,
        )
        data = json.loads(response.choices[0].message.content)
        source_box_html = SOURCE_BOX_TEMPLATE.format(source_name=source_name, source_url=source_url)
        full_content = data["html_body"] + source_box_html
        return data["title"], full_content
    except Exception as e:
        log.error("خطأ أثناء معالجة المقال عبر الذكاء الاصطناعي: %s", e)
        return None, None


# ==============================================================================
# النشر عبر WordPress REST API
# ==============================================================================
def publish_article(cfg: Config, title: str, content: str, category_id: int) -> bool:
    endpoint = f"{cfg.wp_base_url}/wp-json/wp/v2/posts"
    credentials = f"{cfg.wp_username}:{cfg.wp_app_password}"
    encoded_creds = base64.b64encode(credentials.encode()).decode("utf-8")
    headers = {
        "Authorization": f"Basic {encoded_creds}",
        "Content-Type": "application/json",
    }
    payload = {
        "title": title,
        "content": content,
        "status": cfg.post_status,
        "categories": [category_id],
    }
    try:
        response = requests.post(endpoint, headers=headers, json=payload, timeout=REQUEST_TIMEOUT_SECONDS)
        if response.status_code == 201:
            log.info("نُشر بنجاح: %s", title)
            return True
        log.error("فشل النشر (%s): %s", response.status_code, response.text)
        return False
    except requests.RequestException as e:
        log.error("خطأ بالاتصال مع ووردبريس: %s", e)
        return False


# ==============================================================================
# دورة العمل
# ==============================================================================
def execute_cycle(cfg: Config, client: OpenAI) -> None:
    history = get_processed_ids()
    log.info("بدء فحص الخلاصات الإخبارية...")

    for feed_info in cfg.feeds:
        log.info("مراقبة المصدر: %s", feed_info["name"])
        try:
            feed = feedparser.parse(feed_info["url"])
        except Exception as e:
            log.error("خطأ أثناء قراءة خلاصة %s: %s", feed_info["name"], e)
            continue

        for entry in feed.entries[:MAX_ENTRIES_PER_FEED]:
            entry_id = entry.get("id", entry.get("link"))
            if not entry_id or entry_id in history:
                continue

            title = entry.get("title", "")
            summary = entry.get("summary", entry.get("description", ""))
            url = entry.get("link", "")
            log.info("خبر جديد تم رصده: %s", title)

            ai_title, ai_content = process_content_with_ai(
                client, cfg.openai_model, title, summary, feed_info["name"], url
            )
            if ai_title and ai_content:
                if publish_article(cfg, ai_title, ai_content, feed_info["category_id"]):
                    record_processed_id(history, entry_id)
                    time.sleep(PUBLISH_DELAY_SECONDS)  # فاصل أمان بين عمليات النشر


def run_once(cfg: Config, client: OpenAI) -> None:
    execute_cycle(cfg, client)


def run_forever(cfg: Config, client: OpenAI) -> None:
    log.info("=== بدء تشغيل منصة الأخبار الاقتصادية المؤتمتة بالذكاء الاصطناعي ===")
    while True:
        execute_cycle(cfg, client)
        log.info("اكتملت الدورة. الانتظار %d دقيقة حتى الفحص القادم...", cfg.poll_interval_minutes)
        time.sleep(cfg.poll_interval_minutes * 60)


def main() -> None:
    parser = argparse.ArgumentParser(description="BloomEconomy News Bot")
    parser.add_argument(
        "--once",
        action="store_true",
        help="تنفيذ دورة فحص ونشر واحدة ثم الخروج (مناسب للتشغيل عبر cron/scheduled task)",
    )
    args = parser.parse_args()

    cfg = load_config()
    if not cfg.feeds:
        log.error("لا توجد خلاصات RSS معرّفة في feeds.json — أضف مصدراً واحداً على الأقل.")
        sys.exit(1)

    client = OpenAI(api_key=cfg.openai_api_key)

    if args.once:
        run_once(cfg, client)
    else:
        run_forever(cfg, client)


if __name__ == "__main__":
    main()
