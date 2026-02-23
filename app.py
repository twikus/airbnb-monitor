"""
Point d'entrée production (Docker / Coolify).
Flask API + dashboard HTML + planificateur quotidien.

Routes :
  GET  /              → dashboard HTML
  GET  /api/status    → état du scraper (running, last_count, last_time)
  POST /api/scrape    → déclenche un relevé manuel
  POST /api/dates     → met à jour checkin/checkout et régénère le dashboard
"""
import json
import logging
import os
import schedule
import sys
import threading
import time

from flask import Flask, jsonify, request, send_file

import config as cfg
import database as db
import scraper
import dashboard as dash_gen

# ── Logging stdout (compatible Docker / Coolify logs) ────────────────────────
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(message)s",
    handlers=[logging.StreamHandler(sys.stdout)],
)
logger = logging.getLogger(__name__)

app  = Flask(__name__)
PORT = int(os.environ.get("PORT", 8080))

# ── Config runtime persistée (survit aux redémarrages du conteneur) ──────────
RUNTIME_CFG_PATH = "data/runtime_config.json"

def _load_runtime_config():
    if os.path.exists(RUNTIME_CFG_PATH):
        with open(RUNTIME_CFG_PATH) as f:
            data = json.load(f)
        cfg.CHECKIN_DATE  = data.get("checkin",  cfg.CHECKIN_DATE)
        cfg.CHECKOUT_DATE = data.get("checkout", cfg.CHECKOUT_DATE)
        logger.info(f"Dates chargées : {cfg.CHECKIN_DATE} → {cfg.CHECKOUT_DATE}")

def _save_runtime_config():
    os.makedirs("data", exist_ok=True)
    with open(RUNTIME_CFG_PATH, "w") as f:
        json.dump({"checkin": cfg.CHECKIN_DATE, "checkout": cfg.CHECKOUT_DATE}, f)

# ── État du scraper ───────────────────────────────────────────────────────────
_status = {"running": False, "last_count": None, "last_time": None}

# ── Tâche de scraping ─────────────────────────────────────────────────────────
def _run_job():
    logger.info(f"=== Relevé {cfg.CHECKIN_DATE} → {cfg.CHECKOUT_DATE} ===")
    db.init_db()
    try:
        result = scraper.run()
    except Exception as e:
        logger.error(f"Erreur scraping: {e}", exc_info=True)
        result = {"count": None, "url": scraper.build_search_url(), "screenshot": None}

    db.insert_snapshot(result["count"], result["url"], result.get("screenshot"))
    _status["last_count"] = result["count"]
    _status["last_time"]  = result.get("timestamp")
    dash_gen.generate()
    logger.info(f"✅ {result['count']} logement(s) — dashboard mis à jour")

# ── Routes Flask ──────────────────────────────────────────────────────────────

@app.route("/")
def index():
    if not os.path.exists(cfg.DASHBOARD_PATH):
        db.init_db()
        dash_gen.generate()
    return send_file(os.path.abspath(cfg.DASHBOARD_PATH))


@app.route("/api/status")
def api_status():
    return jsonify(_status)


@app.route("/api/scrape", methods=["POST"])
def api_scrape():
    if _status["running"]:
        return jsonify({"status": "already_running"}), 409

    def _do():
        _status["running"] = True
        try:
            _run_job()
        finally:
            _status["running"] = False

    threading.Thread(target=_do, daemon=True).start()
    return jsonify({"status": "started"})


@app.route("/api/dates", methods=["POST"])
def api_dates():
    data     = request.get_json(force=True)
    checkin  = (data.get("checkin")  or "").strip()
    checkout = (data.get("checkout") or "").strip()

    if not checkin or not checkout:
        return jsonify({"error": "Dates manquantes"}), 400
    if checkin >= checkout:
        return jsonify({"error": "L'arrivée doit être avant le départ"}), 400

    cfg.CHECKIN_DATE  = checkin
    cfg.CHECKOUT_DATE = checkout
    _save_runtime_config()
    dash_gen.generate()
    logger.info(f"Dates mises à jour → {checkin} / {checkout}")
    return jsonify({"status": "ok", "checkin": checkin, "checkout": checkout})


# ── Démarrage ─────────────────────────────────────────────────────────────────
if __name__ == "__main__":
    os.makedirs("data/screenshots", exist_ok=True)
    _load_runtime_config()

    # Premier relevé en arrière-plan dès le démarrage
    threading.Thread(target=lambda: (_status.__setitem__("running", True),
                                     _run_job(),
                                     _status.__setitem__("running", False)),
                     daemon=True).start()

    # Planification quotidienne dans un thread séparé
    hhmm = f"{cfg.RUN_HOUR:02d}:{cfg.RUN_MINUTE:02d}"
    schedule.every().day.at(hhmm).do(_run_job)
    logger.info(f"Planificateur actif — relevé automatique à {hhmm}")

    def _scheduler_loop():
        while True:
            schedule.run_pending()
            time.sleep(30)

    threading.Thread(target=_scheduler_loop, daemon=True).start()

    app.run(host="0.0.0.0", port=PORT, threaded=True)
