// SPDX-License-Identifier: GPL-3.0-or-later
// Copyright (C) 2026 DigitalHome.cloud
// "dhc edge out": a command to the edge (contract dhc-edge/0.1). Either msg.payload is the whole command
// ({"t": "say", "text": ...}), or the node's command kind is set and msg.payload fills it:
//   say, toast   payload: the text ({en, fr, de} for a toast)        state   payload: the value of the tile (msg.tile,
//   profile      payload: the profile's id                                   msg.topic's last part, or the node's
//   tiles        payload: [tiles]                                            tile); or {tile: value, ...} for several
//   ask          payload: {ask, text, options}                       vibrate payload: ms
//   open         payload: app.html or check.html                     home    (no payload)
'use strict';
const { statusOf } = require('./edge-config');

function command(kind, msg, tile) {
  const p = msg.payload;
  switch (kind) {
    case 'say': return { t: 'say', text: String(p), ...(msg.lang ? { lang: msg.lang } : {}) };
    case 'toast': return { t: 'toast', text: p, ...(msg.ms ? { ms: msg.ms } : {}) };
    case 'state': {
      const id = msg.tile || tile || (typeof msg.topic === 'string' ? msg.topic.split('/').pop() : '');
      if (p && typeof p === 'object' && !Array.isArray(p) && !id) return { t: 'state', states: p };
      return { t: 'state', tile: id, value: p, ...(msg.label ? { label: msg.label } : {}) };
    }
    case 'profile': return { t: 'profile', profile: String(p) };
    case 'tiles': return { t: 'tiles', tiles: Array.isArray(p) ? p : [p] };
    case 'ask': return Object.assign({ t: 'ask' }, p);
    case 'vibrate': return { t: 'vibrate', ms: Number(p) || 200 };
    case 'open': return { t: 'open', page: String(p || 'app.html') };
    case 'home': return { t: 'home' };
    default: return p;   // "payload": the whole command
  }
}

module.exports = function (RED) {
  function EdgeOut(config) {
    RED.nodes.createNode(this, config);
    const node = this, edge = RED.nodes.getNode(config.edge);
    if (!edge) { node.status({ fill: 'red', shape: 'ring', text: 'no edge' }); return; }
    const watch = (s, d) => node.status(statusOf(s, d));
    edge.watchers.add(watch);
    watch(edge.state);
    node.on('input', (msg, send, done) => {
      const cmd = command(config.command || 'payload', msg, config.tile);
      if (!cmd || typeof cmd !== 'object' || !cmd.t) return done(new Error('not a command: ' + JSON.stringify(cmd)));
      if (!edge.send(cmd)) return done(new Error('the edge is not connected'));
      done();
    });
    node.on('close', () => edge.watchers.delete(watch));
  }
  RED.nodes.registerType('dhc-edge-out', EdgeOut);
};
module.exports.command = command;
