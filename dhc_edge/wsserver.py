# SPDX-License-Identifier: GPL-3.0-or-later
# Copyright (C) 2026 Atelier-5
# Copyright (C) 2026 DigitalHome.cloud
"""wsserver.py — the phone's pages, its WebSocket and the backends' WebSocket on one port (standard library only).

Derived from atl-phone's wsserver.py: the same TLS handshake per request thread, Origin check, takeover and
loopback-only setup API; its mirror became a backend link, which also speaks.

GET /          -> app.html (any file of web/ is served as is)
GET /ws        -> the phone's WebSocket (RFC 6455, text frames only); ?key=... when the edge has a pairing key
GET /ws/backend -> a backend's WebSocket (Node-RED, a test console): it gets every event and may send commands.
                  With the backend token (?token=... or "Authorization: Bearer ..."); without one only from this PC
POST /report   -> a phone check's report (check.html), from any phone; kept in the registry when the edge has one
GET /api/state, POST /api/act -> the setup page: this PC only (loopback; a phone on USB is loopback too, through
                  adb reverse)
GET /api/photo?e=N&p=K -> a photo of a recent event, for the setup page: this PC only, kept in memory only
GET /ca.crt    -> this PC's certificate authority, for a phone to install once (when the edge has one)
GET /docs/     -> the architecture pack (docs/architecture), when the edge has it

One phone at a time: a new phone takes over and the old one is closed; a frame the old one had already sent is dropped.
Backends: up to MAX_BACKENDS, beside the phone. A link that stops reading is dropped after SEND_TIMEOUT_S (events
are sent on the phone's thread, while it holds the phone's lock).
A browser on another site is refused (Origin must match Host).
"""
import base64
import hashlib
import hmac
import ipaddress
import json
import os
import socket
import ssl
import struct
import threading
from functools import partial
from pathlib import Path
from http.server import SimpleHTTPRequestHandler, ThreadingHTTPServer
from urllib.parse import parse_qs, urlsplit

BACKEND = "/ws/backend"   # contract.BACKEND_PATH (this module imports nothing of the package)
MAX_BACKENDS = 8

GUID = "258EAFA5-E914-47DA-95CA-C5AB0DC85B11"
MAX_FRAME = 4 * 1024 * 1024   # a tile's photos as base64 (protocol.MAX_PHOTO each, at most protocol.MAX_PHOTOS)
MAX_POST = 64 * 1024
SEND_TIMEOUT_S = 10   # a link that takes nothing for this long is dropped: a stuck backend must not stall the phone


class Server(ThreadingHTTPServer):
    """A threading HTTP server whose TLS handshake happens in each request's own thread, with a time limit: done in
    accept(), on the only accepting thread, one silent connection would keep every other phone out."""
    daemon_threads = True
    HANDSHAKE_S = 10

    def use_tls(self, cert, cert_key):
        ctx = ssl.SSLContext(ssl.PROTOCOL_TLS_SERVER)
        ctx.load_cert_chain(cert, cert_key)
        self.socket = ctx.wrap_socket(self.socket, server_side=True, do_handshake_on_connect=False)

    def finish_request(self, request, client_address):
        if isinstance(request, ssl.SSLSocket):
            try:
                request.settimeout(self.HANDSHAKE_S)
                request.do_handshake()
                request.settimeout(None)
            except (OSError, ValueError):   # silent, too slow, or not TLS: this connection only (closed after)
                return
        super().finish_request(request, client_address)


def accept_key(key: str) -> str:
    return base64.b64encode(hashlib.sha1((key + GUID).encode()).digest()).decode()


def frame(payload: bytes, opcode: int = 1, mask: bool = False) -> bytes:
    """One final frame. A server never masks; a client always does."""
    head = bytes([0x80 | opcode])
    n = len(payload)
    bit = 0x80 if mask else 0
    if n < 126:
        head += bytes([bit | n])
    elif n < 1 << 16:
        head += bytes([bit | 126]) + struct.pack(">H", n)
    else:
        head += bytes([bit | 127]) + struct.pack(">Q", n)
    if not mask:
        return head + payload
    key = os.urandom(4)
    return head + key + _xor(payload, key)


def _xor(data: bytes, key: bytes) -> bytes:
    """Masking, fast enough for a photo: one big integer XOR instead of a loop over each byte."""
    n = len(data)
    if not n:
        return data
    k = (key * (n // 4 + 1))[:n]
    return (int.from_bytes(data, "big") ^ int.from_bytes(k, "big")).to_bytes(n, "big")


def read_frame(rfile, limit: int = MAX_FRAME) -> tuple:
    """(opcode, payload) of the next message; (8, b"") when the peer is gone. Fragments are joined (Node's ws and
    browsers send one frame per message, but may fragment), up to limit bytes in all."""
    data, first = b"", None
    while True:
        head = rfile.read(2)
        if len(head) < 2:
            return 8, b""
        fin, opcode = head[0] & 0x80, head[0] & 0x0F
        masked, n = head[1] & 0x80, head[1] & 0x7F
        if n == 126:
            n = struct.unpack(">H", rfile.read(2))[0]
        elif n == 127:
            n = struct.unpack(">Q", rfile.read(8))[0]
        if len(data) + n > limit:
            raise ValueError("message too big")
        key = rfile.read(4) if masked else b""
        part = rfile.read(n)
        if masked:
            part = _xor(part, key)
        if opcode >= 8:   # a control frame may come between fragments: handed back on its own
            return opcode, part
        if first is None:
            first = opcode
        data += part
        if fin:
            return first, data


def web_id(web_dir) -> str:
    """A fingerprint of the pages this edge serves: a page loaded from an older edge sees it change, and reloads.
    The files' bytes, except vendor/ (fixed versions), where the names and sizes are enough."""
    h = hashlib.sha256()
    root = Path(web_dir)
    for f in sorted(p for p in root.rglob("*") if p.is_file()):
        rel = f.relative_to(root).as_posix()
        h.update(rel.encode() + b"\0")
        h.update(str(f.stat().st_size).encode() if rel.startswith("vendor/") else f.read_bytes())
    return h.hexdigest()[:16]


def lan_address() -> str:
    """This PC's address on the local network (the phones' Wi-Fi), or 127.0.0.1."""
    with socket.socket(socket.AF_INET, socket.SOCK_DGRAM) as s:
        try:
            s.connect(("192.0.2.1", 9))  # no packet is sent; it only picks the outgoing interface
            return s.getsockname()[0]
        except OSError:
            return "127.0.0.1"


class Link:
    """A connection (the phone's, or a backend's), as the edge sees it."""

    def __init__(self, wfile, peer, kind="phone", sock=None):
        self.wfile, self.peer, self.kind, self.sock = wfile, peer, kind, sock
        if sock:   # writes give up when nothing moves for SEND_TIMEOUT_S (reads still wait as long as they like)
            sock.setsockopt(socket.SOL_SOCKET, socket.SO_SNDTIMEO, struct.pack("ll", SEND_TIMEOUT_S, 0))
        self.lock = threading.Lock()
        self.open = True

    @property
    def local(self) -> bool:
        return ipaddress.ip_address(self.peer).is_loopback

    def send(self, text: str) -> bool:
        with self.lock:
            if not self.open:
                return False
            try:
                self.wfile.write(frame(text.encode()))
                self.wfile.flush()
                return True
            except OSError:   # gone, or stuck: half a frame may have gone out, so the link is ended
                self.open = False
                self.shut()
                return False

    def shut(self):
        """Ends the connection under its reader too (its pump stops, the link's owner is told)."""
        if self.sock:
            try:
                self.sock.shutdown(socket.SHUT_RDWR)
            except OSError:
                pass

    def close(self, code: int = 1000):
        with self.lock:
            if self.open:
                self.open = False
                try:
                    self.wfile.write(frame(struct.pack(">H", code), opcode=8))
                    self.wfile.flush()
                except OSError:
                    pass


class PhoneServer:
    """Serves web_dir, one phone and its backends. Callbacks run on the connection's thread:
    on_open(link), on_text(text), on_close(link) for the phone; on_backend(link, text) for a backend's message,
    on_backend_open(link) and on_backend_close(link) for its link."""

    def __init__(self, web_dir, port, bind="0.0.0.0", key="", on_open=None, on_text=None, on_close=None,
                 cert=None, cert_key=None, api=None, ca=None, docs=None, token="",
                 on_backend=None, on_backend_open=None, on_backend_close=None):
        """api, for the setup page: state() -> dict, act(dict) -> None or an answer (ValueError refuses it),
        report(dict) -> None or where it was kept, photo(event, part) -> JPEG bytes or None.
        ca: the authority that signed cert, offered at /ca.crt (public: it is what a phone needs to trust the edge).
        token: what a backend must show; "" lets only this PC's backends in.
        docs: the architecture pack's folder, served at /docs/ (static pages, as web_dir)."""
        self.key, self.token = key, token
        self.docs = str(docs) if docs and Path(docs).is_dir() else None
        self.ca = ca
        self.api = api
        self.on_open = on_open or (lambda link: None)
        self.on_text = on_text or (lambda text: None)
        self.on_close = on_close or (lambda link: None)
        self.on_backend = on_backend or (lambda link, text: None)
        self.on_backend_open = on_backend_open or (lambda link: None)
        self.on_backend_close = on_backend_close or (lambda link: None)
        self.link = None
        self.backends, self.block = [], threading.Lock()   # its own lock: the phone's is held while a message is delivered
        self.lock = threading.Lock()
        self.httpd = Server((bind, port), partial(make_handler(self), directory=str(web_dir)))
        self.scheme = "http"
        if cert:
            self.httpd.use_tls(cert, cert_key)
            self.scheme = "https"
        self.port = self.httpd.server_port

    def start(self):
        threading.Thread(target=self.httpd.serve_forever, daemon=True, name="edge-server").start()
        return self

    def stop(self):
        with self.lock:
            if self.link:
                self.link.close(1001)
        with self.block:
            for b in self.backends:
                b.close(1001)
        self.httpd.shutdown()
        self.httpd.server_close()

    def send(self, text: str) -> bool:
        """To the phone. True when it got it."""
        link = self.link
        return bool(link and link.send(text))

    def send_backends(self, text: str) -> int:
        """To every backend: how many got it."""
        with self.block:
            self.backends = [b for b in self.backends if b.open]
            backends = list(self.backends)
        return sum(b.send(text) for b in backends)

    @property
    def backend_count(self) -> int:
        return sum(1 for b in self.backends if b.open)

    @property
    def connected(self) -> bool:
        return bool(self.link and self.link.open)

    def take_over(self, link):
        with self.lock:  # waits for a message being delivered (deliver), so none of the old phone's lands after this
            old, self.link = self.link, link
        if old:
            old.close(4000)  # another phone took over

    def deliver(self, link, text: str) -> bool:
        """on_text, if link is still the phone. A frame read after a takeover is the old phone's: dropped."""
        with self.lock:
            if self.link is not link:
                return False
            self.on_text(text)
            return True

    def release(self, link) -> bool:
        with self.lock:
            if self.link is not link:
                return False
            self.link = None
            return True


def bearer(headers, query) -> str:
    auth = headers.get("Authorization", "")
    if auth.lower().startswith("bearer "):
        return auth[7:].strip()
    return parse_qs(query).get("token", [""])[0]


def make_handler(server: PhoneServer):
    class Handler(SimpleHTTPRequestHandler):
        # OCR's library: WebAssembly, which the browser compiles while it loads only with its own type
        extensions_map = {**SimpleHTTPRequestHandler.extensions_map, ".mjs": "text/javascript", ".js": "text/javascript",
                          ".wasm": "application/wasm", ".webmanifest": "application/manifest+json"}

        def log_message(self, *args):  # quiet: the edge logs what matters
            pass

        def end_headers(self):
            # vendor/ holds fixed versions (some 13 MB): a phone keeps them a day; the rest is never cached
            self.send_header("Cache-Control", "max-age=86400" if self.path.startswith("/vendor/") else "no-store")
            super().end_headers()

        def translate_path(self, path):
            p = urlsplit(path).path
            if server.docs and (p == "/docs" or p.startswith("/docs/")):   # the pack, from its own folder
                web, self.directory = self.directory, server.docs
                try:
                    return super().translate_path(path[len("/docs"):])
                finally:
                    self.directory = web
            return super().translate_path(path)

        def do_GET(self):
            url = urlsplit(self.path)
            if url.path == "/":
                self.send_response(302)
                self.send_header("Location", "/app.html" + (f"?{url.query}" if url.query else ""))
                self.end_headers()
                return
            if url.path == "/ca.crt":
                if not server.ca:
                    return self.send_error(404)
                with open(server.ca, "rb") as f:
                    body = f.read()
                self.send_response(200)
                self.send_header("Content-Type", "application/x-x509-ca-cert")
                self.send_header("Content-Disposition", 'attachment; filename="dhc-edge-ca.crt"')
                self.send_header("Content-Length", str(len(body)))
                self.end_headers()
                self.wfile.write(body)
                return
            if url.path == "/api/state":
                if self.refused(local=True):
                    return
                return self.answer(200, server.api.state())
            if url.path == "/api/photo":  # a recent event's photo, for the setup page: this PC only, never stored
                if self.refused(local=True):
                    return
                q = parse_qs(url.query)
                try:
                    jpeg = server.api.photo(int(q.get("e", ["-1"])[0]), q.get("p", [""])[0])
                except ValueError:
                    jpeg = None
                if not jpeg:
                    return self.send_error(404, "no such photo")
                self.send_response(200)
                self.send_header("Content-Type", "image/jpeg")
                self.send_header("Content-Length", str(len(jpeg)))
                self.end_headers()
                self.wfile.write(jpeg)
                return
            if url.path not in ("/ws", BACKEND):
                return super().do_GET()
            if url.path == BACKEND:
                if self.refused(origin=False):  # Node-RED sends no Origin; a browser's must match
                    return
                given = bearer(self.headers, url.query)
                if server.token:
                    if not hmac.compare_digest(given, server.token):
                        return self.send_error(403, "wrong token")
                elif not ipaddress.ip_address(self.client_address[0]).is_loopback:
                    return self.send_error(403, "this PC only (start the edge with a backend token)")
            else:
                if self.refused():
                    return
                given = parse_qs(url.query).get("key", [""])[0]
                if server.key and not hmac.compare_digest(given, server.key):
                    return self.send_error(403, "wrong key")
            ws_key = self.headers.get("Sec-WebSocket-Key")
            if self.headers.get("Upgrade", "").lower() != "websocket" or not ws_key:
                return self.send_error(400, "not a WebSocket")
            self.send_response(101)
            self.send_header("Upgrade", "websocket")
            self.send_header("Connection", "Upgrade")
            self.send_header("Sec-WebSocket-Accept", accept_key(ws_key))
            super(SimpleHTTPRequestHandler, self).end_headers()  # no Cache-Control on a 101
            self.wfile.flush()
            self.close_connection = True
            self.serve_backend() if url.path == BACKEND else self.serve_ws()

        def refused(self, local=False, origin=True) -> bool:
            """A browser on another site, or (local) someone not on this PC: refused, with the answer sent."""
            o = self.headers.get("Origin")
            if o and urlsplit(o).netloc != self.headers.get("Host"):
                self.send_error(403, "foreign origin")
                return True
            if local and not (server.api and ipaddress.ip_address(self.client_address[0]).is_loopback):
                self.send_error(403, "this PC only")
                return True
            return False

        def answer(self, status, payload=None):
            body = json.dumps(payload).encode() if payload is not None else b""
            self.send_response(status)
            if body:
                self.send_header("Content-Type", "application/json")
            self.send_header("Content-Length", str(len(body)))
            self.end_headers()
            self.wfile.write(body)

        def do_POST(self):
            path = urlsplit(self.path).path
            if path not in ("/report", "/api/act") or not server.api:
                return self.send_error(404)
            if self.refused(local=path.startswith("/api/")):
                return
            size = int(self.headers.get("Content-Length") or 0)
            if not 0 < size <= MAX_POST:
                return self.send_error(413)
            try:
                body = json.loads(self.rfile.read(size))
                if not isinstance(body, dict):
                    raise ValueError("not an object")
                if path == "/report":
                    if not isinstance(body.get("checks"), dict):
                        raise ValueError("not a phone check report")
                    saved = server.api.report(body)
                else:
                    saved = server.api.act(body)
            except ValueError as e:
                return self.answer(400, {"error": str(e)})
            self.answer(200, saved) if saved else self.answer(204)

        def pump(self, link, on_text):
            """Reads the link's messages until it closes: text to on_text, pings answered."""
            try:
                while link.open:
                    opcode, data = read_frame(self.rfile)
                    if opcode == 1:
                        on_text(data.decode("utf-8", "replace"))
                    elif opcode == 9:
                        with link.lock:
                            self.wfile.write(frame(data, opcode=10))
                    elif opcode == 8:
                        break
            except (OSError, ValueError):
                pass
            finally:
                link.close()

        def serve_ws(self):
            self.connection.setsockopt(socket.IPPROTO_TCP, socket.TCP_NODELAY, 1)
            link = Link(self.wfile, self.client_address[0], sock=self.connection)
            server.take_over(link)
            server.on_open(link)
            try:
                self.pump(link, lambda text: server.deliver(link, text))
            finally:
                if server.release(link):
                    server.on_close(link)

        def serve_backend(self):
            link = Link(self.wfile, self.client_address[0], kind="backend", sock=self.connection)
            with server.block:
                server.backends = [b for b in server.backends if b.open]
                full = len(server.backends) >= MAX_BACKENDS
                if not full:
                    server.backends.append(link)
            if full:
                link.close(4001)
                return
            server.on_backend_open(link)
            try:
                self.pump(link, lambda text: server.on_backend(link, text))
            finally:
                server.on_backend_close(link)

    return Handler
