#!/usr/bin/env bash
# SPDX-License-Identifier: GPL-3.0-or-later
# Copyright (C) 2026 Atelier-5
# Copyright (C) 2026 DigitalHome.cloud
# Makes the certificates for Wi-Fi over HTTPS: a small certificate authority of this PC (once), and the edge's
# certificate for this PC's addresses (again when the address changes, or a month before it runs out).
# Each phone installs the authority once (ca.crt; the setup page offers it), then trusts the edge.
#
#   ./scripts/make_cert.sh [DIR]     default DIR: certs/ (git-ignored)
#
# DIR/ca.key  the authority's key: it stays on this PC, never in the container nor on a phone
# DIR/ca.crt  the authority, for the phones
# DIR/cert.pem, DIR/key.pem  the edge's certificate and key (./start.sh --cert DIR)
set -euo pipefail
cd "$(dirname "$0")/.."
DIR=${1:-certs}
mkdir -p "$DIR"
chmod 700 "$DIR"
command -v openssl >/dev/null || { echo "openssl is missing: sudo apt install openssl" >&2; exit 1; }

IP=$(ip route get 192.0.2.1 2>/dev/null | awk '{for (i = 1; i < NF; i++) if ($i == "src") print $(i + 1)}')
HOST=$(hostname)
SAN="DNS:localhost,DNS:$HOST,DNS:$HOST.local,IP:127.0.0.1${IP:+,IP:$IP}"

# our own config: the system's default adds extensions of its own (a second basicConstraints makes the CA invalid)
CNF=$(mktemp)
EXT=$(mktemp)
trap 'rm -f "$CNF" "$EXT" "$DIR/cert.csr"' EXIT
printf '[req]\ndistinguished_name = dn\nx509_extensions = ca\n[dn]\n[ca]\n%s\n%s\n%s\n' \
  "basicConstraints = critical, CA:TRUE, pathlen:0" "keyUsage = critical, keyCertSign, cRLSign" \
  "subjectKeyIdentifier = hash" > "$CNF"

if [ ! -f "$DIR/ca.crt" ] || [ ! -f "$DIR/ca.key" ]; then
  # EC P-256: Android has read it since 4.x. Ten years: phones in a drawer should not lose it.
  openssl ecparam -name prime256v1 -genkey -noout -out "$DIR/ca.key"
  chmod 600 "$DIR/ca.key"
  openssl req -config "$CNF" -x509 -new -key "$DIR/ca.key" -sha256 -days 3650 \
    -subj "/O=DigitalHome edge/CN=DigitalHome edge CA ($HOST)" -out "$DIR/ca.crt"
  echo "new authority: $DIR/ca.crt (install it once on each phone)"
  rm -f "$DIR/cert.pem"   # a new authority needs a new certificate
fi

# a new certificate when there is none, it misses this address, or it runs out within 30 days
if [ -f "$DIR/cert.pem" ] && openssl x509 -in "$DIR/cert.pem" -noout -checkend $((30 * 86400)) >/dev/null \
   && openssl x509 -in "$DIR/cert.pem" -noout -text | grep -q "IP Address:${IP:-127.0.0.1}\b"; then
  echo "certificate for $HOST${IP:+ ($IP)}: still good ($DIR/cert.pem)"
  exit 0
fi
printf 'subjectAltName=%s\nbasicConstraints=critical,CA:FALSE\nkeyUsage=critical,digitalSignature\nextendedKeyUsage=serverAuth\nauthorityKeyIdentifier=keyid\n' "$SAN" > "$EXT"
openssl ecparam -name prime256v1 -genkey -noout -out "$DIR/key.pem"
chmod 600 "$DIR/key.pem"
openssl req -config "$CNF" -new -key "$DIR/key.pem" -subj "/O=DigitalHome edge/CN=$HOST" -out "$DIR/cert.csr"
# 397 days: the longest a browser accepts for a server certificate
openssl x509 -req -in "$DIR/cert.csr" -CA "$DIR/ca.crt" -CAkey "$DIR/ca.key" -CAcreateserial -sha256 -days 397 \
  -extfile "$EXT" -out "$DIR/cert.pem" 2>/dev/null
echo "new certificate for $SAN ($DIR/cert.pem)"
