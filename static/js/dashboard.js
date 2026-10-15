document.addEventListener('DOMContentLoaded', () => {
  const styles = getComputedStyle(document.documentElement);
  const accent = styles.getPropertyValue('--accent').trim() || '#171717';
  const muted = styles.getPropertyValue('--muted').trim() || '#8f8f8f';
  const reduceMotion = window.matchMedia('(prefers-reduced-motion: reduce)').matches;

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

  // Leaderboard bars grow in
  document.querySelectorAll('.leader-bar i').forEach((bar, idx) => {
    if (reduceMotion) return;
    const final = bar.style.width;
    bar.style.width = '0';
    requestAnimationFrame(() => requestAnimationFrame(() => {
      bar.style.transitionDelay = (idx * 80) + 'ms';
      bar.style.width = final;
    }));
  });

  // Sales line paint (colors/fonts/grid only — data untouched; skipped if Chart CDN is blocked)
  const salesCanvas = document.getElementById('salesChart');
  if (window.salesData?.length && salesCanvas && typeof Chart !== 'undefined') {
    const blue = '#2456D6';
    const grid = (muted || '#8f8f8f') + '1F';
    let fill = 'rgba(36,86,214,.12)';
    try {
      const ctx = salesCanvas.getContext('2d');
      const grad = ctx.createLinearGradient(0, 0, 0, 220);
      grad.addColorStop(0, 'rgba(36,86,214,.22)');
      grad.addColorStop(1, 'rgba(36,86,214,0)');
      fill = grad;
    } catch (e) {}
    const tickFont = { family: 'Inter, system-ui, sans-serif', size: 11 };
    const isNarrow = window.matchMedia('(max-width: 480px)').matches;
    const xTicks = isNarrow ? { color: muted, font: tickFont, maxTicksLimit: 4, maxRotation: 0, autoSkip: true } : { color: muted, font: tickFont, maxTicksLimit: 8 };
    const tooltipStyle = { backgroundColor: '#16233A', titleFont: { family: 'Inter, system-ui, sans-serif', size: 12, weight: '600' }, bodyFont: { family: 'Inter, system-ui, sans-serif', size: 12 }, padding: 10, cornerRadius: 10, displayColors: false };
    new Chart(salesCanvas, {type:'line',data:{labels:window.salesLabels,datasets:[{data:window.salesData,borderColor:blue,backgroundColor:fill,fill:true,tension:.42,pointRadius:0,pointHoverRadius:5,pointHoverBackgroundColor:blue,pointHoverBorderColor:'#fff',pointHoverBorderWidth:1.5,borderWidth:2.5}]},options:{animation:reduceMotion ? false : {duration:900,easing:'easeOutQuart'},interaction:{mode:'index',intersect:false},plugins:{legend:{display:false},tooltip:{...tooltipStyle,callbacks:{label:ctx=>` ₹${Number(ctx.parsed.y).toLocaleString('en-IN')}`}}},scales:{y:{beginAtZero:true,grid:{color:grid},ticks:{color:muted,font:tickFont,callback:v=>'₹'+v,maxTicksLimit:5}},x:{grid:{display:false},ticks:xTicks}}}});
  }
  if (window.categoryData?.length && document.getElementById('categoryChart') && typeof Chart !== 'undefined') new Chart(document.getElementById('categoryChart'), {type:'doughnut',data:{labels:window.categoryData.map(x=>x.label),datasets:[{data:window.categoryData.map(x=>x.value),backgroundColor:['#2456D6','#0E9F8A','#D9930D','#64748B','#7C5CD6','#D6577B'],borderWidth:3,borderColor:getComputedStyle(document.body).backgroundColor,borderRadius:5,hoverOffset:6}]},options:{animation:reduceMotion ? false : {animateRotate:true,duration:900,easing:'easeOutQuart'},plugins:{legend:{display:false},tooltip:{backgroundColor:'#16233A',titleFont:{family:'Inter, system-ui, sans-serif',size:12,weight:'600'},bodyFont:{family:'Inter, system-ui, sans-serif',size:12},padding:10,cornerRadius:10,callbacks:{label:ctx=>` ${ctx.label}: ₹${ctx.parsed} (${((ctx.parsed/(window.categoryData.reduce((a,b)=>a+b.value,0)))*100).toFixed(0)}%)`}}},cutout:'70%'}});
});
