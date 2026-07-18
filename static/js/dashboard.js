// High Yield Income ETF Dashboard - Client JS
const API = '/api';

// State
let allEtfs = [];
let pfChartNav = null;
let pfChartIncome = null;
let betaChart = null;
let portfolioEtfs = []; // {ticker, name, weight, yield}

// Navigation
document.querySelectorAll('.nav-link').forEach(link => {
    link.addEventListener('click', (e) => {
        e.preventDefault();
        document.querySelectorAll('.nav-link').forEach(l => l.classList.remove('active'));
        link.classList.add('active');
        document.querySelectorAll('.section').forEach(s => s.classList.remove('active'));
        const sectionId = link.dataset.section;
        document.getElementById(sectionId).classList.add('active');

        // Load section data
        if (sectionId === 'overview') loadOverview();
        if (sectionId === 'leaderboard') loadLeaderboard();
        if (sectionId === 'compare') loadCompareTable();
        if (sectionId === 'beta') loadBetaChart();
        if (sectionId === 'portfolio') setupPortfolio();
        if (sectionId === 'best') loadBestPortfolios();
    });
});

// === OVERVIEW ===
async function loadOverview() {
    const resp = await fetch(`${API}/stats`);
    const stats = await resp.json();
    document.getElementById('etf-count').textContent = stats.total_etfs;
    document.getElementById('ov-total').textContent = stats.total_etfs;
    document.getElementById('ov-providers').textContent = stats.total_providers;
    document.getElementById('qs-avg-yield').textContent = stats.avg_yield + '%';
    document.getElementById('qs-total').textContent = stats.total_etfs;
    document.getElementById('qs-providers').textContent = stats.total_providers;

    // Newest additions
    const newResp = await fetch(`${API}/etfs/new?limit=20`);
    const newEtfs = await newResp.json();
    document.getElementById('new-count').textContent = newEtfs.length;
    const grid = document.getElementById('new-etfs-grid');
    grid.innerHTML = newEtfs.map(e => `
        <div class="etf-card" title="${e.name} (inception: ${e.inception_date || 'N/A'})">
            <div class="ticker">${e.ticker}</div>
            <div class="name" title="${e.name}">${e.name}</div>
            <div class="yield">${e.current_yield != null ? e.current_yield + '%' : '--'}</div>
            <div class="return ${e.total_return_1yr >= 0 ? 'positive' : 'negative'}">${e.total_return_1yr != null ? e.total_return_1yr + '%' : '--'} T12</div>
        </div>
    `).join('');
}

// === LEADERBOARD ===
async function loadLeaderboard() {
    const resp = await fetch(`${API}/leaderboard`);
    const data = await resp.json();

    // Update stats
    document.getElementById('qs-avg-yield').textContent = data.stats.avg_yield + '%';

    const grid = document.getElementById('leaderboard-grid');
    const catLabels = {
        'highest_yield': '💰 Highest Current Yield',
        'best_dist_coverage': '📊 Best Distribution Coverage',
        'best_total_return_1yr': '📈 Best Total Return (1 Year)',
        'best_total_return_3yr': '📈 Best Total Return (3 Year)',
        'best_total_return_5yr': '📈 Best Total Return (5 Year)',
        'best_total_return_10yr': '📈 Best Total Return (10 Year)',
        'best_sharpe': '🎯 Best Sharpe Ratio',
        'best_sortino': '🎯 Best Sortino Ratio',
        'best_calmar': '🎯 Best Calmar Ratio',
        'best_nav_growth': '📉 Best NAV Growth',
    };

    let html = '';
    for (const [key, entries] of Object.entries(data.categories)) {
        html += `<div class="lb-category">
            <div class="lb-cat-header">${catLabels[key] || key}</div>`;
        entries.slice(0, 10).forEach((e, i) => {
            let val;
            if (key.includes('yield')) val = e.current_yield + '%';
            else if (key.includes('dist_coverage')) val = e.distribution_coverage + 'x';
            else if (key.includes('total_return')) {
                const period = key.replace('best_', '');
                val = (e[period] != null ? e[period] + '%' : 'N/A');
            }
            else if (key.includes('sharpe')) val = e.sharpe_ratio;
            else if (key.includes('sortino')) val = e.sortino_ratio;
            else if (key.includes('calmar')) val = e.calmar_ratio;
            else if (key.includes('nav_growth')) val = e.nav_annual_change + '%';
            else val = '--';

            html += `<div class="lb-row">
                <span class="lb-rank">#${i + 1}</span>
                <span class="lb-ticker">${e.ticker}</span>
                <span class="lb-name" title="${e.name}">${e.name}</span>
                <span class="lb-val">${val}</span>
                <span class="lb-tier ${e.tier}"></span>
            </div>`;
        });
        html += `</div>`;
    }
    grid.innerHTML = html;
}

// === COMPARE TABLE ===
async function loadCompareTable() {
    if (allEtfs.length === 0) {
        const resp = await fetch(`${API}/etfs`);
        allEtfs = await resp.json();
    }

    // Populate provider filter
    const providers = [...new Set(allEtfs.map(e => e.provider))].sort();
    const sel = document.getElementById('provider-filter');
    sel.innerHTML = '<option value="">All</option>' + providers.map(p => `<option>${p}</option>`).join('');

    renderTable();

    // Event listeners
    document.getElementById('provider-filter').onchange = renderTable;
    document.getElementById('sort-by').onchange = renderTable;
    document.getElementById('sort-desc').onchange = renderTable;
}

function renderTable() {
    const provider = document.getElementById('provider-filter').value;
    const sortBy = document.getElementById('sort-by').value;
    const desc = document.getElementById('sort-desc').checked;

    let etfs = [...allEtfs];
    if (provider) etfs = etfs.filter(e => e.provider === provider);

    etfs.sort((a, b) => {
        let va = a[sortBy] ?? -Infinity;
        let vb = b[sortBy] ?? -Infinity;
        if (desc) return vb - va;
        return va - vb;
    });

    // Update sort indicator on header
    document.querySelectorAll('#etf-table th').forEach(th => {
        const key = th.dataset.sort;
        if (!key) return;
        th.innerHTML = th.innerHTML.replace(/ [▲▼]/, '');
        if (key === sortBy) th.innerHTML += desc ? ' ▼' : ' ▲';
    });

    function fmt(val, suffix='', dec=2) {
        if (val == null || val === '') return '--';
        return Number(val).toFixed(dec) + suffix;
    }

    const tbody = document.querySelector('#etf-table tbody');
    tbody.innerHTML = etfs.map(e => `
        <tr>
            <td><strong>${e.ticker}</strong></td>
            <td title="${e.name}">${e.name.length > 40 ? e.name.slice(0,38)+'…' : e.name}</td>
            <td>${e.provider}</td>
            <td class="yield-col">${fmt(e.current_yield, '%')}</td>
            <td>${fmt(e.avg_yield_since_inception, '%')}</td>
            <td class="${e.distribution_coverage >= 1 ? 'positive' : 'negative'}">${fmt(e.distribution_coverage, 'x')}</td>
            <td class="${e.sharpe_ratio >= 0 ? 'positive' : 'negative'}">${fmt(e.sharpe_ratio)}</td>
            <td>${fmt(e.sortino_ratio)}</td>
            <td>${fmt(e.calmar_ratio)}</td>
            <td class="${e.total_return_1yr >= 0 ? 'positive' : 'negative'}">${fmt(e.total_return_1yr, '%')}</td>
            <td class="yield-col">$${e.available_income_10k != null ? Number(e.available_income_10k).toLocaleString() : '--'}</td>
            <td class="${e.nav_annual_change >= 0 ? 'positive' : 'negative'}">${fmt(e.nav_annual_change, '%')}</td>
            <td>${fmt(e.beta_sp500)}</td>
            <td>${fmt(e.correlation_sp500)}</td>
        </tr>
    `).join('');
}

// === BETA CHART ===
async function loadBetaChart() {
    const resp = await fetch(`${API}/beta-correlation`);
    const data = await resp.json();

    const ctx = document.getElementById('beta-chart').getContext('2d');
    if (betaChart) betaChart.destroy();

    const points = data.points;
    const datasets = points.map(p => ({
        label: p.ticker,
        data: [{ x: p.beta, y: p.correlation }],
        backgroundColor: p.yield > 20 ? '#ef5350' : p.yield > 10 ? '#ffa726' : '#42a5f5',
        borderColor: 'transparent',
        pointRadius: 5,
        pointHoverRadius: 8,
    }));

    betaChart = new Chart(ctx, {
        type: 'scatter',
        data: { datasets },
        options: {
            responsive: true,
            maintainAspectRatio: false,
            plugins: {
                tooltip: {
                    callbacks: {
                        label: (ctx) => {
                            const p = points[ctx.datasetIndex];
                            return `${p.ticker}: β=${p.beta}, ρ=${p.correlation}, yield=${p.yield}%`;
                        }
                    }
                },
                legend: { display: false },
                title: {
                    display: true,
                    text: 'Beta (X) vs Correlation (Y) with S&P 500',
                    color: '#e0e0e0',
                }
            },
            scales: {
                x: {
                    title: { display: true, text: 'Beta (magnitude)', color: '#888' },
                    grid: { color: '#2a2d38' },
                    ticks: { color: '#888' },
                },
                y: {
                    title: { display: true, text: 'Correlation (direction)', color: '#888' },
                    grid: { color: '#2a2d38' },
                    ticks: { color: '#888' },
                    min: -0.2, max: 1.1,
                }
            }
        }
    });
}

// === PORTFOLIO BUILDER ===
async function setupPortfolio() {
    if (allEtfs.length === 0) {
        const resp = await fetch(`${API}/etfs`);
        allEtfs = await resp.json();
    }

    const searchInput = document.getElementById('pf-search');
    const dropdown = document.getElementById('pf-search-results');

    searchInput.oninput = () => {
        const q = searchInput.value.toLowerCase();
        if (q.length < 1) { dropdown.classList.remove('show'); return; }

        const matches = allEtfs
            .filter(e => e.ticker.toLowerCase().includes(q) || e.name.toLowerCase().includes(q))
            .slice(0, 8);

        dropdown.innerHTML = matches.map(e => `
            <div class="pf-dropdown-item" data-ticker="${e.ticker}">
                <span><span class="pf-dd-ticker">${e.ticker}</span> ${e.name.slice(0,30)}</span>
                <span class="pf-dd-yield">${e.current_yield}%</span>
            </div>
        `).join('');
        dropdown.classList.add('show');

        dropdown.querySelectorAll('.pf-dropdown-item').forEach(item => {
            item.onclick = () => {
                const ticker = item.dataset.ticker;
                if (portfolioEtfs.find(p => p.ticker === ticker)) return;
                const etf = allEtfs.find(e => e.ticker === ticker);
                if (!etf) return;
                portfolioEtfs.push({
                    ticker: etf.ticker,
                    name: etf.name,
                    weight: Math.floor(100 / (portfolioEtfs.length + 1)),
                    yield: etf.current_yield
                });
                // Normalize weights
                const total = portfolioEtfs.reduce((s, p) => s + p.weight, 0);
                if (total !== 100) {
                    const diff = 100 - total;
                    portfolioEtfs[0].weight += diff;
                }
                renderPortfolioEtfs();
                dropdown.classList.remove('show');
                searchInput.value = '';
            };
        });
    };

    searchInput.onblur = () => { setTimeout(() => dropdown.classList.remove('show'), 200); };

    document.getElementById('pf-reinvest').oninput = function() {
        document.getElementById('pf-reinvest-val').textContent = this.value + '%';
    };

    document.getElementById('pf-simulate').onclick = simulatePortfolio;

    renderPortfolioEtfs();
}

function renderPortfolioEtfs() {
    const container = document.getElementById('pf-selected');
    if (portfolioEtfs.length === 0) {
        container.innerHTML = '<p class="hint">Search and add ETFs to your portfolio (4-8 recommended)</p>';
        return;
    }
    container.innerHTML = portfolioEtfs.map((p, i) => `
        <div class="pf-selected-item">
            <span><strong>${p.ticker}</strong> <span style="color:#888;font-size:0.8em">${p.name.slice(0,25)}</span></span>
            <span style="display:flex;align-items:center;gap:8px">
                <input type="number" class="weight-input" value="${p.weight}" min="0" max="100"
                    onchange="updateWeight(${i}, this.value)" style="width:55px">%
                <button class="remove-btn" onclick="removeEtf(${i})">✕</button>
            </span>
        </div>
    `).join('');
}

function updateWeight(index, val) {
    portfolioEtfs[index].weight = parseInt(val) || 0;
    renderPortfolioEtfs();
}

function removeEtf(index) {
    portfolioEtfs.splice(index, 1);
    // Redistribute weights
    if (portfolioEtfs.length > 0) {
        const each = Math.floor(100 / portfolioEtfs.length);
        portfolioEtfs.forEach(p => p.weight = each);
        portfolioEtfs[0].weight += 100 - each * portfolioEtfs.length;
    }
    renderPortfolioEtfs();
}

async function simulatePortfolio() {
    if (portfolioEtfs.length < 1) return;

    const payload = {
        tickers: portfolioEtfs.map(p => ({ ticker: p.ticker, weight: p.weight })),
        initial_investment: parseInt(document.getElementById('pf-investment').value) || 25000,
        reinvest_pct: parseInt(document.getElementById('pf-reinvest').value),
        rebalance: document.getElementById('pf-rebalance').value,
    };

    const resp = await fetch(`${API}/portfolio/simulate`, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify(payload),
    });
    const result = await resp.json();

    document.getElementById('pf-final-val').textContent = '$' + result.final_value.toLocaleString();
    document.getElementById('pf-cash').textContent = '$' + result.total_cash_received.toLocaleString();
    document.getElementById('pf-total-ret').textContent = result.total_return_pct + '%';
    document.getElementById('pf-nav-chg').textContent = result.nav_change_pct + '%';

    // Charts
    const startDate = result.start_date;
    const months = result.monthly_nav.length;
    const labels = Array.from({length: months}, (_, i) => {
        const d = new Date(startDate);
        d.setMonth(d.getMonth() + i + 1);
        return d.toLocaleDateString('en-US', {month:'short', year:'2-digit'});
    });

    // NAV chart
    if (pfChartNav) pfChartNav.destroy();
    const ctxNav = document.getElementById('pf-nav-chart').getContext('2d');
    pfChartNav = new Chart(ctxNav, {
        type: 'line',
        data: {
            labels,
            datasets: [
                {
                    label: 'Portfolio Value',
                    data: result.monthly_nav,
                    borderColor: '#4fc3f7',
                    backgroundColor: 'rgba(79,195,247,0.1)',
                    fill: true,
                    tension: 0.3,
                },
                {
                    label: 'Initial Investment',
                    data: Array(months).fill(result.initial_investment),
                    borderColor: '#888',
                    borderDash: [5,5],
                    pointRadius: 0,
                }
            ]
        },
        options: {
            responsive: true,
            plugins: { title: { display: true, text: 'Portfolio Value Over Time', color: '#e0e0e0' } },
            scales: {
                y: { ticks: { color: '#888', callback: v => '$' + v.toLocaleString() }, grid: { color: '#2a2d38' } },
                x: { ticks: { color: '#888', maxTicksLimit: 12 }, grid: { color: '#2a2d38' } },
            }
        }
    });

    // Income chart
    if (pfChartIncome) pfChartIncome.destroy();
    const ctxIncome = document.getElementById('pf-income-chart').getContext('2d');
    pfChartIncome = new Chart(ctxIncome, {
        type: 'bar',
        data: {
            labels,
            datasets: [{
                label: 'Monthly Income',
                data: result.monthly_income,
                backgroundColor: '#66bb6a',
                borderRadius: 2,
            }]
        },
        options: {
            responsive: true,
            plugins: { title: { display: true, text: 'Monthly Income', color: '#e0e0e0' } },
            scales: {
                y: { ticks: { color: '#888', callback: v => '$' + v.toLocaleString() }, grid: { color: '#2a2d38' } },
                x: { ticks: { color: '#888', maxTicksLimit: 12 }, grid: { color: '#2a2d38' } },
            }
        }
    });
}

// === BEST PORTFOLIOS ===
async function loadBestPortfolios() {
    const period = document.getElementById('bp-period').value;
    const sortBy = document.getElementById('bp-sort').value;

    document.getElementById('bp-period').onchange = loadBestPortfolios;
    document.getElementById('bp-sort').onchange = loadBestPortfolios;

    const resp = await fetch(`${API}/best-portfolios?period=${period}&sort_by=${sortBy}`);
    const data = await resp.json();

    document.getElementById('bp-eligible').textContent =
        `${data.eligible_etfs} eligible ETFs | ${(data.total_simulations/1000).toFixed(0)}k combinations tested`;

    if (!data.portfolios || data.portfolios.length === 0) {
        document.getElementById('best-portfolios-table').innerHTML =
            '<p class="hint">Not enough ETFs with sufficient history for this period.</p>';
        return;
    }

    const container = document.getElementById('best-portfolios-table');
    container.innerHTML = data.portfolios.map((p, i) => `
        <div class="bp-row">
            <div class="bp-rank">#${i + 1}</div>
            <div class="bp-etfs">
                ${p.etfs.map(e => `<span class="bp-etf-tag ${e.highlight ? 'highlight' : ''}">${e.ticker} ${e.weight}%</span>`).join('')}
            </div>
            <div class="bp-metrics">
                <div class="bp-metric"><span class="val">$${p.monthly_income.toLocaleString()}/mo</span><span class="lbl">Income</span></div>
                <div class="bp-metric"><span class="val">${p.total_return}%</span><span class="lbl">Total Return</span></div>
                <div class="bp-metric"><span class="val">${p.nav_change}%</span><span class="lbl">NAV Change</span></div>
                <div class="bp-metric"><span class="val">${p.sharpe}</span><span class="lbl">Sharpe</span></div>
                <div class="bp-metric"><span class="val">${p.avg_yield}%</span><span class="lbl">Avg Yield</span></div>
            </div>
        </div>
    `).join('');
}

// Initial load
loadOverview();
