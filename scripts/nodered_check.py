#!/usr/bin/env python3
# SPDX-License-Identifier: GPL-3.0-or-later
# Copyright (C) 2026 DigitalHome.cloud
"""nodered_check — the example flows in a real Node-RED, against an edge started here, with a mock phone.

    python3 scripts/nodered_check.py --node-red PATH/node_modules/node-red/red.js [--port 8793]

For each example (inventory, checkinout with the cellar profile, switch): a fresh Node-RED user folder with the
package linked in and the flow imported (its "dhc edge" node pointed at this edge, with the token), then the phone
does what a person would, and what the flow answers must reach the phone. Node-RED on port 18800.
Get Node-RED once: npm install node-red@4.0.9 (in any folder). Prints PASS/FAIL, exits 1 if any failed.
"""
import argparse
import json
import os
import shutil
import subprocess
import sys
import tempfile
import time
import urllib.request
from argparse import Namespace
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))
from dhc_edge import adapters  # noqa: E402
from dhc_edge.core import Edge  # noqa: E402
from dhc_edge.mock_phone import TINY_JPEG, MockPhone  # noqa: E402

PKG = ROOT / "node-red" / "node-red-contrib-dhc-edge"
NR_PORT = 18800
TOKEN = "check-token"


def node_red(red_js: Path, flow: list, edge_port: int, tmp: Path):
    user = tmp / "nr"
    (user / "node_modules").mkdir(parents=True)
    (user / "node_modules" / PKG.name).symlink_to(PKG)
    (user / "settings.js").write_text("module.exports = { uiPort: %d, uiHost: '127.0.0.1', credentialSecret: false, "
                                      "flowFile: 'flows.json' };\n" % NR_PORT)
    flow = [dict(n) for n in flow]
    for n in flow:
        if n["type"] == "dhc-edge-config":
            n["url"] = f"ws://127.0.0.1:{edge_port}/ws/backend"
        else:
            n["z"] = "tab1"
    flow.insert(0, {"id": "tab1", "type": "tab", "label": "check"})
    (user / "flows.json").write_text(json.dumps(flow))
    (user / "flows_cred.json").write_text(json.dumps({"edgecfg": {"token": TOKEN}}))
    log = open(tmp / "nr.log", "w")
    env = dict(os.environ, DHC_API=f"http://127.0.0.1:{NR_PORT}/dhc-mock")
    proc = subprocess.Popen(["node", str(red_js), "--userDir", str(user), "--settings", str(user / "settings.js")],
                            stdout=log, stderr=subprocess.STDOUT, env=env)
    for _ in range(100):
        if "Started flows" in (tmp / "nr.log").read_text():
            break
        if proc.poll() is not None:
            raise RuntimeError("Node-RED ended:\n" + (tmp / "nr.log").read_text()[-2000:])
        time.sleep(0.2)
    else:
        raise RuntimeError("Node-RED did not start:\n" + (tmp / "nr.log").read_text()[-2000:])
    return proc


def run(example: str, profile: str, red_js: Path, port: int, steps):
    tmp = Path(tempfile.mkdtemp(prefix="dhc-nr-", dir=os.environ.get("DHC_SCRATCH")))
    edge = Edge(ROOT / "web", ROOT / "profiles", profile=profile, edge_id="nrcheck", port=port, bind="127.0.0.1", token=TOKEN)
    edge.start(adapters.load(["nodered"], edge, Namespace()))
    proc = None
    try:
        proc = node_red(red_js, json.loads((PKG / "examples" / f"{example}.json").read_text()), port, tmp)
        for _ in range(50):   # the flow's edge link
            if edge.server.backend_count:
                break
            time.sleep(0.1)
        phone = MockPhone(f"ws://127.0.0.1:{port}/ws")
        phone.hello()
        phone.expect("profile")
        steps(phone)
        phone.close()
    finally:
        if proc:
            proc.terminate()
            proc.wait(10)
        edge.stop()
        if os.environ.get("DHC_KEEP"):
            print("kept", tmp)
        else:
            shutil.rmtree(tmp, ignore_errors=True)


def main() -> int:
    a = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    a.add_argument("--node-red", required=True, help="node-red's red.js (node_modules/node-red/red.js)")
    a.add_argument("--port", type=int, default=8793)
    o = a.parse_args()
    fails = []

    def ok(name, good, detail=""):
        print(("PASS " if good else "FAIL ") + name + (f"  ({detail})" if detail else ""))
        if not good:
            fails.append(name)

    def inventory(phone):
        phone.tap("appliance", room="kitchen", photo={"jpeg": TINY_JPEG, "w": 1, "h": 1},
                  plate={"jpeg": TINY_JPEG, "w": 1, "h": 1, "text": "Bosch SMS4"}, note="")
        t = phone.expect("toast", timeout=8)
        ok("inventory: the record is saved (POST to the mock platform)", t["text"]["en"] == "Saved ✓", t["text"]["en"])
        s = phone.expect("state", timeout=5)
        ok("inventory: the Recorded tile counts", s["states"] == {"count": 1.0})
        phone.tap("tag", tag={"code": "QR-77", "format": "qr_code"})
        t = phone.expect("toast", timeout=5)
        ok("inventory: an unknown tag is said so", "QR-77" in t["text"]["en"], t["text"]["en"])

    def cellar(phone):
        phone.tap("checkin", code={"code": "3760", "format": "ean_13"}, qty=2, place="r1")
        t = phone.expect("toast", timeout=8)
        ok("cellar: two bottles in", t["text"]["en"] == "+2 → 2", t["text"]["en"])
        ok("cellar: the stock tile", phone.expect("state", timeout=5)["states"] == {"stock": 2.0})
        phone.tap("lookup", lookup={"code": "3760", "format": "ean_13"})
        t = phone.expect("toast", timeout=5)
        ok("cellar: a lookup says where", t["text"]["en"] == "2 in r1", t["text"]["en"])
        phone.tap("checkout", code={"code": "3760", "format": "ean_13"}, qty=1, rating="3")
        ok("cellar: one bottle out", phone.expect("toast", timeout=5)["text"]["en"] == "−1 → 1")

    def switch(phone):
        temp = phone.expect("state", timeout=8)
        ok("switch: the thermometer sets its tile", "temp" in temp["states"], str(temp["states"]))
        phone.tap("ceiling", value=True)
        deadline = time.monotonic() + 5
        s = {}
        while time.monotonic() < deadline and "ceiling" not in s:
            s = phone.expect("state", timeout=5)["states"]
        ok("switch: a tap turns the light on", s.get("ceiling") is True, str(s))
        phone.tap("all_off")
        t = phone.expect("toast", timeout=5)
        ok("switch: all off says good night", t["text"]["en"] == "Good night")

    try:
        urllib.request.urlopen(f"http://127.0.0.1:{NR_PORT}/", timeout=1)
        print(f"port {NR_PORT} is taken: another Node-RED?")
        return 1
    except OSError:
        pass
    red_js = Path(o.node_red).resolve()
    for example, profile, steps in (("inventory", "inventory", inventory), ("checkinout", "cellar", cellar), ("switch", "switch", switch)):
        try:
            run(example, profile, red_js, o.port, steps)
        except (TimeoutError, RuntimeError, KeyError) as e:
            ok(f"{example}: ran to the end", False, f"{type(e).__name__}: {e}")
    print(f"{'ALL PASS' if not fails else str(len(fails)) + ' FAILED'}")
    return 1 if fails else 0


if __name__ == "__main__":
    sys.exit(main())
