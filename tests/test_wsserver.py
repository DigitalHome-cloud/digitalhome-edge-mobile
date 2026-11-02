# SPDX-License-Identifier: GPL-3.0-or-later
# Copyright (C) 2026 Atelier-5
# Copyright (C) 2026 DigitalHome.cloud
import io
import json
import queue
import socket
import time
import urllib.error
import urllib.request

import pytest

from conftest import ROOT
from dhc_edge.mock_phone import MockPhone
from dhc_edge.wsserver import PhoneServer, accept_key, frame, read_frame, web_id

WEB = ROOT / "web"


@pytest.fixture
def server():
    events = queue.Queue()
    s = PhoneServer(WEB, 0, "127.0.0.1", key="k3y", token="t0k", on_open=lambda l: events.put("open"),
                    on_text=lambda t: events.put(json.loads(t)), on_close=lambda l: events.put("close"),
                    on_backend=lambda l, t: events.put(("backend", json.loads(t)))).start()
    s.events = events
    yield s
    s.stop()


def url(s, key="k3y"):
    return f"ws://127.0.0.1:{s.port}/ws?key={key}"


def test_accept_key():
    assert accept_key("dGhlIHNhbXBsZSBub25jZQ==") == "s3pPLMBiTxaQ9kYGzzhZRbK+xOo="  # RFC 6455, 1.3


def test_masking_round_trip_and_fragments():
    big = bytes(range(256)) * 300
    op, data = read_frame(io.BytesIO(frame(big, mask=True)))
    assert (op, data) == (1, big)
    parts = bytes([0x01, 0x83]) + b"\0\0\0\0" + b"abc" + bytes([0x80, 0x83]) + b"\0\0\0\0" + b"def"  # text, then continuation
    assert read_frame(io.BytesIO(parts)) == (1, b"abcdef")
    with pytest.raises(ValueError):
        read_frame(io.BytesIO(frame(b"x" * 100)), limit=10)


def test_serves_the_pages(server):
    base = f"http://127.0.0.1:{server.port}"
    assert "app.js" in urllib.request.urlopen(base + "/?key=k3y", timeout=5).read().decode()  # / -> app.html
    assert "setup.js" in urllib.request.urlopen(base + "/setup.html", timeout=5).read().decode()


def test_both_ways(server):
    phone = MockPhone(url(server))
    assert server.events.get(timeout=3) == "open"
    phone.hello()
    assert server.events.get(timeout=3)["t"] == "hello"
    assert server.send(json.dumps({"t": "toast", "text": "hi"}))
    assert phone.expect("toast") == {"t": "toast", "text": "hi"}
    big = "x" * 70000  # needs a 64-bit length
    assert server.send(json.dumps({"t": "say", "text": big}))
    assert phone.expect("say")["text"] == big
    phone.close()
    assert server.events.get(timeout=3) == "close"
    assert not server.connected


def test_a_backend_speaks_and_hears_with_the_token(server):
    b = MockPhone(f"ws://127.0.0.1:{server.port}/ws/backend?token=t0k", origin=False)
    time.sleep(0.2)
    assert server.backend_count == 1
    assert server.send_backends(json.dumps({"t": "tile"})) == 1
    assert b.expect("tile") == {"t": "tile"}
    b.send(t="say", text="hello")
    assert server.events.get(timeout=3) == ("backend", {"t": "say", "text": "hello"})
    b.close()


def test_a_backend_needs_the_token(server):
    with pytest.raises(ConnectionError):
        MockPhone(f"ws://127.0.0.1:{server.port}/ws/backend?token=nope", origin=False)
    with pytest.raises(ConnectionError):
        MockPhone(f"ws://127.0.0.1:{server.port}/ws/backend", origin=False)


def test_without_a_token_only_this_pc(tmp_path):
    s = PhoneServer(WEB, 0, "127.0.0.1").start()
    try:
        b = MockPhone(f"ws://127.0.0.1:{s.port}/ws/backend", origin=False)   # loopback: in
        b.close()
    finally:
        s.stop()


def test_an_idle_link_stays_open(server):
    phone = MockPhone(url(server))
    assert server.events.get(timeout=3) == "open"
    time.sleep(1.5)
    assert server.connected
    phone.close()


def test_a_new_phone_takes_over(server):
    a = MockPhone(url(server))
    assert server.events.get(timeout=3) == "open"
    b = MockPhone(url(server))
    assert server.events.get(timeout=3) == "open"
    assert a.closed.wait(3)
    b.hello()
    assert server.events.get(timeout=3)["t"] == "hello"
    b.close()


def test_wrong_key_is_refused(server):
    with pytest.raises(ConnectionError):
        MockPhone(url(server, key="nope"))


def test_foreign_origin_is_refused(server):
    req = urllib.request.Request(f"http://127.0.0.1:{server.port}/ws?key=k3y",
                                 headers={"Origin": "http://evil.example", "Upgrade": "websocket", "Connection": "Upgrade",
                                          "Sec-WebSocket-Key": "dGhlIHNhbXBsZSBub25jZQ==", "Sec-WebSocket-Version": "13"})
    with pytest.raises(urllib.error.HTTPError) as e:
        urllib.request.urlopen(req, timeout=5)
    assert e.value.code == 403


def test_no_api_no_routes(server):
    for path in ("/api/state", "/api/photo?e=1&p=x"):
        with pytest.raises(urllib.error.HTTPError) as e:
            urllib.request.urlopen(f"http://127.0.0.1:{server.port}{path}", timeout=5)
        assert e.value.code == 403


def test_the_pages_fingerprint_changes_with_a_page(tmp_path):
    (tmp_path / "a.html").write_text("one")
    before = web_id(tmp_path)
    (tmp_path / "a.html").write_text("two")
    assert web_id(tmp_path) != before


def test_a_silent_connection_does_not_keep_other_phones_out(tmp_path):
    import subprocess
    subprocess.run(["openssl", "req", "-x509", "-newkey", "ec", "-pkeyopt", "ec_paramgen_curve:prime256v1", "-nodes",
                    "-keyout", str(tmp_path / "k.pem"), "-out", str(tmp_path / "c.pem"), "-days", "1", "-subj", "/CN=localhost"],
                   check=True, capture_output=True)
    s = PhoneServer(WEB, 0, "127.0.0.1", cert=tmp_path / "c.pem", cert_key=tmp_path / "k.pem").start()
    try:
        idle = socket.create_connection(("127.0.0.1", s.port))   # says nothing: no TLS hello
        phone = MockPhone(f"wss://127.0.0.1:{s.port}/ws", timeout=3)
        phone.close()
        idle.close()
    finally:
        s.stop()
