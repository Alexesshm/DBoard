/**
 * DBoard - Dashboard Main Script
 * Fetches and displays marketplace analytics data with charts.
 */

// State
let isLoading = false;
let hasError = false;
let stocksChart = null;
let dashboardData = null;
let currentMarketplace = 'wb';  // 'wb' or 'ozon'
let currentPeriod = 'today';    // 'today', 'yesterday', 'days_3', 'days_7'
let currentDetailTab = 'stocks'; // 'stocks', 'orders', 'regions'

/**
 * Format number as Russian currency
 */
function formatCurrency(value) {
    if (value === null || value === undefined || isNaN(value)) {
        return '—';
    }
    return new Intl.NumberFormat('ru-RU', {
        style: 'currency',
        currency: 'RUB',
        maximumFractionDigits: 0
    }).format(value);
}

/**
 * Format number with locale
 */
function formatNumber(value) {
    if (value === null || value === undefined || isNaN(value)) {
        return '—';
    }
    return value.toLocaleString('ru-RU');
}

/**
 * Show loading state
 */
function showLoading() {
    isLoading = true;
    const mpSales = document.getElementById('mp-sales');
    const mpStocks = document.getElementById('mp-stocks');

    if (mpSales) mpSales.textContent = 'Загрузка...';
    if (mpStocks) mpStocks.textContent = 'Загрузка...';
    document.getElementById('last-update').textContent = 'обновление...';

    const productsGrid = document.getElementById('productsGrid');
    if (productsGrid) {
        productsGrid.innerHTML = `
            <div class="loading-placeholder">
                <div class="spinner"></div>
                <p>Загрузка данных...</p>
            </div>
        `;
    }
}

/**
 * Show error state
 */
function showError(message) {
    hasError = true;
    isLoading = false;

    const mpSales = document.getElementById('mp-sales');
    const mpStocks = document.getElementById('mp-stocks');

    if (mpSales) mpSales.textContent = '—';
    if (mpStocks) mpStocks.textContent = '—';
    document.getElementById('last-update').textContent = 'ошибка загрузки';

    const productsGrid = document.getElementById('productsGrid');
    if (productsGrid) {
        productsGrid.innerHTML = `
            <div class="error-state">
                <span class="error-icon">⚠️</span>
                <h3>Не удалось загрузить данные</h3>
                <p>${message}</p>
                <button onclick="fetchDashboardData()" class="retry-btn">Попробовать снова</button>
            </div>
        `;
    }
}

/**
 * Update UI with fetched data
 */
function updateUI(data) {
    // Update header info with user's timezone
    const lastUpdateEl = document.getElementById('last-update');
    const nextUpdateEl = document.getElementById('next-update');

    if (data.last_update) {
        // Parse the date and format in user's timezone
        const lastUpdateDate = new Date(data.last_update.replace(/(\d{2})\.(\d{2})\.(\d{4}) (\d{2}):(\d{2})/, '$3-$2-$1T$4:$5:00'));

        if (!isNaN(lastUpdateDate.getTime())) {
            // Format in user's local time
            const options = { day: '2-digit', month: '2-digit', year: 'numeric', hour: '2-digit', minute: '2-digit' };
            lastUpdateEl.textContent = lastUpdateDate.toLocaleString('ru-RU', options);

            // Calculate next update (every 2 hours on the hour)
            const now = new Date();
            const nextUpdate = new Date(lastUpdateDate);
            nextUpdate.setMinutes(0, 0, 0); // Round to hour
            nextUpdate.setHours(nextUpdate.getHours() + 2); // Add 2 hours

            // If next update is in the past, calculate from now
            while (nextUpdate <= now) {
                nextUpdate.setHours(nextUpdate.getHours() + 2);
            }

            nextUpdateEl.textContent = nextUpdate.toLocaleString('ru-RU', { hour: '2-digit', minute: '2-digit' });
        } else {
            lastUpdateEl.textContent = data.last_update;
            nextUpdateEl.textContent = '~2ч';
        }
    } else {
        lastUpdateEl.textContent = 'неизвестно';
        nextUpdateEl.textContent = '—';
    }

    // Update marketplace-specific UI (Sales, Stocks, Chart, Product Grid)
    updateMarketplaceUI();

    // Update stock monitoring section
    updateStockMonitoring();
}

/**
 * Fetch dashboard data from JSON file
 */
async function fetchDashboardData() {
    showLoading();

    try {
        const response = await fetch('dashboard_data.json?' + Date.now());

        if (!response.ok) {
            if (response.status === 404) {
                throw new Error('Файл данных не найден. Запустите скрипт обновления данных (run_all.py).');
            }
            throw new Error(`HTTP ошибка: ${response.status}`);
        }

        const data = await response.json();

        if (!data || !data.summary) {
            throw new Error('Некорректный формат данных');
        }

        // Store data globally for marketplace switching
        dashboardData = data;

        updateUI(data);
        hasError = false;

    } catch (error) {
        console.error('Error fetching dashboard data:', error);
        showError(error.message || 'Неизвестная ошибка');
    }

    isLoading = false;
}

/**
 * Switch between marketplaces (WB/OZON)
 */
function switchMarketplace(mp) {
    if (mp === currentMarketplace || !dashboardData) return;

    currentMarketplace = mp;

    // Update tab buttons (both tab-btn and mp-btn)
    document.querySelectorAll('.tab-btn, .mp-btn').forEach(btn => {
        btn.classList.remove('active');
        if (btn.dataset.mp === mp) {
            btn.classList.add('active');
        }
    });

    // Update charts and summaries for selected marketplace
    updateMarketplaceUI();

    // Update detail section title
    const detailTitle = document.getElementById('detailTitle');
    if (detailTitle) {
        detailTitle.textContent = `Детальная аналитика ${mp === 'wb' ? 'Wildberries' : 'Ozon'}`;
    }

    // Refresh detail table
    updateDetailTable();

    // Refresh stock monitoring for selected marketplace
    updateStockMonitoring();
}

/**
 * Switch period (today, yesterday, etc.)
 */
function switchPeriod(period) {
    if (period === currentPeriod || !dashboardData) return;

    currentPeriod = period;

    // Update buttons
    document.querySelectorAll('.period-btn').forEach(btn => {
        btn.classList.remove('active');
        if (btn.dataset.period === period) {
            btn.classList.add('active');
        }
    });

    // Update UI components that depend on sales data
    updateMarketplaceUI();
}

/**
 * Switch between detailed tabs (Stocks/Orders/Regions)
 */
function switchDetailTab(tab) {
    if (tab === currentDetailTab) return;

    currentDetailTab = tab;

    // Update tab buttons
    document.querySelectorAll('.detail-tab-btn').forEach(btn => {
        btn.classList.remove('active');
        if (btn.dataset.tab === tab) {
            btn.classList.add('active');
        }
    });

    updateDetailTable();
}

/**
 * Update the detailed table based on current marketplace and selected tab
 */
function updateDetailTable() {
    if (!dashboardData) return;

    const container = document.getElementById('detailTableContainer');
    if (!container) return;

    const mpKey = currentMarketplace;
    const tab = currentDetailTab;

    let html = '';

    if (tab === 'stocks') {
        const stocksData = dashboardData.stocks?.[mpKey] || {};
        const stocks = stocksData.by_warehouse || [];
        html = `
            <table class="detail-table">
                <thead>
                    <tr>
                        <th class="table-rank">#</th>
                        <th>Склад</th>
                        <th style="text-align: right;">Остаток</th>
                        <th style="text-align: right;">Товаров</th>
                    </tr>
                </thead>
                <tbody>
                    ${stocks.map((s, i) => `
                        <tr>
                            <td class="table-rank">${i + 1}</td>
                            <td><span class="table-value-main">${s.name}</span></td>
                            <td style="text-align: right;"><span class="table-value-main">${formatNumber(s.quantity)}</span><span class="table-value-sub">шт.</span></td>
                            <td style="text-align: right;">${s.items_count || 0}</td>
                        </tr>
                    `).join('')}
                </tbody>
            </table>
        `;
    } else if (tab === 'orders') {
        const salesPeriodData = dashboardData.period_data?.[currentPeriod]?.[mpKey] || {};
        const sales = salesPeriodData.sales_by_warehouse || [];
        html = `
            <table class="detail-table">
                <thead>
                    <tr>
                        <th class="table-rank">#</th>
                        <th>Склад отгрузки</th>
                        <th style="text-align: right;">Заказов</th>
                        <th style="text-align: right;">Выручка</th>
                    </tr>
                </thead>
                <tbody>
                    ${sales.map((s, i) => {
            const products = s.by_product || [];
            const tooltipContent = products.length > 0
                ? products.map(p => `<div class="wh-tooltip-row"><span>${p.article}</span><span>${p.count} шт.</span></div>`).join('')
                : '<div class="wh-tooltip-empty">Нет данных о товарах</div>';
            return `
                        <tr class="orders-row-with-tooltip">
                            <td class="table-rank">${i + 1}</td>
                            <td class="orders-cell-with-tooltip">
                                <span class="table-value-main">${s.name}</span>
                                <div class="orders-tooltip">
                                    <div class="orders-tooltip-title">Товары со склада ${s.name}:</div>
                                    <div class="orders-tooltip-content">${tooltipContent}</div>
                                </div>
                            </td>
                            <td style="text-align: right;"><span class="table-value-main">${s.count}</span><span class="table-value-sub">шт.</span></td>
                            <td style="text-align: right;" class="table-positive">${formatCurrency(s.revenue)}</td>
                        </tr>
                    `;
        }).join('')}
                </tbody>
            </table>
        `;
    } else if (tab === 'regions') {
        html = buildStockMatrix(mpKey);
    }

    if (!html || html.includes('<tbody></tbody>')) {
        container.innerHTML = '<div class="empty-data" style="padding: 40px; text-align: center; opacity: 0.5;">Нет данных для отображения</div>';
    } else {
        container.innerHTML = html;
    }
}

/**
 * Update UI elements for current marketplace
 */
function updateMarketplaceUI() {
    if (!dashboardData) return;

    const mpKey = currentMarketplace;
    const mpName = mpKey === 'wb' ? 'Wildberries' : 'Ozon';
    const mpType = mpKey === 'wb' ? 'FBW' : 'FBO';

    // Get Data based on Period
    // Sales data depends on period
    const periodData = dashboardData.period_data?.[currentPeriod]?.[mpKey] || {};
    // Stocks data is always current (from 'stocks')
    const stocksData = dashboardData.stocks?.[mpKey] || {};

    // Update dynamic stats
    const mpSales = periodData.revenue || 0;
    // Redemptions: use redemptions_revenue for both marketplaces
    const mpRedemptions = periodData.redemptions_revenue || 0;

    document.getElementById('mp-sales').textContent = formatCurrency(mpSales);
    document.getElementById('mp-redemptions').textContent = formatCurrency(mpRedemptions);

    // Update period-specific labels
    const periodLabels = {
        'today': { title: 'за сегодня', short: 'Сегодня' },
        'yesterday': { title: 'за вчера', short: 'Вчера' },
        'days_3': { title: 'за 3 дня', short: '3 дня' },
        'days_7': { title: 'за 7 дней', short: '7 дней' },
        'days_30': { title: 'за 30 дней', short: '30 дней' }
    };

    const periodInfo = periodLabels[currentPeriod] || periodLabels['today'];

    const salesTitle = document.getElementById('sales-title');
    const salesLabel = document.getElementById('sales-label');
    const redemptionsLabel = document.getElementById('redemptions-label');

    if (salesTitle) salesTitle.textContent = `Заказы`;
    if (salesLabel) salesLabel.textContent = periodInfo.title;
    if (redemptionsLabel) redemptionsLabel.textContent = periodInfo.title;

    // Populate other period values (exclude current period)
    const periodsOrder = ['today', 'yesterday', 'days_3', 'days_7', 'days_30'];
    const otherPeriods = periodsOrder.filter(p => p !== currentPeriod);

    const salesPeriodsContainer = document.getElementById('sales-periods');
    const redemptionsPeriodsContainer = document.getElementById('redemptions-periods');

    if (salesPeriodsContainer) {
        salesPeriodsContainer.innerHTML = otherPeriods.map(period => {
            const pData = dashboardData.period_data?.[period]?.[mpKey] || {};
            const value = pData.revenue || 0;
            return `<div class="period-item">
                <span class="period-label">${periodLabels[period].short}</span>
                <span class="period-value">${formatCurrency(value)}</span>
            </div>`;
        }).join('');
    }

    if (redemptionsPeriodsContainer) {
        redemptionsPeriodsContainer.innerHTML = otherPeriods.map(period => {
            const pData = dashboardData.period_data?.[period]?.[mpKey] || {};
            const value = pData.redemptions_revenue || 0;
            return `<div class="period-item">
                <span class="period-label">${periodLabels[period].short}</span>
                <span class="period-value">${formatCurrency(value)}</span>
            </div>`;
        }).join('');
    }

    // Update icons colors based on marketplace
    const salesIcon = document.getElementById('salesIcon');
    const redemptionsIcon = document.getElementById('redemptionsIcon');
    if (mpKey === 'wb') {
        salesIcon.style.filter = 'drop-shadow(0 0 10px #7c3aed)';
        redemptionsIcon.style.filter = 'drop-shadow(0 0 10px #7c3aed)';
    } else {
        salesIcon.style.filter = 'drop-shadow(0 0 10px #0ea5e9)';
        redemptionsIcon.style.filter = 'drop-shadow(0 0 10px #0ea5e9)';
    }

    // Update chart title and subtitle
    const chartTitle = document.getElementById('chartTitle');
    const chartSubtitle = document.getElementById('chartSubtitle');
    if (chartTitle) {
        chartTitle.textContent = `📊 Остатки ${mpName} по регионам`;
    }
    if (chartSubtitle) {
        chartSubtitle.textContent = `Группировка по кластерам → склады → товары (${mpType})`;
    }

    // Update horizontal clustered bar chart (Stocks data)
    const chartData = stocksData.chart_data;
    if (chartData) {
        createClusteredHorizontalChart(chartData, mpKey);
    } else {
        // No chart data - show empty state
        const ctxContainer = document.querySelector('.chart-container');
        if (ctxContainer) {
            ctxContainer.innerHTML = `
                <div class="chart-empty-state">
                    <div class="chart-empty-icon">📦</div>
                    <div class="chart-empty-text">Нет данных о складах для ${mpName}</div>
                </div>
            `;
        }
    }

    // Update stocks summary by product (Stocks data)
    const stocksByProduct = stocksData.by_product;
    createStocksSummary(stocksByProduct, mpType);

    // Update sales by product grid (Sales Period Data)
    const salesByProduct = periodData.sales_by_product;
    createProductsGrid(salesByProduct, mpKey);

    // Update products section title based on period
    const productsSectionTitle = document.getElementById('products-section-title');
    if (productsSectionTitle) {
        productsSectionTitle.textContent = `🔥 Продажи по товарам`;
    }

    // Initial table load
    updateDetailTable();
}

/**
 * Create stacked bar chart for stocks by warehouse and product
 */
function createStocksChart(chartData) {
    const ctx = document.getElementById('stocksChart');
    if (!ctx) return;

    // Destroy existing chart
    if (stocksChart) {
        stocksChart.destroy();
    }

    if (!chartData || !chartData.datasets || chartData.datasets.length === 0) {
        ctx.parentElement.innerHTML = '<div class="empty-data">Нет данных для диаграммы</div>';
        return;
    }

    stocksChart = new Chart(ctx, {
        type: 'bar',
        data: chartData,
        options: {
            responsive: true,
            maintainAspectRatio: false,
            plugins: {
                legend: {
                    display: false
                },
                tooltip: {
                    mode: 'index',
                    intersect: false,
                    backgroundColor: 'rgba(0, 0, 0, 0.8)',
                    titleColor: '#fff',
                    bodyColor: '#fff',
                    borderColor: 'rgba(255, 255, 255, 0.1)',
                    borderWidth: 1,
                    callbacks: {
                        label: function (context) {
                            if (context.raw === 0) return null;
                            return `${context.dataset.label}: ${context.raw} шт.`;
                        },
                        // Add cluster name to tooltip title
                        title: function (context) {
                            const warehouseName = chartData.labels[context[0].dataIndex];
                            // Find which cluster this warehouse belongs to
                            if (chartData.clusters) {
                                for (const cluster of chartData.clusters) {
                                    if (context[0].dataIndex >= cluster.start_index &&
                                        context[0].dataIndex <= cluster.end_index) {
                                        return `${warehouseName} (${cluster.name})`;
                                    }
                                }
                            }
                            return warehouseName;
                        }
                    }
                }
            },
            scales: {
                x: {
                    stacked: true,
                    ticks: {
                        color: 'rgba(255, 255, 255, 0.7)',
                        maxRotation: 45,
                        minRotation: 45
                    },
                    grid: {
                        color: 'rgba(255, 255, 255, 0.05)'
                    }
                },
                y: {
                    stacked: true,
                    ticks: {
                        color: 'rgba(255, 255, 255, 0.7)'
                    },
                    grid: {
                        color: 'rgba(255, 255, 255, 0.05)'
                    },
                    title: {
                        display: true,
                        text: 'Остатки (шт.)',
                        color: 'rgba(255, 255, 255, 0.5)'
                    }
                }
            }
        }
    });

    // Create custom legend
    const legendContainer = document.getElementById('chartLegend');
    if (legendContainer) {
        legendContainer.innerHTML = chartData.datasets.map(ds => `
            <div class="legend-item">
                <span class="legend-color" style="background: ${ds.backgroundColor}"></span>
                <span class="legend-label">${ds.label}</span>
            </div>
        `).join('');
    }

    // Add cluster headers if cluster data is available
    if (chartData.clusters && chartData.clusters.length > 0) {
        addClusterHeaders(chartData.clusters, chartData.labels.length);
    }
}

/**
 * Create horizontal clustered stocks chart with region grouping
 */
function createClusteredHorizontalChart(chartData, mpType) {
    const container = document.querySelector('.chart-container');
    if (!container) return;

    // Destroy existing Chart.js chart if present
    if (stocksChart) {
        stocksChart.destroy();
        stocksChart = null;
    }

    if (!chartData || !chartData.datasets || chartData.datasets.length === 0) {
        container.innerHTML = `
            <div class="chart-empty-state">
                <div class="chart-empty-icon">📦</div>
                <div class="chart-empty-text">Нет данных об остатках</div>
            </div>
        `;
        return;
    }

    const warehouses = chartData.labels || [];
    const datasets = chartData.datasets || [];
    const clusters = mpType === 'wb' ? WB_CLUSTERS : OZON_CLUSTERS;

    // Build warehouse data structure: { warehouseName: { article: qty, ... }, ... }
    const warehouseData = {};
    warehouses.forEach((wh, idx) => {
        warehouseData[wh] = {};
        datasets.forEach(ds => {
            if (ds.data[idx] > 0) {
                warehouseData[wh][ds.label] = {
                    qty: ds.data[idx],
                    color: ds.backgroundColor
                };
            }
        });
    });

    // Group warehouses by cluster
    // Warehouses with total stock = 1 go to 'Прочие' regardless of cluster
    const clusteredData = {};
    warehouses.forEach(wh => {
        const whData = warehouseData[wh];
        let whTotal = 0;
        Object.values(whData).forEach(p => whTotal += p.qty);

        // Determine cluster: warehouses with 1 item total go to 'Прочие'
        let clusterName;
        if (whTotal === 1) {
            clusterName = 'Прочие';
        } else {
            clusterName = getWarehouseCluster(wh, mpType === 'wb' ? 'wb' : 'ozon');
        }

        if (!clusteredData[clusterName]) {
            clusteredData[clusterName] = {
                name: clusterName,
                warehouses: [],
                totalStock: 0
            };
        }

        clusteredData[clusterName].warehouses.push({
            name: wh,
            products: whData,
            total: whTotal
        });
        clusteredData[clusterName].totalStock += whTotal;
    });

    // Sort clusters by total stock (descending)
    const sortedClusters = Object.values(clusteredData).sort((a, b) => b.totalStock - a.totalStock);

    // Find max warehouse total for bar scaling
    let maxWarehouseTotal = 0;
    sortedClusters.forEach(cluster => {
        cluster.warehouses.forEach(wh => {
            if (wh.total > maxWarehouseTotal) maxWarehouseTotal = wh.total;
        });
    });

    // Build product legend (unique articles with colors)
    const productColors = {};
    datasets.forEach(ds => {
        productColors[ds.label] = ds.backgroundColor;
    });

    // Generate HTML
    let html = `
        <div class="horizontal-chart-legend">
            ${Object.entries(productColors).map(([article, color]) => `
                <div class="h-legend-item">
                    <span class="h-legend-color" style="background: ${color}"></span>
                    <span class="h-legend-label">${article}</span>
                </div>
            `).join('')}
        </div>
        <div class="clustered-stocks-container">
    `;

    sortedClusters.forEach((cluster, clusterIdx) => {
        // Sort warehouses within cluster by total (descending)
        cluster.warehouses.sort((a, b) => b.total - a.total);

        html += `
            <div class="region-group" data-cluster="${clusterIdx}">
                <div class="region-header" onclick="toggleRegionGroup(this)">
                    <div class="region-header-left">
                        <span class="region-toggle">▼</span>
                        <span class="region-icon">🌍</span>
                        <span class="region-name">${cluster.name}</span>
                    </div>
                    <div class="region-header-right">
                        <div class="region-stats">
                            <span class="region-stat">
                                <span class="region-stat-value">${cluster.warehouses.length}</span> складов
                            </span>
                        </div>
                        <div class="region-total">${formatNumber(cluster.totalStock)} шт</div>
                    </div>
                </div>
                <div class="region-content">
        `;

        cluster.warehouses.forEach(wh => {
            const products = wh.products;
            const total = wh.total;

            // Build stacked bar segments
            let barHtml = '';
            Object.entries(products).forEach(([article, data]) => {
                const widthPercent = maxWarehouseTotal > 0 ? (data.qty / maxWarehouseTotal) * 100 : 0;
                const showLabel = widthPercent > 5; // Only show label if segment is wide enough
                barHtml += `
                    <div class="bar-segment" 
                         style="width: ${widthPercent}%; background: ${data.color};"
                         title="${article}: ${data.qty} шт"
                         onmouseenter="showSegmentTooltip(event, '${article}', ${data.qty})"
                         onmouseleave="hideSegmentTooltip()">
                        ${showLabel ? `<span class="bar-segment-label">${data.qty}</span>` : ''}
                    </div>
                `;
            });

            html += `
                <div class="warehouse-row">
                    <div class="warehouse-name" title="${wh.name}">${wh.name}</div>
                    <div class="warehouse-bar-container">
                        <div class="warehouse-bar">${barHtml}</div>
                        <div class="warehouse-total">${formatNumber(total)}<span>шт</span></div>
                    </div>
                </div>
            `;
        });

        html += `
                </div>
            </div>
        `;
    });

    html += '</div>';

    container.innerHTML = html;

    // Update legend container (hide old one)
    const oldLegend = document.getElementById('chartLegend');
    if (oldLegend) oldLegend.innerHTML = '';

    // Remove old cluster headers
    const existingHeaders = document.querySelectorAll('.cluster-labels-container');
    existingHeaders.forEach(el => el.remove());
}

/**
 * Toggle region group visibility
 */
function toggleRegionGroup(headerEl) {
    const content = headerEl.nextElementSibling;
    const toggle = headerEl.querySelector('.region-toggle');

    if (content.classList.contains('collapsed')) {
        content.classList.remove('collapsed');
        headerEl.classList.remove('collapsed');
        toggle.textContent = '▼';
    } else {
        content.classList.add('collapsed');
        headerEl.classList.add('collapsed');
        toggle.textContent = '▶';
    }
}

/**
 * Show tooltip for bar segment
 */
function showSegmentTooltip(event, article, qty) {
    hideSegmentTooltip();

    const tooltip = document.createElement('div');
    tooltip.id = 'segmentTooltip';
    tooltip.className = 'segment-tooltip';
    tooltip.innerHTML = `
        <div class="segment-tooltip-article">${article}</div>
        <div class="segment-tooltip-qty">${formatNumber(qty)} шт</div>
    `;

    document.body.appendChild(tooltip);

    // Position tooltip
    const rect = event.target.getBoundingClientRect();
    tooltip.style.left = `${rect.left + rect.width / 2}px`;
    tooltip.style.top = `${rect.top - 50 + window.scrollY}px`;
    tooltip.style.transform = 'translateX(-50%)';
}

/**
 * Hide segment tooltip
 */
function hideSegmentTooltip() {
    const existing = document.getElementById('segmentTooltip');
    if (existing) existing.remove();
}

/**
 * Add visual cluster headers to the chart
 */
function addClusterHeaders(clusters, totalWarehouses) {
    // Remove existing cluster headers
    const existingHeaders = document.querySelectorAll('.cluster-labels-container');
    existingHeaders.forEach(el => el.remove());

    const chartContainer = document.querySelector('.chart-container');
    if (!chartContainer) return;

    // Create container for cluster labels
    const labelsContainer = document.createElement('div');
    labelsContainer.className = 'cluster-labels-container';

    clusters.forEach((cluster, idx) => {
        const label = document.createElement('div');
        label.className = 'cluster-label';

        // Calculate position percentage
        const startPercent = (cluster.start_index / totalWarehouses) * 100;
        const endPercent = ((cluster.end_index + 1) / totalWarehouses) * 100;
        const width = endPercent - startPercent;

        label.style.left = `${startPercent}%`;
        label.style.width = `${width}%`;

        label.innerHTML = `
            <span class="cluster-icon">🌍</span>
            <span class="cluster-name">${cluster.name}</span>
            <span class="cluster-stats">${cluster.warehouse_count} ${cluster.warehouse_count === 1 ? 'склад' : 'складов'} • ${formatNumber(cluster.total_stock)} шт</span>
        `;

        labelsContainer.appendChild(label);
    });

    // Insert after chart subtitle
    const subtitle = document.getElementById('chartSubtitle');
    if (subtitle && subtitle.parentNode) {
        subtitle.parentNode.insertBefore(labelsContainer, subtitle.nextSibling);
    } else {
        chartContainer.insertBefore(labelsContainer, chartContainer.firstChild);
    }
}


/**
 * Create stocks summary by product
 */
function createStocksSummary(stocksByProduct, mpType = 'FBW') {
    const container = document.getElementById('stocksSummary');
    if (!container) return;

    if (!stocksByProduct || stocksByProduct.length === 0) {
        container.innerHTML = '<div class="empty-data">Нет данных об остатках</div>';
        return;
    }

    const totalStocks = stocksByProduct.reduce((sum, p) => sum + p.quantity, 0);

    container.innerHTML = `
        <h4>📦 Общие остатки ${mpType} по товарам</h4>
        <div class="stocks-summary-grid">
            ${stocksByProduct.map((p, idx) => {
        const percent = totalStocks > 0 ? ((p.quantity / totalStocks) * 100).toFixed(1) : 0;

        // Build warehouse tooltip content
        const warehouseDetails = (p.by_warehouse || [])
            .map(wh => `<div class="tooltip-wh-item"><span>${wh.name}</span><span>${wh.quantity} шт</span></div>`)
            .join('');

        return `
                    <div class="stock-item" data-product-idx="${idx}">
                        <div class="stock-color" style="background: ${p.color}"></div>
                        <div class="stock-info">
                            <span class="stock-article">${p.article}</span>
                            <span class="stock-warehouses">${p.warehouses_count} складов</span>
                        </div>
                        <div class="stock-value">
                            <span class="stock-qty">${formatNumber(p.quantity)} шт.</span>
                            <span class="stock-percent">${percent}%</span>
                        </div>
                        ${p.by_warehouse && p.by_warehouse.length > 0 ? `
                        <div class="stock-tooltip">
                            <div class="tooltip-content">
                                ${warehouseDetails}
                            </div>
                        </div>
                        ` : ''}
                    </div>
                `;
    }).join('')}
        </div>
        <div class="stocks-total">
            <span>Итого:</span>
            <span>${formatNumber(totalStocks)} шт.</span>
        </div>
    `;
}

/**
 * Create products sales grid with warehouse breakdown tooltip
 */
function createProductsGrid(products, mpKey) {
    const container = document.getElementById('productsGrid');
    if (!container) return;

    if (!products || products.length === 0) {
        container.innerHTML = '<div class="empty-data">Нет данных о продажах за день</div>';
        return;
    }

    container.innerHTML = products.map((p, i) => {
        const trendIcon = i < 3 ? '🔥' : (i < 6 ? '📈' : '');

        // Build warehouse breakdown for tooltip
        let warehouseTooltip = '';
        if (p.by_warehouse && p.by_warehouse.length > 0) {
            warehouseTooltip = p.by_warehouse.map(wh =>
                `${wh.name}: ${wh.count} шт.`
            ).join('\n');
        } else {
            warehouseTooltip = 'Нет данных по складам';
        }

        return `
            <div class="product-card reveal" style="animation-delay: ${i * 0.05}s" 
                 data-warehouses='${JSON.stringify(p.by_warehouse || [])}'
                 onmouseenter="showWarehouseTooltip(event, this)"
                 onmouseleave="hideWarehouseTooltip()">
                <div class="product-rank">#${i + 1} ${trendIcon}</div>
                <div class="product-article">${p.article}</div>
                <div class="product-stats">
                    <div class="product-count">${p.count} <span>шт.</span></div>
                    <div class="product-revenue" style="color: #22c55e; font-weight: 600;">${formatCurrency(p.revenue)}</div>
                </div>
            </div>
        `;
    }).join('');
}

/**
 * Show sales tooltip (detail by products)
 */
function showSalesTooltip(event) {
    if (!dashboardData) return;

    const mpKey = currentMarketplace;
    const salesPeriodData = dashboardData.period_data?.[currentPeriod]?.[mpKey] || {};
    const products = salesPeriodData.sales_by_product || [];
    if (products.length === 0) return;

    // Remove existing
    hideSalesTooltip();

    const tooltip = document.createElement('div');
    tooltip.id = 'salesTooltip';
    tooltip.className = 'sales-tooltip';

    tooltip.innerHTML = `
        <div class="tooltip-header">
            <span class="tooltip-title">📊 Продажи по товарам</span>
        </div>
        <div class="tooltip-content">
            ${products.slice(0, 10).map(p => `
                <div class="tooltip-row">
                    <span class="tooltip-product-name">${p.article}</span>
                    <span class="tooltip-product-rev">${formatCurrency(p.revenue)} <small style="color:rgba(255,255,255,0.4); font-weight:400; margin-left:5px">${p.count} шт.</small></span>
                </div>
            `).join('')}
            ${products.length > 10 ? `<div style="text-align:center; padding-top:5px; font-size:0.75rem; opacity:0.4">...и еще ${products.length - 10} товаров</div>` : ''}
        </div>
    `;

    document.body.appendChild(tooltip);

    // Position
    const rect = event.currentTarget.getBoundingClientRect();
    tooltip.style.left = `${rect.left}px`;
    tooltip.style.top = `${rect.bottom + 10 + window.scrollY}px`;

    // Adjust if off-screen
    const tooltipRect = tooltip.getBoundingClientRect();
    if (tooltipRect.right > window.innerWidth) {
        tooltip.style.left = `${window.innerWidth - tooltipRect.width - 20}px`;
    }
}

/**
 * Hide sales tooltip
 */
function hideSalesTooltip() {
    const existing = document.getElementById('salesTooltip');
    if (existing) existing.remove();
}

/**
 * Show warehouse tooltip
 */
function showWarehouseTooltip(event, card) {
    const warehouses = JSON.parse(card.dataset.warehouses || '[]');
    if (!warehouses || warehouses.length === 0) return;

    // Remove existing tooltip
    hideWarehouseTooltip();

    // Create tooltip
    const tooltip = document.createElement('div');
    tooltip.id = 'warehouseTooltip';
    tooltip.className = 'warehouse-tooltip';

    const article = card.querySelector('.product-article').textContent;

    tooltip.innerHTML = `
        <div class="tooltip-header">
            <span class="tooltip-title">📦 ${article} — по складам</span>
        </div>
        <div class="tooltip-content">
            ${warehouses.map((wh, i) => `
                <div class="tooltip-row">
                    <span class="tooltip-wh-name">${wh.name}</span>
                    <span class="tooltip-wh-count">${wh.count} шт.</span>
                </div>
            `).join('')}
        </div>
    `;

    document.body.appendChild(tooltip);

    // Position tooltip near the card
    const rect = card.getBoundingClientRect();
    tooltip.style.left = `${rect.right + 10}px`;
    tooltip.style.top = `${rect.top + window.scrollY}px`;

    // Adjust if going off-screen
    const tooltipRect = tooltip.getBoundingClientRect();
    if (tooltipRect.right > window.innerWidth) {
        tooltip.style.left = `${rect.left - tooltipRect.width - 10}px`;
    }
}

/**
 * Hide warehouse tooltip
 */
function hideWarehouseTooltip() {
    const existing = document.getElementById('warehouseTooltip');
    if (existing) {
        existing.remove();
    }
}

/**
 * Create warehouse breakdown table
 */
function createWarehouseTable(warehouses, title, showRevenue = false) {
    if (!warehouses || warehouses.length === 0) {
        return `<div class="empty-data">Нет данных</div>`;
    }

    let rows = warehouses.map((wh, i) => `
        <tr>
            <td class="rank">${i + 1}</td>
            <td class="wh-name">${wh.name || 'Unknown'}</td>
            <td class="wh-qty">${formatNumber(wh.quantity || wh.count || 0)}${showRevenue ? '' : ' шт.'}</td>
            ${showRevenue ? `<td class="wh-revenue">${formatCurrency(wh.revenue || 0)}</td>` : ''}
        </tr>
    `).join('');

    return `
        <div class="breakdown-table">
            <h4>${title}</h4>
            <table>
                <thead>
                    <tr>
                        <th>#</th>
                        <th>Название</th>
                        <th>${showRevenue ? 'Заказов' : 'Кол-во'}</th>
                        ${showRevenue ? '<th>Выручка</th>' : ''}
                    </tr>
                </thead>
                <tbody>${rows}</tbody>
            </table>
        </div>
    `;
}

function createRegionTable(regions, title) {
    if (!regions || regions.length === 0) {
        return `<div class="empty-data">Нет данных</div>`;
    }

    let rows = regions.map((r, i) => `
        <tr>
            <td class="rank">${i + 1}</td>
            <td class="region-name">${r.name || 'Unknown'}</td>
            <td class="region-count">${formatNumber(r.count || 0)}</td>
            <td class="region-revenue">${formatCurrency(r.revenue || 0)}</td>
        </tr>
    `).join('');

    return `
        <div class="breakdown-table">
            <h4>${title}</h4>
            <table>
                <thead>
                    <tr>
                        <th>#</th>
                        <th>Регион</th>
                        <th>Заказов</th>
                        <th>Выручка</th>
                    </tr>
                </thead>
                <tbody>${rows}</tbody>
            </table>
        </div>
    `;
}


/**
 * Open refresh modal with instructions
 */
function refreshData() {
    const modal = document.getElementById('refreshModal');
    if (modal) {
        modal.classList.add('active');
    }
}

/**
 * Close refresh modal
 */
function closeRefreshModal() {
    const modal = document.getElementById('refreshModal');
    if (modal) {
        modal.classList.remove('active');
    }
}

/**
 * Copy command to clipboard
 */
function copyCommand() {
    const command = 'python Scripts/run_all.py';
    navigator.clipboard.writeText(command).then(() => {
        const btn = document.querySelector('.copy-btn');
        if (btn) {
            btn.textContent = '✓';
            btn.classList.add('copied');
            setTimeout(() => {
                btn.textContent = '📋';
                btn.classList.remove('copied');
            }, 2000);
        }
    }).catch(err => {
        console.error('Failed to copy:', err);
    });
}

/**
 * Reload data and close modal
 */
function reloadDataAndClose() {
    closeRefreshModal();

    // Add loading animation to refresh button
    const refreshBtn = document.querySelector('.refresh-btn');
    if (refreshBtn) {
        refreshBtn.classList.add('loading');
    }

    // Reload data
    fetchDashboardData().finally(() => {
        // Remove loading animation
        if (refreshBtn) {
            refreshBtn.classList.remove('loading');
        }
    });
}

// Close modal on background click
document.addEventListener('click', (e) => {
    const modal = document.getElementById('refreshModal');
    if (e.target === modal) {
        closeRefreshModal();
    }
});

// Close modal on Escape key
document.addEventListener('keydown', (e) => {
    if (e.key === 'Escape') {
        closeRefreshModal();
    }
});

// Initial fetch
document.addEventListener('DOMContentLoaded', () => {
    fetchDashboardData();
});

// Refresh every 5 minutes
setInterval(() => {
    if (!isLoading) {
        fetchDashboardData();
    }
}, 300000);


// ===== STOCK MONITORING FUNCTIONS =====

let monitoringData = [];
let monitoringSortColumn = 'daysLeft';
let monitoringSortAsc = true;

/**
 * Update stock monitoring section
 */
function updateStockMonitoring() {
    if (!dashboardData) return;

    const statusFilter = document.getElementById('monitoringStatusFilter')?.value || 'all';

    // Build monitoring data from stocks and period data
    monitoringData = buildMonitoringData();

    // Filter out single-item warehouses with no sales (likely returns)
    monitoringData = monitoringData.filter(item => {
        // Keep if stock > 1 OR has 7d sales
        return item.stock > 1 || item.orders7d > 0;
    });

    // Filter by current marketplace (from tabs)
    let filtered = monitoringData.filter(item => item.mp === currentMarketplace);

    // Apply status filter
    if (statusFilter !== 'all') {
        filtered = filtered.filter(item => item.statusKey === statusFilter);
    }

    // Sort
    filtered.sort((a, b) => {
        let valA = a[monitoringSortColumn];
        let valB = b[monitoringSortColumn];
        if (typeof valA === 'string') valA = valA.toLowerCase();
        if (typeof valB === 'string') valB = valB.toLowerCase();
        if (valA < valB) return monitoringSortAsc ? -1 : 1;
        if (valA > valB) return monitoringSortAsc ? 1 : -1;
        return 0;
    });

    // Create smart alerts: 5 cards for specific products on high-turnover warehouses
    createSmartAlerts(monitoringData);

    // Create table
    createMonitoringTableClustered(filtered);
}

/**
 * Build monitoring data from dashboard data
 * Now calculates consumption per warehouse using by_warehouse data from sales
 */
function buildMonitoringData() {
    const result = [];

    // Helper: get orders for specific product+warehouse combo
    function getWarehouseOrders(productList, article, warehouseName) {
        const product = productList.find(p => p.article === article);
        if (!product || !product.by_warehouse) return 0;

        // Normalize warehouse name for comparison
        const normalizedWarehouse = warehouseName.toLowerCase().replace(/[_\s]/g, '');
        const warehouseData = product.by_warehouse.find(w => {
            const normalizedName = w.name.toLowerCase().replace(/[_\s]/g, '');
            return normalizedName.includes(normalizedWarehouse) || normalizedWarehouse.includes(normalizedName);
        });
        return warehouseData ? warehouseData.count : 0;
    }

    // Process WB data
    const wbChartData = dashboardData.stocks?.wb?.chart_data || {};
    const wbWarehouses = wbChartData.labels || [];
    const wbDatasets = wbChartData.datasets || [];
    const wbPeriods = {
        today: dashboardData.period_data?.today?.wb?.sales_by_product || [],
        yesterday: dashboardData.period_data?.yesterday?.wb?.sales_by_product || [],
        days_3: dashboardData.period_data?.days_3?.wb?.sales_by_product || [],
        days_7: dashboardData.period_data?.days_7?.wb?.sales_by_product || [],
        days_30: dashboardData.period_data?.days_30?.wb?.sales_by_product || []
    };

    // Build WB per product per warehouse
    wbDatasets.forEach(dataset => {
        const article = dataset.label;
        dataset.data.forEach((qty, idx) => {
            if (qty <= 0) return;
            const warehouse = wbWarehouses[idx] || 'Unknown';

            // Get orders for this specific product+warehouse
            const ordersToday = getWarehouseOrders(wbPeriods.today, article, warehouse);
            const ordersYesterday = getWarehouseOrders(wbPeriods.yesterday, article, warehouse);
            const orders3d = getWarehouseOrders(wbPeriods.days_3, article, warehouse);
            const orders7d = getWarehouseOrders(wbPeriods.days_7, article, warehouse);
            const orders30d = getWarehouseOrders(wbPeriods.days_30, article, warehouse);

            // Calculate averages EXCLUDING today (today is incomplete)
            // days_3 includes today, so we subtract today: (orders3d - ordersToday) / 2 days
            // days_7 includes today, so we subtract today: (orders7d - ordersToday) / 6 days
            // days_30 includes today, so we subtract today: (orders30d - ordersToday) / 29 days
            const orders3dNoToday = Math.max(0, orders3d - ordersToday);
            const orders7dNoToday = Math.max(0, orders7d - ordersToday);
            const orders30dNoToday = Math.max(0, orders30d - ordersToday);

            const avg3d = orders3dNoToday > 0 ? (orders3dNoToday / 2) : 0;  // 2 full days (yesterday + day before)
            const avg7d = orders7dNoToday > 0 ? (orders7dNoToday / 6) : 0;  // 6 full days
            const avg30d = orders30dNoToday > 0 ? (orders30dNoToday / 29) : 0;  // 29 full days

            // Deviation 3d vs 7d (percentage)
            let deviation3d = null;
            if (avg7d > 0 && avg3d > 0) {
                deviation3d = Math.round((avg3d / avg7d) * 100);
            }

            // Deviation 30d vs 7d (percentage)
            let deviation30d = null;
            if (avg7d > 0 && avg30d > 0) {
                deviation30d = Math.round((avg30d / avg7d) * 100);
            }

            const daysLeft = avg7d > 0 ? Math.round(qty / avg7d) : 999;
            const status = getStockStatus(daysLeft);

            result.push({
                product: article,
                warehouse: warehouse,
                mp: 'wb',
                stock: qty,
                ordersToday,
                ordersYesterday,
                orders3d,
                orders7d,
                orders30d,
                avg7d: Math.round(avg7d * 10) / 10,
                avg3d: Math.round(avg3d * 10) / 10,
                avg30d: Math.round(avg30d * 10) / 10,
                deviation3d,
                deviation30d,
                daysLeft,
                statusKey: status.key,
                statusLabel: status.label
            });
        });
    });

    // Process Ozon data
    const ozonChartData = dashboardData.stocks?.ozon?.chart_data || {};
    const ozonWarehouses = ozonChartData.labels || [];
    const ozonDatasets = ozonChartData.datasets || [];
    const ozonPeriods = {
        today: dashboardData.period_data?.today?.ozon?.sales_by_product || [],
        yesterday: dashboardData.period_data?.yesterday?.ozon?.sales_by_product || [],
        days_3: dashboardData.period_data?.days_3?.ozon?.sales_by_product || [],
        days_7: dashboardData.period_data?.days_7?.ozon?.sales_by_product || [],
        days_30: dashboardData.period_data?.days_30?.ozon?.sales_by_product || []
    };

    ozonDatasets.forEach(dataset => {
        const article = dataset.label;
        dataset.data.forEach((qty, idx) => {
            if (qty <= 0) return;
            const warehouse = ozonWarehouses[idx] || 'Unknown';

            const ordersToday = getWarehouseOrders(ozonPeriods.today, article, warehouse);
            const ordersYesterday = getWarehouseOrders(ozonPeriods.yesterday, article, warehouse);
            const orders3d = getWarehouseOrders(ozonPeriods.days_3, article, warehouse);
            const orders7d = getWarehouseOrders(ozonPeriods.days_7, article, warehouse);
            const orders30d = getWarehouseOrders(ozonPeriods.days_30, article, warehouse);

            // Calculate averages EXCLUDING today (today is incomplete)
            const orders3dNoToday = Math.max(0, orders3d - ordersToday);
            const orders7dNoToday = Math.max(0, orders7d - ordersToday);
            const orders30dNoToday = Math.max(0, orders30d - ordersToday);

            const avg3d = orders3dNoToday > 0 ? (orders3dNoToday / 2) : 0;
            const avg7d = orders7dNoToday > 0 ? (orders7dNoToday / 6) : 0;
            const avg30d = orders30dNoToday > 0 ? (orders30dNoToday / 29) : 0;

            let deviation3d = null;
            if (avg7d > 0 && avg3d > 0) {
                deviation3d = Math.round((avg3d / avg7d) * 100);
            }

            let deviation30d = null;
            if (avg7d > 0 && avg30d > 0) {
                deviation30d = Math.round((avg30d / avg7d) * 100);
            }

            const daysLeft = avg7d > 0 ? Math.round(qty / avg7d) : 999;
            const status = getStockStatus(daysLeft);

            result.push({
                product: article,
                warehouse: warehouse,
                mp: 'ozon',
                stock: qty,
                ordersToday,
                ordersYesterday,
                orders3d,
                orders7d,
                orders30d,
                avg7d: Math.round(avg7d * 10) / 10,
                avg3d: Math.round(avg3d * 10) / 10,
                avg30d: Math.round(avg30d * 10) / 10,
                deviation3d,
                deviation30d,
                daysLeft,
                statusKey: status.key,
                statusLabel: status.label
            });
        });
    });

    // Sort by days left (critical first)
    result.sort((a, b) => a.daysLeft - b.daysLeft);

    return result;
}

function getProductOrders(productList, article) {
    const found = productList.find(p => p.article === article);
    return found ? found.count : 0;
}

function getStockStatus(daysLeft) {
    if (daysLeft < 14) return { key: 'critical', label: '🔴 Критично' };
    if (daysLeft < 21) return { key: 'warning', label: '🟠 Внимание' };
    return { key: 'normal', label: '🟢 Норма' };
}
/**
 * Create smart alert cards for 5 main products
 * Shows products that are running low in entire CLUSTERS (regions)
 * Only alerts if the product is scarce across ALL warehouses in a cluster
 */
function createSmartAlerts(allItems) {
    const container = document.getElementById('monitoringAlerts');
    if (!container) return;

    const targetProducts = ['SF0125', 'SF0250', 'SF0500', 'SM0250', 'SM0500'];

    // Filter by current marketplace
    const mpItems = allItems.filter(item => item.mp === currentMarketplace);

    // Group items by cluster and product
    const clusterProductStock = {};  // cluster -> product -> total stock in cluster
    const clusterProductDaysLeft = {};  // cluster -> product -> min days left

    for (const item of mpItems) {
        const cluster = getWarehouseCluster(item.warehouse, currentMarketplace);
        if (!clusterProductStock[cluster]) {
            clusterProductStock[cluster] = {};
            clusterProductDaysLeft[cluster] = {};
        }

        const product = item.product;
        if (!clusterProductStock[cluster][product]) {
            clusterProductStock[cluster][product] = 0;
            clusterProductDaysLeft[cluster][product] = 999;
        }

        clusterProductStock[cluster][product] += item.stock;
        clusterProductDaysLeft[cluster][product] = Math.min(
            clusterProductDaysLeft[cluster][product],
            item.daysLeft
        );
    }

    // Find clusters where target products are running low (cluster-wide)
    const alerts = [];

    for (const product of targetProducts) {
        for (const cluster of Object.keys(clusterProductStock)) {
            const totalStock = clusterProductStock[cluster][product] || 0;
            const minDaysLeft = clusterProductDaysLeft[cluster][product] || 999;

            // Alert if cluster-wide stock is critical (less than 14 days across entire cluster)
            if (minDaysLeft < 14 && totalStock > 0) {
                alerts.push({
                    product,
                    cluster,
                    totalStock,
                    daysLeft: minDaysLeft,
                    statusKey: minDaysLeft < 7 ? 'critical' : 'warning'
                });
            }
        }
    }

    // Sort by days left (most critical first), limit to 5
    alerts.sort((a, b) => a.daysLeft - b.daysLeft);
    const topAlerts = alerts.slice(0, 5);

    if (topAlerts.length === 0) {
        container.innerHTML = '<div class="no-alerts">✅ Критичных позиций нет</div>';
        return;
    }

    container.innerHTML = topAlerts.map(item => `
        <div class="alert-card ${item.statusKey}">
            <div class="alert-card-header">
                <span class="alert-card-title">${item.product}</span>
                <span class="alert-card-mp">${currentMarketplace === 'wb' ? 'WB' : 'Ozon'}</span>
            </div>
            <div class="alert-card-warehouse">🌍 ${item.cluster}</div>
            <div class="alert-card-stats">
                <span>В регионе: ${item.totalStock} шт</span>
                <span class="alert-days-left">${item.daysLeft} дн</span>
            </div>
            <div class="alert-card-action">
                <span class="alert-recommendation">➔ Пополнить регион</span>
            </div>
        </div>
    `).join('');
}

/**
 * Create alert cards for critical items (old version, kept for reference)
 */
function createMonitoringAlerts(items) {
    const container = document.getElementById('monitoringAlerts');
    if (!container) return;

    if (items.length === 0) {
        container.innerHTML = '';
        return;
    }

    container.innerHTML = items.map(item => `
        <div class="alert-card ${item.statusKey}">
            <div class="alert-card-header">
                <span class="alert-card-title">${item.product}</span>
                <span class="alert-card-mp">${item.mp === 'wb' ? 'WB' : 'Ozon'}</span>
            </div>
            <div class="alert-card-warehouse">${item.warehouse}</div>
            <div class="alert-card-stats">
                <span>Остаток: ${item.stock} шт</span>
                <span class="alert-days-left">${item.daysLeft} дней</span>
            </div>
        </div>
    `).join('');
}

/**
 * Create monitoring table with grouping by warehouse
 */
function createMonitoringTable(items) {
    const tbody = document.getElementById('monitoringTableBody');
    if (!tbody) return;

    if (items.length === 0) {
        tbody.innerHTML = '<tr><td colspan="10" class="monitoring-empty">Нет данных для отображения</td></tr>';
        return;
    }

    // Group items by warehouse
    const grouped = {};
    items.forEach(item => {
        if (!grouped[item.warehouse]) {
            grouped[item.warehouse] = {
                name: item.warehouse,
                items: [],
                totalStock: 0,
                minDaysLeft: 999,
                worstStatus: 'normal'
            };
        }
        grouped[item.warehouse].items.push(item);
        grouped[item.warehouse].totalStock += item.stock;
        if (item.daysLeft < grouped[item.warehouse].minDaysLeft) {
            grouped[item.warehouse].minDaysLeft = item.daysLeft;
        }
        // Update worst status
        if (item.statusKey === 'critical') {
            grouped[item.warehouse].worstStatus = 'critical';
        } else if (item.statusKey === 'warning' && grouped[item.warehouse].worstStatus !== 'critical') {
            grouped[item.warehouse].worstStatus = 'warning';
        }
    });

    // Sort warehouses by worst status (critical first)
    const sortedWarehouses = Object.values(grouped).sort((a, b) => {
        const order = { critical: 0, warning: 1, normal: 2 };
        return order[a.worstStatus] - order[b.worstStatus] || a.minDaysLeft - b.minDaysLeft;
    });

    let html = '';
    sortedWarehouses.forEach(wh => {
        // Warehouse header row
        const statusClass = wh.worstStatus;
        html += `
        <tr class="warehouse-group-header ${statusClass}" onclick="toggleWarehouseGroup(this)">
            <td colspan="10">
                <div class="warehouse-group-title">
                    <span class="warehouse-toggle">▼</span>
                    <strong>📦 ${wh.name}</strong>
                    <span class="warehouse-summary">${wh.items.length} товаров | ${wh.totalStock} шт | min: ${wh.minDaysLeft === 999 ? '∞' : wh.minDaysLeft} дней</span>
                </div>
            </td>
        </tr>`;

        // Product rows under warehouse
        wh.items.forEach(item => {
            const progressWidth = Math.min(100, Math.max(5, (item.daysLeft / 30) * 100));
            html += `
            <tr class="warehouse-product-row ${item.statusKey}">
                <td style="padding-left: 30px;"><strong>${item.product}</strong></td>
                <td>${item.stock} шт</td>
                <td>${item.ordersToday}</td>
                <td>${item.ordersYesterday}</td>
                <td>${item.orders3d}</td>
                <td>${item.orders7d}</td>
                <td>${item.avgDaily} шт/день</td>
                <td>
                    <div class="days-left-cell">
                        <span>${item.daysLeft === 999 ? '∞' : item.daysLeft}</span>
                        <div class="days-progress">
                            <div class="days-progress-bar ${item.statusKey}" style="width: ${progressWidth}%"></div>
                        </div>
                    </div>
                </td>
                <td><span class="status-badge ${item.statusKey}">${item.statusLabel}</span></td>
            </tr>`;
        });
    });

    tbody.innerHTML = html;
}

/**
 * Toggle warehouse group visibility
 */
function toggleWarehouseGroup(headerRow) {
    const toggle = headerRow.querySelector('.warehouse-toggle');
    let nextRow = headerRow.nextElementSibling;

    const isCollapsed = toggle.textContent === '▶';
    toggle.textContent = isCollapsed ? '▼' : '▶';

    while (nextRow && nextRow.classList.contains('warehouse-product-row')) {
        nextRow.style.display = isCollapsed ? '' : 'none';
        nextRow = nextRow.nextElementSibling;
    }
}

/**
 * Sort monitoring table
 */
function sortMonitoringTable(column) {
    if (monitoringSortColumn === column) {
        monitoringSortAsc = !monitoringSortAsc;
    } else {
        monitoringSortColumn = column;
        monitoringSortAsc = true;
    }
    updateStockMonitoring();
}

/**
 * WB warehouse to cluster mapping (based on official WB documentation)
 */
const WB_CLUSTERS = {
    'Центральный': [
        'пушкино', 'вёшки', 'вешки', 'иваново', 'подольск', 'радумля', 'обухово', 'чашниково',
        'воронеж', 'истра', 'коледино', 'домодедово', 'никольское', 'тверь', 'голицыно',
        'софьино', 'ярославль', 'цифровой', 'рязань', 'тюшевское', 'сабурово', 'владимир',
        'тула', 'котовск', 'электросталь', 'белая дача', 'щербинка', 'чехов'
    ],
    'Северо-Западный': [
        'вологда', 'шушары', 'красный бор', 'санкт-петербург', 'спб', 'уткина'
    ],
    'Приволжский': [
        'ижевск', 'кузнецк', 'пенза', 'самара', 'новосемейкино', 'сарапул', 'казань'
    ],
    'Уральский': [
        'нижний тагил', 'челябинск', 'екатеринбург'
    ],
    'Южный + Северо-Кавказский': [
        'крыловская', 'краснодар', 'волгоград', 'невинномысск', 'тихорецкая'
    ],
    'Дальневосточный + Сибирский': [
        'хабаровск', 'барнаул', 'владивосток', 'юрга', 'новосибирск'
    ],
    'Казахстан': [
        'байсерке', 'атакент', 'актобе', 'астана'
    ],
    'Беларусь': [
        'минск', 'брест', 'гродно'
    ],
    'Узбекистан': [
        'ташкент'
    ],
    'Армения': [
        'ереван'
    ],
    'Грузия': [
        'тбилиси'
    ]
};

/**
 * Ozon warehouse to cluster mapping (based on official Ozon documentation)
 */
const OZON_CLUSTERS = {
    'Москва, МО и Дальние регионы': [
        'хоругвино', 'ногинск', 'пушкино', 'софьино', 'радумля', 'павло', 'слободское',
        'петровское', 'жуковский', 'домодедово', 'гривно'
    ],
    'Санкт-Петербург и СЗО': [
        'колпино', 'шушары', 'волхонка', 'санкт-петербург', 'спб', 'бугры'
    ],
    'Казань': [
        'казань', 'кзн', 'столбище', 'нижний новгород'
    ],
    'Самара': [
        'самара'
    ],
    'Уфа': [
        'уфа'
    ],
    'Оренбург': [
        'оренбург'
    ],
    'Краснодар': [
        'адыгейск', 'южный обход', 'новороссийск'
    ],
    'Ростов': [
        'ростов'
    ],
    'Воронеж': [
        'воронеж'
    ],
    'Саратов': [
        'волгоград', 'саратов'
    ],
    'Невинномысск': [
        'невинномысск'
    ],
    'Махачкала': [
        'махачкала'
    ],
    'Красноярск': [
        'красноярск'
    ],
    'Новосибирск': [
        'новосибирск'
    ],
    'Омск': [
        'омск'
    ],
    'Екатеринбург': [
        'екатеринбург'
    ],
    'Пермь': [
        'пермь'
    ],
    'Тюмень': [
        'тюмень'
    ],
    'Дальний Восток': [
        'хабаровск'
    ],
    'Тверь': [
        'тверь'
    ],
    'Ярославль': [
        'ярославль'
    ],
    'Калининград': [
        'калининград'
    ],
    'Беларусь': [
        'минск'
    ],
    'Астана': [
        'астана'
    ],
    'Алматы': [
        'алматы'
    ],
    'Армения': [
        'ереван'
    ]
};

/**
 * Get cluster name for a warehouse
 * Returns 'Прочие' only for warehouses containing 'СЦ' in name
 * Returns 'Нераспознанные' for other unmatched warehouses
 */
function getWarehouseCluster(warehouseName, mpType) {
    const name = warehouseName.toLowerCase();
    const clusters = mpType === 'wb' ? WB_CLUSTERS : OZON_CLUSTERS;

    for (const [clusterName, keywords] of Object.entries(clusters)) {
        for (const keyword of keywords) {
            if (name.includes(keyword)) {
                return clusterName;
            }
        }
    }

    // Check if it's a sorting center (СЦ)
    if (name.includes('сц') || warehouseName.includes('СЦ')) {
        return 'Прочие';
    }

    return 'Нераспознанные';
}

/**
 * Create monitoring table with Cluster -> Warehouse -> Product grouping
 */
function createMonitoringTableClustered(items) {
    const tbody = document.getElementById('monitoringTableBody');
    if (!tbody) return;

    if (items.length === 0) {
        tbody.innerHTML = '<tr><td colspan="10" class="monitoring-empty">Нет данных для отображения</td></tr>';
        return;
    }

    // Assign cluster to each item
    items.forEach(item => {
        item.cluster = getWarehouseCluster(item.warehouse, item.mp);
    });

    // Target products for summary
    const mainProducts = ['SF0125', 'SF0250', 'SF0500', 'SM0250', 'SM0500'];

    // Group by Cluster -> Warehouse
    const clusters = {};
    items.forEach(item => {
        if (!clusters[item.cluster]) {
            clusters[item.cluster] = {
                name: item.cluster,
                warehouses: {},
                totalStock: 0,
                minDaysLeft: 999,
                worstStatus: 'normal',
                productStock: {}  // product -> total stock in cluster
            };
            // Initialize product stocks
            mainProducts.forEach(p => clusters[item.cluster].productStock[p] = 0);
        }

        if (!clusters[item.cluster].warehouses[item.warehouse]) {
            clusters[item.cluster].warehouses[item.warehouse] = {
                name: item.warehouse,
                items: [],
                totalStock: 0,
                minDaysLeft: 999
            };
        }

        clusters[item.cluster].warehouses[item.warehouse].items.push(item);
        clusters[item.cluster].warehouses[item.warehouse].totalStock += item.stock;
        clusters[item.cluster].totalStock += item.stock;

        // Track product stock in cluster
        if (mainProducts.includes(item.product)) {
            clusters[item.cluster].productStock[item.product] += item.stock;
        }

        if (item.daysLeft < clusters[item.cluster].minDaysLeft) {
            clusters[item.cluster].minDaysLeft = item.daysLeft;
        }
        if (item.daysLeft < clusters[item.cluster].warehouses[item.warehouse].minDaysLeft) {
            clusters[item.cluster].warehouses[item.warehouse].minDaysLeft = item.daysLeft;
        }

        if (item.statusKey === 'critical') {
            clusters[item.cluster].worstStatus = 'critical';
        } else if (item.statusKey === 'warning' && clusters[item.cluster].worstStatus !== 'critical') {
            clusters[item.cluster].worstStatus = 'warning';
        }
    });

    // Sort clusters by worst status
    const sortedClusters = Object.values(clusters).sort((a, b) => {
        const order = { critical: 0, warning: 1, normal: 2 };
        return order[a.worstStatus] - order[b.worstStatus] || a.name.localeCompare(b.name);
    });

    let html = '';

    sortedClusters.forEach(cluster => {
        // Build product summary string
        const productSummary = mainProducts
            .filter(p => cluster.productStock[p] > 0)
            .map(p => `${p}: ${cluster.productStock[p]}`)
            .join(' | ');

        // Cluster header
        html += `
        <tr class="cluster-header-row" onclick="toggleClusterGroup(this)">
            <td colspan="10">
                <div class="cluster-group-title">
                    <span class="cluster-toggle">▼</span>
                    <span class="cluster-icon">🌍</span>
                    <strong>${cluster.name}</strong>
                    <span class="cluster-summary">${Object.keys(cluster.warehouses).length} складов · ${cluster.totalStock} шт</span>
                    <span class="cluster-products">${productSummary}</span>
                    <span class="status-badge ${cluster.worstStatus}">
                        ${cluster.worstStatus === 'critical' ? 'Критично' : cluster.worstStatus === 'warning' ? 'Внимание' : 'Норма'}
                    </span>
                </div>
            </td>
        </tr>`;

        // Warehouses in cluster
        const sortedWarehouses = Object.values(cluster.warehouses).sort((a, b) => a.minDaysLeft - b.minDaysLeft);

        sortedWarehouses.forEach(wh => {
            html += `
            <tr class="warehouse-group-header cluster-child" onclick="toggleWarehouseGroup(this)">
                <td colspan="10">
                    <div class="warehouse-group-title">
                        <span class="warehouse-toggle">▼</span>
                        <strong>📦 ${wh.name}</strong>
                        <span class="warehouse-summary">${wh.items.length} товаров · ${wh.totalStock} шт</span>
                    </div>
                </td>
            </tr>`;

            // Products
            wh.items.forEach(item => {
                const progressWidth = Math.min(100, Math.max(5, (item.daysLeft / 30) * 100));

                // Format consumption value with deviation below
                const formatConsumption = (avg, dev) => {
                    if (avg === 0 || avg === undefined) return '<span class="cons-na">—</span>';

                    let devHtml = '';
                    if (dev !== null && dev !== undefined) {
                        const arrow = dev > 100 ? '▲' : dev < 100 ? '▼' : '•';
                        const colorClass = dev > 120 ? 'dev-up' : dev < 80 ? 'dev-down' : 'dev-stable';
                        devHtml = `<div class="cons-dev ${colorClass}">${arrow}${dev}%</div>`;
                    }

                    return `<div class="cons-value">${avg}</div>${devHtml}`;
                };

                html += `
                <tr class="warehouse-product-row cluster-child ${item.statusKey}">
                    <td style="padding-left: 50px;"><strong>${item.product}</strong></td>
                    <td>${item.stock} шт</td>
                    <td>${item.ordersToday}</td>
                    <td>${item.ordersYesterday}</td>
                    <td>${item.orders3d}</td>
                    <td>${item.orders7d}</td>
                    <td class="consumption-cell">
                        <div class="consumption-display-new">
                            <div class="cons-column">
                                ${formatConsumption(item.avg30d, item.deviation30d)}
                            </div>
                            <div class="cons-column cons-main">
                                <div class="cons-value-main">${item.avg7d}</div>
                                <div class="cons-label">шт/д</div>
                            </div>
                            <div class="cons-column">
                                ${formatConsumption(item.avg3d, item.deviation3d)}
                            </div>
                        </div>
                    </td>
                    <td>
                        <div class="days-left-cell">
                            <span>${item.daysLeft === 999 ? '∞' : item.daysLeft}</span>
                            <div class="days-progress">
                                <div class="days-progress-bar ${item.statusKey}" style="width: ${progressWidth}%"></div>
                            </div>
                        </div>
                    </td>
                    <td><span class="status-badge ${item.statusKey}">${item.statusLabel}</span></td>
                </tr>`;
            });
        });
    });

    tbody.innerHTML = html;
}

/**
 * Toggle cluster group visibility
 */
function toggleClusterGroup(headerRow) {
    const toggle = headerRow.querySelector('.cluster-toggle');
    let nextRow = headerRow.nextElementSibling;

    const isCollapsed = toggle.textContent === '▶';
    toggle.textContent = isCollapsed ? '▼' : '▶';

    while (nextRow && nextRow.classList.contains('cluster-child')) {
        nextRow.style.display = isCollapsed ? '' : 'none';
        nextRow = nextRow.nextElementSibling;
    }
}

// ===== STOCK MATRIX (Регионы) =====

/**
 * Build stock matrix: rows = clusters + warehouses, columns = articles
 * Shows quantity at intersection (0 = empty, number = in stock)
 */
function buildStockMatrix(mpKey) {
    const stocksData = dashboardData?.stocks?.[mpKey] || {};
    const chartData = stocksData.chart_data;
    const allArticles = stocksData.all_articles || [];

    if (!chartData || !chartData.labels || chartData.labels.length === 0) {
        return `<div class="stock-matrix-empty">
            <div class="matrix-empty-icon">📦</div>
            <div class="matrix-empty-text">Нет данных об остатках по складам</div>
        </div>`;
    }

    const warehouses = chartData.labels || [];
    const datasets = chartData.datasets || [];
    const articles = allArticles.length > 0 ? allArticles : datasets.map(d => d.label);

    // Build lookup: warehouse -> article -> qty
    const stockLookup = {}; // warehouseName -> { article: qty }
    warehouses.forEach((wh, idx) => {
        stockLookup[wh] = {};
        datasets.forEach(ds => {
            stockLookup[wh][ds.label] = ds.data[idx] || 0;
        });
    });

    // Group warehouses by cluster
    const clustersMap = {};
    const clusterOrder = [];

    warehouses.forEach(wh => {
        const clusterName = getWarehouseCluster(wh, mpKey);
        if (!clustersMap[clusterName]) {
            clustersMap[clusterName] = { name: clusterName, warehouses: [], totalStock: 0 };
            clusterOrder.push(clusterName);
        }
        const whTotal = Object.values(stockLookup[wh]).reduce((s, v) => s + v, 0);
        clustersMap[clusterName].warehouses.push({ name: wh, total: whTotal });
        clustersMap[clusterName].totalStock += whTotal;
    });

    // Sort clusters by total stock desc
    clusterOrder.sort((a, b) => clustersMap[b].totalStock - clustersMap[a].totalStock);

    // Build article totals per cluster
    const clusterArticleTotals = {};
    clusterOrder.forEach(clusterName => {
        clusterArticleTotals[clusterName] = {};
        articles.forEach(art => {
            clusterArticleTotals[clusterName][art] = 0;
        });
        clustersMap[clusterName].warehouses.forEach(wh => {
            articles.forEach(art => {
                clusterArticleTotals[clusterName][art] += stockLookup[wh.name][art] || 0;
            });
        });
    });

    // Find global max for heatmap scaling (per article column)
    const articleMax = {};
    articles.forEach(art => {
        let max = 0;
        warehouses.forEach(wh => { if ((stockLookup[wh][art] || 0) > max) max = stockLookup[wh][art] || 0; });
        articleMax[art] = max;
    });

    /**
     * Returns heatmap CSS class based on value and max
     */
    function heatClass(val, max) {
        if (val === 0 || val === null || val === undefined) return 'heat-zero';
        if (max === 0) return 'heat-low';
        const pct = val / max;
        if (pct >= 0.66) return 'heat-high';
        if (pct >= 0.33) return 'heat-mid';
        return 'heat-low';
    }

    // ---- Build HTML ----
    const colCount = articles.length;

    let headerCols = articles.map(art => `
        <th class="matrix-art-col" title="${art}">${art}</th>
    `).join('');

    let rows = '';

    clusterOrder.forEach((clusterName, ci) => {
        const cluster = clustersMap[clusterName];
        const clusterTotals = clusterArticleTotals[clusterName];
        const clusterId = `cluster-${ci}`;

        // Cluster summary row
        const clusterCells = articles.map(art => {
            const val = clusterTotals[art];
            const cls = val > 0 ? 'heat-cluster-has' : 'heat-cluster-zero';
            return `<td class="matrix-cell cluster-total-cell ${cls}">
                ${val > 0 ? `<span class="matrix-qty">${formatNumber(val)}</span>` : '<span class="matrix-dash">—</span>'}
            </td>`;
        }).join('');

        rows += `
        <tr class="matrix-cluster-row" onclick="toggleMatrixCluster('${clusterId}')">
            <td class="matrix-row-label cluster-label">
                <span class="matrix-toggle" id="toggle-${clusterId}">▼</span>
                <span class="matrix-cluster-icon">🌍</span>
                <span class="matrix-cluster-name">${clusterName}</span>
                <span class="matrix-cluster-count">${cluster.warehouses.length} скл</span>
            </td>
            <td class="matrix-cell cluster-row-total">
                <span class="matrix-qty cluster-qty">${formatNumber(cluster.totalStock)}</span>
            </td>
            ${clusterCells}
        </tr>`;

        // Warehouse rows within cluster
        cluster.warehouses
            .sort((a, b) => b.total - a.total)
            .forEach((wh, wi) => {
                const whCells = articles.map(art => {
                    const val = stockLookup[wh.name][art] || 0;
                    const cls = heatClass(val, articleMax[art]);
                    return `<td class="matrix-cell wh-cell ${cls}" title="${wh.name} · ${art}: ${val} шт">
                        ${val > 0
                            ? `<span class="matrix-qty">${formatNumber(val)}</span>`
                            : '<span class="matrix-zero">·</span>'
                        }
                    </td>`;
                }).join('');

                rows += `
        <tr class="matrix-wh-row cluster-matrix-child" data-cluster="${clusterId}">
            <td class="matrix-row-label wh-label">
                <span class="wh-indent">└</span>
                <span class="matrix-wh-name" title="${wh.name}">${wh.name.replace(/_/g, ' ')}</span>
            </td>
            <td class="matrix-cell wh-total-cell">
                <span class="matrix-qty">${formatNumber(wh.total)}</span>
                <span class="matrix-qty-unit">шт</span>
            </td>
            ${whCells}
        </tr>`;
            });
    });

    return `
    <div class="stock-matrix-wrapper">
        <div class="stock-matrix-header">
            <div class="matrix-title-block">
                <span class="matrix-title-icon">🗺️</span>
                <span>Матрица остатков по регионам</span>
            </div>
            <div class="matrix-legend">
                <span class="legend-dot heat-high"></span><span>Высокий</span>
                <span class="legend-dot heat-mid"></span><span>Средний</span>
                <span class="legend-dot heat-low"></span><span>Низкий</span>
                <span class="legend-dot heat-zero"></span><span>Нет</span>
            </div>
        </div>
        <div class="stock-matrix-scroll">
            <table class="stock-matrix-table">
                <thead>
                    <tr>
                        <th class="matrix-row-label matrix-header-label">Кластер / Склад</th>
                        <th class="matrix-total-col">Итого</th>
                        ${headerCols}
                    </tr>
                </thead>
                <tbody>
                    ${rows}
                </tbody>
            </table>
        </div>
    </div>
    `;
}

/**
 * Toggle warehouse rows within a cluster in the stock matrix
 */
function toggleMatrixCluster(clusterId) {
    const toggle = document.getElementById(`toggle-${clusterId}`);
    const rows = document.querySelectorAll(`.cluster-matrix-child[data-cluster="${clusterId}"]`);
    const isCollapsed = toggle && toggle.textContent === '▶';

    if (toggle) toggle.textContent = isCollapsed ? '▼' : '▶';
    rows.forEach(row => { row.style.display = isCollapsed ? '' : 'none'; });
}

