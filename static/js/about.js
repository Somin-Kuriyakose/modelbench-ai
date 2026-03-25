/* ============================================================
   ModelBench AI — About Page JavaScript
   ============================================================ */

// ── Nav scroll ────────────────────────────────────────────
const nav = document.querySelector('.nav');
window.addEventListener('scroll', () => {
  nav.classList.toggle('scrolled', window.scrollY > 20);
});

// ── Scroll Reveal ─────────────────────────────────────────
function initReveal() {
  const observer = new IntersectionObserver((entries) => {
    entries.forEach(entry => {
      if (entry.isIntersecting) {
        entry.target.classList.add('visible');
        observer.unobserve(entry.target);
      }
    });
  }, { threshold: 0.12 });

  document.querySelectorAll('.about-reveal, .timeline-item').forEach(el => observer.observe(el));
}

// ── Stagger children reveal ───────────────────────────────
function initStaggerReveal() {
  const observer = new IntersectionObserver((entries) => {
    entries.forEach(entry => {
      if (entry.isIntersecting) {
        const children = entry.target.querySelectorAll('.about-reveal');
        children.forEach((child, i) => {
          setTimeout(() => child.classList.add('visible'), i * 100);
        });
        observer.unobserve(entry.target);
      }
    });
  }, { threshold: 0.08 });

  document.querySelectorAll('.values-grid, .team-grid, .stack-grid').forEach(el => observer.observe(el));
}

// ── Animated number counters ──────────────────────────────
function animateCounter(el, target, duration = 1600) {
  const start = performance.now();
  const isFloat = !Number.isInteger(target);
  function step(now) {
    const t = Math.min((now - start) / duration, 1);
    const eased = 1 - (1 - t) * (1 - t) * (1 - t);
    const val = target * eased;
    el.textContent = isFloat ? val.toFixed(1) : Math.floor(val).toLocaleString();
    if (t < 1) requestAnimationFrame(step);
    else el.textContent = isFloat ? target.toFixed(1) : target.toLocaleString();
  }
  requestAnimationFrame(step);
}

function initCounters() {
  const observer = new IntersectionObserver((entries) => {
    entries.forEach(entry => {
      if (entry.isIntersecting) {
        entry.target.querySelectorAll('[data-count]').forEach(el => {
          if (!el.dataset.done) {
            el.dataset.done = '1';
            animateCounter(el, parseFloat(el.dataset.count));
          }
        });
        observer.unobserve(entry.target);
      }
    });
  }, { threshold: 0.2 });

  document.querySelectorAll('.mission-section').forEach(el => observer.observe(el));
}

// ── Particle background for about hero ───────────────────
function initAboutHeroGrid() {
  // Subtle floating dots in the hero grid pattern
  const hero = document.querySelector('.about-hero');
  if (!hero) return;
  // CSS handles the grid; we add subtle parallax
  window.addEventListener('scroll', () => {
    const scrolled = window.scrollY;
    const rate = scrolled * 0.15;
    const grid = hero.querySelector('.about-hero-inner');
    if (grid) grid.style.transform = `translateY(${rate}px)`;
  });
}

// ── Init ──────────────────────────────────────────────────
document.addEventListener('DOMContentLoaded', () => {
  initReveal();
  initStaggerReveal();
  initCounters();
  initAboutHeroGrid();
});
