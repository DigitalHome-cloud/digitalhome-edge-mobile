# SPDX-License-Identifier: GPL-3.0-or-later
# Copyright (C) 2026 DigitalHome.cloud
import json

import pytest

from conftest import ROOT
from dhc_edge import contract as c
from dhc_edge.profiles import ProfileError, Profiles, check, patch

P = Profiles(ROOT / "profiles")


def test_every_shipped_profile_is_good():
    listed = P.list()
    assert {x["id"] for x in listed} >= {"blank", "inventory", "checkinout", "cellar", "library", "switch"}
    assert all(x["ok"] for x in listed), [x for x in listed if not x["ok"]]


def test_every_label_has_three_languages():
    def labels(o):
        if isinstance(o, dict):
            for k, v in o.items():
                if k in ("label", "title", "prompt", "description", "text") and isinstance(v, dict):
                    yield v
                yield from labels(v)
        elif isinstance(o, list):
            for x in o:
                yield from labels(x)
    for pid in P.ids():
        for lbl in labels(P.load(pid)):
            assert set(lbl) == set(c.LANGS), (pid, lbl)


def test_extends_changes_tiles_by_id():
    base, cellar = P.load("checkinout"), P.load("cellar")
    assert [t["id"] for t in cellar["tiles"]] == [t["id"] for t in base["tiles"]]
    stock = next(t for t in cellar["tiles"] if t["id"] == "stock")
    assert stock["action"] == "state" and stock["icon"] == "🍇"   # kept from the base, changed here
    assert [s["id"] for s in cellar["tiles"][1]["steps"]] == ["code", "qty", "rating"]


def test_defaults_are_filled_in():
    p = check({"id": "x", "tiles": [{"id": "a"}, {"id": "n", "action": "number"}]})
    assert p["tiles"][0]["action"] == "send" and p["tiles"][0]["label"] == "a" and p["home"] == ["a", "n"]
    assert p["tiles"][1]["min"] == 0 and p["tiles"][1]["default"] == 0


@pytest.mark.parametrize("bad, where", [
    ({"id": "x", "tiles": []}, "tiles"),
    ({"id": "x", "tiles": [{"id": "a"}, {"id": "a"}]}, "twice"),
    ({"id": "x", "tiles": [{"id": "a", "action": "fly"}]}, "tiles[0].action"),
    ({"id": "x", "tiles": [{"id": "a", "action": "choice"}]}, "tiles[0].options"),
    ({"id": "x", "tiles": [{"id": "a", "action": "steps", "steps": [{"id": "s", "action": "toggle"}]}]}, "steps[0].action"),
    ({"id": "x", "tiles": [{"id": "a", "action": "number", "min": 5, "max": 1}]}, "max is below min"),
    ({"id": "x", "tiles": [{"id": "a"}], "home": ["b"]}, "home"),
    ({"id": "x", "tiles": [{"id": "a", "color": "pink"}]}, "color"),
])
def test_a_bad_profile_says_where(bad, where):
    with pytest.raises(ProfileError) as e:
        check(bad)
    assert where in str(e.value)


def test_a_backend_patches_the_tiles():
    inv = P.load("inventory")
    rooms = [{"id": "attic", "label": "Attic"}]
    out = patch(inv, [{"id": "tag", "label": "Tag"}, {"id": "new", "icon": "⭐", "action": "send"}])
    assert out["home"][-1] == "new" and next(t for t in out["tiles"] if t["id"] == "tag")["action"] == "scan"
    with pytest.raises(ProfileError):
        patch(inv, [{"id": "tag", "action": "choice"}])   # a choice needs options
    steps = patch(inv, [{"id": "appliance", "steps": [{"id": "room", "action": "choice", "options": rooms}]}])
    assert steps["tiles"][0]["steps"][0]["options"][0]["id"] == "attic"


def test_extends_loops_end(tmp_path):
    (tmp_path / "a.json").write_text(json.dumps({"extends": "b", "tiles": [{"id": "x"}]}))
    (tmp_path / "b.json").write_text(json.dumps({"extends": "a", "tiles": [{"id": "y"}]}))
    with pytest.raises(ProfileError):
        Profiles(tmp_path).load("a")
