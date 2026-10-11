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

  // Basket editor: one row per asset, checked against the API as it is typed.
  function saveBasket() {
    try { localStorage.setItem(STORAGE_KEY, JSON.stringify(basket)) } catch (e) {}
  }

  function presetBasket(i) { return { tickers: PRESETS[i].tickers.slice(), preset: i } }

  function restoreBasket() {
    try {
      var saved = JSON.parse(localStorage.getItem(STORAGE_KEY))
      if (saved && saved.tickers && saved.tickers.length) return saved
    } catch (e) {}
    return presetBasket(0)
  }

  function lookup(ticker) {
    if (!ticker || lookups[ticker]) return
    lookups[ticker] = { status: 'checking' }
    fetch(state.apiBase + '/api/lookup/' + encodeURIComponent(ticker)).then(function (res) {
      return res.json().then(function (body) {
        lookups[ticker] = res.ok ? { status: 'ok', info: body } : { status: 'missing' }
      })
    }).catch(function () { delete lookups[ticker] }).finally(updateBasket)
  }

  function renderBasket() {
    el('rd-preset').value = basket.preset === null || basket.preset === undefined ? '' : String(basket.preset)
    el('rd-book-rows').innerHTML = basket.tickers.map(function (t, i) {
      return '<tr><td><input class="rd-book__ticker" value="' + esc(t) + '" data-i="' + i + '" maxlength="20" spellcheck="false" aria-label="Ticker"></td>' +
        '<td class="rd-book__name" data-name="' + i + '"></td><td class="rd-book__since" data-since="' + i + '"></td>' +
        '<td><button type="button" class="rd-book__remove" data-remove="' + i + '" aria-label="Remove ' + esc(t) + '">' +
        '<svg viewBox="0 0 16 16" width="14" height="14"><path d="M4 4l8 8M12 4l-8 8" stroke="currentColor" stroke-width="1.8" stroke-linecap="round"/></svg></button></td></tr>'
    }).join('') || '<tr><td colspan="4" class="rd-muted">No assets yet. Add one below or load a sample basket.</td></tr>'
    basket.tickers.forEach(lookup)
    updateBasket()
  }

  function updateBasket() {
    basket.tickers.forEach(function (t, i) {
      var name = document.querySelector('[data-name="' + i + '"]')
      if (!name) return
      var l = lookups[t]
      var since = document.querySelector('[data-since="' + i + '"]')
      if (!l || l.status === 'checking') {
        name.innerHTML = '<span class="rd-muted">Checking...</span>'
        since.textContent = ''
      } else if (l.status === 'missing') {
        name.innerHTML = '<span class="rd-book__bad">Not found</span>'
        since.textContent = ''
      } else {
        name.innerHTML = esc(l.info.name) + '<small>' + esc(l.info.currency) + ' ' + num(l.info.last_price, 2) + '</small>'
        since.textContent = l.info.first_date
      }
    })
    var preset = PRESETS[basket.preset]
    el('rd-book-note').textContent = (preset && preset.note ? preset.note + ' ' : '') +
      'An asset joins once it has a full momentum lookback of history.'
    saveBasket()
  }

  function addAsset(ticker) {
    ticker = String(ticker || '').trim().toUpperCase().split(' ')[0]
    if (!ticker) return
    if (basket.tickers.indexOf(ticker) >= 0) {
      showError(ticker + ' is already in the basket')
      return
    }
    showError('')
    basket.tickers.push(ticker)
    basket.preset = null
    el('rd-add').value = ''
    el('rd-suggest').innerHTML = ''
    renderBasket()
  }

  var searchTimer = null
  function suggest(query) {
    clearTimeout(searchTimer)
    if (query.trim().length < 2) return
    searchTimer = setTimeout(function () {
      fetch(state.apiBase + '/api/search?q=' + encodeURIComponent(query.trim())).then(function (res) {
        return res.ok ? res.json() : { results: [] }
      }).then(function (body) {
        el('rd-suggest').innerHTML = body.results.map(function (x) {
          return '<option value="' + esc(x.ticker) + '">' + esc(x.name) + (x.exchange ? ', ' + esc(x.exchange) : '') + '</option>'
        }).join('')
      }).catch(function () {})
    }, 250)
  }

  function wireBasket() {
    var rows = el('rd-book-rows')
    rows.addEventListener('change', function (e) {
      if (e.target.dataset.i === undefined) return
      basket.tickers[Number(e.target.dataset.i)] = e.target.value.trim().toUpperCase()
      basket.preset = null
      renderBasket()
    })
    rows.addEventListener('click', function (e) {
      var btn = e.target.closest('[data-remove]')
      if (!btn) return
      basket.tickers.splice(Number(btn.dataset.remove), 1)
      basket.preset = null
      renderBasket()
    })
    el('rd-add').addEventListener('input', function (e) { suggest(e.target.value) })
    el('rd-add').addEventListener('keydown', function (e) {
      if (e.key !== 'Enter') return
      e.preventDefault()
      addAsset(e.target.value)
    })
    el('rd-add-btn').addEventListener('click', function () { addAsset(el('rd-add').value) })
    var preset = el('rd-preset')
    preset.innerHTML += PRESETS.map(function (p, i) { return '<option value="' + i + '">' + esc(p.name) + '</option>' }).join('')
    preset.addEventListener('change', function () {
      if (preset.value === '') return
      basket = presetBasket(Number(preset.value))
      renderBasket()
    })
  }

  function wireStrategies(list) {
    el('rd-strategies').innerHTML = list.map(function (s) {
      return '<label class="rd-check"><input type="checkbox" value="' + s.id + '" checked><span class="rd-dot" style="background:' + STRATEGY_COLORS[s.id] + '"></span>' + esc(s.name) + '</label>'
    }).join('')
  }

  function requestFromForm() {
    var tickers = basket.tickers.filter(Boolean)
    if (!tickers.length) throw new Error('Add at least one asset')
    var start = el('rd-start').value
    if (!start) throw new Error('Choose a start date')
    var chosen = Array.prototype.map.call(el('rd-strategies').querySelectorAll('input:checked'), function (i) { return i.value })
    if (!chosen.length) throw new Error('Pick at least one strategy in Model settings')
    var n = function (id) { return parseFloat(el(id).value) }
    return {
      tickers: tickers,
      start: start,
      rebalance: el('rd-rebalance').value,
      base_currency: el('rd-currency').value,
      cash_rate: (n('rd-cash') || 0) / 100,
      strategies: chosen,
      settings: {
        lookback_months: n('rd-lookback'),
        skip_months: n('rd-skip'),
        vol_window: n('rd-volwin'),
        min_weight: n('rd-min') / 100,
        max_weight: n('rd-max') / 100
      }
    }
  }

  // Three years back, on the 15th: the desk rebalances mid-month.
  function defaultStart() {
    var d = new Date()
    return (d.getFullYear() - 3) + '-' + String(d.getMonth() + 1).padStart(2, '0') + '-15'
  }

  function submit() {
    try {
      load(requestFromForm()).catch(function () {})
    } catch (err) {
      showError(err.message)
    }
  }

  function init(opts) {
    state.apiBase = (opts && opts.apiBase) || ''
    el('rd-start').value = defaultStart()
    el('rd-start').max = new Date().toISOString().slice(0, 10)
    basket = restoreBasket()
    wireBasket()
    renderBasket()
    el('rd-tabs').addEventListener('click', function (e) {
      var b = e.target.closest('[data-tab]')
      if (!b || !state.result) return
      state.tab = b.dataset.tab
      renderTabs(state.result)
      renderWeights(state.result)
    })
    el('rd-download').addEventListener('click', downloadCsv)
    el('rd-form').addEventListener('submit', function (e) {
      e.preventDefault()
      submit()
    })
    fetch(state.apiBase + '/api/strategies').then(function (res) { return res.json() }).then(function (body) {
      wireStrategies(body.strategies)
      submit()
    })
  }

  return { init: init, load: load, render: render }
})()
