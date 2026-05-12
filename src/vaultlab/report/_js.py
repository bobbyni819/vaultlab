"""Bundled vanilla JS for interactive components.

Only injected when an interactive component (tabs, kanban, template editor,
keynav deck, filter bar) appears in the report. Pure ES2020, no dependencies.
"""

from __future__ import annotations

JS = """
(function () {
  // Tabs
  document.querySelectorAll('.vl-tabs').forEach(function (tabs) {
    var labels = tabs.querySelectorAll('.vl-tab-label');
    var panes = tabs.querySelectorAll('.vl-tab-pane');
    labels.forEach(function (label, i) {
      label.addEventListener('click', function () {
        labels.forEach(function (l) { l.classList.remove('active'); });
        panes.forEach(function (p) { p.classList.remove('active'); });
        label.classList.add('active');
        if (panes[i]) panes[i].classList.add('active');
      });
    });
  });

  // Kanban drag and drop
  document.querySelectorAll('.vl-kanban').forEach(function (board) {
    var dragged = null;
    board.querySelectorAll('.vl-item').forEach(function (item) {
      item.setAttribute('draggable', 'true');
      item.addEventListener('dragstart', function (e) {
        dragged = item;
        item.classList.add('dragging');
        if (e.dataTransfer) e.dataTransfer.effectAllowed = 'move';
      });
      item.addEventListener('dragend', function () {
        item.classList.remove('dragging');
        dragged = null;
      });
    });
    board.querySelectorAll('.vl-col').forEach(function (col) {
      col.addEventListener('dragover', function (e) {
        e.preventDefault();
        col.classList.add('over');
      });
      col.addEventListener('dragleave', function () {
        col.classList.remove('over');
      });
      col.addEventListener('drop', function (e) {
        e.preventDefault();
        col.classList.remove('over');
        if (dragged) col.querySelector('.vl-col-body').appendChild(dragged);
      });
    });
    var exportBtn = board.parentElement && board.parentElement.querySelector('.vl-export-md');
    if (exportBtn) {
      exportBtn.addEventListener('click', function () {
        var md = '';
        board.querySelectorAll('.vl-col').forEach(function (col) {
          var heading = col.querySelector('h4');
          md += '## ' + (heading ? heading.textContent : '') + '\\n\\n';
          col.querySelectorAll('.vl-item').forEach(function (item) {
            md += '- ' + item.textContent.trim() + '\\n';
          });
          md += '\\n';
        });
        navigator.clipboard.writeText(md).then(function () {
          exportBtn.textContent = 'Copied!';
          setTimeout(function () { exportBtn.textContent = 'Copy as markdown'; }, 1500);
        });
      });
    }
    var jsonBtn = board.parentElement && board.parentElement.querySelector('.vl-export-json');
    if (jsonBtn) {
      jsonBtn.addEventListener('click', function () {
        var data = {};
        board.querySelectorAll('.vl-col').forEach(function (col) {
          var heading = col.querySelector('h4');
          var key = heading ? heading.textContent.trim() : 'col';
          data[key] = Array.from(col.querySelectorAll('.vl-item')).map(function (i) { return i.textContent.trim(); });
        });
        navigator.clipboard.writeText(JSON.stringify(data, null, 2)).then(function () {
          jsonBtn.textContent = 'Copied!';
          setTimeout(function () { jsonBtn.textContent = 'Copy as JSON'; }, 1500);
        });
      });
    }
  });

  // Template editor with live preview + token counter
  document.querySelectorAll('.vl-editor').forEach(function (editor) {
    var ta = editor.querySelector('textarea');
    var samples = editor.querySelectorAll('.sample');
    var counter = editor.querySelector('.counter');
    var copyBtn = editor.querySelector('.copy-prompt');
    if (!ta) return;
    var rawSamples = Array.from(samples).map(function (s) { return s.dataset.context ? JSON.parse(s.dataset.context) : {}; });
    function render() {
      var tmpl = ta.value;
      samples.forEach(function (s, i) {
        var ctx = rawSamples[i] || {};
        var filled = tmpl.replace(/\\{\\{(\\w+)\\}\\}/g, function (_, k) {
          return ctx[k] !== undefined ? ctx[k] : '{{' + k + '}}';
        });
        s.textContent = filled;
      });
      if (counter) {
        var n = tmpl.length;
        counter.textContent = n + ' chars · ~' + Math.ceil(n / 4) + ' tokens';
      }
    }
    ta.addEventListener('input', render);
    render();
    if (copyBtn) {
      copyBtn.addEventListener('click', function () {
        navigator.clipboard.writeText(ta.value).then(function () {
          copyBtn.textContent = 'Copied!';
          setTimeout(function () { copyBtn.textContent = 'Copy prompt'; }, 1500);
        });
      });
    }
  });

  // Keynav deck — arrow keys navigate slides
  document.querySelectorAll('.vl-deck').forEach(function (deck) {
    var slides = deck.querySelectorAll('.slide');
    var pos = deck.querySelector('.pos');
    var idx = 0;
    function show(i) {
      idx = Math.max(0, Math.min(slides.length - 1, i));
      slides.forEach(function (s, j) { s.classList.toggle('active', j === idx); });
      if (pos) pos.textContent = (idx + 1) + ' / ' + slides.length;
    }
    deck.querySelectorAll('.prev').forEach(function (b) { b.addEventListener('click', function () { show(idx - 1); }); });
    deck.querySelectorAll('.next').forEach(function (b) { b.addEventListener('click', function () { show(idx + 1); }); });
    document.addEventListener('keydown', function (e) {
      if (!deck.contains(document.activeElement) && document.activeElement !== document.body) return;
      if (e.key === 'ArrowLeft') show(idx - 1);
      else if (e.key === 'ArrowRight') show(idx + 1);
    });
    show(0);
  });

  // Filter bar (data-filter on buttons; matches data-filter-key on rows/cards)
  document.querySelectorAll('.vl-filter').forEach(function (bar) {
    var targetSel = bar.dataset.target;
    if (!targetSel) return;
    var targets = document.querySelectorAll(targetSel);
    bar.querySelectorAll('button').forEach(function (btn) {
      btn.addEventListener('click', function () {
        bar.querySelectorAll('button').forEach(function (b) { b.classList.remove('active'); });
        btn.classList.add('active');
        var key = btn.dataset.filter;
        targets.forEach(function (t) {
          var match = !key || key === 'all' || (t.dataset.filterKey || '').split(',').indexOf(key) >= 0;
          t.style.display = match ? '' : 'none';
        });
      });
    });
  });

  // Copy-to-clipboard for any <button data-copy="text-to-copy"> or [data-copy-target="#sel"]
  document.querySelectorAll('[data-copy], [data-copy-target]').forEach(function (btn) {
    btn.addEventListener('click', function () {
      var text = btn.dataset.copy;
      if (!text && btn.dataset.copyTarget) {
        var el = document.querySelector(btn.dataset.copyTarget);
        if (el) text = el.textContent;
      }
      if (text) {
        navigator.clipboard.writeText(text).then(function () {
          var orig = btn.textContent;
          btn.textContent = 'Copied!';
          setTimeout(function () { btn.textContent = orig; }, 1200);
        });
      }
    });
  });
})();
"""
