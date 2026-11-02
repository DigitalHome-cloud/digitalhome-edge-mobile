// SPDX-License-Identifier: GPL-3.0-or-later
// Copyright (C) 2026 DigitalHome.cloud
// "dhc edge": one edge's link, shared by its in and out nodes. A WebSocket to ws(s)://<edge>:8790/ws/backend with the
// token (Authorization: Bearer), reconnecting by itself; the edge's events go to every in node, commands from the out
// nodes go to the edge (contract dhc-edge/0.1, docs/contract.md in the edge's repository).
'use strict';
const WebSocket = require('ws');

module.exports = function (RED) {
  function EdgeConfig(config) {
    RED.nodes.createNode(this, config);
    const node = this;
    node.url = config.url;
    node.name = config.name;
    node.insecure = !!config.insecure;   // wss with the edge's own certificate authority, not installed on this PC
    node.subscribers = new Set();        // in nodes: fn(event) (not "listeners": an EventEmitter method)
    node.watchers = new Set();           // every node: fn(state) for its status
    node.state = 'connecting';
    node.lastStatus = null;              // the edge's last "status" event
    let ws = null, retry = 1000, timer = null, closing = false;

    function setState(s, detail) {
      node.state = s;
      node.watchers.forEach((f) => f(s, detail));
    }
    function connect() {
      const token = (node.credentials || {}).token || '';
      ws = new WebSocket(node.url, { headers: token ? { Authorization: 'Bearer ' + token } : {}, rejectUnauthorized: !node.insecure,
                                     maxPayload: 8 * 1024 * 1024 });
      ws.on('open', () => { retry = 1000; setState('connected'); });
      ws.on('message', (data) => {
        let e;
        try { e = JSON.parse(data.toString()); } catch (x) { return; }
        if (e.t === 'status') node.lastStatus = e;
        node.subscribers.forEach((f) => f(e));
      });
      ws.on('unexpected-response', (req, res) => {   // 403: a wrong token; ws leaves the request to us: end it, retry later
        setState('refused', 'HTTP ' + res.statusCode);
        ws.terminate();
      });
      ws.on('error', (err) => { if (node.state !== 'refused') setState('error', err.message); });
      ws.on('close', () => {
        ws = null;
        if (closing) return;
        if (node.state === 'connected') setState('connecting');
        timer = setTimeout(connect, retry);
        retry = Math.min(retry * 2, 30000);
      });
    }
    node.send = function (cmd) {  // true when it went out
      if (!ws || ws.readyState !== WebSocket.OPEN) return false;
      ws.send(JSON.stringify(cmd));
      return true;
    };
    node.on('close', (done) => {
      closing = true;
      clearTimeout(timer);
      if (ws) { ws.once('close', () => done()); ws.close(1000); } else done();
    });
    if (node.url) connect(); else setState('error', 'no address');
  }
  RED.nodes.registerType('dhc-edge-config', EdgeConfig, { credentials: { token: { type: 'password' } } });
};

module.exports.statusOf = function (state, detail) {  // for the in and out nodes
  if (state === 'connected') return { fill: 'green', shape: 'dot', text: 'connected' };
  if (state === 'connecting') return { fill: 'yellow', shape: 'ring', text: 'connecting' };
  return { fill: 'red', shape: 'ring', text: state + (detail ? ': ' + detail : '') };
};
