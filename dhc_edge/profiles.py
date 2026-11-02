# SPDX-License-Identifier: GPL-3.0-or-later
# Copyright (C) 2026 DigitalHome.cloud
"""profiles.py — the phone's UX templates: profiles/<id>.json, loaded and checked (standard library only).

A profile is what the phone shows: big tiles in the style of atl-phone's Omi Assist (an icon, one word, said when
touched), each doing one action (contract.ACTIONS). docs/profiles.md describes every field; in short:

    {"id": "inventory", "title": {"en": "Inventory", ...}, "style": "tiles", "columns": 2, "lang": "en",
     "extends": "other-profile",                 (optional: its tiles by id, changed or added here; "drop": [ids])
     "home": ["room", "appliance", ...],          (optional: the tiles shown and their order; else all)
     "tiles": [{"id": "room", "icon": "🏠", "label": {...}, "action": "choice", "options": [...]}, ...]}

check() returns the profile cleaned (only known fields, defaults filled in) or raises ValueError naming the field.
"""
import json
from pathlib import Path

from . import contract as c
from .protocol import _id, _int, _num, _one_of, _options, _text, label, scalar

MAX_TILES = 24
MAX_STEPS = 8
MAX_DEPTH = 3   # extends of extends


class ProfileError(ValueError):
    pass


def _at(where, f, *a, **kw):
    try:
        return f(*a, **kw)
    except ProfileError:
        raise
    except ValueError as e:
        raise ProfileError(f"{where}: {e}")


def _action(t: dict, where: str, step: bool) -> dict:
    """The fields of one action (a tile's, or a step's)."""
    allowed = c.STEP_ACTIONS if step else c.ACTIONS
    a = _at(where + ".action", _one_of, t.get("action", "send"), allowed)
    out = {"action": a}
    if "prompt" in t:
        out["prompt"] = _at(where + ".prompt", label, t["prompt"], 120)
    if a == "send":
        data = t.get("data", {})
        if not isinstance(data, dict):
            raise ProfileError(where + ".data: not an object")
        out["data"] = {_at(where + ".data", _id, k): _at(where + ".data." + str(k), scalar, v) for k, v in data.items()}
    elif a == "state":
        if "unit" in t:
            out["unit"] = _at(where + ".unit", _text, t["unit"], 8)
    elif a == "choice":
        out["options"] = _at(where + ".options", _options, t.get("options"))
    elif a == "number":
        lo, hi = _at(where + ".min", _num, t.get("min", 0)), _at(where + ".max", _num, t.get("max", 99))
        if hi < lo:
            raise ProfileError(where + ": max is below min")
        out.update(min=lo, max=hi, step=_at(where + ".step", _num, t.get("step", 1), 1e-6, 1e6),
                   default=_at(where + ".default", _num, t.get("default", lo), lo, hi))
        if "unit" in t:
            out["unit"] = _at(where + ".unit", _text, t["unit"], 8)
    elif a == "scan":
        formats = t.get("formats", [])
        if not isinstance(formats, list):
            raise ProfileError(where + ".formats: a list")
        out["formats"] = [_at(where + ".formats", _text, f, 24) for f in formats[:16]]
        out["manual"] = bool(t.get("manual", True))   # the code may be typed when the camera reads none
    elif a == "photo":
        out["ocr"] = bool(t.get("ocr", False))
        out["max_px"] = _at(where + ".max_px", _int, t.get("max_px", 1280), 320, 1920)
    elif a == "text":
        out["max"] = _at(where + ".max", _int, t.get("max", 200), 1, 500)
    elif a == "say":
        out["text"] = _at(where + ".text", label, t.get("text"), 300)
    elif a == "steps":
        steps = t.get("steps")
        if not isinstance(steps, list) or not 1 <= len(steps) <= MAX_STEPS:
            raise ProfileError(f"{where}.steps: a list of 1-{MAX_STEPS}")
        seen, out["steps"] = set(), []
        for i, s in enumerate(steps):
            w = f"{where}.steps[{i}]"
            if not isinstance(s, dict):
                raise ProfileError(w + ": not an object")
            sid = _at(w + ".id", _id, s.get("id"))
            if sid in seen:
                raise ProfileError(f"{w}.id: {sid!r} twice")
            seen.add(sid)
            x = {"id": sid, "label": _at(w + ".label", label, s.get("label", sid), 40)}
            x.update(_action(s, w, step=True))
            out["steps"].append(x)
        out["confirm"] = bool(t.get("confirm", True))   # a last card: what was got, Send or Cancel
        data = t.get("data", {})
        if not isinstance(data, dict):
            raise ProfileError(where + ".data: not an object")
        out["data"] = {_at(where + ".data", _id, k): _at(where + ".data." + str(k), scalar, v) for k, v in data.items()}
    return out


def _tile(t, where: str) -> dict:
    if not isinstance(t, dict):
        raise ProfileError(where + ": not an object")
    out = {"id": _at(where + ".id", _id, t.get("id"))}
    out["label"] = _at(where + ".label", label, t.get("label", out["id"]), 40)
    out["icon"] = _at(where + ".icon", _text, t.get("icon", ""), 8)
    out["color"] = _at(where + ".color", _one_of, t.get("color", "blue"), c.COLORS)
    out["speak"] = bool(t.get("speak", True))   # its name is said when touched (Omi's tiles)
    out.update(_action(t, where, step=False))
    return out


def check(p) -> dict:
    """A profile (its extends already resolved), cleaned."""
    if not isinstance(p, dict):
        raise ProfileError("a profile is an object")
    out = {"id": _at("id", _id, p.get("id")), "contract": c.CONTRACT}
    out["title"] = _at("title", label, p.get("title", out["id"]), 40)
    out["style"] = _at("style", _one_of, p.get("style", "tiles"), c.STYLES)
    out["columns"] = _at("columns", _int, p.get("columns", 2), 1, 4)
    out["lang"] = _at("lang", _one_of, p.get("lang", "en"), c.LANGS)
    if "description" in p:
        out["description"] = _at("description", label, p["description"], 300)
    tiles = p.get("tiles")
    if not isinstance(tiles, list) or not 1 <= len(tiles) <= MAX_TILES:
        raise ProfileError(f"tiles: a list of 1-{MAX_TILES}")
    out["tiles"], ids = [], set()
    for i, t in enumerate(tiles):
        x = _tile(t, f"tiles[{i}]")
        if x["id"] in ids:
            raise ProfileError(f"tiles[{i}].id: {x['id']!r} twice")
        ids.add(x["id"])
        out["tiles"].append(x)
    home = p.get("home", [t["id"] for t in out["tiles"]])
    if not isinstance(home, list) or not home:
        raise ProfileError("home: a list of tile ids")
    for h in home:
        if h not in ids:
            raise ProfileError(f"home: no tile {h!r}")
    out["home"] = list(dict.fromkeys(home))
    return out


def merge(base: dict, over: dict) -> dict:
    """over on top of base: its fields win, its tiles change base's tiles of the same id (field by field) or are added;
    "drop" removes tiles. Neither is checked here."""
    out = {k: v for k, v in base.items() if k not in ("tiles", "home")}
    out.update({k: v for k, v in over.items() if k not in ("tiles", "extends", "drop")})
    tiles = [dict(t) for t in base.get("tiles", []) if isinstance(t, dict)]
    index = {t.get("id"): t for t in tiles}
    for t in over.get("tiles", []):
        if isinstance(t, dict) and t.get("id") in index:
            index[t["id"]].update(t)
        else:
            tiles.append(t)
    drop = set(over.get("drop", []))
    out["tiles"] = [t for t in tiles if t.get("id") not in drop]
    if "home" in over:
        out["home"] = over["home"]
    elif "home" in base:
        out["home"] = [h for h in base["home"] if h not in drop] + [t["id"] for t in over.get("tiles", [])
                                                                     if isinstance(t, dict) and t.get("id") not in index]
    return out


class Profiles:
    """The profiles of a folder, by id (the file's name)."""

    def __init__(self, folder):
        self.dir = Path(folder)

    def ids(self) -> list:
        return sorted(f.stem for f in self.dir.glob("*.json"))

    def raw(self, pid: str, depth=0) -> dict:
        _id(pid, "profile")
        f = self.dir / f"{pid}.json"
        if not f.is_file():
            raise ProfileError(f"no profile {pid!r} in {self.dir}")
        try:
            p = json.loads(f.read_text(encoding="utf-8"))
        except ValueError as e:
            raise ProfileError(f"{f.name}: not JSON ({e})")
        if not isinstance(p, dict):
            raise ProfileError(f"{f.name}: not an object")
        p.setdefault("id", pid)
        if p.get("extends"):
            if depth >= MAX_DEPTH:
                raise ProfileError(f"{pid}: extends too deep")
            base = self.raw(p["extends"], depth + 1)
            p = merge(base, p)
            p["id"] = pid
        return p

    def load(self, pid: str) -> dict:
        try:
            return check(self.raw(pid))
        except ProfileError as e:
            raise ProfileError(f"{pid}: {e}") if not str(e).startswith(pid) else e

    def list(self) -> list:
        """[{id, title, ok, error}] of every profile in the folder."""
        out = []
        for pid in self.ids():
            try:
                p = self.load(pid)
                out.append({"id": pid, "title": p["title"], "ok": True})
            except ValueError as e:
                out.append({"id": pid, "title": pid, "ok": False, "error": str(e)})
        return out


def patch(p: dict, tiles: list) -> dict:
    """A backend's "tiles" command on the profile shown: its tiles changed or added, checked again."""
    merged = merge(p, {"tiles": tiles})
    merged["home"] = p["home"] + [t["id"] for t in tiles if t.get("id") not in {x["id"] for x in p["tiles"]}]
    return check(merged)
