// GlintMesh live transport: native WebSocket to /ws/live with auto-reconnect.
// Transport only: routes server messages as window CustomEvents.
//   live:hello {conn, live, models, tick_seconds, agent?}
//   live:tick {symbol, price, change_percent, ts}
//   live:alert {symbol, price, condition, threshold, ts}
//   live:agent {kind, text} · live:sync {prefs} · live:subscribed {symbols}
//   live:open / live:close / live:status {code} / live:pong
export class LiveSocket {
  constructor(getToken) {
    this.getToken = getToken;
    this.ws = null;
    this.retry = 0;
    this.timer = null;
    this.pingTimer = null;
    this.symbols = [];
    this.watches = {};
    this.conn = null;
    this.wantClose = false;
  }

  url() {
    const proto = window.location.protocol === 'https:' ? 'wss' : 'ws';
    const token = (this.getToken && this.getToken()) || '';
    return proto + '://' + window.location.host + '/ws/live'
      + (token ? '?token=' + encodeURIComponent(token) : '');
  }

  connect() {
    this.wantClose = false;
    if (!this.ws || this.ws.readyState === WebSocket.CLOSED) this._open();
  }

  reconnect() {
    // token may have changed (login/logout): reopen with fresh query param
    this.wantClose = false;
    if (this.ws && this.ws.readyState !== WebSocket.CLOSED) {
      try { this.ws.close(); } catch (e) {}
    } else {
      this._open();
    }
  }

  close() {
    this.wantClose = true;
    clearTimeout(this.timer);
    this._pingStop();
    try { this.ws && this.ws.close(); } catch (e) {}
  }

  subscribe(symbols, watches) {
    const clean = [...new Set((symbols || []).map((s) => String(s || '').toUpperCase()))]
      .filter(Boolean).slice(0, 20);
    this.symbols = clean;
    this.watches = watches || {};
    if (this.ws && this.ws.readyState === WebSocket.OPEN) this._resubscribe();
  }

  send(obj) {
    try {
      if (this.ws && this.ws.readyState === WebSocket.OPEN) this.ws.send(JSON.stringify(obj));
    } catch (e) {}
  }

  _open() {
    clearTimeout(this.timer);
    let ws;
    try {
      ws = new WebSocket(this.url());
    } catch (e) {
      this._retry();
      return;
    }
    this.ws = ws;
    ws.onopen = () => {
      this.retry = 0;
      this._emit('live:open');
      this._pingStart();
      this._resubscribe();
    };
    ws.onmessage = (ev) => {
      let msg;
      try { msg = JSON.parse(ev.data); } catch (e) { return; }
      this._route(msg);
    };
    ws.onclose = () => {
      this._pingStop();
      this._emit('live:close');
      if (!this.wantClose) this._retry();
    };
    ws.onerror = () => {
      try { ws.close(); } catch (e) {}
    };
  }

  _retry() {
    const delay = Math.min(30000, 1000 * (2 ** this.retry++));
    clearTimeout(this.timer);
    this.timer = setTimeout(() => { if (!this.wantClose) this._open(); }, delay);
  }

  _resubscribe() {
    if (this.symbols.length || Object.keys(this.watches).length) {
      this.send({ op: 'subscribe', symbols: this.symbols, watches: this.watches });
    }
  }

  _pingStart() {
    this._pingStop();
    this.pingTimer = setInterval(() => this.send({ op: 'ping' }), 25000);
  }

  _pingStop() {
    if (this.pingTimer) { clearInterval(this.pingTimer); this.pingTimer = null; }
  }

  _route(msg) {
    if (!msg || typeof msg.type !== 'string') return;
    if (msg.type === 'hello') this.conn = msg.conn || null;
    const map = {
      hello: 'live:hello', tick: 'live:tick', alert: 'live:alert',
      agent: 'live:agent', sync: 'live:sync', subscribed: 'live:subscribed',
      pong: 'live:pong', status: 'live:status',
    };
    const name = map[msg.type];
    if (name) this._emit(name, msg);
  }

  _emit(name, detail) {
    window.dispatchEvent(new CustomEvent(name, { detail: detail || {} }));
  }
}
