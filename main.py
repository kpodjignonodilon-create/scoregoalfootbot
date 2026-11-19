import os
import time
import requests
from flask import Flask
from threading import Thread

app = Flask(__name__)

@app.route('/')
def home():
    return "ScoreGoalFoot Bot is running !"

# --- CONFIG ---
API_KEY = os.environ.get("API_FOOTBALL_KEY")
# Pour 1 page : PAGE_IDS = "123456"
# Pour plusieurs pages : PAGE_IDS = "123456,789012" et PAGE_TOKENS = "token1,token2"
PAGE_IDS = os.environ.get("PAGE_IDS", "").split(",")
PAGE_TOKENS = os.environ.get("PAGE_TOKENS", "").split(",")

HEADERS = {
    "x-rapidapi-host": "v3.football.api-sports.io",
    "x-rapidapi-key": API_KEY
}

posted_goals = set()

def post_to_all_pages(message):
    for i, page_id in enumerate(PAGE_IDS):
        page_id = page_id.strip()
        if not page_id:
            continue
        token = PAGE_TOKENS[i].strip() if i < len(PAGE_TOKENS) else ""
        url = f"https://graph.facebook.com/v19.0/{page_id}/feed"
        data = {"message": message, "access_token": token}
        try:
            r = requests.post(url, data=data, timeout=20)
            print(f"Post page {page_id} : {r.status_code} {r.text[:200]}")
        except Exception as e:
            print(f"Erreur post {page_id}: {e}")

def check_live():
    print("Check live...")
    try:
        # On prend les matchs en live
        url = "https://v3.football.api-sports.io/fixtures?live=all"
        r = requests.get(url, headers=HEADERS, timeout=20)
        data = r.json()
        fixtures = data.get("response", [])
        print(f"{len(fixtures)} matchs en live")

        for f in fixtures:
            fixture_id = f["fixture"]["id"]
            home = f["teams"]["home"]["name"]
            away = f["teams"]["away"]["name"]
            goals_home = f["goals"]["home"]
            goals_away = f["goals"]["away"]
            status = f["fixture"]["status"]["short"]
            minute = f["fixture"]["status"]["elapsed"]

            # On ne poste que si il y a eu un but
            if goals_home is None or goals_away is None:
                continue
            total_goals = goals_home + goals_away
            if total_goals == 0:
                continue

            key = f"{fixture_id}-{goals_home}-{goals_away}"
            if key in posted_goals:
                continue

            # On évite de poster le même score 2 fois
            posted_goals.add(key)

            message = f"⚽ GOAL ! {minute}'\n\n{home} {goals_home} - {goals_away} {away}\n\n#ScoreGoalFoot #Live #Football"
            print(f"Nouveau but: {message}")
            post_to_all_pages(message)

    except Exception as e:
        print(f"Erreur check_live: {e}")

def loop():
    while True:
        check_live()
        # Vérifie toutes les 2 minutes
        time.sleep(120)

if __name__ == "__main__":
    t = Thread(target=loop, daemon=True)
    t.start()
    port = int(os.environ.get("PORT", 10000))
    app.run(host="0.0.0.0", port=port)
