(() => {
  const toggle = document.querySelector('.mobile-nav-toggle');
  const nav = document.querySelector('#main-nav');
  if (toggle && nav) {
    toggle.addEventListener('click', () => {
      const open = nav.classList.toggle('open');
      toggle.setAttribute('aria-expanded', String(open));
    });
  }

  document.querySelectorAll('.delete-form').forEach(form => {
    form.addEventListener('submit', e => {
      const msg = form.dataset.confirm || 'Delete this item?';
      if (!window.confirm(msg)) e.preventDefault();
    });
  });

  const celebration = document.querySelector('#celebration');
  const close = document.querySelector('#celebration-close');
  const title = document.querySelector('#celebration-title');
  const xp = document.querySelector('#celebration-xp');
  const gold = document.querySelector('#celebration-gold');
  const level = document.querySelector('#celebration-level');

  function showCelebration(data) {
    if (!celebration) return;
    title.textContent = data.level_up ? 'LEVEL UP!' : 'QUEST COMPLETE';
    xp.textContent = `+${data.xp_gained} XP`;
    gold.textContent = `+${data.gold_gained} Gold  •  🔥 ${data.streak} day streak`;
    level.textContent = data.level_up ? `LEVEL ${data.new_level} UNLOCKED` : '';
    celebration.classList.add('show');
    celebration.setAttribute('aria-hidden', 'false');
    close?.focus();
  }
  function hideCelebration() {
    celebration?.classList.remove('show');
    celebration?.setAttribute('aria-hidden', 'true');
  }
  close?.addEventListener('click', hideCelebration);
  celebration?.addEventListener('click', e => { if (e.target === celebration) hideCelebration(); });

  document.querySelectorAll('.complete-form').forEach(form => {
    form.addEventListener('submit', async e => {
      e.preventDefault();
      const button = form.querySelector('button');
      button.disabled = true;
      button.textContent = 'Resolving…';
      try {
        const response = await fetch(form.action, {
          method: 'POST',
          headers: {
            'Accept': 'application/json',
            'X-CSRF-Token': window.APP.csrfToken,
            'Content-Type': 'application/x-www-form-urlencoded'
          },
          body: new URLSearchParams(new FormData(form))
        });
        if (!response.ok) throw new Error('Quest completion failed');
        const data = await response.json();
        showCelebration(data);
        setTimeout(() => window.location.reload(), 1800);
      } catch (err) {
        window.location.reload();
      }
    });
  });
})();
