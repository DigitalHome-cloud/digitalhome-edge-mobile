# SPDX-License-Identifier: GPL-3.0-or-later
# Copyright (C) 2026 Atelier-5
# Copyright (C) 2026 DigitalHome.cloud
"""mock_phone — a phone without a phone: a WebSocket client that talks like web/app.html (standard library only).

    python3 -m dhc_edge.mock_phone [--url ws://127.0.0.1:8790/ws] [--tap TILE]   says hello, taps, prints what comes

The same client is a backend too (MockPhone(".../ws/backend?token=...")): the tests and contract_check use it both ways.
"""
import argparse
import base64
import json
import os
import queue
import socket
import ssl
import threading
import time
from urllib.parse import urlsplit

from .wsserver import accept_key, frame, read_frame

ID = "0123456789abcdef"  # the page's random per-browser id
UA = "Mozilla/5.0 (Linux; Android 8.0.0; MOCK-PHONE) AppleWebKit/537.36 Chrome/119.0 Mobile Safari/537.36"


class MockPhone:
    def __init__(self, url: str, timeout: float = 5.0, origin: bool = True):
        u = urlsplit(url)
        self.sock = socket.create_connection((u.hostname, u.port or 80), timeout=timeout)
        if u.scheme == "wss":   # the edge's own certificate, not checked here (a test tool)
            ctx = ssl.create_default_context()
            ctx.check_hostname, ctx.verify_mode = False, ssl.CERT_NONE
            self.sock = ctx.wrap_socket(self.sock, server_hostname=u.hostname)
        key = base64.b64encode(os.urandom(16)).decode()
        path = u.path + (f"?{u.query}" if u.query else "")
        host = f"{u.hostname}:{u.port or 80}"
        self.sock.sendall((f"GET {path} HTTP/1.1\r\nHost: {host}\r\nUpgrade: websocket\r\nConnection: Upgrade\r\n"
                           f"Sec-WebSocket-Key: {key}\r\nSec-WebSocket-Version: 13\r\n"
                           + (f"Origin: http://{host}\r\n" if origin else "") + "\r\n").encode())
        self.rfile = self.sock.makefile("rb")
        status = self.rfile.readline().decode()
        headers = {}
        while True:
            line = self.rfile.readline().decode().strip()
            if not line:
                break
            k, _, v = line.partition(":")
            headers[k.strip().lower()] = v.strip()
        if " 101 " not in status or headers.get("sec-websocket-accept") != accept_key(key):
            raise ConnectionError(status.strip())
        self.sock.settimeout(None)  # the timeout was for connecting; an idle link is no error
        self.got = queue.Queue()
        self.closed = threading.Event()
        threading.Thread(target=self._read, daemon=True).start()

    def _read(self):
        try:
            while True:
                opcode, data = read_frame(self.rfile, limit=1 << 24)
                if opcode == 8:
                    break
                if opcode == 1:
                    self.got.put(json.loads(data))
        except (OSError, ValueError):
            pass
        self.closed.set()

    def send(self, **msg):
        self.sock.sendall(frame(json.dumps(msg).encode(), mask=True))

    def hello(self):
        self.send(t="hello", id=ID, ua=UA, secure=True, caps={"camera": True, "tts": True, "vibrate": True, "barcode": True},
                  screen=[720, 1280])

    def tap(self, tile: str, value=None, **data):
        """A tile: tapped (value: a toggle's or a choice's), or its steps done (data: step id -> part)."""
        m = {"t": "tile", "tile": tile}
        if value is not None:
            m["value"] = value
        if data:
            m["data"] = data
        self.send(**m)

    def expect(self, t: str, timeout: float = 3.0) -> dict:
        """The next message of kind t (others are skipped)."""
        end = time.monotonic() + timeout
        while True:
            left = end - time.monotonic()
            if left <= 0:
                raise TimeoutError(f"no {t!r} message")
            try:
                m = self.got.get(timeout=left)
            except queue.Empty:
                continue
            if m.get("t") == t:
                return m

    def close(self):
        try:
            self.sock.sendall(frame(b"\x03\xe8", opcode=8, mask=True))
        except OSError:
            pass
        self.sock.close()


# a 1x1 JPEG: what a photo part looks like, for tests (base64)
TINY_JPEG = base64.b64encode(bytes.fromhex(
    "ffd8ffe000104a46494600010100000100010000ffdb004300080606070605080707070909080a0c140d0c0b0b0c1912130f141d1a1f1e1d1a1c1c"
    "20242e2720222c231c1c2837292c30313434341f27393d38323c2e333432ffc0000b080001000101011100ffc4001f0000010501010101010100"
    "000000000000000102030405060708090a0bffc400b5100002010303020403050504040000017d01020300041105122131410613516107227114"
    "328191a1082342b1c11552d1f02433627282090a161718191a25262728292a3435363738393a434445464748494a535455565758595a63646566"
    "6768696a737475767778797a838485868788898a92939495969798999aa2a3a4a5a6a7a8a9aab2b3b4b5b6b7b8b9bac2c3c4c5c6c7c8c9cad2d3"
    "d4d5d6d7d8d9dae1e2e3e4e5e6e7e8e9eaf1f2f3f4f5f6f7f8f9faffda0008010100003f00fbd3ffd9")).decode()


def main():
    p = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    p.add_argument("--url", default="ws://127.0.0.1:8790/ws")
    p.add_argument("--tap", action="append", default=[], help="a tile to tap after the hello (again: several)")
    a = p.parse_args()
    phone = MockPhone(a.url)
    phone.hello()
    for t in a.tap:
        phone.tap(t)
    print("connected; Ctrl-C to stop")
    try:
        while True:
            try:
                print(json.dumps(phone.got.get(timeout=1))[:300])
            except queue.Empty:
                pass
    except KeyboardInterrupt:
        phone.close()


if __name__ == "__main__":
    main()
