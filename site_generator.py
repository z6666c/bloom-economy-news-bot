"""
مولّد الموقع الإخباري الساكن (Static Site) — يبني موقعاً كاملاً بصفحات HTML
جاهزة للنشر مجاناً عبر GitHub Pages، دون الحاجة لووردبريس أو أي استضافة.
"""

import hashlib
import html
import json
import os
import re
from datetime import datetime, timezone
from typing import Dict, List

ARTICLES_PER_PAGE = 30
MAX_STORED_ARTICLES = 500
SECTION_SIZE = 6  # عدد الأخبار المعروضة لكل فئة في قسمها على الصفحة الرئيسية

# لون مميز لكل فئة (يُستخدم في شارات الأخبار وحدود البطاقات) — أي فئة غير
# مذكورة هنا تأخذ لوناً تلقائياً من القائمة الاحتياطية أدناه بالتناوب
CATEGORY_COLORS = {
    "markets": "#0b5fff",
    "oil_energy": "#b45309",
    "crypto": "#7c3aed",
    "companies": "#0f766e",
    "monetary_policy": "#be123c",
    "general": "#475569",
    "other": "#6b7280",
}
_FALLBACK_PALETTE = ["#0b5fff", "#b45309", "#7c3aed", "#0f766e", "#be123c", "#475569", "#0891b2", "#a16207"]

FAVICON_SVG = (
    "data:image/svg+xml,"
    "%3Csvg xmlns='http://www.w3.org/2000/svg' viewBox='0 0 100 100'%3E"
    "%3Crect width='100' height='100' rx='20' fill='%230b5fff'/%3E"
    "%3Cpath d='M22 68 L40 46 L54 58 L78 30' stroke='white' stroke-width='7' "
    "fill='none' stroke-linecap='round' stroke-linejoin='round'/%3E"
    "%3Ccircle cx='78' cy='30' r='6' fill='white'/%3E"
    "%3C/svg%3E"
)


def category_color(key: str, categories: List[Dict]) -> str:
    if key in CATEGORY_COLORS:
        return CATEGORY_COLORS[key]
    for i, cat in enumerate(categories):
        if cat.get("key") == key:
            return _FALLBACK_PALETTE[i % len(_FALLBACK_PALETTE)]
    return _FALLBACK_PALETTE[0]

CSS = """
:root {
  --bg: #f4f5f7;
  --card-bg: #ffffff;
  --text: #14171f;
  --muted: #6b7280;
  --brand: #0b5fff;
  --brand-dark: #06407a;
  --border: #e5e7eb;
  --badge-bg: #eef3ff;
  --shadow-sm: 0 1px 2px rgba(16,24,40,0.05);
  --shadow-md: 0 8px 24px rgba(16,24,40,0.09);
}
* { box-sizing: border-box; }
html { scroll-behavior: smooth; }
body {
  margin: 0;
  background: var(--bg);
  color: var(--text);
  font-family: 'Tajawal', 'Segoe UI', Tahoma, Arial, sans-serif;
  line-height: 1.8;
  -webkit-font-smoothing: antialiased;
}
a { color: inherit; }
header.site-header {
  position: sticky;
  top: 0;
  z-index: 10;
  background: linear-gradient(120deg, var(--brand-dark), var(--brand) 130%);
  color: #fff;
  padding: 18px 24px;
  box-shadow: var(--shadow-md);
}
header.site-header .wrap {
  max-width: 1120px;
  margin: 0 auto;
  display: flex;
  flex-wrap: wrap;
  align-items: center;
  justify-content: space-between;
  gap: 14px;
}
header.site-header h1 {
  margin: 0;
  font-size: 1.45rem;
  font-weight: 700;
  letter-spacing: -0.01em;
}
header.site-header h1 a {
  color: #fff;
  text-decoration: none;
  display: flex;
  align-items: center;
  gap: 8px;
}
header.site-header h1 a::before {
  content: "📈";
  font-size: 1.2rem;
}
nav.categories {
  display: flex;
  flex-wrap: wrap;
  gap: 8px;
}
nav.categories a {
  color: #fff;
  text-decoration: none;
  background: rgba(255,255,255,0.14);
  padding: 7px 16px;
  border-radius: 999px;
  font-size: 0.88rem;
  font-weight: 500;
  transition: background .15s ease;
}
nav.categories a:hover { background: rgba(255,255,255,0.32); }
main {
  max-width: 1120px;
  margin: 0 auto;
  padding: 32px 24px 70px;
}
.grid {
  display: grid;
  grid-template-columns: repeat(auto-fill, minmax(270px, 1fr));
  gap: 22px;
}
.hero {
  display: block;
  background: var(--card-bg);
  border: 1px solid var(--border);
  border-radius: 16px;
  padding: 32px;
  margin-bottom: 44px;
  text-decoration: none;
  color: inherit;
  box-shadow: var(--shadow-sm);
  transition: box-shadow .18s ease, transform .18s ease;
  border-inline-start: 5px solid var(--hero-accent, var(--brand));
}
.hero:hover { box-shadow: var(--shadow-md); transform: translateY(-2px); }
.hero .eyebrow {
  display: flex;
  align-items: center;
  gap: 8px;
  font-size: 0.8rem;
  color: var(--hero-accent, var(--brand));
  font-weight: 700;
  margin-bottom: 12px;
  text-transform: uppercase;
  letter-spacing: 0.03em;
}
.hero h1 {
  margin: 0 0 14px;
  font-size: 1.75rem;
  line-height: 1.45;
  color: var(--text);
}
.hero .excerpt {
  font-size: 1.02rem;
  color: #374151;
  margin: 0 0 14px;
  max-width: 760px;
}
.home-section {
  margin-bottom: 44px;
}
.home-section:last-child {
  margin-bottom: 0;
}
.section-head {
  display: flex;
  align-items: baseline;
  justify-content: space-between;
  flex-wrap: wrap;
  gap: 8px;
  margin-bottom: 18px;
  padding-bottom: 12px;
  border-bottom: 2px solid var(--border);
}
.section-head h2 {
  margin: 0;
  font-size: 1.25rem;
  font-weight: 700;
  color: var(--text);
  display: flex;
  align-items: center;
  gap: 10px;
}
.section-head h2::before {
  content: "";
  display: inline-block;
  width: 10px;
  height: 10px;
  border-radius: 3px;
  background: var(--section-accent, var(--brand));
}
.section-head .see-all {
  font-size: 0.85rem;
  color: var(--brand);
  text-decoration: none;
  white-space: nowrap;
  font-weight: 500;
}
.section-head .see-all:hover { text-decoration: underline; }
.card {
  background: var(--card-bg);
  border: 1px solid var(--border);
  border-inline-start: 4px solid var(--card-accent, var(--brand));
  border-radius: 12px;
  padding: 20px;
  display: flex;
  flex-direction: column;
  gap: 10px;
  box-shadow: var(--shadow-sm);
  transition: box-shadow .15s ease, transform .15s ease;
}
.card:hover { box-shadow: var(--shadow-md); transform: translateY(-3px); }
.badge {
  display: inline-block;
  background: var(--badge-bg);
  color: var(--badge-color, var(--brand-dark));
  font-size: 0.75rem;
  font-weight: 600;
  padding: 4px 12px;
  border-radius: 999px;
  align-self: flex-start;
}
.card h2 { margin: 0; font-size: 1.12rem; line-height: 1.55; font-weight: 700; }
.card h2 a { text-decoration: none; }
.card h2 a:hover { color: var(--brand); }
.meta { color: var(--muted); font-size: 0.82rem; }
.excerpt { color: #4b5563; font-size: 0.95rem; }
article.full {
  max-width: 760px;
  margin: 0 auto;
}
article.full h1 { font-size: 1.85rem; line-height: 1.5; margin: 14px 0 10px; }
article.full .meta { margin-bottom: 28px; }
article.full .content { font-size: 1.05rem; }
article.full .content p { margin: 0 0 18px; }
article.full .content ul { padding-inline-start: 24px; margin: 0 0 18px; }
article.full .content li { margin-bottom: 8px; }
.back-link {
  display: inline-flex;
  align-items: center;
  margin-bottom: 24px;
  color: var(--brand);
  text-decoration: none;
  font-size: 0.92rem;
  font-weight: 500;
}
.back-link:hover { text-decoration: underline; }
.category-title {
  font-size: 1.6rem;
  margin: 0 0 24px;
  padding-bottom: 14px;
  border-bottom: 3px solid var(--cat-accent, var(--brand));
  display: inline-block;
}
footer.site-footer {
  text-align: center;
  color: var(--muted);
  padding: 34px 20px;
  font-size: 0.85rem;
  border-top: 1px solid var(--border);
}
footer.site-footer .updated { display: block; margin-top: 6px; font-size: 0.78rem; opacity: 0.8; }
.empty-state {
  text-align: center;
  color: var(--muted);
  padding: 90px 20px;
  font-size: 1.05rem;
}
@media (max-width: 640px) {
  header.site-header h1 { font-size: 1.2rem; }
  .hero { padding: 22px; }
  .hero h1 { font-size: 1.35rem; }
}
"""

PAGE_TEMPLATE = """<!doctype html>
<html lang="ar" dir="rtl">
<head>
<meta charset="utf-8">
<meta name="viewport" content="width=device-width, initial-scale=1">
<title>{title}</title>
<meta name="description" content="{description}">
<meta property="og:type" content="{og_type}">
<meta property="og:title" content="{title}">
<meta property="og:description" content="{description}">
<link rel="icon" href="{favicon}">
<link rel="preconnect" href="https://fonts.googleapis.com">
<link href="https://fonts.googleapis.com/css2?family=Tajawal:wght@400;500;700&display=swap" rel="stylesheet">
<link rel="stylesheet" href="{css_path}">
</head>
<body>
<header class="site-header">
  <div class="wrap">
    <h1><a href="{home_path}">{site_title}</a></h1>
    <nav class="categories">
      {nav_links}
    </nav>
  </div>
</header>
<main>
{body}
</main>
<footer class="site-footer">
  موقع أخبار مؤتمت — يُحدَّث تلقائياً بواسطة الذكاء الاصطناعي من مصادر اقتصادية عالمية.
  <span class="updated">آخر تحديث: {updated_at}</span>
</footer>
</body>
</html>
"""


def slugify(entry_id: str, title: str) -> str:
    date_prefix = datetime.now(timezone.utc).strftime("%Y%m%d")
    short_hash = hashlib.md5(entry_id.encode("utf-8")).hexdigest()[:10]
    return f"{date_prefix}-{short_hash}"


def _esc(text: str) -> str:
    return html.escape(text or "", quote=True)


def _nav_links(categories: List[Dict], relative_prefix: str = "") -> str:
    links = [f'<a href="{relative_prefix}index.html">الرئيسية</a>']
    for cat in categories:
        links.append(
            f'<a href="{relative_prefix}category/{_esc(cat["key"])}.html">{_esc(cat.get("name_ar", cat["key"]))}</a>'
        )
    return "\n      ".join(links)


def _excerpt_of(article: Dict, length: int = 160) -> str:
    excerpt = re.sub(r"<[^>]+>", " ", article.get("html_body", ""))
    excerpt = re.sub(r"\s+", " ", excerpt).strip()[:length] + "…"
    return excerpt


def _section_html(cat: Dict, cat_articles: List[Dict], categories: List[Dict], link_enabled: bool = True) -> str:
    shown = cat_articles[:SECTION_SIZE]
    accent = category_color(cat["key"], categories)
    cards = "\n".join(_card_html(a, categories=categories) for a in shown)
    more_link = ""
    if link_enabled and len(cat_articles) > SECTION_SIZE:
        more_link = f'<a class="see-all" href="category/{_esc(cat["key"])}.html">عرض كل أخبار {_esc(cat.get("name_ar", cat["key"]))} ←</a>'
    return f"""
    <section class="home-section">
      <div class="section-head" style="--section-accent:{accent}">
        <h2>{_esc(cat.get('name_ar', cat['key']))}</h2>
        {more_link}
      </div>
      <div class="grid">{cards}</div>
    </section>"""


def _hero_html(article: Dict, categories: List[Dict], path_prefix: str = "") -> str:
    accent = category_color(article.get("category_key", ""), categories)
    excerpt = _excerpt_of(article, 220)
    return f"""
    <a class="hero" style="--hero-accent:{accent}" href="{path_prefix}articles/{article['slug']}.html">
      <div class="eyebrow">🔥 الأحدث · {_esc(article.get('category_name', 'عام'))}</div>
      <h1>{_esc(article['title'])}</h1>
      <p class="excerpt">{_esc(excerpt)}</p>
      <p class="meta">{_esc(article.get('source_name', ''))} · {article.get('published_at_display', '')}</p>
    </a>"""


def _card_html(article: Dict, path_prefix: str = "", categories: List[Dict] = None) -> str:
    accent = category_color(article.get("category_key", ""), categories or [])
    excerpt = _excerpt_of(article)
    return f"""
    <div class="card" style="--card-accent:{accent}">
      <span class="badge" style="--badge-color:{accent}">{_esc(article.get('category_name', 'عام'))}</span>
      <h2><a href="{path_prefix}articles/{article['slug']}.html">{_esc(article['title'])}</a></h2>
      <p class="excerpt">{_esc(excerpt)}</p>
      <p class="meta">{_esc(article.get('source_name', ''))} · {article.get('published_at_display', '')}</p>
    </div>"""


def load_articles(path: str) -> List[Dict]:
    if not os.path.exists(path):
        return []
    try:
        with open(path, "r", encoding="utf-8") as f:
            return json.load(f)
    except (json.JSONDecodeError, OSError):
        return []


def save_article(path: str, article: Dict) -> List[Dict]:
    articles = load_articles(path)
    articles.insert(0, article)  # الأحدث أولاً
    if len(articles) > MAX_STORED_ARTICLES:
        articles = articles[:MAX_STORED_ARTICLES]
    tmp_path = path + ".tmp"
    with open(tmp_path, "w", encoding="utf-8") as f:
        json.dump(articles, f, ensure_ascii=False, indent=2)
    os.replace(tmp_path, path)
    return articles


def build_site(output_dir: str, site_title: str, articles: List[Dict], categories: List[Dict]) -> None:
    os.makedirs(output_dir, exist_ok=True)
    os.makedirs(os.path.join(output_dir, "articles"), exist_ok=True)
    os.makedirs(os.path.join(output_dir, "category"), exist_ok=True)
    os.makedirs(os.path.join(output_dir, "assets"), exist_ok=True)

    # يمنع GitHub Pages من معالجة الموقع عبر Jekyll (يحافظ على الملفات كما هي)
    open(os.path.join(output_dir, ".nojekyll"), "w").close()

    with open(os.path.join(output_dir, "assets", "style.css"), "w", encoding="utf-8") as f:
        f.write(CSS)

    updated_at = datetime.now(timezone.utc).strftime("%Y-%m-%d %H:%M UTC")
    common = dict(favicon=FAVICON_SVG, updated_at=updated_at)

    # الصفحة الرئيسية — قصة بارزة أعلى الصفحة، ثم أقسام حسب الفئة
    if articles:
        hero_article = articles[0]
        rest = articles[1:]
        sections = []
        for cat in categories:
            cat_articles = [a for a in rest if a.get("category_key") == cat["key"]]
            if cat_articles:
                sections.append(_section_html(cat, cat_articles, categories))
        # أي مقال بفئة غير مذكورة في categories.json يُجمع تحت قسم "أخبار أخرى"
        known_keys = {c["key"] for c in categories}
        other_articles = [a for a in rest if a.get("category_key") not in known_keys]
        if other_articles:
            sections.append(_section_html(
                {"key": "other", "name_ar": "أخبار أخرى"}, other_articles, categories, link_enabled=False
            ))
        body = _hero_html(hero_article, categories) + "\n".join(sections)
    else:
        body = '<div class="empty-state">لا توجد أخبار منشورة بعد — البوت سيبدأ النشر تلقائياً بمجرد تشغيله.</div>'

    index_html = PAGE_TEMPLATE.format(
        title=site_title,
        description="آخر الأخبار الاقتصادية مترجمة وموثّقة تلقائياً بالذكاء الاصطناعي",
        og_type="website",
        css_path="assets/style.css",
        home_path="index.html",
        site_title=_esc(site_title),
        nav_links=_nav_links(categories),
        body=body,
        **common,
    )
    with open(os.path.join(output_dir, "index.html"), "w", encoding="utf-8") as f:
        f.write(index_html)

    # صفحات المقالات
    for article in articles:
        accent = category_color(article.get("category_key", ""), categories)
        article_body = f"""
    <a class="back-link" href="../index.html">→ الرئيسية</a>
    <article class="full">
      <span class="badge" style="--badge-color:{accent}">{_esc(article.get('category_name', 'عام'))}</span>
      <h1>{_esc(article['title'])}</h1>
      <p class="meta">{_esc(article.get('source_name', ''))} · {article.get('published_at_display', '')}</p>
      <div class="content">{article.get('html_body', '')}</div>
    </article>"""
        article_html = PAGE_TEMPLATE.format(
            title=f"{article['title']} — {site_title}",
            description=_excerpt_of(article, 150),
            og_type="article",
            css_path="../assets/style.css",
            home_path="../index.html",
            site_title=_esc(site_title),
            nav_links=_nav_links(categories, relative_prefix="../"),
            body=article_body,
            **common,
        )
        with open(os.path.join(output_dir, "articles", f"{article['slug']}.html"), "w", encoding="utf-8") as f:
            f.write(article_html)

    # صفحات التصنيفات
    for cat in categories:
        accent = category_color(cat["key"], categories)
        cat_articles = [a for a in articles if a.get("category_key") == cat["key"]]
        if cat_articles:
            cards = "\n".join(_card_html(a, path_prefix="../", categories=categories) for a in cat_articles[:ARTICLES_PER_PAGE])
            body = f'<h1 class="category-title" style="--cat-accent:{accent}">{_esc(cat.get("name_ar", cat["key"]))}</h1><div class="grid">{cards}</div>'
        else:
            body = f'<h1 class="category-title" style="--cat-accent:{accent}">{_esc(cat.get("name_ar", cat["key"]))}</h1><div class="empty-state">لا توجد أخبار في هذا التصنيف بعد.</div>'
        cat_html = PAGE_TEMPLATE.format(
            title=f"{cat.get('name_ar', cat['key'])} — {site_title}",
            description=f"أخبار {cat.get('name_ar', cat['key'])}",
            og_type="website",
            css_path="../assets/style.css",
            home_path="../index.html",
            site_title=_esc(site_title),
            nav_links=_nav_links(categories, relative_prefix="../"),
            body=body,
            **common,
        )
        with open(os.path.join(output_dir, "category", f"{cat['key']}.html"), "w", encoding="utf-8") as f:
            f.write(cat_html)
