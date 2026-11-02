# SPDX-License-Identifier: GPL-3.0-or-later
# Copyright (C) 2026 DigitalHome.cloud
import json
import urllib.error
import urllib.request

import pytest

from dhc_edge.mock_phone import TINY_JPEG, MockPhone


def phone_of(edge):
    ph = MockPhone(f"ws://127.0.0.1:{edge.server.port}/ws")
    ph.hello()
    return ph


def backend_of(edge):
    return MockPhone(f"ws://127.0.0.1:{edge.server.port}/ws/backend?token=t0k3n", origin=False)


def api(edge, path, body=None):
    url = f"http://127.0.0.1:{edge.server.port}{path}"
    req = urllib.request.Request(url, data=json.dumps(body).encode() if body is not None else None,
                                 headers={"Content-Type": "application/json"})
    with urllib.request.urlopen(req, timeout=5) as r:
        raw = r.read()
    return json.loads(raw) if raw else None


def test_a_phone_gets_the_profile_and_the_backend_hears_it(edge):
    ph = phone_of(edge)
    assert ph.expect("web")["id"] == edge.web_id   # first: a page from an older edge reloads before it draws
    prof = ph.expect("profile")
    assert prof["profile"]["id"] == "inventory" and prof["lang"] == "en"
    e = edge.rec.expect("hello")
    assert e["v"] == "dhc-edge/0.1" and e["edge"] == "test" and e["phone"]["link"] == "usb"
    ph.close()
    assert edge.rec.expect("bye")["phone"]["model"] == "MOCK-PHONE"


def test_a_tiles_steps_come_as_one_event_with_the_profiles_data(edge):
    ph = phone_of(edge)
    ph.expect("profile")
    ph.tap("appliance", room="kitchen", photo={"jpeg": TINY_JPEG, "w": 1, "h": 1}, plate={"jpeg": TINY_JPEG, "w": 1, "h": 1, "text": "Bosch SMS"},
           note="")
    e = edge.rec.expect("tile")
    assert e["tile"] == "appliance" and e["action"] == "steps" and e["data"]["kind"] == "appliance"
    assert e["data"]["plate"]["text"] == "Bosch SMS" and e["data"]["photo"]["jpeg"] == TINY_JPEG
    # the setup page: the event without its photos, and each photo at its own address (this PC only)
    s = api(edge, "/api/state")
    last = s["events"][-1]
    assert isinstance(last["data"]["photo"]["jpeg"], int)
    with urllib.request.urlopen(f"http://127.0.0.1:{edge.server.port}/api/photo?e={last['n']}&p=plate", timeout=5) as r:
        assert r.read()[:2] == b"\xff\xd8"
    ph.close()


def test_an_unknown_tile_is_dropped(edge):
    ph = phone_of(edge)
    ph.expect("profile")
    ph.tap("nope")
    ph.tap("tag", tag={"code": "X1", "format": "qr_code"})
    assert edge.rec.expect("tile")["tile"] == "tag"
    ph.close()


def test_a_backend_gets_the_status_first_and_drives_the_phone(edge):
    ph = phone_of(edge)
    ph.expect("profile")
    b = backend_of(edge)
    st = b.expect("status")
    assert st["phone"]["model"] == "MOCK-PHONE" and "appliance" in st["tiles"]
    b.send(t="state", tile="count", value=7)
    assert ph.expect("state") == {"t": "state", "states": {"count": 7.0}}
    b.send(t="toast", text={"en": "Saved", "de": "Gespeichert"})
    assert ph.expect("toast")["text"]["de"] == "Gespeichert"
    b.send(t="state", tile="nope", value=1, id="r9")
    err = b.expect("error")
    assert "nope" in err["error"] and err["id"] == "r9"
    ph.tap("tag", tag={"code": "X1", "format": "qr_code"})
    assert b.expect("tile")["data"]["tag"]["code"] == "X1"
    b.close()
    ph.close()


def test_states_stay_for_a_phone_that_comes_back(edge):
    assert edge.command({"t": "state", "tile": "count", "value": 3, "label": "today"}) is None
    ph = phone_of(edge)
    prof = ph.expect("profile")
    assert prof["states"] == {"count": 3.0} and prof["labels"] == {"count": "today"}
    ph.close()


def test_switching_and_patching_the_profile(edge):
    ph = phone_of(edge)
    ph.expect("profile")
    assert edge.command({"t": "profile", "profile": "switch"}) is None
    assert ph.expect("profile")["profile"]["id"] == "switch"
    assert edge.rec.expect("profile")["tiles"][0] == "ceiling"
    rooms = [{"id": "r1", "label": "Room 1"}, {"id": "r2", "label": "Room 2"}]
    assert edge.command({"t": "tiles", "tiles": [{"id": "scene", "options": rooms}]}) is None
    assert ph.expect("profile")["profile"]["tiles"][2]["options"] == [{"id": "r1", "label": "Room 1"}, {"id": "r2", "label": "Room 2"}]
    assert edge.command({"t": "profile", "profile": "nope"})["t"] == "error"
    ph.close()


def test_say_without_a_phone_is_an_error(edge):
    assert edge.command({"t": "say", "text": "hi"})["error"] == "no phone"


def test_the_setup_page_tries_a_flow_without_a_phone(edge):
    api(edge, "/api/act", {"phone": {"t": "tile", "tile": "count"}})
    assert edge.rec.expect("tile")["tile"] == "count"
    api(edge, "/api/act", {"profile": "cellar"})
    assert api(edge, "/api/state")["profile"]["id"] == "cellar"
    with pytest.raises(urllib.error.HTTPError):
        api(edge, "/api/act", {"command": {"t": "fly"}})


def test_a_check_report_is_counted(edge):
    r = api(edge, "/report", {"model": "SM-A505FN", "checks": {"camera": {"ok": True, "need": "core"}}})
    assert r == {"saved": None}
    assert api(edge, "/api/state")["reports"][-1]["model"] == "SM-A505FN"

