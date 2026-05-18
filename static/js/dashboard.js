/* ====== Dashboard Module ====== */

class Dashboard {
    constructor() {
        this.data = {
            totalOrders: 0,
            totalSpent: 0,
            totalProducts: 0,
            recentOrders: [],
        };
        this.isInitialLoad = true;
        this.chart = null;
        this.init();
    }

    async init() {
        this.renderRecentOrdersSkeleton();
        await this.loadData();
        this.renderStats();
        this.initChart();
        setInterval(async () => {
            await this.loadData();
            this.renderStats();
            this.updateChart();
        }, 5000);
    }

    renderRecentOrdersSkeleton() {
        const recentOrdersEl = document.getElementById('recent-orders');
        if (!recentOrdersEl) return;

        recentOrdersEl.innerHTML = Array.from({ length: 4 }).map(() => `
            <tr>
                <td class="px-6 py-4"><div class="skeleton h-4 rounded-md"></div></td>
                <td class="px-6 py-4"><div class="skeleton h-4 rounded-md"></div></td>
                <td class="px-6 py-4"><div class="skeleton h-4 rounded-md"></div></td>
                <td class="px-6 py-4"><div class="skeleton h-4 rounded-md"></div></td>
                <td class="px-6 py-4"><div class="skeleton h-4 rounded-md"></div></td>
            </tr>
        `).join('');
    }

    async loadData() {
        try {
            const response = await fetch('/api/dashboard-stats', {
                cache: 'no-store',
                headers: {
                    'Cache-Control': 'no-cache',
                },
            });
            const payload = await response.json();
            this.data = {
                totalOrders: payload.totalOrders ?? payload.total_orders ?? 0,
                totalSpent: payload.totalSpent ?? payload.total_spent ?? 0,
                totalProducts: payload.totalProducts ?? payload.total_products ?? 0,
                recentOrders: payload.recentOrders ?? payload.recent_orders ?? [],
            };
        } catch (error) {
            console.error('Failed to load dashboard data:', error);
            toast.error('Failed to load dashboard data');
        }
    }

    renderStats() {
        const totalOrdersEl = document.getElementById('total-orders');
        const totalSpentEl = document.getElementById('total-spent');
        const totalProductsEl = document.getElementById('total-products');
        const recentOrdersEl = document.getElementById('recent-orders');

        if (totalOrdersEl) totalOrdersEl.textContent = this.data.totalOrders;
        if (totalSpentEl) totalSpentEl.textContent = formatCurrency(this.data.totalSpent);
        if (totalProductsEl) totalProductsEl.textContent = this.data.totalProducts;

        if (recentOrdersEl) {
            if (!this.data.recentOrders || this.data.recentOrders.length === 0) {
                recentOrdersEl.innerHTML = `
                    <tr>
                        <td colspan="5" class="px-6 py-8 text-center text-sm text-slate-500">
                            No purchases yet. Complete a checkout to see orders here.
                        </td>
                    </tr>
                `;
                return;
            }

            recentOrdersEl.innerHTML = this.data.recentOrders.map(order => {
                const status = String(order.status || 'pending').toLowerCase();
                const statusClass = ['paid', 'completed', 'success', 'succeeded'].includes(status)
                    ? 'ui-status-success'
                    : ['pending', 'processing', 'requires_payment_method'].includes(status)
                        ? 'ui-status-pending'
                        : 'ui-status-failed';
                return `
                <tr class="border-b border-slate-50 hover:bg-slate-50 transition">
                    <td class="px-6 py-4"><span class="font-mono text-sm text-slate-900">#${order.id}</span></td>
                    <td class="px-6 py-4 text-sm text-slate-600">${order.itemCount || 0} items</td>
                    <td class="px-6 py-4 font-semibold text-slate-900">${formatCurrency(order.total)}</td>
                    <td class="px-6 py-4">
                        <span class="ui-status-chip ${statusClass}">${status}</span>
                    </td>
                    <td class="px-6 py-4 text-sm text-slate-500">${formatDate(order.date)}</td>
                </tr>
            `;
            }).join('');
        }

        this.isInitialLoad = false;
    }

    initChart() {
        const ctx = document.getElementById('purchaseChart');
        if (!ctx) return;

        const chartData = this.generateChartData();
        this.chart = new Chart(ctx, {
            type: 'line',
            data: chartData,
            options: {
                responsive: true,
                maintainAspectRatio: false,
                plugins: {
                    legend: {
                        display: true,
                        labels: {
                            font: { weight: '600', size: 12 },
                            color: '#334155',
                            padding: 15,
                        }
                    },
                    tooltip: {
                        backgroundColor: '#1e293b',
                        titleColor: '#fff',
                        bodyColor: '#e2e8f0',
                        borderColor: '#475569',
                        borderWidth: 1,
                        padding: 12,
                        displayColors: true,
                        callbacks: {
                            label: function(context) {
                                return 'Amount: ₹' + context.parsed.y.toFixed(2);
                            }
                        }
                    }
                },
                scales: {
                    y: {
                        beginAtZero: true,
                        ticks: { color: '#64748b', font: { size: 11 } },
                        grid: { color: 'rgba(203, 213, 225, 0.1)' },
                        title: { display: true, text: 'Amount (₹)', color: '#475569' }
                    },
                    x: {
                        ticks: { color: '#64748b', font: { size: 11 } },
                        grid: { display: false }
                    }
                }
            }
        });
    }

    generateChartData() {
        const today = new Date();
        const days = [];
        const totalsByDay = new Map();
        for (let i = 6; i >= 0; i--) {
            const date = new Date(today);
            date.setDate(date.getDate() - i);
            const key = date.toISOString().slice(0, 10);
            totalsByDay.set(key, 0);
            days.push({
                key,
                label: date.toLocaleDateString('en-US', { month: 'short', day: 'numeric' }),
            });
        }

        (this.data.recentOrders || []).forEach((order) => {
            if (!order?.date) return;
            const dayKey = String(order.date).slice(0, 10);
            if (!totalsByDay.has(dayKey)) return;
            const current = totalsByDay.get(dayKey) || 0;
            totalsByDay.set(dayKey, current + Number(order.total || 0));
        });

        const purchaseData = days.map((d) => Number((totalsByDay.get(d.key) || 0).toFixed(2)));

        return {
            labels: days.map((d) => d.label),
            datasets: [
                {
                    label: 'Daily Purchase Amount (₹)',
                    data: purchaseData,
                    borderColor: '#3b82f6',
                    backgroundColor: 'rgba(59, 130, 246, 0.1)',
                    borderWidth: 3,
                    fill: true,
                    tension: 0.4,
                    pointRadius: 5,
                    pointBackgroundColor: '#3b82f6',
                    pointBorderColor: '#fff',
                    pointBorderWidth: 2,
                    pointHoverRadius: 7,
                }
            ]
        };
    }

    updateChart() {
        if (!this.chart) return;
        const newData = this.generateChartData();
        this.chart.data = newData;
        this.chart.update('none'); // Update without animation for smooth real-time updates
    }
}

// Initialize dashboard
document.addEventListener('DOMContentLoaded', () => {
    new Dashboard();
});
