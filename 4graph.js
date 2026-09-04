/* Dashboard chart logic */

const salesData = {
    today: {
        labels: ['8am', '10am', '12pm', '2pm', '4pm', '6pm', '8pm', ''],
        data:   [100, 150, 400, 300, 500, 700, 850, null],
        max:    1000
    },
    week: {
        labels: ['Mon', 'Tue', 'Wed', 'Thu', 'Fri', 'Sat', 'Sun', ''],
        data:   [150, 230, 190, 310, 270, 490, 550, null],
        max:    850
    },
    month: {
        labels: ['Week 1', 'Week 2', 'Week 3', 'Week 4', ''],
        data:   [1200, 2100, 1800, 2600, null],
        max:    3000
    }
};

let myChart = null;

/* dotted-projection line plugin */
const dottedLinePlugin = {
    id: 'dottedLine',
    afterDraw: (chart) => {
        const { ctx } = chart;
        const meta = chart.getDatasetMeta(0);
        const lastIdx = chart.data.datasets[0].data.length - 2;
        const lastPoint = meta.data[lastIdx];
        if (lastPoint) {
            ctx.save();
            ctx.beginPath();
            ctx.setLineDash([5, 5]);
            ctx.moveTo(lastPoint.x, lastPoint.y);
            ctx.lineTo(chart.width, lastPoint.y);
            ctx.strokeStyle = '#4e8bff';
            ctx.stroke();
            ctx.restore();
        }
    }
};

document.addEventListener('DOMContentLoaded', () => {
    const canvas = document.getElementById('salesChart');
    if (!canvas) return;

    const ctx = canvas.getContext('2d');
    const gradient = ctx.createLinearGradient(0, 0, 0, 300);
    gradient.addColorStop(0, 'rgba(78, 139, 255, 0.30)');
    gradient.addColorStop(1, 'rgba(78, 139, 255, 0)');

    myChart = new Chart(ctx, {
        type: 'line',
        data: {
            labels: salesData.week.labels,
            datasets: [{
                data: salesData.week.data,
                borderColor: '#2563eb',
                backgroundColor: gradient,
                fill: true,
                tension: 0.4,
                pointRadius: c => (c.dataIndex === c.dataset.data.length - 2 ? 6 : 0),
                pointBackgroundColor: '#fff',
                pointBorderColor: '#2563eb',
                pointBorderWidth: 3,
                borderWidth: 3
            }]
        },
        options: {
            responsive: true,
            maintainAspectRatio: false,
            plugins: { legend: { display: false } },
            scales: {
                y: {
                    beginAtZero: true, max: 850,
                    grid: { color: '#f0f0f0' },
                    ticks: { callback: v => 'Rs ' + v, color: '#94a3b8' }
                },
                x: {
                    grid: { display: false },
                    ticks: { color: '#94a3b8' }
                }
            }
        },
        plugins: [dottedLinePlugin]
    });
});

function updateChart(period, element) {
    if (!myChart || !salesData[period]) return;
    myChart.data.labels = salesData[period].labels;
    myChart.data.datasets[0].data = salesData[period].data;
    myChart.options.scales.y.max = salesData[period].max;
    myChart.update();

    document.querySelectorAll('.tab-item').forEach(b => b.classList.remove('active'));
    element.classList.add('active');
}
