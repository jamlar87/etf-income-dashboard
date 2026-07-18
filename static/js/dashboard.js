// ETF Dashboard JS — aligned to reference design
const API = '/api';

let allEtfs = [];
let pfChartNav = null;
let pfChartIncome = null;
let betaChart = null;
let portfolioEtfs = [];

// === Navigation ===
document.querySelectorAll('.nav-link').forEach(link => {
    link.addEventListener('click', (e) => {
        e.preventDefault();
        document.querySelectorAll('.nav-link').forEach(l => l.classList.remove('active'));
        link.classList.add('active');
        document.querySelectorAll('.section').forEach(s => s.classList.remove('active'));
        const id = link.dataset.section;
        document.getElementById(id).classList.add('active');
        loadSection(id);
    });
});

function loadSection(id) {
    if (id === 'overview') loadOverview();
    if (id === 'compare') loadCompare();
    if (id === 'newest') loadNewest();
    if (id === 'dist-yield') loadDistYield();
    if (id === 'dist-coverage') loadDistCoverage();
    if (id === 'nav-erosion') loadNavErosion();
    if (id === 'total-return') loadTotalReturn();
    if (id === 'sharpe') loadSharpe();
    if (id === 't12-perf') loadT12Perf();
    if (id === 'beta') loadBetaChart();
    if (id === 'portfolio') setupPortfolio();
    if (id === 'best') loadBestPortfolios();
    if (id === 'return-chart') loadReturnChart();
}

// === Helpers ===
function fmt(v, s='', d=2) {
    if (v == null) return '--';
    return Number(v).toFixed(d) + s;
}

function pct(v) { return fmt(v, '%'); }

// === NEWEST ADDITIONS (styled to match reference) ===
async function loadNewest() {
    const resp = await fetch(`${API}/etfs/new?limit=50`);
    const etfs = await resp.json();
    document.getElementById('new-count').textContent = etfs.length;
    document.getElementById('new-date').textContent = 'Latest inception: ' + (etfs[0]?.inception_date || 'N/A');
    const grid = document.getElementById('new-etfs-grid');
    grid.innerHTML = etfs.map(e => {
        const arrow = e.total_return_1yr >= 0 ? '▲' : '▼';
        const cls = e.total_return_1yr >= 0 ? 'positive' : 'negative';
        return `<div class="na-card" title="${e.name}">
            <div class="na-ticker">${e.ticker}</div>
            <div class="na-yield">${pct(e.current_yield)}</div>
            <div class="na-return ${cls}">${arrow} ${pct(e.total_return_1yr)} <span class="na-ttm">T12M</span></div>
        </div>`;
    }).join('');
}

// === OVERVIEW / LEADERBOARD ===
async function loadOverview() {
    // Stats
    const s = await (await fetch(`${API}/stats`)).json();
    document.getElementById('os-etfs').textContent = s.total_etfs;
    document.getElementById('os-avg-yield').textContent = s.avg_yield + '%';

    // Best return and sharpe come from leaderboard
    const lb = await (await fetch(`${API}/leaderboard`)).json();
    const bestRet = lb.categories.best_total_return_1yr?.[0];
    const bestSharpe = lb.categories.best_sharpe?.[0];
    document.getElementById('os-best-ret').textContent = bestRet
        ? `${bestRet.ticker} ${bestRet.total_return_1yr}%` : '--';
    document.getElementById('os-best-sharpe').textContent = bestSharpe
        ? `${bestSharpe.ticker} ${bestSharpe.sharpe_ratio}` : '--';

    // Leaderboard categories (top 7 per category, 2 columns: Best TR + Best Sharpe)
    const grid = document.getElementById('leaderboard-grid');
    const catLabels = {
        'best_total_return_1yr': 'Best Total Return (TTM)',
        'best_sharpe': 'Best Sharpe Ratio (TTM)',
        'total_return_1yr': 'Trailing 12 Months (TTM)',
    };

    function renderCat(catKey, label) {
        const entries = lb.categories[catKey]?.slice(0, 7) || [];
        let html = `<div class="lb-category">
            <div class="lb-cat-header">${label}</div>`;
        entries.forEach((e, i) => {
            let val;
            if (catKey.includes('yield')) val = pct(e.current_yield);
            else if (catKey.includes('total_return')) val = pct(e.total_return_1yr);
            else if (catKey.includes('sharpe')) val = e.sharpe_ratio;
            else if (catKey.includes('dist_coverage')) val = fmt(e.distribution_coverage, 'x');
            else val = '--';
            html += `<div class="lb-row">
                <span class="lb-rank">#${i+1}</span>
                <span class="lb-ticker">${e.ticker}</span>
                <span class="lb-name" title="${e.name}">${e.name}</span>
                <span class="lb-val">${val}</span>
                <span class="lb-legend ${e.tier}"></span>
            </div>`;
        });
        html += `</div>`;
        return html;
    }

    grid.innerHTML = renderCat('best_total_return_1yr', 'Best Total Return (TTM)')
        + renderCat('best_sharpe', 'Best Sharpe Ratio')
        + renderCat('best_dist_coverage', 'Best Distribution Coverage')
        + renderCat('highest_yield', 'Highest Current Yield')
        + renderCat('best_total_return_3yr', 'Best 3-Year Return')
        + renderCat('best_sortino', 'Best Sortino Ratio')
        + renderCat('best_nav_growth', 'Best NAV Growth')
        + renderCat('best_calmar', 'Best Calmar Ratio');
}

// === DISTRIBUTION YIELD ===
async function loadDistYield() {
    const etfs = await (await fetch(`${API}/etfs?sort_by=current_yield&sort_dir=desc`)).json();
    document.getElementById('dist-yield-content').innerHTML = `
        <div class="quick-lists">
            <div class="quick-list"><h3>🔝 Highest Current Yield</h3>
                ${etfs.slice(0, 15).map(e => `<div class="ql-item"><span>${e.ticker}</span><span class="yield-col">${pct(e.current_yield)}</span></div>`).join('')}
            </div>
            <div class="quick-list"><h3>⚠️ Yield Gap (Current vs Avg)</h3>
                ${etfs.filter(e => e.avg_yield_since_inception).sort((a,b) => Math.abs(b.current_yield - b.avg_yield_since_inception) - Math.abs(a.current_yield - a.avg_yield_since_inception)).slice(0, 15).map(e =>
                    `<div class="ql-item"><span>${e.ticker}</span><span class="${Math.abs(e.current_yield - e.avg_yield_since_inception) > 10 ? 'negative' : ''}">${pct(e.current_yield)} vs ${pct(e.avg_yield_since_inception)}</span></div>`
                ).join('')}
            </div>
        </div>`;
}

// === DISTRIBUTION COVERAGE ===
async function loadDistCoverage() {
    const best = await (await fetch(`${API}/etfs?sort_by=distribution_coverage&sort_dir=desc`)).json();
    const worst = await (await fetch(`${API}/etfs?sort_by=distribution_coverage&sort_dir=asc`)).json();
    document.getElementById('dist-coverage-content').innerHTML = `
        <div class="quick-lists">
            <div class="quick-list"><h3>✅ Best Coverage (1-2x ideal)</h3>
                ${best.slice(0, 15).map(e => `<div class="ql-item"><span>${e.ticker} (${e.current_yield}%)</span><span style="color:var(--green)">${fmt(e.distribution_coverage, 'x')}</span></div>`).join('')}
            </div>
            <div class="quick-list"><h3>⚠️ Worst Coverage (&lt;0 = NAV erosion)</h3>
                ${worst.filter(e => e.distribution_coverage !== null).slice(0, 15).map(e => `<div class="ql-item"><span>${e.ticker} (${pct(e.current_yield)})</span><span style="color:var(--red)">${fmt(e.distribution_coverage, 'x')}</span></div>`).join('')}
            </div>
        </div>`;
}

// === NAV EROSION ===
async function loadNavErosion() {
    const best = await (await fetch(`${API}/etfs?sort_by=nav_annual_change&sort_dir=desc`)).json();
    const worst = await (await fetch(`${API}/etfs?sort_by=nav_annual_change&sort_dir=asc`)).json();
    document.getElementById('nav-erosion-content').innerHTML = `
        <div class="quick-lists">
            <div class="quick-list"><h3>📈 Strongest NAV Growth</h3>
                ${best.filter(e => e.nav_annual_change !== null).slice(0, 15).map(e => `<div class="ql-item"><span>${e.ticker} (${pct(e.current_yield)})</span><span style="color:var(--green)">${pct(e.nav_annual_change)}</span></div>`).join('')}
            </div>
            <div class="quick-list"><h3>📉 Worst NAV Erosion</h3>
                ${worst.filter(e => e.nav_annual_change !== null).slice(0, 15).map(e => `<div class="ql-item"><span>${e.ticker} (${pct(e.current_yield)})</span><span style="color:var(--red)">${pct(e.nav_annual_change)}</span></div>`).join('')}
            </div>
        </div>`;
}

// === TOTAL RETURN ===
async function loadTotalReturn() {
    const periods = [
        { key: 'total_return_1yr', label: '1 Year' },
        { key: 'total_return_3yr', label: '3 Year' },
        { key: 'total_return_5yr', label: '5 Year' },
        { key: 'total_return_10yr', label: '10 Year' },
    ];
    const all = await (await fetch(`${API}/etfs?sort_by=total_return_1yr&sort_dir=desc`)).json();
    let html = `<div class="quick-lists">`;
    periods.forEach(p => {
        const sorted = [...all].filter(e => e[p.key] !== null).sort((a,b) => b[p.key] - a[p.key]);
        html += `<div class="quick-list"><h3>Top 10 — ${p.label}</h3>
            ${sorted.slice(0, 10).map(e => `<div class="ql-item"><span>${e.ticker}</span><span class="${e[p.key] >= 0 ? 'positive' : 'negative'}">${pct(e[p.key])}</span></div>`).join('')}
        </div>`;
    });
    html += `</div>`;
    document.getElementById('total-return-content').innerHTML = html;
}

// === SHARPE / SORTINO / CALMAR ===
async function loadSharpe() {
    const all = await (await fetch(`${API}/etfs`)).json();
    const bySharpe = [...all].filter(e => e.sharpe_ratio !== null).sort((a,b) => b.sharpe_ratio - a.sharpe_ratio);
    const bySortino = [...all].filter(e => e.sortino_ratio !== null).sort((a,b) => b.sortino_ratio - a.sortino_ratio);
    const byCalmar = [...all].filter(e => e.calmar_ratio !== null).sort((a,b) => b.calmar_ratio - a.calmar_ratio);

    document.getElementById('sharpe-content').innerHTML = `
        <div class="quick-lists">
            <div class="quick-list"><h3>🎯 Best Sharpe Ratio</h3>
                ${bySharpe.slice(0, 12).map(e => `<div class="ql-item"><span>${e.ticker}</span><span>${e.sharpe_ratio}</span></div>`).join('')}
            </div>
            <div class="quick-list"><h3>🎯 Best Sortino Ratio</h3>
                ${bySortino.slice(0, 12).map(e => `<div class="ql-item"><span>${e.ticker}</span><span>${e.sortino_ratio}</span></div>`).join('')}
            </div>
            <div class="quick-list" style="grid-column:1/3;margin-top:10px"><h3>🎯 Best Calmar Ratio</h3>
                ${byCalmar.slice(0, 12).map(e =>
                    `<div class="ql-item"><span>${e.ticker} — ${e.name.slice(0,40)}</span><span>${e.calmar_ratio}</span></div>`
                ).join('')}
            </div>
        </div>`;
}

// === TRAILING 12M PERFORMANCE ===
async function loadT12Perf() {
    const all = await (await fetch(`${API}/etfs?sort_by=total_return_1yr&sort_dir=desc`)).json();
    const best = all.filter(e => e.total_return_1yr !== null);
    const worst = [...all].filter(e => e.total_return_1yr !== null).sort((a,b) => a.total_return_1yr - b.total_return_1yr);

    document.getElementById('t12-perf-content').innerHTML = `
        <div class="quick-lists">
            <div class="quick-list"><h3>🏆 Best T12 Total Return</h3>
                ${best.slice(0, 15).map(e => `<div class="ql-item"><span>${e.ticker} — ${e.provider}</span><span class="positive">${pct(e.total_return_1yr)}</span></div>`).join('')}
            </div>
            <div class="quick-list"><h3>⚠️ Worst T12 Total Return</h3>
                ${worst.slice(0, 15).map(e => `<div class="ql-item"><span>${e.ticker} — ${e.provider}</span><span class="negative">${pct(e.total_return_1yr)}</span></div>`).join('')}
            </div>
        </div>`;
}

// === RETURN SCATTER CHART ===
async function loadReturnChart() {
    const all = await (await fetch(`${API}/etfs`)).json();
    const chartData = all
        .filter(e => e.total_return_3yr !== null && e.sharpe_ratio !== null && e.current_yield !== null)
        .map(e => ({
            x: e.sharpe_ratio,
            y: e.total_return_3yr,
            ticker: e.ticker,
            yield: e.current_yield,
            provider: e.provider,
        }));

    const ctx = document.getElementById('return-scatter-chart').getContext('2d');
    if (window.retChart) window.retChart.destroy();

    window.retChart = new Chart(ctx, {
        type: 'scatter',
        data: {
            datasets: [{
                label: 'ETFs',
                data: chartData,
                backgroundColor: chartData.map(d => d.yield > 20 ? '#e74c5c' : d.yield > 10 ? '#f0a030' : '#4a90d9'),
                pointRadius: 5,
                pointHoverRadius: 8,
            }]
        },
        options: {
            responsive: true,
            maintainAspectRatio: false,
            plugins: {
                tooltip: {
                    callbacks: {
                        label: (c) => {
                            const d = chartData[c.dataIndex];
                            return `${d.ticker}: 3yr ret=${d.y.toFixed(1)}%, sharpe=${d.x}, yield=${d.yield}%`;
                        }
                    }
                },
                legend: { display: false },
                title: { display: true, text: '3-Year Return vs Sharpe Ratio', color: '#e8eaed' }
            },
            scales: {
                x: { title: { display: true, text: 'Sharpe Ratio', color: '#888' }, grid: { color: '#1e2538' }, ticks: { color: '#888' } },
                y: { title: { display: true, text: '3-Year Total Return %', color: '#888' }, grid: { color: '#1e2538' }, ticks: { color: '#888' } },
            }
        }
    });
}

// === COMPARE TABLE ===
async function loadCompare() {
    if (allEtfs.length === 0) allEtfs = await (await fetch(`${API}/etfs`)).json();
    const providers = [...new Set(allEtfs.map(e => e.provider))].sort();
    document.getElementById('provider-filter').innerHTML = '<option value="">All</option>'
        + providers.map(p => `<option>${p}</option>`).join('');
    renderTable();
    document.getElementById('provider-filter').onchange = renderTable;
    document.getElementById('sort-by').onchange = renderTable;
    document.getElementById('sort-desc').onchange = renderTable;
}

function renderTable() {
    const provider = document.getElementById('provider-filter').value;
    const sortBy = document.getElementById('sort-by').value;
    const desc = document.getElementById('sort-desc').checked;
    let etfs = provider ? allEtfs.filter(e => e.provider === provider) : [...allEtfs];
    etfs.sort((a, b) => {
        const va = a[sortBy] ?? (desc ? Infinity : -Infinity);
        const vb = b[sortBy] ?? (desc ? Infinity : -Infinity);
        return desc ? vb - va : va - vb;
    });
    document.querySelectorAll('#etf-table th').forEach(th => {
        const k = th.dataset.sort;
        if (!k) return;
        th.innerHTML = th.innerHTML.replace(/ [▲▼]/, '');
        if (k === sortBy) th.innerHTML += desc ? ' ▼' : ' ▲';
    });
    document.querySelector('#etf-table tbody').innerHTML = etfs.map(e => `
        <tr>
            <td><strong>${e.ticker}</strong></td>
            <td title="${e.name}">${e.name.length > 42 ? e.name.slice(0,40)+'…' : e.name}</td>
            <td>${e.provider}</td>
            <td class="yield-col">${pct(e.current_yield)}</td>
            <td>${pct(e.avg_yield_since_inception)}</td>
            <td class="${e.distribution_coverage >= 1 ? 'positive' : 'negative'}">${fmt(e.distribution_coverage, 'x')}</td>
            <td class="${e.sharpe_ratio >= 0 ? 'positive' : 'negative'}">${fmt(e.sharpe_ratio)}</td>
            <td>${fmt(e.sortino_ratio)}</td>
            <td>${fmt(e.calmar_ratio)}</td>
            <td class="${e.total_return_1yr >= 0 ? 'positive' : 'negative'}">${pct(e.total_return_1yr)}</td>
            <td class="yield-col">${e.available_income_10k != null ? '$' + Number(e.available_income_10k).toLocaleString() : '--'}</td>
            <td class="${e.nav_annual_change >= 0 ? 'positive' : 'negative'}">${pct(e.nav_annual_change)}</td>
            <td>${fmt(e.beta_sp500)}</td>
            <td>${fmt(e.correlation_sp500)}</td>
        </tr>
    `).join('');
}

// === BETA CHART ===
async function loadBetaChart() {
    const data = await (await fetch(`${API}/beta-correlation`)).json();
    const ctx = document.getElementById('beta-chart').getContext('2d');
    if (betaChart) betaChart.destroy();
    const points = data.points;
    betaChart = new Chart(ctx, {
        type: 'scatter',
        data: {
            datasets: points.map(p => ({
                label: p.ticker,
                data: [{ x: p.beta, y: p.correlation }],
                backgroundColor: p.yield > 20 ? '#e74c5c' : p.yield > 10 ? '#f0a030' : '#4a90d9',
                borderColor: 'transparent', pointRadius: 5, pointHoverRadius: 8,
            }))
        },
        options: {
            responsive: true, maintainAspectRatio: false,
            plugins: {
                tooltip: { callbacks: { label: (c) => `${points[c.datasetIndex].ticker}: β=${points[c.datasetIndex].beta}, ρ=${points[c.datasetIndex].correlation}, yield=${points[c.datasetIndex].yield}%` } },
                legend: { display: false },
                title: { display: true, text: 'Beta (X) vs Correlation (Y) with S&P 500', color: '#e8eaed' }
            },
            scales: {
                x: { title: { display: true, text: 'Beta', color: '#888' }, grid: { color: '#1e2538' }, ticks: { color: '#888' } },
                y: { title: { display: true, text: 'Correlation', color: '#888' }, grid: { color: '#1e2538' }, ticks: { color: '#888' }, min: -0.2, max: 1.1 },
            }
        }
    });
}

// === PORTFOLIO BUILDER ===
async function setupPortfolio() {
    if (allEtfs.length === 0) allEtfs = await (await fetch(`${API}/etfs`)).json();
    const si = document.getElementById('pf-search');
    const dd = document.getElementById('pf-search-results');
    si.oninput = () => {
        const q = si.value.toLowerCase();
        if (q.length < 1) { dd.classList.remove('show'); return; }
        const matches = allEtfs.filter(e => e.ticker.toLowerCase().includes(q) || e.name.toLowerCase().includes(q)).slice(0, 8);
        dd.innerHTML = matches.map(e => `<div class="pf-dropdown-item" data-t="${e.ticker}">
            <span><span class="pf-dd-ticker">${e.ticker}</span> ${e.name.slice(0,28)}</span>
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
    document.getElementById('pf-reinvest').oninput = function() {
        document.getElementById('pf-reinvest-val').textContent = this.value + '%';
    };
    document.getElementById('pf-simulate').onclick = simulatePortfolio;
    renderPortfolio();
}

function renderPortfolio() {
    const el = document.getElementById('pf-selected');
    if (!portfolioEtfs.length) { el.innerHTML = '<p class="hint">Search and add ETFs to your portfolio (4-8 recommended)</p>'; return; }
    el.innerHTML = portfolioEtfs.map((p, i) => `
        <div class="pf-selected-item">
            <span><strong>${p.ticker}</strong> <span style="color:var(--text-dim);font-size:0.78em">${p.name.slice(0,20)}</span></span>
            <span><input type="number" class="weight-input" value="${Math.round(p.weight)}" min="0" max="100" onchange="updateWeight(${i},this.value)" style="width:48px;background:var(--card-bg);color:var(--text);border:1px solid var(--border);padding:2px 4px;border-radius:3px;text-align:right;font-size:0.85em">%
            <button onclick="removeEtf(${i})" style="background:none;border:none;color:var(--red);cursor:pointer;margin-left:4px">✕</button></span>
        </div>`).join('');
}

function updateWeight(i, v) { portfolioEtfs[i].weight = parseInt(v) || 0; renderPortfolio(); }
function removeEtf(i) { portfolioEtfs.splice(i, 1); if (portfolioEtfs.length) { const e = Math.floor(100 / portfolioEtfs.length); portfolioEtfs.forEach(p => p.weight = e); portfolioEtfs[0].weight += 100 - e * portfolioEtfs.length; } renderPortfolio(); }

async function simulatePortfolio() {
    if (!portfolioEtfs.length) return;
    const payload = {
        tickers: portfolioEtfs.map(p => ({ ticker: p.ticker, weight: Math.round(p.weight) })),
        initial_investment: parseInt(document.getElementById('pf-investment').value) || 25000,
        reinvest_pct: parseInt(document.getElementById('pf-reinvest').value),
        rebalance: document.getElementById('pf-rebalance').value,
    };
    const r = await (await fetch(`${API}/portfolio/simulate`, { method: 'POST', headers: { 'Content-Type': 'application/json' }, body: JSON.stringify(payload) })).json();
    document.getElementById('pf-final-val').textContent = '$' + Number(r.final_value).toLocaleString();
    document.getElementById('pf-cash').textContent = '$' + Number(r.total_cash_received).toLocaleString();
    document.getElementById('pf-total-ret').textContent = r.total_return_pct + '%';
    document.getElementById('pf-nav-chg').textContent = r.nav_change_pct + '%';
    document.querySelector('.pf-results').style.display = 'block';

    const labels = Array.from({ length: r.monthly_nav.length }, (_, i) => {
        const d = new Date(r.start_date); d.setMonth(d.getMonth() + i + 1);
        return d.toLocaleDateString('en-US', { month: 'short', year: '2-digit' });
    });

    if (pfChartNav) pfChartNav.destroy();
    pfChartNav = new Chart(document.getElementById('pf-nav-chart'), {
        type: 'line', data: {
            labels,
            datasets: [
                { label: 'Portfolio Value', data: r.monthly_nav, borderColor: '#4fc3f7', backgroundColor: 'rgba(79,195,247,0.08)', fill: true, tension: 0.3 },
                { label: 'Initial', data: Array(r.monthly_nav.length).fill(r.initial_investment), borderColor: '#888', borderDash: [5,5], pointRadius: 0 }
            ]
        },
        options: { responsive: true, plugins: { title: { display: true, text: 'Portfolio Value', color: '#e8eaed' } }, scales: { y: { ticks: { color: '#888', callback: v => '$' + v.toLocaleString() }, grid: { color: '#1e2538' } }, x: { ticks: { color: '#888', maxTicksLimit: 12 }, grid: { color: '#1e2538' } } } }
    });

    if (pfChartIncome) pfChartIncome.destroy();
    pfChartIncome = new Chart(document.getElementById('pf-income-chart'), {
        type: 'bar', data: { labels, datasets: [{ label: 'Monthly Income', data: r.monthly_income, backgroundColor: '#46b97e', borderRadius: 2 }] },
        options: { responsive: true, plugins: { title: { display: true, text: 'Monthly Income', color: '#e8eaed' } }, scales: { y: { ticks: { color: '#888', callback: v => '$' + v.toLocaleString() }, grid: { color: '#1e2538' } }, x: { ticks: { color: '#888', maxTicksLimit: 12 }, grid: { color: '#1e2538' } } } }
    });
}

// === BEST PORTFOLIOS ===
async function loadBestPortfolios() {
    const period = document.getElementById('bp-period').value;
    const sortBy = document.getElementById('bp-sort').value;
    document.getElementById('bp-period').onchange = loadBestPortfolios;
    document.getElementById('bp-sort').onchange = loadBestPortfolios;
    const d = await (await fetch(`${API}/best-portfolios?period=${period}&sort_by=${sortBy}`)).json();
    document.getElementById('bp-eligible').textContent = `${d.eligible_etfs} eligible ETFs`;
    if (!d.portfolios?.length) {
        document.getElementById('best-portfolios-table').innerHTML = '<p class="hint">Not enough ETFs with sufficient history.</p>';
        return;
    }
    document.getElementById('best-portfolios-table').innerHTML = d.portfolios.map((p, i) => `
        <div class="bp-row">
            <div class="bp-rank">#${i+1}</div>
            <div class="bp-etfs">${p.etfs.map(e => `<span class="bp-etf-tag ${e.highlight ? 'highlight' : ''}">${e.ticker} ${e.weight}%</span>`).join('')}</div>
            <div class="bp-metrics">
                <div class="bp-metric"><span class="val">$${Number(p.monthly_income).toLocaleString()}/mo</span><span class="lbl">Income</span></div>
                <div class="bp-metric"><span class="val">${p.total_return}%</span><span class="lbl">Return</span></div>
                <div class="bp-metric"><span class="val">${p.nav_change}%</span><span class="lbl">NAV</span></div>
                <div class="bp-metric"><span class="val">${p.sharpe}</span><span class="lbl">Sharpe</span></div>
                <div class="bp-metric"><span class="val">${p.avg_yield}%</span><span class="lbl">Yield</span></div>
            </div>
        </div>`).join('');
}

// === INIT ===
loadNewest();
