/**
 * StyleSphere Admin Real-Time Analytics & Live Login Monitoring
 */

let salesChartInstance = null;
let categoryChartInstance = null;
let topProductsChartInstance = null;
let orderStatusChartInstance = null;
let loginActChartInstance = null;
let registrationChartInstance = null;

document.addEventListener('DOMContentLoaded', function () {
    initCharts(30);
    initRealtimeUpdates();

    // Date range filter buttons
    document.querySelectorAll('.btn-date-range').forEach(btn => {
        btn.addEventListener('click', function () {
            document.querySelectorAll('.btn-date-range').forEach(b => b.classList.remove('active', 'btn-dark'));
            document.querySelectorAll('.btn-date-range').forEach(b => b.classList.add('btn-outline-secondary'));
            this.classList.remove('btn-outline-secondary');
            this.classList.add('active', 'btn-dark');

            const days = parseInt(this.dataset.days);
            loadChartData(days);
        });
    });
});

function initCharts(days) {
    loadChartData(days);
}

function loadChartData(days) {
    fetch(`/admin/api/charts?days=${days}`)
        .then(res => res.json())
        .then(data => {
            renderSalesChart(data.sales);
            renderCategoryChart(data.category_revenue);
            renderTopProductsChart(data.top_products);
            renderOrderStatusChart(data.order_status);
            renderLoginActChart(data.login_activity);
            renderRegistrationChart(data.registrations);
        })
        .catch(err => console.error('Failed to load chart analytics:', err));
}

function renderSalesChart(sales) {
    const ctx = document.getElementById('salesChart');
    if (!ctx) return;

    if (salesChartInstance) salesChartInstance.destroy();

    salesChartInstance = new Chart(ctx, {
        type: 'line',
        data: {
            labels: sales.labels,
            datasets: [
                {
                    label: 'Revenue (₹)',
                    data: sales.revenue,
                    borderColor: '#111827',
                    backgroundColor: 'rgba(17, 24, 39, 0.05)',
                    borderWidth: 2.5,
                    fill: true,
                    tension: 0.35,
                    yAxisID: 'y'
                },
                {
                    label: 'Orders',
                    data: sales.orders,
                    borderColor: '#3b82f6',
                    backgroundColor: 'transparent',
                    borderWidth: 2,
                    borderDash: [4, 4],
                    tension: 0.2,
                    yAxisID: 'y1'
                }
            ]
        },
        options: {
            responsive: true,
            maintainAspectRatio: false,
            interaction: { mode: 'index', intersect: false },
            scales: {
                y: {
                    type: 'linear',
                    display: true,
                    position: 'left',
                    ticks: {
                        callback: val => '₹' + val.toLocaleString()
                    }
                },
                y1: {
                    type: 'linear',
                    display: true,
                    position: 'right',
                    grid: { drawOnChartArea: false },
                    ticks: { precision: 0 }
                }
            }
        }
    });
}

function renderCategoryChart(cat) {
    const ctx = document.getElementById('categoryChart');
    if (!ctx) return;
    if (categoryChartInstance) categoryChartInstance.destroy();

    categoryChartInstance = new Chart(ctx, {
        type: 'doughnut',
        data: {
            labels: cat.labels,
            datasets: [{
                data: cat.revenue,
                backgroundColor: ['#111827', '#c5a880', '#64748b', '#cbd5e1', '#3b82f6']
            }]
        },
        options: {
            responsive: true,
            maintainAspectRatio: false,
            plugins: {
                legend: { position: 'bottom' }
            }
        }
    });
}

function renderTopProductsChart(top) {
    const ctx = document.getElementById('topProductsChart');
    if (!ctx) return;
    if (topProductsChartInstance) topProductsChartInstance.destroy();

    topProductsChartInstance = new Chart(ctx, {
        type: 'bar',
        data: {
            labels: top.labels,
            datasets: [{
                label: 'Units Sold',
                data: top.quantities,
                backgroundColor: '#1e293b',
                borderRadius: 4
            }]
        },
        options: {
            indexAxis: 'y',
            responsive: true,
            maintainAspectRatio: false,
            scales: {
                x: { ticks: { precision: 0 } }
            }
        }
    });
}

function renderOrderStatusChart(status) {
    const ctx = document.getElementById('orderStatusChart');
    if (!ctx) return;
    if (orderStatusChartInstance) orderStatusChartInstance.destroy();

    orderStatusChartInstance = new Chart(ctx, {
        type: 'pie',
        data: {
            labels: status.labels,
            datasets: [{
                data: status.counts,
                backgroundColor: ['#f59e0b', '#3b82f6', '#10b981', '#6366f1', '#ef4444', '#94a3b8']
            }]
        },
        options: {
            responsive: true,
            maintainAspectRatio: false,
            plugins: {
                legend: { position: 'bottom' }
            }
        }
    });
}

function renderLoginActChart(act) {
    const ctx = document.getElementById('loginActChart');
    if (!ctx) return;
    if (loginActChartInstance) loginActChartInstance.destroy();

    loginActChartInstance = new Chart(ctx, {
        type: 'bar',
        data: {
            labels: act.labels,
            datasets: [{
                label: 'Successful Logins',
                data: act.counts,
                backgroundColor: '#3b82f6',
                borderRadius: 4
            }]
        },
        options: {
            responsive: true,
            maintainAspectRatio: false,
            scales: {
                y: { ticks: { precision: 0 } }
            }
        }
    });
}

function renderRegistrationChart(reg) {
    const ctx = document.getElementById('registrationChart');
    if (!ctx) return;
    if (registrationChartInstance) registrationChartInstance.destroy();

    registrationChartInstance = new Chart(ctx, {
        type: 'line',
        data: {
            labels: reg.labels,
            datasets: [{
                label: 'New Customers',
                data: reg.counts,
                borderColor: '#10b981',
                backgroundColor: 'rgba(16, 185, 129, 0.1)',
                fill: true,
                tension: 0.3
            }]
        },
        options: {
            responsive: true,
            maintainAspectRatio: false,
            scales: {
                y: { ticks: { precision: 0 } }
            }
        }
    });
}

function updateKPIElements(kpis) {
    // 5 Distinct Customer Login Monitoring Metrics:
    setText('kpi-total-customers', kpis.total_customers);
    setText('kpi-total-logins', kpis.total_successful_logins);
    setText('kpi-logged-in-customers', kpis.currently_logged_in_customers);
    setText('kpi-recent-active', kpis.recent_active_customers_5m);
    setText('kpi-active-sessions', kpis.active_sessions_count);

    // Orders & Revenue
    setText('kpi-total-orders', kpis.total_orders);
    setText('kpi-orders-today', kpis.orders_today);
    setText('kpi-paid-orders', kpis.paid_orders);
    setText('kpi-pending-orders', kpis.pending_orders);
    setText('kpi-cancelled-orders', kpis.cancelled_orders);
    setText('kpi-total-revenue', '₹' + Number(kpis.total_revenue).toLocaleString(undefined, { minimumFractionDigits: 2 }));
    setText('kpi-revenue-today', '₹' + Number(kpis.revenue_today).toLocaleString(undefined, { minimumFractionDigits: 2 }));
    setText('kpi-available-products', kpis.available_products);
    setText('kpi-low-stock', kpis.low_stock_count);
    setText('kpi-out-of-stock', kpis.out_of_stock_count);

    const tsEl = document.getElementById('live-timestamp');
    if (tsEl && kpis.timestamp) {
        tsEl.textContent = kpis.timestamp;
    }
}

function setText(id, val) {
    const el = document.getElementById(id);
    if (el) el.textContent = val;
}

function initRealtimeUpdates() {
    // 1. Check for SocketIO client library
    if (typeof io !== 'undefined') {
        const socket = io();

        socket.on('connect', () => {
            console.log('Connected to StyleSphere Live Admin Socket.');
        });

        socket.on('customer_login', data => {
            console.log('Live customer login event:', data.user_display);
            if (data.metrics) updateKPIElements(data.metrics);
        });

        socket.on('new_order', data => {
            console.log('New order received:', data.order_number);
            if (data.kpis) updateKPIElements(data.kpis);
            // Refresh chart data
            const activeDaysBtn = document.querySelector('.btn-date-range.active');
            const days = activeDaysBtn ? parseInt(activeDaysBtn.dataset.days) : 30;
            loadChartData(days);
        });
    }

    // 2. Continuous fallback polling every 10 seconds for robustness
    setInterval(() => {
        fetch('/admin/api/kpis')
            .then(res => res.json())
            .then(kpis => updateKPIElements(kpis))
            .catch(() => {});
    }, 10000);
}
