"""
Notification Discord après chaque relevé Airbnb.
Utilise un webhook Discord — aucune dépendance externe.
"""
import json
import logging
import urllib.request
from datetime import datetime

import config as cfg

logger = logging.getLogger(__name__)

# Wine red en décimal pour la couleur de l'embed Discord
_WINE_COLOR = 0x9B2335


def send_scrape_result(checkin: str, checkout: str, count):
    """Envoie un embed Discord avec le résultat du relevé."""
    if not cfg.DISCORD_WEBHOOK_URL:
        return  # Webhook non configuré — silencieux

    try:
        checkin_fmt  = datetime.strptime(checkin,  "%Y-%m-%d").strftime("%d/%m/%Y")
        checkout_fmt = datetime.strptime(checkout, "%Y-%m-%d").strftime("%d/%m/%Y")
        now          = datetime.now().strftime("%d/%m/%Y à %H:%M")

        count_display = str(count) if count is not None else "—"
        description   = (
            f"**{count_display} logement(s)** disponible(s) pour ce week-end."
            if count else
            "⚠️ Impossible de récupérer le nombre de logements."
        )

        payload = {
            "embeds": [{
                "title": "🍷 Relevé Airbnb — Dijon",
                "description": description,
                "color": _WINE_COLOR,
                "fields": [
                    {
                        "name": "📅 Week-end analysé",
                        "value": f"{checkin_fmt} → {checkout_fmt}",
                        "inline": True,
                    },
                    {
                        "name": "🏠 Logements",
                        "value": count_display,
                        "inline": True,
                    },
                    {
                        "name": "🔗 Dashboard",
                        "value": f"[Voir le dashboard]({cfg.PROD_URL})",
                        "inline": False,
                    },
                ],
                "footer": {"text": f"Relevé effectué le {now}"},
            }]
        }

        data = json.dumps(payload).encode("utf-8")
        req  = urllib.request.Request(
            cfg.DISCORD_WEBHOOK_URL,
            data=data,
            headers={"Content-Type": "application/json"},
            method="POST",
        )
        with urllib.request.urlopen(req, timeout=10) as resp:
            if resp.status not in (200, 204):
                logger.warning(f"Discord webhook status inattendu : {resp.status}")

    except Exception as e:
        logger.warning(f"Erreur notification Discord : {e}")
