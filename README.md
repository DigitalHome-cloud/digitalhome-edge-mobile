# digitalhome-edge-mobile

A phone as the edge of [DigitalHome.cloud](https://github.com/DigitalHome-cloud): any Android phone with Chrome (an old one is
fine) becomes the home's screen, camera and code reader. It needs no app: a small server on a PC or a Pi serves a web page to
the phone (by USB, or on the Wi-Fi by QR code) and passes what the person does to the backends, **Node-RED** first, and
**MQTT** or **ROS 2** for other IoT and robot scenarios.

```
 phone (Chrome)                    edge (this repository, Python)                  backends
 ┌──────────────┐  USB: localhost  ┌──────────────────────────────┐  /ws/backend   ┌──────────────────────────┐
 │ tiles, steps │  Wi-Fi: https+QR │ pages · phone link · profile │ ─────────────▶ │ Node-RED (node-red-      │
 │ camera, OCR, │ ◀──────────────▶ │ states · protocol check      │                │ contrib-dhc-edge) → DHC   │
 │ code reader  │  WebSocket /ws   │ adapters: nodered mqtt ros2  │ ─ MQTT ──────▶ │ any broker / IoT          │
 └──────────────┘                  └──────────────────────────────┘ ─ ROS 2 ─────▶ │ robots                    │
                                     setup.html: the test console                  └──────────────────────────┘
```

The phone decides nothing and keeps nothing: it shows a **profile**, big tiles in the style of atl-phone's Omi Assist, and
sends one event per tile. What a tile means is decided by the backend, which answers with states, words and questions. Codes
and type-plate text are read *on the phone*; a photo leaves the phone only when a person takes it for a photo step.

It is derived from [atl-phone](https://github.com/Atelier-5) (Atelier-5's old phone as a robot's face): the same server, link,
setup page and tile style, with ROS 2 swapped for pluggable adapters (NOTICE.md).

## Templates (profiles)

| profile      | what for | tiles |
|---|---|---|
| `inventory`  | photograph each appliance and its type plate, for the home's inventory | New appliance (room → photo → plate photo + OCR → note → review), Scan a tag, Read a plate, Recorded |
| `checkinout` | things with a code going in and out of a store | Check in (scan → how many → where), Check out, What is it?, In stock |
| `cellar`     | the wine cellar (extends `checkinout`) | bottles by rack, a rating when one is opened |
| `library`    | the home library (extends `checkinout`) | books by ISBN and shelf, lent to someone |
| `switch`     | an intelligent switch with a display | lights (toggle), scene, blinds, temperature, all off |
| `blank`      | the smallest one, to copy | Hello, Status |

A profile is a JSON file in `profiles/`: tiles, each with one action (`send`, `toggle`, `state`, `choice`, `number`, `scan`,
`photo`, `text`, `say`, or `steps` that chain several). All words in English, French and German. [docs/profiles.md](docs/profiles.md)
describes every field; a backend may change tiles at run time (for example the rooms of the home, from DigitalHome.cloud).

## Quick start

```bash
./start.sh --profile inventory          # Docker; or --venv for no Docker. Opens http://localhost:8790/setup.html
./scripts/usb.sh                        # a phone on USB (USB debugging on): the page opens, tap ▶
./start.sh --make-cert                  # Wi-Fi with HTTPS (the camera needs it): the setup page shows the QR codes
./start.sh token                        # the backends' token (kept in .edge/token)
./start.sh stop | logs
```

The setup page is the test console: the edge and its adapters, connecting a phone (USB or Wi-Fi by QR code, the certificate
authority to install once), the profile (a tap there pretends to be the phone, to try a flow without one), the events the
backends get (photos included), and a box to send commands as a backend would.

### Node-RED (DigitalHome.cloud)

On the Node-RED machine: `npm install <this repo>/node-red/node-red-contrib-dhc-edge` in `~/.node-red` (or from git), restart
Node-RED, then import an example (Menu › Import › Examples › node-red-contrib-dhc-edge: `inventory`, `checkinout`, `switch`).
Open the **dhc edge** config node: the address `ws://<edge>:8790/ws/backend` (the setup page shows it) and the token.

- **edge in**: one message per event; filters by kind (`tile`, `hello`, `bye`, `answer`, `status`, `profile`, `error`) and by
  tile; photos as base64, Buffers, or dropped. `msg.topic` is `<edge>/tile/<tile>`, `msg.data` what the steps got.
- **edge out**: a command: `msg.payload` as the whole command, or a kind (`say`, `toast`, `state`, `ask`, `profile`, `tiles`,
  `vibrate`, `open`, `home`) that `msg.payload` fills.

The inventory example POSTs each record to `$DHC_API/inventory` (a mock endpoint in the same flow when `DHC_API` is not set).

### MQTT, ROS 2

```bash
./start.sh --profile switch --adapter nodered,mqtt --mqtt 192.168.1.10:1883   # or --broker: a Mosquitto in Docker
./start.sh --profile cellar --adapter ros2,nodered                            # docker/Dockerfile.ros2 (Kilted)
```

MQTT: `dhc/edge/<edge>/event/<t>`, commands on `dhc/edge/<edge>/command`, `dhc/edge/<edge>/status` retained (last will:
offline). ROS 2: `std_msgs/String` JSON on `/dhc_edge/<edge>/event` and `/dhc_edge/<edge>/command`. The same JSON everywhere:
[docs/contract.md](docs/contract.md). A new transport is one class: [docs/adapters.md](docs/adapters.md).

### On a Pi or a home server

`docker compose up -d` (compose.yaml: restarts after a reboot; `DHC_PROFILE`, `DHC_ADAPTERS`, `DHC_MQTT`, `DHC_EDGE_ID`;
`--profile broker` adds a Mosquitto). Run `./start.sh token` once first.

## Layout

```
dhc_edge/            the edge (standard library; paho-mqtt for mqtt, rclpy for ros2)
  wsserver.py          pages, the phone's WebSocket, the backends' WebSocket, the setup API (from atl-phone)
  protocol.py          every message checked both ways         contract.py  names, topics
  core.py              the phone, the profile, the states, events to the adapters, commands from them
  profiles.py          load, extend and check profiles          adapters/   nodered, mqtt, ros2
  mock_phone.py        a phone without a phone (tests)          contract_check.py  a running edge, end to end
web/                 app.html + app.js + actions.js (the phone), setup.html (the console), check.html (the phone check)
profiles/            the templates                              node-red/   node-red-contrib-dhc-edge, with examples
docs/                contract, profiles, adapters; architecture/ (Archify pack, served at /docs/)
scripts/             usb.sh, make_cert.sh, browser_check.py, nodered_check.py, make_icons.py
```

## Checks

```bash
./test.sh                     # pytest (protocol, profiles, core, adapters: mqtt against its own Mosquitto) + the Node-RED nodes
./test.sh --browser           # + headless Chrome as the phone: steps, a photo, OCR, a barcode read from a fake camera
python3 scripts/nodered_check.py --node-red <dir>/node_modules/node-red/red.js   # the examples in a real Node-RED
python -m dhc_edge.contract_check --token-file .edge/token                      # a running edge (--via mqtt)
```

## Licence

GPL-3.0-or-later (LICENSE). Vendored libraries: web/vendor/README.md. NOTICE.md says what comes from atl-phone.
