"""
يعيد بناء الموقع الساكن بالكامل من الأخبار المخزَّنة حالياً في articles.json،
دون انتظار خبر جديد. مفيد بعد أي تحديث في تصميم site_generator.py لرؤية
النتيجة فوراً على كل المقالات الموجودة مسبقاً.

الاستخدام:
    python3 rebuild_site.py
"""

from config import ARTICLES_FILE, load_config
from site_generator import build_site, load_articles


def main() -> None:
    cfg = load_config()
    articles = load_articles(ARTICLES_FILE)
    build_site(
        cfg.site_output_dir,
        cfg.site_title,
        articles,
        cfg.categories,
        enable_adsense=cfg.enable_adsense,
        adsense_client_id=cfg.adsense_client_id,
    )
    print(f"[+] تم إعادة بناء الموقع ({len(articles)} مقال) في: {cfg.site_output_dir}")


if __name__ == "__main__":
    main()
