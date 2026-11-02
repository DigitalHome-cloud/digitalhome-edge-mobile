#!/usr/bin/env bash
# SPDX-License-Identifier: GPL-3.0-or-later
# Copyright (C) 2026 Atelier-5
# Copyright (C) 2026 DigitalHome.cloud
# Starts the edge (in Docker, or in a venv) and opens its setup page, which guides through connecting a phone.
# The image is built when it is missing or the sources changed. The backends' token is made once, in .edge/token.
#
#   ./start.sh [--profile inventory] [--adapter nodered[,mqtt][,ros2]] [--port 8790] [--lang en|fr|de] [--edge-id ID]
#              [--make-cert [DIR] | --cert DIR] [--mqtt HOST:PORT] [--broker] [--key KEY] [--venv] [--rebuild] [--no-open]
#   ./start.sh stop | logs | token
#
# --profile: the phone's template, profiles/<id>.json (blank, inventory, checkinout, cellar, library, switch). The
#   profiles folder is mounted, so a changed profile needs no rebuild: send {"t": "profile", "profile": ID} or restart.
# --adapter: the backends: nodered (default: /ws/backend on the edge's port, for node-red-contrib-dhc-edge), mqtt
#   (--mqtt HOST:PORT, default 127.0.0.1:1883; --broker starts a Mosquitto in Docker when none listens there), ros2
#   (its own image, docker/Dockerfile.ros2; ROS_DOMAIN_ID is passed on).
# --make-cert [DIR]: Wi-Fi over HTTPS with this PC's own certificate authority (DIR default certs/): made the first
#   time, renewed when this PC's address changes. Each phone installs the authority once (the setup page offers it).
# --cert DIR: DIR/cert.pem and DIR/key.pem (and DIR/ca.crt, offered to the phones, if there is one).
# --venv: no Docker: .venv (made the first time, with paho-mqtt), in the foreground (Ctrl-C stops it).
# token: prints the backends' token (for Node-RED's "dhc edge" config node).
set -euo pipefail
cd "$(dirname "$0")"
HERE="$(pwd)"
NAME=dhc-edge
PROFILE=inventory ADAPTER=nodered PORT=8790 LANG_="" EDGE_ID=edge KEY="" CERT="" MAKE_CERT="" MQTT=127.0.0.1:1883
BROKER=0 VENV=0 REBUILD=0 OPEN=1

token() {   # the backends' token: made once, kept in .edge/ (git-ignored)
  mkdir -p .edge && chmod 700 .edge
  [ -s .edge/token ] || { head -c 18 /dev/urandom | base64 | tr '+/' '-_' > .edge/token; chmod 600 .edge/token; }
  cat .edge/token
}
case "${1:-}" in
  stop) docker rm -f "$NAME" >/dev/null 2>&1 && echo "stopped" || echo "not running"; exit 0 ;;
  logs) exec docker logs -f "$NAME" ;;
  token) token; exit 0 ;;
esac
while [ $# -gt 0 ]; do
  case "$1" in
    --profile) PROFILE=$2; shift 2 ;;
    --adapter) ADAPTER=$2; shift 2 ;;
    --port) PORT=$2; shift 2 ;;
    --lang) LANG_=$2; shift 2 ;;
    --edge-id) EDGE_ID=$2; shift 2 ;;
    --key) KEY=$2; shift 2 ;;
    --cert) CERT=$(cd "$2" && pwd); shift 2 ;;
    --make-cert) if [ -n "${2:-}" ] && [ "${2#--}" = "$2" ]; then MAKE_CERT=$2; shift; else MAKE_CERT=certs; fi; shift ;;
    --mqtt) MQTT=$2; shift 2 ;;
    --broker) BROKER=1; shift ;;
    --venv) VENV=1; shift ;;
    --rebuild) REBUILD=1; shift ;;
    --no-open) OPEN=0; shift ;;
    -h|--help) sed -n '5,22p' "$0" | sed 's/^# \{0,1\}//'; exit 0 ;;
    *) echo "unknown option: $1 (see --help)" >&2; exit 2 ;;
  esac
done
[ -f "profiles/$PROFILE.json" ] || { echo "no profile $PROFILE (profiles/: $(cd profiles && ls *.json | sed 's/\.json//' | tr '\n' ' '))" >&2; exit 2; }
if [ -n "$MAKE_CERT" ]; then
  ./scripts/make_cert.sh "$MAKE_CERT"
  CERT=$(cd "$MAKE_CERT" && pwd)
fi
TOKEN=$(token)
docker rm -f "$NAME" >/dev/null 2>&1 || true
if ss -ltn "( sport = :$PORT )" | grep -q LISTEN; then
  echo "port $PORT is taken (by: $(ss -ltnp "( sport = :$PORT )" | grep -o 'users:(("[^"]*' | cut -d'"' -f2 | head -1)); try --port" >&2
  exit 1
fi
if [ "$BROKER" = 1 ] && [[ ",$ADAPTER," == *",mqtt,"* ]]; then
  if ss -ltn "( sport = :${MQTT##*:} )" | grep -q LISTEN; then
    echo "a broker already listens on ${MQTT##*:}: using it"
  else
    docker rm -f dhc-edge-mqtt >/dev/null 2>&1 || true
    docker run -d --rm --name dhc-edge-mqtt --net=host -v "$HERE/docker/mosquitto.conf:/mosquitto/config/mosquitto.conf:ro" \
      eclipse-mosquitto:2.0.20 >/dev/null
    echo "Mosquitto on 1883 (docker: dhc-edge-mqtt)"
  fi
fi

ARGS=(--profile "$PROFILE" --adapter "$ADAPTER" --port "$PORT" --edge-id "$EDGE_ID" --mqtt "$MQTT")
[ -n "$LANG_" ] && ARGS+=(--lang "$LANG_")
[ -n "$KEY" ] && ARGS+=(--key "$KEY")
SCHEME=http
if [ -n "$CERT" ]; then
  [ -f "$CERT/cert.pem" ] && [ -f "$CERT/key.pem" ] || { echo "$CERT needs cert.pem and key.pem" >&2; exit 1; }
  SCHEME=https
fi
open_setup() {
  [ "$OPEN" = 1 ] || return 0
  for _ in $(seq 40); do curl -sfk -o /dev/null "$SCHEME://localhost:$PORT/setup.html" && break; sleep 0.25; done
  command -v xdg-open >/dev/null && xdg-open "$SCHEME://localhost:$PORT/setup.html" >/dev/null 2>&1 || true
}
echo "backends: ${SCHEME/http/ws}://$(hostname -I | awk '{print $1}'):$PORT/ws/backend   token: $TOKEN   (./start.sh token)"

if [ "$VENV" = 1 ]; then
  if [ ! -x .venv/bin/python ]; then
    python3 -m venv .venv && .venv/bin/pip install -q paho-mqtt==2.1.0
  fi
  mkdir -p reports
  ARGS+=(--token-file .edge/token --reports reports)
  [ -n "$CERT" ] && ARGS+=(--cert "$CERT/cert.pem" --cert-key "$CERT/key.pem") && [ -f "$CERT/ca.crt" ] && ARGS+=(--ca "$CERT/ca.crt")
  open_setup &
  exec env -u PYTHONPATH .venv/bin/python -m dhc_edge "${ARGS[@]}"
fi

# Docker: the plain image, or the ROS 2 one when the ros2 adapter is on
if [[ ",$ADAPTER," == *",ros2,"* ]]; then IMAGE=dhc-edge:ros2-kilted DOCKERFILE=docker/Dockerfile.ros2; else IMAGE=dhc-edge:latest DOCKERFILE=docker/Dockerfile; fi
SRC=$( { find dhc_edge web docker -type f -not -path '*/__pycache__/*' -print0
         find docs/architecture -maxdepth 1 -type f -name '*.html' -print0 2>/dev/null; } | sort -z | xargs -0 sha256sum | sha256sum | cut -c1-16)
HAVE=$(docker image inspect --format '{{index .Config.Labels "dhc.src"}}' "$IMAGE" 2>/dev/null || true)
if [ "$REBUILD" = 1 ] || [ "$HAVE" != "$SRC" ]; then
  echo "building $IMAGE…"
  docker build -q --label "dhc.src=$SRC" -f "$DOCKERFILE" -t "$IMAGE" . >/dev/null
fi
mkdir -p "$HERE/reports"
MOUNT=(-v "$HERE/profiles:/app/profiles:ro" -v "$HERE/.edge/token:/edge/token:ro" -v "$HERE/reports:/reports")
ARGS+=(--token-file /edge/token --reports /reports)
if [ -n "$CERT" ]; then
  # the files the edge needs, one by one: an authority's key next to them stays on this PC
  MOUNT+=(-v "$CERT/cert.pem:/certs/cert.pem:ro" -v "$CERT/key.pem:/certs/key.pem:ro")
  ARGS+=(--cert /certs/cert.pem --cert-key /certs/key.pem)
  if [ -f "$CERT/ca.crt" ]; then MOUNT+=(-v "$CERT/ca.crt:/certs/ca.crt:ro"); ARGS+=(--ca /certs/ca.crt); fi
fi
# Fast DDS between containers: their shared memory is not shared, so UDP only (as atl-phone)
docker run -d --rm --name "$NAME" --net=host --user "$(id -u):$(id -g)" -e HOME=/tmp \
  -e ROS_DOMAIN_ID="${ROS_DOMAIN_ID:-0}" -e FASTDDS_BUILTIN_TRANSPORTS=UDPv4 -e DHC_MQTT_PASSWORD="${DHC_MQTT_PASSWORD:-}" \
  "${MOUNT[@]}" "$IMAGE" "${ARGS[@]}" >/dev/null
echo "edge $EDGE_ID running ($IMAGE, profile $PROFILE, adapters $ADAPTER); setup page: $SCHEME://localhost:$PORT/setup.html"
echo "logs: ./start.sh logs   stop: ./start.sh stop   phone over USB: ./scripts/usb.sh"
open_setup
