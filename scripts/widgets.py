#!/usr/bin/env python3
"""Курс НБУ і погода по областях -> data/widgets.json.
Запити йдуть з GitHub Actions, а не з браузера відвідувача: сайт нічого не передає третім сторонам.
Використання: python scripts/widgets.py [папка-виводу]"""
import json, os, sys
from pathlib import Path
from datetime import datetime, timezone, timedelta
from urllib.request import Request, urlopen

ROOT = Path(__file__).resolve().parent.parent
OUT = Path(sys.argv[1]) if len(sys.argv) > 1 else ROOT
NBU = os.environ.get("NBU_URL", "https://bank.gov.ua/NBUStatService/v1/statdirectory/exchange?json")
METEO = os.environ.get("METEO_URL", "https://api.open-meteo.com/v1/forecast")
CODES = ["USD", "EUR", "PLN", "GBP"]
WEATHER_EVERY_MIN = 55
UA = {"User-Agent": "Mozilla/5.0 (compatible; DobirkaNazhyvo/1.0)"}
# id області (як у fetch.py) -> координати обласного центру
CITIES = {
 "kyiv": (50.45, 30.52), "kyivska": (49.80, 30.12), "vinnytsia": (49.23, 28.47), "volyn": (50.75, 25.34),
 "dnipro": (48.46, 35.05), "donetsk": (48.87, 37.62), "zhytomyr": (50.25, 28.66), "zakarpattia": (48.62, 22.29),
 "zaporizhzhia": (47.84, 35.14), "ivanofrankivsk": (48.92, 24.71), "kirovohrad": (48.51, 32.26),
 "luhansk": (48.95, 38.49), "lviv": (49.84, 24.03), "mykolaiv": (46.97, 32.00), "odesa": (46.48, 30.73),
 "poltava": (49.59, 34.55), "rivne": (50.62, 26.25), "sumy": (50.91, 34.80), "ternopil": (49.55, 25.59),
 "kharkiv": (49.99, 36.23), "kherson": (46.64, 32.62), "khmelnytskyi": (49.42, 26.99), "cherkasy": (49.44, 32.06),
 "chernivtsi": (48.29, 25.94), "chernihiv": (51.50, 31.29), "crimea": (44.95, 34.10),
}

def get(url):
    with urlopen(Request(url, headers=UA), timeout=25) as r:
        return json.loads(r.read().decode("utf-8"))

def rates():
    rows = {r["cc"]: r for r in get(NBU) if r.get("cc") in CODES}
    items = [{"cc": c, "r": round(float(rows[c]["rate"]), 2)} for c in CODES if c in rows]
    if not items:
        raise ValueError("порожня відповідь НБУ")
    return {"date": rows[items[0]["cc"]].get("exchangedate", ""), "items": items}

def weather():
    ids = list(CITIES)
    q = "?latitude=%s&longitude=%s&current=temperature_2m,weather_code,wind_speed_10m&wind_speed_unit=ms&timezone=auto" % (
        ",".join(str(CITIES[i][0]) for i in ids), ",".join(str(CITIES[i][1]) for i in ids))
    data = get(METEO + q)
    if isinstance(data, dict):
        data = [data]
    out = {}
    for i, d in zip(ids, data):
        c = d["current"]
        out[i] = {"t": int(round(c["temperature_2m"])), "c": int(c["weather_code"]), "w": int(round(c["wind_speed_10m"]))}
    return out

def main():
    path = OUT / "data" / "widgets.json"
    try:
        old = json.loads(path.read_text("utf-8"))
    except Exception:
        old = {}
    new, now = dict(old), datetime.now(timezone.utc)
    try:
        new["rates"] = rates()
    except Exception as e:
        print("ПОМИЛКА курсу НБУ:", e, file=sys.stderr)
    fresh = False
    try:
        fresh = now - datetime.fromisoformat(old["wt"]) < timedelta(minutes=WEATHER_EVERY_MIN)
    except Exception:
        pass
    if not fresh or "weather" not in old:
        try:
            new["weather"] = weather()
            new["wt"] = now.isoformat(timespec="seconds")
        except Exception as e:
            print("ПОМИЛКА погоди:", e, file=sys.stderr)
    if new != old and new:
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(json.dumps(new, ensure_ascii=False), "utf-8")
        print("Віджети оновлено: курс %s, погода %s областей" % ("ok" if "rates" in new else "—", len(new.get("weather", {}))))
    else:
        print("Віджети без змін")

main()
