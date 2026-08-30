/* =============================================================================
 * FlatLand BD — core + public interactions
 * Vanilla ES2015+. No dependencies, no CDN, no build step.
 * Everything degrades gracefully and honours prefers-reduced-motion.
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
  function ready(fn) {
    if (doc.readyState === "loading") doc.addEventListener("DOMContentLoaded", fn);
    else fn();
  }

  /* ------------------------------------------------------- scroll effects */
  function initScrollChrome() {
    var rail = $("[data-progress]");
    var head = $("[data-masthead]");
    var fab = $("[data-totop]");
    if (!rail && !head && !fab) return;

    var ticking = false;
    function paint() {
      var y = window.pageYOffset || root.scrollTop || 0;
      if (rail) {
        var h = doc.body.scrollHeight - window.innerHeight;
        rail.style.width = (h > 0 ? Math.min(100, (y / h) * 100) : 0) + "%";
      }
      if (head) head.classList.toggle("is-stuck", y > 12);
      if (fab) fab.classList.toggle("is-shown", y > 480);
      ticking = false;
    }
    on(window, "scroll", function () {
      if (!ticking) { ticking = true; window.requestAnimationFrame(paint); }
    }, { passive: true });
    on(window, "resize", paint, { passive: true });
    paint();

    if (fab) on(fab, "click", function () {
      window.scrollTo({ top: 0, behavior: reduceMotion ? "auto" : "smooth" });
    });
  }

  /* ------------------------------------------------------------- reveals */
  function initReveal() {
    var items = $$("[data-reveal]");
    var blueprints = $$(".blueprint");
    var targets = items.concat(blueprints);
    if (!targets.length) return;

    if (reduceMotion || !("IntersectionObserver" in window)) {
      targets.forEach(function (el) { el.classList.add("is-in"); });
      return;
    }

    // Stagger children of a group
    $$("[data-reveal-group]").forEach(function (group) {
      var step = parseInt(group.getAttribute("data-reveal-group"), 10) || 80;
      $$("[data-reveal]", group).forEach(function (child, i) {
        child.style.setProperty("--reveal-delay", (i * step) + "ms");
      });
    });

    var io = new IntersectionObserver(function (entries) {
      entries.forEach(function (entry) {
        if (!entry.isIntersecting) return;
        entry.target.classList.add("is-in");
        io.unobserve(entry.target);
      });
    }, { threshold: 0.12, rootMargin: "0px 0px -8% 0px" });

    targets.forEach(function (el) { io.observe(el); });
  }

  function initSvgDrawLengths() {
    $$(".blueprint").forEach(function (svg) {
      $$("path, line, rect, circle", svg).forEach(function (shape, i) {
        var len = 600;
        try { if (shape.getTotalLength) len = Math.ceil(shape.getTotalLength()); } catch (e) {}
        shape.style.setProperty("--len", len);
        shape.style.setProperty("--d", i);
      });
    });
  }

  /* ---------------------------------------------------------- word split */
  function initWordSplit() {
    $$("[data-words]").forEach(function (el) {
      if (el.dataset.split === "1") return;
      el.dataset.split = "1";
      var html = el.innerHTML;
      // Only split top level text nodes, keep inline markup intact.
      var parts = html.split(/(<[^>]+>)/g);
      var idx = 0;
      var out = parts.map(function (chunk) {
        if (!chunk || chunk.charAt(0) === "<") return chunk;
        return chunk.split(/(\s+)/).map(function (word) {
          if (!word.trim()) return word;
          var span = '<span class="w" style="--i:' + idx + '">' + word + "</span>";
          idx += 1;
          return span;
        }).join("");
      }).join("");
      el.innerHTML = out;
      el.classList.add("reveal-words");
    });
  }

  /* ----------------------------------------------------------- counters */
  function animateCount(el) {
    var target = parseFloat(el.getAttribute("data-count"));
    if (isNaN(target)) return;
    var suffix = el.getAttribute("data-count-suffix") || "";
    var prefix = el.getAttribute("data-count-prefix") || "";
    var dec = parseInt(el.getAttribute("data-count-dec"), 10) || 0;

    function fmt(v) {
      return prefix + v.toLocaleString("en-US", {
        minimumFractionDigits: dec, maximumFractionDigits: dec
      }) + suffix;
    }
    if (reduceMotion) { el.textContent = fmt(target); return; }

    var dur = 1200, t0 = null;
    function frame(ts) {
      if (t0 === null) t0 = ts;
      var p = Math.min(1, (ts - t0) / dur);
      var eased = 1 - Math.pow(1 - p, 3);
      el.textContent = fmt(target * eased);
      if (p < 1) window.requestAnimationFrame(frame);
      else el.textContent = fmt(target);
    }
    window.requestAnimationFrame(frame);
  }

  function initCounters() {
    var els = $$("[data-count]");
    if (!els.length) return;
    if (!("IntersectionObserver" in window)) { els.forEach(animateCount); return; }
    var io = new IntersectionObserver(function (entries) {
      entries.forEach(function (e) {
        if (!e.isIntersecting) return;
        animateCount(e.target);
        io.unobserve(e.target);
      });
    }, { threshold: 0.4 });
    els.forEach(function (el) { io.observe(el); });
  }

  /* ------------------------------------------------------------- bars */
  function initBars() {
    var bars = $$("[data-bar]");
    if (!bars.length) return;
    function fill(el) {
      var pct = Math.max(0, Math.min(100, parseFloat(el.getAttribute("data-bar")) || 0));
      el.style.width = pct + "%";
    }
    if (!("IntersectionObserver" in window) || reduceMotion) { bars.forEach(fill); return; }
    var io = new IntersectionObserver(function (entries) {
      entries.forEach(function (e) {
        if (!e.isIntersecting) return;
        window.setTimeout(function () { fill(e.target); }, 120);
        io.unobserve(e.target);
      });
    }, { threshold: 0.3 });
    bars.forEach(function (el) { io.observe(el); });
  }

  /* -------------------------------------------------- magnetic + tilt */
  function initMagnetic() {
    if (reduceMotion) return;
    $$(".btn").forEach(function (btn) {
      on(btn, "pointermove", function (e) {
        var r = btn.getBoundingClientRect();
        btn.style.setProperty("--mx", ((e.clientX - r.left) / r.width) * 100 + "%");
        btn.style.setProperty("--my", ((e.clientY - r.top) / r.height) * 100 + "%");
      });
    });
  }

  function initTilt() {
    if (reduceMotion) return;
    var strength = 7;
    $$("[data-tilt]").forEach(function (card) {
      var raf = null;
      on(card, "pointermove", function (e) {
        if (raf) return;
        raf = window.requestAnimationFrame(function () {
          var r = card.getBoundingClientRect();
          var px = (e.clientX - r.left) / r.width - 0.5;
          var py = (e.clientY - r.top) / r.height - 0.5;
          card.style.transform =
            "perspective(900px) rotateY(" + (px * strength) + "deg) rotateX(" +
            (-py * strength) + "deg) translateY(-4px)";
          raf = null;
        });
      });
      on(card, "pointerleave", function () { card.style.transform = ""; });
    });
  }

  function initParallax() {
    var els = $$("[data-parallax]");
    if (!els.length || reduceMotion) return;
    var ticking = false;
    function paint() {
      var vh = window.innerHeight;
      els.forEach(function (el) {
        var r = el.getBoundingClientRect();
        if (r.bottom < -200 || r.top > vh + 200) return;
        var speed = parseFloat(el.getAttribute("data-parallax")) || 0.12;
        var mid = r.top + r.height / 2 - vh / 2;
        el.style.transform = "translate3d(0," + (-mid * speed).toFixed(2) + "px,0)";
      });
      ticking = false;
    }
    on(window, "scroll", function () {
      if (!ticking) { ticking = true; window.requestAnimationFrame(paint); }
    }, { passive: true });
    paint();
  }

  /* ------------------------------------------------------------ ticker */
  function initTicker() {
    $$(".ticker").forEach(function (t) {
      var track = $(".ticker__track", t);
      if (!track || track.dataset.cloned === "1") return;
      track.dataset.cloned = "1";
      track.innerHTML = track.innerHTML + track.innerHTML;
    });
  }

  /* -------------------------------------------------- nav / drawer / menu */
  var scrollLocks = {};
  var lockedY = 0;

  function lockScroll(id, lock) {
    if (lock) scrollLocks[id] = true;
    else delete scrollLocks[id];
    var any = Object.keys(scrollLocks).length > 0;
    if (any && !doc.body.classList.contains("is-locked")) {
      lockedY = window.pageYOffset;
      doc.body.style.position = "fixed";
      doc.body.style.top = -lockedY + "px";
      doc.body.style.width = "100%";
      doc.body.classList.add("is-locked");
    } else if (!any && doc.body.classList.contains("is-locked")) {
      doc.body.classList.remove("is-locked");
      doc.body.style.position = "";
      doc.body.style.top = "";
      doc.body.style.width = "";
      window.scrollTo(0, lockedY);
    }
  }
  window.FLB_lockScroll = lockScroll;

  function initDrawer() {
    var burger = $("[data-drawer-toggle]");
    var drawer = $("[data-drawer]");
    if (!burger || !drawer) return;

    function setOpen(open) {
      drawer.classList.toggle("is-open", open);
      burger.setAttribute("aria-expanded", open ? "true" : "false");
      burger.setAttribute("aria-label", open ? "Close menu" : "Open menu");
      lockScroll("drawer", open);
      $$("[data-burger-open]", burger).forEach(function (n) { n.style.display = open ? "none" : ""; });
      $$("[data-burger-close]", burger).forEach(function (n) { n.style.display = open ? "" : "none"; });
    }
    setOpen(false);
    on(burger, "click", function () { setOpen(!drawer.classList.contains("is-open")); });
    $$("a", drawer).forEach(function (a) { on(a, "click", function () { setOpen(false); }); });
    on(window, "keydown", function (e) { if (e.key === "Escape") setOpen(false); });
    on(window, "resize", function () { if (window.innerWidth > 1000) setOpen(false); });
  }

  function initMenus() {
    $$("[data-menu]").forEach(function (menu) {
      var btn = $("[data-menu-btn]", menu);
      if (!btn) return;
      function close() { menu.classList.remove("is-open"); btn.setAttribute("aria-expanded", "false"); }
      on(btn, "click", function (e) {
        e.stopPropagation();
        var open = !menu.classList.contains("is-open");
        $$("[data-menu].is-open").forEach(function (m) { m.classList.remove("is-open"); });
        menu.classList.toggle("is-open", open);
        btn.setAttribute("aria-expanded", open ? "true" : "false");
      });
      on(doc, "click", function (e) { if (!menu.contains(e.target)) close(); });
      on(doc, "keydown", function (e) { if (e.key === "Escape") close(); });
    });
  }

  /* ------------------------------------------------------------ toasts */
  var toastHost = null;
  function toastLayer() {
    if (toastHost) return toastHost;
    toastHost = $("[data-toasts]");
    if (!toastHost) {
      toastHost = doc.createElement("div");
      toastHost.className = "toasts";
      toastHost.setAttribute("data-toasts", "");
      toastHost.setAttribute("role", "status");
      toastHost.setAttribute("aria-live", "polite");
      doc.body.appendChild(toastHost);
    }
    return toastHost;
  }

  var TOAST_ICON = {
    success: "check-circle", danger: "alert-circle", error: "alert-circle",
    warning: "alert-triangle", info: "info", message: "info"
  };

  function dismissToast(el) {
    el.classList.add("is-out");
    window.setTimeout(function () { if (el.parentNode) el.parentNode.removeChild(el); }, 300);
  }

  function toast(message, type, ttl) {
    var kind = type || "info";
    var el = doc.createElement("div");
    el.className = "toast toast--" + kind;
    el.innerHTML =
      '<span class="toast__icon"><svg class="i" aria-hidden="true"><use href="#i-' +
      (TOAST_ICON[kind] || "info") + '"></use></svg></span>' +
      '<p class="toast__msg"></p>' +
      '<button class="toast__x" type="button" aria-label="Dismiss">' +
      '<svg class="i" aria-hidden="true"><use href="#i-x"></use></svg></button>';
    $(".toast__msg", el).textContent = message;
    on($(".toast__x", el), "click", function () { dismissToast(el); });
    toastLayer().appendChild(el);
    window.setTimeout(function () { dismissToast(el); }, ttl || 5200);
    return el;
  }
  window.FLB_toast = toast;

  function initFlashes() {
    var box = $("[data-flashes]");
    if (!box) return;
    var items = [];
    try { items = JSON.parse(box.textContent || "[]"); } catch (e) { items = []; }
    items.forEach(function (item, i) {
      window.setTimeout(function () { toast(item.message, item.category); }, i * 220);
    });
  }

  /* --------------------------------------------------------- lightbox */
  var lb = { el: null, img: null, count: null, items: [], index: 0 };

  function buildLightbox() {
    if (lb.el) return;
    var el = doc.createElement("div");
    el.className = "lightbox";
    el.setAttribute("role", "dialog");
    el.setAttribute("aria-modal", "true");
    el.setAttribute("aria-label", "Image viewer");
    el.innerHTML =
      '<button class="lightbox__close" type="button" aria-label="Close viewer">' +
      '<svg class="i" aria-hidden="true"><use href="#i-x"></use></svg></button>' +
      '<button class="lightbox__nav lightbox__nav--prev" type="button" aria-label="Previous image">' +
      '<svg class="i" aria-hidden="true"><use href="#i-chevron-left"></use></svg></button>' +
      '<img class="lightbox__img" alt="">' +
      '<button class="lightbox__nav lightbox__nav--next" type="button" aria-label="Next image">' +
      '<svg class="i" aria-hidden="true"><use href="#i-chevron-right"></use></svg></button>' +
      '<p class="lightbox__count"></p>';
    doc.body.appendChild(el);
    lb.el = el;
    lb.img = $(".lightbox__img", el);
    lb.count = $(".lightbox__count", el);
    on($(".lightbox__close", el), "click", closeLightbox);
    on($(".lightbox__nav--prev", el), "click", function () { step(-1); });
    on($(".lightbox__nav--next", el), "click", function () { step(1); });
    on(el, "click", function (e) { if (e.target === el) closeLightbox(); });
    on(doc, "keydown", function (e) {
      if (!el.classList.contains("is-open")) return;
      if (e.key === "Escape") closeLightbox();
      if (e.key === "ArrowLeft") step(-1);
      if (e.key === "ArrowRight") step(1);
    });
  }

  function paintLightbox() {
    var item = lb.items[lb.index];
    if (!item) return;
    lb.img.src = item.src;
    lb.img.alt = item.alt || "Enlarged image";
    var many = lb.items.length > 1;
    lb.count.textContent = many ? (lb.index + 1) + " / " + lb.items.length : "";
    lb.count.style.display = many ? "" : "none";
    $$(".lightbox__nav", lb.el).forEach(function (n) { n.style.display = many ? "" : "none"; });
  }

  function step(dir) {
    if (!lb.items.length) return;
    lb.index = (lb.index + dir + lb.items.length) % lb.items.length;
    paintLightbox();
  }

  function openLightbox(items, index) {
    buildLightbox();
    lb.items = items;
    lb.index = index || 0;
    paintLightbox();
    lb.el.classList.add("is-open");
    lockScroll("lightbox", true);
    $(".lightbox__close", lb.el).focus();
  }

  function closeLightbox() {
    if (!lb.el) return;
    lb.el.classList.remove("is-open");
    lockScroll("lightbox", false);
  }
  window.FLB_lightbox = openLightbox;

  function initLightboxTriggers() {
    on(doc, "click", function (e) {
      var trigger = e.target.closest ? e.target.closest("[data-zoom]") : null;
      if (!trigger) return;
      e.preventDefault();
      var groupName = trigger.getAttribute("data-zoom-group");
      var pool = groupName
        ? $$('[data-zoom][data-zoom-group="' + groupName + '"]')
        : [trigger];
      var items = pool.map(function (node) {
        return {
          src: node.getAttribute("data-zoom-src") || node.getAttribute("src") ||
               (node.querySelector("img") ? node.querySelector("img").src : ""),
          alt: node.getAttribute("alt") ||
               (node.querySelector("img") ? node.querySelector("img").alt : "")
        };
      }).filter(function (i) { return i.src; });
      openLightbox(items, pool.indexOf(trigger));
    });
  }

  /* ---------------------------------------------------------- gallery */
  function initGallery() {
    $$("[data-gallery]").forEach(function (gal) {
      var stage = $("[data-gallery-stage]", gal);
      var thumbs = $$("[data-gallery-thumb]", gal);
      if (!stage || !thumbs.length) return;

      function select(i) {
        var t = thumbs[i];
        if (!t) return;
        var src = t.getAttribute("data-src");
        var srcset = t.getAttribute("data-srcset");
        stage.style.opacity = "0";
        window.setTimeout(function () {
          stage.src = src;
          if (srcset) stage.srcset = srcset;
          stage.setAttribute("data-zoom-src", src);
          stage.style.opacity = "1";
        }, reduceMotion ? 0 : 130);
        thumbs.forEach(function (o, oi) { o.classList.toggle("is-active", oi === i); });
      }
      thumbs.forEach(function (t, i) {
        on(t, "click", function () { select(i); });
      });
      select(0);
    });
  }

  /* ------------------------------------------------------- file inputs */
  function initUploads() {
    $$(".dropzone").forEach(function (zone) {
      var input = $('input[type="file"]', zone);
      if (!input || zone.dataset.ready === "1") return;
      zone.dataset.ready = "1";
      var namesSel = input.getAttribute("data-file-names");
      var thumbsSel = input.getAttribute("data-file-thumbs");
      var names = namesSel ? doc.querySelector(namesSel) : null;
      var thumbs = thumbsSel ? doc.querySelector(thumbsSel) : null;
      var maxThumbs = parseInt(zone.getAttribute("data-max-thumbs"), 10) || 8;

      function paint() {
        var files = Array.prototype.slice.call(input.files || [])
          .filter(function (f) { return /^image\//.test(f.type); });
        zone.classList.toggle("has-file", files.length > 0);
        if (names) {
          names.textContent = files.length
            ? files.length + (files.length === 1 ? " image ready: " : " images ready: ") +
              files.map(function (f) { return f.name; }).slice(0, 3).join(", ") +
              (files.length > 3 ? " +" + (files.length - 3) + " more" : "")
            : "No image selected yet";
        }
        if (!thumbs) return;
        thumbs.innerHTML = "";
        thumbs.hidden = files.length === 0;
        files.slice(0, maxThumbs).forEach(function (file) {
          var url = URL.createObjectURL(file);
          var tile = doc.createElement("div");
          tile.className = "thumbs__tile";
          var img = doc.createElement("img");
          img.src = url;
          img.alt = file.name;
          img.loading = "lazy";
          img.onload = function () { URL.revokeObjectURL(url); };
          tile.appendChild(img);
          thumbs.appendChild(tile);
        });
      }

      on(input, "change", paint);
      ["dragenter", "dragover"].forEach(function (ev) {
        on(zone, ev, function (e) { e.preventDefault(); zone.classList.add("is-dragging"); });
      });
      ["dragleave", "drop"].forEach(function (ev) {
        on(zone, ev, function () { zone.classList.remove("is-dragging"); });
      });
      on(zone, "drop", function (e) {
        e.preventDefault();
        if (!e.dataTransfer || !e.dataTransfer.files.length) return;
        try {
          input.files = e.dataTransfer.files;
          paint();
        } catch (err) { /* older browsers */ }
      });
    });
  }

  /* ------------------------------------------------------- form extras */
  function initFormChrome() {
    // Submit veil
    var veil = $("[data-veil]");
    $$("form").forEach(function (form) {
      on(form, "submit", function () {
        if (form.hasAttribute("data-no-veil")) return;
        var btn = form.querySelector('button[type="submit"], .btn[type="submit"]');
        if (btn) { btn.setAttribute("aria-disabled", "true"); }
        if (veil) veil.classList.add("is-on");
      });
    });
    on(window, "pageshow", function () { if (veil) veil.classList.remove("is-on"); });

    // Password reveal
    $$("[data-pw-toggle]").forEach(function (btn) {
      on(btn, "click", function () {
        var input = $("input", btn.parentNode);
        if (!input) return;
        var show = input.type === "password";
        input.type = show ? "text" : "password";
        btn.setAttribute("aria-label", show ? "Hide password" : "Show password");
        $$("use", btn).forEach(function (u) {
          u.setAttribute("href", show ? "#i-eye-off" : "#i-eye");
        });
      });
    });

    // Password strength
    $$("[data-strength-for]").forEach(function (meter) {
      var input = doc.getElementById(meter.getAttribute("data-strength-for"));
      if (!input) return;
      var segs = $$(".strength__seg", meter);
      var label = $("[data-strength-label]", meter);
      on(input, "input", function () {
        var v = input.value || "";
        var score = 0;
        if (v.length >= 8) score += 1;
        if (v.length >= 12) score += 1;
        if (/[A-Z]/.test(v) && /[a-z]/.test(v)) score += 1;
        if (/\d/.test(v) && /[^\w\s]/.test(v)) score += 1;
        segs.forEach(function (s, i) {
          s.classList.remove("is-on", "is-weak", "is-mid");
          if (i < score) s.classList.add(score <= 1 ? "is-weak" : score === 2 ? "is-mid" : "is-on");
        });
        if (label) {
          label.textContent = !v ? "Use 8+ characters"
            : score <= 1 ? "Weak password"
            : score === 2 ? "Getting better"
            : score === 3 ? "Strong password" : "Excellent password";
        }
      });
    });

    // Auto submit on select change (filter forms)
    $$("[data-autosubmit]").forEach(function (el) {
      on(el, "change", function () { if (el.form) el.form.submit(); });
    });

    // Character counters
    $$("[data-counter-for]").forEach(function (out) {
      var input = doc.getElementById(out.getAttribute("data-counter-for"));
      if (!input) return;
      var max = input.getAttribute("maxlength");
      function paint() {
        out.textContent = (input.value || "").length + (max ? " / " + max : "") + " characters";
      }
      on(input, "input", paint);
      paint();
    });
  }

  /* ---------------------------------------------------------- wizard */
  function initWizard() {
    $$("[data-wizard]").forEach(function (wiz) {
      var steps = $$("[data-wizard-step]", wiz);
      var pips = $$("[data-wizard-pip]", wiz);
      if (steps.length < 2) return;
      var bar = $("[data-wizard-bar]", wiz);
      var at = 0;

      function paintBar() {
        if (!bar) return;
        bar.style.transform = "scaleX(" + (steps.length > 1 ? at / (steps.length - 1) : 1) + ")";
      }

      function paint() {
        steps.forEach(function (s, i) { s.classList.toggle("is-current", i === at); });
        pips.forEach(function (p, i) {
          p.classList.toggle("is-active", i === at);
          p.classList.toggle("is-done", i < at);
        });
        paintBar();
        var top = wiz.getBoundingClientRect().top + window.pageYOffset - 110;
        window.scrollTo({ top: top, behavior: reduceMotion ? "auto" : "smooth" });
      }

      function valid(index) {
        var ok = true;
        $$("input, select, textarea", steps[index]).forEach(function (f) {
          if (f.disabled || !f.checkValidity) return;
          if (!f.checkValidity()) {
            ok = false;
            if (f.reportValidity) f.reportValidity();
          }
        });
        return ok;
      }

      $$("[data-wizard-next]", wiz).forEach(function (btn) {
        on(btn, "click", function () {
          if (!valid(at)) return;
          at = Math.min(steps.length - 1, at + 1);
          paint();
        });
      });
      $$("[data-wizard-prev]", wiz).forEach(function (btn) {
        on(btn, "click", function () { at = Math.max(0, at - 1); paint(); });
      });
      pips.forEach(function (p, i) {
        on(p, "click", function () { if (i <= at || valid(at)) { at = i; paint(); } });
      });
      steps.forEach(function (s, i) { s.classList.toggle("is-current", i === 0); });
      pips.forEach(function (p, i) { p.classList.toggle("is-active", i === 0); });
      paintBar();
    });

    // Listing type switch (flat vs interior blocks)
    $$("[data-type-switch]").forEach(function (radio) {
      on(radio, "change", function () {
        var value = radio.value;
        $$("[data-type-block]").forEach(function (block) {
          var show = block.getAttribute("data-type-block") === value;
          block.hidden = !show;
          $$("input, select, textarea", block).forEach(function (f) {
            if (f.hasAttribute("data-required-when-visible")) f.required = show;
          });
        });
      });
      if (radio.checked) radio.dispatchEvent(new Event("change"));
    });
  }

  /* --------------------------------------------------------- clipboard */
  function initCopy() {
    on(doc, "click", function (e) {
      var btn = e.target.closest ? e.target.closest("[data-copy]") : null;
      if (!btn) return;
      var text = btn.getAttribute("data-copy");
      if (!text) {
        var src = btn.parentNode.querySelector("[data-copy-src]");
        text = src ? (src.textContent || "").trim() : "";
      }
      if (!text) return;
      var done = function () { toast("Copied to clipboard", "success", 2200); };
      if (navigator.clipboard && navigator.clipboard.writeText) {
        navigator.clipboard.writeText(text).then(done, function () {});
      } else {
        var ta = doc.createElement("textarea");
        ta.value = text;
        doc.body.appendChild(ta);
        ta.select();
        try { doc.execCommand("copy"); done(); } catch (err) {}
        doc.body.removeChild(ta);
      }
    });
  }

  /* -------------------------------------------------- smooth anchor scroll */
  function initSmoothAnchors() {
    on(doc, "click", function (e) {
      var a = e.target.closest ? e.target.closest('a[href^="#"]') : null;
      if (!a) return;
      var href = a.getAttribute("href");
      if (!href || href === "#" || href.length < 2) return;
      var target = doc.querySelector(href);
      if (!target) return;
      e.preventDefault();
      var head = $("[data-masthead]");
      var offset = (head ? head.offsetHeight : 72) + 16;
      var top = target.getBoundingClientRect().top + window.pageYOffset - offset;
      window.scrollTo({ top: Math.max(0, top), behavior: reduceMotion ? "auto" : "smooth" });
      if (window.history && window.history.pushState) window.history.pushState(null, null, href);
    });
  }

  /* ------------------------------------------------- maintenance popup */
  function initMaintenanceBanner() {
    var pop = $("[data-maint-pop]");
    if (!pop) return;
    var STORAGE_KEY = "flb_maint_seen";

    try {
      if (sessionStorage.getItem(STORAGE_KEY) === "1") return;
    } catch (e) {}

    function dismiss() {
      pop.classList.remove("is-on");
      try { sessionStorage.setItem(STORAGE_KEY, "1"); } catch (e) {}
    }

    // Popup appears shortly after load, then closes itself.
    window.setTimeout(function () { pop.classList.add("is-on"); }, reduceMotion ? 0 : 600);
    window.setTimeout(dismiss, 9000);

    $$("[data-maint-dismiss]", pop).forEach(function (btn) {
      on(btn, "click", dismiss);
    });
    var backdrop = $("[data-maint-backdrop]", pop);
    if (backdrop) on(backdrop, "click", dismiss);
    on(doc, "keydown", function (e) {
      if (e.key === "Escape" && pop.classList.contains("is-on")) dismiss();
    });
  }

  /* --------------------------------------------------- username field */
  function initUsernameField() {
    var input = $("[data-username-check]");
    if (!input) return;
    var wrap = input.closest("[data-uname]");
    var msg = $("[data-uname-msg]");
    var ideas = $("[data-uname-ideas]");
    var seed = $("[data-username-seed]");
    var endpoint = input.getAttribute("data-username-check");
    var defaultMsg = msg ? msg.textContent : "";
    var timer = null;
    var token = 0;
    var touched = (input.value || "").length > 0;

    function clean(value) {
      return String(value || "")
        .toLowerCase()
        .replace(/[\s.\-]+/g, "_")
        .replace(/[^a-z0-9_]/g, "")
        .replace(/_{2,}/g, "_")
        .slice(0, 20);
    }

    function setState(state, text) {
      if (wrap) {
        wrap.classList.toggle("is-checking", state === "checking");
        wrap.classList.toggle("is-ok", state === "ok");
        wrap.classList.toggle("is-bad", state === "bad");
      }
      if (msg) {
        msg.textContent = text || defaultMsg;
        msg.classList.toggle("is-ok", state === "ok");
        msg.classList.toggle("is-bad", state === "bad");
      }
    }

    function showIdeas(list) {
      if (!ideas) return;
      ideas.innerHTML = "";
      if (!list || !list.length) { ideas.hidden = true; return; }
      var label = doc.createElement("b");
      label.textContent = "Free right now:";
      ideas.appendChild(label);
      list.forEach(function (name, i) {
        var btn = doc.createElement("button");
        btn.type = "button";
        btn.className = "uname__idea";
        btn.textContent = "@" + name;
        btn.style.animationDelay = (i * 60) + "ms";
        on(btn, "click", function () {
          input.value = name;
          touched = true;
          ideas.hidden = true;
          check();
          input.focus();
        });
        ideas.appendChild(btn);
      });
      ideas.hidden = false;
    }

    function check() {
      var value = clean(input.value);
      if (input.value !== value) input.value = value;
      showIdeas(null);
      if (!value) { setState("", defaultMsg); return; }
      if (value.length < 3) { setState("bad", "At least 3 characters."); return; }
      if (/^[0-9_]/.test(value)) { setState("bad", "Start your username with a letter."); return; }
      setState("checking", "Checking availability\u2026");
      var mine = ++token;
      window.fetch(endpoint + "?u=" + encodeURIComponent(value), { credentials: "same-origin" })
        .then(function (r) { return r.json(); })
        .then(function (data) {
          if (mine !== token) return;
          if (data.status === "available") {
            setState("ok", data.message);
          } else {
            setState("bad", data.message);
            showIdeas(data.suggestions);
          }
        })
        .catch(function () { if (mine === token) setState("", defaultMsg); });
    }

    on(input, "input", function () {
      touched = true;
      window.clearTimeout(timer);
      timer = window.setTimeout(check, 380);
    });
    on(input, "blur", function () {
      window.clearTimeout(timer);
      if (input.value) check();
    });

    // Offer a username built from the name above, until they type their own.
    if (seed) {
      on(seed, "input", function () {
        if (touched) return;
        input.value = clean(seed.value);
      });
      on(seed, "blur", function () {
        if (touched || !input.value) return;
        check();
      });
    }

    // Never submit a username we already know is taken.
    if (input.form) {
      on(input.form, "submit", function (e) {
        if (!wrap || !wrap.classList.contains("is-bad")) return;
        e.preventDefault();
        var veil = $("[data-veil]");
        if (veil) veil.classList.remove("is-on");
        input.focus();
        if (input.scrollIntoView) {
          input.scrollIntoView({ block: "center", behavior: reduceMotion ? "auto" : "smooth" });
        }
      });
    }

    if (input.value) check();
  }

  /* ------------------------------------------------ Bangladeshi mobile */
  function initBdPhone() {
    $$("[data-bd-phone]").forEach(function (input) {
      var wrap = input.closest("[data-phonebd]");
      var count = $("[data-phone-count]", wrap || doc);
      var dots = $("[data-phone-dots]");
      var msg = $("[data-phone-msg]");
      var defaultMsg = msg ? msg.textContent : "";

      if (dots && !dots.children.length) {
        for (var d = 0; d < 11; d++) dots.appendChild(doc.createElement("i"));
      }
      var cells = dots ? $$("i", dots) : [];

      function paint() {
        var digits = (input.value || "").replace(/\D/g, "");
        // Paste of +8801XXXXXXXXX or 8801XXXXXXXXX becomes 01XXXXXXXXX.
        if (digits.length > 11 && digits.indexOf("880") === 0) digits = "0" + digits.slice(3);
        digits = digits.slice(0, 11);
        if (input.value !== digits) input.value = digits;

        var n = digits.length;
        var valid = /^01[3-9]\d{8}$/.test(digits);
        var state = "";
        var text = defaultMsg;

        if (!n) { text = defaultMsg; }
        else if (digits.charAt(0) !== "0") { state = "bad"; text = "Bangladeshi numbers start with 0."; }
        else if (n >= 2 && digits.charAt(1) !== "1") { state = "bad"; text = "Mobile numbers start with 01."; }
        else if (n >= 3 && !/^01[3-9]/.test(digits)) { state = "bad"; text = "Third digit must be 3 to 9 (013\u2013019)."; }
        else if (valid) { state = "ok"; text = "Valid 11-digit Bangladeshi number."; }
        else { text = (11 - n) + " more digit" + ((11 - n) === 1 ? "" : "s") + " to go."; }

        if (count) count.textContent = n + "/11";
        cells.forEach(function (c, i) { c.classList.toggle("is-on", i < n); });
        if (dots) dots.classList.toggle("is-ok", valid);
        if (wrap) {
          wrap.classList.toggle("is-ok", state === "ok");
          wrap.classList.toggle("is-bad", state === "bad");
        }
        if (msg) {
          msg.textContent = text;
          msg.classList.toggle("is-ok", state === "ok");
          msg.classList.toggle("is-bad", state === "bad");
        }
      }

      on(input, "input", paint);
      on(input, "paste", function () { window.setTimeout(paint, 0); });
      paint();
    });
  }

  /* ------------------------------------------------- login identifier */
  function initLoginIdentifier() {
    var input = $("[data-login-id]");
    if (!input) return;
    var use = $("[data-login-ic] use");
    if (!use) return;
    on(input, "input", function () {
      var v = (input.value || "").trim();
      var icon = "#i-user";
      if (v.indexOf("@") > -1) icon = "#i-mail";
      else if (/^[0-9+]/.test(v)) icon = "#i-phone";
      use.setAttribute("href", icon);
    });
  }

  /* ------------------------------------------------------------- boot */
  ready(function () {
    initScrollChrome();
    initWordSplit();
    initSvgDrawLengths();
    initReveal();
    initCounters();
    initBars();
    initTicker();
    initDrawer();
    initMenus();
    initFlashes();
    initLightboxTriggers();
    initGallery();
    initUploads();
    initFormChrome();
    initWizard();
    initCopy();
    initMagnetic();
    initTilt();
    initParallax();
    initSmoothAnchors();
    initMaintenanceBanner();
    initUsernameField();
    initBdPhone();
    initLoginIdentifier();
    doc.body.classList.add("is-booted");
  });
})();
