# node-red-contrib-dhc-edge

Node-RED nodes for a [DigitalHome.cloud phone edge](../../README.md) (contract `dhc-edge/0.1`): what happens on the phone
comes in as messages, and commands go out to it.

```bash
cd ~/.node-red && npm install <path or git URL of digitalhome-edge-mobile>/node-red/node-red-contrib-dhc-edge
```

Restart Node-RED. The nodes are in the palette's **DigitalHome** group; the examples are under Menu › Import › Examples.

| node | |
|---|---|
| **dhc edge** (config) | the edge's address `ws://<edge>:8790/ws/backend` and its token (`./start.sh token` on the edge) |
| **edge in** | one message per event. Filter by kind (`tile`, `hello`, `bye`, `answer`, `status`, `profile`, `error`, `all`) and tiles. `msg.payload`: the event; `msg.topic`: `<edge>/tile/<tile>`; `msg.tile`, `msg.data`, `msg.value`. Photos as base64, Buffers or dropped |
| **edge out** | a command: `msg.payload` is the whole command, or pick a kind (`say`, `toast`, `state`, `ask`, `profile`, `tiles`, `vibrate`, `open`, `home`) that `msg.payload` fills. `state` takes its tile from the node, `msg.tile` or the last part of `msg.topic` |

## Examples

- **inventory**: each new appliance becomes a record (room, photos, the plate's text, a note) POSTed to `$DHC_API/inventory`
  (a mock endpoint in the flow when unset); the phone hears "Saved ✓" and its *Recorded* tile counts.
- **checkinout**: in, out and lookup keep a stock in flow context (for `checkinout`, `cellar`, `library`).
- **switch**: lights follow the taps, scenes, blinds, "all off", and a (simulated) thermometer every 30 s.

`npm test` checks the nodes without Node-RED; `scripts/nodered_check.py` in the repository runs the examples in a real
Node-RED against a real edge.

GPL-3.0-or-later. Depends on `ws` (MIT).
