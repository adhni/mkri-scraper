/* Progressive enhancement: links and forms remain usable without JavaScript. */
(() => {
  const storageKey = 'mkri-browse-position';
  document.querySelectorAll('[data-case-link]').forEach(link => link.addEventListener('click', () => {
    try { sessionStorage.setItem(storageKey, JSON.stringify({url: location.pathname + location.search, y: scrollY})); } catch (_) {}
  }));
  if (location.pathname === '/cases' || location.pathname === '/') {
    try {
      const prior = JSON.parse(sessionStorage.getItem(storageKey) || 'null');
      if (prior && prior.url === location.pathname + location.search) {
        requestAnimationFrame(() => window.scrollTo(0, prior.y));
        sessionStorage.removeItem(storageKey);
      }
    } catch (_) {}
  }
  const navLinks = [...document.querySelectorAll('.case-nav a')];
  if ('IntersectionObserver' in window && navLinks.length) {
    const observer = new IntersectionObserver(entries => {
      const entry = entries.find(e => e.isIntersecting);
      if (!entry) return;
      navLinks.forEach(a => a.toggleAttribute('aria-current', a.hash === '#' + entry.target.id));
    }, {rootMargin: '-70px 0px -65% 0px'});
    navLinks.forEach(a => { const section = document.querySelector(a.hash); if (section) observer.observe(section); });
  }
  const dialog = document.getElementById('source-reader');
  if (dialog) {
    const frame = document.getElementById('source-frame');
    const field = document.getElementById('pdf-page');
    const openPage = page => {
      page = Math.min(Number(field.max), Math.max(1, Number(page) || 1));
      field.value = page;
      // The page-specific URL also works when the server redirects to MK's PDF host.
      const url = frame.dataset.pdfUrl + '#page=' + page;
      frame.src = url;
      document.getElementById('external-pdf').href = url;
    };
    document.querySelectorAll('[data-pdf-page]').forEach(link => link.addEventListener('click', event => {
      if (event.metaKey || event.ctrlKey || event.shiftKey || event.altKey) return;
      event.preventDefault();
      const context = link.closest('article') || link.closest('.reader-section');
      document.getElementById('source-context').textContent = (context?.innerText || document.querySelector('h1').innerText).slice(0, 1200);
      openPage(link.dataset.pdfPage);
      dialog.showModal();
    }));
    document.getElementById('close-source').addEventListener('click', () => dialog.close());
    dialog.addEventListener('close', () => frame.removeAttribute('src'));
    document.getElementById('pdf-page-form').addEventListener('submit', event => { event.preventDefault(); openPage(field.value); });
  }
  const searchForm = document.getElementById('text-search-form');
  if (searchForm) {
    const text = document.querySelector('.document-text');
    const status = document.getElementById('text-search-status');
    let query = '', matches = [], current = -1;
    searchForm.addEventListener('submit', event => {
      event.preventDefault();
      const next = document.getElementById('document-query').value.trim();
      if (next !== query) {
        text.querySelectorAll('mark').forEach(mark => mark.replaceWith(document.createTextNode(mark.textContent)));
        text.normalize(); matches = []; current = -1; query = next;
        if (query) {
          const nodes = [], walker = document.createTreeWalker(text, NodeFilter.SHOW_TEXT);
          while (walker.nextNode()) nodes.push(walker.currentNode);
          nodes.forEach(node => {
            const source = node.textContent, lower = source.toLocaleLowerCase('id');
            let start = 0, index = lower.indexOf(query.toLocaleLowerCase('id'));
            if (index < 0) return;
            const fragment = document.createDocumentFragment();
            while (index >= 0) {
              fragment.append(document.createTextNode(source.slice(start, index)));
              const mark = document.createElement('mark'); mark.textContent = source.slice(index, index + query.length);
              fragment.append(mark); matches.push(mark); start = index + query.length;
              index = lower.indexOf(query.toLocaleLowerCase('id'), start);
            }
            fragment.append(document.createTextNode(source.slice(start))); node.replaceWith(fragment);
          });
        }
      }
      matches.forEach(mark => mark.classList.remove('current-match'));
      if (matches.length) {
        current = (current + 1) % matches.length;
        matches[current].classList.add('current-match');
        const mark = matches[current];
        text.scrollTop += mark.getBoundingClientRect().top - text.getBoundingClientRect().top - 60;
        status.textContent = `${current + 1} dari ${matches.length} hasil · Temukan untuk berikutnya`;
      } else status.textContent = query ? 'Tidak ditemukan dalam teks.' : 'Masukkan kata untuk mencari.';
    });
  }
})();
