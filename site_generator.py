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

CSS = """
:root {
  --bg: #f7f8fa;
  --card-bg: #ffffff;
  --text: #1a1d23;
  --muted: #6b7280;
  --brand: #0b5fff;
  --brand-dark: #06407a;
  --border: #e5e7eb;
  --badge-bg: #eef3ff;
}
* { box-sizing: border-box; }
body {
  margin: 0;
  background: var(--bg);
  color: var(--text);
  font-family: 'Tajawal', 'Segoe UI', Tahoma, Arial, sans-serif;
  line-height: 1.8;
}
header.site-header {
  background: linear-gradient(135deg, var(--brand), var(--brand-dark));
  color: #fff;
  padding: 28px 20px;
}
header.site-header .wrap {
  max-width: 1000px;
  margin: 0 auto;
  display: flex;
  flex-wrap: wrap;
  align-items: center;
  justify-content: space-between;
  gap: 12px;
}
header.site-header h1 {
  margin: 0;
  font-size: 1.6rem;
}
header.site-header h1 a { color: #fff; text-decoration: none; }
nav.categories {
  display: flex;
  flex-wrap: wrap;
  gap: 10px;
}
nav.categories a {
  color: #fff;
  text-decoration: none;
  background: rgba(255,255,255,0.15);
  padding: 6px 14px;
  border-radius: 999px;
  font-size: 0.9rem;
}
nav.categories a:hover { background: rgba(255,255,255,0.3); }
main {
  max-width: 1000px;
  margin: 0 auto;
  padding: 24px 20px 60px;
}
.grid {
  display: grid;
  grid-template-columns: repeat(auto-fill, minmax(260px, 1fr));
  gap: 20px;
}
.card {
  background: var(--card-bg);
  border: 1px solid var(--border);
  border-radius: 12px;
  padding: 18px;
  display: flex;
  flex-direction: column;
  gap: 10px;
  transition: box-shadow .15s ease, transform .15s ease;
}
.card:hover { box-shadow: 0 6px 18px rgba(0,0,0,0.08); transform: translateY(-2px); }
.badge {
  display: inline-block;
  background: var(--badge-bg);
  color: var(--brand-dark);
  font-size: 0.78rem;
  padding: 3px 10px;
  border-radius: 999px;
  align-self: flex-start;
}
.card h2 { margin: 0; font-size: 1.15rem; line-height: 1.5; }
.card h2 a { color: var(--text); text-decoration: none; }
.card h2 a:hover { color: var(--brand); }
.meta { color: var(--muted); font-size: 0.85rem; }
.excerpt { color: #374151; font-size: 0.95rem; }
article.full h1 { font-size: 1.7rem; margin-bottom: 4px; }
article.full .meta { margin-bottom: 20px; }
article.full .content p { margin: 0 0 16px; }
article.full .content ul { padding-inline-start: 22px; }
.back-link { display: inline-block; margin-bottom: 20px; color: var(--brand); text-decoration: none; }
.back-link:hover { text-decoration: underline; }
footer.site-footer {
  text-align: center;
  color: var(--muted);
  padding: 30px 20px;
  font-size: 0.85rem;
  border-top: 1px solid var(--border);
}
.empty-state {
  text-align: center;
  color: var(--muted);
  padding: 80px 20px;
  font-size: 1.05rem;
}
"""

PAGE_TEMPLATE = """<!doctype html>
<html lang="ar" dir="rtl">
<head>
<meta charset="utf-8">
<meta name="viewport" content="width=device-width, initial-scale=1">
<title>{title}</title>
<meta name="description" content="{description}">
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


def _card_html(article: Dict, path_prefix: str = "") -> str:
    excerpt = re.sub(r"<[^>]+>", " ", article.get("html_body", ""))
    excerpt = re.sub(r"\s+", " ", excerpt).strip()[:160] + "…"
    return f"""
    <div class="card">
      <span class="badge">{_esc(article.get('category_name', 'عام'))}</span>
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

    # الصفحة الرئيسية
    if articles:
        cards = "\n".join(_card_html(a) for a in articles[:ARTICLES_PER_PAGE])
        body = f'<div class="grid">{cards}</div>'
    else:
        body = '<div class="empty-state">لا توجد أخبار منشورة بعد — البوت سيبدأ النشر تلقائياً بمجرد تشغيله.</div>'

    index_html = PAGE_TEMPLATE.format(
        title=site_title,
        description="آخر الأخبار الاقتصادية مترجمة وموثّقة تلقائياً",
        css_path="assets/style.css",
        home_path="index.html",
        site_title=_esc(site_title),
        nav_links=_nav_links(categories),
        body=body,
    )
    with open(os.path.join(output_dir, "index.html"), "w", encoding="utf-8") as f:
        f.write(index_html)

    # صفحات المقالات
    for article in articles:
        article_body = f"""
    <a class="back-link" href="../index.html">→ الرئيسية</a>
    <article class="full">
      <span class="badge">{_esc(article.get('category_name', 'عام'))}</span>
      <h1>{_esc(article['title'])}</h1>
      <p class="meta">{_esc(article.get('source_name', ''))} · {article.get('published_at_display', '')}</p>
      <div class="content">{article.get('html_body', '')}</div>
    </article>"""
        article_html = PAGE_TEMPLATE.format(
            title=f"{article['title']} — {site_title}",
            description=re.sub(r"<[^>]+>", " ", article.get("html_body", ""))[:150],
            css_path="../assets/style.css",
            home_path="../index.html",
            site_title=_esc(site_title),
            nav_links=_nav_links(categories, relative_prefix="../"),
            body=article_body,
        )
        with open(os.path.join(output_dir, "articles", f"{article['slug']}.html"), "w", encoding="utf-8") as f:
            f.write(article_html)

    # صفحات التصنيفات
    for cat in categories:
        cat_articles = [a for a in articles if a.get("category_key") == cat["key"]]
        if cat_articles:
            cards = "\n".join(_card_html(a, path_prefix="../") for a in cat_articles[:ARTICLES_PER_PAGE])
            body = f'<div class="grid">{cards}</div>'
        else:
            body = '<div class="empty-state">لا توجد أخبار في هذا التصنيف بعد.</div>'
        cat_html = PAGE_TEMPLATE.format(
            title=f"{cat.get('name_ar', cat['key'])} — {site_title}",
            description=f"أخبار {cat.get('name_ar', cat['key'])}",
            css_path="../assets/style.css",
            home_path="../index.html",
            site_title=_esc(site_title),
            nav_links=_nav_links(categories, relative_prefix="../"),
            body=body,
        )
        with open(os.path.join(output_dir, "category", f"{cat['key']}.html"), "w", encoding="utf-8") as f:
            f.write(cat_html)
