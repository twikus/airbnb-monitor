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

from flask import Flask, jsonify, request, send_file

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

app  = Flask(__name__)
PORT = int(os.environ.get("PORT", 8080))

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

@app.route("/")
def index():
    if not os.path.exists(cfg.DASHBOARD_PATH):
        db.init_db()
        dash_gen.generate()
    return send_file(os.path.abspath(cfg.DASHBOARD_PATH))


@app.route("/api/status")
def api_status():
    return jsonify(_status)


@app.route("/api/analyses", methods=["GET"])
def api_get_analyses():
    rows = db.get_all_analyses()
    return jsonify([dict(r) for r in rows])


@app.route("/api/analyses", methods=["POST"])
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

if __name__ == "__main__":
    os.makedirs("data/screenshots", exist_ok=True)
    db.init_db()

    # Créer l'analyse par défaut si la base est vide
    if not db.get_all_analyses():
        db.add_analysis(cfg.CHECKIN_DATE, cfg.CHECKOUT_DATE)
        logger.info(f"Analyse par défaut créée : {cfg.CHECKIN_DATE} → {cfg.CHECKOUT_DATE}")

    # Régénérer le dashboard au démarrage (pour avoir la dernière version de l'UI)
    dash_gen.generate()

    # Planification quotidienne
    hhmm = f"{cfg.RUN_HOUR:02d}:{cfg.RUN_MINUTE:02d}"
    schedule.every().day.at(hhmm).do(_run_all_analyses)
    logger.info(f"Planificateur actif — relevé automatique à {hhmm}")

    def _scheduler_loop():
        while True:
            schedule.run_pending()
            time.sleep(30)

    threading.Thread(target=_scheduler_loop, daemon=True).start()
    app.run(host="0.0.0.0", port=PORT, threaded=True)
