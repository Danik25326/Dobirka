#!/usr/bin/env python3
"""Публікує в Telegram-канал: (1) «події дня» (їх висвітлили щонайменше 2 видання), (2) свіжі важливі
новини з теми «Найважливіше», (3) раз на добу вранці дайджест «Головне за добу».
Секрети репозиторію: TELEGRAM_BOT_TOKEN, TELEGRAM_CHAT_ID. Без них скрипт нічого не робить.
Перший запуск лише запам’ятовує поточні новини. TELEGRAM_DRY_RUN=1 — тільки показати, TELEGRAM_FORCE_DIGEST=1 — дайджест зараз."""
import json, os, sys, time, html
from pathlib import Path
from datetime import datetime, timezone, timedelta
from urllib.parse import urlencode
from urllib.request import Request, urlopen
try:
    from zoneinfo import ZoneInfo
    KYIV = ZoneInfo("Europe/Kyiv")
except Exception:
    KYIV = timezone(timedelta(hours=2))

ROOT = Path(__file__).resolve().parent.parent
OUT = Path(sys.argv[1]) if len(sys.argv) > 1 else ROOT
TOKEN, CHAT, DRY = os.environ.get("TELEGRAM_BOT_TOKEN"), os.environ.get("TELEGRAM_CHAT_ID"), os.environ.get("TELEGRAM_DRY_RUN")
MAX_PER_RUN = 2          # скільки повідомлень максимум за один запуск
URGENT_TOPIC = "vazhlyve"  # id теми для окремих важливих новин
URGENT_MAX_AGE_H = 2     # старіші за 2 години важливі новини не публікуємо
DIGEST_HOUR, DIGEST_N, KEEP = 8, 10, 800   # дайджест о 8:00 за Києвом

esc = lambda s: html.escape(str(s), quote=True)

def urls_of(t):
    return {t["u"]} | {x["u"] for x in t.get("l", [])}

def msg_top(t, site):
    srcs = " · ".join('<a href="%s">%s</a>' % (esc(x["u"]), esc(x["s"])) for x in t["l"])
    return "🔥 <b>%s</b>\n\nПишуть: %s\n\n📰 Усі новини: %s" % (esc(t["t"]), srcs, esc(site))

def msg_item(i, site):
    return "⚡ <b>%s</b>\n\n<a href=\"%s\">%s</a>\n\n📰 Усі новини: %s" % (esc(i["t"]), esc(i["u"]), esc(i["s"]), esc(site))

def msg_digest(top, site):
    rows = ['%d. <a href="%s">%s</a> · %d вид.' % (n, esc(t["u"]), esc(t["t"]), t["n"]) for n, t in enumerate(top, 1)]
    return "☀️ <b>Головне за добу</b>\n\n" + "\n".join(rows) + "\n\n📰 Усі новини: " + esc(site)

def send(text):
    if DRY:
        print("--- DRY RUN ---\n" + text + "\n")
        return True
    req = Request("https://api.telegram.org/bot%s/sendMessage" % TOKEN,
                  data=urlencode({"chat_id": CHAT, "text": text, "parse_mode": "HTML"}).encode())
    with urlopen(req, timeout=25) as r:
        return json.loads(r.read().decode()).get("ok", False)

def fresh(i):
    try:
        return datetime.now(timezone.utc) - datetime.fromisoformat(i["d"]) < timedelta(hours=URGENT_MAX_AGE_H)
    except Exception:
        return False

def main():
    if not DRY and not (TOKEN and CHAT):
        print("Telegram не налаштовано, пропускаю")
        return
    news = json.loads((OUT / "data" / "news.json").read_text("utf-8"))
    site = json.loads((ROOT / "feeds.json").read_text("utf-8"))["site"]["url"]
    top = news.get("top", [])
    urgent = [i for i in news.get("items", []) if URGENT_TOPIC in i.get("c", []) and not i.get("v")]
    path = OUT / "data" / "posted.json"
    try:
        posted = json.loads(path.read_text("utf-8"))
    except Exception:
        posted = None
    if posted is None:
        posted = sorted({u for t in top for u in urls_of(t)} | {i["u"] for i in urgent})
        path.write_text(json.dumps(posted), "utf-8")
        print("Перший запуск: запам’ятав %d посилань, нічого не публікую" % len(posted))
        return
    seen, sent = set(posted), 0
    queue = [("top", t) for t in reversed(top)] + [("item", i) for i in reversed(urgent) if fresh(i)]
    for kind, x in queue:
        if sent >= MAX_PER_RUN:
            break
        urls = urls_of(x) if kind == "top" else {x["u"]}
        if urls & seen:
            seen |= urls
            continue
        try:
            ok = send(msg_top(x, site) if kind == "top" else msg_item(x, site))
        except Exception as e:
            print("ПОМИЛКА Telegram:", e, file=sys.stderr)
            break
        if ok:
            seen |= urls
            sent += 1
            time.sleep(1.5)
    out = (posted + [u for u in sorted(seen) if u not in posted])[-KEEP:]
    if out != posted:
        path.write_text(json.dumps(out), "utf-8")
    # ранковий дайджест
    now_k = datetime.now(timezone.utc).astimezone(KYIV)
    dpath, today = OUT / "data" / "digest.json", now_k.strftime("%Y-%m-%d")
    try:
        last = json.loads(dpath.read_text("utf-8")).get("date")
    except Exception:
        last = None
    if (os.environ.get("TELEGRAM_FORCE_DIGEST") or now_k.hour == DIGEST_HOUR) and last != today and len(top) >= 3:
        try:
            if send(msg_digest(top[:DIGEST_N], site)):
                dpath.write_text(json.dumps({"date": today}), "utf-8")
                print("Дайджест опубліковано")
        except Exception as e:
            print("ПОМИЛКА дайджесту:", e, file=sys.stderr)
    print("Опубліковано в Telegram: %d" % sent)

main()
