"""
إعدادات المنصة: كل القيم الحساسة تُقرأ من متغيرات البيئة (ملف .env) بدلاً من
كتابتها مباشرة في الكود، لتفادي تسريب المفاتيح عند رفع المشروع إلى GitHub.
"""

import os
import json
import sys
from dataclasses import dataclass, field
from typing import List, Dict

from dotenv import load_dotenv

load_dotenv()

BASE_DIR = os.path.dirname(os.path.abspath(__file__))
FEEDS_FILE = os.path.join(BASE_DIR, "feeds.json")
CATEGORIES_FILE = os.path.join(BASE_DIR, "categories.json")
HISTORY_FILE = os.path.join(BASE_DIR, "published_history.json")
ARTICLES_FILE = os.path.join(BASE_DIR, "articles.json")
DEFAULT_SITE_OUTPUT_DIR = os.path.join(BASE_DIR, "docs")

# الوحيد الإلزامي فعلياً هو مفتاح OpenAI — أي قناة نشر أخرى (ووردبريس، تليجرام،
# الموقع الساكن) تُفعَّل اختيارياً عبر ENABLE_* الخاص بها
REQUIRED_ENV_VARS = [
    "OPENAI_API_KEY",
]


def _bool_env(name: str, default: bool = False) -> bool:
    val = os.getenv(name)
    if val is None:
        return default
    return val.strip().lower() in ("1", "true", "yes", "on")


@dataclass
class Config:
    # OpenAI
    openai_api_key: str
    openai_model: str

    # عام
    poll_interval_minutes: int
    feeds: List[Dict] = field(default_factory=list)
    categories: List[Dict] = field(default_factory=list)
    duplicate_similarity_threshold: float = 0.6
    duplicate_window_hours: int = 48

    # الموقع الإخباري الساكن (القناة الافتراضية — لا يحتاج ووردبريس ولا استضافة)
    enable_static_site: bool = True
    site_title: str = "BloomEconomy — أخبار اقتصادية"
    site_base_url: str = ""
    site_output_dir: str = DEFAULT_SITE_OUTPUT_DIR

    # إعلانات جوجل AdSense (اختياري — معطّل افتراضياً حتى تحصل على حساب مقبول)
    enable_adsense: bool = False
    adsense_client_id: str = ""

    # ووردبريس (اختياري — مُعطّل افتراضياً لمن لا يملك موقع ووردبريس)
    enable_wordpress: bool = False
    wp_base_url: str = ""
    wp_username: str = ""
    wp_app_password: str = ""
    post_status: str = "publish"

    # تليجرام (اختياري)
    enable_telegram: bool = False
    telegram_bot_token: str = ""
    telegram_chat_id: str = ""

    # الإشعارات عند الفشل (اختياري — تُرسل عبر تليجرام)
    enable_notifications: bool = False
    telegram_admin_chat_id: str = ""

    # منصة X (اختياري ومُعطّل افتراضياً — للتفعيل لاحقاً)
    enable_x: bool = False
    x_api_key: str = ""
    x_api_secret: str = ""
    x_access_token: str = ""
    x_access_secret: str = ""


def _load_json(path: str) -> List[Dict]:
    if not os.path.exists(path):
        return []
    with open(path, "r", encoding="utf-8") as f:
        return json.load(f)


def load_config() -> Config:
    missing = [v for v in REQUIRED_ENV_VARS if not os.getenv(v)]
    if missing:
        sys.stderr.write(
            "[-] متغيرات بيئة ناقصة: "
            + ", ".join(missing)
            + "\n[-] انسخ .env.example إلى .env وعبّئ القيم المطلوبة قبل التشغيل"
            + " (أو شغّل: bash setup_env.sh)\n"
        )
        sys.exit(1)

    enable_wordpress = _bool_env("ENABLE_WORDPRESS", False)
    if enable_wordpress:
        wp_missing = [v for v in ("WP_BASE_URL", "WP_USERNAME", "WP_APP_PASSWORD") if not os.getenv(v)]
        if wp_missing:
            sys.stderr.write(
                "[-] ENABLE_WORDPRESS=true لكن متغيرات ناقصة: " + ", ".join(wp_missing) + "\n"
            )
            sys.exit(1)

    return Config(
        openai_api_key=os.getenv("OPENAI_API_KEY", ""),
        openai_model=os.getenv("OPENAI_MODEL", "gpt-4o-mini"),
        poll_interval_minutes=int(os.getenv("POLL_INTERVAL_MINUTES", "30")),
        feeds=_load_json(FEEDS_FILE),
        categories=_load_json(CATEGORIES_FILE),
        duplicate_similarity_threshold=float(os.getenv("DUPLICATE_SIMILARITY_THRESHOLD", "0.6")),
        duplicate_window_hours=int(os.getenv("DUPLICATE_WINDOW_HOURS", "48")),
        enable_static_site=_bool_env("ENABLE_STATIC_SITE", True),
        site_title=os.getenv("SITE_TITLE", "BloomEconomy — أخبار اقتصادية"),
        site_base_url=os.getenv("SITE_BASE_URL", ""),
        site_output_dir=os.getenv("SITE_OUTPUT_DIR", DEFAULT_SITE_OUTPUT_DIR),
        enable_adsense=_bool_env("ENABLE_ADSENSE", False),
        adsense_client_id=os.getenv("ADSENSE_CLIENT_ID", ""),
        enable_wordpress=enable_wordpress,
        wp_base_url=os.getenv("WP_BASE_URL", "").rstrip("/"),
        wp_username=os.getenv("WP_USERNAME", ""),
        wp_app_password=os.getenv("WP_APP_PASSWORD", ""),
        post_status=os.getenv("POST_STATUS", "publish"),
        enable_telegram=_bool_env("ENABLE_TELEGRAM", False),
        telegram_bot_token=os.getenv("TELEGRAM_BOT_TOKEN", ""),
        telegram_chat_id=os.getenv("TELEGRAM_CHAT_ID", ""),
        enable_notifications=_bool_env("ENABLE_NOTIFICATIONS", False),
        telegram_admin_chat_id=os.getenv("TELEGRAM_ADMIN_CHAT_ID", ""),
        enable_x=_bool_env("ENABLE_X", False),
        x_api_key=os.getenv("X_API_KEY", ""),
        x_api_secret=os.getenv("X_API_SECRET", ""),
        x_access_token=os.getenv("X_ACCESS_TOKEN", ""),
        x_access_secret=os.getenv("X_ACCESS_SECRET", ""),
    )
