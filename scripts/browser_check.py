#!/usr/bin/env python3
# SPDX-License-Identifier: GPL-3.0-or-later
# Copyright (C) 2026 Atelier-5
# Copyright (C) 2026 DigitalHome.cloud
"""browser_check — the phone page in a real (headless) Chrome as the phone, against an edge started here.

    python3 scripts/browser_check.py [--port 8791] [--shots DIR]

The edge runs in this process with the nodered adapter; a backend client (MockPhone on /ws/backend) sees its events
and sends commands. Chrome's fake camera shows an EAN-13 barcode drawn here (a Y4M file), so a scan step reads it
with ZXing (headless Chrome on Linux has no BarcodeDetector) and a photo step takes a picture of it.
Checks: hello, the tiles drawn, a tap, a state shown, the inventory's steps (choice, photo, photo + OCR, note, review)
as one event with real JPEGs, a scanned code, a profile switch, a toggle confirmed by its state, a question answered,
and the setup page showing the phone and the events. Prints PASS/FAIL per check, exits 1 if any failed.
CDP on ports 9311/9312 (never 9333: atl-phone's check, and a phone's DevTools forwarded there, use it).
Standard library only.
"""
import argparse
import base64
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
from dhc_edge.mock_phone import MockPhone  # noqa: E402  (a WebSocket client is all CDP needs)

PHONE_PORT, SETUP_PORT = 9311, 9312
CODE = "4006381333931"


class Page:
    def __init__(self, url: str, extra=(), debug_port: int = PHONE_PORT, window="412,860"):
        self.profile = tempfile.mkdtemp(prefix="dhc-edge-chrome-", dir=os.environ.get("DHC_SCRATCH"))
        self.chrome = subprocess.Popen(
            ["google-chrome", "--headless=new", "--no-sandbox", f"--user-data-dir={self.profile}",
             f"--remote-debugging-port={debug_port}", "--remote-allow-origins=*", f"--window-size={window}",
             "--autoplay-policy=no-user-gesture-required", *extra, url],
            stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
        for _ in range(50):
            try:
                pages = json.load(urllib.request.urlopen(f"http://127.0.0.1:{debug_port}/json/list", timeout=1))
                ws = next(p["webSocketDebuggerUrl"] for p in pages if p["type"] == "page")
                break
            except (OSError, StopIteration, ValueError):
                time.sleep(0.2)
        else:
            raise RuntimeError("Chrome did not start")
        self.cdp, self.id = MockPhone(ws, origin=False), 0

    def call(self, method: str, **params):
        self.id += 1
        self.cdp.send(id=self.id, method=method, params=params)
        end = time.monotonic() + 20
        while time.monotonic() < end:
            m = self.cdp.got.get(timeout=20)
            if m.get("id") == self.id:
                if "error" in m:
                    raise RuntimeError(m["error"])
                return m.get("result", {})
        raise TimeoutError(method)

    def js(self, expr: str):
        r = self.call("Runtime.evaluate", expression=expr, returnByValue=True, userGesture=True)
        if "exceptionDetails" in r:
            raise RuntimeError(r["exceptionDetails"].get("exception", {}).get("description", "js error"))
        return r["result"].get("value")

    def wait_for(self, expr: str, tries=40, pause=0.3):
        v = None
        for _ in range(tries):
            try:
                v = self.js(expr)
            except (RuntimeError, TimeoutError):
                v = None
            if v:
                return v
            time.sleep(pause)
        return v

    def click(self, selector: str) -> bool:
        return bool(self.js(f"(function () {{ var e = document.querySelector({json.dumps(selector)}); if (e) e.click(); return !!e; }})()"))

    def shot(self, path: Path):
        path.write_bytes(base64.b64decode(self.call("Page.captureScreenshot", format="png")["data"]))

    def close(self):
        self.cdp.close()
        self.chrome.terminate()
        self.chrome.wait(10)
        shutil.rmtree(self.profile, ignore_errors=True)


# ---- an EAN-13 barcode as Chrome's fake camera (Y4M, one frame, looped) ---------------------------------------------
L = ["0001101", "0011001", "0010011", "0111101", "0100011", "0110001", "0101111", "0111011", "0110111", "0001011"]
G = ["".join("1" if c == "0" else "0" for c in x[::-1]) for x in L]
R = ["".join("1" if c == "0" else "0" for c in x) for x in L]
PARITY = ["LLLLLL", "LLGLGG", "LLGGLG", "LLGGGL", "LGLLGG", "LGGLLG", "LGGGLL", "LGLGLG", "LGLGGL", "LGGLGL"]


def ean13_bits(code: str) -> str:
    d = [int(c) for c in code]
    left = "".join((L if p == "L" else G)[x] for p, x in zip(PARITY[d[0]], d[1:7]))
    return "101" + left + "01010" + "".join(R[x] for x in d[7:]) + "101"


def barcode_y4m(path: Path, w=1280, h=720, module=8):
    bits = ean13_bits(CODE)
    x0 = (w - len(bits) * module) // 2
    y = bytearray(b"\xeb" * (w * h))   # white (video range)
    for i, b in enumerate(bits):
        if b == "1":
            for row in range(h // 4, 3 * h // 4):
                start = row * w + x0 + i * module
                y[start:start + module] = b"\x10" * module
    uv = b"\x80" * (w * h // 4)
    path.write_bytes(f"YUV4MPEG2 W{w} H{h} F10:1 Ip A1:1 C420jpeg\n".encode() + b"FRAME\n" + bytes(y) + uv + uv)


def main() -> int:
    a = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    a.add_argument("--port", type=int, default=8791)
    a.add_argument("--shots", default="", help="save screenshots here")
    o = a.parse_args()
    shots = Path(o.shots) if o.shots else None
    if shots:
        shots.mkdir(parents=True, exist_ok=True)
    fails = []

    def ok(name, good, detail=""):
        print(("PASS " if good else "FAIL ") + name + (f"  ({detail})" if detail else ""))
        if not good:
            fails.append(name)

    tmp = Path(tempfile.mkdtemp(prefix="dhc-edge-check-", dir=os.environ.get("DHC_SCRATCH")))
    barcode_y4m(tmp / "code.y4m")
    edge = Edge(ROOT / "web", ROOT / "profiles", profile="inventory", edge_id="check", port=o.port, bind="127.0.0.1",
                token="tok", docs=ROOT / "docs" / "architecture")
    edge.start(adapters.load(["nodered"], edge, Namespace()))
    backend = MockPhone(f"ws://127.0.0.1:{o.port}/ws/backend?token=tok", origin=False)
    backend.expect("status")
    phone = setup = None
    try:
        phone = Page(f"http://localhost:{o.port}/app.html?autostart=1&lang=en",
                     ["--use-fake-ui-for-media-stream", "--use-fake-device-for-media-stream",
                      f"--use-file-for-fake-video-capture={tmp / 'code.y4m'}"])
        phone.call("Emulation.setDeviceMetricsOverride", width=412, height=860, deviceScaleFactor=1, mobile=True)
        hello = backend.expect("hello", timeout=15)
        ok("the phone says hello", hello["phone"]["link"] == "usb", hello["phone"]["model"])
        n = phone.wait_for("document.querySelectorAll('#home .tile').length")
        ok("the tiles are drawn", n == len(edge.profile["home"]), f"{n} tiles")
        if shots:
            phone.shot(shots / "1-inventory.png")

        phone.click("[data-tile=count]")
        ok("a tap reaches the backend", backend.expect("tile")["tile"] == "count")
        backend.send(t="state", tile="count", value=12, label="today")
        ok("a state shows on its tile", phone.wait_for("(document.querySelector('[data-tile=count] small') || {}).textContent") == "12 · today")

        # the inventory's steps: room, appliance photo, type plate (OCR), note, review, send
        phone.click("[data-tile=appliance]")
        ok("a choice step shows its options", phone.wait_for("document.querySelectorAll('#body .grid .tile').length") == 8)
        if shots:
            phone.shot(shots / "2-room.png")
        phone.js("document.querySelectorAll('#body .grid .tile')[0].click()")
        ready = phone.wait_for("(document.querySelector('#body video') || {}).videoWidth", tries=60)
        ok("a photo step opens the camera", bool(ready), f"{ready} px wide")
        phone.js("document.querySelector('#body .big.go').click()")
        ok("the photo is shown to keep", bool(phone.wait_for("!!document.querySelector('#body img.shot')")))
        phone.js("document.querySelector('#body .big.go').click()")
        phone.wait_for("(document.querySelector('#body video') || {}).videoWidth", tries=60)
        phone.js("document.querySelector('#body .big.go').click()")
        read = phone.wait_for("(function () { var b = document.querySelector('#body .big.go'); return b && !b.disabled && document.querySelector('#body textarea') ? 1 : 0; })()",
                              tries=120, pause=0.5)
        ok("the type plate is read on the phone", bool(read), "Tesseract done")
        if shots:
            phone.shot(shots / "3-plate.png")
        phone.js("document.querySelector('#body textarea').value = 'TYPE AB 1234'; document.querySelector('#body .big.go').click()")
        phone.wait_for("document.querySelector('#body textarea')")
        phone.js("document.querySelector('#body textarea').value = 'under the stairs'; document.querySelector('#body .big.go').click()")
        ok("the review lists the steps", phone.wait_for("document.querySelectorAll('#body .review > div').length") == 4)
        if shots:
            phone.shot(shots / "4-review.png")
        phone.js("document.querySelector('#body .big.go').click()")
        e = backend.expect("tile", timeout=10)
        d = e.get("data", {})
        jpeg = base64.b64decode(d.get("photo", {}).get("jpeg", ""))
        ok("one event with every step", e["tile"] == "appliance" and d.get("room") == "kitchen" and d.get("note") == "under the stairs"
           and d.get("kind") == "appliance", ", ".join(sorted(d)))
        ok("the photos are JPEGs", jpeg[:2] == b"\xff\xd8" and base64.b64decode(d.get("plate", {}).get("jpeg", "AA=="))[:2] == b"\xff\xd8",
           f"{len(jpeg) // 1024} KB, {d.get('photo', {}).get('w')}x{d.get('photo', {}).get('h')}")
        ok("the plate's text comes along", d.get("plate", {}).get("text") == "TYPE AB 1234")

        # a scan step reads the fake camera's barcode
        phone.click("[data-tile=tag]")
        e = backend.expect("tile", timeout=30)
        code = e.get("data", {}).get("tag", {})
        ok("a scan step reads a barcode", code.get("code") == CODE, f"{code}")

        # the switch: a toggle waits for its state
        backend.send(t="profile", profile="switch")
        ok("a profile command switches the tiles", phone.wait_for("document.querySelector('[data-tile=ceiling]') ? 1 : 0") == 1)
        phone.click("[data-tile=ceiling]")
        e = backend.expect("tile")
        ok("a toggle asks for the other state", e["tile"] == "ceiling" and e["value"] is True)
        backend.send(t="state", states={"ceiling": True, "temp": 21.5, "scene": "evening"})
        ok("the state turns the tile on", phone.wait_for("document.querySelector('[data-tile=ceiling]').classList.contains('on')"))
        ok("a choice tile shows its state", "Evening" in (phone.wait_for("(document.querySelector('[data-tile=scene] small') || {}).textContent") or ""))
        if shots:
            phone.shot(shots / "5-switch.png")

        backend.send(t="ask", ask="leave", text={"en": "Turn everything off?"})
        ok("a question shows", phone.wait_for("document.getElementById('card').style.display === 'flex'"))
        phone.js("document.querySelector('#card button').click()")
        ans = backend.expect("answer")
        ok("its answer reaches the backend", (ans["ask"], ans["value"]) == ("leave", "yes"))

        # the setup page, on this PC
        setup = Page(f"http://localhost:{o.port}/setup.html", debug_port=SETUP_PORT, window="1280,1400")
        setup.call("Emulation.setDeviceMetricsOverride", width=1280, height=1400, deviceScaleFactor=1, mobile=False)
        st = setup.wait_for("document.getElementById('phone-status').textContent.indexOf('USB') >= 0 ? document.getElementById('phone-status').textContent : ''")
        ok("the setup page shows the phone", bool(st), st or "")
        ok("the setup page lists the events", (setup.wait_for("document.querySelectorAll('#log .ev').length") or 0) >= 5)
        ok("the setup page shows the photos", bool(setup.wait_for("(function () { var i = document.querySelector('#log img'); return i && i.naturalWidth; })()")))
        setup.js("document.querySelector('#preview button[title]').click()")   # a pretend tap: ceiling
        e = backend.expect("tile")
        ok("a pretend tap reaches the backend", e["tile"] == "ceiling")
        if shots:
            setup.shot(shots / "6-setup.png")
    finally:
        for p in (phone, setup):
            if p:
                p.close()
        backend.close()
        edge.stop()
        shutil.rmtree(tmp, ignore_errors=True)
    print(f"{'ALL PASS' if not fails else str(len(fails)) + ' FAILED'}")
    return 1 if fails else 0


if __name__ == "__main__":
    sys.exit(main())
