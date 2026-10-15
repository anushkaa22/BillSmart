document.addEventListener('DOMContentLoaded', () => {
  const root = document.documentElement;
  const saved = localStorage.getItem('billsmart-theme');
  const prefersDark = window.matchMedia('(prefers-color-scheme: dark)').matches;
  const initial = saved || (prefersDark ? 'dark' : 'light');
  root.dataset.theme = initial;
  root.classList.toggle('dark', initial === 'dark');
  const themeToggle = document.getElementById('themeToggle');
  if (themeToggle) themeToggle.addEventListener('click', () => {
    const isDark = root.classList.contains('dark');
    const next = isDark ? 'light' : 'dark';
    root.dataset.theme = next;
    root.classList.toggle('dark', next === 'dark');
    localStorage.setItem('billsmart-theme', next);
  });
  window.matchMedia('(prefers-color-scheme: dark)').addEventListener('change', e => {
    if (!localStorage.getItem('billsmart-theme')) {
      const next = e.matches ? 'dark' : 'light';
      root.dataset.theme = next;
      root.classList.toggle('dark', next === 'dark');
    }
  });
  const menu = document.getElementById('menuToggle'), sidebar = document.getElementById('sidebar'), backdrop = document.getElementById('sidebarBackdrop');
  function setCollapsed(collapsed) {
    document.body.classList.toggle('sidebar-collapsed', collapsed);
    document.documentElement.classList.toggle('sidebar-collapsed', collapsed);
    try { localStorage.setItem('billsmart-sidebar', collapsed ? 'collapsed' : 'expanded'); } catch (e) {}
    if (menu) {
      menu.setAttribute('aria-expanded', collapsed ? 'false' : 'true');
      menu.innerHTML = `<i class="bi bi-${collapsed ? 'list' : 'chevron-left'}"></i>`;
    }
  }
  try {
    if (document.documentElement.classList.contains('sidebar-collapsed')) {
      document.body.classList.add('sidebar-collapsed');
      if (menu) { menu.setAttribute('aria-expanded', 'false'); menu.innerHTML = '<i class="bi bi-list"></i>'; }
    } else if (window.innerWidth > 800 && localStorage.getItem('billsmart-sidebar') === 'collapsed') {
      document.body.classList.add('sidebar-collapsed');
      document.documentElement.classList.add('sidebar-collapsed');
      if (menu) { menu.setAttribute('aria-expanded', 'false'); menu.innerHTML = '<i class="bi bi-list"></i>'; }
    }
  } catch (e) {}
  function openSidebar(open) {
    const isOpen = open !== undefined ? open : !sidebar.classList.contains('open');
    sidebar.classList.toggle('open', isOpen);
    if (backdrop) backdrop.classList.toggle('open', isOpen);
    document.body.classList.toggle('sidebar-open', isOpen);
    if (menu && window.innerWidth <= 800) menu.setAttribute('aria-expanded', isOpen ? 'true' : 'false');
  }
  if (menu && sidebar) {
    menu.addEventListener('click', () => {
      if (window.innerWidth > 800) {
        setCollapsed(!document.body.classList.contains('sidebar-collapsed'));
      } else {
        openSidebar();
      }
    });
    if (backdrop) backdrop.addEventListener('click', () => openSidebar(false));
    document.querySelectorAll('.side-nav a.nav-link').forEach(a => a.addEventListener('click', () => { if (window.innerWidth <= 800) openSidebar(false); }));
    document.addEventListener('keydown', e => { if (e.key === 'Escape' && sidebar.classList.contains('open')) openSidebar(false); });
    window.addEventListener('resize', () => { if (window.innerWidth > 800 && sidebar.classList.contains('open')) openSidebar(false); });
  }
  document.querySelectorAll('.password-toggle').forEach(btn => btn.addEventListener('click', () => { const input = document.getElementById(btn.dataset.target); input.type = input.type === 'password' ? 'text' : 'password'; btn.innerHTML = `<i class="bi bi-${input.type === 'password' ? 'eye' : 'eye-slash'}"></i>`; }));
  document.querySelectorAll('[data-modal]').forEach(btn => btn.addEventListener('click', () => document.getElementById(btn.dataset.modal).classList.add('open')));
  document.querySelectorAll('.modal-close').forEach(btn => btn.addEventListener('click', () => btn.closest('.modal').classList.remove('open')));
  document.querySelectorAll('.modal').forEach(modal => modal.addEventListener('click', e => { if (e.target === modal) modal.classList.remove('open'); }));
  const productImageInput=document.getElementById('productImage'),preview=document.getElementById('preview');if(productImageInput&&preview){productImageInput.addEventListener('change',e=>{const f=e.target.files[0];if(!f)return;if(!f.type.startsWith('image/'))return;preview.src=URL.createObjectURL(f);preview.classList.remove('hidden');preview.onload=()=>URL.revokeObjectURL(preview.src);const hint=preview.nextElementSibling;if(hint)hint.textContent='New image selected: '+f.name;});}
  setTimeout(() => document.querySelectorAll('.toast-message').forEach(t => t.classList.add('hide')), 4200);
  const splash = document.getElementById('splash');
  if (splash) {
    const reduceMotion = window.matchMedia('(prefers-reduced-motion: reduce)').matches;
    document.body.classList.add('splash-lock');
    let finished = false;
    const finish = () => {
      if (finished) return;
      finished = true;
      splash.classList.add('done');
      splash.setAttribute('aria-hidden', 'true');
      document.body.classList.remove('splash-lock');
      const focusTarget = document.querySelector('.auth-card input[name="identity"], .auth-card input[name="username"]');
      if (focusTarget && !reduceMotion) focusTarget.focus({ preventScroll: true });
      setTimeout(() => splash.remove(), 400);
    };
    if (reduceMotion) {
      finish();
    } else {
      setTimeout(finish, 1500);
      splash.addEventListener('click', finish);
      document.addEventListener('keydown', function skip(e) {
        if (finished) return;
        if (e.key === 'Escape' || e.key === 'Enter' || e.key === ' ') finish();
      }, { once: false });
    }
  }
});
