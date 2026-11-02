// SPDX-License-Identifier: GPL-3.0-or-later
// Copyright (C) 2026 DigitalHome.cloud
// "dhc edge in": the edge's events, one message each. msg.payload is the event (contract dhc-edge/0.1), msg.topic
// "<edge>/<t>" or "<edge>/tile/<tile>"; msg.tile, msg.data for a tile. Filters: the kinds of event, and the tiles.
// Photos: as the edge sends them (base64), as Buffers (for a file or an HTTP upload), or dropped.
'use strict';
const { statusOf } = require('./edge-config');

function photos(e, mode) {
  if (!e.data || mode === 'base64') return e;
  const data = {};
  for (const [k, v] of Object.entries(e.data)) {
    if (v && typeof v === 'object' && typeof v.jpeg === 'string') {
      if (mode === 'drop') data[k] = Object.assign({}, v, { jpeg: undefined, bytes: Math.floor(v.jpeg.length * 3 / 4) });
      else data[k] = Object.assign({}, v, { jpeg: Buffer.from(v.jpeg, 'base64') });
    } else data[k] = v;
  }
  return Object.assign({}, e, { data });
}

module.exports = function (RED) {
  function EdgeIn(config) {
    RED.nodes.createNode(this, config);
    const node = this, edge = RED.nodes.getNode(config.edge);
    const kinds = (config.events || 'tile').split(',').map((s) => s.trim()).filter(Boolean);
    const tiles = (config.tiles || '').split(',').map((s) => s.trim()).filter(Boolean);
    const mode = config.photos || 'base64';
    if (!edge) { node.status({ fill: 'red', shape: 'ring', text: 'no edge' }); return; }
    const watch = (s, d) => node.status(statusOf(s, d));
    const hear = (e) => {
      if (kinds.indexOf('all') < 0 && kinds.indexOf(e.t) < 0) return;
      if (tiles.length && e.t === 'tile' && tiles.indexOf(e.tile) < 0) return;
      const ev = photos(e, mode);
      const msg = { payload: ev, topic: e.edge + '/' + e.t + (e.tile ? '/' + e.tile : ''), edge: e.edge, profile: e.profile };
      if (e.tile) { msg.tile = e.tile; msg.data = ev.data || {}; if ('value' in e) msg.value = e.value; }
      node.send(msg);
    };
    edge.watchers.add(watch); edge.subscribers.add(hear);
    watch(edge.state);
    if (edge.lastStatus && (kinds.indexOf('status') >= 0 || kinds.indexOf('all') >= 0)) hear(edge.lastStatus);
    node.on('close', () => { edge.watchers.delete(watch); edge.subscribers.delete(hear); });
  }
  RED.nodes.registerType('dhc-edge-in', EdgeIn);
};
module.exports.photos = photos;
