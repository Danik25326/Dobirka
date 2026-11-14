#!/usr/bin/env python3
"""Публікує нові «події дня» (їх висвітлили щонайменше 2 видання) у Telegram-канал.
Потрібні секрети репозиторію TELEGRAM_BOT_TOKEN і TELEGRAM_CHAT_ID. Без них скрипт нічого не робить.
Перший запуск лише запам’ятовує поточні новини, щоб не засмітити канал. TELEGRAM_DRY_RUN=1 — тільки показати."""
import json, os, sys, time, html
from pathlib import Path
from urllib.parse import urlencode
from urllib.request import Request, urlopen

ROOT = Path(__file__).resolve().parent.parent
TOKEN, CHAT, DRY = os.environ.get("TELEGRAM_BOT_TOKEN"), os.environ.get("TELEGRAM_CHAT_ID"), os.environ.get("TELEGRAM_DRY_RUN")
MAX_PER_RUN, KEEP = 3, 600
OUT = Path(sys.argv[1]) if len(sys.argv) > 1 else ROOT

def urls_of(t):
    return {t["u"]} | {x["u"] for x in t.get("l", [])}

def message(t, site):
    srcs = " · ".join('<a href="%s">%s</a>' % (html.escape(x["u"], quote=True), html.escape(x["s"])) for x in t["l"])
    return "🔥 <b>%s</b>\n\nПишуть: %s\n\n📰 Усі новини: %s" % (html.escape(t["t"]), srcs, html.escape(site))

def send(text):
    if DRY:
        print("--- DRY RUN ---\n" + text + "\n")
        return True
    req = Request("https://api.telegram.org/bot%s/sendMessage" % TOKEN,
                  data=urlencode({"chat_id": CHAT, "text": text, "parse_mode": "HTML"}).encode())
    with urlopen(req, timeout=25) as r:
        return json.loads(r.read().decode()).get("ok", False)

def main():
    if not DRY and not (TOKEN and CHAT):
        print("Telegram не налаштовано, пропускаю")
        return
    news = json.loads((OUT / "data" / "news.json").read_text("utf-8"))
    site = json.loads((ROOT / "feeds.json").read_text("utf-8"))["site"]["url"]
    path = OUT / "data" / "posted.json"
    top = news.get("top", [])
    try:
        posted = json.loads(path.read_text("utf-8"))
    except Exception:
        posted = None
    if posted is None:
        posted = sorted({u for t in top for u in urls_of(t)})
        path.write_text(json.dumps(posted), "utf-8")
        print("Перший запуск: запам’ятав %d посилань, нічого не публікую" % len(posted))
        return
    seen, sent = set(posted), 0
    for t in reversed(top):
        if sent >= MAX_PER_RUN:
            break
        if urls_of(t) & seen:
            seen |= urls_of(t)
            continue
        try:
            ok = send(message(t, site))
        except Exception as e:
            print("ПОМИЛКА Telegram:", e, file=sys.stderr)
            break
        if ok:
            seen |= urls_of(t)
            sent += 1
            time.sleep(1.5)
    out = (posted + [u for u in sorted(seen) if u not in posted])[-KEEP:]
    if out != posted:
        path.write_text(json.dumps(out), "utf-8")
    print("Опубліковано в Telegram: %d" % sent)

main()
