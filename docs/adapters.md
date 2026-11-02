# Adapters: how the edge reaches its backends

The core (`dhc_edge/core.py`) knows nothing of transports: it hands each event to every adapter that is on, and takes
commands from any of them. `--adapter nodered,mqtt,ros2` picks them; they all carry the same JSON ([contract.md](contract.md)).

| adapter | for | needs | tested by |
|---|---|---|---|
| `nodered` | Node-RED (node-red-contrib-dhc-edge), any WebSocket client | nothing (standard library) | tests/test_adapters.py, scripts/nodered_check.py (a real Node-RED) |
| `mqtt` | any broker: Mosquitto, an IoT platform, Home Assistant | paho-mqtt 2.1.0 (in the image; `pip install paho-mqtt==2.1.0` in a venv) | tests/test_adapters.py, against a Mosquitto it starts |
| `ros2` | robots | rclpy, std_msgs: docker/Dockerfile.ros2 (Kilted) | tests/test_adapters.py, in that image or a sourced ROS 2 (Foxy works too) |

## Node-RED

The edge serves `/ws/backend` on its own port; up to 8 backends at once (a test console, two flows). The token (`--token`,
`--token-file`; `./start.sh` keeps one in `.edge/token`) is asked as `Authorization: Bearer` or `?token=`; without a token
only this machine may connect. With `--cert` it is `wss://`: tick "accept the edge's own certificate" in the config node, or
install the edge's authority (`certs/ca.crt`) on the Node-RED machine.

The package (`node-red/node-red-contrib-dhc-edge`) has three nodes: **dhc edge** (the link, shared), **edge in** (events,
filtered), **edge out** (commands). Its examples are the three templates' flows.

## MQTT

```
dhc/edge/<edge>/status          the status event, retained; {"t": "offline"} as the last will and on stop
dhc/edge/<edge>/event/<t>       tile, hello, bye, answer, profile, error (QoS 1)
dhc/edge/<edge>/command         commands (subscribed, QoS 1)
```

Options: `--mqtt host:port`, `--mqtt-prefix`, `--mqtt-user` with `DHC_MQTT_PASSWORD`, `--mqtt-tls`. Photos travel inside
their event as base64: Node-RED's mqtt-in with "parsed JSON" reads it whole. `--broker` (start.sh) or compose's `broker`
profile starts a Mosquitto for trying it on one machine (anonymous, local only: docker/mosquitto.conf).

## ROS 2

`/dhc_edge/<edge>/event` and `/dhc_edge/<edge>/command`, `std_msgs/String` with the contract's JSON. The adapter spins
its own executor in a thread. JSON keeps the contract the same everywhere; a robot's node turns what it needs into typed
messages. For a richer, typed example of a phone on ROS 2, see atl-phone's `bridge_node.py`. `start.sh` passes
`ROS_DOMAIN_ID` and sets Fast DDS to UDP (containers do not share their memory).

```bash
ros2 topic echo --no-daemon /dhc_edge/edge/event
ros2 topic pub --once /dhc_edge/edge/command std_msgs/String '{data: "{\"t\": \"say\", \"text\": \"Hallo\", \"lang\": \"de\"}"}'
```

## A new adapter

One module in `dhc_edge/adapters/`, one line in `KNOWN` (`dhc_edge/adapters/__init__.py`):

```python
from . import Adapter

class Http(Adapter):          # e.g. a webhook: events POSTed to a URL
    name = "http"

    def start(self):          # connect; raise AdapterError when it cannot (the edge then does not start)
        ...

    def event(self, e):       # every event; never raise: a backend that is gone misses it
        ...

    def status(self):         # for the setup page and the logs
        return {"ok": True, "detail": "..."}
```

What its backend sends goes to `self.edge.command(raw, source=self.name)`: it returns None, or an `error` event to hand back
to that backend only. The options come from `__main__.py`'s argparse (add yours there). Test it as `tests/test_adapters.py`
does: an `Edge` on port 0, a `MockPhone`, the real transport.
