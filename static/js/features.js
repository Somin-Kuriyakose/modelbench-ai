/* ============================================================
   ModelBench AI — Features Page JavaScript
   ============================================================ */

// ── Nav scroll ─────────────────────────────────────────────
const nav = document.querySelector('.nav');
window.addEventListener('scroll', () => {
  nav.classList.toggle('scrolled', window.scrollY > 20);
});

// ── Scroll Reveal ───────────────────────────────────────────
function initReveal() {
  const observer = new IntersectionObserver((entries) => {
    entries.forEach(e => {
      if (e.isIntersecting) { e.target.classList.add('visible'); observer.unobserve(e.target); }
    });
  }, { threshold: 0.12 });
  document.querySelectorAll('.feat-reveal').forEach(el => observer.observe(el));
}

// ── Index Nav Scroll Spy ────────────────────────────────────
function initScrollSpy() {
  const sections = document.querySelectorAll('.feat-section[id]');
  const links    = document.querySelectorAll('.feat-index-list a');

  const observer = new IntersectionObserver((entries) => {
    entries.forEach(e => {
      if (e.isIntersecting) {
        links.forEach(l => l.classList.remove('active'));
        const active = document.querySelector(`.feat-index-list a[href="#${e.target.id}"]`);
        if (active) active.classList.add('active');
      }
    });
  }, { rootMargin: '-30% 0px -60% 0px' });

  sections.forEach(s => observer.observe(s));
}

// ── Animated Mockups ────────────────────────────────────────
function initMockupAnimations() {
  const observer = new IntersectionObserver((entries) => {
    entries.forEach(e => {
      if (e.isIntersecting) {
        const id = e.target.closest('.feat-section')?.id;
        if (id) triggerMockup(id);
        observer.unobserve(e.target);
      }
    });
  }, { threshold: 0.3 });

  document.querySelectorAll('.feat-mockup').forEach(m => observer.observe(m));
}

function triggerMockup(sectionId) {
  switch (sectionId) {
    case 'latency':    animateLatencyMockup();    break;
    case 'memory':     animateMemoryMockup();     break;
    case 'accuracy':   animateAccuracyMockup();   break;
    case 'sweep':      animateSweepMockup();      break;
    case 'introspect': animateIntrospectMockup(); break;
    case 'async':      animateAsyncMockup();      break;
  }
}

// Latency bars
function animateLatencyMockup() {
  const fills = document.querySelectorAll('#latency .lat-fill');
  const targets = [18, 42, 55, 72, 84, 91, 100];
  fills.forEach((f, i) => {
    setTimeout(() => { f.style.width = targets[i] + '%'; }, i * 80);
  });
}

// Memory bar chart
function animateMemoryMockup() {
  const bars   = document.querySelectorAll('#memory .mem-bar');
  const heights = [25, 40, 38, 55, 62, 70, 65, 72, 68, 80, 75, 82, 78, 88, 84, 90];
  bars.forEach((b, i) => {
    setTimeout(() => { b.style.height = (heights[i] || 40) + '%'; }, i * 50);
  });
}

// Accuracy donut SVG animation
function animateAccuracyMockup() {
  const circle = document.getElementById('donut-circle');
  if (!circle) return;
  const r = 34, circumference = 2 * Math.PI * r;
  circle.style.strokeDasharray = circumference;
  circle.style.strokeDashoffset = circumference;
  setTimeout(() => {
    const pct = 0.943;
    circle.style.transition = 'stroke-dashoffset 1.4s cubic-bezier(0.22,1,0.36,1)';
    circle.style.strokeDashoffset = circumference * (1 - pct);
  }, 200);
}

// Sweep bars
function animateSweepMockup() {
  const heights = { bs1: 20, bs8: 45, bs32: 78, bs128: 95, bs256: 70 };
  Object.entries(heights).forEach(([id, h], i) => {
    const el = document.getElementById('sweep-bar-' + id.replace('bs',''));
    if (el) setTimeout(() => { el.style.height = h + '%'; }, i * 120);
  });
}

// Introspect feature importance bars
function animateIntrospectMockup() {
  const fills  = document.querySelectorAll('#introspect .fi-mini-fill');
  const widths = [92, 78, 65, 51, 38, 22];
  fills.forEach((f, i) => {
    setTimeout(() => { f.style.width = widths[i] + '%'; }, i * 100);
  });
}

// Async jobs progress bars
function animateAsyncMockup() {
  // Job 1 — done instantly
  const p1 = document.getElementById('async-prog-1');
  if (p1) p1.style.width = '100%';

  // Job 2 — animate to 67%
  const p2 = document.getElementById('async-prog-2');
  if (p2) setTimeout(() => { p2.style.width = '67%'; }, 300);
}

// ── Smooth scroll for index nav ─────────────────────────────
document.querySelectorAll('.feat-index-list a').forEach(a => {
  a.addEventListener('click', e => {
    e.preventDefault();
    const target = document.querySelector(a.getAttribute('href'));
    if (target) {
      const offset = 72 + 46; // nav + feat-index height
      const top = target.getBoundingClientRect().top + window.scrollY - offset;
      window.scrollTo({ top, behavior: 'smooth' });
    }
  });
});

// ── Init ────────────────────────────────────────────────────
document.addEventListener('DOMContentLoaded', () => {
  initReveal();
  initScrollSpy();
  initMockupAnimations();
});
