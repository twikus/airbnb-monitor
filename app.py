"""
Point d'entrée production (Docker / Coolify).

Routes :
  GET  /                      → dashboard HTML
  GET  /api/status            → état du scraper en cours
  GET  /api/analyses          → liste toutes les analyses
  POST /api/analyses          → ajoute une analyse  {checkin, checkout}
  DEL  /api/analyses/<id>     → supprime une analyse et ses relevés
  POST /api/scrape            → lance un relevé manuel {analysis_id, checkin, checkout}
"""
import json
import logging
import os
import schedule
import sys
import threading
import time

from functools import wraps
from flask import Flask, jsonify, request, send_file, session, redirect

import config as cfg
import database as db
import scraper
import dashboard as dash_gen

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(message)s",
    handlers=[logging.StreamHandler(sys.stdout)],
)
logger = logging.getLogger(__name__)

app            = Flask(__name__)
app.secret_key = cfg.SECRET_KEY
PORT           = int(os.environ.get("PORT", 8080))


def login_required(f):
    @wraps(f)
    def decorated(*args, **kwargs):
        if not session.get("logged_in"):
            return redirect("/login")
        return f(*args, **kwargs)
    return decorated


def _login_page(error=None):
    err_html = f'<p class="error">{error}</p>' if error else ""
    return f"""<!DOCTYPE html>
<html lang="fr">
<head>
<meta charset="UTF-8">
<meta name="viewport" content="width=device-width, initial-scale=1.0">
<title>Connexion — Airbnb Market</title>
<style>
  :root {{ --bg:#12080d; --card:#2a1422; --border:#5c2d3a; --wine:#9b2335; --gold:#c9a84c; --gold-lt:#e8cc7a; --cream:#f5f0e8; --muted:#9e8a90; --down:#f87171; }}
  * {{ box-sizing:border-box; margin:0; padding:0; }}
  body {{ background:var(--bg); color:var(--cream); font-family:'Segoe UI',system-ui,sans-serif;
          min-height:100vh; display:flex; align-items:center; justify-content:center; }}
  .card {{
    background:var(--card); border:1px solid var(--border); border-radius:16px;
    padding:40px 36px; width:100%; max-width:380px;
    box-shadow:0 20px 60px rgba(0,0,0,.5);
  }}
  .card::before {{
    content:'🍷'; display:block; text-align:center; font-size:2.5rem; margin-bottom:16px;
  }}
  h1 {{ font-family:Georgia,serif; color:var(--gold-lt); font-size:1.4rem; text-align:center; margin-bottom:6px; }}
  p.sub {{ color:var(--muted); font-size:.82rem; text-align:center; margin-bottom:28px; }}
  label {{ font-size:.72rem; text-transform:uppercase; letter-spacing:1px; color:var(--muted); display:block; margin-bottom:6px; }}
  input[type=password] {{
    width:100%; background:#1e0f18; border:1px solid var(--border); border-radius:8px;
    padding:10px 14px; color:var(--cream); font-size:.95rem; margin-bottom:20px;
    outline:none; transition:border-color .2s;
  }}
  input[type=password]:focus {{ border-color:var(--gold); }}
  button {{
    width:100%; background:var(--wine); color:var(--cream); border:none;
    border-radius:8px; padding:11px; font-size:.95rem; cursor:pointer; transition:opacity .2s;
  }}
  button:hover {{ opacity:.85; }}
  .error {{ color:var(--down); font-size:.82rem; text-align:center; margin-bottom:16px; }}
</style>
</head>
<body>
  <div class="card">
    <h1>Airbnb Market — Dijon</h1>
    <p class="sub">Accès privé</p>
    {err_html}
    <form method="POST" action="/login">
      <label>Mot de passe</label>
      <input type="password" name="password" autofocus autocomplete="current-password">
      <button type="submit">Connexion</button>
    </form>
  </div>
</body>
</html>"""

# ── État du scraper ───────────────────────────────────────────────────────────
_status = {
    "running":     False,
    "analysis_id": None,   # id de l'analyse en cours
    "checkin":     None,
    "checkout":    None,
    "last_count":  None,
    "last_time":   None,
}

# ── Routes ────────────────────────────────────────────────────────────────────

@app.route("/health")
def health():
    return "ok", 200


@app.route("/login", methods=["GET", "POST"])
def login():
    if request.method == "POST":
        if request.form.get("password") == cfg.ADMIN_PASSWORD:
            session["logged_in"] = True
            return redirect("/")
        return _login_page(error="Mot de passe incorrect")
    return _login_page()


@app.route("/logout")
def logout():
    session.clear()
    return redirect("/login")


@app.route("/")
@login_required
def index():
    if not os.path.exists(cfg.DASHBOARD_PATH):
        db.init_db()
        dash_gen.generate()
    return send_file(os.path.abspath(cfg.DASHBOARD_PATH))


@app.route("/api/status")
@login_required
def api_status():
    return jsonify(_status)


@app.route("/api/analyses", methods=["GET"])
@login_required
def api_get_analyses():
    rows = db.get_all_analyses()
    return jsonify([dict(r) for r in rows])


@app.route("/api/analyses", methods=["POST"])
@login_required
def api_add_analysis():
    data     = request.get_json(force=True)
    checkin  = (data.get("checkin")  or "").strip()
    checkout = (data.get("checkout") or "").strip()

    if not checkin or not checkout:
        return jsonify({"error": "Dates manquantes"}), 400
    if checkin >= checkout:
        return jsonify({"error": "L'arrivée doit être avant le départ"}), 400

    analysis_id = db.add_analysis(checkin, checkout)
    if analysis_id is None:
        return jsonify({"error": "Cette analyse existe déjà"}), 409

    dash_gen.generate()
    logger.info(f"Analyse ajoutée #{analysis_id} : {checkin} → {checkout}")
    return jsonify({"status": "ok", "id": analysis_id}), 201


@app.route("/api/analyses/<int:analysis_id>", methods=["DELETE"])
@login_required
def api_delete_analysis(analysis_id):
    if _status["running"] and _status.get("analysis_id") == analysis_id:
        return jsonify({"error": "Impossible de supprimer une analyse en cours de scraping"}), 409

    ok = db.delete_analysis(analysis_id)
    if not ok:
        return jsonify({"error": "Analyse introuvable"}), 404

    dash_gen.generate()
    logger.info(f"Analyse #{analysis_id} supprimée")
    return jsonify({"status": "ok"})


@app.route("/api/scrape", methods=["POST"])
@login_required
def api_scrape():
    if _status["running"]:
        return jsonify({"status": "already_running"}), 409

    data        = request.get_json(force=True) or {}
    analysis_id = data.get("analysis_id")
    checkin     = (data.get("checkin")  or "").strip()
    checkout    = (data.get("checkout") or "").strip()

    if not checkin or not checkout:
        return jsonify({"error": "Dates manquantes"}), 400

    def _do():
        _status["running"]     = True
        _status["analysis_id"] = analysis_id
        _status["checkin"]     = checkin
        _status["checkout"]    = checkout
        try:
            _run_single(checkin, checkout)
        finally:
            _status["running"]     = False
            _status["analysis_id"] = None
            _status["checkin"]     = None
            _status["checkout"]    = None

    threading.Thread(target=_do, daemon=True).start()
    return jsonify({"status": "started"})


# ── Tâche de scraping ─────────────────────────────────────────────────────────

def _run_single(checkin: str, checkout: str):
    logger.info(f"=== Relevé {checkin} → {checkout} ===")
    try:
        result = scraper.run(checkin, checkout)
    except Exception as e:
        logger.error(f"Erreur scraping: {e}", exc_info=True)
        result = {"count": None, "url": scraper.build_search_url(checkin, checkout), "screenshot": None}

    db.insert_snapshot(checkin, checkout, result["count"], result["url"], result.get("screenshot"))
    _status["last_count"] = result["count"]
    _status["last_time"]  = result.get("timestamp")
    dash_gen.generate()
    logger.info(f"✅ {result['count']} logement(s) — {checkin} / {checkout}")


def _run_all_analyses():
    """Lance le scraping de toutes les analyses actives (tâche planifiée)."""
    if _status["running"]:
        logger.warning("Scraping déjà en cours, tâche planifiée ignorée")
        return
    analyses = db.get_all_analyses()
    if not analyses:
        logger.info("Aucune analyse active, rien à scraper")
        return
    _status["running"] = True
    try:
        for a in analyses:
            _status["analysis_id"] = a["id"]
            _run_single(a["checkin"], a["checkout"])
    finally:
        _status["running"]     = False
        _status["analysis_id"] = None


# ── Démarrage ─────────────────────────────────────────────────────────────────

def _init():
    """Initialisation en arrière-plan — Flask répond déjà pendant ce temps."""
    os.makedirs("data/screenshots", exist_ok=True)
    db.init_db()

    if not db.get_all_analyses():
        db.add_analysis(cfg.CHECKIN_DATE, cfg.CHECKOUT_DATE)
        logger.info(f"Analyse par défaut créée : {cfg.CHECKIN_DATE} → {cfg.CHECKOUT_DATE}")

    dash_gen.generate()

    hhmm = f"{cfg.RUN_HOUR:02d}:{cfg.RUN_MINUTE:02d}"
    schedule.every().day.at(hhmm).do(_run_all_analyses)
    logger.info(f"Planificateur actif — relevé automatique à {hhmm}")

    while True:
        schedule.run_pending()
        time.sleep(30)


if __name__ == "__main__":
    # Démarrer l'init + planificateur en arrière-plan
    # Flask écoute immédiatement sur le port → Coolify health check OK
    threading.Thread(target=_init, daemon=True).start()
    app.run(host="0.0.0.0", port=PORT, threaded=True)
