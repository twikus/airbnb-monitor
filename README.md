# 🍷 Airbnb Market Analyzer — Dijon

Outil de veille concurrentielle pour un loveroom atypique (jacuzzi, arrivée autonome, annulation gratuite, TV) sur la zone Dijon et sa périphérie.

**Production → [airbnb.axelduquelzar.fr](https://airbnb.axelduquelzar.fr)**

---

## Fonctionnalités

- Suivi quotidien automatique du nombre de logements disponibles sur Airbnb
- Plusieurs week-ends analysés simultanément
- Dashboard HTML interactif avec graphique d'évolution
- Lancement manuel d'un relevé depuis le dashboard
- Accès sécurisé par mot de passe

## Stack

- **Scraper** — Playwright (Chromium headless)
- **Base de données** — SQLite
- **Serveur** — Flask
- **Planificateur** — `schedule` (relevé quotidien à 9h)
- **Déploiement** — Docker + Coolify

## Lancer en local

```bash
pip3 install flask playwright schedule
playwright install chromium
python3 app.py
```

Ouvre `http://localhost:8080` — mot de passe par défaut : `admin`

## Configuration

Édite `config.py` pour changer la zone géographique, les filtres Airbnb ou l'heure du relevé automatique.

## Variables d'environnement (production)

| Variable | Description |
|---|---|
| `ADMIN_PASSWORD` | Mot de passe de connexion |
| `SECRET_KEY` | Clé de session Flask (chaîne aléatoire) |
| `TZ` | Fuseau horaire (ex. `Europe/Paris`) |
