# Contract dhc-edge/0.1

The messages between the phone, the edge and the backends. `dhc_edge/protocol.py` checks every message both ways
(`parse()` for the phone, `command()` for a backend); `dhc_edge/contract.py` holds the names. Every adapter carries the same
JSON, so a flow written against Node-RED works the same over MQTT or ROS 2.

**Versioning.** While 0.x, a change that breaks a reader raises the minor version (0.1 → 0.2), and the change is listed at
the end of this file. Every event carries `"v": "dhc-edge/0.1"`; the profile the phone gets carries `"contract"`.

## Events (edge → backends)

Every event has:

| field | |
|---|---|
| `v` | `"dhc-edge/0.1"` |
| `edge` | the edge's name (`--edge-id`, default `edge`) |
| `t` | the kind, below |
| `profile` | the id of the profile shown |
| `ts` | seconds since 1970, with milliseconds |
| `n` | a counter, one per event since the edge started (not on `status`) |

| `t` | when | its own fields |
|---|---|---|
| `status` | a backend connects (nodered: its first message; mqtt: retained on `…/status`; ros2: transient local) | `phone` (or null), `states` {tile: value}, `tiles` [ids], `adapters` [names] |
| `hello` | a phone came (or reloaded) | `phone`: `{id, model, link: "usb"\|"wifi", secure, caps}` |
| `bye` | the phone went | `phone`: `{id, model}` |
| `tile` | a person used a tile | `tile`, `action`, `label`; `value` (toggle: the state asked for); `data` (below) |
| `answer` | a person answered an `ask` | `ask` (its id), `value` (the option's id) |
| `profile` | the profile changed | `title`, `tiles` [ids] |
| `error` | a command was refused (to the backend that sent it only) | `error` (why), `source` (the adapter), `id` (the command's, if it had one) |

### A tile's data

`data` holds what the person entered, by step id. A single input tile (`choice`, `number`, `scan`, `photo`, `text` without
steps) puts it under its own id. The profile's fixed `data` of a `send` or `steps` tile comes along, under what was entered.

| part | from | form |
|---|---|---|
| text | `text`, a `choice` (the option's id) | `"kitchen"` |
| number | `number` | `2.0` |
| code | `scan` | `{"code": "4006381333931", "format": "ean_13"}` (`format`: BarcodeDetector's names; `typed` when keyed in) |
| photo | `photo` | `{"jpeg": "<base64>", "w": 1280, "h": 960, "text": "what OCR read (with ocr)"}` |

Limits: 12 parts, 2 photos per event, 1400 KB of base64 per photo (the phone lowers the JPEG quality until it fits),
2000 characters of OCR text, 500 of a note.

```json
{"v": "dhc-edge/0.1", "edge": "hall", "t": "tile", "profile": "inventory", "ts": 1793650000.123, "n": 7,
 "tile": "appliance", "action": "steps", "label": {"en": "New appliance", "fr": "Nouvel appareil", "de": "Neues Gerät"},
 "data": {"kind": "appliance", "room": "kitchen", "photo": {"jpeg": "/9j/4AAQ…", "w": 1280, "h": 720},
          "plate": {"jpeg": "/9j/4AAQ…", "w": 1280, "h": 720, "text": "BOSCH SMS46\n230 V 50 Hz"}, "note": ""}}
```

## Commands (backends → edge)

A command is a JSON object with `t`. It may carry an `id` of the backend's own: a refused command comes back as an `error`
event with it. Labels (`text` of toast and ask, option labels) are text or `{"en", "fr", "de"}`: the phone picks its language.

| `t` | fields | does |
|---|---|---|
| `state` | `tile`, `value` (text, number, true/false, null), or `states` {tile: value}; `label` (a word under it) | sets what tiles show; the edge keeps it for a phone that comes back. A toggle waits for it after a tap |
| `toast` | `text` (label), `ms` (500–60000, default 4000) | written big for a moment |
| `say` | `text`, `lang` | said by the phone's voice |
| `ask` | `ask` (an id), `text` (label), `options` [{id, label, icon}] (default yes/no), `say` (default true) | a card with big answers; the answer comes as an `answer` event |
| `vibrate` | `ms` (0–2000) | |
| `profile` | `profile` (an id in `profiles/`) | another template; the states start empty |
| `tiles` | `tiles` [tile objects, each with its `id`] | changes tiles of the profile shown (field by field) or adds them; checked as a profile |
| `open` | `page`: `app.html` or `check.html` | sends the phone to the tiles or to the phone check |
| `home` | | ends any steps and question: back to the tiles |

`toast`, `say`, `ask`, `vibrate`, `open` and `home` need a phone: without one they come back as an `error` ("no phone").

```json
{"t": "state", "tile": "count", "value": 12, "label": {"en": "today", "de": "heute"}}
{"t": "tiles", "tiles": [{"id": "appliance", "steps": [{"id": "room", "action": "choice", "options": [{"id": "attic", "label": "Attic"}]}]}]}
```

## Phone ↔ edge

The phone's page (`web/app.js`) and the edge, on `/ws` (one phone at a time: a new one takes over, the old one is closed
with code 4000 and stays quiet).

| phone → edge | |
|---|---|
| `{"t": "hello", "id", "ua", "model", "secure", "caps", "screen", "lang"}` | on each connection |
| `{"t": "tile", "tile", "value"?, "data"?}` | a tile used |
| `{"t": "answer", "id", "value"}` | an answer to `ask` |

| edge → phone | |
|---|---|
| `{"t": "web", "id"}` | the pages' fingerprint: a page from an older edge reloads |
| `{"t": "profile", "profile", "states", "labels", "lang"}` | the profile (checked), what its tiles show, the language |
| `state`, `toast`, `say`, `ask`, `vibrate`, `open`, `home` | the commands above, as the backend sent them (`ask`'s id as `id`) |

## Transports

| adapter | events | commands |
|---|---|---|
| `nodered` | WebSocket `ws(s)://<edge>:8790/ws/backend`, one text frame each; token as `Authorization: Bearer <token>` or `?token=` | text frames on the same link |
| `mqtt` | `<prefix>/<edge>/event/<t>` QoS 1; `status` retained on `<prefix>/<edge>/status`, last will `{"t": "offline"}` | `<prefix>/<edge>/command` |
| `ros2` | `/dhc_edge/<edge>/event` (`std_msgs/String`, JSON; transient local, depth 10) | `/dhc_edge/<edge>/command` |

`<prefix>` is `dhc/edge` unless `--mqtt-prefix` says otherwise.

## Changes

- 0.1 (2026-11-02): the first version.
