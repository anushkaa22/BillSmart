document.addEventListener('DOMContentLoaded', () => {
  const reduceMotion = window.matchMedia('(prefers-reduced-motion: reduce)').matches;

  function themeVars() {
    const styles = getComputedStyle(document.documentElement);
    const get = (name, fallback) => styles.getPropertyValue(name).trim() || fallback;
    const isDark = document.documentElement.classList.contains('dark');
    return {
      isDark,
      link: get('--link', '#2456D6'),
      muted: get('--muted', '#5B6B7F'),
      surface: get('--surface', '#ffffff'),
      grid: get('--line', '#E6EAF0'),
    };
  }

  // Animated KPI counters (server-rendered values stay as no-JS fallback)
  document.querySelectorAll('[data-count]').forEach(el => {
    const target = parseFloat(el.dataset.count);
    if (!isFinite(target)) return;
    const prefix = el.dataset.prefix || '';
    const decimals = parseInt(el.dataset.decimals || '0', 10);
    const fmt = v => prefix + v.toLocaleString('en-IN', { minimumFractionDigits: decimals, maximumFractionDigits: decimals });
    if (reduceMotion) { el.textContent = fmt(target); return; }
    const duration = 900, start = performance.now();
    const tick = now => {
      const p = Math.min((now - start) / duration, 1);
      const eased = 1 - Math.pow(1 - p, 3);
      el.textContent = fmt(target * eased);
      if (p < 1) requestAnimationFrame(tick);
    };
    requestAnimationFrame(tick);
  });

  // Leaderboard bars grow in (flat solid bar; CSS handles color)
  document.querySelectorAll('.leader-bar i').forEach((bar, idx) => {
    if (reduceMotion) return;
    const final = bar.style.width;
    bar.style.width = '0';
    requestAnimationFrame(() => requestAnimationFrame(() => {
      bar.style.transitionDelay = (idx * 80) + 'ms';
      bar.style.width = final;
    }));
  });

  let salesChart = null;
  let categoryChart = null;

  function buildCharts() {
    const { isDark, link, muted, surface, grid } = themeVars();
    const tickFont = { family: 'Inter, system-ui, sans-serif', size: 11 };
    const tooltipBg = isDark ? '#1a1a1a' : '#16233A';
    const tooltipColor = isDark ? '#ededed' : '#ffffff';

    const salesCanvas = document.getElementById('salesChart');
    if (window.salesData?.length && salesCanvas && typeof Chart !== 'undefined') {
      if (salesChart) salesChart.destroy();
      // Flat fill, no gradient mesh — restrained per design reference.
      const fill = isDark ? 'rgba(50,145,255,.12)' : 'rgba(36,86,214,.10)';
      const isNarrow = window.matchMedia('(max-width: 480px)').matches;
      const xTicks = isNarrow
        ? { color: muted, font: tickFont, maxTicksLimit: 4, maxRotation: 0, autoSkip: true }
        : { color: muted, font: tickFont, maxTicksLimit: 8 };
      const tooltipStyle = {
        backgroundColor: tooltipBg, titleColor: tooltipColor, bodyColor: tooltipColor,
        borderColor: isDark ? '#2e2e2e' : 'transparent', borderWidth: isDark ? 1 : 0,
        titleFont: { family: 'Inter, system-ui, sans-serif', size: 12, weight: '600' },
        bodyFont: { family: 'Inter, system-ui, sans-serif', size: 12 },
        padding: 10, cornerRadius: 10, displayColors: false,
      };
      salesChart = new Chart(salesCanvas, {
        type: 'line',
        data: { labels: window.salesLabels, datasets: [{ data: window.salesData, borderColor: link, backgroundColor: fill, fill: true, tension: .42, pointRadius: 0, pointHoverRadius: 5, pointHoverBackgroundColor: link, pointHoverBorderColor: surface, pointHoverBorderWidth: 1.5, borderWidth: 2.5 }] },
        options: {
          animation: reduceMotion ? false : { duration: 900, easing: 'easeOutQuart' },
          interaction: { mode: 'index', intersect: false },
          plugins: { legend: { display: false }, tooltip: { ...tooltipStyle, callbacks: { label: ctx => ` \u20B9${Number(ctx.parsed.y).toLocaleString('en-IN')}` } } },
          scales: {
            y: { beginAtZero: true, grid: { color: grid }, ticks: { color: muted, font: tickFont, callback: v => '\u20B9' + v, maxTicksLimit: 5 } },
            x: { grid: { display: false }, ticks: xTicks },
          },
        },
      });
    }

    const categoryCanvas = document.getElementById('categoryChart');
    if (window.categoryData?.length && categoryCanvas && typeof Chart !== 'undefined') {
      if (categoryChart) categoryChart.destroy();
      const palette = isDark
        ? ['#3291ff', '#50e3c2', '#f5a623', '#a1a1a1', '#eb367f', '#ff0080']
        : ['#2456D6', '#0E9F8A', '#D9930D', '#64748B', '#7C5CD6', '#D6577B'];
      categoryChart = new Chart(categoryCanvas, {
        type: 'doughnut',
        data: { labels: window.categoryData.map(x => x.label), datasets: [{ data: window.categoryData.map(x => x.value), backgroundColor: palette, borderWidth: 3, borderColor: surface, borderRadius: 5, hoverOffset: 6 }] },
        options: {
          animation: reduceMotion ? false : { animateRotate: true, duration: 900, easing: 'easeOutQuart' },
          plugins: {
            legend: { display: false },
            tooltip: {
              backgroundColor: tooltipBg, titleColor: tooltipColor, bodyColor: tooltipColor,
              borderColor: isDark ? '#2e2e2e' : 'transparent', borderWidth: isDark ? 1 : 0,
              titleFont: { family: 'Inter, system-ui, sans-serif', size: 12, weight: '600' },
              bodyFont: { family: 'Inter, system-ui, sans-serif', size: 12 },
              padding: 10, cornerRadius: 10,
              callbacks: { label: ctx => ` ${ctx.label}: \u20B9${ctx.parsed} (${((ctx.parsed / window.categoryData.reduce((a, b) => a + b.value, 0)) * 100).toFixed(0)}%)` },
            },
          },
          cutout: '70%',
        },
      });
    }
  }

  buildCharts();

  // Rebuild on theme toggle so canvas colors follow CSS vars.
  window.addEventListener('billsmart-theme', () => buildCharts());
});
