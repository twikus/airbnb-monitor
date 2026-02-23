"""
Point d'entrée production (Docker / Coolify).
Lance en parallèle :
  - un serveur HTTP qui expose le dashboard sur le port 8080
  - le planificateur quotidien du scraper
"""
import http.server
import logging
import os
import schedule
import sys
import threading
import time

import config as cfg
import database as db
import scraper
import dashboard as dash_gen

# Logging stdout (compatible Docker / Coolify logs)
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(message)s",
    handlers=[logging.StreamHandler(sys.stdout)],
)
logger = logging.getLogger(__name__)

PORT = int(os.environ.get("PORT", 8080))


# ---------------------------------------------------------------------------
# Serveur HTTP — expose le dashboard HTML
# ---------------------------------------------------------------------------

class DashboardHandler(http.server.BaseHTTPRequestHandler):

    def do_GET(self):
        # Générer un dashboard vide si pas encore de données
        if not os.path.exists(cfg.DASHBOARD_PATH):
            db.init_db()
            dash_gen.generate()

        try:
            with open(cfg.DASHBOARD_PATH, "rb") as f:
                content = f.read()
            self.send_response(200)
            self.send_header("Content-Type", "text/html; charset=utf-8")
            self.send_header("Content-Length", str(len(content)))
            self.end_headers()
            self.wfile.write(content)
        except Exception as e:
            self.send_error(500, str(e))

    def log_message(self, fmt, *args):
        logger.debug(f"HTTP {self.address_string()} — {fmt % args}")


def _start_http_server():
    server = http.server.HTTPServer(("0.0.0.0", PORT), DashboardHandler)
    logger.info(f"Dashboard accessible sur http://0.0.0.0:{PORT}")
    server.serve_forever()


# ---------------------------------------------------------------------------
# Tâche de scraping
# ---------------------------------------------------------------------------

def run_job():
    logger.info("=" * 50)
    logger.info(f"Relevé — {cfg.CHECKIN_DATE} → {cfg.CHECKOUT_DATE}")
    logger.info("=" * 50)
    db.init_db()
    try:
        result = scraper.run()
    except Exception as e:
        logger.error(f"Erreur scraping: {e}", exc_info=True)
        result = {"count": None, "url": scraper.build_search_url(), "screenshot": None}

    db.insert_snapshot(result["count"], result["url"], result.get("screenshot"))
    dash_gen.generate()
    logger.info(f"✅ {result['count']} logement(s) — dashboard mis à jour")


# ---------------------------------------------------------------------------
# Démarrage
# ---------------------------------------------------------------------------

if __name__ == "__main__":
    os.makedirs("data/screenshots", exist_ok=True)

    # Serveur HTTP en arrière-plan
    threading.Thread(target=_start_http_server, daemon=True).start()

    # Premier relevé dès le démarrage du conteneur
    run_job()

    # Relevés quotidiens automatiques
    hhmm = f"{cfg.RUN_HOUR:02d}:{cfg.RUN_MINUTE:02d}"
    schedule.every().day.at(hhmm).do(run_job)
    logger.info(f"Prochain relevé automatique chaque jour à {hhmm}")

    while True:
        schedule.run_pending()
        time.sleep(30)
