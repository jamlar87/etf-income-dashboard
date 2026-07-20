// ETF Dip Screener — Buy the Dip Signals
const DIP_API = '/api/dip-screener';
let allDipResults = [];
let filteredResults = [];

// Helpers
function fmt(v, s='', d=2) {
    if (v == null || v === undefined) return '--';
    return Number(v).toFixed(d) + s;
}
function pct(v) { return fmt(v, '%'); }
function dollar(v) {
    if (v == null) return '--';
    if (v >= 1000) return '$' + (v/1000).toFixed(1) + 'B';
    return '$' + Number(v).toLocaleString() + 'M';
}

// Signal tag classes
function signalClass(sig) {
    const m = {
        'RSI Oversold': 'rsi', 'Deep Pullback': 'pullback', 'Moderate Pullback': 'pullback',
        'Below BB': 'bb', '52W Bottom': 'range', 'Uptrend Dip': 'trend', 'Rare Dip': 'range'
    };
    return m[sig] || '';
}

function tierClass(t) {
    return t === 'strong' ? 's-strong' : t === 'moderate' ? 's-moderate' : t === 'watch' ? 's-watch' : 's-neutral';
}

function trendClass(t) {
    return (t || '').toLowerCase();
}

function pctClass(v, invert=false) {
    if (v == null) return '';
    if (!invert) return v >= 0 ? 'val-pos' : 'val-neg';
    return v <= 0 ? 'val-pos' : 'val-neg'; // for pullbacks, negative = good
}

async function loadDipScreener(forceRefresh) {
    try {
        const tbody = document.getElementById('dip-tbody');
        if (tbody) tbody.innerHTML = '<tr><td colspan="15" style="text-align:center;padding:30px;color:var(--text-dim)">⏳ Computing dip signals...</td></tr>';

        const params = forceRefresh ? '?limit=2000&force_refresh=true' : '?limit=2000';
        const resp = await fetch(DIP_API + params);
        const data = await resp.json();
        allDipResults = data.results || [];
        
        applyFilters();
        document.getElementById('dip-last-updated').textContent = 'Updated: ' + new Date().toLocaleString();
    } catch (e) {
        console.error('Dip screener load error:', e);
        const tbody = document.getElementById('dip-tbody');
        if (tbody) tbody.innerHTML = '<tr><td colspan="15" style="text-align:center;padding:30px;color:var(--red)">⚠ Error loading data: ' + e.message + '</td></tr>';
    }
}

function applyFilters() {
    const minScore = parseInt(document.getElementById('dip-min-score')?.value) || 0;
    const trendFilter = document.getElementById('dip-trend-filter')?.value || 'any';
    const tierFilter = document.getElementById('dip-tier-filter')?.value || 'all';
    const minYield = parseFloat(document.getElementById('dip-min-yield')?.value) || 0;
    const minNav = parseFloat(document.getElementById('dip-min-nav')?.value) || -100;
    const maxER = parseFloat(document.getElementById('dip-max-er')?.value) || 10;
    const sortBy = document.getElementById('dip-sort-by')?.value || 'dip_score';

    let results = [...allDipResults];

    // Client-side filters (in addition to what API already does)
    if (minYield > 0) results = results.filter(r => (r.current_yield || 0) >= minYield);
    if (minNav > -100) results = results.filter(r => r.nav_annual_change == null || r.nav_annual_change >= minNav);
    if (maxER < 10) results = results.filter(r => (r.expense_ratio || 0) <= maxER);
    if (tierFilter === 'strong') results = results.filter(r => r.dip_score >= 70);
    else if (tierFilter === 'moderate') results = results.filter(r => r.dip_score >= 50);
    else if (tierFilter === 'watch') results = results.filter(r => r.dip_score >= 30);
    
    // Trend filter (client-side since API already handles some)
    if (trendFilter === 'uptrend') results = results.filter(r => r.trend_label === 'Uptrend');
    else if (trendFilter === 'neutral') results = results.filter(r => r.trend_label !== 'Downtrend');

    // Sort — respect column click direction if set, else use defaults per field
    const sortDir = window._dipSortDir;
    const defaultsAsc = ['rsi_14', 'expense_ratio', 'bb_percent_b', 'range_percentile'];
    const desc = sortDir ? sortDir === 'desc' : !defaultsAsc.includes(sortBy);
    results.sort((a, b) => {
        const va = a[sortBy] ?? (desc ? -Infinity : Infinity);
        const vb = b[sortBy] ?? (desc ? -Infinity : Infinity);
        return desc ? vb - va : va - vb;
    });

    filteredResults = results;
    renderTable(results);
    updateStats(results, allDipResults.length);
}

function updateStats(filtered, total) {
    const strong = filtered.filter(r => r.dip_score >= 70).length;
    const moderate = filtered.filter(r => r.dip_score >= 50 && r.dip_score < 70).length;
    const watch = filtered.filter(r => r.dip_score >= 30 && r.dip_score < 50).length;
    
    document.getElementById('ds-total').querySelector('.stat-num').textContent = total;
    document.getElementById('ds-strong').querySelector('.stat-num').textContent = strong;
    document.getElementById('ds-moderate').querySelector('.stat-num').textContent = moderate;
    document.getElementById('ds-watch').querySelector('.stat-num').textContent = watch;
}

function signalTagHtml(signals) {
    if (!signals || !signals.length) return '<span style="color:#555;font-size:0.72em">—</span>';
    return signals.map(s => `<span class="signal-tag ${signalClass(s)}">${s}</span>`).join('');
}

function scoreBarHtml(score) {
    const tier = score >= 70 ? 'strong' : score >= 50 ? 'moderate' : score >= 30 ? 'watch' : 'neutral';
    const barWidth = Math.max(3, Math.min(60, score * 0.6));
    return `<span class="score-bar ${tier}" style="width:${barWidth}px"></span>`;
}

function renderTable(results) {
    const tbody = document.getElementById('dip-tbody');
    const empty = document.getElementById('dip-empty');
    if (!tbody) return;

    if (results.length === 0) {
        tbody.innerHTML = '';
        if (empty) empty.style.display = 'block';
        return;
    }
    if (empty) empty.style.display = 'none';

    tbody.innerHTML = results.map((r, i) => `
        <tr class="dip-main-row" data-ticker="${r.ticker}" data-idx="${i}" style="cursor:pointer">
            <td>${i + 1}</td>
            <td class="ticker-col" data-ticker="${r.ticker}"><strong>${r.ticker}</strong> <a href="https://www.tradingview.com/symbols/${r.ticker}/" target="_blank" title="Open on TradingView" style="text-decoration:none;font-size:0.75em;color:var(--text-dim);margin-left:2px" onclick="event.stopPropagation()">📈</a></td>
            <td class="score-col ${tierClass(r.tier || 'neutral')}">
                ${scoreBarHtml(r.dip_score)}${r.dip_score}
            </td>
            <td><span class="tier-badge ${r.tier || 'neutral'}">${r.tier || 'neutral'}</span></td>
            <td>${signalTagHtml(r.signals)}</td>
            <td><span class="trend-badge ${trendClass(r.trend_label)}">${r.trend_label || '--'}</span></td>
            <td class="${pctClass(r.nav_annual_change)}">${r.nav_annual_change != null ? r.nav_annual_change.toFixed(1) + '%' : '--'}</td>
            <td class="${pctClass(r.rsi_14 != null ? 50 - r.rsi_14 : null)}">${r.rsi_14 != null ? r.rsi_14.toFixed(1) : '--'}</td>
            <td class="${pctClass(r.pct_off_52w_high, true)}">${pct(r.pct_off_52w_high)}</td>
            <td>${r.bb_percent_b != null ? r.bb_percent_b.toFixed(2) : '--'}</td>
            <td>${r.range_percentile != null ? r.range_percentile.toFixed(1) + '%' : '--'}</td>
            <td style="font-size:0.75em">${r.current_dd_pctile != null ? (r.current_dd_pctile >= 90 ? '<span style="color:var(--dip-strong);font-weight:700">' + r.current_dd_pctile + '%' : r.current_dd_pctile >= 75 ? '<span style="color:var(--dip-moderate)">' + r.current_dd_pctile + '%' : '<span style="color:var(--text-dim)">' + r.current_dd_pctile + '%') + '</span>' : '--'}</td>
            <td class="${pctClass(r.pct_vs_sma200)}">${r.pct_vs_sma200 != null ? pct(r.pct_vs_sma200) : '--'}</td>
            <td class="${pctClass(r.current_yield)}">${pct(r.current_yield)}</td>
            <td>${r.expense_ratio != null ? r.expense_ratio.toFixed(2) + '%' : '--'}</td>
            <td>${dollar(r.aum)}</td>
            <td style="font-size:0.72em;color:var(--text-dim)">${r.provider || '--'}</td>
        </tr>
        <tr class="detail-row" data-ticker="${r.ticker}">
            <td colspan="16" class="detail-cell">
                <div class="detail-grid">
                    <div class="detail-item">
                        <div class="lbl">RSI Score</div>
                        <div class="val">${r.rsi_score}/25</div>
                    </div>
                    <div class="detail-item">
                        <div class="lbl">Pullback Score</div>
                        <div class="val">${r.pullback_score}/25</div>
                    </div>
                    <div class="detail-item">
                        <div class="lbl">BB Score</div>
                        <div class="val">${r.bb_score}/20</div>
                    </div>
                    <div class="detail-item">
                        <div class="lbl">Range Score</div>
                        <div class="val">${r.range_score}/15</div>
                    </div>
                    <div class="detail-item">
                        <div class="lbl">Trend Score</div>
                        <div class="val">${r.trend_score}/15</div>
                    </div>
                    <div class="detail-item">
                        <div class="lbl">RSI Rising</div>
                        <div class="val ${r.rsi_rising ? 'positive' : ''}">${r.rsi_rising ? '✓' : '—'}</div>
                    </div>
                    <div class="detail-item">
                        <div class="lbl">SMA200</div>
                        <div class="val">${r.sma_200 != null ? '$' + r.sma_200.toFixed(2) : '--'}</div>
                    </div>
                    <div class="detail-item">
                        <div class="lbl">Latest Price</div>
                        <div class="val">$${(r.latest_price || 0).toFixed(2)}</div>
                    </div>
                    <div class="detail-item">
                        <div class="lbl">Hist Bonus</div>
                        <div class="val">${r.hist_bonus || 0}/5</div>
                    </div>
                    <div class="detail-item" style="grid-column:span 2">
                        <div class="lbl">Historical Pullbacks: avg ${r.hist_avg_dd || '--'}% · max ${r.hist_max_dd || '--'}% · ${r.hist_dd_count || 0} events</div>
                        <div class="val">${r.current_dd_pctile != null ? 'Current dip deeper than <strong>' + r.current_dd_pctile + '%</strong> of past pullbacks' : '—'}</div>
                    </div>
                </div>
            </td>
        </tr>
    `).join('');

    // Click to expand detail
    tbody.querySelectorAll('.dip-main-row').forEach(row => {
        row.onclick = () => {
            const ticker = row.dataset.ticker;
            const detail = tbody.querySelector(`.detail-row[data-ticker="${ticker}"]`);
            if (detail) {
                detail.classList.toggle('show');
                if (detail.classList.contains('show')) {
                    setTimeout(() => detail.scrollIntoView({ behavior: 'smooth', block: 'nearest' }), 50);
                }
            }
        };
    });

    // Click-to-sort on column headers
    document.querySelectorAll('#dip-table th[data-sort]').forEach(th => {
        th.style.cursor = 'pointer';
        th.onclick = () => {
            const field = th.dataset.sort;
            const sb = document.getElementById('dip-sort-by');
            if (!sb) return;
            // Toggle direction if same field, else default desc
            if (sb.value === field) {
                // Flip: currently desc → asc, or asc → desc
                const isDesc = !th.innerHTML.includes('▼');
                sb.value = field;
                // Store direction in sort dir tracked by the render
                window._dipSortDir = isDesc ? 'desc' : 'asc';
            } else {
                sb.value = field;
                window._dipSortDir = 'desc';
            }
            // Update sort arrow indicators
            document.querySelectorAll('#dip-table th[data-sort]').forEach(h => {
                h.innerHTML = h.innerHTML.replace(/ [▲▼]/, '');
            });
            th.innerHTML += window._dipSortDir === 'desc' ? ' ▼' : ' ▲';
            applyFilters();
        };
    });
}

// === INIT ===
document.addEventListener('DOMContentLoaded', () => {
    loadDipScreener();

    // Wire controls
    const refreshBtn = document.getElementById('dip-refresh');
    if (refreshBtn) refreshBtn.onclick = () => loadDipScreener(true);

    const minScoreRange = document.getElementById('dip-min-score');
    const minScoreVal = document.getElementById('dip-min-score-val');
    if (minScoreRange && minScoreVal) {
        minScoreRange.oninput = function() {
            minScoreVal.textContent = this.value;
            applyFilters();
        };
    }

    ['dip-trend-filter', 'dip-tier-filter', 'dip-min-yield', 'dip-min-nav', 'dip-max-er', 'dip-sort-by'].forEach(id => {
        const el = document.getElementById(id);
        if (el) el.onchange = () => {
            // Clear column sort indicators when using dropdown
            if (id === 'dip-sort-by') {
                window._dipSortDir = undefined;
                document.querySelectorAll('#dip-table th[data-sort]').forEach(h => {
                    h.innerHTML = h.innerHTML.replace(/ [▲▼]/g, '');
                });
            }
            applyFilters();
        };
    });

    // Ticker Score Search
    const searchInput = document.getElementById('ticker-search-input');
    const searchBtn = document.getElementById('ticker-search-btn');
    const searchResult = document.getElementById('ticker-search-result');

    function doTickerSearch() {
        const q = (searchInput?.value || '').trim().toUpperCase();
        if (!q) {
            if (searchResult) searchResult.innerHTML = '';
            return;
        }
        const match = allDipResults.find(r => r.ticker === q);
        if (!match) {
            const maybe = allDipResults.filter(r => r.ticker.startsWith(q)).slice(0, 5);
            if (maybe.length) {
                searchResult.innerHTML = `<div style="padding:14px;background:var(--bg);border-radius:var(--radius);border:1px solid var(--border)">
                    <p style="color:var(--orange);margin-bottom:6px">"<strong>${q}</strong>" not found. Did you mean?</p>
                    ${maybe.map(r => `<span class="bp-etf-tag" data-ticker="${r.ticker}" style="cursor:pointer;background:var(--card-bg);padding:3px 8px;margin:2px;border-radius:3px;display:inline-block">${r.ticker}</span>`).join('')}
                </div>`;
                searchResult.querySelectorAll('[data-ticker]').forEach(el => {
                    el.onclick = () => { searchInput.value = el.dataset.ticker; doTickerSearch(); };
                });
            } else {
                searchResult.innerHTML = `<div style="padding:14px;background:var(--bg);border-radius:var(--radius);border:1px solid var(--border)">
                    <p style="color:var(--text-dim)">"<strong>${q}</strong>" is not in the scanned universe (may be excluded by quality filters — $2B AUM, no leverage, or <14 months history).</p>
                </div>`;
            }
            return;
        }

        const r = match;
        const sigs = (r.signals || []).map(s => `<span class="signal-tag ${signalClass(s)}">${s}</span>`).join(' ');
        searchResult.innerHTML = `<div style="padding:16px;background:var(--bg);border-radius:var(--radius);border:1px solid var(--border)">
            <div style="display:flex;align-items:center;gap:12px;margin-bottom:12px">
                <span style="font-size:1.3em;font-weight:700;color:var(--accent)">${r.ticker}</span>
                <span class="tier-badge ${r.tier}">${r.tier}</span>
                <span class="score-col ${tierClass(r.tier)}" style="font-size:1.1em">${scoreBarHtml(r.dip_score)}${r.dip_score}</span>
                ${sigs}
            </div>
            <div style="display:grid;grid-template-columns:repeat(auto-fit, minmax(110px, 1fr));gap:8px;font-size:0.82em">
                <div class="detail-item"><div class="lbl">RSI(14)</div><div class="val ${r.rsi_14 < 40 ? 'positive' : ''}">${r.rsi_14 != null ? r.rsi_14.toFixed(1) : '--'}</div></div>
                <div class="detail-item"><div class="lbl">% off 52W High</div><div class="val negative">${r.pct_off_52w_high != null ? r.pct_off_52w_high.toFixed(1) + '%' : '--'}</div></div>
                <div class="detail-item"><div class="lbl">BB %B</div><div class="val">${r.bb_percent_b != null ? r.bb_percent_b.toFixed(2) : '--'}</div></div>
                <div class="detail-item"><div class="lbl">52W %ile</div><div class="val">${r.range_percentile != null ? r.range_percentile.toFixed(1) + '%' : '--'}</div></div>
                <div class="detail-item"><div class="lbl">vs SMA200</div><div class="val ${r.pct_vs_sma200 >= 0 ? 'positive' : 'negative'}">${r.pct_vs_sma200 != null ? r.pct_vs_sma200.toFixed(1) + '%' : '--'}</div></div>
                <div class="detail-item"><div class="lbl">Trend</div><div class="val"><span class="trend-badge ${trendClass(r.trend_label)}">${r.trend_label}</span></div></div>
                <div class="detail-item"><div class="lbl">NAV Change</div><div class="val ${r.nav_annual_change >= 0 ? 'positive' : 'negative'}">${r.nav_annual_change != null ? r.nav_annual_change.toFixed(1) + '%' : '--'}</div></div>
                <div class="detail-item"><div class="lbl">Yield</div><div class="val">${r.current_yield != null ? r.current_yield.toFixed(1) + '%' : '--'}</div></div>
                <div class="detail-item"><div class="lbl">vs Hist</div><div class="val">${r.current_dd_pctile != null ? r.current_dd_pctile + '%' : '--'}</div></div>
            </div>
            <div style="display:grid;grid-template-columns:repeat(5,1fr);gap:6px;margin-top:10px;font-size:0.78em;border-top:1px solid var(--border);padding-top:8px">
                <div class="detail-item"><div class="lbl">RSI Score</div><div class="val">${r.rsi_score}/25</div></div>
                <div class="detail-item"><div class="lbl">Pullback</div><div class="val">${r.pullback_score}/25</div></div>
                <div class="detail-item"><div class="lbl">BB</div><div class="val">${r.bb_score}/20</div></div>
                <div class="detail-item"><div class="lbl">Range</div><div class="val">${r.range_score}/15</div></div>
                <div class="detail-item"><div class="lbl">Trend</div><div class="val">${r.trend_score}/15</div></div>
                <div class="detail-item"><div class="lbl">Hist</div><div class="val">${r.hist_bonus || 0}/5</div></div>
            </div>
            <div style="margin-top:6px;font-size:0.78em;color:var(--text-dim);border-top:1px solid var(--border);padding-top:6px">
                <strong>Historical:</strong> avg pullback ${r.hist_avg_dd || '--'}% · max ${r.hist_max_dd || '--'}% · ${r.hist_dd_count || 0} events
                ${r.current_dd_pctile != null ? ' · Current dip deeper than <strong>' + r.current_dd_pctile + '%</strong> of past' : ''}
            </div>
            <div style="margin-top:8px">
                <a href="https://www.tradingview.com/symbols/${r.ticker}/" target="_blank" style="color:var(--accent);font-size:0.82em">📈 Open on TradingView</a>
            </div>
        </div>`;
    }

    if (searchBtn) searchBtn.onclick = doTickerSearch;
    if (searchInput) {
        searchInput.onkeydown = (e) => { if (e.key === 'Enter') doTickerSearch(); };
    }
});
