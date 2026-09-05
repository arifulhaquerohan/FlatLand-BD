/* =============================================================================
 * FlatLand BD — Enhanced animations module
 * Particle system, cursor follower, card glow, 3D tilt, ripple, testimonial
 * carousel, scroll progress, stagger reveals, and spring counters.
 * Vanilla ES2015+. No dependencies.
 * ========================================================================== */
(function () {
  "use strict";

  var doc = document;
  var root = doc.documentElement;
  var reduceMotion = window.matchMedia
    ? window.matchMedia("(prefers-reduced-motion: reduce)").matches
    : false;

  function $(sel, ctx) { return (ctx || doc).querySelector(sel); }
  function $$(sel, ctx) { return Array.prototype.slice.call((ctx || doc).querySelectorAll(sel)); }
  function on(el, ev, fn, opts) { if (el) el.addEventListener(ev, fn, opts || false); }
  function raf(fn) { window.requestAnimationFrame(fn); }

  /* ===========================================================
     1. PARTICLE SYSTEM — Floating dots in the hero
     =========================================================== */
  function initParticles() {
    var canvas = $(".particle-canvas");
    if (!canvas || reduceMotion) return;

    var ctx;
    var c = doc.createElement("canvas");
    c.style.cssText = "position:absolute;inset:0;width:100%;height:100%;pointer-events:none";
    canvas.appendChild(c);
    ctx = c.getContext("2d");

    var COUNT = 48;
    var particles = [];
    var w, h;
    var mouseX = -1000, mouseY = -1000;

    function resize() {
      var r = canvas.getBoundingClientRect();
      w = c.width = r.width;
      h = c.height = r.height;
    }

    function createParticle() {
      return {
        x: Math.random() * w,
        y: Math.random() * h,
        vx: (Math.random() - 0.5) * 0.35,
        vy: (Math.random() - 0.5) * 0.35,
        r: Math.random() * 2 + 0.6,
        opacity: Math.random() * 0.3 + 0.1
      };
    }

    resize();
    for (var i = 0; i < COUNT; i++) particles.push(createParticle());

    function draw() {
      ctx.clearRect(0, 0, w, h);

      for (var i = 0; i < particles.length; i++) {
        var p = particles[i];

        // Mouse repel
        var dx = p.x - mouseX;
        var dy = p.y - mouseY;
        var dist = Math.sqrt(dx * dx + dy * dy);
        if (dist < 120 && dist > 0) {
          var force = (120 - dist) / 120 * 0.02;
          p.vx += dx / dist * force;
          p.vy += dy / dist * force;
        }

        // Friction
        p.vx *= 0.995;
        p.vy *= 0.995;

        p.x += p.vx;
        p.y += p.vy;

        // Wrap
        if (p.x < -10) p.x = w + 10;
        if (p.x > w + 10) p.x = -10;
        if (p.y < -10) p.y = h + 10;
        if (p.y > h + 10) p.y = -10;

        ctx.beginPath();
        ctx.arc(p.x, p.y, p.r, 0, Math.PI * 2);
        ctx.fillStyle = "rgba(194, 98, 47, " + p.opacity + ")";
        ctx.fill();

        // Draw connections
        for (var j = i + 1; j < particles.length; j++) {
          var q = particles[j];
          var ddx = p.x - q.x;
          var ddy = p.y - q.y;
          var d2 = ddx * ddx + ddy * ddy;
          if (d2 < 18000) {
            var alpha = (1 - d2 / 18000) * 0.12;
            ctx.beginPath();
            ctx.moveTo(p.x, p.y);
            ctx.lineTo(q.x, q.y);
            ctx.strokeStyle = "rgba(194, 98, 47, " + alpha + ")";
            ctx.lineWidth = 0.6;
            ctx.stroke();
          }
        }
      }

      raf(draw);
    }

    raf(draw);
    on(window, "resize", resize, { passive: true });

    on(canvas, "mousemove", function (e) {
      var r = canvas.getBoundingClientRect();
      mouseX = e.clientX - r.left;
      mouseY = e.clientY - r.top;
    });
    on(canvas, "mouseleave", function () { mouseX = -1000; mouseY = -1000; });
  }

  /* ===========================================================
     2. CUSTOM CURSOR FOLLOWER
     =========================================================== */
  function initCursor() {
    if (reduceMotion || window.matchMedia("(pointer: coarse)").matches) return;

    var dot = doc.createElement("div");
    dot.className = "cursor-dot";
    doc.body.appendChild(dot);

    var cx = -100, cy = -100;
    var tx = -100, ty = -100;
    var hovering = false;

    function lerp(a, b, t) { return a + (b - a) * t; }

    function loop() {
      cx = lerp(cx, tx, 0.18);
      cy = lerp(cy, ty, 0.18);
      dot.style.left = cx + "px";
      dot.style.top = cy + "px";
      raf(loop);
    }
    raf(loop);

    on(doc, "mousemove", function (e) {
      tx = e.clientX;
      ty = e.clientY;
      if (!dot.classList.contains("is-visible")) dot.classList.add("is-visible");
    });

    on(doc, "mouseleave", function () { dot.classList.remove("is-visible"); });

    // Detect hoverable elements
    var hoverSels = "a, button, .btn, .listing, .chip, .navlink, .quote-card, .step, .icon-btn, .fab";
    on(doc, "mouseover", function (e) {
      var target = e.target.closest ? e.target.closest(hoverSels) : null;
      if (target && !hovering) { hovering = true; dot.classList.add("is-hovering"); }
    });
    on(doc, "mouseout", function (e) {
      var target = e.target.closest ? e.target.closest(hoverSels) : null;
      if (target && hovering) {
        var related = e.relatedTarget ? e.relatedTarget.closest(hoverSels) : null;
        if (!related) { hovering = false; dot.classList.remove("is-hovering"); }
      }
    });
  }

  /* ===========================================================
     3. CARD GLOW TRACKING
     =========================================================== */
  function initCardGlow() {
    if (reduceMotion) return;
    $$(".listing").forEach(function (card) {
      card.classList.add("has-glow");
      on(card, "pointermove", function (e) {
        var r = card.getBoundingClientRect();
        card.style.setProperty("--glow-x", ((e.clientX - r.left)) + "px");
        card.style.setProperty("--glow-y", ((e.clientY - r.top)) + "px");
      });
    });
  }

  /* ===========================================================
     4. BUTTON RIPPLE EFFECT
     =========================================================== */
  function initRipple() {
    if (reduceMotion) return;
    on(doc, "click", function (e) {
      var btn = e.target.closest ? e.target.closest(".btn") : null;
      if (!btn) return;
      btn.classList.add("has-ripple");
      var r = btn.getBoundingClientRect();
      var ripple = doc.createElement("span");
      ripple.className = "ripple";
      var size = Math.max(r.width, r.height) * 2;
      ripple.style.width = size + "px";
      ripple.style.height = size + "px";
      ripple.style.left = (e.clientX - r.left - size / 2) + "px";
      ripple.style.top = (e.clientY - r.top - size / 2) + "px";
      btn.appendChild(ripple);
      window.setTimeout(function () {
        if (ripple.parentNode) ripple.parentNode.removeChild(ripple);
      }, 700);
    });
  }

  /* ===========================================================
     5. ENHANCED SCROLL PROGRESS
     =========================================================== */
  function initScrollProgress() {
    var bar = $(".scroll-progress__bar");
    if (!bar) return;

    var ticking = false;
    function paint() {
      var scrollTop = window.pageYOffset || root.scrollTop || 0;
      var docHeight = doc.body.scrollHeight - window.innerHeight;
      var pct = docHeight > 0 ? Math.min(1, scrollTop / docHeight) : 0;
      bar.style.transform = "scaleX(" + pct + ")";
      ticking = false;
    }

    on(window, "scroll", function () {
      if (!ticking) { ticking = true; raf(paint); }
    }, { passive: true });
    paint();
  }

  /* ===========================================================
     6. REVEAL GROUP STAGGER
     =========================================================== */
  function initStaggerGroups() {
    var groups = $$("[data-reveal-group='stagger']");
    if (!groups.length) return;

    if (reduceMotion || !("IntersectionObserver" in window)) {
      groups.forEach(function (g) { g.classList.add("is-in"); });
      return;
    }

    var io = new IntersectionObserver(function (entries) {
      entries.forEach(function (entry) {
        if (!entry.isIntersecting) return;
        entry.target.classList.add("is-in");
        io.unobserve(entry.target);
      });
    }, { threshold: 0.15, rootMargin: "0px 0px -6% 0px" });

    groups.forEach(function (g) { io.observe(g); });
  }

  /* ===========================================================
     7. TESTIMONIAL CAROUSEL
     =========================================================== */
  function initTestimonialCarousel() {
    var track = $(".testimonials-track");
    if (!track) return;

    var cards = $$(".quote-card", track);
    var dotsWrap = $(".testimonial-dots");
    if (!dotsWrap || !cards.length) return;

    // Create dots
    cards.forEach(function (_, i) {
      var dot = doc.createElement("button");
      dot.className = "testimonial-dot" + (i === 0 ? " is-active" : "");
      dot.setAttribute("aria-label", "Go to testimonial " + (i + 1));
      dot.setAttribute("type", "button");
      dotsWrap.appendChild(dot);

      on(dot, "click", function () {
        cards[i].scrollIntoView({ behavior: reduceMotion ? "auto" : "smooth", block: "nearest", inline: "start" });
      });
    });

    var dots = $$(".testimonial-dot", dotsWrap);

    // Observe which card is visible
    if ("IntersectionObserver" in window) {
      var io = new IntersectionObserver(function (entries) {
        entries.forEach(function (entry) {
          if (!entry.isIntersecting) return;
          var idx = cards.indexOf(entry.target);
          dots.forEach(function (d, di) { d.classList.toggle("is-active", di === idx); });
        });
      }, { root: track, threshold: 0.6 });
      cards.forEach(function (c) { io.observe(c); });
    }

    // Auto-scroll
    if (!reduceMotion) {
      var autoIdx = 0;
      var autoInterval = window.setInterval(function () {
        autoIdx = (autoIdx + 1) % cards.length;
        cards[autoIdx].scrollIntoView({ behavior: "smooth", block: "nearest", inline: "start" });
      }, 6000);

      on(track, "pointerdown", function () { window.clearInterval(autoInterval); });
      on(track, "wheel", function () { window.clearInterval(autoInterval); }, { passive: true });
    }
  }

  /* ===========================================================
     8. SPRING COUNTER (bounce on count end)
     =========================================================== */
  function initSpringCounters() {
    $$("[data-count]").forEach(function (el) {
      el.classList.add("counter-spring");
    });

    // Watch for existing animateCount to finish by observing text changes
    if (!("MutationObserver" in window)) return;
    $$(".counter-spring").forEach(function (el) {
      var target = parseFloat(el.getAttribute("data-count"));
      if (isNaN(target)) return;

      var observer = new MutationObserver(function () {
        var text = el.textContent.replace(/[^0-9.]/g, "");
        var val = parseFloat(text);
        if (!isNaN(val) && Math.abs(val - target) < 0.1) {
          el.classList.add("is-counting");
          window.setTimeout(function () { el.classList.remove("is-counting"); }, 400);
          observer.disconnect();
        }
      });
      observer.observe(el, { childList: true, characterData: true, subtree: true });
    });
  }

  /* ===========================================================
     9. STEP HOVER ANIMATIONS
     =========================================================== */
  function initStepAnimations() {
    $$(".step").forEach(function (step) {
      step.classList.add("has-anim");
    });
  }

  /* ===========================================================
     10. QUOTE CARD ACCENTS
     =========================================================== */
  function initQuoteAccents() {
    $$(".quote-card").forEach(function (card) {
      card.classList.add("has-accent");
    });
  }

  /* ===========================================================
     11. ENHANCED BUTTON SHINE
     =========================================================== */
  function initButtonShine() {
    if (reduceMotion) return;
    $$(".btn--lg, .btn-arrow").forEach(function (btn) {
      btn.classList.add("has-shine");
    });
  }

  /* ===========================================================
     12. FAB PULSE
     =========================================================== */
  function initFabPulse() {
    if (reduceMotion) return;
    $$(".fab--wa").forEach(function (fab) {
      fab.classList.add("has-pulse");
    });
  }

  /* ===========================================================
     13. CTA SHIMMER
     =========================================================== */
  function initCtaShimmer() {
    if (reduceMotion) return;
    $$(".cta-band").forEach(function (band) {
      band.classList.add("has-shimmer");
    });
  }

  /* ===========================================================
     14. SMOOTH TEXT REVEAL (character-by-character for hero)
     =========================================================== */
  function initTextReveal() {
    if (reduceMotion) return;
    var el = $(".hero__title .accent");
    if (!el) return;

    // Add shimmer to the "About" heading
    var aboutH2 = $("#about .h1");
    if (aboutH2) aboutH2.classList.add("text-shimmer");
  }

  /* ===========================================================
     15. METRIC GLOW
     =========================================================== */
  function initMetricGlow() {
    $$(".metric").forEach(function (m) {
      m.classList.add("has-glow");
    });
  }

  /* ===========================================================
     BOOT
     =========================================================== */
  function ready(fn) {
    if (doc.readyState === "loading") doc.addEventListener("DOMContentLoaded", fn);
    else fn();
  }

  ready(function () {
    initParticles();
    initCursor();
    initCardGlow();
    initRipple();
    initScrollProgress();
    initStaggerGroups();
    initTestimonialCarousel();
    initSpringCounters();
    initStepAnimations();
    initQuoteAccents();
    initButtonShine();
    initFabPulse();
    initCtaShimmer();
    initTextReveal();
    initMetricGlow();
  });
})();
