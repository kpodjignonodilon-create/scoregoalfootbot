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

PRIORITY_LEAGUES = [1,2,3,4,5,6,7,8,9,10,11,12,13,14,15,16,39,140,135,78,61,88,94,71,72,253,262,45,48,143,141,848,29,30]
def league_rank(league_id):
    if league_id in PRIORITY_LEAGUES:
        return PRIORITY_LEAGUES.index(league_id)
    return 1000 + league_id

posted_goals = set()
posted_program_date = None
posted_result_date = None

def post_fb(message):
    for pid, token in zip(PAGE_IDS, PAGE_TOKENS):
        try:
            r = requests.post(f"https://graph.facebook.com/v18.0/{pid}/feed", data={"message": message, "access_token": token}, timeout=20)
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
            time.sleep(2)
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
        if now_utc.hour != 7:
            return
        print("Check programme du jour...", flush=True)
        r = api_get("https://v3.football.api-sports.io/fixtures", {"date": today})
        if r.status_code != 200:
            return
        games = r.json().get("response", [])
        games.sort(key=lambda g: (league_rank(g["league"]["id"]), g["fixture"]["date"]))
        if not games:
            posted_program_date = today
            return
        top = games[:30]
        lines = []
        for g in top:
            dt = datetime.fromisoformat(g["fixture"]["date"].replace("Z", "+00:00")) + timedelta(hours=1)
            lines.append(f"⚽ {dt.strftime('%H:%M')} - {g['teams']['home']['name']} vs {g['teams']['away']['name']} - {g['league']['name']} ({g['league']['country']})")
        post_fb(f"📅 PROGRAMME DU JOUR - {today} - TOP MATCHS 🌍\n\n" + "\n".join(lines) + "\n\n#ScoreGoalFoot #Programme")
        others = games[30:120]
        if others:
            lines2 = []
            for g in others:
                dt = datetime.fromisoformat(g["fixture"]["date"].replace("Z", "+00:00")) + timedelta(hours=1)
                lines2.append(f"⚽ {dt.strftime('%H:%M')} - {g['teams']['home']['name']} vs {g['teams']['away']['name']} - {g['league']['name']}")
            post_fb(f"📅 PROGRAMME DU JOUR - {today} - SUITE 🌍\n\n" + "\n".join(lines2) + "\n\n#ScoreGoalFoot")
        posted_program_date = today
        print(f"Programme posté - {len(games)} matchs", flush=True)
    except Exception as e:
        print(f"Erreur programme: {e}", flush=True)

def check_results():
    global posted_result_date
    try:
        now_utc = datetime.now(timezone.utc)
        today = date.today().isoformat()
        if posted_result_date == today:
            return
        if now_utc.hour != 22:
            return
        print("Check résultats du jour...", flush=True)
        r = api_get("https://v3.football.api-sports.io/fixtures", {"date": today, "status": "FT"})
        if r.status_code != 200:
            return
        games = r.json().get("response", [])
        games.sort(key=lambda g: league_rank(g["league"]["id"]))
        if not games:
            posted_result_date = today
            return
        games = [g for g in games if g["goals"]["home"] is not None]
        top = games[:30]
        lines = []
        for g in top:
            lines.append(f"✅ {g['teams']['home']['name']} {g['goals']['home']} - {g['goals']['away']} {g['teams']['away']['name']} - {g['league']['name']} ({g['league']['country']})")
        post_fb(f"📊 RÉSULTATS DU JOUR - {today} - TOP MATCHS 🌍\n\n" + "\n".join(lines) + "\n\nQuel résultat vous a surpris ? 👇\n\n#ScoreGoalFoot #Resultats")
        others = games[30:120]
        if others:
            lines2 = []
            for g in others:
                lines2.append(f"✅ {g['teams']['home']['name']} {g['goals']['home']} - {g['goals']['away']} {g['teams']['away']['name']} - {g['league']['name']}")
            post_fb(f"📊 RÉSULTATS DU JOUR - {today} - SUITE 🌍\n\n" + "\n".join(lines2) + "\n\n#ScoreGoalFoot #Resultats")
        posted_result_date = today
        print(f"Résultats postés - {len(games)} matchs", flush=True)
    except Exception as e:
        print(f"Erreur résultats: {e}", flush=True)

def worker():
    print("Worker démarré - MONDE ENTIER + RESULTATS", flush=True)
    while True:
        try:
            check_live()
            check_program()
            check_results()
        except Exception as e:
            print(f"Erreur worker: {e}", flush=True)
        time.sleep(60)

CONFERENCE_HTML = """
<html><head><meta charset="utf-8"><meta name="viewport" content="width=device-width, initial-scale=1">
<title>Conference de Presse</title>
<style>body{font-family:Arial;padding:15px;background:#f0f2f5}input,select,textarea{width:100%;padding:12px;margin:8px 0;border-radius:8px;border:1px solid #ccc;font-size:16px}button{background:#1877f2;color:white;padding:14px;border:none;border-radius:8px;width:100%;font-size:18px;font-weight:bold}h2{text-align:center}</style>
</head><body>
<h2>🎙️ Conférence de Presse</h2>
<form method="POST" action="/conference">
<label>Équipe :</label><input name="equipe" required>
<label>Entraîneur :</label><input name="coach" required>
<label>Match :</label><input name="match" required>
<label>Ce qu'il a dit :</label><textarea name="citation" rows="6" required></textarea>
<label>Type :</label><select name="type"><option>Avant-match</option><option>Après-match</option><option>Blessure / Mercato</option></select>
<button type="submit">📢 POSTER SUR LA PAGE</button>
</form></body></html>
"""

@app.route("/")
def home():
    return "ScoreGoalFoot bot is running - MONDE ENTIER - <a href='/conference'>Conference</a> - <a href='/debug-live'>Debug Live</a>"

@app.route("/conference", methods=["GET", "POST"])
def conference():
    if request.method == "GET":
        return CONFERENCE_HTML
    equipe = request.form.get("equipe", "").strip()
    coach = request.form.get("coach", "").strip()
    match = request.form.get("match", "").strip()
    citation = request.form.get("citation", "").strip()
    typ = request.form.get("type", "Avant-match").strip()
    msg = f"🎙️ CONFÉRENCE DE PRESSE - {typ}\n\n🏟️ {equipe}\n👔 Coach : {coach}\n⚽ Match : {match}\n\n💬 \"{citation}\"\n\nQu'en pensez-vous ? 👇\n\n#ScoreGoalFoot #ConferenceDePresse"
    ok = post_fb(msg)
    if ok:
        return f"<h2 style='font-family:Arial;text-align:center'>✅ Posté !<br><br><a href='/conference'>Poster une autre</a></h2>"
    else:
        return f"<h2>❌ Erreur, vérifie les Logs.</h2>"

@app.route("/debug-live")
def debug_live():
    try:
        r = api_get("https://v3.football.api-sports.io/fixtures", {"live": "all"})
        data = r.json()
        games = data.get("response", [])
        txt = f"API status: {r.status_code}<br>Nombre live selon API: {len(games)}<br><br>"
        for g in games[:50]:
            txt += f"{g['teams']['home']['name']} {g['goals']['home']} - {g['goals']['away']} {g['teams']['away']['name']} - {g['league']['name']} - {g['fixture']['status']['elapsed']}'<br>"
        if not games:
            txt += "Aucun match live selon API-Football en ce moment."
        return txt
    except Exception as e:
        return f"Erreur: {e}"

@app.route("/test-resultats")
def test_resultats():
    try:
        today = date.today().isoformat()
        r = api_get("https://v3.football.api-sports.io/fixtures", {"date": today, "status": "FT"})
        games = r.json().get("response", [])
        games.sort(key=lambda g: league_rank(g["league"]["id"]))
        games = [g for g in games if g["goals"]["home"] is not None][:10]
        if not games:
            return "Aucun match terminé aujourd'hui pour l'instant. Réessaie ce soir."
        lines = [f"✅ {g['teams']['home']['name']} {g['goals']['home']} - {g['goals']['away']} {g['teams']['away']['name']} - {g['league']['name']}" for g in games]
        post_fb(f"📊 RÉSULTATS DU JOUR - TEST - {today}\n\n" + "\n".join(lines) + "\n\n#ScoreGoalFoot #Resultats")
        return "Résultats test postés ! Regarde ta Page."
    except Exception as e:
        return f"Erreur: {e}"

@app.route("/test")
def test():
    post_fb("✅ Test ScoreGoalFoot - MONDE ENTIER ! #ScoreGoalFoot")
    return "Test posté"

threading.Thread(target=worker, daemon=True).start()

if __name__ == "__main__":
    app.run(host="0.0.0.0", port=10000)
