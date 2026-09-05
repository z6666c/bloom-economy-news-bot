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
HISTORY_FILE = os.path.join(BASE_DIR, "published_history.json")

REQUIRED_ENV_VARS = [
    "OPENAI_API_KEY",
    "WP_BASE_URL",
    "WP_USERNAME",
    "WP_APP_PASSWORD",
]


@dataclass
class Config:
    openai_api_key: str
    openai_model: str
    wp_base_url: str
    wp_username: str
    wp_app_password: str
    post_status: str
    poll_interval_minutes: int
    feeds: List[Dict] = field(default_factory=list)


def _load_feeds() -> List[Dict]:
    if not os.path.exists(FEEDS_FILE):
        return []
    with open(FEEDS_FILE, "r", encoding="utf-8") as f:
        return json.load(f)


def load_config() -> Config:
    missing = [v for v in REQUIRED_ENV_VARS if not os.getenv(v)]
    if missing:
        sys.stderr.write(
            "[-] متغيرات بيئة ناقصة: "
            + ", ".join(missing)
            + "\n[-] انسخ .env.example إلى .env وعبّئ القيم المطلوبة قبل التشغيل.\n"
        )
        sys.exit(1)

    return Config(
        openai_api_key=os.getenv("OPENAI_API_KEY", ""),
        openai_model=os.getenv("OPENAI_MODEL", "gpt-4o-mini"),
        wp_base_url=os.getenv("WP_BASE_URL", "").rstrip("/"),
        wp_username=os.getenv("WP_USERNAME", ""),
        wp_app_password=os.getenv("WP_APP_PASSWORD", ""),
        post_status=os.getenv("POST_STATUS", "publish"),
        poll_interval_minutes=int(os.getenv("POLL_INTERVAL_MINUTES", "30")),
        feeds=_load_feeds(),
    )
