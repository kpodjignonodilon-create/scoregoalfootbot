import os, time, threading, requests
from flask import Flask

app = Flask(__name__)

API_KEY = os.environ.get("API_FOOTBALL_KEY", "").strip()
PAGE_IDS = os.environ.get("PAGE_IDS", "").strip().split(",")
PAGE_TOKENS = os.environ.get("PAGE_TOKENS", "").strip().split(",")

print(f"DEBUG - API_KEY present: {bool(API_KEY)} len={len(API_KEY)}", flush=True)
print(f"DEBUG - PAGE_IDS: {PAGE_IDS}", flush=True)
print(f"DEBUG - PAGE_TOKENS present: {bool(PAGE_TOKENS[0]) if PAGE_TOKENS else False}", flush=True)

seen_goals = set()

def post_to_fb(message):
    for pid, token in zip(PAGE_IDS, PAGE_TOKENS):
        try:
            r = requests.post(f"https://graph.facebook.com/v19.0/{pid.strip()}/feed",
                data={"message": message, "access_token": token.strip()}, timeout=15)
            print(f"FB post -> {r.status_code} {r.text[:200]}", flush=True)
        except Exception as e:
            print(f"FB ERROR: {e}", flush=True)

def check_live():
    while True:
        try:
            print("Check live...", flush=True)
            if not API_KEY:
                print("ERROR: API_FOOTBALL_KEY manquante !", flush=True)
            else:
                r = requests.get("https://v3.football.api-sports.io/fixtures?live=all",
                    headers={"x-apisports-key": API_KEY}, timeout=15)
                print(f"API-Football status: {r.status_code}", flush=True)
                data = r.json()
                fixtures = data.get("response", [])
                print(f"{len(fixtures)} matchs en live", flush=True)
                for f in fixtures:
                    fid = f["fixture"]["id"]
                    goals_home = f["goals"]["home"]
                    goals_away = f["goals"]["away"]
                    key = f"{fid}-{goals_home}-{goals_away}"
                    if key not in seen_goals and (goals_home is not None and goals_away is not None):
                        # On ne poste que si c'est un nouveau score et pas le 0-0 du début
                        if goals_home + goals_away > 0:
                            home = f["teams"]["home"]["name"]
                            away = f["teams"]["away"]["name"]
                            minute = f["fixture"]["status"]["elapsed"]
                            msg = f"⚽ BUT ! {home} {goals_home} - {goals_away} {away} ({minute}')\n#ScoreGoalFoot #Live"
                            print(f"POST: {msg}", flush=True)
                            post_to_fb(msg)
                        seen_goals.add(key)
        except Exception as e:
            print(f"ERROR check_live: {e}", flush=True)
        time.sleep(120)

@app.route("/")
def home():
    return "ScoreGoalFoot Bot is running ✅"

@app.route("/test")
def test():
    post_to_fb("✅ TEST - Le bot ScoreGoalFoot est en ligne ! Il va poster les buts en live. ⚽")
    return "Test post envoyé, regarde ta Page Facebook !"

threading.Thread(target=check_live, daemon=True).start()

if __name__ == "__main__":
    app.run(host="0.0.0.0", port=int(os.environ.get("PORT", 10000)))
