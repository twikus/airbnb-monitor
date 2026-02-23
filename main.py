"""
Point d'entrée principal.

Usage :
  python main.py              → un relevé immédiat
  python main.py --schedule   → tourne en continu et scrape chaque jour à l'heure configurée
"""
import argparse
import logging
import os
import sys
import time
from datetime import date, timedelta

import config as cfg
import database as db
import scraper
import dashboard


# ---------------------------------------------------------------------------
# Logging
# ---------------------------------------------------------------------------
os.makedirs("data", exist_ok=True)
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(message)s",
    handlers=[
        logging.StreamHandler(sys.stdout),
        logging.FileHandler(cfg.LOG_PATH, encoding="utf-8"),
    ],
)
logger = logging.getLogger(__name__)


# ---------------------------------------------------------------------------
# Tâche principale
# ---------------------------------------------------------------------------
def run_once():
    logger.info("=" * 60)
    logger.info(f"Relevé Airbnb — {cfg.CHECKIN_DATE} → {cfg.CHECKOUT_DATE}")
    logger.info("=" * 60)

    db.init_db()

    try:
        result = scraper.run()
    except Exception as e:
        logger.error(f"Erreur scraping: {e}", exc_info=True)
        result = {"count": None, "url": scraper.build_search_url(), "screenshot": None}

    snapshot_id = db.insert_snapshot(
        count=result["count"],
        url=result["url"],
        screenshot=result.get("screenshot"),
    )
    logger.info(f"Relevé #{snapshot_id} enregistré → {result['count']} logements")

    dash_path = dashboard.generate()
    logger.info(f"Dashboard mis à jour → {dash_path}")

    # Ouvrir automatiquement le dashboard dans le navigateur
    try:
        import subprocess
        subprocess.Popen(["open", dash_path])
    except Exception:
        pass

    return result


# ---------------------------------------------------------------------------
# Planificateur
# ---------------------------------------------------------------------------
def run_scheduled():
    import schedule

    hhmm = f"{cfg.RUN_HOUR:02d}:{cfg.RUN_MINUTE:02d}"
    logger.info(f"Planificateur actif — exécution quotidienne à {hhmm}")

    schedule.every().day.at(hhmm).do(run_once)

    # Lancer une première fois immédiatement si demandé
    run_once()

    while True:
        schedule.run_pending()
        time.sleep(30)


# ---------------------------------------------------------------------------
# CLI
# ---------------------------------------------------------------------------
def _next_weekend() -> tuple:
    """Calcule le prochain vendredi–dimanche."""
    today = date.today()
    days_to_friday = (4 - today.weekday()) % 7 or 7
    friday = today + timedelta(days=days_to_friday)
    return friday.strftime("%Y-%m-%d"), (friday + timedelta(days=2)).strftime("%Y-%m-%d")


def _validate_date(value: str, label: str) -> str:
    try:
        date.fromisoformat(value)
        return value
    except ValueError:
        print(f"❌ Format de date invalide pour {label} : '{value}' (attendu YYYY-MM-DD)")
        sys.exit(1)


if __name__ == "__main__":
    parser = argparse.ArgumentParser(
        description="Airbnb Market Analyzer — Dijon",
        formatter_class=argparse.RawTextHelpFormatter,
        epilog=(
            "Exemples :\n"
            "  python main.py                                    → week-end depuis config.py\n"
            "  python main.py --next-weekend                     → prochain vendredi–dimanche\n"
            "  python main.py --checkin 2026-03-13 --checkout 2026-03-15\n"
            "  python main.py --next-weekend --schedule          → planificateur sur prochain WE\n"
        ),
    )
    parser.add_argument("--checkin",       type=str,        help="Date d'arrivée  (YYYY-MM-DD)")
    parser.add_argument("--checkout",      type=str,        help="Date de départ  (YYYY-MM-DD)")
    parser.add_argument("--next-weekend",  action="store_true", help="Utiliser le prochain vendredi–dimanche")
    parser.add_argument("--schedule",      action="store_true", help="Tourne en continu (relevé quotidien)")
    args = parser.parse_args()

    # --- Résolution des dates ---
    if args.next_weekend:
        cfg.CHECKIN_DATE, cfg.CHECKOUT_DATE = _next_weekend()
        logger.info(f"Mode 'prochain week-end' → {cfg.CHECKIN_DATE} / {cfg.CHECKOUT_DATE}")
    elif args.checkin or args.checkout:
        if not args.checkin or not args.checkout:
            print("❌ --checkin et --checkout doivent être fournis ensemble.")
            sys.exit(1)
        cfg.CHECKIN_DATE  = _validate_date(args.checkin,  "--checkin")
        cfg.CHECKOUT_DATE = _validate_date(args.checkout, "--checkout")

    if args.schedule:
        run_scheduled()
    else:
        run_once()
