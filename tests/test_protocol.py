# SPDX-License-Identifier: GPL-3.0-or-later
# Copyright (C) 2026 DigitalHome.cloud
import json

import pytest

from dhc_edge import protocol as p
from dhc_edge.mock_phone import TINY_JPEG


def test_hello_keeps_only_its_fields():
    m = p.parse(json.dumps({"t": "hello", "id": "0123456789abcdef", "ua": "x" * 999, "caps": {"camera": 1}, "screen": [1e9, -5],
                            "evil": True, "lang": "xx"}))
    assert m["ua"] == "x" * 300 and m["caps"] == {"camera": True} and m["screen"] == [10000, 0]
    assert "evil" not in m and m["lang"] == ""


def test_a_tile_with_its_parts():
    m = p.parse(json.dumps({"t": "tile", "tile": "appliance", "data": {
        "room": "kitchen", "qty": 3, "ok": True, "photo": {"jpeg": TINY_JPEG, "w": 1280, "h": 960, "text": "AEG 123"},
        "code": {"code": "4006381333931", "format": "ean_13", "extra": 1}}}))
    assert m["data"]["photo"]["text"] == "AEG 123" and m["data"]["qty"] == 3.0
    assert m["data"]["code"] == {"code": "4006381333931", "format": "ean_13"}


@pytest.mark.parametrize("bad", [
    {"t": "tile"},
    {"t": "tile", "tile": "../x"},
    {"t": "tile", "tile": "a", "data": {"p": {"jpeg": "bm90IGEganBlZw=="}}},          # not a JPEG
    {"t": "tile", "tile": "a", "data": {"p": {"jpeg": "%%%"}}},                       # not base64
    {"t": "tile", "tile": "a", "data": {"p": {"jpeg": "/9j/" + "A" * (p.MAX_PHOTO)}}},  # too big
    {"t": "tile", "tile": "a", "data": {k: {"jpeg": TINY_JPEG} for k in ("a", "b", "c")}},  # too many photos
    {"t": "tile", "tile": "a", "data": {"x": {"what": 1}}},
    {"t": "tile", "tile": "a", "data": {"x": float("nan")}},
    {"t": "nope"},
])
def test_a_bad_phone_message_is_refused(bad):
    with pytest.raises(ValueError):
        p.parse(json.dumps(bad))


def test_not_json():
    for raw in ("{", "[]", "3", None):
        with pytest.raises(ValueError):
            p.parse(raw)


def test_commands():
    assert p.command('{"t": "say", "text": "Hallo", "lang": "de"}') == {"t": "say", "text": "Hallo", "lang": "de"}
    assert p.command({"t": "state", "tile": "temp", "value": 21.5}) == {"t": "state", "states": {"temp": 21.5}}
    assert p.command({"t": "state", "states": {"a": True, "b": None}})["states"] == {"a": True, "b": None}
    assert p.command({"t": "vibrate", "ms": 99999})["ms"] == 2000
    ask = p.command({"t": "ask", "ask": "keep", "text": {"en": "Keep it?"}})
    assert [o["id"] for o in ask["options"]] == ["yes", "no"]
    assert p.to_phone(ask)["id"] == "keep"
    assert p.command({"t": "toast", "text": "x", "id": "ref-1"})["id"] == "ref-1"
    assert "id" not in p.to_phone(p.command({"t": "toast", "text": "x", "id": "ref-1"}))


@pytest.mark.parametrize("bad", [
    {"t": "rm -rf"}, {"t": "open", "page": "../../etc/passwd"}, {"t": "state"}, {"t": "state", "tile": "x", "value": {"a": 1}},
    {"t": "tiles", "tiles": []}, {"t": "tiles", "tiles": [{"label": "no id"}]}, {"t": "ask", "ask": "a", "text": "?", "options": []},
    {"t": "profile", "profile": "../x"},
])
def test_a_bad_command_is_refused(bad):
    with pytest.raises(ValueError):
        p.command(bad)


def test_the_setup_page_lists_events_without_their_photos():
    e = p.event("e", "tile", "inventory", data={"photo": {"jpeg": TINY_JPEG, "w": 1, "h": 1}, "room": "bath"})
    slim = p.without_photos(e)
    assert isinstance(slim["data"]["photo"]["jpeg"], int) and slim["data"]["room"] == "bath"
    assert e["data"]["photo"]["jpeg"] == TINY_JPEG   # the event itself is untouched
