# SPDX-License-Identifier: GPL-3.0-or-later
# Copyright (C) 2026 DigitalHome.cloud
"""core.py — the edge: one phone, the profile it shows, the tiles' states, and the adapters it tells.

    phone (web/app.html)  --hello, tile, answer-->  Edge  --events-->  adapters (nodered, mqtt, ros2)
                          <--profile, state, ...--        <--commands--

The phone decides nothing and keeps nothing: it shows the profile and says what the person did. The edge keeps the
profile and the states a backend set (so a phone that comes back sees them at once), and the last events for the
setup page, photos included, in memory only: nothing is written to disk but the phone check's reports.
"""
import base64
import ipaddress
import json
import logging
import re
import threading
import time
from collections import OrderedDict, deque

from . import contract as c
from . import protocol as p
from .profiles import ProfileError, Profiles, patch
from .registry import Registry
from .wsserver import PhoneServer, lan_address, web_id

log = logging.getLogger("dhc_edge")
KEEP_EVENTS = 60   # for the setup page's log
KEEP_PHOTOS = 6    # events whose photos the setup page may still show


class Edge:
    def __init__(self, web_dir, profiles_dir, profile="blank", edge_id="edge", port=8790, bind="0.0.0.0", key="",
                 token="", cert=None, cert_key=None, ca=None, lang="", docs=None, reports=None):
        self.edge_id = p._id(edge_id, "edge")
        self.lang = lang if lang in c.LANGS else ""
        self.key = key
        self.profiles = Profiles(profiles_dir)
        self.profile = self.profiles.load(profile)
        self.states, self.labels = {}, {}
        self.phone, self.phone_link, self.since = None, "", None
        self.events, self.photos, self.seq = deque(maxlen=KEEP_EVENTS), OrderedDict(), 0
        self.adapters = []
        self.lock = threading.RLock()
        self.web_id = web_id(web_dir)
        self.registry = Registry(reports) if reports else None
        self.reports = []
        self.server = PhoneServer(web_dir, port, bind, key=key, on_open=self.opened, on_text=self.text,
                                  on_close=self.closed, cert=cert, cert_key=cert_key, api=self, ca=ca, docs=docs,
                                  token=token)

    # ---- running ---------------------------------------------------------------------------------------------
    def start(self, adapters=()):
        self.adapters = list(adapters)
        for a in self.adapters:
            a.start()
        self.server.start()
        self.emit(self.status_event())
        return self

    def stop(self):
        for a in self.adapters:
            try:
                a.stop()
            except Exception as e:   # one adapter's trouble must not keep the others running
                log.warning("stopping %s: %s", a.name, e)
        self.server.stop()

    def emit(self, e: dict, only=None):
        """An event to every adapter (only: to that one), and into the setup page's log."""
        if e["t"] != "status":
            with self.lock:
                self.seq += 1
                e["n"] = self.seq
                photos = {k: x["jpeg"] for k, x in (e.get("data") or {}).items() if isinstance(x, dict) and "jpeg" in x}
                if photos:
                    self.photos[self.seq] = photos
                    while len(self.photos) > KEEP_PHOTOS:
                        self.photos.popitem(last=False)
                self.events.append(p.without_photos(e))
        for a in self.adapters:
            if only is None or a.name == only:
                try:
                    a.event(e)
                except Exception as x:   # a backend that is gone misses the event; the phone goes on
                    log.warning("%s: event %s not sent: %s", a.name, e["t"], x)

    def event(self, t, **fields) -> dict:
        return p.event(self.edge_id, t, self.profile["id"], **fields)

    def status_event(self) -> dict:
        with self.lock:
            return self.event("status", phone=self.phone_info(), states=dict(self.states),
                              tiles=[t["id"] for t in self.profile["tiles"]], adapters=[a.name for a in self.adapters])

    def phone_info(self):
        if not self.phone or not self.server.connected:
            return None
        return {"id": self.phone["id"], "model": self.phone["model"] or model_of(self.phone["ua"]),
                "link": self.phone_link, "secure": self.phone["secure"], "caps": self.phone["caps"]}

    # ---- the phone ---------------------------------------------------------------------------------------------
    def opened(self, link):
        self.phone_link = "usb" if ipaddress.ip_address(link.peer).is_loopback else "wifi"
        log.info("phone link from %s (%s)", link.peer, self.phone_link)

    def text(self, raw: str):
        try:
            m = p.parse(raw)
        except ValueError as e:
            log.info("phone: refused (%s)", e)
            return
        self.handle(m)

    def handle(self, m: dict):
        if m["t"] == "hello":
            with self.lock:
                self.phone, self.since = m, time.time()
            self.server.send(json.dumps(p.web(self.web_id)))
            self.send_profile()
            log.info("phone: %s", self.phone_info())
            self.emit(self.event("hello", phone=self.phone_info()))
        elif m["t"] == "tile":
            tile = self.tile(m["tile"])
            if not tile:
                log.info("phone: no tile %r in %s", m["tile"], self.profile["id"])
                return
            e = self.event("tile", tile=tile["id"], action=tile["action"], label=tile["label"])
            for k in ("value", "data"):
                if k in m:
                    e[k] = m[k]
            if tile["action"] in ("send", "steps") and tile.get("data"):
                e["data"] = dict(tile["data"], **e.get("data", {}))   # the profile's fixed data, under what was got
            self.emit(e)
        elif m["t"] == "answer":
            self.emit(self.event("answer", ask=m["id"], value=m["value"]))

    def closed(self, link):
        log.info("phone gone")
        with self.lock:
            had, self.phone = self.phone, None
        if had:
            self.emit(self.event("bye", phone={"id": had["id"], "model": had["model"] or model_of(had["ua"])}))

    def tile(self, tid):
        return next((t for t in self.profile["tiles"] if t["id"] == tid), None)

    def send_profile(self):
        with self.lock:
            msg = p.profile(self.profile, dict(self.states), self.lang or self.profile["lang"])
            msg["labels"] = dict(self.labels)
        self.server.send(json.dumps(msg))

    # ---- the backends --------------------------------------------------------------------------------------------
    def command(self, raw, source="") -> dict:
        """A backend's command: done, or an "error" event (for that backend alone) saying why not."""
        ref = None
        try:
            cmd = p.command(raw)
            ref = cmd.get("id")
            t = cmd["t"]
            if t == "profile":
                prof = self.profiles.load(cmd["profile"])
                with self.lock:
                    self.profile, self.states, self.labels = prof, {}, {}
                self.send_profile()
                log.info("%s: profile %s", source, prof["id"])
                self.emit(self.event("profile", title=prof["title"], tiles=[x["id"] for x in prof["tiles"]]))
            elif t == "tiles":
                with self.lock:
                    self.profile = patch(self.profile, cmd["tiles"])
                self.send_profile()
            elif t == "state":
                unknown = [k for k in cmd["states"] if not self.tile(k)]
                if unknown:
                    raise ValueError(f"no tile {unknown[0]!r} in {self.profile['id']}")
                with self.lock:
                    self.states.update(cmd["states"])
                    if "label" in cmd:
                        for k in cmd["states"]:
                            self.labels[k] = cmd["label"]
                self.server.send(json.dumps(p.to_phone(cmd)))
            elif not self.server.send(json.dumps(p.to_phone(cmd))):
                raise ValueError("no phone")
            return None
        except ValueError as e:   # ProfileError too
            log.info("%s: command refused (%s)", source or "backend", e)
            err = self.event("error", error=str(e), source=source)
            if ref:
                err["id"] = ref
            return err

    def backend_url(self) -> str:
        ws = "wss" if self.server.scheme == "https" else "ws"
        return f"{ws}://{lan_address()}:{self.server.port}{c.BACKEND_PATH}"

    # ---- the setup page (wsserver api) ---------------------------------------------------------------------------
    def state(self) -> dict:
        q = f"?key={self.key}" if self.key else ""
        port, scheme = self.server.port, self.server.scheme
        with self.lock:
            return {"contract": c.CONTRACT, "edge": self.edge_id, "now": time.time(), "web": self.web_id,
                    "urls": {"usb": f"{scheme}://localhost:{port}/{q}", "wifi": f"{scheme}://{lan_address()}:{port}/{q}",
                             "ca": f"{scheme}://{lan_address()}:{port}/ca.crt" if self.server.ca else None,
                             "backend": self.backend_url()},
                    "secure_wifi": scheme == "https", "connected": self.server.connected, "phone": self.phone_info(),
                    "since": self.since, "profile": self.profile, "profiles": self.profiles.list(),
                    "states": dict(self.states), "labels": dict(self.labels),
                    "adapters": [dict(a.status(), name=a.name) for a in self.adapters],
                    "events": list(self.events), "reports": self.reports[-3:], "docs": bool(self.server.docs)}

    def act(self, body: dict):
        """The setup page: a command as a backend would send it ({"command": {...}}), a profile to show
        ({"profile": id}), or what a phone would send ({"phone": {...}}, to try a flow without a phone)."""
        if "command" in body:
            err = self.command(body["command"], source="setup")
            if err:
                raise ValueError(err["error"])
        elif "profile" in body:
            err = self.command({"t": "profile", "profile": body["profile"]}, source="setup")
            if err:
                raise ValueError(err["error"])
        elif "phone" in body:
            m = p.parse(json.dumps(body["phone"]))
            if m["t"] == "hello":
                raise ValueError("a pretend phone sends tiles and answers only")
            self.handle(m)
        else:
            raise ValueError("unknown act")

    def report(self, body: dict):
        """A phone check's report (check.html): its checks, and into the registry when the edge has one."""
        model = body.get("model") if isinstance(body.get("model"), str) else ""
        r = {"id": p.phone_id(body.get("phone_id")), "model": model.strip()[:40] or model_of(str(body.get("userAgent", ""))),
             "at": time.time(),
             "checks": {str(k)[:40]: {"ok": v.get("ok"), "note": str(v.get("note", ""))[:200], "need": v.get("need")}
                        for k, v in list(body["checks"].items())[:60] if isinstance(v, dict)}}
        with self.lock:
            self.reports = (self.reports + [r])[-10:]
        core = [k for k, v in r["checks"].items() if v["need"] == "core" and v["ok"] is False]
        log.info("phone check from %s: %s", r["model"], f"core missing: {', '.join(core)}" if core else "core complete")
        if not self.registry:
            return {"saved": None}
        try:
            path = self.registry.check(body, r["model"])
        except OSError as e:
            log.warning("the registry could not keep it: %s", e)
            return {"saved": None, "error": str(e)}
        return {"saved": f"reports/{path.relative_to(self.registry.dir)}"}

    def photo(self, e: int, part: str):
        with self.lock:
            b64 = self.photos.get(e, {}).get(part)
        return base64.b64decode(b64) if b64 else None


def model_of(ua: str) -> str:
    """'... (Linux; Android 8.0.0; SM-G950F) ...' -> 'SM-G950F'. Chrome 110+ hides it as 'K' (then: client hints)."""
    m = re.search(r"Android ([\d.]+); ([^;)]+)", ua or "")
    if not m:
        return "unknown"
    return f"Android {m.group(1)} phone" if m.group(2).strip() == "K" else m.group(2).strip()[:40]
