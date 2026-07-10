const chartData = {{ chart_data_json|safe }};
for (const [symbol, data] of Object.entries(chartData)) {
  const grid = document.getElementById('charts');
  const card = document.createElement('div');
  card.className = 'card';
  card.id = 'card-' + symbol;
  card.dataset.symbol = symbol;
  card.innerHTML = `<h2>${symbol} <span style="font-size:0.8rem; color:${data.bias_color}">&#9679; ${data.bias}</span></h2>` +
    `<div style="font-size:0.8rem; color:#999; margin-bottom:0.5rem">${data.bias_reason}<br>` +
    `ATR(14): ${data.atr} &middot; Support: ${data.support} &middot; Resistance: ${data.resistance}</div>` +
    `<canvas></canvas>`;
  grid.appendChild(card);
  const ctx = card.querySelector('canvas');
  new Chart(ctx, {
    type: 'line',
    data: {
      labels: data.dates,
      datasets: [
        { label: 'Close', data: data.close, borderColor: '#4ea1ff', yAxisID: 'y', tension: 0.1, pointRadius: 0 },
        { label: 'RSI', data: data.rsi, borderColor: '#ff9f4e', yAxisID: 'y1', tension: 0.1, pointRadius: 0 }
      ]
    },
    options: {
      scales: {
        y: { position: 'left' },
        y1: { position: 'right', min: 0, max: 100, grid: { drawOnChartArea: false } }
      }
    }
  });
}

function scrollToChart(symbol) {
  const card = document.getElementById('card-' + symbol);
  if (card) {
    card.scrollIntoView({ behavior: 'smooth', block: 'center' });
    card.style.outline = '2px solid #4ea1ff';
    setTimeout(() => card.style.outline = '', 1500);
  }
}

function applyFilters() {
  const symbolQuery = document.getElementById('symbolFilter').value.trim().toUpperCase();
  const category = document.getElementById('categoryFilter').value;

  document.querySelectorAll('#alertsTable tbody tr').forEach(row => {
    const rowSymbol = (row.dataset.symbol || '').toUpperCase();
    const rowCategory = row.dataset.category || '';
    const symbolMatch = !symbolQuery || rowSymbol.includes(symbolQuery);
    const categoryMatch = !category || rowCategory === category;
    row.classList.toggle('hidden-row', !(symbolMatch && categoryMatch));
  });

  document.querySelectorAll('#charts .card').forEach(card => {
    const cardSymbol = (card.dataset.symbol || '').toUpperCase();
    card.classList.toggle('hidden-card', !(!symbolQuery || cardSymbol.includes(symbolQuery)));
  });
}

// addEventListener statt inline onclick/onchange-Attribute: robuster, funktioniert auch wenn
// Browser/Erweiterungen/CSP-Regeln Inline-Event-Handler blockieren.
document.getElementById('symbolFilter').addEventListener('input', applyFilters);
document.getElementById('categoryFilter').addEventListener('change', applyFilters);
document.getElementById('resetFilters').addEventListener('click', () => {
  document.getElementById('symbolFilter').value = '';
  document.getElementById('categoryFilter').value = '';
  applyFilters();
});
document.getElementById('alertsTable').addEventListener('click', (event) => {
  const link = event.target.closest('.symlink');
  if (link) {
    const row = link.closest('tr');
    if (row) scrollToChart(row.dataset.symbol);
  }
});
