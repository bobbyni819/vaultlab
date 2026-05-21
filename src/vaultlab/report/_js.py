"""Bundled vanilla JS for interactive components.

Inlined at the end of every consumer page. Wires the theme toggle, tabs,
kanban drag-and-drop, template editor, keynav deck, filter bar, copy buttons,
and toast. Pure ES5-safe vanilla JS, no dependencies.

Ported from the Claude Design handoff (``design_handoff_vaultlab_visual_system/``).
Stored as a raw string so JS regex escapes (\\s, \\w) survive verbatim.
"""

from __future__ import annotations

JS = r"""
/* ============================================================
   vaultlab.report — shared interactive behaviour
   Vanilla JS, no deps. Inlined into every consumer page.
   ============================================================ */
(function () {
  'use strict';

  // ─── Toast ──────────────────────────────────────────────
  var toast = null;
  function ensureToast () {
    if (toast) return toast;
    toast = document.createElement('div');
    toast.className = 'vl-toast';
    toast.setAttribute('role', 'status');
    toast.setAttribute('aria-live', 'polite');
    document.body.appendChild(toast);
    return toast;
  }
  function showToast (msg) {
    var t = ensureToast();
    t.innerHTML = '<span class="check" aria-hidden="true">✓</span><span>' + msg + '</span>';
    t.classList.add('show');
    clearTimeout(t._h);
    t._h = setTimeout(function () { t.classList.remove('show'); }, 1600);
  }

  // ─── Theme toggle ───────────────────────────────────────
  var savedTheme = (function () {
    try { return localStorage.getItem('vl-theme'); } catch (e) { return null; }
  })();
  if (savedTheme === 'dark') document.documentElement.setAttribute('data-theme', 'dark');

  document.querySelectorAll('[data-vl-theme]').forEach(function (btn) {
    function refresh () {
      var d = document.documentElement.getAttribute('data-theme') === 'dark';
      btn.textContent = d ? '☀ Light' : '☾ Dark';
      btn.setAttribute('aria-pressed', d ? 'true' : 'false');
    }
    refresh();
    btn.addEventListener('click', function () {
      var d = document.documentElement.getAttribute('data-theme') === 'dark';
      if (d) document.documentElement.removeAttribute('data-theme');
      else document.documentElement.setAttribute('data-theme', 'dark');
      try { localStorage.setItem('vl-theme', d ? 'light' : 'dark'); } catch (e) {}
      refresh();
    });
  });

  // ─── Tabs ───────────────────────────────────────────────
  document.querySelectorAll('.vl-tabs').forEach(function (tabs) {
    var labels = tabs.querySelectorAll('.vl-tab-label');
    var panes  = tabs.querySelectorAll('.vl-tab-pane');
    labels.forEach(function (label, i) {
      label.setAttribute('role', 'tab');
      label.setAttribute('tabindex', i === 0 ? '0' : '-1');
      label.addEventListener('click', function () { activate(i); });
      label.addEventListener('keydown', function (e) {
        if (e.key === 'ArrowRight') { e.preventDefault(); activate((i + 1) % labels.length); labels[(i + 1) % labels.length].focus(); }
        else if (e.key === 'ArrowLeft') { e.preventDefault(); var j = (i - 1 + labels.length) % labels.length; activate(j); labels[j].focus(); }
        else if (e.key === 'Enter' || e.key === ' ') { e.preventDefault(); activate(i); }
      });
    });
    function activate (i) {
      labels.forEach(function (l, j) {
        l.classList.toggle('active', i === j);
        l.setAttribute('tabindex', i === j ? '0' : '-1');
        l.setAttribute('aria-selected', i === j ? 'true' : 'false');
      });
      panes.forEach(function (p, j) { p.classList.toggle('active', i === j); });
    }
  });

  // ─── Kanban drag & drop ─────────────────────────────────
  document.querySelectorAll('.vl-kanban').forEach(function (board) {
    var dragged = null;

    function refreshCounts () {
      board.querySelectorAll('.vl-col').forEach(function (col) {
        var c = col.querySelector('.count');
        if (c) c.textContent = col.querySelectorAll('.vl-item').length;
      });
    }

    function bindItem (item) {
      item.setAttribute('draggable', 'true');
      item.setAttribute('tabindex', '0');
      item.setAttribute('role', 'listitem');
      item.addEventListener('dragstart', function (e) {
        dragged = item;
        item.classList.add('dragging');
        if (e.dataTransfer) {
          e.dataTransfer.effectAllowed = 'move';
          try { e.dataTransfer.setData('text/plain', item.textContent.trim()); } catch (_) {}
        }
      });
      item.addEventListener('dragend', function () {
        item.classList.remove('dragging');
        dragged = null;
        refreshCounts();
      });
      // Keyboard fallback: arrow keys move between columns
      item.addEventListener('keydown', function (e) {
        if (e.key !== 'ArrowLeft' && e.key !== 'ArrowRight') return;
        e.preventDefault();
        var cols = Array.from(board.querySelectorAll('.vl-col'));
        var here = item.closest('.vl-col');
        var idx = cols.indexOf(here);
        var next = cols[idx + (e.key === 'ArrowRight' ? 1 : -1)];
        if (!next) return;
        next.querySelector('.vl-col-body').appendChild(item);
        item.focus();
        refreshCounts();
      });
    }

    board.querySelectorAll('.vl-item').forEach(bindItem);

    board.querySelectorAll('.vl-col').forEach(function (col) {
      var body = col.querySelector('.vl-col-body');
      col.addEventListener('dragover', function (e) {
        e.preventDefault();
        col.classList.add('over');
        if (e.dataTransfer) e.dataTransfer.dropEffect = 'move';
      });
      col.addEventListener('dragleave', function (e) {
        if (col.contains(e.relatedTarget)) return;
        col.classList.remove('over');
      });
      col.addEventListener('drop', function (e) {
        e.preventDefault();
        col.classList.remove('over');
        if (dragged && body) {
          body.appendChild(dragged);
          dragged.focus();
        }
        refreshCounts();
      });
    });

    refreshCounts();

    var wrap = board.parentElement;
    if (!wrap) return;
    var mdBtn   = wrap.querySelector('.vl-export-md');
    var jsonBtn = wrap.querySelector('.vl-export-json');

    function pileName (col) {
      var named = col.querySelector('h4 .name');
      if (named) return named.textContent.trim();
      // Fallback: text content of <h4> minus glyph/count children
      var h4 = col.querySelector('h4');
      if (!h4) return 'col';
      var s = '';
      h4.childNodes.forEach(function (n) {
        if (n.nodeType === 3) { s += n.nodeValue; return; }
        if (n.nodeType === 1 && !n.classList.contains('glyph') && !n.classList.contains('count')) {
          s += n.textContent;
        }
      });
      return s.trim();
    }

    function itemText (it) {
      return it.textContent.replace(/^⠿\s*/, '').replace(/\s+/g, ' ').trim();
    }

    if (mdBtn) mdBtn.addEventListener('click', function () {
      var md = '';
      board.querySelectorAll('.vl-col').forEach(function (col) {
        md += '## ' + pileName(col) + '\n\n';
        col.querySelectorAll('.vl-item').forEach(function (it) {
          md += '- ' + itemText(it) + '\n';
        });
        md += '\n';
      });
      copyText(md, mdBtn, 'Copied as markdown');
    });

    if (jsonBtn) jsonBtn.addEventListener('click', function () {
      var data = {};
      board.querySelectorAll('.vl-col').forEach(function (col) {
        var key = pileName(col);
        data[key] = Array.from(col.querySelectorAll('.vl-item')).map(itemText);
      });
      copyText(JSON.stringify(data, null, 2), jsonBtn, 'Copied as JSON');
    });
  });

  // ─── Template editor ───────────────────────────────────
  document.querySelectorAll('.vl-editor').forEach(function (editor) {
    var ta = editor.querySelector('textarea');
    if (!ta) return;
    var samples = editor.querySelectorAll('.sample');
    var counter = editor.querySelector('.counter');
    var copyBtn = editor.querySelector('.copy-prompt');
    var raw = Array.from(samples).map(function (s) {
      try { return s.dataset.context ? JSON.parse(s.dataset.context) : {}; }
      catch (e) { return {}; }
    });
    function render () {
      var tmpl = ta.value;
      samples.forEach(function (s, i) {
        var ctx = raw[i] || {};
        s.textContent = tmpl.replace(/\{\{(\w+)\}\}/g, function (_, k) {
          return ctx[k] !== undefined ? ctx[k] : '{{' + k + '}}';
        });
      });
      if (counter) {
        var n = tmpl.length;
        counter.textContent = n + ' chars · ~' + Math.ceil(n / 4) + ' tokens';
      }
    }
    ta.addEventListener('input', render);
    render();
    if (copyBtn) copyBtn.addEventListener('click', function () { copyText(ta.value, copyBtn, 'Copied prompt'); });
  });

  // ─── Keynav deck ───────────────────────────────────────
  document.querySelectorAll('.vl-deck').forEach(function (deck) {
    var slides = deck.querySelectorAll('.slide');
    var pos    = deck.querySelector('.pos');
    var idx = 0;
    function show (i) {
      idx = Math.max(0, Math.min(slides.length - 1, i));
      slides.forEach(function (s, j) { s.classList.toggle('active', j === idx); });
      if (pos) pos.textContent = (idx + 1) + ' / ' + slides.length;
    }
    deck.querySelectorAll('.prev').forEach(function (b) { b.addEventListener('click', function () { show(idx - 1); }); });
    deck.querySelectorAll('.next').forEach(function (b) { b.addEventListener('click', function () { show(idx + 1); }); });
    document.addEventListener('keydown', function (e) {
      if (!deck.contains(document.activeElement) && document.activeElement !== document.body) return;
      if (e.key === 'ArrowLeft')  show(idx - 1);
      if (e.key === 'ArrowRight') show(idx + 1);
    });
    show(0);
  });

  // ─── Filter bar ────────────────────────────────────────
  document.querySelectorAll('.vl-filter').forEach(function (bar) {
    var sel = bar.dataset.target;
    if (!sel) return;
    var targets = document.querySelectorAll(sel);
    bar.querySelectorAll('button').forEach(function (btn) {
      btn.addEventListener('click', function () {
        bar.querySelectorAll('button').forEach(function (b) { b.classList.remove('active'); });
        btn.classList.add('active');
        var key = btn.dataset.filter;
        targets.forEach(function (t) {
          var keys = (t.dataset.filterKey || '').split(',').map(function (s) { return s.trim(); });
          var match = !key || key === 'all' || keys.indexOf(key) >= 0;
          t.style.display = match ? '' : 'none';
        });
      });
    });
  });

  // ─── Generic copy buttons ──────────────────────────────
  document.querySelectorAll('[data-copy], [data-copy-target]').forEach(function (btn) {
    btn.addEventListener('click', function (e) {
      e.stopPropagation();
      e.preventDefault();
      var text = btn.dataset.copy;
      if (!text && btn.dataset.copyTarget) {
        var el = document.querySelector(btn.dataset.copyTarget);
        if (el) text = el.textContent;
      }
      if (text) copyText(text, btn, 'Copied to clipboard');
    });
  });

  function copyText (text, btn, label) {
    function done () {
      showToast(label);
      if (btn) {
        var orig = btn.dataset.origLabel || btn.textContent;
        if (!btn.dataset.origLabel) btn.dataset.origLabel = orig;
        btn.textContent = '✓ Copied';
        btn.classList.add('vl-btn--copied');
        clearTimeout(btn._t);
        btn._t = setTimeout(function () {
          btn.textContent = btn.dataset.origLabel;
          btn.classList.remove('vl-btn--copied');
        }, 1500);
      }
    }
    if (navigator.clipboard && navigator.clipboard.writeText) {
      navigator.clipboard.writeText(text).then(done, fallback);
    } else { fallback(); }
    function fallback () {
      try {
        var ta = document.createElement('textarea');
        ta.value = text;
        ta.style.position = 'fixed'; ta.style.opacity = '0';
        document.body.appendChild(ta);
        ta.select();
        document.execCommand('copy');
        document.body.removeChild(ta);
        done();
      } catch (e) { /* swallow */ }
    }
  }
})();
"""
