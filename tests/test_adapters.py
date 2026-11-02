# SPDX-License-Identifier: GPL-3.0-or-later
# Copyright (C) 2026 DigitalHome.cloud
"""The adapters against their real transports: nodered over the edge's WebSocket, mqtt against a Mosquitto started
here (skipped without mosquitto or paho-mqtt), ros2 in its image only (skipped without rclpy)."""
import json
import queue
import shutil
import socket
import subprocess
import time
from argparse import Namespace

import pytest

from conftest import ROOT
from dhc_edge import adapters
from dhc_edge.core import Edge
from dhc_edge.mock_phone import MockPhone


def free_port():
    with socket.socket() as s:
        s.bind(("127.0.0.1", 0))
        return s.getsockname()[1]


def test_unknown_adapter():
    with pytest.raises(adapters.AdapterError):
        adapters.load(["fax"], None, None)


def test_nodered_adapter():
    e = Edge(ROOT / "web", ROOT / "profiles", profile="switch", edge_id="nr", port=0, bind="127.0.0.1", token="tk")
    e.start(adapters.load(["nodered"], e, Namespace()))
    try:
        b = MockPhone(f"ws://127.0.0.1:{e.server.port}/ws/backend?token=tk", origin=False)
        assert b.expect("status")["profile"] == "switch"
        ph = MockPhone(f"ws://127.0.0.1:{e.server.port}/ws")
        ph.hello()
        ph.expect("profile")
        assert b.expect("hello")["phone"]["link"] == "usb"
        ph.tap("ceiling", value=True)
        t = b.expect("tile")
        assert (t["tile"], t["action"], t["value"]) == ("ceiling", "toggle", True)
        b.send(t="state", tile="ceiling", value=True)
        assert ph.expect("state")["states"] == {"ceiling": True}
        b.send(t="fly")
        assert b.expect("error")["source"] == "nodered"
        st = e.adapters[0].status()
        assert st["clients"] == 1 and st["token"]
        b.close()
        ph.close()
    finally:
        e.stop()


@pytest.fixture
def broker(tmp_path):
    pytest.importorskip("paho.mqtt")
    if not shutil.which("mosquitto") and not shutil.which("/usr/sbin/mosquitto"):
        pytest.skip("no mosquitto")
    port = free_port()
    (tmp_path / "m.conf").write_text(f"listener {port} 127.0.0.1\nallow_anonymous true\n")
    proc = subprocess.Popen([shutil.which("mosquitto") or "/usr/sbin/mosquitto", "-c", str(tmp_path / "m.conf")],
                            stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
    for _ in range(50):
        try:
            socket.create_connection(("127.0.0.1", port), timeout=0.2).close()
            break
        except OSError:
            time.sleep(0.1)
    yield port
    proc.terminate()
    proc.wait(5)


def test_mqtt_adapter(broker):
    import paho.mqtt.client as mqtt
    e = Edge(ROOT / "web", ROOT / "profiles", profile="cellar", edge_id="cellar1", port=0, bind="127.0.0.1")
    e.start(adapters.load(["mqtt"], e, Namespace(mqtt=f"127.0.0.1:{broker}", mqtt_prefix="dhc/edge")))
    got = queue.Queue()
    c = mqtt.Client(mqtt.CallbackAPIVersion.VERSION2, client_id="test")
    def heard(cl, u, m):
        try:
            got.put((m.topic, json.loads(m.payload), m.retain))
        except ValueError:   # the bad command this test sends, heard back on dhc/edge/cellar1/command
            pass
    c.on_message = heard
    c.connect("127.0.0.1", broker)
    c.subscribe("dhc/edge/cellar1/#", qos=1)
    c.loop_start()
    try:
        def expect(topic):
            end = time.monotonic() + 5
            while time.monotonic() < end:
                try:
                    t, m, r = got.get(timeout=0.5)
                except queue.Empty:
                    continue
                if t == topic:
                    return m, r
            raise TimeoutError(topic)
        st, retained = expect("dhc/edge/cellar1/status")
        assert st["t"] == "status" and retained
        ph = MockPhone(f"ws://127.0.0.1:{e.server.port}/ws")
        ph.hello()
        ph.expect("profile")
        assert expect("dhc/edge/cellar1/event/hello")[0]["phone"]["model"] == "MOCK-PHONE"
        ph.tap("checkin", code={"code": "3760", "format": "ean_13"}, qty=2, place="r1")
        t, _ = expect("dhc/edge/cellar1/event/tile")
        assert t["data"] == {"direction": "in", "store": "cellar", "code": {"code": "3760", "format": "ean_13"}, "qty": 2.0, "place": "r1"}
        c.publish("dhc/edge/cellar1/command", json.dumps({"t": "state", "tile": "stock", "value": 41}), qos=1)
        assert ph.expect("state")["states"] == {"stock": 41.0}
        c.publish("dhc/edge/cellar1/command", "not json", qos=1)
        assert "JSON" in expect("dhc/edge/cellar1/event/error")[0]["error"]
        assert e.adapters[0].status()["ok"]
        ph.close()
    finally:
        e.stop()
        st, _ = expect("dhc/edge/cellar1/status")
        assert st["t"] in ("offline", "status")
        c.loop_stop()


def test_ros2_adapter():
    pytest.importorskip("rclpy")
    import rclpy
    from std_msgs.msg import String
    e = Edge(ROOT / "web", ROOT / "profiles", profile="blank", edge_id="ros", port=0, bind="127.0.0.1")
    e.start(adapters.load(["ros2"], e, Namespace()))
    try:
        node = rclpy.create_node("test_listener")
        from rclpy.qos import DurabilityPolicy, QoSProfile
        got = queue.Queue()
        node.create_subscription(String, "/dhc_edge/ros/event", lambda m: got.put(json.loads(m.data)),
                                 QoSProfile(depth=10, durability=DurabilityPolicy.TRANSIENT_LOCAL))
        pub = node.create_publisher(String, "/dhc_edge/ros/command", 10)
        ph = MockPhone(f"ws://127.0.0.1:{e.server.port}/ws")
        ph.hello()
        ph.expect("profile")
        seen = set()
        end = time.monotonic() + 10
        while time.monotonic() < end and "state" not in seen:
            rclpy.spin_once(node, timeout_sec=0.2)
            while not got.empty():
                seen.add(got.get()["t"])
            if "hello" in seen:
                pub.publish(String(data=json.dumps({"t": "state", "tile": "status", "value": "ok"})))
                try:
                    if ph.expect("state", timeout=0.3)["states"] == {"status": "ok"}:
                        seen.add("state")
                except TimeoutError:
                    pass
        assert {"status", "hello", "state"} <= seen
        ph.close()
        node.destroy_node()
    finally:
        e.stop()
