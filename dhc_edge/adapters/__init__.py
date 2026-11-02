# SPDX-License-Identifier: GPL-3.0-or-later
# Copyright (C) 2026 DigitalHome.cloud
"""adapters — how the edge reaches its backends. Each adapter carries the same events and commands (contract.py)
over its own transport; the core never knows which ones are on.

An adapter:
    name                    its name on the command line (--adapter nodered,mqtt)
    __init__(edge, opts)    edge: the Edge (core.py); opts: the command line's options (argparse.Namespace)
    start()                 connect, subscribe, listen; may raise AdapterError (the edge then does not start)
    stop()
    event(e: dict)          an event for the backend (never raises: a backend that is gone misses it)
    status() -> dict        for the setup page and the "status" event: {"ok": bool, "detail": text, ...}

and hands what its backend sends to edge.command(cmd, source=name), which checks it and answers an error event to
that adapter alone (event() with t "error"), or returns None.

Adding one: a module here with a class, and a line in KNOWN (docs/adapters.md).
"""
import importlib

KNOWN = {"nodered": "dhc_edge.adapters.nodered:NodeRed",
         "mqtt": "dhc_edge.adapters.mqtt:Mqtt",
         "ros2": "dhc_edge.adapters.ros2:Ros2"}


class AdapterError(RuntimeError):
    pass


class Adapter:
    name = ""

    def __init__(self, edge, opts):
        self.edge, self.opts = edge, opts

    def start(self):
        pass

    def stop(self):
        pass

    def event(self, e: dict):
        raise NotImplementedError

    def status(self) -> dict:
        return {"ok": True, "detail": ""}


def load(names, edge, opts) -> list:
    """The adapters named, made (not started). An unknown name, or one whose library is missing, raises AdapterError."""
    out = []
    for n in names:
        if n not in KNOWN:
            raise AdapterError(f"unknown adapter {n!r} (known: {', '.join(KNOWN)})")
        mod, _, cls = KNOWN[n].partition(":")
        try:
            out.append(getattr(importlib.import_module(mod), cls)(edge, opts))
        except ImportError as e:
            raise AdapterError(f"adapter {n}: {e.name or e} is missing (docs/adapters.md says how to get it)")
    return out
