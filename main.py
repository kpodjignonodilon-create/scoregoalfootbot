import os
import time
import requests
import threading
from flask import Flask

app = Flask(__name__)

API_KEY = os.environ.get("API_KEY", "")
PAGE_IDS = [x.strip() for x in os.environ.get("PAGE_IDS", "").split(",") if x.strip()]
PAGE_TOKENS = [x.strip() for x in os.environ.get("PAGE_TOKENS", "").split(",") if x.strip()]

print(f"DEBUG - API_KEY present: {bool(API_KEY)} len={len(API_KEY) if API_KEY else 0}", flush=True)
print(f"DEBUG - PAGE_IDS: {PAGE_IDS}", flush=True)
print(f"DEBUG - PAGE_TOKENS present: {bool(PAGE_TOKENS)}", flush=True)

HEADERS = {"x-apisports-key": API_KEY}
seen_goals = set()

def post_facebook(message):
    for page_id, token in zip(PAGE_IDS, PAGE_TOKENS):
        try:
            r = requests.post(f"https://graph.facebook.com/{page_id}/feed",
                data={"message": message, "access_token": token}, timeout=20)
            print(f"FB post -> {r.status_code} {r.text[:200]}", flush=True)
        except Exception as e:
            print(f"FB error: {e}", flush=True)

def check_live():
    print("Check live...", flush=True)
    try:
        r = requests.get("https://v3.football.api-sports.io/fixtures?live=all",
            headers=HEADERS, timeout=20)
        print(f"API-Football status: {r.status_code}", flush=True)
        if r.status_code != 200:
            return
        fixtures = r.json().get("response", [])
        print(f"{len(fixtures)} matchs en live", flush=True)
        for f in fixtures:
            fixture = f.get("fixture", {})
            teams = f.get("teams", {})
            goals = f.get("goals", {})
            league = f.get("league", {})
            fid = fixture.get("id")
            home = teams.get("home", {}).get("name", "?")
            away = teams.get("away", {}).get("name", "?")
            gh = goals.get("home", 0) or 0
            ga = goals.get("away", 0) or 0
            minute = fixture.get("status", {}).get("elapsed")
            key = f"{fid}-{gh}-{ga}"
            if key in seen_goals:
                continue
            # Premier passage, on mémorise sans poster pour ne pas spammer l'historique
            if f"{fid}-start" not in seen_goals:
                seen_goals.add(f"{fid}-start")
                seen_goals.add(key)
                continue
            seen_goals.add(key)
            msg = f"⚽ BUT / SCORE EN DIRECT\n\n{home} {gh} - {ga} {away}\n{league.get('name','')} - {minute}'\n\n#ScoreGoalFoot #Live"
            post_facebook(msg)
    except Exception as e:
        print(f"Check live error: {e}", flush=True)

def loop():
    # Petite attente au démarrage
    time.sleep(5)
    while True:
        check_live()
        time.sleep(60)  # vérifie toutes les 60 secondes

# Lance la boucle en fond
threading.Thread(target=loop, daemon=True).start()

@app.route("/")
def home():
    return "ScoreGoalFoot Bot en ligne !"

@app.route("/test")
def test():
    post_facebook("✅ TEST - Le bot ScoreGoalFoot est en ligne !")
    return "Test post envoyé..."

if __name__ == "__main__":
    app.run(host="0.0.0.0", port=10000)
