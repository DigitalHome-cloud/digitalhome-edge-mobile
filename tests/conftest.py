# SPDX-License-Identifier: GPL-3.0-or-later
# Copyright (C) 2026 DigitalHome.cloud
import sys
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))   # dhc_edge without installing it

from dhc_edge.core import Edge   # noqa: E402


class Recorder:
    """An adapter that keeps what it is told."""
    name = "rec"

    def __init__(self):
        import queue
        self.got = queue.Queue()

    def start(self):
        pass

    def stop(self):
        pass

    def event(self, e):
        self.got.put(e)

    def status(self):
        return {"ok": True, "detail": "recording"}

    def expect(self, t, timeout=3.0):
        import queue
        import time
        end = time.monotonic() + timeout
        while True:
            left = end - time.monotonic()
            if left <= 0:
                raise TimeoutError(f"no {t!r} event")
            try:
                e = self.got.get(timeout=left)
            except queue.Empty:
                continue
            if e["t"] == t:
                return e


@pytest.fixture
def edge():
    """An edge on a free port with the inventory profile, a backend token, the nodered adapter and a recording one."""
    from dhc_edge.adapters.nodered import NodeRed
    rec = Recorder()
    e = Edge(ROOT / "web", ROOT / "profiles", profile="inventory", edge_id="test", port=0, bind="127.0.0.1",
             token="t0k3n")
    e.start([rec, NodeRed(e, None)])
    e.rec = rec
    yield e
    e.stop()
