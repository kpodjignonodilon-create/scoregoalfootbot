import os, time, json, threading, traceback, html
from datetime import datetime, date, timedelta
import requests
from flask import Flask, request

app = Flask(__name__)

API_KEY = os.environ.get("API_KEY", "").strip()
PAGE_IDS_RAW = os.environ.get("PAGE_IDS", "").strip()
try:
    PAGE_IDS = json.loads(PAGE_IDS_RAW) if PAGE_IDS_RAW.startswith("[") else [p.strip() for p in PAGE_IDS_RAW.split(",") if p.strip()]
except:
    PAGE_IDS = ["1423564444178990"]
PAGE_TOKENS_RAW = os.environ.get("PAGE_TOKENS", "").strip()
try:
    PAGE_TOKENS = json.loads(PAGE_TOKENS_RAW) if PAGE_TOKENS_RAW.startswith("[") or PAGE_TOKENS_RAW.startswith("{") else [PAGE_TOKENS_RAW]
    if isinstance(PAGE_TOKENS, dict):
        PAGE_TOKENS = list(PAGE_TOKENS.values())
except:
    PAGE_TOKENS = [PAGE_TOKENS_RAW]

print(f"DEBUG - API_KEY present: {bool(API_KEY)} len={len(API_KEY)}", flush=True)
print(f"DEBUG - PAGE_IDS: {PAGE_IDS}", flush=True)

LEAGUES = [39, 140, 135, 78, 61, 2, 3, 71, 45, 15, 27, 31, 34, 128, 186, 81]
posted_goals = set()
posted_program_date = None

def post_fb(message):
    for pid, token in zip(PAGE_IDS, PAGE_TOKENS):
        try:
            r = requests.post(f"https://graph.facebook.com/v18.0/{pid}/feed",
                data={"message": message, "access_token": token}, timeout=20)
            print(f"FB post -> {r.status_code} {r.text[:300]}", flush=True)
            return r.status_code == 200
        except Exception as e:
            print(f"FB post error: {e}", flush=True)
            return False
    return False

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
        games = [g for g in games if g["league"]["id"] in LEAGUES]
        print(f"{len(games)} matchs en live (grandes ligues)", flush=True)
        for g in games:
            fid = g["fixture"]["id"]
            home = g["teams"]["home"]["name"]
            away = g["teams"]["away"]["name"]
            gh = g["goals"]["home"] or 0
            ga = g["goals"]["away"] or 0
            key = f"{fid}-{gh}-{ga}"
            if key in posted_goals:
                continue
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
            lines.append(f"⚽ {dt.strftime('%H:%M')} - {g['teams']['home']['name']} vs {g['teams']['away']['name']} - {g['league']['name']}")
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

# ========== CONFERENCE DE PRESSE ==========
# Tu vas sur : https://scoregoalfootbot.onrender.com/conference
# Tu remplis le formulaire, tu cliques Poster, et ça poste sur ta Page.

CONFERENCE_HTML = """
<html><head><meta charset="utf-8"><meta name="viewport" content="width=device-width, initial-scale=1">
<title>Conference de Presse - ScoreGoalFoot</title>
<style>body{font-family:Arial;padding:15px;background:#f0f2f5}input,select,textarea{width:100%;padding:12px;margin:8px 0;border-radius:8px;border:1px solid #ccc;font-size:16px}button{background:#1877f2;color:white;padding:14px;border:none;border-radius:8px;width:100%;font-size:18px;font-weight:bold}h2{text-align:center}</style>
</head><body>
<h2>🎙️ Conférence de Presse</h2>
<form method="POST" action="/conference">
<label>Équipe :</label><input name="equipe" placeholder="Ex: Real Madrid" required>
<label>Entraîneur :</label><input name="coach" placeholder="Ex: Xabi Alonso" required>
<label>Match à venir :</label><input name="match" placeholder="Ex: Real Madrid vs Barcelone - Dimanche 20:45" required>
<label>Ce qu'il a dit (colle ici) :</label><textarea name="citation" rows="6" placeholder="Ex: On est prêts, on va tout donner pour gagner ce Clasico..." required></textarea>
<label>Type :</label><select name="type"><option>Avant-match</option><option>Après-match</option><option>Blessure / Mercato</option></select>
<button type="submit">📢 POSTER SUR LA PAGE</button>
</form>
<p style="text-align:center;color:#888">ScoreGoalFoot Bot</p>
</body></html>
"""

@app.route("/")
def home():
    return "ScoreGoalFoot bot is running - worker alive - <a href='/conference'>Conference de Presse</a>"

@app.route("/conference", methods=["GET", "POST"])
def conference():
    if request.method == "GET":
        return CONFERENCE_HTML
    equipe = request.form.get("equipe", "").strip()
    coach = request.form.get("coach", "").strip()
    match = request.form.get("match", "").strip()
    citation = request.form.get("citation", "").strip()
    typ = request.form.get("type", "Avant-match").strip()
    if typ == "Avant-match":
        emoji, titre = "🎙️", "CONFÉRENCE DE PRESSE - AVANT-MATCH"
    elif typ == "Après-match":
        emoji, titre = "🎙️", "CONFÉRENCE DE PRESSE - APRÈS-MATCH"
    else:
        emoji, titre = "🚨", "CONFÉRENCE DE PRESSE"
    msg = f"{emoji} {titre}\n\n🏟️ {equipe}\n👔 Coach : {coach}\n⚽ Match : {match}\n\n💬 \"{citation}\"\n\nQu'en pensez-vous les fans ? 👇\n\n#ScoreGoalFoot #ConferenceDePresse #{equipe.replace(' ', '')}"
    ok = post_fb(msg)
    if ok:
        return f"<h2 style='font-family:Arial;text-align:center'>✅ Posté sur ta Page !<br><br><a href='/conference'>Poster une autre conférence</a></h2>"
    else:
        return f"<h2>❌ Erreur, vérifie les Logs Render. Message essayé :<br>{html.escape(msg)}</h2>"

@app.route("/test")
def test():
    post_fb("✅ Test ScoreGoalFoot - Le bot marche ! #ScoreGoalFoot")
    return "Test posté"

threading.Thread(target=worker, daemon=True).start()

if __name__ == "__main__":
    app.run(host="0.0.0.0", port=10000)
