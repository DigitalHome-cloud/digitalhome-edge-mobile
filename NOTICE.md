# Notice

digitalhome-edge-mobile, Copyright (C) 2026 DigitalHome.cloud, is free software under the GNU General Public License,
version 3 or (at your option) any later version (LICENSE). It comes with no warranty.

## Derived from atl-phone

Parts of it come from **atl-phone**, Copyright (C) 2026 Atelier-5, also GPL-3.0-or-later: an old phone as a robot's face,
eyes and ears over ROS 2. Those files keep Atelier-5's copyright line beside DigitalHome.cloud's:

| here | from atl-phone | changed |
|---|---|---|
| `dhc_edge/wsserver.py` | `atl_phone/wsserver.py` | the mirror became a two-way backend link with a token; the guest port and the show route dropped; fragmented frames joined |
| `dhc_edge/protocol.py` | `atl_phone/protocol.py` | its checking style; a new message set |
| `dhc_edge/mock_phone.py`, `dhc_edge/registry.py` | the same files | the messages; the paths |
| `web/app.js` | `web/face.js` | the link, the voice and the start; the tiles of Omi Assist; no face |
| `web/app.html`, `web/actions.js` | `web/face.html`, `web/omi.js` | the tiles' style; the text reader |
| `web/setup.html`, `web/setup.js` | the same files | the Connect step and the QR codes; the rest is new |
| `web/check.html` | the same file | the vision checks dropped; OCR and ZXing added |
| `web/sw.js`, `scripts/make_cert.sh`, `scripts/usb.sh`, `scripts/browser_check.py` | the same files | names, ports, pages |
| `start.sh` | `start.sh` | the options |

## Third-party code

`web/vendor/README.md` lists the libraries the phone's page loads (Tesseract.js, ZXing, the QR code generator), their
versions and licences; their licence files are beside them. The Node-RED package depends on `ws` (MIT), installed by npm.
