const $ = (selector) => document.querySelector(selector);
const $$ = (selector) => document.querySelectorAll(selector);

function loadStoredState() {
  try {
    const stored = JSON.parse(localStorage.getItem('banana-paper-state') || '{}');
    return stored && typeof stored === 'object' && !Array.isArray(stored) ? stored : {};
  } catch (error) {
    return {};
  }
}

function normalizeTimestamp(value) {
  if (typeof value !== 'string') return new Date().toISOString();
  const parsed = new Date(value);
  return Number.isFinite(parsed.getTime()) ? parsed.toISOString() : new Date().toISOString();
}

function normalizeStoredState(stored) {
  const normalized = {};
  if (Number.isFinite(Number(stored.cash))) normalized.cash = Number(stored.cash);
  if (Number.isFinite(Number(stored.equity))) normalized.equity = Number(stored.equity);
  if (Array.isArray(stored.trades)) normalized.trades = stored.trades.filter((trade) => (
    trade && typeof trade === 'object'
    && Number.isFinite(Number(trade.entry))
    && Number.isFinite(Number(trade.exit))
    && Number.isFinite(Number(trade.pnl))
  )).map((trade) => ({
    side: trade.side === 'SHORT' ? 'SHORT' : 'LONG',
    entry: Number(trade.entry),
    exit: Number(trade.exit),
    pnl: Number(trade.pnl),
    closed: normalizeTimestamp(trade.closed),
  }));
  if (stored.position && typeof stored.position === 'object') {
    const position = stored.position;
    const entry = Number(position.entry);
    const qty = Number(position.qty);
    if (Number.isFinite(entry) && entry > 0 && Number.isFinite(qty) && qty > 0) {
      normalized.position = {
        side: position.side === 'SHORT' ? 'SHORT' : 'LONG',
        entry,
        qty,
        opened: normalizeTimestamp(position.opened),
      };
    }
  }
  return normalized;
}

function persistState(payload) {
  try {
    localStorage.setItem('banana-paper-state', JSON.stringify(payload));
  } catch (error) {
    // The backend remains authoritative when browser storage is unavailable.
  }
}

function clearStoredState() {
  try {
    localStorage.removeItem('banana-paper-state');
  } catch (error) {
    // Reload still resets in-memory UI when browser storage is unavailable.
  }
}

const storedState = normalizeStoredState(loadStoredState());
const state = {
  cash: null,
  equity: null,
  position: null,
  trades: [],
  ...storedState,
  // A price is valid only after it has been received from /api/snapshot.
  price: null,
  snapshot: null,
  equity: null,
};

const SNAPSHOT_SYMBOL = 'BTC/USDT';
const SNAPSHOT_TIMEFRAME = '1h';

const clock = $('#clock');
function tick() {
  if (clock) clock.textContent = new Date().toISOString().slice(11, 19);
}
tick();
setInterval(tick, 1000);

const toast = $('#toast');
function notify(message) {
  if (!toast) return;
  toast.textContent = message;
  toast.classList.add('show');
  setTimeout(() => toast.classList.remove('show'), 2200);
}

async function readJson(response) {
  try {
    return await response.json();
  } catch (error) {
    return { error: 'Backend returned invalid JSON' };
  }
}

function normalizePaperState(payload) {
  if (!payload || typeof payload !== 'object' || Array.isArray(payload)) return null;
  const positions = payload.positions && typeof payload.positions === 'object' && !Array.isArray(payload.positions)
    ? payload.positions
    : {};
  const cash = Number(payload.cash);
  const equity = Number(payload.equity);
  return {
    positions,
    cash: Number.isFinite(cash) ? cash : null,
    equity: Number.isFinite(equity) ? equity : null,
  };
}

function normalizePosition(payload) {
  if (!payload || typeof payload !== 'object') return null;
  const quantity = Number(payload.quantity);
  const averagePrice = Number(payload.average_price);
  if (!Number.isFinite(quantity) || quantity === 0 || !Number.isFinite(averagePrice) || averagePrice <= 0) return null;
  return {
    side: quantity > 0 ? 'LONG' : 'SHORT',
    entry: averagePrice,
    qty: Math.abs(quantity),
    opened: normalizeTimestamp(payload.opened),
  };
}

function normalizeAnalysis(payload) {
  if (!payload || typeof payload !== 'object' || Array.isArray(payload) || !Array.isArray(payload.reports)) return null;
  const reports = payload.reports.filter((report) => (
    report && typeof report === 'object' && typeof report.agent === 'string'
  ));
  return { reports };
}

function readOrderId(payload) {
  const orderId = payload?.order?.order_id;
  return typeof orderId === 'string' && orderId ? orderId : null;
}

function requireOrderId(payload, close = false) {
  const orderId = readOrderId(payload);
  if (!orderId) throw new Error(close ? 'Backend returned invalid close order' : 'Backend returned invalid order');
  return orderId;
}

function save() {
  persistState({
    cash: state.cash,
    position: state.position,
    trades: state.trades,
  });
}

function snapshotSource(snapshot) {
  return snapshot?.snapshot || snapshot || {};
}

function snapshotPrice(snapshot) {
  const source = snapshotSource(snapshot);
  const summary = source.timeframes?.[SNAPSHOT_TIMEFRAME];
  const value = source.last_price ?? summary?.last_price;
  const price = Number(value);
  return Number.isFinite(price) ? price : null;
}

function snapshotIndicators(snapshot) {
  const source = snapshotSource(snapshot);
  return source.indicators || source.timeframes?.[SNAPSHOT_TIMEFRAME]?.indicators || {};
}

function snapshotRegime(snapshot) {
  const regime = snapshotSource(snapshot).regime;
  return typeof regime === 'string' && regime.trim() ? regime.trim().toUpperCase() : '—';
}

function formatMetric(value, digits = 2) {
  const number = Number(value);
  return Number.isFinite(number) ? number.toLocaleString(undefined, { maximumFractionDigits: digits }) : '—';
}

function renderSnapshotMetrics(snapshot) {
  const indicators = snapshotIndicators(snapshot);
  const marketBias = $('#market-bias');
  const confidence = $('#market-confidence');
  const chartFooter = document.querySelector('.chart-footer');
  if (marketBias) marketBias.textContent = snapshotRegime(snapshot);
  if (confidence) confidence.textContent = snapshotSource(snapshot).stale ? 'stale snapshot' : 'snapshot source';
  if (chartFooter) {
    chartFooter.innerHTML = [
      ['EMA', indicators.ema],
      ['RSI', indicators.rsi],
      ['ATR', indicators.atr],
      ['VOL Z', indicators.volume_zscore],
    ].map(([label, value]) => `<span>${label} <b>${formatMetric(value)}</b></span>`).join('');
  }
}

function snapshotCandles(snapshot, price) {
  const source = snapshotSource(snapshot);
  const configured = source.candles ?? snapshot?.candles ?? source.ohlcv;
  const input = Array.isArray(configured)
    ? configured
    : configured?.[SNAPSHOT_TIMEFRAME] || [];
  const candles = input
    .map((candle) => ({
      open: Number(candle.open),
      high: Number(candle.high),
      low: Number(candle.low),
      close: Number(candle.close),
    }))
    .filter((candle) => Object.values(candle).every(Number.isFinite));

  if (!candles.length) {
    return [{ open: price, high: price, low: price, close: price }];
  }

  // The snapshot's canonical last price is the chart's final close as well.
  candles[candles.length - 1] = {
    ...candles[candles.length - 1],
    close: price,
    high: Math.max(candles[candles.length - 1].high, price),
    low: Math.min(candles[candles.length - 1].low, price),
  };
  return candles;
}

function setStaleBadge(stale) {
  const price = $('#market-price');
  const parent = price?.parentElement;
  if (!parent) return;
  let badge = $('#snapshot-stale');
  if (!badge) {
    badge = document.createElement('span');
    badge.id = 'snapshot-stale';
    badge.className = 'badge stale-badge';
    badge.setAttribute('aria-label', 'Market snapshot is stale');
    parent.appendChild(badge);
  }
  badge.textContent = 'STALE';
  badge.hidden = !stale;
}

function renderCandles(snapshot) {
  const svg = $('#live-candles');
  const price = snapshotPrice(snapshot);
  if (!svg || price === null) return;

  svg.querySelectorAll('.area, .line, .guide, .point, .live-candle').forEach((node) => node.remove());
  const candles = snapshotCandles(snapshot, price);
  const lows = candles.map((candle) => candle.low);
  const highs = candles.map((candle) => candle.high);
  const rawLow = Math.min(...lows);
  const rawHigh = Math.max(...highs);
  const rawRange = rawHigh - rawLow;
  const padding = rawRange ? rawRange * 0.05 : Math.max(Math.abs(price) * 0.001, 1);
  const low = rawLow - padding;
  const high = rawHigh + padding;
  const range = high - low || 1;
  const width = 760;
  const height = 245;
  const step = width / candles.length;
  const y = (value) => ((high - value) / range) * height;

  candles.forEach((candle, index) => {
    const x = index * step + step * 0.18;
    const candleWidth = step * 0.64;
    const group = document.createElementNS('http://www.w3.org/2000/svg', 'g');
    group.classList.add('live-candle');
    group.dataset.close = String(candle.close);
    const wick = document.createElementNS('http://www.w3.org/2000/svg', 'line');
    wick.setAttribute('x1', String(x + candleWidth / 2));
    wick.setAttribute('x2', String(x + candleWidth / 2));
    wick.setAttribute('y1', String(y(candle.high)));
    wick.setAttribute('y2', String(y(candle.low)));
    wick.setAttribute('stroke', candle.close >= candle.open ? '#35d399' : '#ff647c');
    const body = document.createElementNS('http://www.w3.org/2000/svg', 'rect');
    body.setAttribute('x', String(x));
    body.setAttribute('y', String(Math.min(y(candle.open), y(candle.close))));
    body.setAttribute('width', String(candleWidth));
    body.setAttribute('height', String(Math.max(1, Math.abs(y(candle.close) - y(candle.open)))));
    body.setAttribute('fill', candle.close >= candle.open ? '#35d399' : '#ff647c');
    body.setAttribute('opacity', '.85');
    group.append(wick, body);
    svg.appendChild(group);
  });

  const closePath = candles.map((candle, index) => {
    const x = index * step + step / 2;
    return `${index === 0 ? 'M' : 'L'} ${x} ${y(candle.close)}`;
  }).join(' ');
  const priceOverlay = document.createElementNS('http://www.w3.org/2000/svg', 'path');
  priceOverlay.classList.add('line', 'price-overlay');
  priceOverlay.setAttribute('d', closePath);
  priceOverlay.setAttribute('fill', 'none');
  priceOverlay.setAttribute('stroke', '#35d7ff');
  priceOverlay.setAttribute('stroke-width', '2.5');
  priceOverlay.setAttribute('stroke-linecap', 'round');
  priceOverlay.setAttribute('stroke-linejoin', 'round');
  priceOverlay.setAttribute('vector-effect', 'non-scaling-stroke');
  priceOverlay.setAttribute('data-series', 'price-close');
  priceOverlay.setAttribute('aria-label', 'BTC/USDT price close overlay (blue line)');
  svg.appendChild(priceOverlay);

  const legend = document.createElementNS('http://www.w3.org/2000/svg', 'g');
  legend.classList.add('line', 'price-overlay-legend');
  legend.setAttribute('transform', 'translate(16 18)');
  legend.setAttribute('role', 'group');
  legend.setAttribute('aria-label', 'Price chart legend: blue line is price close');
  const legendBackground = document.createElementNS('http://www.w3.org/2000/svg', 'rect');
  legendBackground.setAttribute('x', '0');
  legendBackground.setAttribute('y', '-12');
  legendBackground.setAttribute('width', '132');
  legendBackground.setAttribute('height', '22');
  legendBackground.setAttribute('rx', '4');
  legendBackground.setAttribute('fill', '#080d16');
  legendBackground.setAttribute('fill-opacity', '.86');
  legendBackground.setAttribute('stroke', 'none');
  const legendLine = document.createElementNS('http://www.w3.org/2000/svg', 'line');
  legendLine.setAttribute('x1', '8');
  legendLine.setAttribute('x2', '28');
  legendLine.setAttribute('y1', '0');
  legendLine.setAttribute('y2', '0');
  legendLine.setAttribute('stroke', '#35d7ff');
  legendLine.setAttribute('stroke-width', '2.5');
  legendLine.setAttribute('stroke-linecap', 'round');
  const legendText = document.createElementNS('http://www.w3.org/2000/svg', 'text');
  legendText.setAttribute('x', '36');
  legendText.setAttribute('y', '4');
  legendText.setAttribute('fill', '#e7f0fa');
  legendText.setAttribute('stroke', 'none');
  legendText.setAttribute('font-family', 'DM Mono, monospace');
  legendText.setAttribute('font-size', '10');
  legendText.setAttribute('letter-spacing', '.8');
  legendText.textContent = 'PRICE CLOSE';
  legend.append(legendBackground, legendLine, legendText);
  svg.appendChild(legend);
  svg.dataset.lastPrice = String(price);
}

function renderSnapshotViews() {
  const price = snapshotPrice(state.snapshot);
  const chart = $('#live-candles');
  if (chart && price === null) {
    chart.querySelectorAll('.area, .line, .guide, .point, .live-candle').forEach((node) => node.remove());
  }
  const priceElement = $('#market-price');
  const orderPrice = $('#order-price');
  if (price === null) {
    if (priceElement) priceElement.textContent = '—';
    if (orderPrice) orderPrice.value = '';
    renderSnapshotMetrics(state.snapshot);
    setStaleBadge(false);
    return;
  }
  if (priceElement) priceElement.textContent = '$' + price.toFixed(2);
  if (orderPrice) orderPrice.value = price.toFixed(2);
  setStaleBadge(Boolean(snapshotSource(state.snapshot).stale ?? state.snapshot.stale));
  renderSnapshotMetrics(state.snapshot);
  renderCandles(state.snapshot);
}

async function updateSnapshot() {
  try {
    const params = new URLSearchParams({
      symbol: SNAPSHOT_SYMBOL,
      timeframe: SNAPSHOT_TIMEFRAME,
    });
    const response = await fetch('/api/snapshot?' + params.toString());
    if (!response.ok) throw new Error('snapshot unavailable');
    const snapshot = await readJson(response);
    const price = snapshotPrice(snapshot);
    if (price === null) throw new Error('snapshot has no last price');
    state.snapshot = snapshot;
    state.price = price;
    save();
    renderSnapshotViews();
    renderState();
    notify('Market snapshot refreshed');
  } catch (error) {
    state.snapshot = null;
    state.price = null;
    renderSnapshotViews();
    notify('Market snapshot unavailable');
  }
}

async function renderState() {
  let backendState = null;
  try {
    const response = await fetch('/api/paper/state');
    if (!response.ok) throw new Error('paper state unavailable');
    backendState = normalizePaperState(await readJson(response));
    if (!backendState) throw new Error('paper state has invalid shape');
    const positions = Object.values(backendState.positions)
      .map((position) => normalizePosition(position))
      .filter((position) => position !== null);
    state.position = positions[0] || null;
    // The backend currently exposes fills, not closed-trade PnL. Preserve
    // locally recorded closed trades until the backend exposes an audit trail.
    state.cash = Number.isFinite(Number(backendState.cash)) ? Number(backendState.cash) : null;
    state.equity = Number.isFinite(Number(backendState.equity)) ? Number(backendState.equity) : null;
    save();
  } catch (error) {
    backendState = null;
    state.position = null;
    state.cash = null;
    state.equity = null;
    state.trades = [];
    clearStoredState();
  }
  const equityElement = $('#paper-equity');
  const paperState = $('#paper-state');
  if (equityElement) equityElement.textContent = Number.isFinite(state.equity) ? '$' + state.equity.toFixed(2) : '—';
  if (paperState) {
    paperState.textContent = state.position ? '● ' + state.position.side : backendState ? '● flat' : '● waiting for backend';
    paperState.className = state.position ? 'cyan' : backendState ? 'up' : 'muted';
  }
  renderSnapshotViews();
}

function metrics() {
  const trades = state.trades;
  const wins = trades.filter((trade) => trade.pnl > 0);
  const pnl = trades.reduce((total, trade) => total + trade.pnl, 0);
  const gains = trades.filter((trade) => trade.pnl > 0).reduce((total, trade) => total + trade.pnl, 0);
  const losses = Math.abs(trades.filter((trade) => trade.pnl < 0).reduce((total, trade) => total + trade.pnl, 0));
  return { pnl, wins, rate: trades.length ? (wins.length / trades.length) * 100 : null, pf: losses ? gains / losses : null };
}

function bind() {
  $$('.rail-btn').forEach((button) => {
    button.onclick = () => {
      $$('.rail-btn').forEach((item) => item.classList.remove('active'));
      button.classList.add('active');
      const view = button.dataset.view;
      $('.content').innerHTML = views[view] || views.overview;
      bind();
      renderState();
      notify(view + ' workspace active');
    };
  });
  $('#refresh')?.addEventListener('click', updateSnapshot);
  $$('.tabs button').forEach((button) => button.onclick = () => {
    $$('.tabs button').forEach((item) => item.classList.remove('selected'));
    button.classList.add('selected');
    notify('Timeframe changed to ' + button.textContent);
  });
  $('#submit-order')?.addEventListener('click', async () => {
    const side = $('#order-side').value;
    const quantity = Number($('#order-qty').value);
    const price = Number($('#order-price').value);
    const stopLoss = Number($('#order-stop').value);
    const takeProfit = Number($('#order-target').value);
    const values = [quantity, price, stopLoss, takeProfit];
    if (values.some((value) => !Number.isFinite(value) || value <= 0)) {
      notify('Nhập quantity, entry, stop và target hợp lệ');
      return;
    }
    const body = {
      symbol: SNAPSHOT_SYMBOL,
      side,
      quantity,
      price,
      stop_loss: stopLoss,
      take_profit: takeProfit,
    };
    try {
      const response = await fetch('/api/paper/order', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify(body),
      });
      const data = await readJson(response);
      if (!response.ok) throw new Error(data.error || 'risk rejected');
      const orderId = requireOrderId(data);
      notify('Paper order filled · ' + orderId);
    } catch (error) {
      notify('Order rejected: ' + error.message);
    }
  });
  $$('.run-analysis').forEach((button) => button.onclick = async () => {
    notify('AI analysis running...');
    try {
      const response = await fetch('/api/analysis/run');
      const data = normalizeAnalysis(await readJson(response));
      if (!response.ok) throw new Error(data?.error || 'analysis failed');
      if (!data) throw new Error('Backend returned invalid analysis');
      const report = data.reports.find((item) => item.agent === 'technical_analyst');
      notify(report ? 'AI bias: ' + (report.bias || '—') + ' · confidence ' + (report.confidence || '—') : 'AI analysis completed');
    } catch (error) {
      notify('Analysis failed: ' + error.message);
    }
  });
  $('#paper-buy')?.addEventListener('click', () => openPaper('LONG'));
  $('#paper-sell')?.addEventListener('click', () => openPaper('SHORT'));
  $('#paper-close')?.addEventListener('click', closePaper);
  $('#reset-paper')?.addEventListener('click', () => {
    clearStoredState();
    location.reload();
  });
}

async function openPaper(side) {
  if (state.position) return notify('Đã có position đang mở');
  if (state.price === null) return notify('Market snapshot chưa sẵn sàng');
  const quantity = Number($('#order-qty')?.value);
  if (!Number.isFinite(quantity) || quantity <= 0) return notify('Nhập quantity hợp lệ trong order ticket');
  try {
    const response = await fetch('/api/paper/order', {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ symbol: SNAPSHOT_SYMBOL, side: side === 'LONG' ? 'buy' : 'sell', quantity, price: state.price }),
    });
    const data = await readJson(response);
    if (!response.ok) throw new Error(data.error || 'order rejected');
    requireOrderId(data);
    state.position = { side, entry: state.price, qty: quantity, opened: new Date().toISOString() };
    save();
    notify('Backend paper ' + side + ' opened');
    $('.content').innerHTML = views.positions;
    bind();
    renderState();
  } catch (error) {
    notify('Order rejected: ' + error.message);
  }
}

async function closePaper() {
  if (!state.position) return notify('Không có position để đóng');
  if (state.price === null) return notify('Market snapshot chưa sẵn sàng');
  try {
    const response = await fetch('/api/paper/order', {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({
        symbol: SNAPSHOT_SYMBOL,
        side: state.position.side === 'LONG' ? 'sell' : 'buy',
        quantity: state.position.qty,
        price: state.price,
      }),
    });
    const data = await readJson(response);
    if (!response.ok) throw new Error(data.error || 'close rejected');
    requireOrderId(data, true);
    const pnl = state.position.side === 'LONG'
      ? (state.price - state.position.entry) * state.position.qty
      : (state.position.entry - state.price) * state.position.qty;
    state.trades.push({ side: state.position.side, entry: state.position.entry, exit: state.price, pnl, closed: new Date().toISOString() });
    state.position = null;
    save();
    notify('Backend position closed · PnL $' + pnl.toFixed(2));
    $('.content').innerHTML = views.positions;
    bind();
    renderState();
  } catch (error) {
    notify('Close rejected: ' + error.message);
  }
}

const base = $('.content')?.innerHTML || '';
const views = {
  overview: base,
  council: `<div class="hero"><div><p class="eyebrow">AI COUNCIL <span>OFFLINE UNTIL RUN</span></p><h1>Decision intelligence<span class="cursor">_</span></h1><p class="sub">Phân tích AI và decision gate cho paper trading.</p></div></div><div class="grid"><article class="panel signal-panel"><div class="panel-head"><b>COUNCIL CONSENSUS</b><span class="badge">NO RUN DATA</span></div><div class="signal-main"><div class="orb"><div class="orb-core">—<small></small></div></div><div><small class="muted">CURRENT BIAS</small><h2>—</h2><p>Chưa có dữ liệu phân tích từ backend.</p></div></div><div class="agent"><span class="agent-icon cyan-bg">⌁</span><div><b>Sentiment Agent</b><small>Waiting for analysis response</small></div><strong class="muted">—</strong></div><button class="primary run-analysis">RUN FULL ANALYSIS <span>→</span></button></article><article class="panel positions"><div class="panel-head"><b>DECISION GATE</b><span class="badge">NO RUN DATA</span></div><div class="empty-state"><div class="empty-icon">◇</div><b>No decision data</b><span>Chạy phân tích để nhận quyết định backend.</span></div></article></div>`,
  positions: `<div class="hero"><div><p class="eyebrow">PAPER TRADING <span>SIMULATION</span></p><h1>Positions & execution<span class="cursor">_</span></h1><p class="sub">Mô phỏng cục bộ, dữ liệu được lưu trong trình duyệt.</p></div></div><div class="ticker"><div><small>EQUITY</small><strong>${Number.isFinite(state.equity) ? '$' + state.equity.toFixed(2) : '—'}</strong><span>paper backend</span></div><div><small>LAST PRICE</small><strong>${state.price === null ? '—' : '$' + state.price.toFixed(2)}</strong><span class="up">snapshot source</span></div><div><small>OPEN POSITIONS</small><strong>${state.position ? 1 : 0}</strong><span>${state.position ? state.position.side : 'flat'}</span></div><div><small>TRADES</small><strong>${state.trades.length}</strong><span>closed</span></div></div><article class="panel positions"><div class="panel-head"><b>EXECUTION CONSOLE</b><span class="badge">PAPER ONLY</span></div>${state.position ? `<div class="event"><time>${state.position.side}</time><span class="event-dot cyan-dot"></span><div><b>Entry $${state.position.entry.toFixed(2)}</b><small>Qty ${state.position.qty.toFixed(5)} BTC · opened ${new Date(state.position.opened).toLocaleTimeString()}</small></div><button class="primary" id="paper-close">CLOSE POSITION</button></div>` : `<div class="empty-state"><div class="empty-icon">◌</div><b>No open position</b><span>Chọn lệnh mô phỏng để kiểm tra execution và PnL.</span><div><button class="primary" id="paper-buy">PAPER BUY</button><button class="primary" id="paper-sell">PAPER SELL</button></div></div>`}</article><button class="primary" id="reset-paper">RESET PAPER ACCOUNT</button>`,
  performance: `<div class="hero"><div><p class="eyebrow">AI PERFORMANCE <span>REAL LOCAL DATA</span></p><h1>Hiệu quả AI trade<span class="cursor">_</span></h1><p class="sub">Metrics được tính từ paper trades đã đóng trên tài khoản này.</p></div></div><div class="ticker"><div><small>NET PNL</small><strong class="up">$${metrics().pnl.toFixed(2)}</strong><span>realized</span></div><div><small>WIN RATE</small><strong>${metrics().rate === null ? '—' : metrics().rate.toFixed(1) + '%'}</strong><span>${state.trades.length} closed trades</span></div><div><small>PROFIT FACTOR</small><strong>${metrics().pf === null ? '—' : metrics().pf.toFixed(2)}</strong><span>gross gain / loss</span></div><div><small>MAX DRAWDOWN</small><strong>—</strong><span>needs equity history</span></div></div><article class="panel activity"><div class="panel-head"><b>CLOSED TRADES</b><span class="badge">LOCAL PAPER DATA</span></div>${state.trades.length ? state.trades.slice().reverse().map((trade) => `<div class="event"><time>${trade.side}</time><span class="event-dot ${trade.pnl >= 0 ? 'green-dot' : 'cyan-dot'}"></span><div><b>${trade.pnl >= 0 ? '+' : ''}$${trade.pnl.toFixed(2)} PnL</b><small>Entry $${trade.entry.toFixed(2)} → Exit $${trade.exit.toFixed(2)}</small></div></div>`).join('') : `<div class="empty-state"><div class="empty-icon">◔</div><b>Chưa có trade đã đóng</b><span>Vào Positions để mở paper order và đo kết quả.</span></div>`}</article>`,
  journal: base,
};

// Remove the HTML fallback values before the first snapshot response arrives.
renderSnapshotViews();
bind();
renderState();
updateSnapshot();
setInterval(updateSnapshot, 15000);
