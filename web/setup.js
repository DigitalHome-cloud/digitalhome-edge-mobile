// SPDX-License-Identifier: GPL-3.0-or-later
// Copyright (C) 2026 Atelier-5
// Copyright (C) 2026 DigitalHome.cloud
// The edge's test console (setup.html): reads /api/state each second, acts through /api/act. The connect steps and
// the QR code come from atl-phone's setup page.
'use strict';

var T = {
  en: { title: 'Edge setup', docs: 'Architecture', s_edge: 'The edge', s_edge_lead: 'This PC serves the phone’s page and passes what happens on to the backends.',
    adapters: 'Adapters', nodered_hint: 'Node-RED: install node-red-contrib-dhc-edge, add a “dhc edge” config node with this address and the token from .edge/token.',
    s_connect: 'Connect the phone', usb1: 'On the phone: Settings › About phone › tap “Build number” seven times.',
    usb2: 'Settings › Developer options › turn on “USB debugging”.', usb3: 'Plug the phone into this PC and allow it on the phone.',
    usb4: 'On this PC, in the edge’s folder:', usb5: 'The page opens on the phone: tap ▶.',
    usb_why: 'USB makes the page the phone’s “localhost”: a secure page, so the camera works without certificates. The cable charges the phone too.',
    wifi_warn: 'Without HTTPS the tiles work, but the camera is blocked on Wi-Fi. Use USB, or start the edge with a certificate: ./start.sh --make-cert',
    ca_h: 'Once per phone: let it trust this PC', ca_then: 'Then, every time: the page',
    ca1: 'Put the phone on the same Wi-Fi and scan this code. Chrome warns once that the connection is not private: Advanced › Proceed. The file dhc-edge-ca.crt downloads.',
    ca2: 'Settings › Security › Encryption & credentials › Install a certificate › CA certificate, and pick dhc-edge-ca.crt. Menus differ per phone: search Settings for “certificate”.',
    ca3: 'Close Chrome completely and open it again.',
    wifi1: 'Put the phone on the same Wi-Fi as this PC.', wifi2: 'Scan the code with the phone’s camera, or type the address:',
    copy: 'Copy', copied: 'Copied', open_check: 'Open the phone check', open_app: 'Back to the tiles',
    s_profile: 'The profile', s_profile_lead: 'What the phone shows. A tap here pretends to be the phone (steps get sample answers), so a flow can be tried without one.',
    show: 'Show on the phone', photo_warn: 'This profile takes photos: they go from the phone to the backends, inside the tile’s event. The edge keeps none (the last few, in memory, for this page).',
    s_events: 'Events', s_events_lead: 'What the backends get, newest first.', s_command: 'Send a command',
    s_command_lead: 'As a backend sends it (Node-RED, MQTT, ROS 2): JSON, contract dhc-edge/0.1.', send: 'Send', sent_ok: 'done',
    cmd_hint: 'docs/contract.md lists every command and its fields.',
    no_phone: 'No phone yet', phone_on: 'connected by', since: 'since', contract: 'Contract', edge: 'Edge', profile: 'Profile',
    backend: 'Backend address', token: 'Token', token_yes: 'required', token_no: 'none: this PC only', usb_url: 'USB address', wifi_url: 'Wi-Fi address',
    gone: 'The edge does not answer: is it running? (./start.sh)', no_events: 'No event yet: tap a tile on the phone, or in the profile above.',
    pretend: 'pretend tap', report: 'last phone check:', tile: 'Tile', does: 'Does', state: 'State' },
  fr: { title: 'Réglage de l’edge', docs: 'Architecture', s_edge: 'L’edge', s_edge_lead: 'Ce PC sert la page du téléphone et transmet ce qui se passe aux backends.',
    adapters: 'Adaptateurs', nodered_hint: 'Node-RED : installez node-red-contrib-dhc-edge, ajoutez un nœud de config « dhc edge » avec cette adresse et le jeton de .edge/token.',
    s_connect: 'Connecter le téléphone', usb1: 'Sur le téléphone : Paramètres › À propos › touchez « Numéro de build » sept fois.',
    usb2: 'Paramètres › Options pour les développeurs › activez « Débogage USB ».', usb3: 'Branchez le téléphone sur ce PC et autorisez-le sur le téléphone.',
    usb4: 'Sur ce PC, dans le dossier de l’edge :', usb5: 'La page s’ouvre sur le téléphone : touchez ▶.',
    usb_why: 'L’USB fait de la page le « localhost » du téléphone : une page sécurisée, la caméra marche sans certificats. Le câble charge aussi le téléphone.',
    wifi_warn: 'Sans HTTPS les tuiles marchent, mais la caméra est bloquée en Wi-Fi. Passez par USB, ou démarrez l’edge avec un certificat : ./start.sh --make-cert',
    ca_h: 'Une fois par téléphone : qu’il fasse confiance à ce PC', ca_then: 'Puis, à chaque fois : la page',
    ca1: 'Mettez le téléphone sur le même Wi-Fi et scannez ce code. Chrome avertit une fois que la connexion n’est pas privée : Paramètres avancés › Continuer. Le fichier dhc-edge-ca.crt se télécharge.',
    ca2: 'Paramètres › Sécurité › Chiffrement et identifiants › Installer un certificat › Certificat CA, et choisissez dhc-edge-ca.crt. Les menus varient : cherchez « certificat » dans les Paramètres.',
    ca3: 'Fermez complètement Chrome et rouvrez-le.',
    wifi1: 'Mettez le téléphone sur le même Wi-Fi que ce PC.', wifi2: 'Scannez le code avec la caméra du téléphone, ou tapez l’adresse :',
    copy: 'Copier', copied: 'Copié', open_check: 'Ouvrir le test du téléphone', open_app: 'Retour aux tuiles',
    s_profile: 'Le profil', s_profile_lead: 'Ce que montre le téléphone. Un toucher ici joue le téléphone (les étapes reçoivent des réponses d’exemple) : un flux s’essaie sans téléphone.',
    show: 'Montrer sur le téléphone', photo_warn: 'Ce profil prend des photos : elles vont du téléphone aux backends, dans l’événement de la tuile. L’edge n’en garde aucune (les dernières, en mémoire, pour cette page).',
    s_events: 'Événements', s_events_lead: 'Ce que reçoivent les backends, le plus récent en haut.', s_command: 'Envoyer une commande',
    s_command_lead: 'Comme l’envoie un backend (Node-RED, MQTT, ROS 2) : JSON, contrat dhc-edge/0.1.', send: 'Envoyer', sent_ok: 'fait',
    cmd_hint: 'docs/contract.md liste chaque commande et ses champs.',
    no_phone: 'Pas encore de téléphone', phone_on: 'connecté par', since: 'depuis', contract: 'Contrat', edge: 'Edge', profile: 'Profil',
    backend: 'Adresse des backends', token: 'Jeton', token_yes: 'requis', token_no: 'aucun : ce PC seulement', usb_url: 'Adresse USB', wifi_url: 'Adresse Wi-Fi',
    gone: 'L’edge ne répond pas : tourne-t-il ? (./start.sh)', no_events: 'Pas encore d’événement : touchez une tuile sur le téléphone, ou dans le profil ci-dessus.',
    pretend: 'toucher simulé', report: 'dernier test du téléphone :', tile: 'Tuile', does: 'Fait', state: 'État' },
  de: { title: 'Edge-Einrichtung', docs: 'Architektur', s_edge: 'Das Edge', s_edge_lead: 'Dieser PC liefert die Seite des Handys und gibt weiter, was passiert, an die Backends.',
    adapters: 'Adapter', nodered_hint: 'Node-RED: node-red-contrib-dhc-edge installieren, einen Konfig-Knoten „dhc edge“ mit dieser Adresse und dem Token aus .edge/token anlegen.',
    s_connect: 'Handy verbinden', usb1: 'Am Handy: Einstellungen › Telefoninfo › sieben Mal auf „Buildnummer“ tippen.',
    usb2: 'Einstellungen › Entwickleroptionen › „USB-Debugging“ einschalten.', usb3: 'Handy an diesen PC stecken und es am Handy erlauben.',
    usb4: 'Auf diesem PC, im Ordner des Edge:', usb5: 'Die Seite öffnet sich am Handy: ▶ tippen.',
    usb_why: 'USB macht die Seite zum „localhost“ des Handys: eine sichere Seite, die Kamera geht ohne Zertifikate. Das Kabel lädt das Handy auch.',
    wifi_warn: 'Ohne HTTPS gehen die Kacheln, aber die Kamera ist im WLAN gesperrt. USB nutzen, oder das Edge mit Zertifikat starten: ./start.sh --make-cert',
    ca_h: 'Einmal pro Handy: diesem PC vertrauen', ca_then: 'Dann, jedes Mal: die Seite',
    ca1: 'Handy ins selbe WLAN und diesen Code scannen. Chrome warnt einmal, die Verbindung sei nicht privat: Erweitert › Weiter. Die Datei dhc-edge-ca.crt lädt herunter.',
    ca2: 'Einstellungen › Sicherheit › Verschlüsselung & Anmeldedaten › Zertifikat installieren › CA-Zertifikat, dhc-edge-ca.crt wählen. Menüs sind je Handy anders: in den Einstellungen nach „Zertifikat“ suchen.',
    ca3: 'Chrome ganz schließen und wieder öffnen.',
    wifi1: 'Handy ins selbe WLAN wie dieser PC.', wifi2: 'Den Code mit der Kamera des Handys scannen, oder die Adresse eintippen:',
    copy: 'Kopieren', copied: 'Kopiert', open_check: 'Handy-Check öffnen', open_app: 'Zurück zu den Kacheln',
    s_profile: 'Das Profil', s_profile_lead: 'Was das Handy zeigt. Ein Tippen hier spielt das Handy (Schritte bekommen Beispielantworten): so lässt sich ein Flow ohne Handy probieren.',
    show: 'Am Handy zeigen', photo_warn: 'Dieses Profil macht Fotos: sie gehen vom Handy an die Backends, im Ereignis der Kachel. Das Edge behält keins (die letzten, im Speicher, für diese Seite).',
    s_events: 'Ereignisse', s_events_lead: 'Was die Backends bekommen, das neueste oben.', s_command: 'Befehl senden',
    s_command_lead: 'So, wie ein Backend ihn sendet (Node-RED, MQTT, ROS 2): JSON, Vertrag dhc-edge/0.1.', send: 'Senden', sent_ok: 'erledigt',
    cmd_hint: 'docs/contract.md listet jeden Befehl und seine Felder.',
    no_phone: 'Noch kein Handy', phone_on: 'verbunden über', since: 'seit', contract: 'Vertrag', edge: 'Edge', profile: 'Profil',
    backend: 'Adresse für Backends', token: 'Token', token_yes: 'nötig', token_no: 'keins: nur dieser PC', usb_url: 'USB-Adresse', wifi_url: 'WLAN-Adresse',
    gone: 'Das Edge antwortet nicht: läuft es? (./start.sh)', no_events: 'Noch kein Ereignis: eine Kachel am Handy tippen, oder im Profil oben.',
    pretend: 'gespieltes Tippen', report: 'letzter Handy-Check:', tile: 'Kachel', does: 'Macht', state: 'Zustand' }
};
var lang = 'en';
try { lang = localStorage.getItem('dhc-lang') || (navigator.language || 'en').slice(0, 2); } catch (e) {}
if (!T[lang]) lang = 'en';
function t(k) { return T[lang][k] || T.en[k] || k; }
function $(id) { return document.getElementById(id); }
function el(tag, attrs, kids) {
  var e = document.createElement(tag);
  for (var k in attrs || {}) { if (k === 'text') e.textContent = attrs[k]; else if (k.slice(0, 2) === 'on') e[k] = attrs[k]; else e.setAttribute(k, attrs[k]); }
  (kids || []).forEach(function (c) { if (c) e.appendChild(typeof c === 'string' ? document.createTextNode(c) : c); });
  return e;
}
function L(x) { return x === null || x === undefined ? '' : typeof x === 'object' ? x[lang] || x.en || x[Object.keys(x)[0]] : String(x); }
function rows(table, list) {
  table.innerHTML = '';
  list.forEach(function (r) { table.appendChild(el('tr', {}, [el('th', { text: r[0] }), r[1] instanceof Node ? el('td', {}, [r[1]]) : el('td', { text: r[1] })])); });
}

var S = null;
function act(body) {
  return fetch('/api/act', { method: 'POST', headers: { 'Content-Type': 'application/json' }, body: JSON.stringify(body) })
    .then(function (r) { return r.status === 204 ? {} : r.json().then(function (j) { if (!r.ok) throw new Error(j.error || r.status); return j; }); });
}
function poll() {
  fetch('/api/state').then(function (r) { return r.json(); }).then(function (s) { S = s; update(); })
    .catch(function () { $('meta').textContent = t('gone'); })
    .then(function () { setTimeout(poll, 1000); });
}

// ---- the edge, the phone ---------------------------------------------------------------------------------------------
function update() {
  $('meta').textContent = S.contract + ' · ' + S.edge + ' · ' + L(S.profile.title);
  $('docs').style.display = S.docs ? '' : 'none';
  rows($('edge'), [[t('contract'), S.contract], [t('edge'), S.edge], [t('profile'), S.profile.id + ' — ' + L(S.profile.title)],
                   [t('usb_url'), S.urls.usb], [t('wifi_url'), S.urls.wifi], [t('backend'), S.urls.backend]]);
  rows($('adapters'), S.adapters.map(function (a) {
    return [a.name, el('span', {}, [el('span', { class: 'dot' + (a.ok ? ' on' : ''), style: 'display:inline-block;margin-right:6px' }), a.detail +
            (a.name === 'nodered' ? ' · ' + t('token') + ': ' + t(a.token ? 'token_yes' : 'token_no') : '') +
            (a.topics ? ' · ' + a.topics.event + '/…' : '')])];
  }));
  $('wifi-url').textContent = S.urls.wifi; $('wifi-warn').style.display = S.secure_wifi ? 'none' : 'block';
  drawQr(S.urls.wifi);
  $('ca-steps').style.display = S.urls.ca ? 'block' : 'none';
  if (S.urls.ca && qrCaFor !== S.urls.ca) { qrCaFor = S.urls.ca; drawQr(S.urls.ca, $('qr-ca'), 4); }
  var ph = S.phone;
  $('phone-dot').className = 'dot' + (ph ? ' on' : '');
  $('phone-status').textContent = ph ? (ph.model + ' — ' + t('phone_on') + ' ' + ph.link.toUpperCase() + (S.since ? ', ' + t('since') + ' ' + new Date(S.since * 1000).toLocaleTimeString() : '')) : t('no_phone');
  $('phone-caps').innerHTML = '';
  if (ph) Object.keys(ph.caps).forEach(function (k) { $('phone-caps').appendChild(el('span', { class: 'chip ' + (ph.caps[k] ? 'yes' : 'no'), text: k })); });
  var r = S.reports[S.reports.length - 1];
  $('reports').textContent = r ? t('report') + ' ' + r.model + ', ' + new Date(r.at * 1000).toLocaleString() : '';
  profileView();
  logView();
}

// ---- the profile: a small copy of the phone's tiles; a tap pretends to be the phone ------------------------------------
var shownProfile = '', SAMPLE_JPEG = '';
function sampleJpeg() {  // a small picture for a pretend photo step
  if (SAMPLE_JPEG) return SAMPLE_JPEG;
  var c = document.createElement('canvas'); c.width = 160; c.height = 120;
  var g = c.getContext('2d'); g.fillStyle = '#10303a'; g.fillRect(0, 0, 160, 120); g.fillStyle = '#3fd8ff'; g.font = 'bold 18px sans-serif'; g.fillText('sample', 44, 66);
  return (SAMPLE_JPEG = c.toDataURL('image/jpeg', 0.8).split(',')[1]);
}
function sample(s) {
  if (s.action === 'choice') return s.options[0].id;
  if (s.action === 'number') return s['default'];
  if (s.action === 'text') return 'test';
  if (s.action === 'scan') return { code: 'TEST-4006381333931', format: 'ean_13' };
  if (s.action === 'photo') { var p = { jpeg: sampleJpeg(), w: 160, h: 120 }; if (s.ocr) p.text = 'TYPE XYZ 123\n230 V 50 Hz'; return p; }
  return null;
}
function pretend(tile) {
  var m = { t: 'tile', tile: tile.id };
  if (tile.action === 'toggle') m.value = !(S.states[tile.id] === true);
  else if (tile.action === 'steps') { m.data = {}; tile.steps.forEach(function (s) { m.data[s.id] = sample(s); }); }
  else if (['choice', 'number', 'text', 'scan', 'photo'].indexOf(tile.action) >= 0) { m.data = {}; m.data[tile.id] = sample(tile); }
  act({ phone: m }).catch(function (e) { $('profile-note').textContent = e.message; });
}
function actionText(x) {
  if (x.action === 'steps') return 'steps: ' + x.steps.map(function (s) { return s.id + ' (' + s.action + (s.ocr ? '+ocr' : '') + ')'; }).join(' → ');
  if (x.action === 'choice') return 'choice: ' + x.options.map(function (o) { return o.id; }).join(', ');
  return x.action + (x.ocr ? ' + ocr' : '') + (x.unit ? ' (' + x.unit + ')' : '');
}
function profileView() {
  var P = S.profile, key = JSON.stringify([P, S.states, S.labels, lang]);
  var sel = $('profile');
  if (sel.options.length !== S.profiles.length) {
    sel.innerHTML = '';
    S.profiles.forEach(function (x) { sel.appendChild(el('option', { value: x.id, text: x.id + ' — ' + L(x.title) + (x.ok ? '' : ' ⚠') })); });
  }
  if (document.activeElement !== sel) sel.value = P.id;
  var bad = S.profiles.filter(function (x) { return !x.ok; });
  $('profile-note').textContent = bad.length ? '⚠ ' + bad.map(function (x) { return x.error; }).join('; ') : '';
  if (key === shownProfile) return;
  shownProfile = key;
  var photos = P.tiles.some(function (x) { return x.action === 'photo' || (x.steps || []).some(function (s) { return s.action === 'photo'; }); });
  $('photo-warn').style.display = photos ? 'block' : 'none';
  var pv = $('preview');
  pv.innerHTML = '';
  pv.style.gridTemplateColumns = 'repeat(' + P.columns + ', 1fr)';
  P.home.forEach(function (id) {
    var x = P.tiles.filter(function (y) { return y.id === id; })[0], v = S.states[id];
    var b = el('button', { class: 'c-' + x.color + (x.action === 'toggle' && v === true ? ' on' : ''), title: t('pretend') },
               [x.icon ? el('i', { text: x.icon }) : null, el('span', { text: L(x.label) }), v !== undefined ? el('small', { text: String(v) + (x.unit ? ' ' + x.unit : '') }) : null]);
    b.onclick = function () { pretend(x); };
    pv.appendChild(b);
  });
  var tbl = $('tiles');
  tbl.innerHTML = '';
  tbl.appendChild(el('tr', {}, [el('th', { text: t('tile') }), el('th', { text: t('does') }), el('th', { text: t('state') })]));
  P.tiles.forEach(function (x) {
    tbl.appendChild(el('tr', {}, [el('td', {}, [el('code', { text: x.id })]), el('td', { text: actionText(x) }),
                                  el('td', { text: S.states[x.id] === undefined ? '' : JSON.stringify(S.states[x.id]) })]));
  });
}

// ---- the events -------------------------------------------------------------------------------------------------------
var shownLog = -1;
function logView() {
  var last = S.events.length ? S.events[S.events.length - 1].n : 0;
  if (last === shownLog) return;
  shownLog = last;
  var log = $('log');
  log.innerHTML = '';
  if (!S.events.length) return log.appendChild(el('p', { class: 'hint', text: t('no_events') }));
  S.events.slice().reverse().forEach(function (e) {
    var body = {};
    Object.keys(e).forEach(function (k) { if (['v', 'edge', 'profile', 'ts', 'n', 't'].indexOf(k) < 0) body[k] = e[k]; });
    var imgs = [];
    Object.keys(e.data || {}).forEach(function (k) {
      if (e.data[k] && typeof e.data[k] === 'object' && 'jpeg' in e.data[k]) imgs.push(el('img', { src: '/api/photo?e=' + e.n + '&p=' + encodeURIComponent(k), alt: k, title: k + ': ' + e.data[k].jpeg + ' bytes' }));
    });
    log.appendChild(el('div', { class: 'ev t-' + e.t }, [
      el('div', { class: 'h' }, [el('b', { text: e.t + (e.tile ? ' ' + e.tile : '') }), el('span', { text: '#' + e.n + ' · ' + new Date(e.ts * 1000).toLocaleTimeString() + ' · ' + e.profile })]),
      imgs.length ? el('div', {}, imgs) : null, el('pre', { text: JSON.stringify(body, null, 1) })]));
  });
}

// ---- commands -----------------------------------------------------------------------------------------------------------
function presets() {
  var P = S ? S.profile : null, first = P ? P.tiles[0].id : 'tile', st = P ? (P.tiles.filter(function (x) { return x.action === 'state' || x.action === 'toggle'; })[0] || P.tiles[0]).id : 'tile';
  return {
    say: { t: 'say', text: { en: 'Hello from the backend', fr: 'Bonjour du backend', de: 'Hallo vom Backend' }[lang], lang: lang },
    toast: { t: 'toast', text: { en: 'Saved', fr: 'Enregistré', de: 'Gespeichert' }, ms: 3000 },
    state: { t: 'state', tile: st, value: 42 },
    states: { t: 'state', states: (function () { var o = {}; o[st] = true; return o; })() },
    ask: { t: 'ask', ask: 'keep', text: { en: 'Keep this one?', fr: 'On le garde ?', de: 'Behalten?' }, options: [{ id: 'yes', label: { en: 'Yes', fr: 'Oui', de: 'Ja' } }, { id: 'no', label: { en: 'No', fr: 'Non', de: 'Nein' } }] },
    tiles: { t: 'tiles', tiles: [{ id: first, label: { en: 'Changed', fr: 'Changé', de: 'Geändert' } }] },
    profile: { t: 'profile', profile: 'switch' },
    vibrate: { t: 'vibrate', ms: 300 },
    home: { t: 'home' },
    open: { t: 'open', page: 'check.html' }
  };
}
function fillPreset() { $('cmd').value = JSON.stringify(presets()[$('preset').value], null, 2); }
$('preset').innerHTML = '';
Object.keys(presets()).forEach(function (k) { $('preset').appendChild(el('option', { value: k, text: k })); });
$('preset').onchange = fillPreset;
$('send').onclick = function () {
  var c;
  try { c = JSON.parse($('cmd').value); } catch (e) { $('sent').textContent = e.message; return; }
  act({ command: c }).then(function () { $('sent').textContent = t('sent_ok'); }, function (e) { $('sent').textContent = e.message; });
};

// ---- the page --------------------------------------------------------------------------------------------------------
var qrFor = null, qrCaFor = null;
function drawQr(text, c, s) {
  if (!c) { if (qrFor === text) return; qrFor = text; c = $('qr'); s = 5; }
  if (typeof qrcode !== 'function') return;
  var q = qrcode(0, 'M'); q.addData(text); q.make();
  var n = q.getModuleCount(); c.width = c.height = n * s;
  var g = c.getContext('2d'); g.fillStyle = '#fff'; g.fillRect(0, 0, n * s, n * s); g.fillStyle = '#000';
  for (var y = 0; y < n; y++) for (var x = 0; x < n; x++) if (q.isDark(y, x)) g.fillRect(x * s, y * s, s, s);
}
function copy(text, done) {
  (navigator.clipboard && navigator.clipboard.writeText ? navigator.clipboard.writeText(text) : Promise.reject())
    .then(done, function () { var a = el('textarea'); a.value = text; document.body.appendChild(a); a.select(); document.execCommand('copy'); a.remove(); done(); });
}
function translate() {
  document.documentElement.lang = lang;
  [].forEach.call(document.querySelectorAll('[data-t]'), function (e) { e.textContent = t(e.getAttribute('data-t')); });
  [].forEach.call(document.querySelectorAll('.lang button'), function (b) { b.className = b.getAttribute('data-l') === lang ? 'on' : ''; });
  document.title = t('title');
  shownProfile = ''; shownLog = -1;
  if (S) update();
}
[].forEach.call(document.querySelectorAll('.lang button'), function (b) {
  b.onclick = function () { lang = b.getAttribute('data-l'); try { localStorage.setItem('dhc-lang', lang); } catch (e) {} translate(); fillPreset(); };
});
[].forEach.call(document.querySelectorAll('.tabs button'), function (b) {
  b.onclick = function () {
    [].forEach.call(document.querySelectorAll('.tabs button'), function (x) { x.className = x === b ? 'on' : ''; });
    $('tab-usb').style.display = b.getAttribute('data-tab') === 'usb' ? 'block' : 'none';
    $('tab-wifi').style.display = b.getAttribute('data-tab') === 'wifi' ? 'block' : 'none';
  };
});
[].forEach.call(document.querySelectorAll('[data-copy]'), function (b) { b.onclick = function () { copy(b.getAttribute('data-copy'), function () { b.textContent = t('copied'); }); }; });
$('copy-wifi').onclick = function () { copy($('wifi-url').textContent, function () { $('copy-wifi').textContent = t('copied'); }); };
$('show').onclick = function () { act({ profile: $('profile').value }).catch(function (e) { $('profile-note').textContent = e.message; }); };
$('open-check').onclick = function () { act({ command: { t: 'open', page: 'check.html' } }).catch(function (e) { $('reports').textContent = e.message; }); };
$('open-app').onclick = function () { act({ command: { t: 'open', page: 'app.html' } }).catch(function (e) { $('reports').textContent = e.message; }); };
translate();
fillPreset();
poll();
