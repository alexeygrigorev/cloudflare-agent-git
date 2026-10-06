/* Public history product chips and half-open Berlin hour bounds.
   Progressive enhancement: the built HTML is the full 24h / four-product view. */
(function () {
  'use strict';
  var page = document.getElementById('history-page');
  var dataEl = document.getElementById('history-telemetry-data');
  if (!page || !dataEl) return;

  var payload;
  try { payload = JSON.parse(dataEl.textContent || ''); }
  catch (_) { return; }
  if (!payload || !payload.window || !payload.hourly || !payload.products) return;

  var CANONICAL = payload.products.map(function (p) { return p.id; });
  var CHIPS = {};
  payload.products.forEach(function (p) { CHIPS[p.id] = p.chip; });
  var NAMES = {};
  payload.products.forEach(function (p) { NAMES[p.id] = p.name; });

  var winStart = payload.window.start_utc;
  var winEnd = payload.window.end_utc;
  var hourly = payload.hourly;
  var starts = hourly.map(function (b) { return b.bucket_start_utc; });
  var ends = hourly.map(function (b) { return b.bucket_end_utc; });

  var chips = Array.prototype.slice.call(page.querySelectorAll('.history-chip[data-product]'));
  var fromSel = document.getElementById('history-from');
  var toSel = document.getElementById('history-to');
  var fromUtc = document.getElementById('history-from-utc');
  var toUtc = document.getElementById('history-to-utc');
  var resetBtn = document.getElementById('history-reset');
  var emptyEl = document.getElementById('history-empty');
  var resultsEl = document.getElementById('history-results');
  var plotEl = document.getElementById('history-chart-plot');
  var xlabelEl = document.getElementById('history-chart-xlabels');
  var originalPlot = plotEl ? plotEl.innerHTML : '';
  var originalXlabels = xlabelEl ? xlabelEl.innerHTML : '';
  var applying = false;

  function parseUtc(value) {
    if (!value || typeof value !== 'string') return null;
    var text = value.trim();
    if (!text) return null;
    if (/^\d{4}-\d{2}-\d{2}T\d{2}:\d{2}:\d{2}Z$/.test(text)) {
      var ms = Date.parse(text);
      return isNaN(ms) ? null : ms;
    }
    if (/^\d{4}-\d{2}-\d{2}T\d{2}:\d{2}:\d{2}(?:\.\d+)?(?:Z|[+-]\d{2}:\d{2})$/.test(text)) {
      var parsed = Date.parse(text);
      return isNaN(parsed) ? null : parsed;
    }
    return null;
  }

  function isoZ(ms) {
    var d = new Date(ms);
    var y = d.getUTCFullYear();
    var m = String(d.getUTCMonth() + 1).padStart(2, '0');
    var day = String(d.getUTCDate()).padStart(2, '0');
    var h = String(d.getUTCHours()).padStart(2, '0');
    var min = String(d.getUTCMinutes()).padStart(2, '0');
    var s = String(d.getUTCSeconds()).padStart(2, '0');
    return y + '-' + m + '-' + day + 'T' + h + ':' + min + ':' + s + 'Z';
  }

  function snapFrom(ms) {
    var ws = parseUtc(winStart);
    var we = parseUtc(winEnd);
    if (ms <= ws) return ws;
    if (ms >= we) return we;
    var prev = ws;
    for (var i = 0; i < starts.length; i++) {
      var edge = parseUtc(starts[i]);
      if (edge === ms) return edge;
      if (edge < ms) prev = edge;
      else break;
    }
    return prev;
  }

  function snapTo(ms) {
    var ws = parseUtc(winStart);
    var we = parseUtc(winEnd);
    if (ms <= ws) return ws;
    if (ms >= we) return we;
    for (var i = 0; i < ends.length; i++) {
      var edge = parseUtc(ends[i]);
      if (edge === ms) return edge;
      if (edge > ms) return edge;
    }
    return we;
  }

  function uniqueCanonical(ids) {
    var set = {};
    ids.forEach(function (id) { set[id] = true; });
    return CANONICAL.filter(function (id) { return set[id]; });
  }

  function parseQuery(search) {
    var params = new URLSearchParams(search || '');
    var products = CANONICAL.slice();
    var from = winStart;
    var to = winEnd;

    if (params.has('product')) {
      var raw = params.get('product');
      if (raw === '' || raw === null) {
        products = [];
      } else {
        var ids = raw.split(',').map(function (s) { return s.trim(); }).filter(Boolean);
        var known = {};
        CANONICAL.forEach(function (id) { known[id] = true; });
        var valid = ids.length > 0 && ids.every(function (id) { return known[id]; });
        products = valid ? uniqueCanonical(ids) : CANONICAL.slice();
      }
    }

    if (params.has('from')) {
      var fromMs = parseUtc(params.get('from'));
      if (fromMs === null) {
        return { products: products, from: winStart, to: winEnd };
      }
      from = isoZ(snapFrom(fromMs));
    }
    if (params.has('to')) {
      var toMs = parseUtc(params.get('to'));
      if (toMs === null) {
        return { products: products, from: winStart, to: winEnd };
      }
      to = isoZ(snapTo(toMs));
    }
    return { products: products, from: from, to: to };
  }

  function inRange(bucket, from, to) {
    var start = parseUtc(bucket.bucket_start_utc);
    var a = parseUtc(from);
    var b = parseUtc(to);
    return start !== null && a !== null && b !== null && start >= a && start < b;
  }

  function observedCell(cell) {
    return cell && (cell.observation_status === 'observed' || cell.observation_status === 'partial');
  }

  function compute(state) {
    var selected = state.products;
    var inRangeBuckets = hourly.filter(function (b) { return inRange(b, state.from, state.to); });
    var fromMs = parseUtc(state.from);
    var toMs = parseUtc(state.to);
    var emptyReason = null;
    if (!selected.length) emptyReason = 'products';
    else if (fromMs >= toMs || !inRangeBuckets.length) emptyReason = 'range';

    if (emptyReason) {
      return {
        tokens: 0,
        observed: 0,
        inRangeCount: emptyReason === 'range' ? 0 : inRangeBuckets.length,
        work: 0,
        productCount: selected.length,
        showTokens: false,
        emptyReason: emptyReason,
        buckets: emptyReason === 'range' ? [] : inRangeBuckets
      };
    }

    var observed = 0;
    var work = 0;
    inRangeBuckets.forEach(function (b) {
      var anyObs = false;
      selected.forEach(function (pid) {
        var cell = (b.products && b.products[pid]) || {};
        if (observedCell(cell)) {
          anyObs = true;
          work += Number(cell.sampled_working_hours || 0);
        }
      });
      if (anyObs) observed += 1;
    });

    var tokens = 0;
    (payload.token_attribution || []).forEach(function (row) {
      if (selected.indexOf(row.product) === -1) return;
      var bucket = hourly[row.bucket_index];
      if (bucket && inRange(bucket, state.from, state.to)) tokens += Number(row.tokens || 0);
    });

    return {
      tokens: tokens,
      observed: observed,
      inRangeCount: inRangeBuckets.length,
      work: work,
      productCount: selected.length,
      showTokens: tokens > 0,
      emptyReason: null,
      buckets: inRangeBuckets
    };
  }

  function fmtTokens(n) {
    return String(n).replace(/\B(?=(\d{3})+(?!\d))/g, ',');
  }

  function fmtWork(hours) {
    return hours.toFixed(2) + ' h';
  }

  function selectedSet(products) {
    var set = {};
    products.forEach(function (id) { set[id] = true; });
    return set;
  }

  function isDefault(state) {
    return state.products.length === CANONICAL.length &&
      CANONICAL.every(function (id, i) { return state.products[i] === id; }) &&
      state.from === winStart &&
      state.to === winEnd;
  }

  function persist(state) {
    var parts = [];
    if (state.products.length !== CANONICAL.length ||
        !CANONICAL.every(function (id, i) { return state.products[i] === id; })) {
      parts.push('product=' + state.products.join(','));
    }
    if (state.from !== winStart) parts.push('from=' + state.from);
    if (state.to !== winEnd) parts.push('to=' + state.to);
    if (isDefault(state)) parts = [];
    var url = new URL(window.location.href);
    var search = parts.length ? '?' + parts.join('&') : '';
    var next = url.pathname + search + url.hash;
    var cur = window.location.pathname + window.location.search + window.location.hash;
    if (next !== cur) {
      window.history.replaceState(window.history.state, '', next);
    }
  }

  function setKpi(id, number, note, restore) {
    var card = document.getElementById(id);
    if (!card) return;
    var num = card.querySelector('.kpi-num');
    var nte = card.querySelector('.kpi-note');
    if (restore) {
      if (num) num.textContent = num.getAttribute('data-full') || number;
      if (nte) nte.textContent = nte.getAttribute('data-full') || note;
      return;
    }
    if (num) num.textContent = number;
    if (nte) nte.textContent = note;
  }

  function productNote(products) {
    return products.map(function (id) { return CHIPS[id]; }).join(', ') || 'None';
  }

  function updateKpis(state, result) {
    if (isDefault(state) && !result.emptyReason) {
      setKpi('kpi-tokens', '', '', true);
      setKpi('kpi-observed', '', '', true);
      setKpi('kpi-work', '', '', true);
      setKpi('kpi-products', '', '', true);
      return;
    }
    var teamWord = result.productCount === 1 ? ' Team' : ' Teams';
    setKpi(
      'kpi-tokens',
      fmtTokens(result.tokens),
      result.tokens
        ? 'Attributed tokens for selected products whose hour is in range'
        : 'No attributed tokens for this selection and range'
    );
    setKpi(
      'kpi-observed',
      result.observed + ' / ' + result.inRangeCount,
      'Hours in range where a selected product is observed or partial'
    );
    setKpi(
      'kpi-work',
      fmtWork(result.work),
      'Sampled working hours for selected products in range'
    );
    setKpi(
      'kpi-products',
      String(result.productCount) + teamWord,
      productNote(state.products)
    );
  }

  function berlinTick(bucket) {
    var label = bucket.berlin_label || '';
    var parts = label.split(' ');
    if (parts.length >= 2) {
      return parts[1].split('\u2013')[0];
    }
    return '';
  }

  function redrawChart(result, selected) {
    var plot = document.getElementById('history-chart-plot');
    var xlabels = document.getElementById('history-chart-xlabels');
    var svg = document.getElementById('history-chart-svg');
    if (!plot || !xlabels || !svg) return;

    var NS = 'http://www.w3.org/2000/svg';
    while (plot.firstChild) plot.removeChild(plot.firstChild);
    while (xlabels.firstChild) xlabels.removeChild(xlabels.firstChild);

    var buckets = result.buckets || [];
    var width = 960;
    var height = 240;
    var padL = 60;
    var padR = 24;
    var padT = 28;
    var padB = 44;
    var chartW = width - padL - padR;
    var chartH = height - padT - padB;
    var maxVal = 4.5;
    var n = Math.max(buckets.length, 1);
    var barW = chartW / n;
    var sel = selectedSet(selected);
    var firstUnobs = true;

    buckets.forEach(function (b, i) {
      var x = padL + i * barW;
      var g = document.createElementNS(NS, 'g');
      g.setAttribute('class', 'chart-bar');
      g.setAttribute('data-index', String(b.bucket_index));
      g.setAttribute('data-start', b.bucket_start_utc || '');
      g.setAttribute('data-end', b.bucket_end_utc || '');

      var presence = 0;
      var working = 0;
      var isObs = false;
      CANONICAL.forEach(function (pid) {
        if (!sel[pid]) return;
        var cell = (b.products && b.products[pid]) || {};
        if (observedCell(cell)) {
          isObs = true;
          presence += Number(cell.presence_hours || 0);
          working += Number(cell.sampled_working_hours || 0);
        }
      });
      g.setAttribute('data-observed', isObs ? '1' : '0');

      if (!isObs) {
        var hatch = document.createElementNS(NS, 'rect');
        hatch.setAttribute('x', (x + 2).toFixed(1));
        hatch.setAttribute('y', padT.toFixed(1));
        hatch.setAttribute('width', (barW - 4).toFixed(1));
        hatch.setAttribute('height', chartH.toFixed(1));
        hatch.setAttribute('fill', '#F4F5F0');
        hatch.setAttribute('stroke', '#DADCD9');
        hatch.setAttribute('stroke-width', '1');
        hatch.setAttribute('stroke-dasharray', '3,3');
        g.appendChild(hatch);
        if (firstUnobs) {
          firstUnobs = false;
          var t = document.createElementNS(NS, 'text');
          t.setAttribute('x', (x + barW).toFixed(1));
          t.setAttribute('y', (padT + 16).toFixed(1));
          t.setAttribute('font-family', 'Arial,sans-serif');
          t.setAttribute('font-size', '11');
          t.setAttribute('fill', '#EF7134');
          t.setAttribute('font-weight', '600');
          t.setAttribute('text-anchor', 'middle');
          t.textContent = 'Pre-collector (Unobserved)';
          g.appendChild(t);
        }
      } else {
        var presH = Math.min(presence, maxVal) / maxVal * chartH;
        var workH = Math.min(working, maxVal) / maxVal * chartH;
        var yPres = padT + chartH - presH;
        var yWork = padT + chartH - workH;
        var r1 = document.createElementNS(NS, 'rect');
        r1.setAttribute('x', (x + 3).toFixed(1));
        r1.setAttribute('y', yPres.toFixed(1));
        r1.setAttribute('width', (barW - 6).toFixed(1));
        r1.setAttribute('height', presH.toFixed(1));
        r1.setAttribute('fill', '#E5E8EB');
        r1.setAttribute('rx', '1');
        g.appendChild(r1);
        if (workH > 0) {
          var r2 = document.createElementNS(NS, 'rect');
          r2.setAttribute('x', (x + 4).toFixed(1));
          r2.setAttribute('y', yWork.toFixed(1));
          r2.setAttribute('width', (barW - 8).toFixed(1));
          r2.setAttribute('height', workH.toFixed(1));
          r2.setAttribute('fill', '#2455ED');
          r2.setAttribute('rx', '1');
          g.appendChild(r2);
        }
      }
      plot.appendChild(g);

      if (i % 3 === 0 || i === buckets.length - 1) {
        var tick = document.createElementNS(NS, 'text');
        tick.setAttribute('x', (x + barW / 2).toFixed(1));
        tick.setAttribute('y', String(height - 14));
        tick.setAttribute('font-family', 'ui-monospace,Menlo,Consolas,monospace');
        tick.setAttribute('font-size', '11');
        tick.setAttribute('fill', '#1C2027');
        tick.setAttribute('text-anchor', 'middle');
        tick.textContent = berlinTick(b);
        xlabels.appendChild(tick);
      }
    });
  }

  function restoreDefaultChart() {
    if (plotEl) plotEl.innerHTML = originalPlot;
    if (xlabelEl) xlabelEl.innerHTML = originalXlabels;
  }

  function updateTable(state, result) {
    var sel = selectedSet(state.products);
    var showTokens = result.showTokens;
    var cols = page.querySelectorAll('.telemetry-table .col-product');
    Array.prototype.forEach.call(cols, function (el) {
      var pid = el.getAttribute('data-product');
      el.hidden = !sel[pid];
    });
    var tokCols = page.querySelectorAll('.telemetry-table .col-tok');
    Array.prototype.forEach.call(tokCols, function (el) {
      el.hidden = !showTokens;
    });
    var rows = page.querySelectorAll('#history-ledger tbody tr.history-row');
    var fromMs = parseUtc(state.from);
    var toMs = parseUtc(state.to);
    Array.prototype.forEach.call(rows, function (row) {
      var start = parseUtc(row.getAttribute('data-start'));
      var visible = start !== null && start >= fromMs && start < toMs;
      row.hidden = !visible;
    });
    var span = (state.products.length) + (showTokens ? 1 : 0);
    var unobs = page.querySelectorAll('#history-ledger .cell-unobserved');
    Array.prototype.forEach.call(unobs, function (cell) {
      cell.colSpan = Math.max(span, 1);
    });
  }

  function updateCards(state) {
    var sel = selectedSet(state.products);
    var cards = page.querySelectorAll('.tracker-card[data-product]');
    Array.prototype.forEach.call(cards, function (card) {
      var pid = card.getAttribute('data-product');
      card.hidden = !sel[pid];
    });
  }

  function updateEmpty(result) {
    var btnJson = document.getElementById('history-export-json');
    var btnCsv = document.getElementById('history-export-csv');
    var btnMd = document.getElementById('history-export-md');
    var disable = !!result.emptyReason;
    if (btnJson) btnJson.disabled = disable;
    if (btnCsv) btnCsv.disabled = disable;
    if (btnMd) btnMd.disabled = disable;

    if (!emptyEl || !resultsEl) return;
    if (!result.emptyReason) {
      emptyEl.hidden = true;
      emptyEl.textContent = '';
      resultsEl.hidden = false;
      return;
    }
    resultsEl.hidden = true;
    emptyEl.hidden = false;
    emptyEl.textContent = result.emptyReason === 'products'
      ? 'Select at least one product to see occupancy, the ledger, and current-lane cards.'
      : 'No hours fall in this range. Each hour counts when its start is at or after From and before To.';
  }

  function syncControls(state) {
    applying = true;
    var sel = selectedSet(state.products);
    chips.forEach(function (btn) {
      var on = !!sel[btn.getAttribute('data-product')];
      btn.setAttribute('aria-pressed', on ? 'true' : 'false');
    });
    if (fromSel) {
      fromSel.value = state.from;
      if (fromSel.value !== state.from) {
        /* snapped bound may equal window end, which is a To option only */
        fromSel.selectedIndex = 0;
      }
    }
    if (toSel) {
      toSel.value = state.to;
      if (toSel.value !== state.to) {
        toSel.selectedIndex = toSel.options.length - 1;
      }
    }
    if (fromUtc && fromSel && fromSel.selectedOptions[0]) {
      fromUtc.textContent = fromSel.selectedOptions[0].getAttribute('data-utc') || '';
    }
    if (toUtc && toSel && toSel.selectedOptions[0]) {
      toUtc.textContent = toSel.selectedOptions[0].getAttribute('data-utc') || '';
    }
    applying = false;
  }

  function apply(state, writeUrl) {
    var result = compute(state);
    syncControls(state);
    updateKpis(state, result);
    updateEmpty(result);
    if (!result.emptyReason) {
      if (isDefault(state)) restoreDefaultChart();
      else redrawChart(result, state.products);
    }
    updateTable(state, result);
    updateCards(state);
    if (writeUrl) persist(state);
  }

  function readControls() {
    var products = chips
      .filter(function (btn) { return btn.getAttribute('aria-pressed') === 'true'; })
      .map(function (btn) { return btn.getAttribute('data-product'); });
    products = uniqueCanonical(products);
    var from = fromSel ? fromSel.value : winStart;
    var to = toSel ? toSel.value : winEnd;
    return { products: products, from: from, to: to };
  }

  chips.forEach(function (btn) {
    btn.addEventListener('click', function () {
      var on = btn.getAttribute('aria-pressed') === 'true';
      btn.setAttribute('aria-pressed', on ? 'false' : 'true');
      apply(readControls(), true);
    });
  });

  function onBoundChange() {
    if (applying) return;
    apply(readControls(), true);
  }
  if (fromSel) fromSel.addEventListener('change', onBoundChange);
  if (toSel) toSel.addEventListener('change', onBoundChange);
  if (resetBtn) {
    resetBtn.addEventListener('click', function () {
      apply({ products: CANONICAL.slice(), from: winStart, to: winEnd }, true);
    });
  }

  window.addEventListener('popstate', function () {
    apply(parseQuery(window.location.search), false);
  });

  page.classList.add('is-enhanced');
  apply(parseQuery(window.location.search), true);
  var btnJson = document.getElementById('history-export-json');
  var btnCsv = document.getElementById('history-export-csv');
  var btnMd = document.getElementById('history-export-md');

  function getExportFilename(state, ext) {
    var pids = state.products.length === CANONICAL.length ? 'all' : state.products.join('-');
    var f = state.from.replace(/[:-]/g, '').replace('T', '_').replace('Z', '');
    var t = state.to.replace(/[:-]/g, '').replace('T', '_').replace('Z', '');
    return 'hourly-history-' + f + '-' + t + '-' + pids + '.' + ext;
  }

  function downloadBlob(content, type, filename) {
    var blob = new Blob([content], { type: type });
    var url = URL.createObjectURL(blob);
    var a = document.createElement('a');
    a.href = url;
    a.download = filename;
    document.body.appendChild(a);
    a.click();
    document.body.removeChild(a);
    setTimeout(function () { URL.revokeObjectURL(url); }, 100);
  }

  function csvEscape(val) {
    if (val === null || val === undefined) return '';
    var s = String(val);
    if (/^[=+\-@\t\r]/.test(s)) s = "'" + s;
    if (s.indexOf(',') !== -1 || s.indexOf('"') !== -1 || s.indexOf('\n') !== -1 || s.indexOf('\r') !== -1) {
      s = '"' + s.replace(/"/g, '""') + '"';
    }
    return s;
  }

  function generateJson(state, result) {
    var exp = {
      window: payload.window,
      epistemic_policy: payload.epistemic_policy,
      filter: {
        products: state.products,
        from: state.from,
        to: state.to,
        generated_at_utc: payload.generated_at_utc || new Date().toISOString(),
        exported_at_utc: new Date().toISOString()
      },
      products: payload.products.filter(function (p) { return state.products.indexOf(p.id) !== -1; }),
      hourly: result.buckets.map(function (b) {
        var copy = {
          bucket_index: b.bucket_index,
          bucket_start_utc: b.bucket_start_utc,
          bucket_end_utc: b.bucket_end_utc,
          berlin_label: b.berlin_label,
          products: {}
        };
        state.products.forEach(function (pid) {
          if (b.products && b.products[pid]) {
            copy.products[pid] = b.products[pid];
          }
        });
        return copy;
      }),
      token_attribution: []
    };
    if (payload.token_attribution) {
      payload.token_attribution.forEach(function (row) {
        if (state.products.indexOf(row.product) !== -1) {
          var b = hourly[row.bucket_index];
          if (b && inRange(b, state.from, state.to)) {
            exp.token_attribution.push(row);
          }
        }
      });
    }
    downloadBlob(JSON.stringify(exp, null, 2), 'application/json', getExportFilename(state, 'json'));
  }

  function generateCsv(state, result) {
    var cols = [
      'bucket_index', 'bucket_start_utc', 'bucket_end_utc', 'berlin_label',
      'product_id', 'product_name', 'observation_status', 'coverage_fraction',
      'presence_hours', 'sampled_working_hours', 'active_presence_agents', 'active_working_agents'
    ];
    var lines = [cols.join(',')];
    result.buckets.forEach(function (b) {
      state.products.forEach(function (pid) {
        var pName = NAMES[pid] || pid;
        var c = (b.products && b.products[pid]) || {};
        var row = [
          b.bucket_index, b.bucket_start_utc, b.bucket_end_utc, b.berlin_label,
          pid, pName, c.observation_status || 'unobserved',
          c.coverage_fraction, c.presence_hours, c.sampled_working_hours,
          c.active_presence_agents, c.active_working_agents
        ];
        lines.push(row.map(csvEscape).join(','));
      });
    });
    downloadBlob(lines.join('\r\n'), 'text/csv;charset=utf-8', getExportFilename(state, 'csv'));
  }

  function generateMd(state, result) {
    var lines = [
      '# Filtered Hourly History Export', '',
      '- **From:** ' + state.from,
      '- **To:** ' + state.to,
      '- **Products:** ' + state.products.map(function(id) { return NAMES[id] || id; }).join(', '),
      '- **Generated:** ' + (payload.generated_at_utc || new Date().toISOString()),
      '- **Exported:** ' + new Date().toISOString(),
      ''
    ];
    var head = ['Hour'].concat(state.products.map(function(id) { return NAMES[id] || id; }));
    var sep = ['---'].concat(state.products.map(function() { return '---'; }));
    lines.push('| ' + head.join(' | ') + ' |');
    lines.push('| ' + sep.join(' | ') + ' |');
    result.buckets.forEach(function (b) {
      var row = [b.berlin_label || ''];
      state.products.forEach(function (pid) {
        var c = (b.products && b.products[pid]) || {};
        if (observedCell(c)) {
          var ph = Number(c.presence_hours || 0).toFixed(1);
          var wh = Number(c.sampled_working_hours || 0).toFixed(1);
          row.push(ph + 'h / ' + wh + 'h');
        } else {
          row.push('-');
        }
      });
      lines.push('| ' + row.join(' | ') + ' |');
    });
    lines.push('');
    downloadBlob(lines.join('\n'), 'text/markdown;charset=utf-8', getExportFilename(state, 'md'));
  }

  if (btnJson) btnJson.addEventListener('click', function() { var s = readControls(); generateJson(s, compute(s)); });
  if (btnCsv) btnCsv.addEventListener('click', function() { var s = readControls(); generateCsv(s, compute(s)); });
  if (btnMd) btnMd.addEventListener('click', function() { var s = readControls(); generateMd(s, compute(s)); });

})();
