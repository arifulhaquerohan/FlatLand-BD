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
  // Hover effects (glow tracking, shine, shimmer) only make sense where a
  // real cursor exists; on touch they are dead weight at best, scroll jank
  // at worst.
  var finePointer = window.matchMedia
    ? window.matchMedia("(hover: hover) and (pointer: fine)").matches
    : true;

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

    // Touch hardware runs this on the weakest GPU of the day, and the cursor
    // repel can never fire there: fewer particles, slower drift, and none of
    // the O(n²) connection-line drawing.
    var coarse = window.matchMedia
      ? window.matchMedia("(pointer: coarse)").matches
      : false;
    var COUNT = coarse ? 20 : 48;
    var SPEED = coarse ? 0.18 : 0.35;

    var ctx;
    var c = doc.createElement("canvas");
    c.style.cssText = "position:absolute;inset:0;width:100%;height:100%;pointer-events:none";
    canvas.appendChild(c);
    ctx = c.getContext("2d");

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
        vx: (Math.random() - 0.5) * SPEED,
        vy: (Math.random() - 0.5) * SPEED,
        r: Math.random() * 2 + 0.6,
        opacity: Math.random() * 0.3 + 0.1
      };
    }

    resize();
    for (var i = 0; i < COUNT; i++) particles.push(createParticle());

    // The particle + connection loop is the heaviest animation on the page.
    // Stop it entirely while the hero is off-screen or the tab is hidden,
    // instead of burning 60 rAF wakeups per second forever.
    var running = false;
    var intersecting = true;

    function frame() {
      if (!running) return;
      drawStep();
      raf(frame);
    }

    function setRunning(next) {
      if (next && !running) { running = true; raf(frame); }
      else if (!next) { running = false; }
    }

    function drawStep() {
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

        // Draw connections (fine pointers only — the pairing loop is the
        // most expensive part of this canvas and reads as noise on phones).
        if (!coarse) {
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
      }
    }

    if ("IntersectionObserver" in window) {
      var io = new IntersectionObserver(function (entries) {
        intersecting = entries[0].isIntersecting;
        setRunning(intersecting);
      }, { threshold: 0 });
      io.observe(canvas);
    } else {
      setRunning(true);
    }

    on(doc, "visibilitychange", function () {
      if (doc.hidden) setRunning(false);
      else setRunning(intersecting);
    });

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
    if (reduceMotion || !finePointer) return;
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

    function scrollToCard(index) {
      // Scroll only the row; scrollIntoView also moves the whole page.
      track.scrollTo({
        left: cards[index].offsetLeft - cards[0].offsetLeft,
        behavior: reduceMotion ? "auto" : "smooth"
      });
    }

    // Create dots
    cards.forEach(function (_, i) {
      var dot = doc.createElement("button");
      dot.className = "testimonial-dot" + (i === 0 ? " is-active" : "");
      dot.setAttribute("aria-label", "Go to testimonial " + (i + 1));
      dot.setAttribute("type", "button");
      dotsWrap.appendChild(dot);

      on(dot, "click", function () {
        scrollToCard(i);
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

    // Auto-scroll: pauses on hover/keyboard focus, resumes after; direct
    // interaction (drag, wheel) stops it for good. The pause button is the
    // explicit control — looping content must be stoppable on purpose.
    if (!reduceMotion) {
      var autoIdx = 0;
      var autoTimer = null;
      var userTookOver = false;
      var pausedByUser = false;
      var pauseBtn = doc.createElement("button");
      pauseBtn.className = "testimonial-pause";
      pauseBtn.setAttribute("type", "button");
      pauseBtn.setAttribute("aria-pressed", "false");
      pauseBtn.setAttribute("aria-label", "Pause automatic slide advance");
      pauseBtn.innerHTML =
        '<svg class="i i-pause" aria-hidden="true"><use href="#i-pause"></use></svg>' +
        '<svg class="i i-play" aria-hidden="true"><use href="#i-play"></use></svg>';
      dotsWrap.appendChild(pauseBtn);

      function syncPauseBtn() {
        var off = userTookOver || pausedByUser;
        pauseBtn.setAttribute("aria-pressed", String(off));
        pauseBtn.setAttribute("aria-label", off ? "Play automatic slide advance" : "Pause automatic slide advance");
      }
      function startAuto() {
        if (autoTimer || userTookOver || pausedByUser) return;
        autoTimer = window.setInterval(function () {
          autoIdx = (autoIdx + 1) % cards.length;
          scrollToCard(autoIdx);
        }, 6000);
      }
      function stopAuto() {
        if (autoTimer) { window.clearInterval(autoTimer); autoTimer = null; }
      }

      on(pauseBtn, "click", function () {
        pausedByUser = !pausedByUser;
        if (pausedByUser) { stopAuto(); }
        else { userTookOver = false; startAuto(); }
        syncPauseBtn();
      });

      startAuto();
      syncPauseBtn();
      on(track, "pointerdown", function () { userTookOver = true; stopAuto(); syncPauseBtn(); });
      on(track, "wheel", function () { userTookOver = true; stopAuto(); syncPauseBtn(); }, { passive: true });
      on(track, "pointerenter", stopAuto);
      on(track, "pointerleave", startAuto);
      if (dotsWrap) {
        on(dotsWrap, "focusin", stopAuto);
        on(dotsWrap, "focusout", startAuto);
        on(dotsWrap, "pointerenter", stopAuto);
        on(dotsWrap, "pointerleave", startAuto);
      }
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
    if (reduceMotion || !finePointer) return;
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
    if (reduceMotion || !finePointer) return;
    $$(".cta-band").forEach(function (band) {
      band.classList.add("has-shimmer");
    });
  }

  /* ===========================================================
     16. PAUSE INFINITE LOOPS OFF-SCREEN
     =========================================================== */
  function initLoopPause() {
    if (reduceMotion || !("IntersectionObserver" in window)) return;
    var loops = $$(".text-shimmer, .cta-band.has-shimmer");
    if (!loops.length) return;
    var io = new IntersectionObserver(function (entries) {
      entries.forEach(function (entry) {
        entry.target.classList.toggle("is-paused", !entry.isIntersecting);
      });
    }, { threshold: 0 });
    loops.forEach(function (el) { io.observe(el); });
  }

  /* ===========================================================
     17. CARD IMAGE FADE-IN ON LOAD
     =========================================================== */
  function initImageFade() {
    if (reduceMotion) return;
    $$(".listing__media img").forEach(function (img) {
      // Already-decoded images (cached, above the fold) render as normal —
      // only lazy ones that are still in flight get the fade bridge.
      if (img.complete || img.dataset.fadeReady === "1") return;
      img.dataset.fadeReady = "1";
      img.classList.add("img-lazy-fade");
      var settle = function () { img.classList.add("is-loaded"); };
      on(img, "load", settle);
      on(img, "error", settle); // broken images must not stay invisible
    });
  }

  /* ===========================================================
     14. SMOOTH TEXT REVEAL (character-by-character for hero)
     =========================================================== */
  function initTextReveal() {
    if (reduceMotion || !finePointer) return;
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
    initStaggerGroups();
    initTestimonialCarousel();
    initSpringCounters();
    initStepAnimations();
    initQuoteAccents();
    initButtonShine();
    initFabPulse();
    initCtaShimmer();
    initTextReveal();
    initLoopPause();
    initImageFade();
    initMetricGlow();
  });
})();
