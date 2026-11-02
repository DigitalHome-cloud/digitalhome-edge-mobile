# SPDX-License-Identifier: GPL-3.0-or-later
# Copyright (C) 2026 DigitalHome.cloud
"""contract_check — a running edge against contract dhc-edge/0.1: a mock phone and a backend, end to end.

    python -m dhc_edge.contract_check [--url ws://127.0.0.1:8790] [--token-file .edge/token]
    python -m dhc_edge.contract_check --via mqtt --mqtt 127.0.0.1:1883 [--edge-id edge]

The mock phone takes over the edge's link (a real phone there is closed: it reconnects when the check is done).
Every tile of the profile shown is tapped with a sample answer (as the setup page's pretend taps), and must reach the
backend as its event; the backend's commands (state, toast, say, ask, vibrate, home) must reach the phone, and an answer
the backend. --via mqtt: the backend is an MQTT client on the edge's topics instead of /ws/backend.
Prints PASS/FAIL per check and exits 1 if any failed.
"""
import argparse
import json
import queue
import sys
import time
from pathlib import Path

from . import contract as c
from .mock_phone import TINY_JPEG, MockPhone


def sample(s: dict):
    a = s["action"]
    if a == "choice":
        return s["options"][0]["id"]
    if a == "number":
        return s["default"]
    if a == "text":
        return "contract check"
    if a == "scan":
        return {"code": "CHECK-0001", "format": "qr_code"}
    if a == "photo":
        return dict({"jpeg": TINY_JPEG, "w": 1, "h": 1}, **({"text": "TYPE 1"} if s.get("ocr") else {}))
    return None


def tap_of(t: dict) -> dict:
    """What the phone sends for tile t, with sample answers."""
    if t["action"] == "toggle":
        return {"value": True}
    if t["action"] == "steps":
        return {"data": {s["id"]: sample(s) for s in t["steps"]}}
    if t["action"] in c.STEP_ACTIONS:
        return {"data": {t["id"]: sample(t)}}
    return {}


class WsBackend:
    def __init__(self, url, token):
        self.link = MockPhone(f"{url.rstrip('/')}{c.BACKEND_PATH}" + (f"?token={token}" if token else ""), origin=False)

    def send(self, cmd):
        self.link.send(**cmd)

    def expect(self, t, timeout=5.0):
        return self.link.expect(t, timeout)

    def close(self):
        self.link.close()


class MqttBackend:
    def __init__(self, broker, prefix, edge_id):
        import paho.mqtt.client as mqtt
        self.topics = c.mqtt_topics(prefix, edge_id)
        self.got = queue.Queue()
        self.client = mqtt.Client(mqtt.CallbackAPIVersion.VERSION2, client_id="dhc-contract-check")
        self.client.on_message = lambda cl, u, m: self._heard(m)
        host, _, port = broker.partition(":")
        self.client.connect(host, int(port or 1883))
        self.client.subscribe([(self.topics["event"] + "/#", 1), (self.topics["status"], 1)])
        self.client.loop_start()

    def _heard(self, m):
        try:
            self.got.put(json.loads(m.payload))
        except ValueError:
            pass

    def send(self, cmd):
        self.client.publish(self.topics["command"], json.dumps(cmd), qos=1)

    def expect(self, t, timeout=5.0):
        end = time.monotonic() + timeout
        while time.monotonic() < end:
            try:
                e = self.got.get(timeout=max(0.05, end - time.monotonic()))
            except queue.Empty:
                continue
            if e.get("t") == t:
                return e
        raise TimeoutError(f"no {t!r} event")

    def close(self):
        self.client.loop_stop()
        self.client.disconnect()


def main(argv=None) -> int:
    a = argparse.ArgumentParser(prog="python -m dhc_edge.contract_check", description=__doc__.splitlines()[0])
    a.add_argument("--url", default="ws://127.0.0.1:8790", help="the edge (ws:// or wss://)")
    a.add_argument("--token", default="")
    a.add_argument("--token-file", default="")
    a.add_argument("--key", default="", help="the phone's pairing key, if the edge has one")
    a.add_argument("--via", choices=("nodered", "mqtt"), default="nodered")
    a.add_argument("--mqtt", default="127.0.0.1:1883")
    a.add_argument("--mqtt-prefix", default="dhc/edge")
    a.add_argument("--edge-id", default="edge")
    o = a.parse_args(argv)
    token = Path(o.token_file).read_text().strip() if o.token_file else o.token
    fails = []

    def ok(name, good, detail=""):
        print(("PASS " if good else "FAIL ") + name + (f"  ({detail})" if detail else ""))
        if not good:
            fails.append(name)

    backend = WsBackend(o.url, token) if o.via == "nodered" else MqttBackend(o.mqtt, o.mqtt_prefix, o.edge_id)
    phone = None
    try:
        if o.via == "nodered":
            st = backend.expect("status")
            ok("a backend gets the status first", st["v"] == c.CONTRACT, f"edge {st['edge']}, profile {st['profile']}")
        phone = MockPhone(f"{o.url.rstrip('/')}/ws" + (f"?key={o.key}" if o.key else ""))
        phone.hello()
        web = phone.expect("web")
        prof = phone.expect("profile")["profile"]
        ok("the phone gets the pages' fingerprint, then the profile", len(web["id"]) == 16, f"{prof['id']}: {len(prof['tiles'])} tiles")
        hello = backend.expect("hello")
        ok("the backend hears the phone come", hello["phone"]["model"] == "MOCK-PHONE")
        for t in prof["tiles"]:
            m = tap_of(t)
            phone.tap(t["id"], **({"value": m["value"]} if "value" in m else {}), **m.get("data", {}))
            e = backend.expect("tile")
            good = e["tile"] == t["id"] and e["action"] == t["action"] and all(k in e.get("data", {}) for k in m.get("data", {}))
            ok(f"tile {t['id']} ({t['action']}) reaches the backend", good, ", ".join(sorted(e.get("data", {}))))
        shown = [t for t in prof["tiles"] if t["action"] in ("state", "toggle")]
        if shown:
            tid = shown[0]["id"]
            backend.send({"t": "state", "tile": tid, "value": True if shown[0]["action"] == "toggle" else 7})
            ok(f"a state reaches the phone ({tid})", tid in phone.expect("state")["states"])
        for cmd in ({"t": "toast", "text": {"en": "check"}}, {"t": "say", "text": "check"}, {"t": "vibrate", "ms": 50}, {"t": "home"}):
            backend.send(cmd)
            ok(f"{cmd['t']} reaches the phone", phone.expect(cmd["t"])["t"] == cmd["t"])
        backend.send({"t": "ask", "ask": "check", "text": "?"})
        q = phone.expect("ask")
        phone.send(t="answer", id=q["id"], value=q["options"][0]["id"])
        ok("an answer reaches the backend", backend.expect("answer")["value"] == "yes")
        backend.send({"t": "state", "tile": "no-such-tile", "value": 1, "id": "c1"})
        err = backend.expect("error")
        ok("a bad command comes back as an error", err.get("id") == "c1", err["error"])
        phone.close()
        phone = None
        ok("the backend hears the phone go", backend.expect("bye")["phone"]["model"] == "MOCK-PHONE")
    except (TimeoutError, ConnectionError, OSError) as e:
        ok("the check ran to the end", False, f"{type(e).__name__}: {e}")
    finally:
        if phone:
            phone.close()
        backend.close()
    print(f"{'ALL PASS' if not fails else str(len(fails)) + ' FAILED'}")
    return 1 if fails else 0


if __name__ == "__main__":
    sys.exit(main())
