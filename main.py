import os, time, json, threading, traceback
from datetime import datetime, date, timedelta
import requests
from flask import Flask

app = Flask(__name__)

API_KEY = os.environ.get("API_KEY", "").strip()
PAGE_IDS = json.loads(os.environ.get("PAGE_IDS", '["1423564444178990"]')) if os.environ.get("PAGE_IDS", "").strip().startswith("[") else [p.strip() for p in os.environ.get("PAGE_IDS", "").split(",") if p.strip()]
PAGE_TOKENS_RAW = os.environ.get("PAGE_TOKENS", "").strip()
try:
    PAGE_TOKENS = json.loads(PAGE_TOKENS_RAW) if PAGE_TOKENS_RAW.startswith("[") or PAGE_TOKENS_RAW.startswith("{") else [PAGE_TOKENS_RAW]
    if isinstance(PAGE_TOKENS, dict):
        PAGE_TOKENS = list(PAGE_TOKENS.values())
except:
    PAGE_TOKENS = [PAGE_TOKENS_RAW]

print(f"DEBUG - API_KEY present: {bool(API_KEY)} len={len(API_KEY)}", flush=True)
print(f"DEBUG - PAGE_IDS: {PAGE_IDS}", flush=True)
print(f"DEBUG - PAGE_TOKENS present: {bool(PAGE_TOKENS_RAW)}", flush=True)

# Grandes ligues seulement - change si tu veux toutes les ligues
LEAGUES = [39, 140, 135, 78, 61, 2, 3, 71, 45, 15, 27, 31, 34, 128, 186, 81]
# 39=Premier League, 140=La Liga, 135=Serie A, 78=Bundesliga, 61=Ligue 1, 2=LDC, 3=Europa, 71=Serie A Brésil, 45=FA Cup, etc.

posted_goals = set()
posted_program_date = None

def post_fb(message):
    for pid, token in zip(PAGE_IDS, PAGE_TOKENS):
        try:
            r = requests.post(f"https://graph.facebook.com/v18.0/{pid}/feed",
                data={"message": message, "access_token": token}, timeout=20)
            print(f"FB post -> {r.status_code} {r.text[:200]}", flush=True)
        except Exception as e:
            print(f"FB post error: {e}", flush=True)

def api_get(url, params):
    headers = {"x-rapidapi-key": API_KEY, "x-rapidapi-host": "v3.football.api-sports.io"}
    r = requests.get(url, headers=headers, params=params, timeout=20)
    print(f"API-Football status: {r.status_code}", flush=True)
    return r

def check_live():
    try:
        print("Check live...", flush=True)
        r = api_get("https://v3.football.api-sports.io/fixtures", {"live": "all"})
        if r.status_code != 200:
            return
        games = r.json().get("response", [])
        # Filtre grandes ligues
        games = [g for g in games if g["league"]["id"] in LEAGUES]
        print(f"{len(games)} matchs en live (grandes ligues)", flush=True)
        for g in games:
            fid = g["fixture"]["id"]
            home = g["teams"]["home"]["name"]
            away = g["teams"]["away"]["name"]
            gh = g["goals"]["home"]
            ga = g["goals"]["away"]
            if gh is None: gh = 0
            if ga is None: ga = 0
            key = f"{fid}-{gh}-{ga}"
            if key in posted_goals:
                continue
            # Ne poste que si il y a eu un but (pas 0-0 au début)
            if gh + ga == 0:
                continue
            posted_goals.add(key)
            minute = g["fixture"]["status"]["elapsed"]
            league = g["league"]["name"]
            msg = f"⚽ BUT ! {minute}'\n\n{home} {gh} - {ga} {away}\n🏆 {league}\n\n#ScoreGoalFoot #But #Live"
            post_fb(msg)
    except Exception as e:
        print(f"Erreur check_live: {e}", flush=True)
        traceback.print_exc()

def check_program():
    global posted_program_date
    try:
        now_utc = datetime.utcnow()
        # 07:00 UTC = 08:00 Bénin
        today = date.today().isoformat()
        if posted_program_date == today:
            return
        if now_utc.hour != 7:
            return
        print("Check programme du jour...", flush=True)
        r = api_get("https://v3.football.api-sports.io/fixtures", {"date": today})
        if r.status_code != 200:
            return
        games = r.json().get("response", [])
        games = [g for g in games if g["league"]["id"] in LEAGUES]
        games.sort(key=lambda x: x["fixture"]["date"])
        if not games:
            posted_program_date = today
            return
        lines = []
        for g in games[:25]:
            dt = datetime.fromisoformat(g["fixture"]["date"].replace("Z", "+00:00")) + timedelta(hours=1)
            heure = dt.strftime("%H:%M")
            lines.append(f"⚽ {heure} - {g['teams']['home']['name']} vs {g['teams']['away']['name']} - {g['league']['name']}")
        msg = f"📅 PROGRAMME DU JOUR - {today}\n\n" + "\n".join(lines) + "\n\n#ScoreGoalFoot #Programme"
        post_fb(msg)
        posted_program_date = today
        print("Programme posté", flush=True)
    except Exception as e:
        print(f"Erreur programme: {e}", flush=True)

def worker():
    print("Worker démarré - boucle solide", flush=True)
    while True:
        try:
            check_live()
            check_program()
        except Exception as e:
            print(f"Erreur worker: {e}", flush=True)
        time.sleep(60)

@app.route("/")
def home():
    return "ScoreGoalFoot bot is running - worker alive"

@app.route("/test")
def test():
    post_fb("✅ Test ScoreGoalFoot - Le bot marche ! #ScoreGoalFoot")
    return "Test posté"

# Lance le worker UNE SEULE FOIS, il ne meurt plus
threading.Thread(target=worker, daemon=True).start()

if __name__ == "__main__":
    app.run(host="0.0.0.0", port=10000)
