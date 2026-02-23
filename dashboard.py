"""
Génère le dashboard HTML à partir des données SQLite.
Thème : luxe / vin (Burgundy & Gold).
"""
import os
import json
from datetime import datetime
from typing import List

import database as db
import config as cfg


def _trend_arrow(rows) -> str:
    if len(rows) < 2:
        return "—"
    delta = (rows[-1]["listing_count"] or 0) - (rows[-2]["listing_count"] or 0)
    if delta > 0:
        return f"▲ +{delta}"
    elif delta < 0:
        return f"▼ {delta}"
    return "= 0"


def generate() -> str:
    """Génère le fichier dashboard.html et retourne son chemin."""
    rows = db.get_all_snapshots()
    os.makedirs(os.path.dirname(cfg.DASHBOARD_PATH), exist_ok=True)

    counts = [r["listing_count"] for r in rows if r["listing_count"] is not None]
    labels = [r["scraped_at"][:16] for r in rows]  # "YYYY-MM-DD HH:MM"

    current  = counts[-1] if counts else "—"
    minimum  = min(counts) if counts else "—"
    maximum  = max(counts) if counts else "—"
    moyenne  = f"{sum(counts)/len(counts):.1f}" if counts else "—"
    trend    = _trend_arrow(rows)
    updated  = datetime.now().strftime("%d/%m/%Y à %H:%M")

    checkin_fmt  = datetime.strptime(cfg.CHECKIN_DATE, "%Y-%m-%d").strftime("%d/%m/%Y")
    checkout_fmt = datetime.strptime(cfg.CHECKOUT_DATE, "%Y-%m-%d").strftime("%d/%m/%Y")

    chart_labels = json.dumps(labels)
    chart_data   = json.dumps(counts)

    # Lignes du tableau historique (du plus récent au plus ancien)
    table_rows_html = ""
    for r in reversed(rows):
        cnt = r["listing_count"] if r["listing_count"] is not None else "—"
        table_rows_html += (
            "<tr>"
            f"<td>{r['scraped_at'][:10]}</td>"
            f"<td>{r['scraped_at'][11:16]}</td>"
            f"<td class='count-cell'>{cnt}</td>"
            f"<td><a href=\"{r['search_url']}\" target=\"_blank\" class=\"url-link\">Ouvrir ↗</a></td>"
            "</tr>"
        )

    # Bloc tableau pré-calculé (évite les f-strings imbriquées)
    if not rows:
        table_block = "<div class='empty'><strong>Aucun relevé</strong><p>Le premier relevé arrivera bientôt.</p></div>"
    else:
        table_block = (
            "<table><thead><tr>"
            "<th>Date</th><th>Heure</th><th>Logements</th><th>Recherche</th>"
            "</tr></thead>"
            f"<tbody>{table_rows_html}</tbody></table>"
        )

    chart_empty = "<p class='empty'>Pas encore assez de données — revenez demain.</p>" if len(counts) < 2 else ""

    html = f"""<!DOCTYPE html>
<html lang="fr">
<head>
<meta charset="UTF-8">
<meta name="viewport" content="width=device-width, initial-scale=1.0">
<title>Airbnb Market — Dijon</title>
<script src="https://cdn.jsdelivr.net/npm/chart.js@4.4.0/dist/chart.umd.min.js"></script>
<style>
  :root {{
    --bg:       #12080d;
    --surface:  #1e0f18;
    --card:     #2a1422;
    --border:   #5c2d3a;
    --wine:     #9b2335;
    --gold:     #c9a84c;
    --gold-lt:  #e8cc7a;
    --cream:    #f5f0e8;
    --muted:    #9e8a90;
    --up:       #4ade80;
    --down:     #f87171;
    --radius:   12px;
    --font:     'Georgia', serif;
  }}
  * {{ box-sizing: border-box; margin: 0; padding: 0; }}
  body {{
    background: var(--bg);
    color: var(--cream);
    font-family: 'Segoe UI', system-ui, sans-serif;
    min-height: 100vh;
    padding: 0 0 60px 0;
  }}

  /* ── HEADER ── */
  header {{
    background: linear-gradient(135deg, #1e0f18 0%, #3a1428 50%, #1e0f18 100%);
    border-bottom: 1px solid var(--border);
    padding: 32px 40px 28px;
    display: flex;
    align-items: center;
    justify-content: space-between;
    gap: 20px;
    flex-wrap: wrap;
  }}
  .header-left h1 {{
    font-family: var(--font);
    font-size: 1.9rem;
    color: var(--gold-lt);
    letter-spacing: .5px;
  }}
  .header-left p {{
    color: var(--muted);
    font-size: .9rem;
    margin-top: 4px;
  }}
  .header-left .weekend-badge {{
    display: inline-block;
    margin-top: 10px;
    background: var(--wine);
    color: var(--cream);
    padding: 4px 14px;
    border-radius: 20px;
    font-size: .82rem;
    letter-spacing: .4px;
  }}
  .updated {{
    text-align: right;
    font-size: .8rem;
    color: var(--muted);
    line-height: 1.6;
  }}
  .updated strong {{ color: var(--gold); }}

  /* ── MAIN LAYOUT ── */
  main {{ max-width: 1100px; margin: 0 auto; padding: 36px 24px 0; }}

  /* ── STAT CARDS ── */
  .stats-grid {{
    display: grid;
    grid-template-columns: repeat(auto-fit, minmax(190px, 1fr));
    gap: 16px;
    margin-bottom: 32px;
  }}
  .stat-card {{
    background: var(--card);
    border: 1px solid var(--border);
    border-radius: var(--radius);
    padding: 22px 24px;
    position: relative;
    overflow: hidden;
  }}
  .stat-card::before {{
    content: '';
    position: absolute;
    top: 0; left: 0; right: 0;
    height: 3px;
    background: linear-gradient(90deg, var(--wine), var(--gold));
  }}
  .stat-label {{
    font-size: .75rem;
    text-transform: uppercase;
    letter-spacing: 1px;
    color: var(--muted);
    margin-bottom: 8px;
  }}
  .stat-value {{
    font-size: 2.4rem;
    font-family: var(--font);
    color: var(--gold-lt);
    font-weight: bold;
  }}
  .stat-sub {{
    font-size: .75rem;
    color: var(--muted);
    margin-top: 4px;
  }}
  .trend-up   {{ color: var(--up) !important; }}
  .trend-down {{ color: var(--down) !important; }}

  /* ── CHART ── */
  .chart-card {{
    background: var(--card);
    border: 1px solid var(--border);
    border-radius: var(--radius);
    padding: 28px 28px 20px;
    margin-bottom: 28px;
  }}
  .chart-card h2 {{
    font-family: var(--font);
    font-size: 1.05rem;
    color: var(--gold);
    margin-bottom: 20px;
    letter-spacing: .3px;
  }}
  .chart-wrapper {{ position: relative; height: 300px; }}

  /* ── TABLE ── */
  .table-card {{
    background: var(--card);
    border: 1px solid var(--border);
    border-radius: var(--radius);
    padding: 28px 28px 12px;
    overflow-x: auto;
  }}
  .table-card h2 {{
    font-family: var(--font);
    font-size: 1.05rem;
    color: var(--gold);
    margin-bottom: 20px;
    letter-spacing: .3px;
  }}
  table {{
    width: 100%;
    border-collapse: collapse;
    font-size: .88rem;
  }}
  thead tr {{
    border-bottom: 1px solid var(--border);
  }}
  th {{
    text-align: left;
    padding: 8px 16px 12px;
    color: var(--muted);
    font-weight: 600;
    font-size: .75rem;
    text-transform: uppercase;
    letter-spacing: .8px;
  }}
  td {{
    padding: 12px 16px;
    border-bottom: 1px solid #2e1820;
    color: var(--cream);
  }}
  tr:last-child td {{ border-bottom: none; }}
  tr:hover td {{ background: #33182600; }}
  .count-cell {{
    font-family: var(--font);
    font-size: 1.1rem;
    color: var(--gold-lt);
    font-weight: bold;
  }}
  .url-link {{
    color: var(--wine);
    text-decoration: none;
    font-size: .82rem;
  }}
  .url-link:hover {{ color: var(--gold); text-decoration: underline; }}

  /* ── FILTERS BADGE ── */
  .filters-row {{
    display: flex;
    flex-wrap: wrap;
    gap: 8px;
    margin-bottom: 28px;
  }}
  .filter-tag {{
    background: #3a1428;
    border: 1px solid var(--border);
    border-radius: 20px;
    padding: 4px 14px;
    font-size: .78rem;
    color: var(--muted);
  }}
  .filter-tag span {{ color: var(--gold); }}

  /* ── EMPTY STATE ── */
  .empty {{ text-align: center; padding: 60px 20px; color: var(--muted); }}
  .empty p {{ margin-top: 10px; font-size: .9rem; }}

  /* ── CONTROL PANEL ── */
  .control-panel {{
    background: var(--card);
    border: 1px solid var(--border);
    border-radius: var(--radius);
    padding: 20px 24px;
    margin-bottom: 28px;
    display: flex;
    align-items: flex-end;
    gap: 32px;
    flex-wrap: wrap;
  }}
  .cp-group label {{
    display: block;
    font-size: .72rem;
    text-transform: uppercase;
    letter-spacing: 1px;
    color: var(--muted);
    margin-bottom: 8px;
  }}
  .cp-row {{ display: flex; align-items: center; gap: 10px; flex-wrap: wrap; }}
  .cp-sep {{ width: 1px; height: 44px; background: var(--border); align-self: center; }}
  input[type="date"] {{
    background: var(--surface);
    border: 1px solid var(--border);
    border-radius: 8px;
    padding: 8px 12px;
    color: var(--cream);
    font-size: .9rem;
    cursor: pointer;
    appearance: none;
  }}
  input[type="date"]::-webkit-calendar-picker-indicator {{ filter: invert(.6); cursor: pointer; }}
  .btn {{
    border: none;
    border-radius: 8px;
    padding: 9px 18px;
    font-size: .88rem;
    cursor: pointer;
    transition: opacity .2s;
    white-space: nowrap;
  }}
  .btn:hover  {{ opacity: .85; }}
  .btn:disabled {{ opacity: .4; cursor: not-allowed; }}
  .btn-wine  {{ background: var(--wine);  color: var(--cream); }}
  .btn-gold  {{ background: transparent; border: 1px solid var(--gold); color: var(--gold); }}
  .cp-status {{
    font-size: .82rem;
    color: var(--muted);
    min-width: 160px;
  }}
  .cp-status.running {{ color: var(--gold); }}
  .cp-status.success {{ color: var(--up); }}
</style>
</head>
<body>

<header>
  <div class="header-left">
    <h1>🍷 Airbnb Market — Dijon</h1>
    <p>Loveroom atypique · Jacuzzi · Luxe · Arrivée autonome</p>
    <span class="weekend-badge">Week-end cible : {checkin_fmt} → {checkout_fmt}</span>
  </div>
  <div class="updated">
    Dernière mise à jour<br>
    <strong>{updated}</strong>
  </div>
</header>

<main>

  <!-- PANNEAU DE CONTRÔLE -->
  <div class="control-panel">
    <div class="cp-group">
      <label>Week-end analysé</label>
      <div class="cp-row">
        <input type="date" id="checkin-input"  value="{cfg.CHECKIN_DATE}">
        <span style="color:var(--muted)">→</span>
        <input type="date" id="checkout-input" value="{cfg.CHECKOUT_DATE}">
        <button class="btn btn-gold" onclick="updateDates()">Appliquer</button>
      </div>
    </div>
    <div class="cp-sep"></div>
    <div class="cp-group">
      <label>Analyse manuelle</label>
      <div class="cp-row">
        <button class="btn btn-wine" id="scrape-btn" onclick="launchScrape()">🔍 Lancer l'analyse</button>
        <span class="cp-status" id="cp-status"></span>
      </div>
    </div>
  </div>

  <!-- FILTRES ACTIFS -->
  <div class="filters-row">
    <div class="filter-tag">📍 <span>Dijon & périphérie</span></div>
    <div class="filter-tag">🏠 <span>Logement entier</span></div>
    <div class="filter-tag">🛁 <span>Jacuzzi</span></div>
    <div class="filter-tag">📺 <span>Télévision</span></div>
    <div class="filter-tag">🔑 <span>Arrivée autonome</span></div>
    <div class="filter-tag">✅ <span>Annulation gratuite</span></div>
  </div>

  <!-- STATISTIQUES -->
  <div class="stats-grid">
    <div class="stat-card">
      <div class="stat-label">Aujourd'hui</div>
      <div class="stat-value">{current}</div>
      <div class="stat-sub">logements disponibles</div>
    </div>
    <div class="stat-card">
      <div class="stat-label">Minimum observé</div>
      <div class="stat-value">{minimum}</div>
      <div class="stat-sub">sur toute la période</div>
    </div>
    <div class="stat-card">
      <div class="stat-label">Maximum observé</div>
      <div class="stat-value">{maximum}</div>
      <div class="stat-sub">sur toute la période</div>
    </div>
    <div class="stat-card">
      <div class="stat-label">Moyenne</div>
      <div class="stat-value">{moyenne}</div>
      <div class="stat-sub">logements / relevé</div>
    </div>
    <div class="stat-card">
      <div class="stat-label">Tendance</div>
      <div class="stat-value" style="font-size:1.5rem">{trend}</div>
      <div class="stat-sub">vs relevé précédent</div>
    </div>
  </div>

  <!-- GRAPHIQUE -->
  <div class="chart-card">
    <h2>📈 Évolution du nombre de logements disponibles</h2>
    {chart_empty}
    <div class="chart-wrapper">
      <canvas id="chart"></canvas>
    </div>
  </div>

  <!-- TABLEAU HISTORIQUE -->
  <div class="table-card">
    <h2>🗂 Historique des relevés</h2>
    {table_block}
  </div>

</main>

<script>
const labels = {chart_labels};
const data   = {chart_data};

if (labels.length >= 1) {{
  const ctx = document.getElementById('chart').getContext('2d');
  new Chart(ctx, {{
    type: 'line',
    data: {{
      labels,
      datasets: [{{
        label: 'Logements disponibles',
        data,
        borderColor: '#c9a84c',
        backgroundColor: 'rgba(201,168,76,0.10)',
        borderWidth: 2.5,
        pointBackgroundColor: '#c9a84c',
        pointRadius: 5,
        pointHoverRadius: 7,
        tension: 0.35,
        fill: true,
      }}]
    }},
    options: {{
      responsive: true,
      maintainAspectRatio: false,
      plugins: {{
        legend: {{ display: false }},
        tooltip: {{
          backgroundColor: '#2a1422',
          borderColor: '#5c2d3a',
          borderWidth: 1,
          titleColor: '#e8cc7a',
          bodyColor: '#f5f0e8',
          callbacks: {{
            label: ctx => ` ${{ctx.parsed.y}} logements`
          }}
        }}
      }},
      scales: {{
        x: {{
          ticks: {{ color: '#9e8a90', font: {{ size: 11 }} }},
          grid:  {{ color: '#2e1820' }},
        }},
        y: {{
          ticks: {{
            color: '#9e8a90',
            stepSize: 1,
            callback: v => Number.isInteger(v) ? v : null
          }},
          grid: {{ color: '#2e1820' }},
          beginAtZero: true,
        }}
      }}
    }}
  }});
}}

// ── Panneau de contrôle ───────────────────────────────────────────────────

window.addEventListener('load', () => {{
  fetch('/api/status')
    .then(r => r.json())
    .then(d => {{ if (d.running) {{ setScraping(true); pollStatus(); }} }})
    .catch(() => {{}});
}});

function setScraping(on) {{
  const btn = document.getElementById('scrape-btn');
  const msg = document.getElementById('cp-status');
  if (on) {{
    btn.disabled    = true;
    btn.textContent = '⏳ En cours…';
    msg.textContent = 'Récupération des données Airbnb…';
    msg.className   = 'cp-status running';
  }} else {{
    btn.disabled    = false;
    btn.textContent = '🔍 Lancer l\'analyse';
    msg.textContent = '';
    msg.className   = 'cp-status';
  }}
}}

async function launchScrape() {{
  try {{
    const res = await fetch('/api/scrape', {{ method: 'POST' }});
    const d   = await res.json();
    if (d.status === 'started' || d.status === 'already_running') {{
      setScraping(true);
      pollStatus();
    }}
  }} catch(e) {{
    document.getElementById('cp-status').textContent = '⚠ Erreur de connexion';
  }}
}}

function pollStatus() {{
  const timer = setInterval(async () => {{
    try {{
      const d = await (await fetch('/api/status')).json();
      if (!d.running) {{ clearInterval(timer); window.location.reload(); }}
    }} catch(e) {{ clearInterval(timer); setScraping(false); }}
  }}, 3000);
}}

async function updateDates() {{
  const checkin  = document.getElementById('checkin-input').value;
  const checkout = document.getElementById('checkout-input').value;
  if (!checkin || !checkout)  {{ alert('Renseignez les deux dates.'); return; }}
  if (checkin >= checkout)    {{ alert("L'arrivée doit être avant le départ."); return; }}
  try {{
    const res = await fetch('/api/dates', {{
      method:  'POST',
      headers: {{ 'Content-Type': 'application/json' }},
      body:    JSON.stringify({{ checkin, checkout }})
    }});
    if (res.ok) window.location.reload();
    else        alert('Erreur mise à jour dates.');
  }} catch(e) {{ alert('Erreur de connexion.'); }}
}}
</script>

</body>
</html>"""

    with open(cfg.DASHBOARD_PATH, "w", encoding="utf-8") as f:
        f.write(html)

    return cfg.DASHBOARD_PATH
