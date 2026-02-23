"""
Génère le dashboard HTML multi-analyses.
Thème : luxe / vin (Burgundy & Gold).
"""
import json
import os
from datetime import date, datetime

import database as db
import config as cfg


def _fmt_date(d: str) -> str:
    months = ["jan","fév","mar","avr","mai","jun","jul","aoû","sep","oct","nov","déc"]
    dt = datetime.strptime(d, "%Y-%m-%d")
    return f"{dt.day} {months[dt.month - 1]} {dt.year}"


def _days_until(checkin: str) -> str:
    delta = (date.fromisoformat(checkin) - date.today()).days
    if delta > 1:  return f"Dans {delta} j"
    if delta == 1: return "Demain"
    if delta == 0: return "Aujourd'hui"
    return f"Il y a {-delta} j"


def _trend(counts: list) -> str:
    if len(counts) < 2: return "—"
    delta = counts[-1] - counts[-2]
    if delta > 0: return f"▲ +{delta}"
    if delta < 0: return f"▼ {delta}"
    return "= 0"


def generate() -> str:
    analyses = db.get_all_analyses()
    os.makedirs(os.path.dirname(cfg.DASHBOARD_PATH), exist_ok=True)
    updated = datetime.now().strftime("%d/%m/%Y à %H:%M")

    # ── Données par analyse ──────────────────────────────────────────────────
    all_data = {}   # injecté en JS
    cards_html = ""

    for a in analyses:
        aid      = a["id"]
        checkin  = a["checkin"]
        checkout = a["checkout"]
        rows     = db.get_snapshots_for_analysis(checkin, checkout)

        counts = [r["listing_count"] for r in rows if r["listing_count"] is not None]
        labels = [r["scraped_at"][:16] for r in rows if r["listing_count"] is not None]

        latest  = counts[-1] if counts else None
        minimum = min(counts) if counts else None
        maximum = max(counts) if counts else None
        avg     = round(sum(counts) / len(counts), 1) if counts else None
        trend   = _trend(counts)
        days    = _days_until(checkin)

        snapshots_js = [
            {
                "date":  r["scraped_at"][:10],
                "time":  r["scraped_at"][11:16],
                "count": r["listing_count"],
                "url":   r["search_url"] or "",
            }
            for r in reversed(rows)
        ]

        all_data[aid] = {
            "checkin":   checkin,
            "checkout":  checkout,
            "labels":    labels,
            "counts":    counts,
            "min":       minimum,
            "max":       maximum,
            "avg":       avg,
            "trend":     trend,
            "snapshots": snapshots_js,
        }

        count_display = str(latest) if latest is not None else "—"
        trend_cls     = "trend-up" if "▲" in trend else ("trend-down" if "▼" in trend else "")
        total_snaps   = a["total_snapshots"] or 0

        cards_html += (
            f'<div class="analysis-card" id="card-{aid}" onclick="selectAnalysis({aid})">'
            f'  <div class="ac-header">'
            f'    <div class="ac-dates">{_fmt_date(checkin)} → {_fmt_date(checkout)}</div>'
            f'    <div class="ac-actions" onclick="event.stopPropagation()">'
            f'      <button class="ac-btn" id="scrape-btn-{aid}" title="Lancer l\'analyse"'
            f'              onclick="launchScrape({aid}, \'{checkin}\', \'{checkout}\')">🔍</button>'
            f'      <button class="ac-btn ac-btn-danger" id="delete-btn-{aid}" title="Supprimer"'
            f'              onclick="deleteAnalysis(event, {aid})">🗑</button>'
            f'    </div>'
            f'  </div>'
            f'  <div class="ac-count">{count_display}</div>'
            f'  <div class="ac-label">logements disponibles</div>'
            f'  <div class="ac-meta">{days} &nbsp;·&nbsp; {total_snaps} relevé(s)</div>'
            f'  <div class="ac-trend {trend_cls}">{trend}</div>'
            f'</div>'
        )

    if not analyses:
        cards_html = "<p class='no-analysis'>Aucune analyse active. Ajoutez un week-end ci-dessus.</p>"

    analyses_json = json.dumps(all_data)

    html = f"""<!DOCTYPE html>
<html lang="fr">
<head>
<meta charset="UTF-8">
<meta name="viewport" content="width=device-width, initial-scale=1.0">
<title>Airbnb Market — Dijon</title>
<script src="https://cdn.jsdelivr.net/npm/chart.js@4.4.0/dist/chart.umd.min.js"></script>
<style>
  :root {{
    --bg:      #12080d; --surface: #1e0f18; --card: #2a1422;
    --border:  #5c2d3a; --wine:    #9b2335; --gold: #c9a84c;
    --gold-lt: #e8cc7a; --cream:   #f5f0e8; --muted: #9e8a90;
    --up: #4ade80; --down: #f87171; --radius: 12px;
  }}
  * {{ box-sizing: border-box; margin: 0; padding: 0; }}
  body {{ background: var(--bg); color: var(--cream); font-family: 'Segoe UI', system-ui, sans-serif; min-height: 100vh; padding-bottom: 60px; }}

  /* HEADER */
  header {{
    background: linear-gradient(135deg, #1e0f18 0%, #3a1428 50%, #1e0f18 100%);
    border-bottom: 1px solid var(--border);
    padding: 26px 40px 22px;
    display: flex; align-items: center; justify-content: space-between; flex-wrap: wrap; gap: 16px;
  }}
  .h-title {{ font-family: Georgia, serif; font-size: 1.75rem; color: var(--gold-lt); }}
  .h-sub   {{ color: var(--muted); font-size: .83rem; margin-top: 4px; }}
  .h-upd   {{ font-size: .78rem; color: var(--muted); text-align: right; line-height: 1.6; }}
  .h-upd strong {{ color: var(--gold); }}

  main {{ max-width: 1100px; margin: 0 auto; padding: 28px 24px 0; }}

  /* ADD PANEL */
  .add-panel {{
    background: var(--card); border: 1px solid var(--border); border-radius: var(--radius);
    padding: 16px 22px; display: flex; align-items: center; gap: 14px; flex-wrap: wrap; margin-bottom: 22px;
  }}
  .add-panel .ap-label {{ font-size: .73rem; text-transform: uppercase; letter-spacing: 1px; color: var(--muted); white-space: nowrap; }}
  .add-sep {{ width: 1px; height: 30px; background: var(--border); }}
  .add-status {{ font-size: .82rem; color: var(--muted); }}
  .add-status.error   {{ color: var(--down); }}
  .add-status.running {{ color: var(--gold); }}

  input[type="date"] {{
    background: var(--surface); border: 1px solid var(--border); border-radius: 8px;
    padding: 7px 12px; color: var(--cream); font-size: .87rem; cursor: pointer;
  }}
  input[type="date"]::-webkit-calendar-picker-indicator {{ filter: invert(.6); cursor: pointer; }}

  .btn {{
    border: none; border-radius: 8px; padding: 8px 18px; font-size: .86rem;
    cursor: pointer; transition: opacity .2s; white-space: nowrap;
  }}
  .btn:hover    {{ opacity: .85; }}
  .btn:disabled {{ opacity: .35; cursor: not-allowed; }}
  .btn-wine {{ background: var(--wine); color: var(--cream); }}
  .btn-gold {{ background: transparent; border: 1px solid var(--gold); color: var(--gold); }}

  /* ANALYSES GRID */
  .analyses-grid {{
    display: grid; grid-template-columns: repeat(auto-fill, minmax(230px, 1fr)); gap: 14px; margin-bottom: 26px;
  }}
  .analysis-card {{
    background: var(--card); border: 2px solid var(--border); border-radius: var(--radius);
    padding: 18px; cursor: pointer; transition: border-color .2s, transform .15s;
    position: relative; overflow: hidden;
  }}
  .analysis-card::before {{
    content: ''; position: absolute; top: 0; left: 0; right: 0; height: 3px;
    background: linear-gradient(90deg, var(--wine), var(--gold));
  }}
  .analysis-card:hover   {{ border-color: var(--gold); transform: translateY(-2px); }}
  .analysis-card.active  {{ border-color: var(--gold); background: #331824; }}
  .analysis-card.scraping {{ border-color: var(--gold-lt); animation: pulse 1.5s infinite; }}
  @keyframes pulse {{ 0%,100% {{ border-color: var(--gold-lt); }} 50% {{ border-color: var(--wine); }} }}

  .ac-header {{ display: flex; justify-content: space-between; align-items: flex-start; margin-bottom: 10px; }}
  .ac-dates  {{ font-size: .8rem; color: var(--gold); font-weight: 600; }}
  .ac-actions {{ display: flex; gap: 5px; }}
  .ac-btn {{
    background: none; border: 1px solid var(--border); border-radius: 6px;
    padding: 3px 7px; font-size: .8rem; cursor: pointer; color: var(--muted); transition: all .15s;
  }}
  .ac-btn:hover         {{ border-color: var(--gold); color: var(--gold); }}
  .ac-btn:disabled      {{ opacity: .3; cursor: not-allowed; }}
  .ac-btn-danger:hover  {{ border-color: var(--down); color: var(--down); }}
  .ac-count {{ font-family: Georgia, serif; font-size: 2.5rem; color: var(--gold-lt); font-weight: bold; line-height: 1; margin: 8px 0 3px; }}
  .ac-label {{ font-size: .72rem; color: var(--muted); margin-bottom: 8px; }}
  .ac-meta  {{ font-size: .72rem; color: var(--muted); }}
  .ac-trend {{ font-size: .8rem; margin-top: 6px; color: var(--muted); }}
  .trend-up   {{ color: var(--up)   !important; }}
  .trend-down {{ color: var(--down) !important; }}
  .no-analysis {{ text-align: center; padding: 40px; color: var(--muted); font-size: .9rem; }}

  /* DETAIL */
  #detail-section {{
    background: var(--surface); border: 1px solid var(--border); border-radius: var(--radius);
    padding: 26px; margin-bottom: 28px;
  }}
  .detail-header {{
    display: flex; justify-content: space-between; align-items: center;
    margin-bottom: 22px; flex-wrap: wrap; gap: 12px;
  }}
  .detail-header h2 {{ font-family: Georgia, serif; color: var(--gold-lt); font-size: 1.15rem; }}
  .btn-close {{
    background: none; border: 1px solid var(--border); border-radius: 8px;
    padding: 5px 14px; color: var(--muted); cursor: pointer; font-size: .82rem; transition: all .15s;
  }}
  .btn-close:hover {{ color: var(--cream); border-color: var(--muted); }}

  /* STATS */
  .stats-grid {{ display: grid; grid-template-columns: repeat(auto-fit, minmax(140px, 1fr)); gap: 12px; margin-bottom: 22px; }}
  .stat-card {{
    background: var(--card); border: 1px solid var(--border); border-radius: 10px;
    padding: 14px 16px; position: relative; overflow: hidden;
  }}
  .stat-card::before {{
    content: ''; position: absolute; top: 0; left: 0; right: 0; height: 2px;
    background: linear-gradient(90deg, var(--wine), var(--gold));
  }}
  .stat-label {{ font-size: .68rem; text-transform: uppercase; letter-spacing: 1px; color: var(--muted); margin-bottom: 5px; }}
  .stat-value {{ font-family: Georgia, serif; font-size: 1.9rem; color: var(--gold-lt); font-weight: bold; }}
  .stat-sub   {{ font-size: .68rem; color: var(--muted); margin-top: 2px; }}

  /* CHART */
  .chart-wrap {{ position: relative; height: 260px; margin-bottom: 22px; }}

  /* TABLE */
  table {{ width: 100%; border-collapse: collapse; font-size: .85rem; }}
  th {{ text-align: left; padding: 7px 14px 9px; color: var(--muted); font-size: .7rem; text-transform: uppercase; letter-spacing: .8px; border-bottom: 1px solid var(--border); }}
  td {{ padding: 10px 14px; border-bottom: 1px solid #2e1820; color: var(--cream); }}
  tr:last-child td {{ border-bottom: none; }}
  .td-count {{ font-family: Georgia, serif; font-size: 1.05rem; color: var(--gold-lt); font-weight: bold; }}
  .td-link  {{ color: var(--wine); text-decoration: none; font-size: .8rem; }}
  .td-link:hover {{ color: var(--gold); }}
</style>
</head>
<body>

<header>
  <div>
    <div class="h-title">🍷 Airbnb Market — Dijon</div>
    <div class="h-sub">Loveroom atypique · Jacuzzi · Luxe · Arrivée autonome</div>
  </div>
  <div class="h-upd">Dernière mise à jour<br><strong>{updated}</strong></div>
</header>

<main>

  <!-- AJOUTER UNE ANALYSE -->
  <div class="add-panel">
    <span class="ap-label">Nouvelle analyse</span>
    <input type="date" id="new-checkin">
    <span style="color:var(--muted)">→</span>
    <input type="date" id="new-checkout">
    <button class="btn btn-wine" id="add-btn" onclick="addAnalysis()">+ Ajouter</button>
    <div class="add-sep"></div>
    <span class="add-status" id="add-status"></span>
  </div>

  <!-- CARTES ANALYSES -->
  <div class="analyses-grid">
    {cards_html}
  </div>

  <!-- DÉTAIL (affiché au clic sur une carte) -->
  <div id="detail-section" style="display:none">
    <div class="detail-header">
      <h2 id="detail-title"></h2>
      <button class="btn-close" onclick="closeDetail()">✕ Fermer</button>
    </div>
    <div class="stats-grid" id="detail-stats"></div>
    <div class="chart-wrap"><canvas id="chart"></canvas></div>
    <table>
      <thead><tr><th>Date</th><th>Heure</th><th>Logements</th><th>Lien</th></tr></thead>
      <tbody id="detail-table"></tbody>
    </table>
  </div>

</main>

<script>
const ANALYSES_DATA = {analyses_json};
let chart = null;
let selectedId = null;

// Init : vérifier si un scrape est déjà en cours
window.addEventListener('load', () => {{
  fetch('/api/status')
    .then(r => r.json())
    .then(d => {{ if (d.running) {{ setScrapingUI(d.analysis_id, true); pollStatus(); }} }})
    .catch(() => {{}});
  // Auto-sélectionner la première analyse
  const ids = Object.keys(ANALYSES_DATA);
  if (ids.length) selectAnalysis(parseInt(ids[0]));
}});

// ── Sélection ─────────────────────────────────────────────────────────────────
function selectAnalysis(id) {{
  selectedId = id;
  const d = ANALYSES_DATA[id];
  if (!d) return;

  document.querySelectorAll('.analysis-card').forEach(c => c.classList.remove('active'));
  const card = document.getElementById('card-' + id);
  if (card) card.classList.add('active');

  document.getElementById('detail-title').textContent =
    'Évolution — ' + fmtDate(d.checkin) + ' → ' + fmtDate(d.checkout);

  const cur = d.counts.length ? d.counts[d.counts.length - 1] : '—';
  document.getElementById('detail-stats').innerHTML =
    statCard("Aujourd'hui", cur,   "logements") +
    statCard("Minimum",     d.min !== null ? d.min : '—', "observé") +
    statCard("Maximum",     d.max !== null ? d.max : '—', "observé") +
    statCard("Moyenne",     d.avg !== null ? d.avg : '—', "par relevé") +
    statCard("Tendance",    d.trend, "vs précédent", "1.2rem");

  if (chart) chart.destroy();
  chart = new Chart(document.getElementById('chart').getContext('2d'), {{
    type: 'line',
    data: {{
      labels: d.labels,
      datasets: [{{
        label: 'Logements', data: d.counts,
        borderColor: '#c9a84c', backgroundColor: 'rgba(201,168,76,.10)',
        borderWidth: 2.5, pointBackgroundColor: '#c9a84c', pointRadius: 5, tension: 0.35, fill: true,
      }}]
    }},
    options: {{
      responsive: true, maintainAspectRatio: false,
      plugins: {{
        legend: {{ display: false }},
        tooltip: {{ backgroundColor: '#2a1422', borderColor: '#5c2d3a', borderWidth: 1,
                    titleColor: '#e8cc7a', bodyColor: '#f5f0e8',
                    callbacks: {{ label: c => ` ${{c.parsed.y}} logements` }} }}
      }},
      scales: {{
        x: {{ ticks: {{ color: '#9e8a90', font: {{ size: 10 }} }}, grid: {{ color: '#2e1820' }} }},
        y: {{ ticks: {{ color: '#9e8a90', stepSize: 1, callback: v => Number.isInteger(v) ? v : null }},
              grid: {{ color: '#2e1820' }}, beginAtZero: true }}
      }}
    }}
  }});

  const tbody = document.getElementById('detail-table');
  if (!d.snapshots.length) {{
    tbody.innerHTML = '<tr><td colspan="4" style="text-align:center;color:var(--muted);padding:24px">Aucun relevé pour cette analyse.</td></tr>';
  }} else {{
    tbody.innerHTML = d.snapshots.map(s =>
      '<tr>' +
      '<td>' + s.date + '</td>' +
      '<td>' + s.time + '</td>' +
      '<td class="td-count">' + (s.count !== null ? s.count : '—') + '</td>' +
      '<td><a href="' + s.url + '" target="_blank" class="td-link">Ouvrir ↗</a></td>' +
      '</tr>'
    ).join('');
  }}

  document.getElementById('detail-section').style.display = 'block';
  document.getElementById('detail-section').scrollIntoView({{ behavior: 'smooth', block: 'start' }});
}}

function closeDetail() {{
  document.getElementById('detail-section').style.display = 'none';
  document.querySelectorAll('.analysis-card').forEach(c => c.classList.remove('active'));
  if (chart) {{ chart.destroy(); chart = null; }}
  selectedId = null;
}}

// ── Ajouter une analyse ───────────────────────────────────────────────────────
async function addAnalysis() {{
  const checkin  = document.getElementById('new-checkin').value;
  const checkout = document.getElementById('new-checkout').value;
  const status   = document.getElementById('add-status');
  if (!checkin || !checkout) {{ setAddStatus("⚠ Renseignez les deux dates.", 'error'); return; }}
  if (checkin >= checkout)   {{ setAddStatus("⚠ L'arrivée doit être avant le départ.", 'error'); return; }}

  document.getElementById('add-btn').disabled = true;
  setAddStatus('', '');
  try {{
    const res = await fetch('/api/analyses', {{
      method: 'POST', headers: {{ 'Content-Type': 'application/json' }},
      body: JSON.stringify({{ checkin, checkout }})
    }});
    const d = await res.json();
    if (!res.ok) {{ setAddStatus('⚠ ' + (d.error || 'Erreur'), 'error'); }}
    else          {{ window.location.reload(); }}
  }} catch(e) {{ setAddStatus('⚠ Erreur de connexion.', 'error'); }}
  finally    {{ document.getElementById('add-btn').disabled = false; }}
}}

// ── Supprimer une analyse ─────────────────────────────────────────────────────
async function deleteAnalysis(event, id) {{
  event.stopPropagation();
  if (!confirm('Supprimer cette analyse et tous ses relevés ?')) return;
  try {{
    const res = await fetch('/api/analyses/' + id, {{ method: 'DELETE' }});
    const d   = await res.json();
    if (!res.ok) {{ alert(d.error || 'Erreur lors de la suppression.'); return; }}
    window.location.reload();
  }} catch(e) {{ alert('Erreur de connexion.'); }}
}}

// ── Lancer un scraping ────────────────────────────────────────────────────────
async function launchScrape(id, checkin, checkout) {{
  try {{
    const res = await fetch('/api/scrape', {{
      method: 'POST', headers: {{ 'Content-Type': 'application/json' }},
      body: JSON.stringify({{ analysis_id: id, checkin, checkout }})
    }});
    const d = await res.json();
    if (d.status === 'already_running') {{
      setAddStatus('⏳ Une analyse est déjà en cours.', 'running'); return;
    }}
    if (res.ok) {{ setScrapingUI(id, true); pollStatus(); }}
  }} catch(e) {{ setAddStatus('⚠ Erreur de connexion.', 'error'); }}
}}

// ── Polling ───────────────────────────────────────────────────────────────────
function pollStatus() {{
  const timer = setInterval(async () => {{
    try {{
      const d = await (await fetch('/api/status')).json();
      if (!d.running) {{ clearInterval(timer); window.location.reload(); }}
    }} catch(e) {{ clearInterval(timer); setScrapingUI(null, false); }}
  }}, 3000);
}}

function setScrapingUI(analysisId, on) {{
  document.querySelectorAll('[id^="scrape-btn-"]').forEach(b => {{ b.disabled = on; if (!on) b.textContent = '🔍'; }});
  document.getElementById('add-btn').disabled = on;
  document.querySelectorAll('.analysis-card').forEach(c => c.classList.remove('scraping'));
  document.querySelectorAll('[id^="delete-btn-"]').forEach(b => b.disabled = false);
  if (on && analysisId) {{
    const card = document.getElementById('card-' + analysisId);
    if (card) card.classList.add('scraping');
    const sb = document.getElementById('scrape-btn-' + analysisId);
    if (sb) sb.textContent = '⏳';
    const db = document.getElementById('delete-btn-' + analysisId);
    if (db) db.disabled = true;
  }}
}}

// ── Helpers ───────────────────────────────────────────────────────────────────
function statCard(label, value, sub, size) {{
  const s = size ? 'style="font-size:' + size + '"' : '';
  return '<div class="stat-card"><div class="stat-label">' + label +
    '</div><div class="stat-value" ' + s + '>' + value +
    '</div><div class="stat-sub">' + sub + '</div></div>';
}}

function fmtDate(s) {{
  const months = ['jan','fév','mar','avr','mai','jun','jul','aoû','sep','oct','nov','déc'];
  const [y,m,d] = s.split('-').map(Number);
  return d + ' ' + months[m-1] + ' ' + y;
}}

function setAddStatus(msg, cls) {{
  const el = document.getElementById('add-status');
  el.textContent = msg;
  el.className   = 'add-status ' + cls;
}}
</script>

</body>
</html>"""

    with open(cfg.DASHBOARD_PATH, "w", encoding="utf-8") as f:
        f.write(html)

    return cfg.DASHBOARD_PATH
