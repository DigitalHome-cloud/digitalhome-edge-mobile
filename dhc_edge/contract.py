# SPDX-License-Identifier: GPL-3.0-or-later
# Copyright (C) 2026 DigitalHome.cloud
"""contract.py — the names of dhc-edge/0.1, shared by the core, the profiles and every adapter (no imports).

The phone speaks to the edge (protocol.py: hello, tile, answer); the edge speaks to its backends in events and hears
commands. Every adapter carries the same JSON, only the transport differs:

    nodered  WebSocket /ws/backend on the edge's port: events out, commands in (node-red-contrib-dhc-edge)
    mqtt     <prefix>/<edge>/event/<t>  (events)   <prefix>/<edge>/command (commands)   <prefix>/<edge>/status (retained)
    ros2     /dhc_edge/<edge>/event     (std_msgs/String JSON)   /dhc_edge/<edge>/command (std_msgs/String JSON)

A change that breaks a reader raises the minor version while it is 0.x (docs/contract.md).
"""
CONTRACT = "dhc-edge/0.1"
LANGS = ("en", "fr", "de")
BACKEND_PATH = "/ws/backend"

# what a tile does (profiles.py); the ones a tile's steps may chain
ACTIONS = ("send", "toggle", "state", "choice", "number", "scan", "photo", "text", "say", "steps")
STEP_ACTIONS = ("choice", "number", "scan", "photo", "text")

# edge -> backend
EVENTS = ("status", "hello", "bye", "tile", "answer", "profile", "error")
# backend -> edge (most go on to the phone)
COMMANDS = ("profile", "tiles", "state", "say", "toast", "vibrate", "ask", "open", "home")

PAGES = ("app.html", "check.html")   # where a command may send the phone
STYLES = ("tiles", "chips")
COLORS = ("blue", "green", "yellow", "red", "grey")   # a tile's accent (web/app.html)


def mqtt_topics(prefix: str, edge: str) -> dict:
    base = f"{prefix.rstrip('/')}/{edge}"
    return {"event": base + "/event", "command": base + "/command", "status": base + "/status"}


def ros_topics(edge: str) -> dict:
    base = f"/dhc_edge/{edge}"
    return {"event": base + "/event", "command": base + "/command"}
