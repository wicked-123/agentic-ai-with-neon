document.addEventListener('DOMContentLoaded', () => {
    const escapeHtml = (value) => String(value)
        .replaceAll('&', '&amp;')
        .replaceAll('<', '&lt;')
        .replaceAll('>', '&gt;')
        .replaceAll('"', '&quot;')
        .replaceAll("'", '&#039;');
    const feedContainer       = document.getElementById('feedContainer');
    const emptyState          = document.getElementById('emptyState');
    const statusEl            = document.getElementById('status');
    const chartsGrid          = document.getElementById('chartsGrid');
    const insightsList        = document.getElementById('insightsList');
    const chartsSectionTitle  = document.getElementById('chartsSectionTitle');
    const insightsSectionTitle = document.getElementById('insightsSectionTitle');
    
    const chartModal          = document.getElementById('chartModal');
    const closeModalBtn       = document.getElementById('closeModalBtn');

    // Track chart instances so we can destroy/recreate if needed
    let chartCounter = 0;
    let modalChartInstance = null;

    if (closeModalBtn && chartModal) {
        closeModalBtn.addEventListener('click', () => {
            chartModal.style.display = 'none';
            if (modalChartInstance) {
                modalChartInstance.destroy();
                modalChartInstance = null;
            }
        });

        chartModal.addEventListener('click', (e) => {
            if (e.target === chartModal) {
                closeModalBtn.click();
            }
        });
    }

    function hideEmptyState() {
        if (emptyState) emptyState.style.display = 'none';
    }

    function checkEmptyState() {
        const hasCharts = chartsGrid.children.length > 0;
        const hasInsights = insightsList.children.length > 0;
        
        if (chartsSectionTitle) chartsSectionTitle.style.display = hasCharts ? 'flex' : 'none';
        if (insightsSectionTitle) insightsSectionTitle.style.display = hasInsights ? 'flex' : 'none';
        
        if (!hasCharts && !hasInsights && emptyState) {
            emptyState.style.display = 'block';
        }
    }

    // ── Layout Persistence ───────────────────────────────────────────────────
    const LAYOUT_KEY = 'df-dashboard-layout';

    function getLayoutStore() {
        try {
            return JSON.parse(localStorage.getItem(LAYOUT_KEY) || '{}');
        } catch { return {}; }
    }

    function saveCardLayout(cardId, props) {
        const store = getLayoutStore();
        store[cardId] = { ...(store[cardId] || {}), ...props };
        localStorage.setItem(LAYOUT_KEY, JSON.stringify(store));
    }

    function restoreCardLayout(card) {
        const store = getLayoutStore();
        const saved = store[card.id];
        if (!saved) return;
        if (saved.width) card.style.width = saved.width;
        if (saved.height) card.style.height = saved.height;
        if (saved.minimized) {
            card.classList.add('card-minimized');
            const btn = card.querySelector('.minimize-btn');
            if (btn) btn.innerHTML = '+';
        }
    }

    function attachResizeObserver(card) {
        let initW = card.offsetWidth, initH = card.offsetHeight;
        const ro = new ResizeObserver(() => {
            const w = card.style.width || card.offsetWidth + 'px';
            const h = card.style.height || card.offsetHeight + 'px';
            if (w !== initW || h !== initH) {
                saveCardLayout(card.id, { width: w, height: h });
            }
        });
        ro.observe(card);
    }

    function removeCardLayout(cardId) {
        const store = getLayoutStore();
        delete store[cardId];
        localStorage.setItem(LAYOUT_KEY, JSON.stringify(store));
    }

    // ── Load past results from history endpoint ───────────────────────────────
    async function loadHistory() {
        try {
            const res = await fetch('/history');
            const items = await res.json();
            if (items.length > 0) {
                hideEmptyState();
                items.forEach(data => {
                    if (data.type === 'chart' && data.chart_config) {
                        renderChartCard(data);
                    } else {
                        renderInsightCard(data);
                    }
                });
            }
        } catch (e) {
            console.error('Failed to load history:', e);
        }
    }

    loadHistory();

    // ── SSE Connection ────────────────────────────────────────────────────────
    const eventSource = new EventSource('/stream');

    eventSource.onopen = () => {
        statusEl.innerHTML = '🟢 Listening for live queries...';
        statusEl.style.color = 'var(--primary)';
    };

    eventSource.onerror = () => {
        statusEl.innerHTML = '🔴 Connection lost. Reconnecting...';
        statusEl.style.color = 'red';
    };

    eventSource.onmessage = (event) => {
        hideEmptyState();
        const data = JSON.parse(event.data);

        if (data.type === 'chart' && data.chart_config) {
            renderChartCard(data);
        } else {
            renderInsightCard(data);
        }
    };

    // ── Helper: derive a short title from the question ────────────────────────
    function deriveChartTitle(question) {
        // Capitalize first letter and truncate if too long
        const clean = question.replace(/^(show me|create|generate|make|draw|plot)\s+(a\s+)?/i, '').trim();
        const title = clean.charAt(0).toUpperCase() + clean.slice(1);
        return title.length > 60 ? title.substring(0, 57) + '...' : title;
    }

    // ── Chart Card Renderer ───────────────────────────────────────────────────
    function renderChartCard(data) {
        let config;
        try {
            config = JSON.parse(data.chart_config);
        } catch (e) {
            console.error('Failed to parse chart config:', e);
            return;
        }

        // Show charts section header
        chartsSectionTitle.style.display = 'block';

        const cardId    = `chart-card-${++chartCounter}`;
        const canvasId  = `chart-canvas-${chartCounter}`;
        const chartTitle = deriveChartTitle(data.question);

        const card = document.createElement('div');
        card.className = 'chart-card';
        card.id = cardId;
        const isPie = config.type === 'pie' || config.type === 'doughnut';
        const numLabels = config.data?.labels?.length || 0;
        let chartWidth = '100%';
        if (!isPie && numLabels > 10) {
            chartWidth = (numLabels * 40) + 'px'; // 40px per bar/point
        }

        card.innerHTML = `
            <div class="card-controls">
                <select class="chart-type-picker" style="padding:0; border:1px solid #ccc; border-radius:4px; font-size:0.85rem; outline:none; background: var(--card-bg); color: var(--text-main);">
                    <option value="bar" ${config.type==='bar'?'selected':''}>Bar</option>
                    <option value="line" ${config.type==='line'?'selected':''}>Line</option>
                    <option value="pie" ${config.type==='pie'?'selected':''}>Pie</option>
                    <option value="doughnut" ${config.type==='doughnut'?'selected':''}>Doughnut</option>
                </select>
                <button class="control-btn export-chart-btn" title="Export Image">📥</button>
                <button class="control-btn expand-btn" title="Expand">⤢</button>
                <button class="control-btn minimize-btn" title="Minimize">-</button>
                <button class="control-btn close-btn" title="Remove">X</button>
            </div>
            <p class="chart-title card-title" style="display:flex; align-items:center; gap:0.4rem;">
                <img src="/static/icons8-chart-96.png" width="18" height="18" alt="Chart"> ${escapeHtml(chartTitle)}
            </p>
            <p class="chart-question"><strong>Q:</strong> ${escapeHtml(data.question)}</p>
            <div style="flex:1; width:100%; overflow-x:auto; overflow-y:hidden;">
                <div class="chart-canvas-wrapper" style="height:100%; min-width:100%; width:${chartWidth}; position:relative;">
                    <canvas id="${canvasId}"></canvas>
                </div>
            </div>
        `;

        // Append so charts flow left-to-right, new ones added beside old ones
        chartsGrid.appendChild(card);

        // Restore saved layout before attaching observers
        restoreCardLayout(card);
        attachResizeObserver(card);

        const minimizeBtn = card.querySelector('.minimize-btn');
        minimizeBtn.addEventListener('click', () => {
            card.classList.toggle('card-minimized');
            const isMin = card.classList.contains('card-minimized');
            minimizeBtn.innerHTML = isMin ? '+' : '-';
            saveCardLayout(card.id, { minimized: isMin });
        });

        const closeBtn = card.querySelector('.close-btn');
        closeBtn.addEventListener('click', () => {
            removeCardLayout(card.id);
            card.remove();
            checkEmptyState();
        });

        const expandBtn = card.querySelector('.expand-btn');
        expandBtn.addEventListener('click', () => {
            chartModal.style.display = 'flex';
            const ctxModal = document.getElementById('modalCanvas').getContext('2d');
            if (modalChartInstance) {
                modalChartInstance.destroy();
            }
            
            // Re-parse config to avoid reference mutations
            const mConfig = JSON.parse(data.chart_config);
            
            // Re-apply palette logic
            if (mConfig.data && mConfig.data.datasets) {
                const palette = [
                    'rgba(99, 102, 241, 0.85)',
                    'rgba(16, 185, 129, 0.85)',
                    'rgba(245, 158, 11, 0.85)',
                    'rgba(239, 68, 68, 0.85)',
                    'rgba(59, 130, 246, 0.85)',
                    'rgba(168, 85, 247, 0.85)',
                    'rgba(236, 72, 153, 0.85)',
                ];
                mConfig.data.datasets.forEach((ds, i) => {
                    if (!ds.backgroundColor) {
                        ds.backgroundColor = palette[i % palette.length];
                    }
                    if (!ds.borderColor) {
                        ds.borderColor = palette[i % palette.length].replace('0.85', '1');
                    }
                    if (mConfig.type === 'line') {
                        ds.tension     = ds.tension ?? 0.4;
                        ds.fill        = ds.fill    ?? false;
                        ds.pointRadius = 4; // larger points for modal
                        ds.borderWidth = 3;
                    }
                    if (mConfig.type === 'bar') {
                        ds.borderWidth = ds.borderWidth ?? 1;
                        ds.borderRadius = ds.borderRadius ?? 4;
                    }
                });
            }

            const cTitle = mConfig.options?.plugins?.title?.text || chartTitle;
            mConfig.options = {
                responsive: true,
                maintainAspectRatio: false,
                plugins: {
                    title: {
                        display: true,
                        text: cTitle,
                        font: { size: 18, weight: '600' },
                        color: '#1F2937',
                        padding: { bottom: 16 }
                    },
                    legend: {
                        display: true,
                        position: 'bottom',
                        labels: {
                            color: '#4B5563',
                            boxWidth: 16,
                            padding: 20,
                            font: { size: 13 },
                            usePointStyle: true
                        }
                    },
                    tooltip: { mode: 'index', intersect: false }
                },
                scales: mConfig.type !== 'pie' && mConfig.type !== 'doughnut'
                    ? {
                        x: {
                            grid: { color: 'rgba(0,0,0,0.05)' },
                            ticks: { color: '#6B7280', font: { size: 12 } }
                        },
                        y: {
                            grid: { color: 'rgba(0,0,0,0.05)' },
                            beginAtZero: true,
                            ticks: { color: '#6B7280', font: { size: 12 } }
                        }
                      }
                    : {},
            };

            // Apply width for horizontal scrolling in modal
            const innerDiv = document.getElementById('modalChartInner');
            if (innerDiv) {
                innerDiv.style.width = chartWidth;
            }

            modalChartInstance = new Chart(ctxModal, mConfig);
        });

        // Render Chart.js chart into the canvas
        const ctx = document.getElementById(canvasId).getContext('2d');

        // Apply default styling to datasets if not set
        if (config.data && config.data.datasets) {
            const palette = [
                'rgba(99, 102, 241, 0.85)',
                'rgba(16, 185, 129, 0.85)',
                'rgba(245, 158, 11, 0.85)',
                'rgba(239, 68, 68, 0.85)',
                'rgba(59, 130, 246, 0.85)',
                'rgba(168, 85, 247, 0.85)',
                'rgba(236, 72, 153, 0.85)',
            ];
            config.data.datasets.forEach((ds, i) => {
                if (!ds.backgroundColor) {
                    ds.backgroundColor = palette[i % palette.length];
                }
                if (!ds.borderColor) {
                    ds.borderColor = palette[i % palette.length].replace('0.85', '1');
                }
                if (config.type === 'line') {
                    ds.tension     = ds.tension ?? 0.4;
                    ds.fill        = ds.fill    ?? false;
                    ds.pointRadius = 3;
                    ds.borderWidth = 2;
                }
                if (config.type === 'bar') {
                    ds.borderWidth = ds.borderWidth ?? 1;
                    ds.borderRadius = ds.borderRadius ?? 4;
                }
            });
        }

        // Chart.js options: always show title + legend
        const chartJsTitle = config.options?.plugins?.title?.text || chartTitle;

        config.options = {
            responsive: true,
            maintainAspectRatio: false,
            plugins: {
                title: {
                    display: true,
                    text: chartJsTitle,
                    font: { size: 13, weight: '600' },
                    color: '#1F2937',
                    padding: { bottom: 8 }
                },
                legend: {
                    display: true,
                    position: 'bottom',
                    labels: {
                        color: '#4B5563',
                        boxWidth: 12,
                        padding: 10,
                        font: { size: 11 },
                        usePointStyle: true
                    }
                },
                tooltip: { mode: 'index', intersect: false }
            },
            scales: config.type !== 'pie' && config.type !== 'doughnut'
                ? {
                    x: {
                        grid: { color: 'rgba(0,0,0,0.05)' },
                        ticks: { color: '#6B7280', font: { size: 10 } }
                    },
                    y: {
                        grid: { color: 'rgba(0,0,0,0.05)' },
                        beginAtZero: true,
                        ticks: { color: '#6B7280', font: { size: 10 } }
                    }
                  }
                : {},
            ...(config.options || {})
        };

        // Always keep our title and legend overrides
        config.options.plugins = {
            ...config.options.plugins,
            title: {
                display: true,
                text: chartJsTitle,
                font: { size: 13, weight: '600' },
                color: '#1F2937',
                padding: { bottom: 8 }
            },
            legend: {
                display: true,
                position: 'bottom',
                labels: {
                    color: '#4B5563',
                    boxWidth: 12,
                    padding: 10,
                    font: { size: 11 },
                    usePointStyle: true
                }
            }
        };

        let chartInstance = new Chart(ctx, config);

        // Interactive chart controls logic
        const typePicker = card.querySelector('.chart-type-picker');
        typePicker.addEventListener('change', (e) => {
            const newType = e.target.value;
            config.type = newType;
            
            const isPie = newType === 'pie' || newType === 'doughnut';
            let newChartWidth = '100%';
            if (!isPie && numLabels > 10) {
                newChartWidth = (numLabels * 40) + 'px';
            }
            card.querySelector('.chart-canvas-wrapper').style.width = newChartWidth;
            
            if (chartInstance) chartInstance.destroy();
            chartInstance = new Chart(ctx, config);
        });

        const exportBtn = card.querySelector('.export-chart-btn');
        exportBtn.addEventListener('click', () => {
            const link = document.createElement('a');
            link.download = chartTitle + '.png';
            link.href = chartInstance.toBase64Image();
            link.click();
        });
    }

    // Track insight card counter
    let insightCounter = 0;

    // ── Insight Card Renderer ─────────────────────────────────────────────────
    function renderInsightCard(data) {
        // Show insights section header
        insightsSectionTitle.style.display = 'block';

        const insightId = `insight-card-${++insightCounter}`;
        const card = document.createElement('div');
        card.className = 'insight-card';
        card.id = insightId;
        card.innerHTML = `
            <div class="card-controls">
                <button class="control-btn minimize-btn" title="Minimize">-</button>
                <button class="control-btn close-btn" title="Remove">X</button>
            </div>
            <h3 class="card-title">💡 Business Insight</h3>
            <p class="q-text"><strong>Q:</strong> ${escapeHtml(data.question)}</p>
            <p class="i-text"><strong>Insight:</strong> ${escapeHtml(data.insight || data.answer || 'No insight available')}</p>
            <div class="insight-table-container"></div>
        `;
        insightsList.prepend(card);

        if (data.raw_result && data.raw_result !== 'no results found') {
            const tableContainer = card.querySelector('.insight-table-container');
            createSmartTable(data.raw_result, tableContainer);
        }

        // Restore saved layout before attaching observers
        restoreCardLayout(card);
        attachResizeObserver(card);

        const minimizeBtn = card.querySelector('.minimize-btn');
        minimizeBtn.addEventListener('click', () => {
            card.classList.toggle('card-minimized');
            const isMin = card.classList.contains('card-minimized');
            minimizeBtn.innerHTML = isMin ? '+' : '-';
            saveCardLayout(card.id, { minimized: isMin });
        });

        const closeBtn = card.querySelector('.close-btn');
        closeBtn.addEventListener('click', () => {
            removeCardLayout(card.id);
            card.remove();
            checkEmptyState();
        });
    }
});
