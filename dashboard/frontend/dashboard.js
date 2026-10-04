// Draws the backtest returned by POST /api/backtest. All numbers come from the API.
var MomentumDashboard = (function () {
  var C = { red: '#ae1f19', grey: '#9ca3af', greyDark: '#6b7280', ink: '#111827', line: '#eef0f2', green: '#16a34a', danger: '#dc2626' }
  var STRATEGY_COLORS = { tsmom: '#ae1f19', equal_weight: '#6b7280', inverse_vol: '#2a78d6', momentum_only: '#f59e0b' }
  var ASSET_COLORS = ['#ae1f19', '#2a78d6', '#f59e0b', '#16a34a', '#7c3aed', '#0891b2', '#db2777', '#65a30d', '#ea580c', '#475569',
    '#e11d48', '#0d9488', '#a16207', '#4f46e5', '#be123c', '#15803d', '#c2410c', '#1d4ed8', '#9333ea', '#0f766e']
  var PRESETS = [
    { name: 'Desk basket, June 2026', note: 'ESS and SOYB replace AVB and SOYB.L, which no longer trade.',
      tickers: ['ONTO', 'ESS', 'UEC', 'VRTX', 'APO', 'SGLD.L', 'SOYB', 'SIVR', 'URNM', 'DBB'] },
    { name: 'Global asset classes', tickers: ['SPY', 'EFA', 'EEM', 'TLT', 'IEF', 'GLD', 'DBC', 'VNQ'] },
    { name: 'US sectors', tickers: ['XLK', 'XLF', 'XLV', 'XLE', 'XLY', 'XLP', 'XLI', 'XLB', 'XLU'] },
    { name: 'US mega caps', tickers: ['AAPL', 'MSFT', 'NVDA', 'AMZN', 'GOOGL', 'META', 'BRK-B', 'JPM'] }
  ]
  var STORAGE_KEY = 'momentum-basket'
  var charts = {}
  var state = { apiBase: '', result: null, tab: 'tsmom' }
  var basket = { tickers: [], preset: null }
  var lookups = {}

  function pct(x, d) {
    if (x === null || x === undefined || isNaN(x)) return '-'
    return (x * 100).toFixed(d === undefined ? 1 : d) + '%'
  }
  function signedPct(x, d) {
    if (x === null || x === undefined || isNaN(x)) return '-'
    return (x >= 0 ? '+' : '') + pct(x, d)
  }
  function num(x, d) {
    if (x === null || x === undefined || isNaN(x)) return '-'
    return Number(x).toFixed(d === undefined ? 2 : d)
  }
  function esc(s) {
    return String(s).replace(/[&<>"']/g, function (c) {
      return { '&': '&amp;', '<': '&lt;', '>': '&gt;', '"': '&quot;', "'": '&#39;' }[c]
    })
  }
  var MONTHS = ['Jan', 'Feb', 'Mar', 'Apr', 'May', 'Jun', 'Jul', 'Aug', 'Sep', 'Oct', 'Nov', 'Dec']
  // 2026-03-30 -> Mar 26
  function shortDate(iso) { return MONTHS[Number(iso.slice(5, 7)) - 1] + ' ' + iso.slice(2, 4) }
  function el(id) { return document.getElementById(id) }

  function baseOptions() {
    return {
      responsive: true,
      maintainAspectRatio: false,
      animation: { duration: 250 },
      plugins: { legend: { display: false }, tooltip: { backgroundColor: C.ink, titleFont: { weight: '700' }, padding: 10, cornerRadius: 8 } },
      scales: {
        x: { grid: { color: C.line, lineWidth: 1, drawTicks: false }, border: { display: false }, ticks: { color: C.greyDark, font: { size: 11 } } },
        y: { grid: { color: C.line, lineWidth: 1, drawTicks: false }, border: { display: false }, ticks: { color: C.greyDark, font: { size: 11 } } }
      }
    }
  }

  function destroy(key) {
    if (!charts[key]) return
    charts[key].destroy()
    delete charts[key]
  }

  function dateTicks(opts, labels, canvas) {
    var every = Math.max(1, Math.round(labels.length / (el(canvas).parentNode.clientWidth < 500 ? 3 : 6)))
    opts.scales.x.grid.display = false
    opts.scales.x.ticks.maxRotation = 0
    opts.scales.x.ticks.autoSkip = false
    opts.scales.x.ticks.callback = function (v, i) { return i % every === 0 ? shortDate(labels[i]) : '' }
  }

  function strategies(r) {
    return Object.keys(r.strategies).map(function (k) { return { id: k, s: r.strategies[k] } })
  }

  function renderHeader(r) {
    el('rd-window').textContent = r.window.start + ' to ' + r.window.end + ', ' + r.window.rebalances + ' rebalances'
    el('rd-schedule').textContent = 'Rebalance ' + r.window.schedule
  }

  function renderMetrics(r) {
    var list = strategies(r)
    var best = function (key, higher) {
      var vals = list.map(function (x) { return x.s.metrics[key] }).filter(function (v) { return v !== null })
      return higher ? Math.max.apply(null, vals) : Math.min.apply(null, vals)
    }
    var top = { sharpe: best('sharpe', true), annualized_return: best('annualized_return', true), max_drawdown: best('max_drawdown', true) }
    var mark = function (key, v) { return v !== null && v === top[key] ? ' class="rd-best"' : '' }
    el('rd-metrics').querySelector('tbody').innerHTML = list.map(function (x) {
      var m = x.s.metrics
      var cell = function (label, key, value) { return '<td data-label="' + label + '"' + mark(key, m[key]) + '>' + value + '</td>' }
      return '<tr><td class="sym"><span class="rd-dot" style="background:' + STRATEGY_COLORS[x.id] + '"></span>' + esc(x.s.name) + '</td>' +
        cell('Total return', 'cumulative_return', signedPct(m.cumulative_return)) +
        cell('Annual return', 'annualized_return', signedPct(m.annualized_return)) +
        cell('Volatility', 'annualized_volatility', pct(m.annualized_volatility)) +
        cell('Sharpe', 'sharpe', num(m.sharpe)) +
        cell('Sortino', 'sortino', num(m.sortino)) +
        cell('Max drawdown', 'max_drawdown', pct(m.max_drawdown)) +
        cell('Turnover', 'avg_turnover', pct(m.avg_turnover)) + '</tr>'
    }).join('')
    el('rd-notes').innerHTML = r.notes.map(function (n) { return '<div class="rd-note">' + esc(n) + '</div>' }).join('')
  }

  function renderGrowth(r) {
    var list = strategies(r)
    var labels = list[0].s.value.dates
    destroy('growth')
    destroy('drawdown')
    var opts = baseOptions()
    opts.interaction = { mode: 'index', intersect: false }
    dateTicks(opts, labels, 'rd-growth')
    opts.scales.y.ticks.callback = function (v) { return num(v, 2) }
    opts.plugins.tooltip.callbacks = { label: function (c) { return c.dataset.label + ': ' + num(c.raw, 3) } }
    charts.growth = new Chart(el('rd-growth'), {
      type: 'line',
      data: {
        labels: labels,
        datasets: list.map(function (x) {
          return { label: x.s.name, data: x.s.value.values, borderColor: STRATEGY_COLORS[x.id], borderWidth: x.id === 'tsmom' ? 2.2 : 1.6, pointRadius: 0, pointHoverRadius: 4, tension: 0.1 }
        })
      },
      options: opts
    })
    el('rd-growth-legend').innerHTML = list.map(function (x) {
      return '<span><i style="background:' + STRATEGY_COLORS[x.id] + '"></i>' + esc(x.s.name) + '</span>'
    }).join('')

    var dopts = baseOptions()
    dopts.interaction = { mode: 'index', intersect: false }
    dopts.scales.x.grid.display = false
    dopts.scales.x.ticks.display = false
    dopts.scales.y.ticks.callback = function (v) { return pct(v, 0) }
    dopts.scales.y.max = 0
    dopts.plugins.tooltip.callbacks = { label: function (c) { return c.dataset.label + ': ' + pct(c.raw, 2) } }
    charts.drawdown = new Chart(el('rd-drawdown'), {
      type: 'line',
      data: {
        labels: labels,
        datasets: list.map(function (x) {
          return { label: x.s.name, data: x.s.drawdown, borderColor: STRATEGY_COLORS[x.id], borderWidth: x.id === 'tsmom' ? 2 : 1.4, pointRadius: 0, pointHoverRadius: 4, tension: 0.1 }
        })
      },
      options: dopts
    })
  }

  function renderAllocation(r) {
    var list = strategies(r)
    var first = list[0].s.current
    el('rd-current-date').textContent = first.date
    var assets = Object.keys(first.weights).filter(function (a) {
      return a !== 'cash' || list.some(function (x) { return x.s.current.weights.cash > 0.0005 })
    })
    assets.sort(function (a, b) {
      if (a === 'cash') return 1
      if (b === 'cash') return -1
      return (list[0].s.current.weights[b] || 0) - (list[0].s.current.weights[a] || 0)
    })
    var names = {}
    r.assets.forEach(function (a) { names[a.ticker] = a.name })
    var table = el('rd-alloc')
    table.querySelector('thead').innerHTML = '<tr><th>Asset</th>' + list.map(function (x) {
      return '<th><span class="rd-dot" style="background:' + STRATEGY_COLORS[x.id] + '"></span>' + esc(x.s.name) + '</th>'
    }).join('') + '</tr>'
    table.querySelector('tbody').innerHTML = assets.map(function (a) {
      return '<tr><td class="sym">' + esc(a === 'cash' ? 'Cash' : a) + (names[a] && names[a] !== a ? '<small>' + esc(names[a]) + '</small>' : '') + '</td>' +
        list.map(function (x) {
          var w = x.s.current.weights[a] || 0
          return '<td data-label="' + esc(x.s.name) + '"><div class="rd-alloc__cell"><div class="rd-bar"><span style="width:' + Math.min(100, w * 100) + '%; background:' + STRATEGY_COLORS[x.id] + '"></span></div><span>' + pct(w) + '</span></div></td>'
        }).join('') + '</tr>'
    }).join('')
  }

  function renderTabs(r) {
    var list = strategies(r)
    if (!r.strategies[state.tab]) state.tab = list[0].id
    el('rd-tabs').innerHTML = list.map(function (x) {
      return '<button type="button" data-tab="' + x.id + '" aria-pressed="' + (x.id === state.tab) + '">' + esc(x.s.name) + '</button>'
    }).join('')
  }

  function renderWeights(r) {
    var s = r.strategies[state.tab]
    var w = s.weights
    destroy('weights')
    var opts = baseOptions()
    opts.interaction = { mode: 'index', intersect: false }
    dateTicks(opts, w.dates, 'rd-weights')
    opts.scales.y.stacked = true
    opts.scales.y.min = 0
    opts.scales.y.max = 1
    opts.scales.y.ticks.callback = function (v) { return pct(v, 0) }
    opts.plugins.legend = { display: true, position: 'bottom', labels: { boxWidth: 10, boxHeight: 10, color: C.greyDark, font: { size: 11 } } }
    opts.plugins.tooltip.callbacks = { label: function (c) { return c.dataset.label + ': ' + pct(c.raw) } }
    var datasets = w.assets.map(function (a, i) {
      var color = a === 'cash' ? '#d1d5db' : ASSET_COLORS[i % ASSET_COLORS.length]
      return { label: a === 'cash' ? 'Cash' : a, data: w.rows.map(function (row) { return row[i] }), backgroundColor: color, borderColor: color, borderWidth: 1, fill: true, pointRadius: 0, stepped: true }
    }).filter(function (d) { return d.data.some(function (v) { return v > 0.0005 }) })
    charts.weights = new Chart(el('rd-weights'), { type: 'line', data: { labels: w.dates, datasets: datasets }, options: opts })
  }

  function render(result) {
    state.result = result
    renderHeader(result)
    renderMetrics(result)
    renderGrowth(result)
    renderAllocation(result)
    renderTabs(result)
    renderWeights(result)
    el('rd-body').classList.remove('rd-loading')
  }

  function downloadCsv() {
    if (!state.result) return
    var s = state.result.strategies[state.tab]
    var lines = ['rebalance_date,' + s.weights.assets.join(',')].concat(s.weights.dates.map(function (d, i) {
      return d + ',' + s.weights.rows[i].map(function (v) { return v === null ? '' : v }).join(',')
    }))
    var link = document.createElement('a')
    link.href = URL.createObjectURL(new Blob([lines.join('\n') + '\n'], { type: 'text/csv' }))
    link.download = state.tab + '_weights.csv'
    link.click()
    URL.revokeObjectURL(link.href)
  }

  function showError(msg) {
    var box = el('rd-error')
    box.textContent = msg
    box.classList.toggle('show', !!msg)
  }

  function load(request) {
    el('rd-body').classList.add('rd-loading')
    el('rd-run').disabled = true
    showError('')
    return fetch(state.apiBase + '/api/backtest', {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify(request)
    }).then(function (res) {
      return res.json().then(function (body) {
        if (!res.ok) throw new Error(typeof body.detail === 'string' ? body.detail : body.detail.map(function (d) { return d.msg }).join('; '))
        return body
      })
    }).then(function (result) {
      render(result)
      return result
    }).catch(function (err) {
      showError(err.message)
      el('rd-body').classList.remove('rd-loading')
      throw err
    }).finally(function () {
      el('rd-run').disabled = false
    })
  }

  return { load: load, render: render }
})()
