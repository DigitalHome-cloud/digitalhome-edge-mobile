// SPDX-License-Identifier: GPL-3.0-or-later
// Copyright (C) 2026 Atelier-5
// Copyright (C) 2026 DigitalHome.cloud
// The phone page's service worker: it only makes it installable as its own app window. It keeps nothing: every page
// still comes from the edge, so an update shows at once, and without the edge the page says it has no link.
'use strict';
self.addEventListener('install', function () { self.skipWaiting(); });
self.addEventListener('activate', function (e) { e.waitUntil(self.clients.claim()); });
self.addEventListener('fetch', function () {});  // the network, as always
