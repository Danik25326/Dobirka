#!/usr/bin/env python3
"""Активні повітряні тривоги по областях -> data/alerts.json.
Джерело: API alerts.in.ua (потрібен особистий токен: devs.alerts.in.ua). Токен тримаємо лише в секреті
репозиторію ALERTS_IN_UA_TOKEN, у код сайту він не потрапляє. Без токена скрипт нічого не робить.
Адресу API за потреби змініть змінною ALERTS_URL (перевірте за документацією сервісу)."""
import json, os, sys
from pathlib import Path
from datetime import datetime, timezone
from urllib.request import Request, urlopen

ROOT = Path(__file__).resolve().parent.parent
OUT = Path(sys.argv[1]) if len(sys.argv) > 1 else ROOT
TOKEN = os.environ.get("ALERTS_IN_UA_TOKEN")
URL = os.environ.get("ALERTS_URL", "https://api.alerts.in.ua/v1/alerts/active.json")
sys.path.insert(0, str(Path(__file__).resolve().parent))
import fetch as F  # беремо звідти список областей

def keys_for(rid, name):
    if rid == "kyiv":
        return ["м. київ", "київ"]
    if rid == "crimea":
        return ["автономна республіка крим", "ар крим", "крим"]
    return [name.lower().replace("обл.", "область")]

IDX = {k: (rid, name) for rid, name, _ in F.REGIONS for k in keys_for(rid, name)}

def main():
    if not TOKEN:
        print("Тривоги: токен не налаштовано, пропускаю")
        return
    req = Request(URL, headers={"Authorization": "Bearer " + TOKEN, "User-Agent": "DobirkaNazhyvo/1.0"})
    try:
        with urlopen(req, timeout=25) as r:
            data = json.loads(r.read().decode("utf-8"))
    except Exception as e:
        print("ПОМИЛКА API тривог:", e, file=sys.stderr)
        return
    agg = {}
    for a in data.get("alerts", []):
        if a.get("alert_type") not in (None, "air_raid") or a.get("finished_at"):
            continue
        hit = IDX.get((a.get("location_oblast") or a.get("location_title") or "").strip().lower())
        if not hit:
            continue
        rid, name = hit
        row = agg.setdefault(rid, {"id": rid, "name": name, "whole": False, "n": 0, "since": a.get("started_at") or ""})
        row["n"] += 1
        row["whole"] = row["whole"] or a.get("location_type") == "oblast"
        if a.get("started_at") and (not row["since"] or a["started_at"] < row["since"]):
            row["since"] = a["started_at"]
    rows = sorted(agg.values(), key=lambda x: x["name"])
    path = OUT / "data" / "alerts.json"
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps({"updated": datetime.now(timezone.utc).isoformat(timespec="seconds"), "regions": rows},
                               ensure_ascii=False), "utf-8")
    print("Тривоги: активні в %d областях" % len(rows))

main()
