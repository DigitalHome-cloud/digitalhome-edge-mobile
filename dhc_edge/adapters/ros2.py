# SPDX-License-Identifier: GPL-3.0-or-later
# Copyright (C) 2026 DigitalHome.cloud
"""ros2 — ROS 2 (Kilted, or any rclpy), for robot scenarios: the same JSON on two std_msgs/String topics.

    /dhc_edge/<edge>/event     each event (the "status" one too), as JSON; transient local, so a late node gets the last
    /dhc_edge/<edge>/command   commands as JSON

JSON in a String keeps the contract the same for every adapter; a robot's own node turns what it needs into typed
messages (atl-phone's bridge_node.py is the richer, typed example). Runs in docker/Dockerfile.ros2; ROS_DOMAIN_ID is
passed on by start.sh.
"""
import json
import logging
import threading

import rclpy
from rclpy.executors import SingleThreadedExecutor
from rclpy.node import Node
from rclpy.qos import DurabilityPolicy, QoSProfile
from std_msgs.msg import String

from . import Adapter
from .. import contract as c

log = logging.getLogger("dhc_edge.ros2")


class Ros2(Adapter):
    name = "ros2"

    def __init__(self, edge, opts):
        super().__init__(edge, opts)
        self.topics = c.ros_topics(edge.edge_id)
        self.node = None

    def start(self):
        if not rclpy.ok():
            rclpy.init()
        self.node = Node(f"dhc_edge_{self.edge.edge_id.replace('-', '_')}")
        latched = QoSProfile(depth=10, durability=DurabilityPolicy.TRANSIENT_LOCAL)
        self.pub = self.node.create_publisher(String, self.topics["event"], latched)
        self.node.create_subscription(String, self.topics["command"], self.on_command, 10)
        # its own executor: the global one may be spinning in a program that hosts the edge (Kilted refuses a second)
        self.executor = SingleThreadedExecutor()
        self.executor.add_node(self.node)
        self.thread = threading.Thread(target=self.executor.spin, daemon=True, name="ros2")
        self.thread.start()
        log.info("ros2: events on %s, commands on %s", self.topics["event"], self.topics["command"])

    def stop(self):
        if self.node:
            self.executor.shutdown()
            self.node.destroy_node()
        if rclpy.ok():
            rclpy.shutdown()

    def on_command(self, msg):
        err = self.edge.command(msg.data, source=self.name)
        if err:
            self.event(err)

    def event(self, e: dict):
        if self.node:
            self.pub.publish(String(data=json.dumps(e)))

    def status(self) -> dict:
        n = self.pub.get_subscription_count() if self.node else 0
        return {"ok": self.node is not None, "detail": f"{n} listening", "topics": self.topics}
