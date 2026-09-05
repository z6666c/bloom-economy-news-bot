#!/usr/bin/env python3
"""
منصة الأخبار الاقتصادية المؤتمتة بالذكاء الاصطناعي (BloomEconomy News Bot)
----------------------------------------------------------------------------
يراقب هذا السكربت مجموعة من خلاصات RSS الاقتصادية، يعيد صياغة وترجمة الأخبار
الجديدة إلى العربية عبر OpenAI مع تصنيفها تلقائياً، يتجنّب نشر الأخبار
المتكررة أو المتشابهة من مصادر مختلفة، ثم ينشرها في موقع إخباري ساكن يُبنى
تلقائياً (docs/ — جاهز للنشر المجاني عبر GitHub Pages دون الحاجة لووردبريس)،
مع دعم اختياري لووردبريس وتليجرام، وإشعار فوري عند حدوث أي فشل.

التشغيل:
    python news_bot.py            # تشغيل مستمر بحلقة لا نهائية (حسب POLL_INTERVAL_MINUTES)
    python news_bot.py --once     # تنفيذ دورة واحدة فقط ثم الخروج (مناسب لجدولة cron/launchd)
"""

import argparse
import base64
import json
import logging
import os
import re
import sys
import time
from typing import Dict, List, Optional, Set, Tuple

import feedparser
import requests
from openai import OpenAI

import site_generator
from config import ARTICLES_FILE, Config, HISTORY_FILE, load_config

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(message)s",
    datefmt="%Y-%m-%d %H:%M:%S",
)
log = logging.getLogger("bloom_economy_bot")

MAX_ENTRIES_PER_FEED = 3
PUBLISH_DELAY_SECONDS = 5
REQUEST_TIMEOUT_SECONDS = 20
MAX_HISTORY_RECORDS = 1500

STOPWORDS = {
    "the", "a", "an", "of", "in", "on", "to", "for", "and", "is", "are",
    "with", "by", "at", "as", "its", "it", "from", "after", "amid", "over",
    "up", "down", "new", "says", "said", "into", "out", "than", "will",
    "has", "have", "had", "be", "been", "was", "were", "this", "that",
    "but", "not", "no", "yes", "amp",
}


# ==============================================================================
# إدارة سجل المقالات المنشورة سابقاً (منع التكرار الدقيق + التشابه)
# ==============================================================================
def tokenize_title(title: str) -> Set[str]:
    words = re.findall(r"[a-zA-Z0-9؀-ۿ]+", title.lower())
    return {w for w in words if w not in STOPWORDS and len(w) > 2}


def jaccard_similarity(a: Set[str], b: Set[str]) -> float:
    if not a or not b:
        return 0.0
    intersection = len(a & b)
    union = len(a | b)
    return intersection / union if union else 0.0


def get_processed_records() -> List[Dict]:
    """يحمّل سجل المنشورات، ويحوّل الصيغة القديمة (قائمة نصوص) للصيغة
    الجديدة (قائمة كائنات تحوي العنوان والكلمات المفتاحية) تلقائياً."""
    if not os.path.exists(HISTORY_FILE):
        return []
    try:
        with open(HISTORY_FILE, "r", encoding="utf-8") as f:
            raw = json.load(f)
    except (json.JSONDecodeError, OSError) as e:
        log.warning("تعذّرت قراءة سجل المنشورات (%s) — سيُعاد إنشاؤه.", e)
        return []

    records = []
    for item in raw:
        if isinstance(item, str):
            # سجل قديم بصيغة معرّف فقط — يُحافظ عليه لمنع التكرار الدقيق
            records.append({"id": item, "title": "", "tokens": [], "ts": 0})
        elif isinstance(item, dict):
            records.append(item)
    return records


def is_duplicate(new_tokens: Set[str], history: List[Dict], threshold: float, window_hours: int) -> Tuple[bool, Optional[str]]:
    now = time.time()
    for rec in history:
        ts = rec.get("ts") or 0
        if ts and (now - ts) > window_hours * 3600:
            continue
        existing_tokens = set(rec.get("tokens", []))
        if jaccard_similarity(new_tokens, existing_tokens) >= threshold:
            return True, rec.get("title", "")
    return False, None


def record_processed(history: List[Dict], entry_id: str, title: str, tokens: Set[str]) -> None:
    history.append({
        "id": entry_id,
        "title": title,
        "tokens": sorted(tokens),
        "ts": time.time(),
    })
    # الاحتفاظ بآخر MAX_HISTORY_RECORDS فقط لتفادي تضخم الملف مع الوقت
    if len(history) > MAX_HISTORY_RECORDS:
        del history[: len(history) - MAX_HISTORY_RECORDS]

    tmp_path = HISTORY_FILE + ".tmp"
    with open(tmp_path, "w", encoding="utf-8") as f:
        json.dump(history, f, ensure_ascii=False, indent=2)
    os.replace(tmp_path, HISTORY_FILE)  # كتابة ذرية لتفادي تلف الملف عند الانقطاع


def already_seen_id(entry_id: str, history: List[Dict]) -> bool:
    return any(rec.get("id") == entry_id for rec in history)


# ==============================================================================
# المعالجة بالذكاء الاصطناعي: إعادة الصياغة والترجمة والتصنيف
# ==============================================================================
SYSTEM_PROMPT = (
    "أنت محرر اقتصادي أول ومترجم صحفي مالي. "
    "مهمتك إعادة صياغة وترجمة الأخبار بدقة مالية شديدة وبلغة عربية فصحى رصينة "
    "تتبع أسلوب الهرم المقلوب، مع تصنيفها ضمن فئة واحدة مناسبة. "
    "يجب إخراج الرد بصيغة JSON حصرية."
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
5. صنّف الخبر ضمن فئة واحدة فقط من القائمة التالية باستخدام مفتاحها (key):
{categories_list}
   إن لم تنطبق أي فئة بدقة، استخدم "general".

الخبر:
العنوان الأصلي: {title}
المحتوى الخام: {raw_text}

أخرج الناتج بصيغة JSON مطابقة تماماً للمخطط التالي:
{{
  "title": "العنوان العربي المقترح",
  "html_body": "محتوى المقال بوسوم HTML",
  "category_key": "مفتاح الفئة المختارة من القائمة"
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


def resolve_category_id(category_key: str, categories: List[Dict], fallback_id: int) -> int:
    for cat in categories:
        if cat.get("key") == category_key:
            return cat.get("wp_category_id", fallback_id)
    return fallback_id


def resolve_category_name(category_key: str, categories: List[Dict]) -> str:
    for cat in categories:
        if cat.get("key") == category_key:
            return cat.get("name_ar", category_key)
    return "عام"


def process_content_with_ai(
    client: OpenAI, cfg: Config, title: str, raw_text: str, source_name: str, source_url: str
) -> Tuple[Optional[str], Optional[str], Optional[str]]:
    categories_list = "\n".join(
        f'   - {c["key"]}: {c.get("name_ar", c["key"])}' for c in cfg.categories
    ) or "   - general: عام"

    user_prompt = USER_PROMPT_TEMPLATE.format(
        title=title, raw_text=raw_text, categories_list=categories_list
    )
    try:
        response = client.chat.completions.create(
            model=cfg.openai_model,
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
        category_key = data.get("category_key", "general")
        return data["title"], full_content, category_key
    except Exception as e:
        log.error("خطأ أثناء معالجة المقال عبر الذكاء الاصطناعي: %s", e)
        return None, None, None


# ==============================================================================
# الموقع الإخباري الساكن — القناة الافتراضية (لا يحتاج ووردبريس ولا استضافة)
# ==============================================================================
def publish_to_static_site(cfg: Config, article: Dict) -> bool:
    if not cfg.enable_static_site:
        return True  # غير مفعّل — لا يُعتبر فشلاً
    try:
        articles = site_generator.save_article(ARTICLES_FILE, article)
        site_generator.build_site(cfg.site_output_dir, cfg.site_title, articles, cfg.categories)
        log.info("أُضيف للموقع الساكن بنجاح: %s", article["title"])
        return True
    except Exception as e:
        log.error("فشل بناء/تحديث الموقع الساكن: %s", e)
        return False


# ==============================================================================
# النشر عبر WordPress REST API (اختياري — لمن يملك موقع ووردبريس)
# ==============================================================================
def publish_to_wordpress(cfg: Config, title: str, content: str, category_id: int) -> bool:
    if not cfg.enable_wordpress:
        return True  # غير مفعّل — لا يُعتبر فشلاً

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
            log.info("نُشر في ووردبريس بنجاح: %s", title)
            return True
        log.error("فشل النشر في ووردبريس (%s): %s", response.status_code, response.text)
        return False
    except requests.RequestException as e:
        log.error("خطأ بالاتصال مع ووردبريس: %s", e)
        return False


# ==============================================================================
# النشر عبر تليجرام (اختياري)
# ==============================================================================
_ALLOWED_TELEGRAM_TAGS = ("b", "i", "a", "code", "pre")


def _strip_disallowed_tags(html: str) -> str:
    def repl(match: "re.Match") -> str:
        tag = match.group(1).lower().lstrip("/")
        return match.group(0) if tag in _ALLOWED_TELEGRAM_TAGS else ""
    return re.sub(r"</?([a-zA-Z0-9]+)[^>]*>", repl, html)


def html_to_telegram_text(html: str) -> str:
    text = re.sub(r"<strong>(.*?)</strong>", r"<b>\1</b>", html, flags=re.S)
    text = re.sub(r"<li>(.*?)</li>", r"• \1\n", text, flags=re.S)
    text = re.sub(r"</?ul>", "", text)
    text = re.sub(r"<p>(.*?)</p>", r"\1\n\n", text, flags=re.S)
    text = _strip_disallowed_tags(text)
    return text.strip()


def publish_to_telegram(cfg: Config, title: str, content_html: str) -> bool:
    if not cfg.enable_telegram:
        return True  # غير مفعّل — لا يُعتبر فشلاً
    if not cfg.telegram_bot_token or not cfg.telegram_chat_id:
        log.warning("تليجرام مفعّل لكن TELEGRAM_BOT_TOKEN أو TELEGRAM_CHAT_ID غير مضبوطين.")
        return False

    body_text = html_to_telegram_text(content_html)
    message = f"<b>{title}</b>\n\n{body_text}"[:4096]

    endpoint = f"https://api.telegram.org/bot{cfg.telegram_bot_token}/sendMessage"
    payload = {
        "chat_id": cfg.telegram_chat_id,
        "text": message,
        "parse_mode": "HTML",
        "disable_web_page_preview": False,
    }
    try:
        response = requests.post(endpoint, json=payload, timeout=REQUEST_TIMEOUT_SECONDS)
        if response.status_code == 200:
            log.info("نُشر في تليجرام بنجاح: %s", title)
            return True
        log.error("فشل النشر في تليجرام (%s): %s", response.status_code, response.text)
        return False
    except requests.RequestException as e:
        log.error("خطأ بالاتصال مع تليجرام: %s", e)
        return False


# ==============================================================================
# النشر عبر منصة X — مُعطّل افتراضياً، جاهز للتفعيل لاحقاً (ENABLE_X=true)
# ==============================================================================
def publish_to_x(cfg: Config, title: str, source_url: str) -> bool:
    if not cfg.enable_x:
        return True  # الميزة غير مفعّلة بعد — مجهّزة للاستخدام لاحقاً

    if not all([cfg.x_api_key, cfg.x_api_secret, cfg.x_access_token, cfg.x_access_secret]):
        log.warning("منصة X مفعّلة (ENABLE_X=true) لكن بيانات الاعتماد غير مكتملة في .env.")
        return False

    try:
        import tweepy  # استيراد اختياري — أضف tweepy إلى requirements.txt عند التفعيل
    except ImportError:
        log.warning("مكتبة tweepy غير مثبتة. ثبّتها عبر: pip install tweepy")
        return False

    try:
        client = tweepy.Client(
            consumer_key=cfg.x_api_key,
            consumer_secret=cfg.x_api_secret,
            access_token=cfg.x_access_token,
            access_token_secret=cfg.x_access_secret,
        )
        tweet_text = f"{title}\n{source_url}"[:280]
        client.create_tweet(text=tweet_text)
        log.info("نُشر على X بنجاح: %s", title)
        return True
    except Exception as e:
        log.error("فشل النشر على X: %s", e)
        return False


# ==============================================================================
# إشعارات الفشل (عبر تليجرام)
# ==============================================================================
def notify_admin(cfg: Config, message: str) -> None:
    if not cfg.enable_notifications:
        return
    chat_id = cfg.telegram_admin_chat_id or cfg.telegram_chat_id
    if not cfg.telegram_bot_token or not chat_id:
        log.warning("الإشعارات مفعّلة لكن TELEGRAM_BOT_TOKEN أو معرّف المحادثة الإداري غير مضبوط.")
        return
    endpoint = f"https://api.telegram.org/bot{cfg.telegram_bot_token}/sendMessage"
    try:
        requests.post(
            endpoint,
            json={"chat_id": chat_id, "text": f"⚠️ تنبيه من بوت BloomEconomy:\n{message}"},
            timeout=REQUEST_TIMEOUT_SECONDS,
        )
    except requests.RequestException as e:
        log.error("تعذّر إرسال إشعار الفشل: %s", e)


# ==============================================================================
# دورة العمل
# ==============================================================================
def execute_cycle(cfg: Config, client: OpenAI) -> None:
    history = get_processed_records()
    log.info("بدء فحص الخلاصات الإخبارية...")

    for feed_info in cfg.feeds:
        log.info("مراقبة المصدر: %s", feed_info["name"])
        try:
            feed = feedparser.parse(feed_info["url"])
        except Exception as e:
            log.error("خطأ أثناء قراءة خلاصة %s: %s", feed_info["name"], e)
            notify_admin(cfg, f"تعذّرت قراءة خلاصة {feed_info['name']}:\n{e}")
            continue

        for entry in feed.entries[:MAX_ENTRIES_PER_FEED]:
            entry_id = entry.get("id", entry.get("link"))
            if not entry_id or already_seen_id(entry_id, history):
                continue

            title = entry.get("title", "")
            summary = entry.get("summary", entry.get("description", ""))
            url = entry.get("link", "")

            new_tokens = tokenize_title(title)
            dup, similar_title = is_duplicate(
                new_tokens, history, cfg.duplicate_similarity_threshold, cfg.duplicate_window_hours
            )
            if dup:
                log.info("تخطّي خبر مشابه لخبر منشور مسبقاً: '%s' ~ '%s'", title, similar_title)
                record_processed(history, entry_id, title, new_tokens)
                continue

            log.info("خبر جديد تم رصده: %s", title)

            ai_title, ai_content, category_key = process_content_with_ai(
                client, cfg, title, summary, feed_info["name"], url
            )
            if not (ai_title and ai_content):
                notify_admin(cfg, f"فشلت معالجة الذكاء الاصطناعي للخبر:\n{title}\n{url}")
                continue

            category_id = resolve_category_id(
                category_key or "general", cfg.categories, feed_info.get("category_id", 1)
            )
            category_name = resolve_category_name(category_key or "general", cfg.categories)

            article = {
                "id": entry_id,
                "title": ai_title,
                "slug": site_generator.slugify(entry_id, ai_title),
                "html_body": ai_content,
                "category_key": category_key or "general",
                "category_name": category_name,
                "source_name": feed_info["name"],
                "source_url": url,
                "published_at_display": time.strftime("%Y-%m-%d %H:%M"),
            }

            site_ok = publish_to_static_site(cfg, article)
            wp_ok = publish_to_wordpress(cfg, ai_title, ai_content, category_id)
            tg_ok = publish_to_telegram(cfg, ai_title, ai_content)
            x_ok = publish_to_x(cfg, ai_title, url)

            if cfg.enable_static_site and not site_ok:
                notify_admin(cfg, f"فشل تحديث الموقع الساكن للمقال:\n{ai_title}")
            if cfg.enable_wordpress and not wp_ok:
                notify_admin(cfg, f"فشل النشر في ووردبريس للمقال:\n{ai_title}")
            if cfg.enable_telegram and not tg_ok:
                notify_admin(cfg, f"فشل النشر في تليجرام للمقال:\n{ai_title}")
            if cfg.enable_x and not x_ok:
                notify_admin(cfg, f"فشل النشر على X للمقال:\n{ai_title}")

            # يُعتبر الخبر "منشوراً" إذا نجحت أي قناة مُفعَّلة على الأقل
            attempted = [
                ok for enabled, ok in (
                    (cfg.enable_static_site, site_ok),
                    (cfg.enable_wordpress, wp_ok),
                    (cfg.enable_telegram, tg_ok),
                    (cfg.enable_x, x_ok),
                )
                if enabled
            ]
            success = any(attempted) if attempted else False

            if success:
                record_processed(history, entry_id, title, new_tokens)
                time.sleep(PUBLISH_DELAY_SECONDS)  # فاصل أمان بين عمليات النشر
            else:
                log.warning("لم ينجح النشر في أي قناة مُفعَّلة للخبر: %s", title)
                notify_admin(cfg, f"فشل النشر في جميع القنوات المُفعَّلة للخبر:\n{ai_title}")


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
        help="تنفيذ دورة فحص ونشر واحدة ثم الخروج (مناسب للتشغيل عبر cron/launchd)",
    )
    args = parser.parse_args()

    cfg = load_config()
    if not cfg.feeds:
        log.error("لا توجد خلاصات RSS معرّفة في feeds.json — أضف مصدراً واحداً على الأقل.")
        sys.exit(1)

    client = OpenAI(api_key=cfg.openai_api_key)

    try:
        if args.once:
            run_once(cfg, client)
        else:
            run_forever(cfg, client)
    except Exception as e:
        log.exception("توقف البوت بسبب خطأ غير متوقع.")
        notify_admin(cfg, f"توقف البوت بسبب خطأ غير متوقع:\n{e}")
        raise


if __name__ == "__main__":
    main()
