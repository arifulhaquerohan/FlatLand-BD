/* =============================================================================
 * FlatLand BD — Operations Console
 * Loaded after app.js (which provides theme, toasts, lightbox, counters, copy).
 * ========================================================================== */
(function () {
  "use strict";

  var doc = document;
  var reduceMotion = window.matchMedia
    ? window.matchMedia("(prefers-reduced-motion: reduce)").matches : false;

  function $(s, c) { return (c || doc).querySelector(s); }
  function $$(s, c) { return Array.prototype.slice.call((c || doc).querySelectorAll(s)); }
  function on(el, ev, fn, o) { if (el) el.addEventListener(ev, fn, o || false); }
  function toast(m, t) { if (window.FLB_toast) window.FLB_toast(m, t); }
  function csrf() {
    var el = $('input[name="csrf_token"]') || $('meta[name="csrf-token"]');
    if (!el) return "";
    return el.value || el.getAttribute("content") || "";
  }

  /* ------------------------------------------------------------ side rail */
  function initRail() {
    var rail = $("[data-rail]");
    var toggle = $("[data-rail-toggle]");
    var scrim = $("[data-rail-scrim]");
    if (!rail || !toggle) return;

    function set(open) {
      rail.classList.toggle("is-open", open);
      if (scrim) scrim.classList.toggle("is-on", open);
      toggle.setAttribute("aria-expanded", open ? "true" : "false");
      if (window.FLB_lockScroll) window.FLB_lockScroll("rail", open);
    }
    on(toggle, "click", function () { set(!rail.classList.contains("is-open")); });
    on(scrim, "click", function () { set(false); });
    on(doc, "keydown", function (e) { if (e.key === "Escape") set(false); });
    on(window, "resize", function () { if (window.innerWidth > 1080) set(false); });
  }

  /* ------------------------------------------------------- command palette */
  function initPalette() {
    var host = $("[data-palette]");
    if (!host) return;
    var input = $("[data-palette-input]", host);
    var list = $("[data-palette-list]", host);
    var data = [];
    var raw = $("[data-palette-data]");
    if (raw) { try { data = JSON.parse(raw.textContent || "[]"); } catch (e) { data = []; } }
    var cursor = 0;
    var shown = data.slice();

    function render() {
      if (!shown.length) {
        list.innerHTML = '<p class="palette__empty">No matching command</p>';
        return;
      }
      list.innerHTML = shown.map(function (item, i) {
        return '<button class="palette__item' + (i === cursor ? " is-cursor" : "") +
          '" type="button" data-idx="' + i + '">' +
          '<svg class="i" aria-hidden="true"><use href="#i-' + (item.icon || "arrow-right") + '"></use></svg>' +
          "<span>" + item.label + "</span>" +
          (item.hint ? "<small>" + item.hint + "</small>" : "") +
          "</button>";
      }).join("");
      $$(".palette__item", list).forEach(function (btn) {
        on(btn, "click", function () { go(shown[parseInt(btn.getAttribute("data-idx"), 10)]); });
      });
    }

    function go(item) {
      if (!item) return;
      close();
      if (item.url) window.location.href = item.url;
    }

    function filter(q) {
      var needle = (q || "").toLowerCase().trim();
      shown = !needle ? data.slice() : data.filter(function (i) {
        return (i.label + " " + (i.keywords || "") + " " + (i.hint || "")).toLowerCase().indexOf(needle) > -1;
      });
      cursor = 0;
      render();
    }

    function open() {
      host.classList.add("is-open");
      input.value = "";
      filter("");
      window.setTimeout(function () { input.focus(); }, 40);
      if (window.FLB_lockScroll) window.FLB_lockScroll("palette", true);
    }
    function close() {
      host.classList.remove("is-open");
      if (window.FLB_lockScroll) window.FLB_lockScroll("palette", false);
    }

    on(input, "input", function () { filter(input.value); });
    on(input, "keydown", function (e) {
      if (e.key === "ArrowDown") { e.preventDefault(); cursor = Math.min(shown.length - 1, cursor + 1); render(); }
      if (e.key === "ArrowUp") { e.preventDefault(); cursor = Math.max(0, cursor - 1); render(); }
      if (e.key === "Enter") { e.preventDefault(); go(shown[cursor]); }
    });
    on(host, "click", function (e) { if (e.target === host) close(); });
    $$("[data-palette-open]").forEach(function (btn) { on(btn, "click", open); });
    on(doc, "keydown", function (e) {
      var mod = e.metaKey || e.ctrlKey;
      if (mod && (e.key === "k" || e.key === "K")) { e.preventDefault(); open(); return; }
      if (e.key === "Escape") close();
      if (e.key === "/" && !/^(INPUT|TEXTAREA|SELECT)$/.test(doc.activeElement.tagName)) {
        var search = $("[data-table-filter]") || $('input[name="q"]');
        if (search) { e.preventDefault(); search.focus(); search.select(); }
      }
    });
    render();
  }

  /* --------------------------------------------------------- row selection */
  function initSelection() {
    $$("[data-select-scope]").forEach(function (scope) {
      var boxes = $$("[data-row-check]", scope);
      var master = $("[data-check-all]", scope);
      var bar = $("[data-bulkbar]", scope) || $("[data-bulkbar]");
      if (!boxes.length) return;
      var last = null;

      function selected() { return boxes.filter(function (b) { return b.checked; }); }

      function paint() {
        var picked = selected();
        boxes.forEach(function (b) {
          var row = b.closest("tr") || b.closest("[data-row]");
          if (row) row.classList.toggle("is-selected", b.checked);
        });
        if (master) {
          master.checked = picked.length === boxes.length && boxes.length > 0;
          master.indeterminate = picked.length > 0 && picked.length < boxes.length;
        }
        if (bar) {
          bar.classList.toggle("is-up", picked.length > 0);
          var n = $("[data-bulk-count]", bar);
          if (n) n.textContent = picked.length;
          $$("[data-bulk-ids]", bar).forEach(function (field) {
            var ids = picked.map(function (b) { return b.value; });
            if (field.tagName === "INPUT") { field.value = ids.join(","); return; }
            var key = field.getAttribute("data-bulk-ids") || "ids";
            field.textContent = "";
            ids.forEach(function (v) {
              var hidden = doc.createElement("input");
              hidden.type = "hidden";
              hidden.name = key;
              hidden.value = v;
              field.appendChild(hidden);
            });
          });
        }
      }

      boxes.forEach(function (b, i) {
        on(b, "click", function (e) {
          if (e.shiftKey && last !== null) {
            var from = Math.min(last, i), to = Math.max(last, i);
            for (var k = from; k <= to; k++) boxes[k].checked = b.checked;
          }
          last = i;
          paint();
        });
      });
      if (master) on(master, "change", function () {
        boxes.forEach(function (b) { b.checked = master.checked; });
        paint();
      });
      $$("[data-bulk-clear]").forEach(function (btn) {
        on(btn, "click", function () {
          boxes.forEach(function (b) { b.checked = false; });
          paint();
        });
      });
      paint();
    });
  }

  /* ------------------------------------------------------- confirm dialogs */
  function initConfirm() {
    var host = $("[data-confirm-dialog]");
    if (!host) return;
    var titleEl = $("[data-confirm-title]", host);
    var bodyEl = $("[data-confirm-body]", host);
    var okBtn = $("[data-confirm-ok]", host);
    var pending = null;

    function close() { host.classList.remove("is-open"); pending = null; }

    on(doc, "click", function (e) {
      var trigger = e.target.closest ? e.target.closest("[data-confirm]") : null;
      if (!trigger) return;
      e.preventDefault();
      pending = trigger;
      if (titleEl) titleEl.textContent = trigger.getAttribute("data-confirm-title") || "Please confirm";
      if (bodyEl) bodyEl.textContent = trigger.getAttribute("data-confirm") || "This action cannot be undone.";
      if (okBtn) okBtn.textContent = trigger.getAttribute("data-confirm-ok-label") || "Yes, continue";
      host.classList.add("is-open");
      if (okBtn) okBtn.focus();
    });

    on(okBtn, "click", function () {
      if (!pending) return;
      var target = pending;
      pending = null;
      host.classList.remove("is-open");
      if (target.tagName === "FORM") { target.submit(); return; }
      var form = target.closest("form");
      if (target.tagName === "BUTTON" && form) {
        if (target.name) {
          var carry = doc.createElement("input");
          carry.type = "hidden";
          carry.name = target.name;
          carry.value = target.value || "";
          form.appendChild(carry);
        }
        form.submit();
        return;
      }
      if (target.href) { window.location.href = target.href; return; }
      if (form) form.submit();
    });
    $$("[data-confirm-cancel]", host).forEach(function (b) { on(b, "click", close); });
    on(host, "click", function (e) { if (e.target === host) close(); });
    on(doc, "keydown", function (e) { if (e.key === "Escape") close(); });
  }

  /* ---------------------------------------------------- client side filter */
  function initTableFilter() {
    $$("[data-table-filter]").forEach(function (input) {
      var scopeSel = input.getAttribute("data-table-filter");
      var scope = scopeSel ? $(scopeSel) : null;
      if (!scope) return;
      var rows = $$("tbody tr", scope);
      var note = $("[data-filter-note]");
      on(input, "input", function () {
        var q = input.value.toLowerCase().trim();
        var hits = 0;
        rows.forEach(function (row) {
          var match = !q || row.textContent.toLowerCase().indexOf(q) > -1;
          row.hidden = !match;
          if (match) hits++;
        });
        if (note) note.textContent = q ? hits + " of " + rows.length + " rows match" : "";
      });
    });
  }

  /* --------------------------------------------------------------- charts */
  function initSpark() {
    $$("[data-spark]").forEach(function (svg) {
      var values = [];
      try { values = JSON.parse(svg.getAttribute("data-spark")); } catch (e) { return; }
      if (!values.length) return;
      var w = 300, h = 76, pad = 6;
      var max = Math.max.apply(null, values) || 1;
      var min = Math.min.apply(null, values);
      var span = Math.max(1, max - min);
      var pts = values.map(function (v, i) {
        var x = pad + (i * (w - pad * 2)) / Math.max(1, values.length - 1);
        var y = h - pad - ((v - min) / span) * (h - pad * 2);
        return [x, y];
      });
      var line = pts.map(function (p, i) {
        return (i ? "L" : "M") + p[0].toFixed(1) + " " + p[1].toFixed(1);
      }).join(" ");
      var area = line + " L" + pts[pts.length - 1][0].toFixed(1) + " " + h + " L" + pts[0][0].toFixed(1) + " " + h + " Z";
      svg.setAttribute("viewBox", "0 0 " + w + " " + h);
      svg.setAttribute("preserveAspectRatio", "none");
      svg.innerHTML =
        '<defs><linearGradient id="sparkGrad" x1="0" y1="0" x2="0" y2="1">' +
        '<stop offset="0%" stop-color="#d57b4c" stop-opacity=".45"/>' +
        '<stop offset="100%" stop-color="#d57b4c" stop-opacity="0"/></linearGradient></defs>' +
        '<path class="spark__area" d="' + area + '"/>' +
        '<path class="spark__line" d="' + line + '"/>' +
        '<circle class="spark__dot" cx="' + pts[pts.length - 1][0].toFixed(1) +
        '" cy="' + pts[pts.length - 1][1].toFixed(1) + '" r="3.4"/>';

      var path = $(".spark__line", svg);
      if (path && !reduceMotion && path.getTotalLength) {
        var len = path.getTotalLength();
        path.style.strokeDasharray = len;
        path.style.strokeDashoffset = len;
        path.getBoundingClientRect();
        path.style.transition = "stroke-dashoffset 1.4s cubic-bezier(.16,1,.3,1)";
        path.style.strokeDashoffset = "0";
      }
    });
  }

  function initBarChart() {
    var segs = $$("[data-seg-height]");
    if (!segs.length) return;
    function fill() {
      segs.forEach(function (s, i) {
        s.style.setProperty("--bd", (i * 25) + "ms");
        s.style.height = s.getAttribute("data-seg-height") + "%";
      });
    }
    if (reduceMotion) { fill(); return; }
    window.setTimeout(fill, 140);
  }

  function initRings() {
    $$("[data-ring]").forEach(function (ring) {
      var bar = $(".ring__bar", ring);
      if (!bar) return;
      var pct = Math.max(0, Math.min(100, parseFloat(ring.getAttribute("data-ring")) || 0));
      var r = parseFloat(bar.getAttribute("r")) || 50;
      var circ = 2 * Math.PI * r;
      bar.style.setProperty("--circ", circ.toFixed(1));
      bar.style.strokeDasharray = circ.toFixed(1);
      bar.style.strokeDashoffset = circ.toFixed(1);
      var apply = function () {
        bar.style.strokeDashoffset = (circ * (1 - pct / 100)).toFixed(1);
      };
      if (reduceMotion) apply();
      else window.setTimeout(apply, 180);
    });
  }

  /* ------------------------------------------------------ AI description */
  function initAiWriter() {
    $$("[data-ai-generate]").forEach(function (btn) {
      on(btn, "click", function () {
        var endpoint = btn.getAttribute("data-ai-generate");
        var targetSel = btn.getAttribute("data-ai-target");
        var notesSel = btn.getAttribute("data-ai-notes");
        var target = targetSel ? $(targetSel) : null;
        var notes = notesSel ? $(notesSel) : null;
        if (!endpoint || !target) return;

        var body = new FormData();
        body.append("notes", (notes && notes.value) || target.value || "");
        body.append("csrf_token", csrf());
        btn.setAttribute("aria-busy", "true");
        btn.setAttribute("aria-disabled", "true");
        var label = btn.querySelector("[data-ai-label]");
        var original = label ? label.textContent : "";
        if (label) label.textContent = "Writing\u2026";

        fetch(endpoint, {
          method: "POST",
          body: body,
          headers: { "X-CSRFToken": csrf(), "X-Requested-With": "fetch" },
          credentials: "same-origin"
        }).then(function (r) { return r.json(); }).then(function (data) {
          if (data && data.description) {
            target.value = data.description;
            target.dispatchEvent(new Event("input", { bubbles: true }));
            toast("Draft description inserted", "success");
          } else {
            toast((data && data.error) || "Could not generate a description", "warning");
          }
        }).catch(function () {
          toast("Description service unavailable", "danger");
        }).finally(function () {
          btn.removeAttribute("aria-busy");
          btn.removeAttribute("aria-disabled");
          if (label) label.textContent = original;
        });
      });
    });
  }

  /* ------------------------------------------------- integration self test */
  function initIntegrationTest() {
    $$("[data-test-endpoint]").forEach(function (btn) {
      on(btn, "click", function () {
        var url = btn.getAttribute("data-test-endpoint");
        var out = $(btn.getAttribute("data-test-output") || "[data-test-output]");
        btn.setAttribute("aria-busy", "true");
        btn.setAttribute("aria-disabled", "true");
        var label = btn.querySelector("[data-test-label]");
        var original = label ? label.textContent : "";
        if (label) label.textContent = "Testing\u2026";
        var body = new FormData();
        body.append("csrf_token", csrf());

        fetch(url, {
          method: "POST",
          body: body,
          headers: { "X-CSRFToken": csrf(), "X-Requested-With": "fetch" },
          credentials: "same-origin"
        }).then(function (r) { return r.json(); }).then(function (data) {
          var ok = data && data.ok;
          toast((data && data.message) || (ok ? "Connection healthy" : "Connection failed"),
            ok ? "success" : "danger");
          if (out) {
            out.hidden = false;
            out.className = "note " + (ok ? "note--sage" : "note--rose");
            out.innerHTML =
              '<svg class="i" aria-hidden="true"><use href="#i-' +
              (ok ? "check-circle" : "alert-circle") + '"></use></svg><div></div>';
            $("div", out).textContent = (data && data.message) || "";
          }
        }).catch(function () {
          toast("Test request failed", "danger");
        }).finally(function () {
          btn.removeAttribute("aria-busy");
          btn.removeAttribute("aria-disabled");
          if (label) label.textContent = original;
        });
      });
    });
  }

  /* ------------------------------------------------------ preview devices */
  function initPreview() {
    var deviceEl = $("[data-device-frame]");
    var iframe = $("iframe[data-preview-frame]") || $("iframe");
    var currentPathEl = $("[data-preview-current]");
    if (!iframe && !deviceEl) return;

    $$("[data-device]").forEach(function (btn) {
      on(btn, "click", function () {
        var mode = btn.getAttribute("data-device") || "desktop";
        if (deviceEl) deviceEl.setAttribute("data-device-frame", mode);
        $$("[data-device]").forEach(function (b) {
          var on = b === btn;
          b.classList.toggle("is-on", on);
          b.classList.toggle("is-active", on);
        });
      });
    });

    $$("[data-preview-path]").forEach(function (btn) {
      on(btn, "click", function () {
        var path = btn.getAttribute("data-preview-path");
        if (iframe && path) iframe.src = path;
        if (currentPathEl && path) currentPathEl.textContent = path;
        $$("[data-preview-path]").forEach(function (b) {
          var on = b === btn;
          b.classList.toggle("is-on", on);
          b.setAttribute("aria-selected", on ? "true" : "false");
        });
      });
    });

    $$("[data-preview-reload]").forEach(function (btn) {
      on(btn, "click", function () {
        if (iframe) {
          try { iframe.contentWindow.location.reload(); } catch (e) { iframe.src = iframe.src; }
          toast("Preview reloaded", "info");
        }
      });
    });
  }

  /* ------------------------------------------------------------- startup */
  function boot() {
    initRail();
    initPalette();
    initSelection();
    initConfirm();
    initTableFilter();
    initSpark();
    initBarChart();
    initRings();
    initAiWriter();
    initIntegrationTest();
    initPreview();
  }

  if (doc.readyState === "loading") on(doc, "DOMContentLoaded", boot);
  else boot();
})();
