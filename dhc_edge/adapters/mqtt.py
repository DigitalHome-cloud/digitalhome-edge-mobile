# SPDX-License-Identifier: GPL-3.0-or-later
# Copyright (C) 2026 DigitalHome.cloud
"""mqtt — any MQTT broker (Mosquitto, Home Assistant's, Node-RED's mqtt nodes, an IoT platform), with paho-mqtt 2.x.

    <prefix>/<edge>/event/<t>   each event as JSON, t = tile, hello, bye, answer, profile, error (QoS 1, not retained)
    <prefix>/<edge>/command     commands as JSON (subscribed, QoS 1)
    <prefix>/<edge>/status      the "status" event, retained; {"t": "offline"} as the last will

A tile's photos travel inside its event as base64 (a few hundred KB): every broker takes it, Node-RED's json node
reads it, and nothing is split. Options: --mqtt host:port, --mqtt-prefix, --mqtt-user, DHC_MQTT_PASSWORD, --mqtt-tls.
"""
import json
import logging
import threading

import paho.mqtt.client as mqtt

from . import Adapter, AdapterError
from .. import contract as c

log = logging.getLogger("dhc_edge.mqtt")


class Mqtt(Adapter):
    name = "mqtt"

    def __init__(self, edge, opts):
        super().__init__(edge, opts)
        host, _, port = (getattr(opts, "mqtt", "") or "127.0.0.1:1883").partition(":")
        self.host, self.port = host or "127.0.0.1", int(port or 1883)
        self.topics = c.mqtt_topics(getattr(opts, "mqtt_prefix", "dhc/edge"), edge.edge_id)
        self.connected = threading.Event()
        self.detail = "not connected"
        self.client = mqtt.Client(mqtt.CallbackAPIVersion.VERSION2, client_id=f"dhc-edge-{edge.edge_id}")
        if getattr(opts, "mqtt_user", ""):
            self.client.username_pw_set(opts.mqtt_user, getattr(opts, "mqtt_password", "") or None)
        if getattr(opts, "mqtt_tls", False):
            self.client.tls_set()
        self.client.will_set(self.topics["status"], json.dumps({"v": c.CONTRACT, "edge": edge.edge_id, "t": "offline"}),
                             qos=1, retain=True)
        self.client.on_connect = self.on_connect
        self.client.on_disconnect = self.on_disconnect
        self.client.on_message = self.on_message

    def start(self):
        try:
            self.client.connect(self.host, self.port, keepalive=30)
        except OSError as e:
            raise AdapterError(f"mqtt: no broker at {self.host}:{self.port} ({e})")
        self.client.loop_start()
        if not self.connected.wait(5):
            self.client.loop_stop()
            raise AdapterError(f"mqtt: {self.host}:{self.port} did not accept the edge ({self.detail})")

    def stop(self):
        self.client.publish(self.topics["status"], json.dumps({"v": c.CONTRACT, "edge": self.edge.edge_id, "t": "offline"}),
                            qos=1, retain=True).wait_for_publish(2)
        self.client.disconnect()
        self.client.loop_stop()

    def on_connect(self, client, userdata, flags, reason, properties=None):
        if reason.is_failure:
            self.detail = str(reason)
            return
        self.detail = f"{self.host}:{self.port}"
        client.subscribe(self.topics["command"], qos=1)
        client.publish(self.topics["status"], json.dumps(self.edge.status_event()), qos=1, retain=True)
        self.connected.set()
        log.info("mqtt: connected to %s, commands on %s", self.detail, self.topics["command"])

    def on_disconnect(self, client, userdata, flags, reason, properties=None):
        self.connected.clear()
        self.detail = f"disconnected ({reason})"   # paho reconnects by itself

    def on_message(self, client, userdata, msg):
        err = self.edge.command(msg.payload.decode("utf-8", "replace"), source=self.name)
        if err:
            self.event(err)

    def event(self, e: dict):
        if e["t"] == "status":
            self.client.publish(self.topics["status"], json.dumps(e), qos=1, retain=True)
        else:
            self.client.publish(f"{self.topics['event']}/{e['t']}", json.dumps(e), qos=1)
        if e["t"] in ("hello", "bye", "profile"):   # the retained status follows the phone and the profile
            self.client.publish(self.topics["status"], json.dumps(self.edge.status_event()), qos=1, retain=True)

    def status(self) -> dict:
        return {"ok": self.connected.is_set(), "detail": self.detail, "topics": self.topics}
