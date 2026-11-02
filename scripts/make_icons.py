#!/usr/bin/env python3
# SPDX-License-Identifier: GPL-3.0-or-later
# Copyright (C) 2026 DigitalHome.cloud
"""Draws the app's icons (web/icons/home-192.png, home-512.png): a white house on the tiles' blue, safe for a
maskable icon (the house inside the middle 60 %). Standard library only: a PNG written by hand.

    python3 scripts/make_icons.py
"""
import struct
import zlib
from pathlib import Path

BLUE, WHITE, DARK = (16, 48, 58), (255, 255, 255), (63, 216, 255)


def inside_house(x, y):
    """x, y in 0..1; the house: a roof (a triangle) on a body, with a door."""
    if 0.30 <= x <= 0.70 and 0.48 <= y <= 0.78:            # body
        return not (0.45 <= x <= 0.55 and 0.60 <= y <= 0.78)   # the door is cut out
    if 0.24 <= y <= 0.50:                                   # roof: from (0.5, 0.24) to (0.22..0.78, 0.50)
        half = (y - 0.24) / 0.26 * 0.28
        return abs(x - 0.5) <= half
    return False


def png(n):
    rows = []
    for j in range(n):
        row = bytearray([0])
        for i in range(n):
            x, y = (i + 0.5) / n, (j + 0.5) / n
            c = WHITE if inside_house(x, y) else DARK if abs(y - 0.84) < 0.015 and 0.26 < x < 0.74 else BLUE
            row += bytes(c)
        rows.append(bytes(row))
    raw = zlib.compress(b"".join(rows), 9)

    def chunk(kind, data):
        return struct.pack(">I", len(data)) + kind + data + struct.pack(">I", zlib.crc32(kind + data) & 0xFFFFFFFF)
    return b"\x89PNG\r\n\x1a\n" + chunk(b"IHDR", struct.pack(">IIBBBBB", n, n, 8, 2, 0, 0, 0)) + chunk(b"IDAT", raw) + chunk(b"IEND", b"")


if __name__ == "__main__":
    out = Path(__file__).resolve().parent.parent / "web" / "icons"
    out.mkdir(parents=True, exist_ok=True)
    for n in (192, 512):
        (out / f"home-{n}.png").write_bytes(png(n))
        print(out / f"home-{n}.png")
