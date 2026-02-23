#!/usr/bin/env bash
# =============================================================================
#  setup.sh — Installation complète du projet Airbnb Market Analyzer
# =============================================================================
set -e

PROJECT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
PYTHON="python3"

echo ""
echo "  🍷 Airbnb Market Analyzer — Installation"
echo "  ==========================================="
echo ""

# 1. Vérifier Python
if ! command -v $PYTHON &>/dev/null; then
  echo "  ❌ Python 3 non trouvé. Installez-le via https://python.org"
  exit 1
fi
echo "  ✅ Python : $($PYTHON --version)"

# 2. Installer les dépendances Python
echo ""
echo "  📦 Installation des dépendances Python…"
$PYTHON -m pip install --quiet --upgrade pip
$PYTHON -m pip install --quiet -r "$PROJECT_DIR/requirements.txt"
echo "  ✅ Dépendances installées"

# 3. Installer le navigateur Playwright (Chromium)
echo ""
echo "  🌐 Installation de Chromium via Playwright…"
$PYTHON -m playwright install chromium
echo "  ✅ Chromium installé"

# 4. Créer le dossier de données
mkdir -p "$PROJECT_DIR/data/screenshots"
echo "  ✅ Dossier data/ créé"

# 5. Proposer la configuration du cron macOS
echo ""
echo "  ⏰ Configuration du planificateur quotidien (cron)…"

HOUR=$(python3 -c "import config; print(config.RUN_HOUR)" 2>/dev/null || echo "9")
MINUTE=$(python3 -c "import config; print(config.RUN_MINUTE)" 2>/dev/null || echo "0")

CRON_JOB="$MINUTE $HOUR * * * cd $PROJECT_DIR && $PYTHON main.py >> $PROJECT_DIR/data/cron.log 2>&1"

echo ""
echo "  La ligne cron suivante sera ajoutée (si elle n'existe pas déjà) :"
echo "  $CRON_JOB"
echo ""
read -p "  Voulez-vous l'ajouter à votre crontab ? [o/N] " REPLY
echo ""

if [[ "$REPLY" =~ ^[Oo]$ ]]; then
  # Éviter les doublons
  (crontab -l 2>/dev/null | grep -v "airbnb\|main.py.*airbnb" ; echo "$CRON_JOB") | crontab -
  echo "  ✅ Cron installé — le scraper tournera chaque jour à ${HOUR}h${MINUTE}"
else
  echo "  ⏩ Cron ignoré. Pour l'ajouter manuellement : crontab -e"
fi

# 6. Premier relevé de test
echo ""
read -p "  Voulez-vous lancer un premier relevé maintenant ? [o/N] " REPLY2
echo ""
if [[ "$REPLY2" =~ ^[Oo]$ ]]; then
  cd "$PROJECT_DIR"
  $PYTHON main.py
fi

echo ""
echo "  ✅ Installation terminée !"
echo ""
echo "  Commandes utiles :"
echo "    python main.py              → un relevé immédiat"
echo "    python main.py --schedule   → planificateur continu"
echo "    open data/dashboard.html    → ouvrir le dashboard"
echo ""
