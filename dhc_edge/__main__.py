# SPDX-License-Identifier: GPL-3.0-or-later
# Copyright (C) 2026 DigitalHome.cloud
"""python -m dhc_edge — the edge: the phone's pages and link, the profile, and the adapters to the backends.

    python -m dhc_edge --profile inventory --adapter nodered --token-file .edge/token
    python -m dhc_edge --profile switch --adapter nodered,mqtt --mqtt 127.0.0.1:1883
    python -m dhc_edge --profile cellar --adapter ros2            (in the ROS 2 image: docker/Dockerfile.ros2)

start.sh runs it in Docker or a venv with these options; --help lists them all.
"""
import argparse
import logging
import os
import signal
import sys
import threading
from pathlib import Path

from . import adapters, contract as c
from .core import Edge
from .profiles import ProfileError

ROOT = Path(__file__).resolve().parent.parent


def options(argv=None):
    a = argparse.ArgumentParser(prog="python -m dhc_edge", description=__doc__.splitlines()[0])
    a.add_argument("--profile", default="blank", help="the phone's template: profiles/<id>.json (default blank)")
    a.add_argument("--profiles", default=str(ROOT / "profiles"), help="the profiles' folder")
    a.add_argument("--web", default=str(ROOT / "web"), help="the pages' folder")
    a.add_argument("--docs", default=str(ROOT / "docs" / "architecture"), help="the architecture pack, at /docs/")
    a.add_argument("--reports", default="", help="the phone registry's folder (phone checks); none: not kept")
    a.add_argument("--adapter", default="nodered", help="comma-separated: " + ", ".join(adapters.KNOWN))
    a.add_argument("--edge-id", default=os.environ.get("DHC_EDGE_ID", "edge"), help="this edge's name in events and topics")
    a.add_argument("--port", type=int, default=8790)
    a.add_argument("--bind", default="0.0.0.0")
    a.add_argument("--lang", default="", choices=("",) + c.LANGS, help="the phone's language (else the profile's)")
    a.add_argument("--key", default="", help="a pairing key the phone must show (?key=)")
    a.add_argument("--token", default=os.environ.get("DHC_EDGE_TOKEN", ""), help="the backends' token (/ws/backend)")
    a.add_argument("--token-file", default="", help="read the backends' token from this file")
    a.add_argument("--cert", default="", help="https: the edge's certificate (cert.pem)")
    a.add_argument("--cert-key", default="", help="https: its key (key.pem)")
    a.add_argument("--ca", default="", help="the authority that signed it, offered to the phones at /ca.crt")
    g = a.add_argument_group("mqtt")
    g.add_argument("--mqtt", default=os.environ.get("DHC_MQTT", "127.0.0.1:1883"), help="the broker, host:port")
    g.add_argument("--mqtt-prefix", default="dhc/edge", help="topics: <prefix>/<edge-id>/event/<t>, .../command, .../status")
    g.add_argument("--mqtt-user", default=os.environ.get("DHC_MQTT_USER", ""))
    g.add_argument("--mqtt-password", default=os.environ.get("DHC_MQTT_PASSWORD", ""), help="better: DHC_MQTT_PASSWORD")
    g.add_argument("--mqtt-tls", action="store_true", help="TLS to the broker (the system's authorities)")
    a.add_argument("-v", "--verbose", action="store_true")
    o = a.parse_args(argv)
    if o.token_file:
        o.token = Path(o.token_file).read_text().strip()
    return o


def main(argv=None):
    o = options(argv)
    logging.basicConfig(level=logging.DEBUG if o.verbose else logging.INFO, format="%(asctime)s %(name)s %(message)s",
                        datefmt="%H:%M:%S")
    log = logging.getLogger("dhc_edge")
    try:
        edge = Edge(o.web, o.profiles, profile=o.profile, edge_id=o.edge_id, port=o.port, bind=o.bind, key=o.key,
                    token=o.token, cert=o.cert or None, cert_key=o.cert_key or None, ca=o.ca or None, lang=o.lang,
                    docs=o.docs, reports=o.reports or None)
        chosen = adapters.load([n.strip() for n in o.adapter.split(",") if n.strip()], edge, o)
        edge.start(chosen)
    except (ProfileError, adapters.AdapterError, OSError) as e:
        log.error("%s", e)
        return 1
    s = edge.state()
    log.info("%s edge %r, profile %s, adapters %s", c.CONTRACT, edge.edge_id, edge.profile["id"],
             ", ".join(a.name for a in chosen) or "none")
    log.info("setup page (this PC): %s://localhost:%d/setup.html", edge.server.scheme, edge.server.port)
    log.info("phone: USB %s  Wi-Fi %s", s["urls"]["usb"], s["urls"]["wifi"])
    log.info("backends: %s%s", s["urls"]["backend"], " (with the token)" if o.token else " (this PC only: no token)")
    done = threading.Event()
    signal.signal(signal.SIGTERM, lambda *_: done.set())
    try:
        done.wait()
    except KeyboardInterrupt:
        pass
    edge.stop()
    return 0


if __name__ == "__main__":
    sys.exit(main())
