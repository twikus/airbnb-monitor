"""
Scraper Airbnb avec Playwright.
Extrait le nombre de logements disponibles pour le week-end cible.
"""
import asyncio
import json
import logging
import os
import re
from datetime import datetime
from typing import Optional
from urllib.parse import quote

import config as cfg

logger = logging.getLogger(__name__)


# ---------------------------------------------------------------------------
# Construction de l'URL
# ---------------------------------------------------------------------------

def build_search_url() -> str:
    """Construit l'URL Airbnb avec tous les filtres configurés."""
    base = f"https://www.airbnb.fr/s/{cfg.LOCATION}/homes"

    parts = [
        ("tab_id", "home_tab"),
        ("refinement_paths[]", "/homes"),
        ("date_picker_type", "calendar"),
        ("checkin", cfg.CHECKIN_DATE),
        ("checkout", cfg.CHECKOUT_DATE),
        ("room_types[]", "Entire home/apt"),
        ("ne_lat", str(cfg.NE_LAT)),
        ("ne_lng", str(cfg.NE_LNG)),
        ("sw_lat", str(cfg.SW_LAT)),
        ("sw_lng", str(cfg.SW_LNG)),
        ("zoom_level", str(cfg.ZOOM_LEVEL)),
        ("search_type", "filter_change"),
    ]

    for amenity_id in cfg.AMENITIES:
        parts.append(("amenities[]", str(amenity_id)))

    if cfg.FREE_CANCELLATION:
        parts.append(("flexible_cancellation", "true"))
        parts.append(("cancel_policy_type", "flexible"))

    if cfg.MIN_PRICE is not None:
        parts.append(("price_min", str(cfg.MIN_PRICE)))
    if cfg.MAX_PRICE is not None:
        parts.append(("price_max", str(cfg.MAX_PRICE)))

    qs = "&".join(f"{k}={quote(str(v), safe='')}" for k, v in parts)
    return f"{base}?{qs}"


# ---------------------------------------------------------------------------
# Extraction du nombre de logements
# ---------------------------------------------------------------------------

def _find_count_in_obj(obj, depth: int = 0) -> Optional[int]:
    """Parcourt récursivement un objet JSON pour trouver un compteur."""
    if depth > 8:
        return None
    if isinstance(obj, dict):
        for key in ("totalCount", "total_count", "resultCount", "homes_count"):
            if key in obj and isinstance(obj[key], (int, float)) and obj[key] > 0:
                return int(obj[key])
        for v in obj.values():
            r = _find_count_in_obj(v, depth + 1)
            if r is not None:
                return r
    elif isinstance(obj, list):
        for item in obj[:10]:
            r = _find_count_in_obj(item, depth + 1)
            if r is not None:
                return r
    return None


def _extract_count_from_api(responses: list) -> Optional[int]:
    for data in responses:
        c = _find_count_in_obj(data)
        if c is not None:
            return c
    return None


async def _extract_count_from_html(page) -> Optional[int]:
    """Cherche le texte 'X logements' dans la page."""
    try:
        text = await page.inner_text("body")
        patterns = [
            r"Plus de\s+([\d\s\u00a0]+)\s+logements?",
            r"([\d\s\u00a0]{1,6})\s+logements?",
            r"(\d+)\+?\s+homes?",
        ]
        for pat in patterns:
            m = re.search(pat, text, re.IGNORECASE)
            if m:
                num = re.sub(r"[\s\u00a0]", "", m.group(1))
                if num.isdigit():
                    return int(num)
    except Exception as e:
        logger.debug(f"HTML parse error: {e}")
    return None


async def _count_card_elements(page) -> Optional[int]:
    """Compte les cartes de logement en dernier recours."""
    selectors = [
        '[data-testid="card-container"]',
        '[itemprop="itemListElement"]',
    ]
    for sel in selectors:
        els = await page.query_selector_all(sel)
        if els:
            return len(els)
    return None


# ---------------------------------------------------------------------------
# Filtre "Arrivée autonome" via UI Airbnb
# ---------------------------------------------------------------------------

async def _apply_self_checkin_filter(page, api_data: list):
    """Ouvre le panneau filtres et active 'Arrivée autonome'."""
    try:
        # Chercher et cliquer le bouton "Filtres"
        filter_btn = None
        for sel in [
            'button:has-text("Plus de filtres")',
            'button:has-text("Filtres")',
            '[data-testid="category-bar-filter-button"]',
            '[data-testid="filters-button"]',
        ]:
            filter_btn = await page.query_selector(sel)
            if filter_btn:
                break

        if not filter_btn:
            logger.warning("Bouton 'Filtres' introuvable — filtre arrivée autonome ignoré")
            return

        await filter_btn.click()
        await asyncio.sleep(2)

        # Chercher le toggle "Arrivée autonome"
        toggled = False
        for sel in [
            'div:has-text("Arrivée autonome") input[type="checkbox"]',
            'label:has-text("Arrivée autonome")',
            'button:has-text("Arrivée autonome")',
            'div[data-testid*="self-check-in"] button',
            'div[data-testid*="self_check_in"] button',
        ]:
            el = await page.query_selector(sel)
            if el:
                await el.click()
                await asyncio.sleep(1)
                toggled = True
                logger.info("Toggle 'Arrivée autonome' activé")
                break

        if not toggled:
            logger.warning("Toggle 'Arrivée autonome' introuvable dans le panneau")
            # Fermer le panneau quand même
            for sel in ['button:has-text("Fermer")', '[aria-label="Fermer"]']:
                btn = await page.query_selector(sel)
                if btn:
                    await btn.click()
                    break
            return

        # Valider les filtres
        for sel in [
            'button:has-text("Afficher les logements")',
            'button:has-text("Afficher")',
            'a:has-text("Afficher")',
        ]:
            apply_btn = await page.query_selector(sel)
            if apply_btn:
                await apply_btn.click()
                await asyncio.sleep(4)
                logger.info("Filtres validés avec arrivée autonome")
                return

        logger.warning("Bouton 'Afficher' introuvable après filtre arrivée autonome")

    except Exception as e:
        logger.warning(f"Erreur filtre arrivée autonome: {e}")


# ---------------------------------------------------------------------------
# Scraping principal
# ---------------------------------------------------------------------------

async def scrape() -> dict:
    """Effectue le scraping et retourne un dict avec 'count' et 'url'."""
    from playwright.async_api import async_playwright

    os.makedirs(cfg.SCREENSHOT_DIR, exist_ok=True)
    url = build_search_url()
    logger.info(f"Scraping → {url}")

    async with async_playwright() as p:
        browser = await p.chromium.launch(
            headless=True,
            args=[
                "--no-sandbox",
                "--disable-setuid-sandbox",
                "--disable-blink-features=AutomationControlled",
            ],
        )
        context = await browser.new_context(
            user_agent=(
                "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) "
                "AppleWebKit/537.36 (KHTML, like Gecko) "
                "Chrome/121.0.0.0 Safari/537.36"
            ),
            viewport={"width": 1440, "height": 900},
            locale="fr-FR",
            timezone_id="Europe/Paris",
        )

        # Masquer l'indicateur webdriver
        await context.add_init_script(
            "Object.defineProperty(navigator, 'webdriver', {get: () => undefined})"
        )

        page = await context.new_page()

        # Interception des réponses API
        api_data: list = []

        async def on_response(response):
            u = response.url.lower()
            if any(k in u for k in ["stayspricing", "stayspricingsearch", "stays_search",
                                     "explore_tabs", "api/v3", "graphql"]):
                try:
                    body = await response.text()
                    if any(k in body for k in ['"count"', '"totalCount"', '"homes"']):
                        api_data.append(json.loads(body))
                except Exception:
                    pass

        page.on("response", on_response)

        # Chargement de la page
        try:
            await page.goto(url, wait_until="domcontentloaded", timeout=45_000)
        except Exception as e:
            logger.warning(f"Timeout chargement: {e}")

        await asyncio.sleep(4)

        # Fermer le bandeau cookies s'il est présent
        for selector in [
            'button:has-text("Tout accepter")',
            'button:has-text("Accepter")',
            '[data-testid="accept-btn"]',
        ]:
            try:
                btn = await page.query_selector(selector)
                if btn:
                    await btn.click()
                    await asyncio.sleep(1)
                    break
            except Exception:
                pass

        await asyncio.sleep(3)

        # Appliquer le filtre "Arrivée autonome" via l'UI
        if cfg.SELF_CHECK_IN:
            await _apply_self_checkin_filter(page, api_data)

        # Extraction du compte
        count = _extract_count_from_api(api_data)
        if count is None:
            count = await _extract_count_from_html(page)
        if count is None:
            count = await _count_card_elements(page)

        # Screenshot de vérification
        ts = datetime.now().strftime("%Y%m%d_%H%M%S")
        screenshot_path = os.path.join(cfg.SCREENSHOT_DIR, f"snap_{ts}.png")
        try:
            await page.screenshot(path=screenshot_path, full_page=False)
            logger.info(f"Screenshot: {screenshot_path}")
        except Exception:
            screenshot_path = None

        await browser.close()

    logger.info(f"Résultat: {count} logement(s) trouvé(s)")
    return {
        "count": count,
        "url": url,
        "screenshot": screenshot_path,
        "timestamp": datetime.now().isoformat(),
    }


def run() -> dict:
    """Point d'entrée synchrone."""
    return asyncio.run(scrape())
