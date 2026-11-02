# SPDX-License-Identifier: GPL-3.0-or-later
# Copyright (C) 2026 DigitalHome.cloud
"""nodered — Node-RED (node-red-contrib-dhc-edge), or any WebSocket client, on the edge's own port: /ws/backend.

Every backend link gets every event as one JSON text frame, and its first is a "status" event (the phone, the
profile, the tiles' states), so a flow that connects late knows where things are. A text frame from it is a command;
a refused one comes back to that link alone as an "error" event. The token is the edge's --token (start.sh keeps
one in .edge/token); without one only this PC may connect.
"""
import json

from . import Adapter


class NodeRed(Adapter):
    name = "nodered"

    def __init__(self, edge, opts):
        super().__init__(edge, opts)
        self.seen = 0   # backends that came since the start

    def start(self):
        s = self.edge.server
        s.on_backend_open = self.opened
        s.on_backend = self.text
        s.on_backend_close = lambda link: None

    def opened(self, link):
        self.seen += 1
        link.send(json.dumps(self.edge.status_event()))

    def text(self, link, raw: str):
        err = self.edge.command(raw, source=self.name)
        if err:
            link.send(json.dumps(err))

    def event(self, e: dict):
        self.edge.server.send_backends(json.dumps(e))

    def status(self) -> dict:
        n = self.edge.server.backend_count
        return {"ok": n > 0, "detail": f"{n} connected", "clients": n, "url": self.edge.backend_url(),
                "token": bool(self.edge.server.token)}
