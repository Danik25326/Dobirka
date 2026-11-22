#!/usr/bin/env python3
"""Генерує статичні сторінки тем і областей (щоб їх бачив Google), sitemap.xml
та блок «Розділи» у футері index.html. Використання: python scripts/build_pages.py [feeds.json] [папка]"""
import json, os, re, shutil, sys, html as H
from pathlib import Path
from datetime import datetime, timezone, timedelta

ROOT = Path(__file__).resolve().parent.parent
CFG = Path(sys.argv[1]) if len(sys.argv) > 1 else ROOT / "feeds.json"
OUT = Path(sys.argv[2]) if len(sys.argv) > 2 else ROOT
LIMIT, MIN_REGION = 40, int(os.environ.get("MIN_REGION_ITEMS", "3"))
REGION_MAX, REGION_DAYS, REGION_PAGE = 200, 14, 60
sys.path.insert(0, str(Path(__file__).resolve().parent))
try:
    import fetch as F  # беремо звідти визначення областей за заголовком
except Exception:
    F = None
try:
    from zoneinfo import ZoneInfo
    KYIV = ZoneInfo("Europe/Kyiv")
except Exception:
    KYIV = timezone(timedelta(hours=2))

esc = lambda s: H.escape(str(s), quote=True)
ARCH_MAX = 1500
MONTHS = ["січня", "лютого", "березня", "квітня", "травня", "червня", "липня", "серпня", "вересня", "жовтня", "листопада", "грудня"]

def day_label(ds):
    y, m, d = map(int, ds.split("-"))
    return "%d %s %d року" % (d, MONTHS[m - 1], y)

def update_archive(items):
    """Дописує нові заголовки в data/archive/РРРР-ММ-ДД.json (за київським часом). Повертає список днів."""
    adir = OUT / "data" / "archive"
    adir.mkdir(parents=True, exist_ok=True)
    by = {}
    for i in items:
        if i.get("v"):
            continue
        day = datetime.fromisoformat(i["d"]).astimezone(KYIV).strftime("%Y-%m-%d")
        by.setdefault(day, []).append({"t": i["t"], "s": i["s"], "u": i["u"], "d": i["d"], "c": i["c"], "r": i.get("r", [])})
    for day, new in by.items():
        p = adir / (day + ".json")
        try:
            old = json.loads(p.read_text("utf-8"))
        except Exception:
            old = []
        m = {x["u"]: x for x in old}
        for x in new:
            m[x["u"]] = {**m.get(x["u"], {}), **x}
        merged = sorted(m.values(), key=lambda x: x["d"], reverse=True)[:ARCH_MAX]
        if merged != old:
            p.write_text(json.dumps(merged, ensure_ascii=False, separators=(",", ":")), "utf-8")
    return sorted(p.stem for p in adir.glob("*.json"))

def region_lists(news, days):
    """Історія по областях: архів за REGION_DAYS днів + свіжі (багаті) новини з news.json."""
    adir = OUT / "data" / "archive"
    out = {r["id"]: {} for r in news["regions"]}
    for day in sorted(days, reverse=True)[:REGION_DAYS]:
        p = adir / (day + ".json")
        rows = json.loads(p.read_text("utf-8"))
        dirty = False
        for x in rows:
            if "r" not in x:  # старі записи без області: визначаємо за заголовком
                x["r"] = F.regions_of(x["t"], "") if F else []
                dirty = True
            for rid in x["r"]:
                if rid in out:
                    out[rid].setdefault(x["u"], x)
        if dirty:
            p.write_text(json.dumps(rows, ensure_ascii=False, separators=(",", ":")), "utf-8")
    for i in news["items"]:
        if i.get("v"):
            continue
        for rid in i.get("r", []):
            if rid in out:
                out[rid][i["u"]] = i
    return {rid: sorted(m.values(), key=lambda x: x["d"], reverse=True)[:REGION_MAX] for rid, m in out.items()}

def write_region_files(rl):
    d = OUT / "data" / "region"
    d.mkdir(parents=True, exist_ok=True)
    for rid, rows in rl.items():
        out = []
        for x in rows:
            y = {k: x[k] for k in ("t", "s", "u", "d", "x", "i") if x.get(k)}
            y["c"], y["r"] = x.get("c", []), x.get("r", [])
            out.append(y)
        txt = json.dumps(out, ensure_ascii=False, separators=(",", ":"))
        p = d / (rid + ".json")
        if not p.exists() or p.read_text("utf-8") != txt:
            p.write_text(txt, "utf-8")

def archive_pages(days, base, tlinks, rlinks):
    shutil.rmtree(OUT / "arhiv", ignore_errors=True)
    (OUT / "arhiv").mkdir(parents=True, exist_ok=True)
    counts = {}
    for n, day in enumerate(days):
        rows = json.loads((OUT / "data" / "archive" / (day + ".json")).read_text("utf-8"))
        counts[day] = len(rows)
        lis = "".join('<li><time datetime="%s">%s</time><a href="%s" target="_blank" rel="noopener noreferrer">%s</a><span>%s</span></li>' % (
            esc(r["d"]), datetime.fromisoformat(r["d"]).astimezone(KYIV).strftime("%H:%M"), esc(r["u"]), esc(r["t"]), esc(r["s"])) for r in rows)
        nav = ['<a href="/arhiv/">Усі дні</a>']
        if n > 0:
            nav.insert(0, '<a href="/arhiv/%s/">← %s</a>' % (days[n - 1], esc(day_label(days[n - 1]))))
        if n < len(days) - 1:
            nav.append('<a href="/arhiv/%s/">%s →</a>' % (days[n + 1], esc(day_label(days[n + 1]))))
        raw = '<p class="lede">%s</p><ul class="arch">%s</ul>' % (" · ".join(nav), lis)
        url = "/arhiv/%s/" % day
        (OUT / "arhiv" / day).mkdir(parents=True, exist_ok=True)
        (OUT / "arhiv" / day / "index.html").write_text(page(
            base, base + url[1:], "Новини за %s: архів — Добірка Наживо" % day_label(day),
            "Архів заголовків новин України за %s: %d матеріалів з посиланнями на першоджерела." % (day_label(day), len(rows)),
            "Новини за %s" % day_label(day), "", [], tlinks, rlinks, "", "/feeds/all.xml", raw=raw), "utf-8")
    lis = "".join('<li><a href="/arhiv/%s/">%s</a><span>%d матеріалів</span></li>' % (d, esc(day_label(d)), counts[d]) for d in reversed(days))
    (OUT / "arhiv" / "index.html").write_text(page(
        base, base + "arhiv/", "Архів новин за днями — Добірка Наживо",
        "Архів заголовків новин України за днями з посиланнями на першоджерела.",
        "Архів новин", "Заголовки з відкритих українських джерел, зібрані за кожен день.", [], tlinks, rlinks, "", "/feeds/all.xml",
        raw='<ul class="arch">%s</ul>' % lis), "utf-8")
DESC_DEFAULT = "Добірка новин з усієї України: заголовки, короткі описи й посилання на першоджерела."

def head(base, title, desc, canon):
    return f'''<!DOCTYPE html>
<html lang="uk">
<head>
<meta charset="utf-8">
<meta name="viewport" content="width=device-width, initial-scale=1, viewport-fit=cover">
<title>{esc(title)}</title>
<meta name="description" content="{esc(desc)}">
<link rel="canonical" href="{esc(canon)}">
<link rel="icon" href="/favicon.ico" sizes="48x48"><link rel="icon" type="image/svg+xml" href="/favicon.svg">
<link rel="icon" type="image/png" sizes="32x32" href="/favicon-32x32.png"><link rel="apple-touch-icon" sizes="180x180" href="/apple-touch-icon.png">
<link rel="manifest" href="/site.webmanifest"><meta name="theme-color" content="#13202C">
<meta property="og:type" content="website"><meta property="og:site_name" content="Добірка Наживо"><meta property="og:locale" content="uk_UA">
<meta property="og:title" content="{esc(title)}"><meta property="og:description" content="{esc(desc)}"><meta property="og:url" content="{esc(canon)}">
<meta property="og:image" content="{esc(base)}og-image.png"><meta name="twitter:card" content="summary_large_image">
<script type="application/ld+json">{json.dumps({"@context": "https://schema.org", "@type": "CollectionPage", "name": title, "description": desc, "url": canon, "inLanguage": "uk", "isPartOf": {"@type": "WebSite", "name": "Добірка Наживо", "url": base}}, ensure_ascii=False)}</script>
<link rel="preconnect" href="https://fonts.googleapis.com">
<link href="https://fonts.googleapis.com/css2?family=Onest:wght@400;500;700&family=Unbounded:wght@600;800&display=swap" rel="stylesheet">
<link rel="stylesheet" href="/style.css">
<script src="/analytics.js" defer></script>
</head>'''

def chips(links, cur, small=False):
    if not links:
        return ""
    cls = "chips small" if small else "chips"
    rows = "".join('<a class="chip" href="%s"%s>%s</a>' % (u, ' aria-current="page"' if u == cur else "", esc(n)) for u, n in links)
    return '<nav class="%s" aria-label="%s">%s</nav>' % (cls, "Області" if small else "Розділи", rows)

def card(i):
    d = datetime.fromisoformat(i["d"]).astimezone(KYIV)
    img = '<div class="thumb"><img src="%s" alt="" loading="lazy" decoding="async" referrerpolicy="no-referrer"></div>' % esc(i["i"]) if i.get("i") else ""
    return ('<a class="card%s" href="%s" target="_blank" rel="noopener noreferrer">%s<div class="meta"><b>%s</b> · <time datetime="%s">%s</time></div>'
            '<h3>%s</h3>%s<div class="meta">Читати на сайті %s →</div></a>') % (
        " hasimg" if i.get("i") else "", esc(i["u"]), img, esc(i["s"]), esc(i["d"]), d.strftime("%d.%m.%Y, %H:%M"),
        esc(i["t"]), "<p>%s</p>" % esc(i["x"]) if i.get("x") else "", esc(i["s"]))

def page(base, canon, title, desc, h1, lede, items, tlinks, rlinks, cur, rss, raw=None):
    body = f'''
<body>
<header><div class="wrap"><div class="top">
  <a class="logo" href="/" aria-label="Добірка Наживо, на головну"><span class="mark" aria-hidden="true">Д<i></i></span><span class="name">Добірка Наживо<small>Новини з усієї України в одному місці</small></span></a>
  <span class="acts"><a class="ibtn live" href="/live.html" aria-label="Прямі ефіри" title="Прямі ефіри"><svg viewBox="0 0 24 24" aria-hidden="true"><circle cx="12" cy="12" r="9" fill="none" stroke="currentColor" stroke-width="2"/><path d="M10 8.5v7l6-3.5z" fill="currentColor"/></svg></a><a class="ibtn" href="{rss}" aria-label="RSS-стрічка" title="RSS"><svg viewBox="0 0 24 24" aria-hidden="true"><path d="M5 11a8 8 0 0 1 8 8M5 5a14 14 0 0 1 14 14" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round"/><circle cx="6" cy="18" r="1.8" fill="currentColor"/></svg></a></span>
</div>{chips([("/", "Усі")] + tlinks, cur)}{chips(rlinks, cur, True)}</div></header>
<div class="wrap"><main class="single">
<h1>{esc(h1)}</h1>
<p class="lede">{esc(lede)}</p>
{raw if raw is not None else "".join(card(i) for i in items)}
</main></div>
<footer><div class="wrap"><div class="row"><a href="/">Головна</a><a href="/live.html">Прямі ефіри</a><a href="/info.html#about">Про нас</a><a href="/info.html#sources">Джерела</a><a href="/info.html#privacy">Політика конфіденційності</a></div>
<div>© Добірка Наживо. Показуємо заголовок, короткий опис і посилання на першоджерело. Усі права на матеріали належать їхнім авторам.</div></div></footer>
<script>document.addEventListener("error",function(e){{var t=e.target;if(t&&t.tagName==="IMG"){{var h=t.closest(".thumb");if(h){{var c=h.closest(".card");if(c)c.classList.remove("hasimg");h.remove()}}}}}},true);</script>
</body>
</html>
'''
    return head(base, title, desc, canon) + body

def main():
    cfg = json.loads(CFG.read_text("utf-8"))
    base = cfg["site"]["url"].rstrip("/") + "/"
    news = json.loads((OUT / "data" / "news.json").read_text("utf-8"))
    items = news["items"]
    tdirs, rdirs = [], []
    topics = []
    for t in news["topics"]:
        sel = [i for i in items if t["id"] in i["c"]][:LIMIT]
        if sel:
            topics.append((t, sel))
    days = update_archive(items)
    rl = region_lists(news, days)
    write_region_files(rl)
    regions = []
    for r in news["regions"]:
        sel = rl.get(r["id"], [])[:REGION_PAGE]
        if len(sel) >= MIN_REGION:
            regions.append((r, sel))
    tlinks = [("/tema/%s/" % t["id"], t["name"]) for t, _ in topics]
    rlinks = [("/oblast/%s/" % r["id"], r["name"]) for r, _ in regions]
    for d in ("tema", "oblast"):
        shutil.rmtree(OUT / d, ignore_errors=True)
        (OUT / d).mkdir(parents=True, exist_ok=True)
    for t, sel in topics:
        url = "/tema/%s/" % t["id"]
        (OUT / "tema" / t["id"]).mkdir(parents=True, exist_ok=True)
        (OUT / "tema" / t["id"] / "index.html").write_text(page(
            base, base + url[1:], "%s: свіжі новини України — Добірка Наживо" % t["name"],
            "Свіжі новини за темою «%s»: заголовки, короткі описи й посилання на першоджерела з відкритих українських джерел." % t["name"],
            "Новини: %s" % t["name"],
            "Остання добірка за темою «%s» із відкритих українських джерел. Сторінка оновлюється автоматично." % t["name"],
            sel, tlinks, rlinks, url, "/feeds/%s.xml" % t["id"]), "utf-8")
    for r, sel in regions:
        url = "/oblast/%s/" % r["id"]
        (OUT / "oblast" / r["id"]).mkdir(parents=True, exist_ok=True)
        (OUT / "oblast" / r["id"] / "index.html").write_text(page(
            base, base + url[1:], "%s: останні новини — Добірка Наживо" % r["name"],
            "Останні новини: %s. Добірка згадок області та її міст у стрічках українських ЗМІ з посиланнями на першоджерела." % r["name"],
            "Новини: %s" % r["name"],
            "Добірка матеріалів, де згадується регіон «%s» або його міста. Визначення автоматичне, тому можливі неточності." % r["name"],
            sel, tlinks, rlinks, url, "/feeds/all.xml"), "utf-8")

    archive_pages(days, base, tlinks, rlinks)
    today = datetime.now(timezone.utc).strftime("%Y-%m-%d")
    urls = ["", "live.html", "info.html", "arhiv/"] + [u[1:] for u, _ in tlinks + rlinks] + ["arhiv/%s/" % d for d in days]
    (OUT / "sitemap.xml").write_text('<?xml version="1.0" encoding="UTF-8"?>\n<urlset xmlns="http://www.sitemaps.org/schemas/sitemap/0.9">\n' +
        "".join("  <url><loc>%s</loc><lastmod>%s</lastmod></url>\n" % (esc(base + u), today) for u in urls) + "</urlset>\n", "utf-8")

    block = '<div class="row"><b>Теми:</b> %s</div>' % " ".join('<a href="%s">%s</a>' % (u[1:], esc(n)) for u, n in tlinks)
    if rlinks:
        block += '\n  <div class="row"><b>Області:</b> %s</div>' % " ".join('<a href="%s">%s</a>' % (u[1:], esc(n)) for u, n in rlinks)
    tg = cfg["site"].get("telegram", "")
    block += '\n  <div class="row"><a href="live.html">Прямі ефіри</a> <a href="arhiv/">Архів новин</a>%s</div>' % (' <a href="%s" target="_blank" rel="noopener noreferrer">Telegram</a>' % esc(tg) if tg else "")
    idx = OUT / "index.html"
    if idx.exists():
        s = idx.read_text("utf-8")
        new = re.sub(r"<!--SECTIONS-->.*?<!--/SECTIONS-->", lambda m: "<!--SECTIONS-->\n  " + block + "\n  <!--/SECTIONS-->", s, flags=re.S)
        if new != s:
            idx.write_text(new, "utf-8")
    print("Сторінок: %d тем, %d областей, %d днів архіву" % (len(topics), len(regions), len(days)))

main()
