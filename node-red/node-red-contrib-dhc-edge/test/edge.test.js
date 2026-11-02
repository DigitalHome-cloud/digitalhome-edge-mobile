// SPDX-License-Identifier: GPL-3.0-or-later
// Copyright (C) 2026 DigitalHome.cloud
// The nodes without Node-RED: a small RED, and a WebSocket server in place of the edge. `npm test` (node --test).
'use strict';
const test = require('node:test');
const assert = require('node:assert');
const { EventEmitter } = require('node:events');
const { WebSocketServer } = require('ws');

function fakeRED() {
  const types = {}, nodes = {};
  return {
    types, nodes,
    nodes: Object.assign(nodes, {
      createNode(node, config) {
        EventEmitter.call(node);
        Object.setPrototypeOf(node, Object.assign(Object.create(EventEmitter.prototype), Object.getPrototypeOf(node)));
        node.id = config.id; node.sent = []; node.statuses = [];
        node.send = (m) => node.sent.push(m);
        node.status = (s) => node.statuses.push(s);
        node.credentials = config.credentials;
      },
      registerType(name, ctor) { types[name] = ctor; },
      getNode(id) { return nodes[id]; }
    })
  };
}
function load(RED) {
  require('../edge-config')(RED); require('../edge-in')(RED); require('../edge-out')(RED);
}
function make(RED, type, config) {
  const n = new RED.types[type](config);
  RED.nodes[config.id] = n;
  return n;
}
function until(f, ms = 3000) {
  return new Promise((ok, no) => {
    const t0 = Date.now();
    (function poll() { const v = f(); if (v) return ok(v); if (Date.now() - t0 > ms) return no(new Error('timeout')); setTimeout(poll, 20); })();
  });
}
async function close(node) {  // as Node-RED does: a handler with a parameter says when it is done
  for (const f of node.listeners('close')) await new Promise((ok) => { if (f.length >= 1) f.call(node, ok); else { f.call(node); ok(); } });
}

test('in and out nodes through a config node', async () => {
  const wss = new WebSocketServer({ port: 0 });
  const got = [], auth = [];
  let client = null;
  wss.on('connection', (ws, req) => {
    auth.push(req.headers.authorization); client = ws;
    ws.send(JSON.stringify({ v: 'dhc-edge/0.1', edge: 'e1', t: 'status', profile: 'switch', phone: null }));
    ws.on('message', (d) => got.push(JSON.parse(d.toString())));
  });
  await new Promise((ok) => wss.on('listening', ok));
  const RED = fakeRED(); load(RED);
  const cfg = make(RED, 'dhc-edge-config', { id: 'c', url: 'ws://127.0.0.1:' + wss.address().port + '/ws/backend', credentials: { token: 'tk' } });
  const inAll = make(RED, 'dhc-edge-in', { id: 'i', edge: 'c', events: 'tile', tiles: '' });
  const inPhoto = make(RED, 'dhc-edge-in', { id: 'p', edge: 'c', events: 'tile', tiles: 'appliance', photos: 'buffer' });
  const inStatus = make(RED, 'dhc-edge-in', { id: 's', edge: 'c', events: 'status,hello' });
  const out = make(RED, 'dhc-edge-out', { id: 'o', edge: 'c', command: 'state', tile: '' });
  const raw = make(RED, 'dhc-edge-out', { id: 'r', edge: 'c', command: 'payload' });
  await until(() => cfg.state === 'connected' && client);
  assert.strictEqual(auth[0], 'Bearer tk');
  await until(() => inStatus.sent.length === 1);
  assert.strictEqual(inStatus.sent[0].topic, 'e1/status');
  assert.deepStrictEqual(inAll.statuses.pop(), { fill: 'green', shape: 'dot', text: 'connected' });

  client.send(JSON.stringify({ edge: 'e1', t: 'tile', tile: 'ceiling', action: 'toggle', value: true, profile: 'switch' }));
  client.send(JSON.stringify({ edge: 'e1', t: 'tile', tile: 'appliance', profile: 'inventory', data: { room: 'bath', photo: { jpeg: '/9j/AA==', w: 1, h: 1 } } }));
  await until(() => inAll.sent.length === 2);
  assert.strictEqual(inAll.sent[0].topic, 'e1/tile/ceiling');
  assert.strictEqual(inAll.sent[0].value, true);
  assert.strictEqual(inPhoto.sent.length, 1);
  assert.ok(Buffer.isBuffer(inPhoto.sent[0].data.photo.jpeg));
  assert.strictEqual(inPhoto.sent[0].data.photo.jpeg[0], 0xff);
  assert.strictEqual(inAll.sent[1].data.photo.jpeg, '/9j/AA==');   // the other node's copy is untouched

  const done = [];
  out.emit('input', { payload: true, topic: 'e1/tile/ceiling' }, null, (e) => done.push(e));
  out.emit('input', { payload: { temp: 21, ceiling: false } }, null, (e) => done.push(e));
  raw.emit('input', { payload: { t: 'say', text: 'Hallo', lang: 'de' } }, null, (e) => done.push(e));
  raw.emit('input', { payload: 'nonsense' }, null, (e) => done.push(e));
  await until(() => got.length === 3);
  assert.deepStrictEqual(got[0], { t: 'state', tile: 'ceiling', value: true });
  assert.deepStrictEqual(got[1], { t: 'state', states: { temp: 21, ceiling: false } });
  assert.deepStrictEqual(got[2], { t: 'say', text: 'Hallo', lang: 'de' });
  assert.ok(done[3] instanceof Error);

  for (const n of [inAll, inPhoto, inStatus, out, raw, cfg]) await close(n);
  wss.close();
});

test('a refused token shows on the nodes', async () => {
  const http = require('node:http');
  const server = http.createServer((req, res) => { res.writeHead(403); res.end(); });
  await new Promise((ok) => server.listen(0, ok));
  const RED = fakeRED(); load(RED);
  const cfg = make(RED, 'dhc-edge-config', { id: 'c', url: 'ws://127.0.0.1:' + server.address().port + '/ws/backend', credentials: { token: 'bad' } });
  const n = make(RED, 'dhc-edge-in', { id: 'i', edge: 'c', events: 'tile' });
  await until(() => n.statuses.some((s) => s.text === 'refused: HTTP 403'));
  await close(n); await close(cfg);
  server.close();
});

test('the out node builds each command', () => {
  const { command } = require('../edge-out');
  assert.deepStrictEqual(command('say', { payload: 'Hi', lang: 'en' }), { t: 'say', text: 'Hi', lang: 'en' });
  assert.deepStrictEqual(command('toast', { payload: { en: 'ok' }, ms: 900 }), { t: 'toast', text: { en: 'ok' }, ms: 900 });
  assert.deepStrictEqual(command('state', { payload: 3, tile: 'stock', label: 'bottles' }), { t: 'state', tile: 'stock', value: 3, label: 'bottles' });
  assert.deepStrictEqual(command('state', { payload: 3 }, 'count'), { t: 'state', tile: 'count', value: 3 });
  assert.deepStrictEqual(command('profile', { payload: 'cellar' }), { t: 'profile', profile: 'cellar' });
  assert.deepStrictEqual(command('tiles', { payload: { id: 'x' } }), { t: 'tiles', tiles: [{ id: 'x' }] });
  assert.deepStrictEqual(command('home', {}), { t: 'home' });
  assert.deepStrictEqual(command('vibrate', { payload: 'x' }), { t: 'vibrate', ms: 200 });
});

test('the example flows wire up', () => {
  const fs = require('node:fs'), path = require('node:path');
  for (const f of fs.readdirSync(path.join(__dirname, '..', 'examples'))) {
    const flow = JSON.parse(fs.readFileSync(path.join(__dirname, '..', 'examples', f)));
    const ids = new Set(flow.map((n) => n.id));
    for (const n of flow) {
      for (const w of n.wires || []) for (const to of w) assert.ok(ids.has(to), f + ': ' + n.id + ' -> ' + to);
      if (n.edge) assert.ok(ids.has(n.edge), f + ': ' + n.id + ' has no edge');
      if (n.type === 'function') new Function('msg', 'flow', 'env', 'node', n.func);   // it parses
    }
  }
});
