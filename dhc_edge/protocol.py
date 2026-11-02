# SPDX-License-Identifier: GPL-3.0-or-later
# Copyright (C) 2026 Atelier-5
# Copyright (C) 2026 DigitalHome.cloud
"""protocol.py — the JSON messages of dhc-edge/0.1, checked both ways (standard library only).

Phone -> edge:   {"t": "hello" | "tile" | "answer", ...}            parse()
Edge -> phone:   {"t": "profile" | "state" | "say" | "toast" | "vibrate" | "ask" | "open" | "home" | "web", ...}
Backend -> edge: {"t": "profile" | "tiles" | "state" | "say" | "toast" | "vibrate" | "ask" | "open" | "home", ...}
                 command(); an optional "id" comes back in the error that refuses it
Edge -> backend: {"v": CONTRACT, "edge": ..., "t": <event>, "profile": ..., "ts": ..., ...}   event()

"tile" is what a person did: a tap (send, toggle, state), a pick, or a tile's steps done, with what each step got
("data": {step id: part}). A part is text, a number, true/false, or an object: a photo {"jpeg": base64, "w", "h",
"text": what OCR read}, a code {"code", "format"}. Photos leave the phone only as the part of a tile whose profile says
"photo": the person took them for this.

"web" is the fingerprint of the pages the edge serves, sent on each hello: a page that an older edge served sees it
change and reloads, so the phone never runs old code against a new edge (as in atl-phone).

Neither a phone nor a backend is trusted: parse() and command() return a clean message or raise ValueError, and every
number is finite and clamped.
"""
import base64
import binascii
import json
import math
import re
import time

from . import contract as c

ID = re.compile(r"[A-Za-z0-9_-]{1,32}")
B64 = re.compile(r"[A-Za-z0-9+/]*={0,2}")
MAX_PHOTO = 1400 * 1024    # bytes of one photo as base64 (a 1280 px JPEG at 0.8 is about 150-400 KB)
MAX_PHOTOS = 2             # photos in one tile's data
MAX_PARTS = 12
MAX_TEXT = 2000            # what OCR read off a type plate
MAX_OPTIONS = 12


def _num(v, lo=-1e9, hi=1e9) -> float:
    if isinstance(v, bool) or not isinstance(v, (int, float)) or not math.isfinite(v):
        raise ValueError(f"not a number: {v!r}")
    return float(min(max(float(v), lo), hi))


def _int(v, lo, hi) -> int:
    return int(_num(v, lo, hi))


def _one_of(v, allowed):
    if v not in allowed:
        raise ValueError(f"{v!r} is not one of {', '.join(allowed)}")
    return v


def _text(v, n=200) -> str:
    if not isinstance(v, str):
        raise ValueError("not text")
    return v[:n]


def _id(v, what="id") -> str:
    if not isinstance(v, str) or not ID.fullmatch(v):
        raise ValueError(f"{what}: an id is 1-32 letters, digits, - and _")
    return v


def label(v, n=40):
    """A label: text, or {"en", "fr", "de"} (each optional)."""
    if isinstance(v, dict):
        out = {k: _text(v[k], n) for k in c.LANGS if isinstance(v.get(k), str)}
        if not out:
            raise ValueError("a label needs a text")
        return out
    return _text(v, n)


def scalar(v, n=200):
    """A value: text, a number, true/false or null."""
    if v is None or isinstance(v, bool):
        return v
    if isinstance(v, (int, float)):
        return _num(v)
    return _text(v, n)


def phone_id(v) -> str:
    """The page's random id for this browser (16 hex digits), or "" when it has none or sends something else."""
    return v if isinstance(v, str) and re.fullmatch(r"[0-9a-f]{16}", v) else ""


def _jpeg(v) -> str:
    if not isinstance(v, str) or len(v) > MAX_PHOTO or not B64.fullmatch(v):
        raise ValueError("a photo is a base64 JPEG of at most %d KB" % (MAX_PHOTO // 1024))
    try:
        head = base64.b64decode(v[:8] + "=" * (-len(v[:8]) % 4))
    except (binascii.Error, ValueError):
        raise ValueError("not base64")
    if not head.startswith(b"\xff\xd8"):
        raise ValueError("not a JPEG")
    return v


def part(v):
    """One step's result: a scalar, a photo or a code (only their own fields)."""
    if not isinstance(v, dict):
        return scalar(v, 500)
    if "jpeg" in v:
        out = {"jpeg": _jpeg(v["jpeg"]), "w": _int(v.get("w", 0), 0, 10000), "h": _int(v.get("h", 0), 0, 10000)}
        if v.get("text") is not None:
            out["text"] = _text(v["text"], MAX_TEXT)
        return out
    if "code" in v:
        return {"code": _text(v["code"], 500), "format": _text(v.get("format", ""), 24)}
    raise ValueError("a part is text, a number, true/false, a photo or a code")


def _data(v) -> dict:
    if not isinstance(v, dict):
        raise ValueError("data: not an object")
    if len(v) > MAX_PARTS:
        raise ValueError(f"data: at most {MAX_PARTS} parts")
    out = {_id(k, "data"): part(x) for k, x in v.items()}
    if sum(1 for x in out.values() if isinstance(x, dict) and "jpeg" in x) > MAX_PHOTOS:
        raise ValueError(f"data: at most {MAX_PHOTOS} photos")
    return out


def parse(raw: str) -> dict:
    """A message from the phone, checked."""
    try:
        m = json.loads(raw)
    except (TypeError, ValueError):
        raise ValueError("not JSON")
    if not isinstance(m, dict):
        raise ValueError("not an object")
    t = m.get("t")
    if t == "hello":
        caps = m.get("caps") if isinstance(m.get("caps"), dict) else {}
        screen = m.get("screen") if isinstance(m.get("screen"), list) and len(m["screen"]) == 2 else [0, 0]
        return {"t": "hello", "id": phone_id(m.get("id")), "ua": _text(m.get("ua", ""), 300),
                "model": _text(m.get("model", ""), 60) if isinstance(m.get("model"), str) else "",
                "secure": bool(m.get("secure")), "lang": m["lang"] if m.get("lang") in c.LANGS else "",
                "caps": {_id(k, "caps"): bool(x) for k, x in list(caps.items())[:20]},
                "screen": [_int(x, 0, 10000) for x in screen]}
    if t == "tile":
        out = {"t": "tile", "tile": _id(m.get("tile"), "tile")}
        if "value" in m:
            out["value"] = scalar(m["value"], 500)
        if "data" in m:
            out["data"] = _data(m["data"])
        return out
    if t == "answer":
        return {"t": "answer", "id": _id(m.get("id"), "answer"), "value": scalar(m.get("value"), 200)}
    raise ValueError(f"unknown message {t!r}")


# ---- backend -> edge --------------------------------------------------------------------------------------------
def _options(v) -> list:
    if not isinstance(v, list) or not 1 <= len(v) <= MAX_OPTIONS:
        raise ValueError(f"options: a list of 1-{MAX_OPTIONS}")
    out = []
    for o in v:
        if not isinstance(o, dict):
            raise ValueError("an option is {id, label}")
        x = {"id": _id(o.get("id"), "option"), "label": label(o.get("label", o.get("id")), 40)}
        if o.get("icon"):
            x["icon"] = _text(o["icon"], 8)
        out.append(x)
    return out


def command(m) -> dict:
    """A backend's command, checked: raw JSON text or an object. "tiles" is checked again against the profile."""
    if isinstance(m, (str, bytes)):
        try:
            m = json.loads(m)
        except ValueError:
            raise ValueError("not JSON")
    if not isinstance(m, dict):
        raise ValueError("not an object")
    t = _one_of(m.get("t"), c.COMMANDS)
    out = {"t": t}
    if isinstance(m.get("id"), str):
        out["id"] = m["id"][:64]   # the backend's own reference, handed back with an error
    if t == "profile":
        out["profile"] = _id(m.get("profile"), "profile")
    elif t == "tiles":
        tiles = m.get("tiles")
        if not isinstance(tiles, list) or not tiles or not all(isinstance(x, dict) and "id" in x for x in tiles):
            raise ValueError("tiles: a list of tiles, each with its id")
        out["tiles"] = tiles
    elif t == "state":
        states = m.get("states") if isinstance(m.get("states"), dict) else {m.get("tile"): m.get("value")}
        if not states or len(states) > 64:
            raise ValueError("state: a tile and its value, or states {tile: value}")
        out["states"] = {_id(k, "tile"): scalar(v) for k, v in states.items()}
        if "label" in m:   # a word under the value (one tile only)
            out["label"] = label(m["label"], 40)
    elif t == "say":
        out["text"] = _text(m.get("text"), 500)
        if m.get("lang") in c.LANGS:
            out["lang"] = m["lang"]
    elif t == "toast":
        out["text"] = label(m.get("text"), 300)
        out["ms"] = _int(m.get("ms", 4000), 500, 60000)
    elif t == "vibrate":
        out["ms"] = _int(m.get("ms", 200), 0, 2000)
    elif t == "ask":
        out["ask"] = _id(m.get("ask"), "ask")
        out["text"] = label(m.get("text"), 300)
        out["options"] = _options(m.get("options", [{"id": "yes", "label": {"en": "Yes", "fr": "Oui", "de": "Ja"}},
                                                    {"id": "no", "label": {"en": "No", "fr": "Non", "de": "Nein"}}]))
        out["say"] = bool(m.get("say", True))
    elif t == "open":
        out["page"] = _one_of(m.get("page"), c.PAGES)
    return out


# ---- edge -> phone ----------------------------------------------------------------------------------------------
def profile(p: dict, states: dict, lang: str) -> dict:
    return {"t": "profile", "profile": p, "states": states, "lang": lang}


def state(states: dict, lbl=None) -> dict:
    out = {"t": "state", "states": states}
    if lbl is not None:
        out["label"] = lbl
    return out


def to_phone(cmd: dict) -> dict:
    """A checked command as the phone gets it (its "id" stays with the edge)."""
    if cmd["t"] == "state":
        return state(cmd["states"], cmd.get("label"))
    if cmd["t"] == "ask":
        return {"t": "ask", "id": cmd["ask"], "text": cmd["text"], "options": cmd["options"], "say": cmd["say"]}
    return {k: v for k, v in cmd.items() if k != "id"}


def web(fingerprint: str) -> dict:
    return {"t": "web", "id": fingerprint}


# ---- edge -> backend --------------------------------------------------------------------------------------------
def event(edge: str, t: str, profile_id: str, **fields) -> dict:
    _one_of(t, c.EVENTS)
    return dict({"v": c.CONTRACT, "edge": edge, "t": t, "profile": profile_id, "ts": round(time.time(), 3)}, **fields)


def without_photos(e: dict) -> dict:
    """The event as the setup page lists it: each photo replaced by its size (it has its own address)."""
    data = e.get("data")
    if not isinstance(data, dict):
        return e
    slim = {k: ({**x, "jpeg": len(x["jpeg"]) * 3 // 4} if isinstance(x, dict) and "jpeg" in x else x)
            for k, x in data.items()}
    return {**e, "data": slim}
