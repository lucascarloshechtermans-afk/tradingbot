from __future__ import annotations

import json
from datetime import datetime
from typing import Any

PAGE_TEMPLATE = """<!doctype html>
<html lang="en">
<head>
<meta charset="utf-8">
<title>Swing Scanner Dashboard</title>
<meta name="viewport" content="width=device-width, initial-scale=1">
<style>
  :root {{
    --bg: #0b0f14; --surface: #131a22; --surface-2: #1a2330; --line: #263241;
    --ink: #e6edf3; --ink-soft: #93a4b8;
    --green: #3fb950; --red: #f85149; --amber: #d29922; --blue: #58a6ff;
  }}
  * {{ box-sizing: border-box; }}
  body {{ background: var(--bg); color: var(--ink); font-family: ui-sans-serif, system-ui, -apple-system, "Segoe UI", sans-serif; margin: 0; padding: 24px; }}
  h1 {{ font-size: 20px; margin: 0 0 4px; }}
  .meta {{ color: var(--ink-soft); font-size: 13px; margin-bottom: 20px; }}
  .badge {{ display: inline-block; padding: 3px 10px; border-radius: 999px; font-size: 12px; font-weight: 600; }}
  .badge.bullish {{ background: rgba(63,185,80,.15); color: var(--green); }}
  .badge.bearish {{ background: rgba(248,81,73,.15); color: var(--red); }}
  .badge.neutral {{ background: rgba(210,153,34,.15); color: var(--amber); }}
  .badge.high_volatility {{ background: rgba(248,81,73,.25); color: var(--red); }}
  .tabs {{ display: flex; gap: 4px; margin-bottom: 16px; border-bottom: 1px solid var(--line); }}
  .tab {{ padding: 8px 16px; cursor: pointer; color: var(--ink-soft); border-bottom: 2px solid transparent; font-size: 14px; }}
  .tab.active {{ color: var(--ink); border-bottom-color: var(--blue); }}
  .panel {{ display: none; }}
  .panel.active {{ display: block; }}
  .card {{ background: var(--surface); border: 1px solid var(--line); border-radius: 10px; padding: 16px; margin-bottom: 14px; }}
  table {{ width: 100%; border-collapse: collapse; font-size: 13px; }}
  th {{ text-align: left; color: var(--ink-soft); font-weight: 600; padding: 8px 10px; border-bottom: 1px solid var(--line); cursor: pointer; }}
  td {{ padding: 8px 10px; border-bottom: 1px solid var(--line); }}
  tr.row:hover {{ background: var(--surface-2); cursor: pointer; }}
  .score {{ font-weight: 700; }}
  .score.high {{ color: var(--green); }}
  .score.mid {{ color: var(--amber); }}
  .score.low {{ color: var(--ink-soft); }}
  .detail {{ display: none; background: var(--surface-2); padding: 14px 18px; }}
  .detail.open {{ display: table-row; }}
  .reasons li {{ color: var(--green); margin-bottom: 3px; }}
  .risks li {{ color: var(--red); margin-bottom: 3px; }}
  ul.plain {{ margin: 6px 0; padding-left: 18px; font-size: 12.5px; }}
  .grid {{ display: grid; grid-template-columns: repeat(auto-fill, minmax(160px, 1fr)); gap: 10px; }}
  .stat {{ background: var(--surface-2); border-radius: 8px; padding: 10px 12px; }}
  .stat .label {{ color: var(--ink-soft); font-size: 11px; text-transform: uppercase; letter-spacing: .04em; }}
  .stat .value {{ font-size: 18px; font-weight: 700; margin-top: 2px; }}
  .status-pill {{ padding: 2px 8px; border-radius: 6px; font-size: 11px; font-weight: 600; }}
  .status-forming {{ background: rgba(210,153,34,.15); color: var(--amber); }}
  .status-ready {{ background: rgba(88,166,255,.15); color: var(--blue); }}
  .status-triggered {{ background: rgba(63,185,80,.15); color: var(--green); }}
  .status-invalidated {{ background: rgba(248,81,73,.15); color: var(--red); }}
  code {{ background: var(--surface-2); padding: 1px 5px; border-radius: 4px; }}
  .cat-breakdown {{ display: flex; flex-direction: column; gap: 4px; min-width: 260px; }}
  .cat-row {{ font-size: 12px; }}
  .cat-row-head {{ display: flex; justify-content: space-between; }}
  .cat-bar-bg {{ background: var(--surface); border-radius: 4px; height: 6px; margin: 2px 0 4px; overflow: hidden; }}
  .cat-bar-fill {{ height: 100%; background: var(--blue); }}
  .cat-bar-fill.high {{ background: var(--green); }}
  .cat-bar-fill.low {{ background: var(--red); }}
  .cat-reasons {{ margin: 0 0 6px; padding-left: 16px; color: var(--ink-soft); font-size: 11px; }}
</style>
</head>
<body>
  <h1>Swing-Trade Scanner</h1>
  <div class="meta">Generated {generated_at} &middot; {universe_size} tickers scanned in {scan_duration}s &middot; {setup_count} setups found</div>

  <div class="tabs">
    <div class="tab active" data-tab="dashboard">Dashboard</div>
    <div class="tab" data-tab="scanner">Scanner</div>
    <div class="tab" data-tab="watchlist">Watchlist</div>
  </div>

  <div id="dashboard" class="panel active">
    <div class="card">
      <div class="grid">
        <div class="stat"><div class="label">Market Regime</div><div class="value"><span class="badge {regime_class}">{regime_label}</span></div></div>
        <div class="stat"><div class="label">Regime Score</div><div class="value">{regime_score}</div></div>
        <div class="stat"><div class="label">Setups Found</div><div class="value">{setup_count}</div></div>
        <div class="stat"><div class="label">Universe Scanned</div><div class="value">{universe_size}</div></div>
      </div>
    </div>
    <div class="card">
      <h3 style="margin-top:0">Market regime factors</h3>
      <ul class="plain">{regime_factors_html}</ul>
    </div>
    <div class="card">
      <h3 style="margin-top:0">Sector strength</h3>
      <table><thead><tr><th>Rank</th><th>ETF</th><th>5D Perf</th><th>1M Perf</th><th>3M Perf</th><th>RS vs SPY</th><th>Volatility</th><th>Trend</th></tr></thead>
      <tbody>{sector_rows_html}</tbody></table>
    </div>
    <div class="card">
      <h3 style="margin-top:0">Top setups</h3>
      <table><thead><tr><th>Rank</th><th>Ticker</th><th>Score</th><th>Setup</th></tr></thead>
      <tbody>{top_setups_html}</tbody></table>
    </div>
  </div>

  <div id="scanner" class="panel">
    <div class="card">
      <table id="scanner-table">
        <thead><tr>
          <th>Rank</th><th>Ticker</th><th>Score</th><th>Setup</th><th>Entry</th><th>Stop</th>
          <th>Target</th><th>R:R</th><th>Trend</th><th>RVOL</th><th>RSI</th><th>Market</th>
        </tr></thead>
        <tbody id="scanner-body"></tbody>
      </table>
    </div>
  </div>

  <div id="watchlist" class="panel">
    <div class="card">
      <table>
        <thead><tr><th>Ticker</th><th>Status</th><th>Added</th><th>Setup Detected</th><th>Notes</th></tr></thead>
        <tbody id="watchlist-body"></tbody>
      </table>
    </div>
  </div>

<script>
const SCAN_DATA = {scan_data_json};
const WATCHLIST_DATA = {watchlist_data_json};

document.querySelectorAll('.tab').forEach(tab => {{
  tab.addEventListener('click', () => {{
    document.querySelectorAll('.tab').forEach(t => t.classList.remove('active'));
    document.querySelectorAll('.panel').forEach(p => p.classList.remove('active'));
    tab.classList.add('active');
    document.getElementById(tab.dataset.tab).classList.add('active');
  }});
}});

function scoreClass(score) {{
  if (score >= 80) return 'high';
  if (score >= 60) return 'mid';
  return 'low';
}}

const CATEGORY_LABELS = {{
  trend: 'Trend', market_structure: 'Market Structure', momentum: 'Momentum',
  volume: 'Volume', price_action: 'Price Action', volatility: 'Volatility',
  relative_strength: 'Relative Strength', market_regime: 'Market Regime',
  sector: 'Sector', risk_reward: 'Risk/Reward', multi_timeframe: 'Multi-Timeframe',
}};

function renderCategoryBreakdown(categories) {{
  if (!categories || categories.length === 0) return '<div style="color:var(--ink-soft)">no breakdown</div>';
  return categories.map(cat => {{
    const barClass = cat.score >= 70 ? 'high' : (cat.score < 40 ? 'low' : '');
    const label = CATEGORY_LABELS[cat.category] || cat.category;
    const reasonsHtml = (cat.reasons || []).map(r => `<li>${{r}}</li>`).join('');
    return `<div class="cat-row">
      <div class="cat-row-head"><strong>${{label}}</strong><span>${{cat.score.toFixed(0)}}/100 &middot; weight ${{cat.weight}}%</span></div>
      <div class="cat-bar-bg"><div class="cat-bar-fill ${{barClass}}" style="width:${{Math.max(0, Math.min(100, cat.score))}}%"></div></div>
      ${{reasonsHtml ? `<ul class="cat-reasons">${{reasonsHtml}}</ul>` : ''}}
    </div>`;
  }}).join('');
}}

function renderSparkline(closes) {{
  if (!closes || closes.length < 2) return '';
  const w = 160, h = 32;
  const min = Math.min(...closes), max = Math.max(...closes);
  const range = (max - min) || 1;
  const pts = closes.map((c, i) => {{
    const x = (i / (closes.length - 1)) * w;
    const y = h - ((c - min) / range) * h;
    return x.toFixed(1) + ',' + y.toFixed(1);
  }}).join(' ');
  return '<svg width="' + w + '" height="' + h + '"><polyline points="' + pts + '" fill="none" stroke="#58a6ff" stroke-width="1.5"/></svg>';
}}

const body = document.getElementById('scanner-body');
SCAN_DATA.forEach((row, idx) => {{
  const tr = document.createElement('tr');
  tr.className = 'row';
  tr.innerHTML = `<td>${{idx + 1}}</td><td><strong>${{row.ticker}}</strong></td>` +
    `<td class="score ${{scoreClass(row.score)}}">${{row.score.toFixed(1)}}</td>` +
    `<td>${{row.setup}}</td><td>${{row.entry.toFixed(2)}}</td><td>${{row.stop.toFixed(2)}}</td>` +
    `<td>${{row.target2.toFixed(2)}}</td><td>${{row.risk_reward.toFixed(1)}}</td>` +
    `<td>${{row.trend}}</td><td>${{row.relative_volume.toFixed(1)}}x</td>` +
    `<td>${{row.rsi.toFixed(0)}}</td><td>${{row.market_regime}}</td>`;

  const detailTr = document.createElement('tr');
  detailTr.className = 'detail';
  const reasonsHtml = row.reasons.map(r => `<li>+ ${{r}}</li>`).join('');
  const risksHtml = row.risks.map(r => `<li>- ${{r}}</li>`).join('');
  detailTr.innerHTML = `<td colspan="12">
    <div style="display:flex; gap:24px; flex-wrap:wrap;">
      <div>${{renderSparkline(row.recent_closes)}}</div>
      <div><strong>Reasons</strong><ul class="plain reasons">${{reasonsHtml || '<li style="color:var(--ink-soft)">none</li>'}}</ul></div>
      <div><strong>Risks</strong><ul class="plain risks">${{risksHtml || '<li style="color:var(--ink-soft)">none</li>'}}</ul></div>
      <div><strong>Confidence</strong><div>${{row.confidence.toFixed(0)}}/100</div>
        <strong>ATR%</strong><div>${{row.atr_pct.toFixed(1)}}%</div>
        <strong>Sector</strong><div>${{row.sector || 'n/a'}}</div>
        <strong>Max holding period</strong><div>${{row.max_holding_days}} trading days</div>
      </div>
      <div class="cat-breakdown"><strong>Score breakdown</strong>${{renderCategoryBreakdown(row.category_breakdown)}}</div>
    </div>
  </td>`;

  tr.addEventListener('click', () => {{ detailTr.classList.toggle('open'); }});
  body.appendChild(tr);
  body.appendChild(detailTr);
}});

const wlBody = document.getElementById('watchlist-body');
if (WATCHLIST_DATA.length === 0) {{
  wlBody.innerHTML = '<tr><td colspan="5" style="color:var(--ink-soft)">No tickers on the watchlist yet.</td></tr>';
}}
WATCHLIST_DATA.forEach(entry => {{
  const tr = document.createElement('tr');
  const statusClass = 'status-' + entry.status.toLowerCase().replace(' ', '-').replace('setup-forming','forming');
  tr.innerHTML = `<td><strong>${{entry.ticker}}</strong></td>` +
    `<td><span class="status-pill ${{statusClass}}">${{entry.status}}</span></td>` +
    `<td>${{entry.added_date}}</td><td>${{entry.setup_detected_date || '-'}}</td><td>${{entry.notes || ''}}</td>`;
  wlBody.appendChild(tr);
}});
</script>
</body>
</html>
"""


def _regime_css_class(label: str) -> str:
    return {"BULLISH": "bullish", "BEARISH": "bearish", "NEUTRAL": "neutral", "HIGH_VOLATILITY": "high_volatility"}.get(
        label, "neutral"
    )


def build_dashboard_html(
    scan_rows: list[dict[str, Any]],
    market_regime: dict[str, Any],
    sector_ranked: list[dict[str, Any]],
    watchlist_entries: list[dict[str, Any]],
    universe_size: int,
    scan_duration_s: float,
    generated_at: datetime | None = None,
) -> str:
    generated_at = generated_at or datetime.now()
    setup_count = len(scan_rows)

    regime_factors_html = "".join(
        f"<li><code>{k}</code>: {v}</li>" for k, v in market_regime.get("factors", {}).items()
    )
    sector_rows_html = "".join(
        f"<tr><td>{s['rank']}</td><td>{s['etf']}</td><td>{s.get('performance_5d', float('nan')):.1f}%</td>"
        f"<td>{s['performance_1m']:.1f}%</td>"
        f"<td>{s['performance_3m']:.1f}%</td><td>{s['relative_strength_vs_spy']:+.1f}%</td>"
        f"<td>{s.get('volatility_pct', float('nan')):.0f}%</td><td>{s['trend']}</td></tr>"
        for s in sector_ranked
    )
    top_setups_html = "".join(
        f"<tr><td>{i+1}</td><td><strong>{r['ticker']}</strong></td><td>{r['score']:.1f}</td><td>{r['setup']}</td></tr>"
        for i, r in enumerate(scan_rows[:10])
    )

    return PAGE_TEMPLATE.format(
        generated_at=generated_at.strftime("%Y-%m-%d %H:%M:%S"),
        universe_size=universe_size,
        scan_duration=f"{scan_duration_s:.1f}",
        setup_count=setup_count,
        regime_class=_regime_css_class(market_regime.get("label", "NEUTRAL")),
        regime_label=market_regime.get("label", "UNKNOWN"),
        regime_score=f"{market_regime.get('score', 0):+.0f}",
        regime_factors_html=regime_factors_html or "<li>No regime data</li>",
        sector_rows_html=sector_rows_html or "<tr><td colspan=8>No sector data</td></tr>",
        top_setups_html=top_setups_html or "<tr><td colspan=4>No setups found</td></tr>",
        scan_data_json=json.dumps(scan_rows),
        watchlist_data_json=json.dumps(watchlist_entries),
    )


def trade_plan_to_row(plan) -> dict[str, Any]:
    """Convert a scanner.TradePlan (or any object with matching attributes) into
    the plain-dict shape the dashboard template expects."""
    return {
        "ticker": plan.ticker,
        "score": plan.score,
        "setup": plan.setup,
        "entry": plan.entry,
        "stop": plan.stop,
        "target2": plan.target2,
        "risk_reward": plan.risk_reward,
        "trend": plan.trend,
        "relative_volume": plan.relative_volume,
        "rsi": plan.rsi,
        "market_regime": plan.market_regime,
        "atr_pct": plan.atr_pct,
        "sector": plan.sector,
        "confidence": plan.confidence,
        "reasons": plan.reasons,
        "risks": plan.risks,
        "recent_closes": plan.recent_closes,
        "max_holding_days": plan.max_holding_days,
        "category_breakdown": getattr(plan, "category_breakdown", []),
    }
