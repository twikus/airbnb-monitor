# =============================================================================
#  CONFIGURATION - Airbnb Market Analyzer
#  Éditez ce fichier pour personnaliser votre surveillance
# =============================================================================

# -----------------------------------------------------------------------------
# WEEK-END CIBLE À SURVEILLER
# Changer ces dates pour chaque nouveau week-end à analyser
# -----------------------------------------------------------------------------
CHECKIN_DATE  = "2026-03-06"   # Vendredi (arrivée)
CHECKOUT_DATE = "2026-03-08"   # Dimanche (départ)

# -----------------------------------------------------------------------------
# ZONE GÉOGRAPHIQUE — Dijon & périphérie
# Bounding box couvrant : Dijon, Talant, Chenove, Quetigny, Saint-Apollinaire
# Pour ajuster, utilisez : https://boundingbox.klokantech.com/
# -----------------------------------------------------------------------------
LOCATION   = "Dijon--France"   # Slug dans l'URL Airbnb
SW_LAT     = 47.25             # Sud-Ouest latitude
SW_LNG     = 4.95              # Sud-Ouest longitude
NE_LAT     = 47.42             # Nord-Est latitude
NE_LNG     = 5.18              # Nord-Est longitude
ZOOM_LEVEL = 11

# -----------------------------------------------------------------------------
# FILTRES AIRBNB
# Pour trouver les IDs d'amenités : faites une recherche sur airbnb.fr,
# appliquez les filtres manuellement et regardez les paramètres dans l'URL.
# -----------------------------------------------------------------------------
ROOM_TYPE = "Entire home/apt"   # Logement entier uniquement

# Amenités par ID Airbnb
# 25  = Jacuzzi / Bain à remous
# 58  = Télévision
# 8   = Cuisine
# 4   = Wifi
AMENITIES = [25, 58]

SELF_CHECK_IN    = True   # Arrivée autonome
FREE_CANCELLATION = True   # Annulation gratuite

# Prix par nuit (None = pas de filtre)
MIN_PRICE = None
MAX_PRICE = None

# -----------------------------------------------------------------------------
# PLANIFICATION
# -----------------------------------------------------------------------------
RUN_HOUR   = 9    # Heure d'exécution quotidienne (format 24h)
RUN_MINUTE = 0    # Minute

# -----------------------------------------------------------------------------
# SÉCURITÉ
# À définir dans les variables d'environnement Coolify (jamais en dur ici)
# -----------------------------------------------------------------------------
import os
SECRET_KEY     = os.environ.get("SECRET_KEY",     "dev-secret-change-me")
ADMIN_PASSWORD = os.environ.get("ADMIN_PASSWORD", "admin")

# -----------------------------------------------------------------------------
# CHEMINS
# -----------------------------------------------------------------------------
DB_PATH        = "data/airbnb_market.db"
DASHBOARD_PATH = "data/dashboard.html"
LOG_PATH       = "data/scraper.log"
SCREENSHOT_DIR = "data/screenshots"
