// ETF Dashboard JS — scroll-based layout (all sections visible)
const API = '/api';
// Click any element with data-ticker to open Seeking Alpha page
document.addEventListener('click', function(e) {
    let el = e.target;
    while (el && el !== document) {
        if (el.dataset && el.dataset.ticker) {
            window.open('https://seekingalpha.com/symbol/' + el.dataset.ticker, '_blank');
            e.preventDefault();
            return;
        }
        el = el.parentElement;
    }
});

let currentPeriod = '1yr';

let allEtfs = [];
let pfChartNav = null;
let pfChartIncome = null;
let retChart = null;
let growthChart = null;
let portfolioEtfs = [];

// === IntersectionObserver (wrapped for browser compat) ===
let observer = null;
try {
    observer = new IntersectionObserver(entries => {
        entries.forEach(entry => {
            if (entry.isIntersecting) {
                document.querySelectorAll('.nav-link').forEach(l => l.classList.remove('active'));
                const link = document.querySelector(`.nav-link[href="#${entry.target.id}"]`);
                if (link) link.classList.add('active');
            }
        });
    }, { rootMargin: '-80px 0px -60% 0px' });
} catch(e) {
    console.warn('IntersectionObserver not supported:', e.message);
}

function watchSections() {
    if (!observer) return;
    document.querySelectorAll('.scroll-section').forEach(s => observer.observe(s));
}

// === Helpers ===
function fmt(v, s='', d=2) {
    if (v == null) return '--';
    return Number(v).toFixed(d) + s;
}

function pct(v) { return fmt(v, '%'); }

// === Status badge helper ===
function updateStatus(msg, color) {
    const badge = document.getElementById('status-badge');
    if (badge) {
        badge.textContent = msg;
        badge.style.color = color || 'var(--orange)';
    }
}

// === INIT — load all sections with timeout ===
function initDashboard() {
    console.log('Dashboard: starting data load...');
    initCollapsible();
    watchSections();

    // Wire up global period selector
    const periodSel = document.getElementById('global-period');
    if (periodSel) {
        periodSel.onchange = async () => {
            currentPeriod = periodSel.value;
            updateStatus('⏳ Reloading with ' + currentPeriod + '...', 'var(--accent)');
            try {
                await Promise.all([
                    loadOverview(),
                    loadInvestmentGrowth(),
                    loadBetaChart(),
                ]);
                updateStatus('✅ Data refreshed (' + currentPeriod + ')', 'var(--green)');
            } catch(e) {
                updateStatus('⚠ Reload error for ' + currentPeriod, 'var(--red)');
                console.warn('Period reload error:', e.message);
            }
        };
    }

    // Timeout: if data doesn't load in 15s, show error
    const timeoutId = setTimeout(() => {
        updateStatus('⏱ Timeout — some API calls hung', 'var(--red)');
        console.error('Dashboard: promise.all timed out after 15s');
    }, 15000);

    Promise.all([
        loadOverview(),
        loadCompare(),
        loadDistYield(),
        loadDistCoverage(),
        loadNavErosion(),
        loadTotalReturn(),
        loadSharpe(),
        loadT12Perf(),
        loadInvestmentGrowth(),
        loadBetaChart(),
        loadReturnChart(),
        setupPortfolio(),
        loadBestPortfolios(),
    ]).then(() => {
        clearTimeout(timeoutId);
        updateStatus('✓ Data loaded — ' + (allEtfs.length || '?') + ' ETFs', 'var(--green)');
        console.log('Dashboard: all data loaded successfully');
    }).catch(err => {
        clearTimeout(timeoutId);
        const msg = '⚠ Error: ' + (err?.message || String(err)).slice(0, 80);
        updateStatus(msg, 'var(--red)');
        console.error('Dashboard: load error:', err);
    });
}

// === COLLAPSIBLE SECTIONS ===
function initCollapsible() {
    const STORAGE_KEY = 'etf-dash-collapse';
    let saved;
    try { saved = JSON.parse(localStorage.getItem(STORAGE_KEY) || '{}'); } catch(e) { saved = {}; }

    // Hamburger sidebar toggle
    const hamburger = document.getElementById('sidebar-toggle');
    const sidebar = document.getElementById('sidebar');
    const overlay = document.getElementById('sidebar-overlay');
    if (hamburger && sidebar && overlay) {
        function closeSidebar() {
            sidebar.classList.remove('open');
            overlay.classList.remove('open');
        }
        hamburger.onclick = () => {
            sidebar.classList.toggle('open');
            overlay.classList.toggle('open');
        };
        overlay.onclick = closeSidebar;
        // Close sidebar when a nav link is clicked
        sidebar.querySelectorAll('.nav-link').forEach(a => {
            a.onclick = closeSidebar;
        });
    }

    document.querySelectorAll('section.scroll-section').forEach(section => {
        const h1 = section.querySelector('h1');
        if (!h1) return;
        // Wrap content after h1 in section-inner
        const inner = document.createElement('div');
        inner.className = 'section-inner';
        let sibling = h1.nextElementSibling;
        const nodes = [];
        while (sibling) {
            nodes.push(sibling);
            sibling = sibling.nextElementSibling;
        }
        nodes.forEach(n => inner.appendChild(n));
        section.appendChild(inner);
        // Toggle icon
        const id = section.id || 'section-' + Math.random().toString(36).slice(2,6);
        const wrap = document.createElement('span');
        wrap.className = 'section-toggle';
        wrap.innerHTML = '<span class="toggle-icon">▼</span> ';
        h1.parentNode.insertBefore(wrap, h1);
        wrap.appendChild(h1);
        // Restore state
        if (saved[id] === 'collapsed') {
            inner.classList.add('collapsed');
            wrap.classList.add('collapsed');
        }
        wrap.onclick = () => {
            const isCollapsed = inner.classList.toggle('collapsed');
            wrap.classList.toggle('collapsed');
            saved[id] = isCollapsed ? 'collapsed' : 'expanded';
            try { localStorage.setItem(STORAGE_KEY, JSON.stringify(saved)); } catch(e) {}
        };
    });
}

// Try both approaches: DOMContentLoaded and direct (for deferred scripts)
if (document.readyState === 'loading') {
    document.addEventListener('DOMContentLoaded', initDashboard);
} else {
    initDashboard();
}
// === OVERVIEW / LEADERBOARD ===
async function loadOverview() {
    try {
        const resp = await fetch(`${API}/leaderboard?period=${currentPeriod}`);
        const lb = await resp.json();
        const s = lb.stats;
        const el = document.getElementById('os-etfs');
        if (el) el.textContent = s.total_etfs;
        const el2 = document.getElementById('os-avg-yield');
        if (el2) el2.textContent = s.avg_yield + '%';

        const bestRet = s.best_total_return;
        const bestSharpe = s.best_sharpe;
        const periodLabel = currentPeriod === '1yr' ? 'TTM' : currentPeriod === 'max' ? '10Y' : currentPeriod.toUpperCase();
        const sharpeLabel = currentPeriod === '1yr' ? 'T12M' : currentPeriod === 'max' ? 'Orig' : currentPeriod.toUpperCase();
        const el3 = document.getElementById('os-best-ret');
        if (el3) el3.textContent = bestRet ? `${bestRet[0]} ${bestRet[1]}%` : '--';
        const el3l = document.getElementById('os-best-ret-label');
        if (el3l) el3l.textContent = 'Best Total Return (' + periodLabel + ')';
        const el4 = document.getElementById('os-best-sharpe');
        if (el4) el4.textContent = bestSharpe ? `${bestSharpe[0]} ${bestSharpe[1]}` : '--';
        const el4l = document.getElementById('os-best-sharpe-label');
        if (el4l) el4l.textContent = 'Best Sharpe (' + sharpeLabel + ')';

        const grid = document.getElementById('leaderboard-grid');
        if (!grid) return;

        function renderCat(catKey, valField, sortField) {
            let entries = lb.categories[catKey]?.slice(0, 5) || [];
            if (sortField) {
                entries = [...entries].sort((a, b) => (b[sortField] ?? -Infinity) - (a[sortField] ?? -Infinity)).slice(0, 5);
            }
            return entries.map((e, i) => {
                let displayVal, displayLabel;
                if (valField === 'total_return_1yr' || valField === 'total_return_3yr') {
                    displayVal = pct(e[valField]);
                    displayLabel = pct(e.current_yield);
                } else if (valField === 'sharpe_ratio' || valField === 'sortino_ratio' || valField === 'calmar_ratio') {
                    displayVal = fmt(e[valField]);
                    displayLabel = pct(e.current_yield);
                } else if (valField === 'current_yield') {
                    displayVal = pct(e.current_yield);
                    displayLabel = '$' + (e.available_income_10k != null ? Number(e.available_income_10k).toLocaleString() : '--');
                } else if (valField === 'avg_yield') {
                    displayVal = pct(e.avg_yield_since_inception);
                    displayLabel = pct(e.current_yield);
                } else if (valField === 'distribution_coverage') {
                    displayVal = fmt(e[valField], 'x');
                    displayLabel = pct(e.current_yield);
                } else if (valField === 'nav_annual_change') {
                    displayVal = pct(e[valField]);
                    displayLabel = pct(e.current_yield);
                } else {
                    displayVal = pct(e.current_yield);
                    displayLabel = '--';
                }
                return `<div class="lb-row">
                    <span class="lb-rank">#${i+1}</span>
                    <span class="lb-ticker" data-ticker="${e.ticker}">${e.ticker}</span>
                    <span class="lb-val">${displayLabel}</span>
                    <span class="lb-val">${displayVal}</span>
                    <span class="lb-legend ${e.tier}"></span>
                </div>`;
            }).join('');
        }

        grid.innerHTML = `<div class="lb-section">
            <h3 class="lb-section-title">📊 Trailing 12 Months (TTM)</h3>
            <div class="lb-two-col">
                <div class="lb-col">
                    <div class="lb-col-header">Best Total Return</div>
                    <div class="lb-col-headers"><span class="lb-hdr-ticker">Ticker</span><span class="lb-hdr-val">Yield</span><span class="lb-hdr-val">Value</span></div>
                    ${renderCat('best_total_return_1yr', 'total_return_1yr')}
                </div>
                <div class="lb-col">
                    <div class="lb-col-header">Best Sharpe Ratio</div>
                    <div class="lb-col-headers"><span class="lb-hdr-ticker">Ticker</span><span class="lb-hdr-val">Yield</span><span class="lb-hdr-val">Value</span></div>
                    ${renderCat('best_sharpe', 'sharpe_ratio')}
                </div>
            </div>
        </div>
        <div class="lb-section">
            <h3 class="lb-section-title">💰 Distribution Quality</h3>
            <div class="lb-three-col">
                <div class="lb-col">
                    <div class="lb-col-header">Highest Current Yield</div>
                    <div class="lb-col-headers"><span class="lb-hdr-ticker">Ticker</span><span class="lb-hdr-val">Yield</span><span class="lb-hdr-val">Value</span></div>
                    ${renderCat('highest_yield', 'current_yield')}
                </div>
                <div class="lb-col">
                    <div class="lb-col-header">Best Avg Yield</div>
                    <div class="lb-col-headers"><span class="lb-hdr-ticker">Ticker</span><span class="lb-hdr-val">Avg Yld</span><span class="lb-hdr-val">Value</span></div>
                    ${renderCat('highest_yield', 'avg_yield', 'avg_yield_since_inception')}
                </div>
                <div class="lb-col">
                    <div class="lb-col-header">Best Distribution Coverage</div>
                    <div class="lb-col-headers"><span class="lb-hdr-ticker">Ticker</span><span class="lb-hdr-val">Cov</span><span class="lb-hdr-val">Value</span></div>
                    ${renderCat('best_dist_coverage', 'distribution_coverage')}
                </div>
            </div>
        </div>
        <div class="lb-section">
            <h3 class="lb-section-title">📈 Total Returns</h3>
            <div class="lb-three-col">
                <div class="lb-col">
                    <div class="lb-col-header">Best 1-Year Return</div>
                    <div class="lb-col-headers"><span class="lb-hdr-ticker">Ticker</span><span class="lb-hdr-val">Yield</span><span class="lb-hdr-val">Value</span></div>
                    ${renderCat('best_total_return_1yr', 'total_return_1yr')}
                </div>
                <div class="lb-col">
                    <div class="lb-col-header">Best 3-Year Return</div>
                    <div class="lb-col-headers"><span class="lb-hdr-ticker">Ticker</span><span class="lb-hdr-val">Yield</span><span class="lb-hdr-val">Value</span></div>
                    ${renderCat('best_total_return_3yr', 'total_return_3yr')}
                </div>
                <div class="lb-col">
                    <div class="lb-col-header">Best 5-Year Return</div>
                    <div class="lb-col-headers"><span class="lb-hdr-ticker">Ticker</span><span class="lb-hdr-val">Yield</span><span class="lb-hdr-val">Value</span></div>
                    ${renderCat('best_total_return_5yr', 'total_return_5yr')}
                </div>
            </div>
        </div>
        <div class="lb-section">
            <h3 class="lb-section-title">🎯 Risk-Adjusted Returns</h3>
            <div class="lb-four-col">
                <div class="lb-col">
                    <div class="lb-col-header">Best Sharpe Ratio</div>
                    <div class="lb-col-headers"><span class="lb-hdr-ticker">Ticker</span><span class="lb-hdr-val">Yield</span><span class="lb-hdr-val">Value</span></div>
                    ${renderCat('best_sharpe', 'sharpe_ratio')}
                </div>
                <div class="lb-col">
                    <div class="lb-col-header">Best Sortino Ratio</div>
                    <div class="lb-col-headers"><span class="lb-hdr-ticker">Ticker</span><span class="lb-hdr-val">Sortino</span><span class="lb-hdr-val">Value</span></div>
                    ${renderCat('best_sortino', 'sortino_ratio')}
                </div>
                <div class="lb-col">
                    <div class="lb-col-header">Best Calmar Ratio</div>
                    <div class="lb-col-headers"><span class="lb-hdr-ticker">Ticker</span><span class="lb-hdr-val">Calmar</span><span class="lb-hdr-val">Value</span></div>
                    ${renderCat('best_calmar', 'calmar_ratio')}
                </div>
                <div class="lb-col">
                    <div class="lb-col-header">Best NAV Growth</div>
                    <div class="lb-col-headers"><span class="lb-hdr-ticker">Ticker</span><span class="lb-hdr-val">NAV</span><span class="lb-hdr-val">Value</span></div>
                    ${renderCat('best_nav_growth', 'nav_annual_change')}
                </div>
            </div>
        </div>`;
    } catch(e) {
        console.error('loadOverview failed:', e);
        throw e;
    }
}

// === COMPARE TABLE ===
let metricsChart = null;

async function loadCompare() {
    try {
        if (allEtfs.length === 0) allEtfs = await (await fetch(`${API}/etfs`)).json();
        const providers = [...new Set(allEtfs.map(e => e.provider))].sort();
        const pf = document.getElementById('provider-filter');
        if (pf) {
            pf.innerHTML = '<option value="">All</option>' + providers.map(p => `<option>${p}</option>`).join('');
        }
        renderTable();
        const pf2 = document.getElementById('provider-filter');
        if (pf2) pf2.onchange = renderTable;
        const sb = document.getElementById('sort-by');
        if (sb) sb.onchange = renderTable;
        const sd = document.getElementById('sort-desc');
        if (sd) sd.onchange = renderTable;

        document.querySelectorAll('#metric-tabs .tab-btn').forEach(btn => {
            btn.onclick = () => {
                document.querySelectorAll('#metric-tabs .tab-btn').forEach(b => b.classList.remove('active'));
                btn.classList.add('active');
                renderMetricsChart(btn.dataset.metric);
            };
        });
        renderMetricsChart('yield');
    } catch(e) {
        console.error('loadCompare failed:', e);
        throw e;
    }
}

function renderTable() {
    const provider = document.getElementById('provider-filter')?.value || '';
    const sortBy = document.getElementById('sort-by')?.value || 'current_yield';
    const desc = document.getElementById('sort-desc')?.checked || true;
    let etfs = provider ? allEtfs.filter(e => e.provider === provider) : [...allEtfs];
    etfs.sort((a, b) => {
        const va = a[sortBy] ?? (desc ? -Infinity : Infinity);
        const vb = b[sortBy] ?? (desc ? -Infinity : Infinity);
        return desc ? vb - va : va - vb;
    });
    document.querySelectorAll('#etf-table th').forEach(th => {
        const k = th.dataset.sort;
        if (!k) return;
        th.innerHTML = th.innerHTML.replace(/ [▲▼]/, '');
        if (k === sortBy) th.innerHTML += desc ? ' ▼' : ' ▲';
    });
    const tbody = document.querySelector('#etf-table tbody');
    if (!tbody) return;
    tbody.innerHTML = etfs.map(e => `
        <tr>
            <td><strong>${e.ticker}</strong></td>
            <td title="${e.name}">${(e.name||'').length > 42 ? e.name.slice(0,40)+'…' : e.name}</td>
            <td>${e.provider}</td>
            <td>${e.inception_date || '--'}</td>
            <td class="yield-col">${pct(e.current_yield)}</td>
            <td>${pct(e.avg_yield_since_inception)}</td>
            <td class="${e.distribution_coverage >= 1 ? 'positive' : 'negative'}">${fmt(e.distribution_coverage, 'x')}</td>
            <td class="${(e.tax_treatment_score||0) >= 0.7 ? 'positive' : (e.tax_treatment_score||0) >= 0.3 ? '' : 'negative'}">${e.tax_treatment_score != null ? (e.tax_treatment_score*100).toFixed(0) + '%' : '--'}</td>
            <td class="${(e.income_stability_score||0) >= 0.65 ? 'positive' : (e.income_stability_score||0) >= 0.4 ? '' : 'negative'}">${e.income_stability_score != null ? (e.income_stability_score*100).toFixed(0) + '%' : '--'}</td>
            <td class="${e.sharpe_ratio >= 0 ? 'positive' : 'negative'}">${fmt(e.sharpe_ratio)}</td>
            <td>${fmt(e.sortino_ratio)}</td>
            <td>${fmt(e.calmar_ratio)}</td>
            <td class="${e.total_return_1yr >= 0 ? 'positive' : 'negative'}">${pct(e.total_return_1yr)}</td>
            <td>${pct(e.total_return_3yr)}</td>
            <td>${pct(e.total_return_5yr)}</td>
            <td class="${e.available_income_10k != null && e.available_income_10k < 0 ? 'negative' : ''}">${e.available_income_10k != null ? '$' + Number(e.available_income_10k).toLocaleString() : '--'}</td>
            <td class="${e.nav_annual_change >= 0 ? 'positive' : 'negative'}">${pct(e.nav_annual_change)}</td>
            <td>${fmt(e.beta_sp500)}</td>
            <td>${fmt(e.correlation_sp500)}</td>
        </tr>
    `).join('');

    // Click-to-sort on column headers
    document.querySelectorAll('#etf-table th[data-sort]').forEach(th => {
        th.style.cursor = 'pointer';
        th.onclick = () => {
            const field = th.dataset.sort;
            const sb = document.getElementById('sort-by');
            const sd = document.getElementById('sort-desc');
            if (!sb || !sd) return;
            if (sb.value === field) {
                sd.checked = !sd.checked; // toggle direction
            } else {
                sb.value = field;
                sd.checked = true; // default descending
            }
            renderTable();
        };
    });
}

function renderMetricsChart(metric) {
    if (!allEtfs.length) return;
    const canvas = document.getElementById('metrics-chart');
    if (!canvas) return;
    const ctx = canvas.getContext('2d');
    if (metricsChart) metricsChart.destroy();

    // Register threshold line plugin once
    if (!Chart.registry.plugins.get('threshold-line')) {
        Chart.register({
            id: 'threshold-line',
            afterDraw: function(chart) {
                const threshold = chart.options._thresholdLine;
                if (threshold === undefined) return;
                const ctx = chart.ctx;
                const yScale = chart.scales.y;
                const xAxis = chart.scales.x;
                if (!yScale || !xAxis) return;
                const yPos = yScale.getPixelForValue(threshold);
                ctx.save();
                ctx.beginPath();
                ctx.moveTo(xAxis.left, yPos);
                ctx.lineTo(xAxis.right, yPos);
                ctx.strokeStyle = 'rgba(240, 160, 48, 0.8)';
                ctx.lineWidth = 2;
                ctx.setLineDash([5, 3]);
                ctx.stroke();
                ctx.fillStyle = 'rgba(240, 160, 48, 0.8)';
                ctx.font = '10px sans-serif';
                ctx.fillText(threshold + 'x', xAxis.right - 20, yPos - 4);
                ctx.restore();
            }
        });
    }

    let labels, data, label, threshold;

    switch (metric) {
        case 'yield':
            const byYield = [...allEtfs].filter(e => e.current_yield != null).sort((a,b) => b.current_yield - a.current_yield);
            labels = byYield.map(e => e.ticker).reverse();
            data = { current: byYield.map(e => e.current_yield).reverse(), avg: byYield.map(e => e.avg_yield_since_inception || 0).reverse() };
            label = 'Current Yield %';
            break;
        case 'coverage':
            const byCov = [...allEtfs].filter(e => e.distribution_coverage != null).sort((a,b) => b.distribution_coverage - a.distribution_coverage);
            labels = byCov.map(e => e.ticker).reverse();
            const covVals = byCov.map(e => e.distribution_coverage).reverse();
            data = { coverage: covVals };
            data._colors = covVals.map(v => v >= 1 ? '#46b97e' : '#e74c5c');
            label = 'Distribution Coverage Ratio (x) — green ≥ 1x, red < 1x';
            threshold = 1;
            break;
        case 'sharpe':
            const bySh = [...allEtfs].filter(e => e.sharpe_ratio != null).sort((a,b) => b.sharpe_ratio - a.sharpe_ratio);
            labels = bySh.map(e => e.ticker).reverse();
            const shIncep = bySh.map(e => e.sharpe_ratio).reverse();
            const shT12 = bySh.map(e => e.sharpe_t12 ?? 0).reverse();
            data = { sharpe_incep: shIncep, sharpe_t12: shT12 };
            data._colors = {};
            label = 'Sharpe Ratio — since inception (blue) vs T12M (orange)';
            break;
        case 'returns':
            const byRet = [...allEtfs].filter(e => e.total_return_1yr != null).sort((a,b) => b.total_return_1yr - a.total_return_1yr);
            labels = byRet.map(e => e.ticker).reverse();
            data = { t12: byRet.map(e => e.total_return_1yr).reverse() };
            data._colors = data.t12.map(v => v >= 0 ? '#46b97e' : '#e74c5c');
            label = 'Total Return T12M %';
            break;
        default: return;
    }

    const datasets = [];
    if (data.current) {
        datasets.push({ label: 'Current Yield', data: data.current, backgroundColor: '#4fc3f7', borderRadius: 2 });
    }
    if (data.avg) {
        datasets.push({ label: 'Avg Yield (Inception)', data: data.avg, backgroundColor: '#46b97e', borderRadius: 2 });
    }
    if (data.coverage) {
        datasets.push({ label: 'Distribution Coverage', data: data.coverage, backgroundColor: data._colors || '#4a90d9', borderRadius: 2 });
    }
    if (data.sharpe_incep) {
        datasets.push({ label: 'Sharpe (Inception)', data: data.sharpe_incep, backgroundColor: data.sharpe_incep.map(v => v >= 0 ? '#4fc3f7' : '#e74c5c'), borderRadius: 2 });
    }
    if (data.sharpe_t12) {
        datasets.push({ label: 'Sharpe (T12M)', data: data.sharpe_t12, backgroundColor: data.sharpe_t12.map(v => v >= 0 ? 'rgba(70,185,126,0.7)' : 'rgba(231,76,92,0.7)'), borderRadius: 2 });
    }
    if (data.t12) {
        datasets.push({ label: 'T12M Total Return', data: data.t12, backgroundColor: data._colors || '#46b97e', borderRadius: 2 });
    }

    metricsChart = new Chart(ctx, {
        type: 'bar',
        data: { labels, datasets },
        options: {
            responsive: true, maintainAspectRatio: false,
            _thresholdLine: threshold,
            plugins: {
                legend: { labels: { color: '#ccc', font: { size: 10 } } },
                title: { display: true, text: label, color: '#e8eaed', font: { size: 12 } },
            },
            scales: {
                x: { grid: { color: '#1e2538' }, ticks: { color: '#888', maxRotation: 90, font: { size: 6 } } },
                y: {
                    grid: { color: '#1e2538' }, ticks: { color: '#888' },
                }
            }
        }
    });

    // Add threshold line annotation
    if (threshold !== undefined) {
    }
}

// === DISTRIBUTION YIELD ===
async function loadDistYield() {
    try {
        const etfs = await (await fetch(`${API}/etfs?sort_by=current_yield&sort_dir=desc`)).json();
        const el = document.getElementById('dist-yield-content');
        if (!el) return;
        el.innerHTML = `<div class="quick-lists">
            <div class="quick-list"><h3>🔝 Highest Current Yield</h3>
                ${etfs.slice(0, 15).map(e => `<div class="ql-item"><span data-ticker="${e.ticker}">${e.ticker}</span><span class="yield-col">${pct(e.current_yield)}</span></div>`).join('')}
            </div>
            <div class="quick-list"><h3>⚠️ Biggest Yield Gap (Current vs Avg)</h3>
                ${etfs.filter(e => e.avg_yield_since_inception).sort((a,b) => Math.abs(b.current_yield - b.avg_yield_since_inception) - Math.abs(a.current_yield - a.avg_yield_since_inception)).slice(0, 15).map(e =>
                    `<div class="ql-item"><span data-ticker="${e.ticker}">${e.ticker}</span><span class="${Math.abs(e.current_yield - e.avg_yield_since_inception) > 10 ? 'negative' : ''}">${pct(e.current_yield)} vs ${pct(e.avg_yield_since_inception)}</span></div>`
                ).join('')}
            </div>
        </div>`;
    } catch(e) { console.warn('loadDistYield:', e.message); }
}

// === DISTRIBUTION COVERAGE ===
async function loadDistCoverage() {
    try {
        const best = await (await fetch(`${API}/etfs?sort_by=distribution_coverage&sort_dir=desc`)).json();
        const worst = await (await fetch(`${API}/etfs?sort_by=distribution_coverage&sort_dir=asc`)).json();
        const el = document.getElementById('dist-coverage-content');
        if (!el) return;
        el.innerHTML = `<div class="quick-lists">
            <div class="quick-list"><h3>✅ Best Coverage (1-2x ideal)</h3>
                ${best.slice(0, 15).map(e => `<div class="ql-item"><span data-ticker="${e.ticker}">${e.ticker} (${pct(e.current_yield)})</span><span style="color:var(--green)">${fmt(e.distribution_coverage, 'x')}</span></div>`).join('')}
            </div>
            <div class="quick-list"><h3>⚠️ Worst Coverage</h3>
                ${worst.filter(e => e.distribution_coverage !== null).slice(0, 15).map(e => `<div class="ql-item"><span data-ticker="${e.ticker}">${e.ticker} (${pct(e.current_yield)})</span><span style="color:var(--red)">${fmt(e.distribution_coverage, 'x')}</span></div>`).join('')}
            </div>
        </div>`;
    } catch(e) { console.warn('loadDistCoverage:', e.message); }
}

// === NAV EROSION ===
async function loadNavErosion() {
    try {
        const all = await (await fetch(`${API}/etfs?sort_by=nav_annual_change&sort_dir=desc`)).json();
        const el = document.getElementById('nav-erosion-content');
        if (!el) return;

        // All ETFs with NAV data, sorted descending
        const chartData = all.filter(e => e.nav_annual_change !== null).reverse();
        const labels = chartData.map(e => e.ticker);
        const values = chartData.map(e => e.nav_annual_change);
        const colors = values.map(v => v >= 0 ? '#46b97e' : '#e74c5c');

        // Render list + chart
        el.innerHTML = `
            <p class="subtitle" style="color:var(--text-dim);font-size:0.82em;margin-bottom:12px">NAV Change since inception — Negative = capital loss even before distributions.</p>
            <div style="display:grid;grid-template-columns:1fr 1fr;gap:14px;margin-bottom:16px">
                <div class="quick-list"><h3>📈 Strongest NAV Growth</h3>
                    ${chartData.slice(-8).reverse().map(e => `<div class="ql-item"><span data-ticker="${e.ticker}">${e.ticker} (${pct(e.current_yield)})</span><span class="positive">${pct(e.nav_annual_change)}</span></div>`).join('')}
                </div>
                <div class="quick-list"><h3>📉 Worst NAV Erosion</h3>
                    ${chartData.slice(0, 8).map(e => `<div class="ql-item"><span data-ticker="${e.ticker}">${e.ticker} (${pct(e.current_yield)})</span><span class="negative">${pct(e.nav_annual_change)}</span></div>`).join('')}
                </div>
            </div>
            <div class="chart-container" style="height:1200px;overflow-y:auto">
                <canvas id="nav-erosion-chart"></canvas>
            </div>`;

        // Create vertical bar chart with all tickers
        const canvas = document.getElementById('nav-erosion-chart');
        if (!canvas) return;
        const ctx = canvas.getContext('2d');
        if (window.navChart) window.navChart.destroy();

        window.navChart = new Chart(ctx, {
            type: 'bar',
            data: { labels, datasets: [{
                label: 'NAV Change Since Inception',
                data: values,
                backgroundColor: colors,
                borderRadius: 2,
            }]},
            options: {
                responsive: true, maintainAspectRatio: false,
                plugins: {
                    legend: { display: false },
                    title: { display: true, text: 'NAV Change Since Inception', color: '#e8eaed', font: { size: 13 } },
                },
                scales: {
                    x: { grid: { color: '#1e2538' }, ticks: { color: '#888', maxRotation: 90, font: { size: 6 } } },
                    y: { grid: { color: '#1e2538' }, ticks: { color: '#888', callback: v => v + '%' } },
                }
            }
        });
    } catch(e) { console.warn('loadNavErosion:', e.message); throw e; }
}

// === INVESTMENT GROWTH CHART ===
async function loadInvestmentGrowth() {
    try {
        const canvas = document.getElementById('growth-chart');
        const statusEl = document.getElementById('growth-status');
        console.log('loadInvestmentGrowth: canvas=', !!canvas);
        if (!canvas) return;
        const ctx = canvas.getContext('2d');
        if (growthChart) growthChart.destroy();

        const data = await (await fetch(`${API}/price-growth?period=${currentPeriod}`)).json();
        console.log('loadInvestmentGrowth: labels=', data.labels?.length, 'datasets=', data.datasets?.length);
        if (!data.labels || data.labels.length === 0) {
            if (statusEl) statusEl.textContent = '⚠ No data available for this period';
            return;
        }

        // Hide status, show canvas
        if (statusEl) statusEl.style.display = 'none';
        canvas.style.display = 'block';

        // Generate semi-transparent colors for each ticker
        const lineDatasets = data.datasets;
        const colors = lineDatasets.map((_, i) => {
            const hue = (i * 137.5) % 360;
            return `hsla(${hue}, 60%, 55%, 0.5)`;
        });

        growthChart = new Chart(ctx, {
            type: 'line',
            data: {
                labels: data.labels,
                datasets: lineDatasets.map((ds, i) => ({
                    label: ds.ticker,
                    data: ds.data,
                    borderColor: colors[i],
                    backgroundColor: 'transparent',
                    borderWidth: 1.5,
                    pointRadius: 0,
                    pointHoverRadius: 3,
                    tension: 0.1,
                    spanGaps: true,
                }))
            },
            options: {
                responsive: true, maintainAspectRatio: false,
                animation: false,
                interaction: { mode: 'nearest', intersect: false },
                plugins: {
                    legend: { display: false },
                    tooltip: {
                        mode: 'nearest',
                        intersect: false,
                        callbacks: {
                            title: (items) => items[0].label,
                            label: (item) => {
                                const v = item.raw;
                                return `${item.dataset.label}: $${v != null ? v.toLocaleString() : 'N/A'}`;
                            }
                        }
                    },
                    title: {
                        display: true,
                        text: `$10,000 Growth — ${currentPeriod === '1yr' ? 'Trailing 12M' : currentPeriod === 'max' ? 'Full History' : 'Trailing ' + currentPeriod.toUpperCase()}`,
                        color: '#e8eaed', font: { size: 13 }
                    }
                },
                scales: {
                    x: {
                        grid: { color: '#1e2538' },
                        ticks: { color: '#888', maxRotation: 45, font: { size: 7 } },
                    },
                    y: {
                        grid: { color: '#1e2538' },
                        ticks: { color: '#888', callback: v => '$' + v.toLocaleString() },
                    }
                }
            }
        });
        console.log('loadInvestmentGrowth: chart created');
    } catch(e) {
        console.warn('loadInvestmentGrowth error:', e.message, e.stack);
        const statusEl2 = document.getElementById('growth-status');
        if (statusEl2) statusEl2.textContent = '⚠ Error: ' + e.message;
    }
}

// === TOTAL RETURN ===
async function loadTotalReturn() {
    try {
        const periods = [
            { key: 'total_return_1yr', label: '1 Year' },
            { key: 'total_return_3yr', label: '3 Year' },
            { key: 'total_return_5yr', label: '5 Year' },
            { key: 'total_return_10yr', label: '10 Year' },
        ];
        const all = await (await fetch(`${API}/etfs?sort_by=total_return_1yr&sort_dir=desc`)).json();
        const el = document.getElementById('total-return-content');
        if (!el) return;
        let html = '<div class="quick-lists">';
        periods.forEach(p => {
            const sorted = [...all].filter(e => e[p.key] !== null).sort((a,b) => b[p.key] - a[p.key]);
            html += `<div class="quick-list"><h3>Top 10 — ${p.label}</h3>
                ${sorted.slice(0, 10).map(e => `<div class="ql-item"><span data-ticker="${e.ticker}">${e.ticker}</span><span class="${e[p.key] >= 0 ? 'positive' : 'negative'}">${pct(e[p.key])}</span></div>`).join('')}
            </div>`;
        });
        html += '</div>';
        el.innerHTML = html;
    } catch(e) { console.warn('loadTotalReturn:', e.message); }
}

// === SHARPE / SORTINO / CALMAR ===
async function loadSharpe() {
    try {
        const all = await (await fetch(`${API}/etfs`)).json();
        const bySharpe = [...all].filter(e => e.sharpe_ratio !== null).sort((a,b) => b.sharpe_ratio - a.sharpe_ratio);
        const bySortino = [...all].filter(e => e.sortino_ratio !== null).sort((a,b) => b.sortino_ratio - a.sortino_ratio);
        const byCalmar = [...all].filter(e => e.calmar_ratio !== null).sort((a,b) => b.calmar_ratio - a.calmar_ratio);
        const el = document.getElementById('sharpe-content');
        if (!el) return;
        el.innerHTML = `<div class="quick-lists">
            <div class="quick-list"><h3>🎯 Best Sharpe Ratio</h3>
                ${bySharpe.slice(0, 12).map(e => `<div class="ql-item"><span data-ticker="${e.ticker}">${e.ticker}</span><span>${fmt(e.sharpe_ratio)}</span></div>`).join('')}
            </div>
            <div class="quick-list"><h3>🎯 Best Sortino Ratio</h3>
                ${bySortino.slice(0, 12).map(e => `<div class="ql-item"><span data-ticker="${e.ticker}">${e.ticker}</span><span>${fmt(e.sortino_ratio)}</span></div>`).join('')}
            </div>
            <div class="quick-list" style="grid-column:1/3;margin-top:10px"><h3>🎯 Best Calmar Ratio</h3>
                ${byCalmar.slice(0, 12).map(e => `<div class="ql-item"><span data-ticker="${e.ticker}">${e.ticker} — ${e.name.slice(0,40)}</span><span>${fmt(e.calmar_ratio)}</span></div>`).join('')}
            </div>
        </div>`;
    } catch(e) { console.warn('loadSharpe:', e.message); }
}

// === TRAILING 12M PERFORMANCE ===
async function loadT12Perf() {
    try {
        const all = await (await fetch(`${API}/etfs?sort_by=total_return_1yr&sort_dir=desc`)).json();
        const best = all.filter(e => e.total_return_1yr !== null);
        const worst = [...all].filter(e => e.total_return_1yr !== null).sort((a,b) => a.total_return_1yr - b.total_return_1yr);
        const el = document.getElementById('t12-perf-content');
        if (!el) return;
        el.innerHTML = `<div class="quick-lists">
            <div class="quick-list"><h3>🏆 Best T12 Total Return</h3>
                ${best.slice(0, 15).map(e => `<div class="ql-item"><span data-ticker="${e.ticker}">${e.ticker} — ${e.provider}</span><span class="positive">${pct(e.total_return_1yr)}</span></div>`).join('')}
            </div>
            <div class="quick-list"><h3>⚠️ Worst T12 Total Return</h3>
                ${worst.slice(0, 15).map(e => `<div class="ql-item"><span data-ticker="${e.ticker}">${e.ticker} — ${e.provider}</span><span class="negative">${pct(e.total_return_1yr)}</span></div>`).join('')}
            </div>
        </div>`;
    } catch(e) { console.warn('loadT12Perf:', e.message); }
}

// === BETA CHART ===
async function loadBetaChart() {
    try {
        const PROVIDER_COLORS = {
            'Adams Funds':'#4fc3f7','Alerian':'#f0a030','Amplify':'#46b97e','Bitwise':'#e74c5c','BlackRock':'#4a90d9',
            'Charles Schwab':'#9b59b6','Cohen & Steers':'#1abc9c','Cornerstone':'#e67e22','Crosshares':'#2ecc71',
            'Curve':'#e91e63','Defiance':'#f39c12','ETRACS':'#3498db','First Trust':'#2980b9','Global X':'#8e44ad',
            'GraniteShares':'#16a085','Invesco':'#d35400','J.P. Morgan':'#c0392b','Kurv':'#7f8c8d','NEOS':'#27ae60',
            'Overlay Shares':'#2c3e50','PIMCO':'#95a5a6','ProShares':'#f1c40f','REX':'#e67e22','Reeves':'#1abc9c',
            'Roundhill':'#3498db','SPDR':'#9b59b6','STF':'#e74c5c','Saba':'#f0a030','Simplify':'#46b97e',
            'Swan':'#4fc3f7','TappAlpha':'#4a90d9','Tidal':'#2ecc71','VanEck':'#e91e63','Vanguard':'#f39c12',
            'Virtus':'#2980b9','West Shore':'#8e44ad','WisdomTree':'#16a085','YieldMax':'#d35400','iShares':'#c0392b',
        };
        let betaChart = window.betaChartInstance;
        const canvas = document.getElementById('beta-chart');
        if (!canvas) return;
        const ctx = canvas.getContext('2d');

        function renderPeriod(period) {
            const periodLabel = period === 't12m' ? '1yr' : period === '3yr' ? '3yr' : 'full';
            fetch(`${API}/beta-correlation?period=${periodLabel}`).then(r => r.json()).then(data => {
                const points = data.points || [];
                // Group by provider for legend
                const providers = [...new Set(points.map(p => p.provider))].sort();
                const legendEl = document.getElementById('beta-provider-legend');
                if (legendEl) {
                    legendEl.innerHTML = providers.map(p => {
                        const c = PROVIDER_COLORS[p] || '#888';
                        return `<span style="display:inline-flex;align-items:center;gap:4px"><span style="display:inline-block;width:10px;height:10px;border-radius:50%;background:${c}"></span>${p}</span>`;
                    }).join('');
                }

                if (betaChart) betaChart.destroy();
                betaChart = new Chart(ctx, {
                    type: 'scatter',
                    data: { datasets: points.map(p => ({
                        label: p.ticker,
                        data: [{ x: p.beta, y: p.correlation }],
                        backgroundColor: PROVIDER_COLORS[p.provider] || '#888',
                        borderColor: 'rgba(255,255,255,0.3)',
                        borderWidth: 1,
                        pointRadius: 6,
                        pointHoverRadius: 9,
                    }))},
                    options: {
                        responsive: true, maintainAspectRatio: false,
                        plugins: {
                            tooltip: {
                                callbacks: {
                                    label: (c) => {
                                        const p = points[c.datasetIndex];
                                        return `${p.ticker}: β=${p.beta?.toFixed(2)}, ρ=${p.correlation?.toFixed(2)}, Yield=${p.yield?.toFixed(1)}%`;
                                    },
                                    afterLabel: (c) => {
                                        const p = points[c.datasetIndex];
                                        return `Provider: ${p.provider}`;
                                    }
                                }
                            },
                            legend: { display: false },
                            title: { display: true, text: `Beta & Correlation with S&P 500 — ${period === 't12m' ? 'Trailing 12M' : period === '3yr' ? 'Trailing 3Y' : 'Full History'}`, color: '#e8eaed', font: { size: 13 } }
                        },
                        scales: {
                            x: {
                                title: { display: true, text: 'Beta vs S&P 500 (1.0 = moves in line with market)', color: '#888' },
                                grid: { color: '#1e2538' }, ticks: { color: '#888' }, min: -0.5, max: 2.5,
                            },
                            y: {
                                title: { display: true, text: 'Correlation with S&P 500', color: '#888' },
                                grid: { color: '#1e2538' }, ticks: { color: '#888' }, min: -0.3, max: 1.1,
                            }
                        }
                    }
                });
                window.betaChartInstance = betaChart;
            });
        }

        // Register reference lines plugin once at top level
        if (!Chart.registry.plugins.get('beta-ref-lines')) {
            Chart.register({
                id: 'beta-ref-lines',
                afterDraw: function(chart) {
                    const x = chart.scales.x;
                    const y = chart.scales.y;
                    if (!x || !y) return;
                    const ctx = chart.ctx;
                    ctx.save();
                    // Vertical line at beta=1
                    const x1 = x.getPixelForValue(1);
                    if (x1 > x.left && x1 < x.right) {
                        ctx.beginPath();
                        ctx.moveTo(x1, y.top);
                        ctx.lineTo(x1, y.bottom);
                        ctx.strokeStyle = 'rgba(255,255,255,0.12)';
                        ctx.lineWidth = 1;
                        ctx.setLineDash([4, 4]);
                        ctx.stroke();
                    }
                    // Horizontal line at correlation=0
                    const y0 = y.getPixelForValue(0);
                    if (y0 > y.top && y0 < y.bottom) {
                        ctx.beginPath();
                        ctx.moveTo(x.left, y0);
                        ctx.lineTo(x.right, y0);
                        ctx.strokeStyle = 'rgba(255,255,255,0.12)';
                        ctx.lineWidth = 1;
                        ctx.setLineDash([4, 4]);
                        ctx.stroke();
                    }
                    ctx.restore();
                }
            });
        }

        // Wire up period tabs
        document.querySelectorAll('#beta-period-tabs .tab-btn').forEach(btn => {
            btn.onclick = () => {
                document.querySelectorAll('#beta-period-tabs .tab-btn').forEach(b => b.classList.remove('active'));
                btn.classList.add('active');
                renderPeriod(btn.dataset.period);
            };
        });
        renderPeriod('t12m');
    } catch(e) { console.warn('loadBetaChart:', e.message); }
}

// === RETURN SCATTER CHART ===
async function loadReturnChart() {
    try {
        const all = await (await fetch(`${API}/etfs`)).json();
        const chartData = all.filter(e => e.total_return_3yr !== null && e.sharpe_ratio !== null && e.current_yield !== null)
            .map(e => ({ x: e.sharpe_ratio, y: e.total_return_3yr, ticker: e.ticker, yield: e.current_yield, provider: e.provider }));
        const canvas = document.getElementById('return-scatter-chart');
        if (!canvas) return;
        const ctx = canvas.getContext('2d');
        if (retChart) retChart.destroy();
        retChart = new Chart(ctx, {
            type: 'scatter',
            data: { datasets: [{ label: 'ETFs', data: chartData, backgroundColor: chartData.map(d => d.yield > 20 ? '#e74c5c' : d.yield > 10 ? '#f0a030' : '#4a90d9'), pointRadius: 5, pointHoverRadius: 8 }] },
            options: {
                responsive: true, maintainAspectRatio: false,
                plugins: { tooltip: { callbacks: { label: (c) => `${chartData[c.dataIndex].ticker}: 3yr ret=${chartData[c.dataIndex].y.toFixed(1)}%, sharpe=${chartData[c.dataIndex].x}, yield=${chartData[c.dataIndex].yield}%` } }, legend: { display: false }, title: { display: true, text: '3-Year Return vs Sharpe Ratio', color: '#e8eaed' } },
                scales: { x: { title: { display: true, text: 'Sharpe Ratio', color: '#888' }, grid: { color: '#1e2538' }, ticks: { color: '#888' } }, y: { title: { display: true, text: '3-Year Total Return %', color: '#888' }, grid: { color: '#1e2538' }, ticks: { color: '#888' } } }
            }
        });
    } catch(e) { console.warn('loadReturnChart:', e.message); }
}

// === PORTFOLIO BUILDER ===
async function setupPortfolio() {
    try {
        if (allEtfs.length === 0) allEtfs = await (await fetch(`${API}/etfs`)).json();
        const si = document.getElementById('pf-search');
        const dd = document.getElementById('pf-search-results');
        if (!si || !dd) return;
        si.oninput = () => {
            const q = si.value.toLowerCase();
            if (q.length < 1) { dd.classList.remove('show'); return; }
            const matches = allEtfs.filter(e => e.ticker.toLowerCase().includes(q) || e.name.toLowerCase().includes(q)).slice(0, 8);
            dd.innerHTML = matches.map(e => `<div class="pf-dropdown-item" data-t="${e.ticker}">
                <span><span class="pf-dd-ticker" data-ticker="${e.ticker}">${e.ticker}</span> ${e.name.slice(0,28)}</span>
                <span class="pf-dd-yield">${pct(e.current_yield)}</span></div>`).join('');
            dd.classList.add('show');
            dd.querySelectorAll('.pf-dropdown-item').forEach(item => {
                item.onclick = () => {
                    const t = item.dataset.t;
                    if (portfolioEtfs.find(p => p.ticker === t)) return;
                    const e = allEtfs.find(x => x.ticker === t);
                    if (!e) return;
                    portfolioEtfs.push({ ticker: e.ticker, name: e.name, weight: 100 / (portfolioEtfs.length + 1), yield: e.current_yield });
                    const total = portfolioEtfs.reduce((s, p) => s + p.weight, 0);
                    if (Math.abs(total - 100) > 0.1) portfolioEtfs[0].weight += 100 - total;
                    renderPortfolio();
                    dd.classList.remove('show');
                    si.value = '';
                };
            });
        };
        si.onblur = () => setTimeout(() => dd.classList.remove('show'), 200);
        const ri = document.getElementById('pf-reinvest');
        if (ri) ri.oninput = function() { const v = document.getElementById('pf-reinvest-val'); if (v) v.textContent = this.value + '%'; };
        const sim = document.getElementById('pf-simulate');
        if (sim) sim.onclick = simulatePortfolio;
        renderPortfolio();
    } catch(e) { console.warn('setupPortfolio:', e.message); }
}

function renderPortfolio() {
    const el = document.getElementById('pf-selected');
    if (!el) return;
    if (!portfolioEtfs.length) { el.innerHTML = '<p class="hint">Search and add ETFs to your portfolio (4-8 recommended)</p>'; return; }
    el.innerHTML = portfolioEtfs.map((p, i) => `
        <div class="pf-selected-item">
            <span><strong>${p.ticker}</strong> <span style="color:var(--text-dim);font-size:0.78em">${p.name.slice(0,20)}</span></span>
            <span><input type="number" class="weight-input" value="${Math.round(p.weight)}" min="0" max="100" onchange="window.updateWeight(${i},this.value)" style="width:48px;background:var(--card-bg);color:var(--text);border:1px solid var(--border);padding:2px 4px;border-radius:3px;text-align:right;font-size:0.85em">%
            <button onclick="window.removeEtf(${i})" style="background:none;border:none;color:var(--red);cursor:pointer;margin-left:4px">✕</button></span>
        </div>`).join('');
}
window.updateWeight = (i, v) => { portfolioEtfs[i].weight = parseInt(v) || 0; renderPortfolio(); };
window.removeEtf = (i) => { portfolioEtfs.splice(i, 1); if (portfolioEtfs.length) { const e = Math.floor(100 / portfolioEtfs.length); portfolioEtfs.forEach(p => p.weight = e); portfolioEtfs[0].weight += 100 - e * portfolioEtfs.length; } renderPortfolio(); };

async function simulatePortfolio() {
    if (!portfolioEtfs.length) return;
    try {
        const payload = {
            tickers: portfolioEtfs.map(p => ({ ticker: p.ticker, weight: Math.round(p.weight) })),
            initial_investment: parseInt(document.getElementById('pf-investment')?.value) || 25000,
            reinvest_pct: parseInt(document.getElementById('pf-reinvest')?.value),
            rebalance: document.getElementById('pf-rebalance')?.value,
            period: document.getElementById('pf-period')?.value || 'max',
        };
        const r = await (await fetch(`${API}/portfolio/simulate`, { method: 'POST', headers: { 'Content-Type': 'application/json' }, body: JSON.stringify(payload) })).json();
        ['pf-final-val', 'pf-cash', 'pf-total-ret', 'pf-nav-chg'].forEach(id => {
            const el = document.getElementById(id);
            if (!el) return;
            if (id === 'pf-final-val') el.textContent = '$' + Number(r.final_value).toLocaleString();
            else if (id === 'pf-cash') el.textContent = '$' + Number(r.total_cash_received).toLocaleString();
            else if (id === 'pf-total-ret') el.textContent = r.total_return_pct + '%';
            else if (id === 'pf-nav-chg') el.textContent = r.nav_change_pct + '%';
        });
        const res = document.querySelector('.pf-results');
        if (res) res.style.display = 'block';

        // Portfolio info header
        const infoEl = document.getElementById('pf-info');
        if (infoEl) {
            const tickerList = portfolioEtfs.map(p => '<strong>' + p.ticker + '</strong>').join(', ');
            const start = new Date(r.start_date);
            const end = new Date(start);
            end.setMonth(end.getMonth() + r.months);
            const yrs = (r.months / 12).toFixed(1);
            infoEl.innerHTML = 'ETF(s): ' + tickerList + ' | Period: ' +
                start.toLocaleDateString('en-US', {year:'numeric',month:'2-digit',day:'2-digit'}) + ' — ' +
                end.toLocaleDateString('en-US', {year:'numeric',month:'2-digit',day:'2-digit'}) +
                ' (' + yrs + ' yrs) | Start date set by shortest-history ETF in portfolio';
        }

        const labels = Array.from({ length: r.monthly_nav.length }, (_, i) => {
            const d = new Date(r.start_date); d.setMonth(d.getMonth() + i + 1);
            return d.toLocaleDateString('en-US', { month: 'short', year: '2-digit' });
        });

        // Store data for tab switching
        window._pfData = { r, labels };
        drawPfChart('value');

        // Wire tab switching
        const tabBar = document.getElementById('pf-chart-tabs');
        if (tabBar) {
            tabBar.querySelectorAll('.tab-btn').forEach(btn => {
                btn.onclick = () => {
                    tabBar.querySelectorAll('.tab-btn').forEach(b => b.classList.remove('active'));
                    btn.classList.add('active');
                    drawPfChart(btn.dataset.pfchart);
                };
            });
        }
    } catch(e) { console.error('simulatePortfolio:', e); }
}

function drawPfChart(tab) {
    if (!window._pfData) return;
    const { r, labels } = window._pfData;
    if (pfChartNav) { pfChartNav.destroy(); pfChartNav = null; }
    const ctx = document.getElementById('pf-chart-canvas')?.getContext('2d');
    if (!ctx) return;

    // Show/hide stat boxes
    const navStats = document.getElementById('pf-nav-stats');
    if (navStats) navStats.style.display = tab === 'nav' ? 'flex' : 'none';
    const incStats = document.getElementById('pf-income-stats');
    if (incStats) incStats.style.display = tab === 'income' ? 'flex' : 'none';

    // Update NAV stats
    if (tab === 'nav') {
        const totalChange = r.monthly_nav.length > 0
            ? r.monthly_nav[r.monthly_nav.length - 1] - r.initial_investment
            : 0;
        const years = r.months / 12;
        const annualized = years > 0
            ? (Math.pow(r.monthly_nav[r.monthly_nav.length - 1] / r.initial_investment, 1 / years) - 1) * 100
            : 0;
        const totalEl = document.getElementById('pf-nav-change-total');
        const annEl = document.getElementById('pf-nav-change-annual');
        if (totalEl) totalEl.textContent = (totalChange >= 0 ? '+' : '') + '$' + Number(totalChange).toLocaleString();
        if (annEl) annEl.textContent = (annualized >= 0 ? '+' : '') + annualized.toFixed(2) + '%/yr';
    }

    const sharedOpts = {
        responsive: true, maintainAspectRatio: false,
        plugins: {
            title: { display: true, text: '', color: '#e8eaed', font: { size: 13 } },
            legend: { labels: { color: '#ccc' } },
        },
        scales: {
            y: { ticks: { color: '#888', callback: v => '$' + v.toLocaleString() }, grid: { color: '#1e2538' } },
            x: { ticks: { color: '#888', maxTicksLimit: 12 }, grid: { color: '#1e2538' } },
        }
    };

    if (tab === 'value') {
        sharedOpts.plugins.title.text = 'Portfolio Value (with reinvestment) vs NAV Only (no reinvestment)';
        sharedOpts.plugins.legend.display = true;
        pfChartNav = new Chart(ctx, {
            type: 'line',
            data: {
                labels,
                datasets: [
                    { label: 'Portfolio Value', data: r.monthly_nav, borderColor: '#4fc3f7', backgroundColor: 'rgba(79,195,247,0.06)', fill: true, tension: 0.3, pointRadius: 0 },
                    { label: 'NAV Only (no reinvestment)', data: r.monthly_no_reinvest, borderColor: '#ffa726', backgroundColor: 'transparent', borderDash: [4,3], tension: 0.3, pointRadius: 0 },
                    { label: 'Initial', data: Array(labels.length).fill(r.initial_investment), borderColor: '#888', borderDash: [5,5], pointRadius: 0, borderWidth: 1 },
                ]
            }, options: sharedOpts
        });
    } else if (tab === 'income') {
        sharedOpts.plugins.title.text = 'Monthly Income';
        sharedOpts.plugins.legend.display = false;
        // Update income stats
        const monthlyInc = r.monthly_income || [];
        const avgInc = monthlyInc.length > 0 ? monthlyInc.reduce((a,b) => a+b, 0) / monthlyInc.length : 0;
        const annInc = avgInc * 12;
        const yieldCost = r.initial_investment > 0 ? (annInc / r.initial_investment) * 100 : 0;
        const avgEl = document.getElementById('pf-avg-income');
        const annEl2 = document.getElementById('pf-ann-income');
        const yocEl = document.getElementById('pf-yield-cost');
        if (avgEl) avgEl.textContent = '$' + Number(avgInc).toLocaleString();
        if (annEl2) annEl2.textContent = '$' + Number(annInc).toLocaleString();
        if (yocEl) yocEl.textContent = yieldCost.toFixed(1) + '%';
        pfChartNav = new Chart(ctx, {
            type: 'bar',
            data: { labels, datasets: [{ label: 'Income', data: r.monthly_income, backgroundColor: '#3696d3', borderRadius: 2 }] },
            options: sharedOpts
        });
    } else if (tab === 'nav') {
        sharedOpts.plugins.title.text = 'NAV Analysis — Portfolio Value & NAV Only';
        sharedOpts.plugins.legend.display = true;
        pfChartNav = new Chart(ctx, {
            type: 'line',
            data: {
                labels,
                datasets: [
                    { label: 'Portfolio Value (reinvested)', data: r.monthly_nav, borderColor: '#4fc3f7', backgroundColor: 'rgba(79,195,247,0.06)', fill: true, tension: 0.3, pointRadius: 0 },
                    { label: 'NAV Only (no reinvestment)', data: r.monthly_no_reinvest, borderColor: '#ffa726', backgroundColor: 'rgba(255,167,38,0.06)', fill: true, tension: 0.3, pointRadius: 0 },
                    { label: 'Initial', data: Array(labels.length).fill(r.initial_investment), borderColor: '#888', borderDash: [5,5], pointRadius: 0, borderWidth: 1 },
                ]
            }, options: sharedOpts
        });
    }
}

// === BEST PORTFOLIOS ===
function renderBestPortfolios(portfolios, table, singleCriterion) {
    table.innerHTML = portfolios.map((p, i) => `
        <div class="bp-row" style="cursor:pointer" data-pf='${encodeURIComponent(JSON.stringify(p.etfs || []))}'>
            <div class="bp-rank">#${i+1}</div>
            <div class="bp-metrics">
                <div class="bp-metric"><span class="val">$${Number(p.available_income_per_10k || p.monthly_income * 12 / 10).toLocaleString()}</span><span class="lbl">Avail Inc/10k <span class="info-tip" data-tip="Annualized average cash income per $10,000 invested. Higher is better for income seekers.">ⓘ</span></span></div>
                <div class="bp-metric"><span class="val">${p.avg_yield}%</span><span class="lbl">Avg Yield <span class="info-tip" data-tip="Average portfolio yield over the full backtest period. Based on actual dividends received.">ⓘ</span></span></div>
                <div class="bp-metric"><span class="val">${p.nav_change >= 0 ? '+' : ''}${p.nav_change}%</span><span class="lbl">NAV Change <span class="info-tip" data-tip="Price-only change in portfolio value. Excludes dividends. Negative = the portfolio principal shrank.">ⓘ</span></span></div>
                <div class="bp-metric"><span class="val">${p.total_return >= 0 ? '+' : ''}${p.total_return}%</span><span class="lbl">Total Return <span class="info-tip" data-tip="Total portfolio return including both NAV change and dividends received. Real-world performance.">ⓘ</span></span></div>
                <div class="bp-metric"><span class="val">${p.sharpe}</span><span class="lbl">Sharpe <span class="info-tip" data-tip="Risk-adjusted return. Higher = better return per unit of volatility. Above 1 is good.">ⓘ</span></span></div>
                <div class="bp-metric"><span class="val">${p.num_etfs || (p.etfs||[]).length}</span><span class="lbl">#ETFs <span class="info-tip" data-tip="Number of ETFs in this portfolio combination (randomized between 4-8).">ⓘ</span></span></div>
            </div>
            <div class="bp-etfs">${(p.etfs||[]).map(e => '<span class="bp-etf-tag' + (e.highlight ? ' highlight' : '') + '" data-ticker="' + e.ticker + '">' + e.ticker + ' ' + e.weight + '%</span>').join('')}</div>
        </div>`).join('');
    wireBestPortfolioClicks(table);
}
async function loadBestPortfolios() {
    try {
        const period = document.getElementById('bp-period')?.value || '1yr';
        const perEl = document.getElementById('bp-period');
        if (perEl) perEl.onchange = loadBestPortfolios;
        // Wire checkboxes
        document.querySelectorAll('.bp-sort-cb').forEach(cb => {
            cb.onchange = loadBestPortfolios;
        });
        const checked = [...document.querySelectorAll('.bp-sort-cb:checked')].map(cb => cb.value);
        const el = document.getElementById('bp-eligible');
        const table = document.getElementById('best-portfolios-table');
        if (!table) return;
        if (!checked.length) {
            table.innerHTML = '<p class="hint">Check at least one filter criterion above.</p>';
            if (el) el.textContent = '';
            return;
        }
        // Fetch top 25 for each checked criterion
        const results = await Promise.all(checked.map(async sortBy => {
            const d = await (await fetch(`${API}/best-portfolios?period=${period}&sort_by=${sortBy}`)).json();
            return { sortBy, eligible: d.eligible_etfs, portfolios: d.portfolios || [] };
        }));
        // Show eligible count from first result
        if (el && results.length) el.textContent = `${results[0].eligible} ETFs have 1+ years of history for this period.`;
        // Build portfolio index by ETF composition signature
        const sigMap = new Map(); // signature -> { portfolios: [{rank, sortBy, data}], ranks: {} }
        results.forEach((r, ri) => {
            r.portfolios.forEach((p, i) => {
                const sig = [...p.etfs].map(e => e.ticker).sort().join('|');
                if (!sigMap.has(sig)) sigMap.set(sig, { data: p, ranks: {}, sig });
                sigMap.get(sig).ranks[checked[ri]] = i + 1; // 1-based rank
                // Keep the first data object we saw (they're all similar)
            });
        });
        // If only one criterion, show that list directly
        if (checked.length === 1) {
            const r = results[0];
            renderBestPortfolios(r.portfolios, table, checked[0], null);
            return;
        }
        // Multiple criteria: find intersection
        const intersection = [];
        for (const [sig, entry] of sigMap) {
            const rankKeys = Object.keys(entry.ranks);
            // Must appear in ALL checked criteria
            if (checked.every(c => entry.ranks[c] !== undefined)) {
                const avgRank = checked.reduce((sum, c) => sum + entry.ranks[c], 0) / checked.length;
                intersection.push({ ...entry, avgRank });
            }
        }
        // Sort by average rank
        intersection.sort((a, b) => a.avgRank - b.avgRank);
        if (intersection.length === 0) {
            table.innerHTML = `<p class="hint">No portfolios rank in the top 25 across all checked criteria. Try checking fewer boxes.</p>`;
            return;
        }
        // Render intersection
        table.innerHTML = intersection.map((p, i) => {
            const data = p.data;
            const rankTags = checked.map(c => `<span class="bp-rank-badge">${({'income':'Income','total_return':'Total Ret','nav_change':'NAV','sharpe':'Sharpe','income_stability':'Stability','tax_treatment':'Tax'})[c]||c}: #${p.ranks[c]}</span>`).join(' ');
            return `<div class="bp-row" style="cursor:pointer" data-pf='${encodeURIComponent(JSON.stringify(data.etfs || []))}'>
                <div class="bp-rank">#${i+1}</div>
                <div class="bp-metrics">
                    <div class="bp-metric"><span class="val">$${Number(data.available_income_per_10k || data.monthly_income * 12 / 10).toLocaleString()}</span><span class="lbl">Avail Inc/10k <span class="info-tip" data-tip="Annualized average cash income per $10,000 invested. Higher is better for income seekers.">ⓘ</span></span></div>
                    <div class="bp-metric"><span class="val">${data.avg_yield}%</span><span class="lbl">Avg Yield <span class="info-tip" data-tip="Average portfolio yield over the full backtest period. Based on actual dividends received.">ⓘ</span></span></div>
                    <div class="bp-metric"><span class="val">${data.nav_change >= 0 ? '+' : ''}${data.nav_change}%</span><span class="lbl">NAV Change <span class="info-tip" data-tip="Price-only change in portfolio value. Excludes dividends. Negative = the portfolio principal shrank.">ⓘ</span></span></div>
                    <div class="bp-metric"><span class="val">${data.total_return >= 0 ? '+' : ''}${data.total_return}%</span><span class="lbl">Total Return <span class="info-tip" data-tip="Total portfolio return including both NAV change and dividends received. Real-world performance.">ⓘ</span></span></div>
                    <div class="bp-metric"><span class="val">${data.sharpe}</span><span class="lbl">Sharpe <span class="info-tip" data-tip="Risk-adjusted return. Higher = better return per unit of volatility. Above 1 is good.">ⓘ</span></span></div>
                    <div class="bp-metric"><span class="val">${data.num_etfs || (data.etfs||[]).length}</span><span class="lbl">#ETFs <span class="info-tip" data-tip="Number of ETFs in this portfolio combination (randomized between 4-8).">ⓘ</span></span></div>
                </div>
                <div class="bp-badges">${rankTags}</div>
                <div class="bp-etfs">${(data.etfs||[]).map(e => '<span class="bp-etf-tag' + (e.highlight ? ' highlight' : '') + '" data-ticker="' + e.ticker + '">' + e.ticker + ' ' + e.weight + '%</span>').join('')}</div>
            </div>`;
        }).join('');
        // Wire click-to-load
        wireBestPortfolioClicks(table);
    } catch(e) { console.warn('loadBestPortfolios:', e.message); }
}
function wireBestPortfolioClicks(table) {
    table.querySelectorAll('.bp-row').forEach(row => {
        row.onclick = () => {
            try {
                const raw = decodeURIComponent(row.dataset.pf);
                const etfs = JSON.parse(raw);
                if (!etfs || !etfs.length) return;
                const loaded = etfs.map(e => {
                    const info = allEtfs.find(x => x.ticker === e.ticker);
                    return {
                        ticker: e.ticker,
                        name: info ? info.name : e.ticker,
                        weight: parseFloat(e.weight) || (100 / etfs.length),
                        yield: info ? info.current_yield : null,
                    };
                });
                portfolioEtfs.length = 0;
                portfolioEtfs.push(...loaded);
                renderPortfolio();
                document.getElementById('portfolio')?.scrollIntoView({ behavior: 'smooth' });
                setTimeout(simulatePortfolio, 400);
            } catch(e) { console.warn('load best portfolio:', e); }
        };
    });
}
