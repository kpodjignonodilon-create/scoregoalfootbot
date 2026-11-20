import os, time, json, threading, traceback, html
from datetime import datetime, date, timedelta, timezone
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

# ORDRE DE CLASSEMENT - du plus grand au plus petit
# On ne filtre PLUS, on classe seulement. Toutes les ligues passent.
PRIORITY_LEAGUES = [
    1, 2, 3, 4, 5, 6, 7, 8, 9, 10, 11, 12, 13, 14, 15, 16, # Coupes du monde, Euro, Copa, CAN, LDC, Europa
    39, 140, 135, 78, 61, # Premier League, La Liga, Serie A, Bundesliga, Ligue 1
    88, 94, 71, 72, 253, 262, # Eredivisie, Portugal, Brésil, Argentine, MLS, Mexique
    45, 48, 143, 141, # FA Cup, Coupe de France, Copa del Rey, Coppa Italia
    2, 3, 848, 29, 30, # LDC, Europa, Conference League, CAN, etc.
]
def league_rank(league_id):
    if league_id in PRIORITY_LEAGUES:
        return PRIORITY_LEAGUES.index(league_id)
    return 1000 + league_id

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
    r = requests.get(url, headers=headers, params=params, timeout=25)
    print(f"API-Football status: {r.status_code}", flush=True)
    return r

def check_live():
    try:
        print("Check live...", flush=True)
        r = api_get("https://v3.football.api-sports.io/fixtures", {"live": "all"})
        if r.status_code != 200:
            return
        games = r.json().get("response", [])
        # PLUS DE FILTRE : tous les matchs du monde entier
        # On trie par rang : grandes compétitions d'abord, puis les autres
        games.sort(key=lambda g: league_rank(g["league"]["id"]))
        print(f"{len(games)} matchs en live - MONDE ENTIER", flush=True)
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
            country = g["league"]["country"]
            msg = f"⚽ BUT ! {minute}'\n\n{home} {gh} - {ga} {away}\n🏆 {league} - {country}\n\n#ScoreGoalFoot #But #Live"
            post_fb(msg)
            time.sleep(2)  # Petite pause pour ne pas spammer Facebook
    except Exception as e:
        print(f"Erreur check_live: {e}", flush=True)
        traceback.print_exc()

def check_program():
    global posted_program_date
    try:
        now_utc = datetime.now(timezone.utc)
        today = date.today().isoformat()
        if posted_program_date == today:
            return
        if now_utc.hour != 7:  # 07:00 UTC = 08:00 Bénin
            return
        print("Check programme du jour...", flush=True)
        r = api_get("https://v3.football.api-sports.io/fixtures", {"date": today})
        if r.status_code != 200:
            return
        games = r.json().get("response", [])
        # PLUS DE FILTRE : tous les matchs du monde
        games.sort(key=lambda g: (league_rank(g["league"]["id"]), g["fixture"]["date"]))
        if not games:
            posted_program_date = today
            return
        # On poste en 2 parties pour ne pas faire un post trop long
        # Partie 1 : Top matchs
        top = games[:30]
        lines = []
        for g in top:
            dt = datetime.fromisoformat(g["fixture"]["date"].replace("Z", "+00:00")) + timedelta(hours=1)
            lines.append(f"⚽ {dt.strftime('%H:%M')} - {g['teams']['home']['name']} vs {g['teams']['away']['name']} - {g['league']['name']} ({g['league']['country']})")
        msg1 = f"📅 PROGRAMME DU JOUR - {today} - TOP MATCHS 🌍\n\n" + "\n".join(lines) + "\n\n#ScoreGoalFoot #Programme"
        post_fb(msg1)
        # Partie 2 : Tous les autres matchs
        others = games[30:120]
        if others:
            lines2 = []
            for g in others:
                dt = datetime.fromisoformat(g["fixture"]["date"].replace("Z", "+00:00")) + timedelta(hours=1)
                lines2.append(f"⚽ {dt.strftime('%H:%M')} - {g['teams']['home']['name']} vs {g['teams']['away']['name']} - {g['league']['name']}")
            msg2 = f"📅 PROGRAMME DU JOUR - {today} - SUITE 🌍\n\n" + "\n".join(lines2) + "\n\n#ScoreGoalFoot"
            post_fb(msg2)
        posted_program_date = today
        print(f"Programme posté - {len(games)} matchs au total", flush=True)
    except Exception as e:
        print(f"Erreur programme: {e}", flush=True)

def worker():
    print("Worker démarré - MONDE ENTIER - boucle solide", flush=True)
    while True:
        try:
            check_live()
            check_program()
        except Exception as e:
            print(f"Erreur worker: {e}", flush=True)
        time.sleep(60)

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
<label>Ce qu'il a dit :</label><textarea name="citation" rows="6" placeholder="Colle ici ce qu'il a dit..." required></textarea>
<label>Type :</label><select name="type"><option>Avant-match</option><option>Après-match</option><option>Blessure / Mercato</option></select>
<button type="submit">📢 POSTER SUR LA PAGE</button>
</form></body></html>
"""

@app.route("/")
def home():
    return "ScoreGoalFoot bot is running - MONDE ENTIER - <a href='/conference'>Conference de Presse</a>"

@app.route("/conference", methods=["GET", "POST"])
def conference():
    if request.method == "GET":
        return CONFERENCE_HTML
    equipe = request.form.get("equipe", "").strip()
    coach = request.form.get("coach", "").strip()
    match = request.form.get("match", "").strip()
    citation = request.form.get("citation", "").strip()
    typ = request.form.get("type", "Avant-match").strip()
    titre = "CONFÉRENCE DE PRESSE - AVANT-MATCH" if typ == "Avant-match" else "CONFÉRENCE DE PRESSE"
    msg = f"🎙️ {titre}\n\n🏟️ {equipe}\n👔 Coach : {coach}\n⚽ Match : {match}\n\n💬 \"{citation}\"\n\nQu'en pensez-vous les fans ? 👇\n\n#ScoreGoalFoot #ConferenceDePresse #{equipe.replace(' ', '')}"
    ok = post_fb(msg)
    if ok:
        return f"<h2 style='font-family:Arial;text-align:center'>✅ Posté !<br><br><a href='/conference'>Poster une autre</a></h2>"
    else:
        return f"<h2>❌ Erreur, vérifie les Logs. Message :<br>{html.escape(msg)}</h2>"

@app.route("/test")
def test():
    post_fb("✅ Test ScoreGoalFoot - Le bot marche - MONDE ENTIER ! #ScoreGoalFoot")
    return "Test posté"

threading.Thread(target=worker, daemon=True).start()

if __name__ == "__main__":
    app.run(host="0.0.0.0", port=10000)
