/* ============================================================
   ModelBench AI — FAQ Page JavaScript
   ============================================================ */

// ── Nav scroll ─────────────────────────────────────────────
const nav = document.querySelector('.nav');
window.addEventListener('scroll', () => {
  nav.classList.toggle('scrolled', window.scrollY > 20);
});

// ── Accordion ──────────────────────────────────────────────
function initAccordion() {
  document.querySelectorAll('.faq-question').forEach(btn => {
    btn.addEventListener('click', () => {
      const item = btn.closest('.faq-item');
      const isOpen = item.classList.contains('open');

      // Close all in same group
      item.closest('.faq-group').querySelectorAll('.faq-item').forEach(i => {
        i.classList.remove('open');
      });

      // Toggle clicked
      if (!isOpen) item.classList.add('open');
    });
  });
}

// ── Category Filter ─────────────────────────────────────────
function initCategoryFilter() {
  const btns   = document.querySelectorAll('.faq-cat-btn');
  const groups = document.querySelectorAll('.faq-group');

  btns.forEach(btn => {
    btn.addEventListener('click', () => {
      btns.forEach(b => b.classList.remove('active'));
      btn.classList.add('active');

      const cat = btn.dataset.cat;
      groups.forEach(g => {
        if (cat === 'all' || g.dataset.cat === cat) {
          g.classList.remove('hidden');
          g.style.animation = 'fadeUp 0.3s ease';
        } else {
          g.classList.add('hidden');
        }
      });

      clearSearch();
    });
  });
}

// ── Search ──────────────────────────────────────────────────
function initSearch() {
  const input   = document.getElementById('faqSearch');
  const countEl = document.getElementById('searchCount');
  const empty   = document.getElementById('faqEmpty');
  if (!input) return;

  input.addEventListener('input', () => {
    const q = input.value.trim().toLowerCase();

    // Reset category to all
    document.querySelectorAll('.faq-cat-btn').forEach(b => b.classList.remove('active'));
    document.querySelector('[data-cat="all"]')?.classList.add('active');
    document.querySelectorAll('.faq-group').forEach(g => g.classList.remove('hidden'));

    if (!q) {
      clearHighlights();
      countEl.textContent = '';
      empty.classList.remove('visible');
      return;
    }

    let matchCount = 0;
    document.querySelectorAll('.faq-item').forEach(item => {
      const qText = item.querySelector('.faq-q-text')?.textContent.toLowerCase() || '';
      const aText = item.querySelector('.faq-answer-inner')?.textContent.toLowerCase() || '';
      const match = qText.includes(q) || aText.includes(q);
      item.style.display = match ? '' : 'none';
      if (match) {
        matchCount++;
        highlightText(item.querySelector('.faq-q-text'), q);
      }
    });

    // Hide empty groups
    document.querySelectorAll('.faq-group').forEach(g => {
      const visible = [...g.querySelectorAll('.faq-item')].some(i => i.style.display !== 'none');
      g.style.display = visible ? '' : 'none';
    });

    countEl.textContent = matchCount > 0 ? `${matchCount} result${matchCount > 1 ? 's' : ''}` : '';
    empty.classList.toggle('visible', matchCount === 0);
  });
}

function highlightText(el, query) {
  if (!el) return;
  const text = el.textContent;
  const idx  = text.toLowerCase().indexOf(query);
  if (idx === -1) { el.innerHTML = text; return; }
  el.innerHTML =
    escHtml(text.slice(0, idx)) +
    `<mark class="search-match">${escHtml(text.slice(idx, idx + query.length))}</mark>` +
    escHtml(text.slice(idx + query.length));
}

function clearHighlights() {
  document.querySelectorAll('.faq-q-text mark').forEach(m => {
    const parent = m.parentNode;
    parent.replaceChild(document.createTextNode(m.textContent), m);
    parent.normalize();
  });
  document.querySelectorAll('.faq-item').forEach(i => { i.style.display = ''; });
  document.querySelectorAll('.faq-group').forEach(g => { g.style.display = ''; });
}

function clearSearch() {
  const input = document.getElementById('faqSearch');
  if (input) { input.value = ''; clearHighlights(); }
  document.getElementById('searchCount').textContent = '';
  document.getElementById('faqEmpty')?.classList.remove('visible');
}

function escHtml(str) {
  return str.replace(/&/g,'&amp;').replace(/</g,'&lt;').replace(/>/g,'&gt;');
}

// ── Scroll reveal ───────────────────────────────────────────
function initReveal() {
  const observer = new IntersectionObserver((entries) => {
    entries.forEach(e => {
      if (e.isIntersecting) { e.target.classList.add('visible'); observer.unobserve(e.target); }
    });
  }, { threshold: 0.1 });
  document.querySelectorAll('.faq-reveal').forEach(el => observer.observe(el));
}

// ── Init ────────────────────────────────────────────────────
document.addEventListener('DOMContentLoaded', () => {
  initAccordion();
  initCategoryFilter();
  initSearch();
  initReveal();

  // Open first item in each group by default
  document.querySelectorAll('.faq-group').forEach(g => {
    g.querySelector('.faq-item')?.classList.add('open');
  });
});
