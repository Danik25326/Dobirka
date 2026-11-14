#!/usr/bin/env python3
"""Збирає RSS зі списку feeds.json у data/news.json і генерує НАШІ RSS у feeds/*.xml.
Додатково: картинки, визначення регіонів, «Топ дня» (групування схожих заголовків).
Використання: python scripts/fetch.py [feeds.json] [папка-виводу]. Лише стандартна бібліотека."""
import json, sys, re, html
from pathlib import Path
from datetime import datetime, timezone
from email.utils import parsedate_to_datetime, format_datetime
from urllib.request import Request, urlopen
from xml.etree import ElementTree as ET
from xml.sax.saxutils import escape

ROOT = Path(__file__).resolve().parent.parent
CFG = Path(sys.argv[1]) if len(sys.argv) > 1 else ROOT / "feeds.json"
OUT = Path(sys.argv[2]) if len(sys.argv) > 2 else ROOT
MAX_PER_FEED, MAX_ITEMS, MAX_RSS, SNIP, TOP_N, TOP_HOURS = 40, 500, 60, 220, 6, 36
UA = "Mozilla/5.0 (compatible; DobirkaNazhyvo/1.0; news-aggregator)"
IMG_EXT = re.compile(r"\.(jpe?g|png|webp|gif|avif)(\?|$)", re.I)

# id, назва, регулярний вираз (шукається спочатку в заголовку, потім в описі)
REGIONS = [
 ("kyiv", "м. Київ", r"\bкиї(?!встар|вщин|вськ)|\bкиє(?!вськ)"),
 ("kyivska", "Київська обл.", r"київщин|київськ\w*\s+обл|бучанськ|ірпін|бориспіл|біл\w+\s+церкв"),
 ("vinnytsia", "Вінницька обл.", r"\bвінниц|\bвінничч"),
 ("volyn", "Волинська обл.", r"\bволин|\bлуцьк"),
 ("dnipro", "Дніпропетровська обл.", r"дніпропетр|\bдніпр[оіау]\b|кривий ріг|кривого рог|нікопол|павлоград"),
 ("donetsk", "Донецька обл.", r"\bдонеч|\bдонецьк|краматорськ|слов.янськ|покровськ|бахмут|маріупол|костянтинівк"),
 ("zhytomyr", "Житомирська обл.", r"\bжитомир"),
 ("zakarpattia", "Закарпатська обл.", r"\bзакарпат|\bужгород|\bмукачев"),
 ("zaporizhzhia", "Запорізька обл.", r"\bзапоріж|\bзапорізьк|мелітопол|енергодар|бердянськ"),
 ("ivanofrankivsk", "Івано-Франківська обл.", r"франківськ|івано-франків|прикарпат"),
 ("kirovohrad", "Кіровоградська обл.", r"кропивницьк|кіровоград"),
 ("luhansk", "Луганська обл.", r"\bлуган|сєвєродонецьк|лисичанськ"),
 ("lviv", "Львівська обл.", r"\bльв[іо]в|\bльвівщин"),
 ("mykolaiv", "Миколаївська обл.", r"\bмиколаї|\bмиколає"),
 ("odesa", "Одеська обл.", r"\bодес|\bодещин|\bізмаїл"),
 ("poltava", "Полтавська обл.", r"\bполтав|\bкременчу"),
 ("rivne", "Рівненська обл.", r"\bрівненськ|\bрівненщин|\bу рівному\b|\bз рівного\b"),
 ("sumy", "Сумська обл.", r"\bсум(?:и|ах|ам|ськ\w*|щин\w*)\b"),
 ("ternopil", "Тернопільська обл.", r"\bтерноп"),
 ("kharkiv", "Харківська обл.", r"\bхарк|\bхарьк|куп.янськ|\bізюм"),
 ("kherson", "Херсонська обл.", r"\bхерсон"),
 ("khmelnytskyi", "Хмельницька обл.", r"хмельницьк|хмельниччин|кам.янець-подільськ"),
 ("cherkasy", "Черкаська обл.", r"\bчеркас|\bуман"),
 ("chernivtsi", "Чернівецька обл.", r"\bчернівц|\bбуковин"),
 ("chernihiv", "Чернігівська обл.", r"\bчернігов|\bчернігів|\bніжин"),
 ("crimea", "АР Крим", r"\bкрим(?!ін)\w*|севастопол|сімферопол"),
]
REG_C = [(i, n, re.compile(p, re.I)) for i, n, p in REGIONS]
STOP = set("який яка яке які того цього через після перед щодо також його вона вони буде були коли може тому проти для при про від між над".split())

def clean(s):
    s = html.unescape(re.sub(r"<[^>]+>", " ", s or ""))
    return re.sub(r"\s+", " ", s).strip()

def snip(s, n=SNIP):
    return s if len(s) <= n else s[:n].rsplit(" ", 1)[0].rstrip(",.;:- ") + "…"

def parse_date(s):
    if not s:
        return None
    s = s.strip()
    try:
        d = parsedate_to_datetime(s)
    except Exception:
        try:
            d = datetime.fromisoformat(s.replace("Z", "+00:00"))
        except Exception:
            return None
    if d.tzinfo is None:
        d = d.replace(tzinfo=timezone.utc)
    return d.astimezone(timezone.utc)

def local(tag):
    return tag.rsplit("}", 1)[-1]

def text(el, *names):
    for c in el:
        if local(c.tag) in names and (c.text or "").strip():
            return c.text
    return ""

def find_image(el):
    url = ""
    for c in el:
        n, u = local(c.tag), c.get("url") or ""
        if n in ("enclosure", "thumbnail", "content") and u:
            typ = (c.get("type") or c.get("medium") or "").lower()
            if typ.startswith("image") or n == "thumbnail" or (not typ and IMG_EXT.search(u)):
                url = u
                break
    if not url:
        for c in el:
            if local(c.tag) in ("description", "summary", "encoded", "content") and c.text:
                m = re.search(r"<img[^>]+src=[\"']([^\"']+)", html.unescape(c.text))
                if m:
                    url = m.group(1)
                    break
    if url.startswith("//"):
        url = "https:" + url
    if url.startswith("http://"):
        url = "https://" + url[7:]
    return url if url.startswith("https://") else ""

def parse(data):
    out = []
    for el in ET.fromstring(data).iter():
        if local(el.tag) not in ("item", "entry"):
            continue
        link = text(el, "link").strip()
        if not link:
            for c in el:
                if local(c.tag) == "link" and c.get("href") and c.get("rel", "alternate") == "alternate":
                    link = c.get("href")
                    break
        out.append({
            "t": clean(text(el, "title")), "u": link,
            "d": parse_date(text(el, "pubDate", "published", "updated", "date")),
            "x": snip(clean(text(el, "description", "summary"))), "i": find_image(el),
        })
    return out

def fetch(url):
    with urlopen(Request(url, headers={"User-Agent": UA}), timeout=25) as r:
        return r.read()

def regions_of(title, body):
    found = []
    for src in (title, body):
        hits = sorted((m.start(), rid) for rid, _, p in REG_C for m in [p.search(src)] if m)
        for _, rid in hits:
            if rid not in found:
                found.append(rid)
        if found:
            break
    return found[:2]

STOP_STEMS = {"укра", "росі", "заяв", "пове", "нови", "року", "роки", "рока", "щодо", "піс"}

def stems(t):
    st = {w[:4] for w in re.findall(r"[\w'’-]{4,}", t.lower()) if w not in STOP}
    return st - STOP_STEMS

def make_top(ranked, now):
    rec = [i for i in ranked if (now - i["_d"]).total_seconds() < TOP_HOURS * 3600]
    S = [stems(i["t"]) for i in rec]
    par = list(range(len(rec)))
    def find(x):
        while par[x] != x:
            par[x] = par[par[x]]
            x = par[x]
        return x
    for a in range(len(rec)):
        for b in range(a + 1, len(rec)):
            if rec[a]["s"] == rec[b]["s"]:
                continue
            inter = len(S[a] & S[b])
            if inter >= 3 and inter / len(S[a] | S[b]) >= 0.4:
                par[find(a)] = find(b)
    groups = {}
    for idx in range(len(rec)):
        groups.setdefault(find(idx), []).append(rec[idx])
    top = []
    for g in groups.values():
        srcs = list(dict.fromkeys(i["s"] for i in g))
        if len(srcs) < 2:
            continue
        g.sort(key=lambda i: i["_d"], reverse=True)
        links = [next({"s": s, "u": i["u"]} for i in g if i["s"] == s) for s in srcs]
        top.append({"t": g[0]["t"], "u": g[0]["u"], "i": next((i["i"] for i in g if i["i"]), ""),
                    "n": len(srcs), "l": links, "d": g[0]["_d"]})
    top.sort(key=lambda x: (x["n"], x["d"]), reverse=True)
    return top[:TOP_N]

def build_rss(cfg, title, items, link):
    now = items[0]["_d"] if items else datetime.now(timezone.utc)
    rows = []
    for i in items:
        enc = '<enclosure url="%s" type="image/jpeg" length="0"/>' % escape(i["i"]) if i.get("i") else ""
        rows.append(
            "<item><title>%s</title><link>%s</link><guid isPermaLink=\"true\">%s</guid>"
            "<pubDate>%s</pubDate><category>%s</category><description>%s</description>%s</item>"
            % (escape(i["t"]), escape(i["u"]), escape(i["u"]), format_datetime(i["_d"]),
               escape(i["s"]), escape(i["x"] or i["t"]), enc))
    return ("<?xml version=\"1.0\" encoding=\"UTF-8\"?>\n<rss version=\"2.0\"><channel>"
            "<title>%s</title><link>%s</link><description>%s</description><language>uk</language>"
            "<lastBuildDate>%s</lastBuildDate>%s</channel></rss>\n"
            % (escape(title), escape(link), escape(cfg["site"]["description"]), format_datetime(now), "".join(rows)))

def main():
    cfg = json.loads(CFG.read_text("utf-8"))
    now = datetime.now(timezone.utc)
    items, seen_title, ok = {}, {}, 0
    for topic in cfg["topics"]:
        for f in topic["feeds"]:
            try:
                entries = parse(fetch(f["url"]))[:MAX_PER_FEED]
                ok += 1
                print("OK %s (%d): %s" % (topic["id"], len(entries), f["url"]))
            except Exception as e:
                print("ПОМИЛКА %s: %s" % (f["url"], e), file=sys.stderr)
                continue
            for e in entries:
                if not e["t"] or not e["u"].startswith(("http://", "https://")):
                    continue
                key = e["u"].split("#")[0]
                tkey = re.sub(r"\W+", "", e["t"].lower())
                key = seen_title.get(tkey, key)
                if key in items:
                    it = items[key]
                    if topic["id"] not in it["c"]:
                        it["c"].append(topic["id"])
                    if not it["i"] and e["i"]:
                        it["i"] = e["i"]
                    continue
                seen_title[tkey] = key
                d = min(e["d"] or now, now)
                items[key] = {"t": e["t"], "s": f["source"], "u": key, "x": e["x"], "i": e["i"],
                              "d": d.isoformat(timespec="seconds"), "c": [topic["id"]], "_d": d}
    if not ok:
        sys.exit("Жодна стрічка не відповіла")
    ranked = sorted(items.values(), key=lambda i: i["_d"], reverse=True)[:MAX_ITEMS]
    for i in ranked:
        i["r"] = regions_of(i["t"], i["x"])
    pub = []
    for i in ranked:
        row = {k: v for k, v in i.items() if k != "_d"}
        for k in ("i", "r", "x"):
            if not row.get(k):
                row.pop(k, None)
        pub.append(row)
    top = make_top(ranked, now)
    top_pub = [{**{k: v for k, v in t.items() if k != "d"}, "d": t["d"].isoformat(timespec="seconds")} for t in top]
    for t in top_pub:
        if not t["i"]:
            t.pop("i")

    (OUT / "data").mkdir(parents=True, exist_ok=True)
    (OUT / "feeds").mkdir(parents=True, exist_ok=True)
    news_path = OUT / "data" / "news.json"
    topics_out = [{"id": t["id"], "name": t["name"]} for t in cfg["topics"]]
    regions_out = [{"id": i, "name": n} for i, n, _ in REGIONS]
    try:
        oj = json.loads(news_path.read_text("utf-8"))
        old = (oj.get("items"), oj.get("top"), oj.get("regions"), oj.get("topics"))
    except Exception:
        old = None
    if old == (pub, top_pub, regions_out, topics_out):
        print("Змін немає")
        return
    news_path.write_text(json.dumps({
        "updated": now.isoformat(timespec="seconds"),
        "topics": topics_out, "regions": regions_out,
        "top": top_pub, "items": pub}, ensure_ascii=False, indent=1), "utf-8")
    base = cfg["site"]["url"]
    (OUT / "feeds" / "all.xml").write_text(build_rss(cfg, cfg["site"]["title"], ranked[:MAX_RSS], base), "utf-8")
    for t in cfg["topics"]:
        sel = [i for i in ranked if t["id"] in i["c"]][:MAX_RSS]
        (OUT / "feeds" / (t["id"] + ".xml")).write_text(
            build_rss(cfg, "%s — %s" % (cfg["site"]["title"], t["name"]), sel, base), "utf-8")
    print("Оновлено: %d новин із %d стрічок, у топі %d" % (len(pub), ok, len(top_pub)))

main()
