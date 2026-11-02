// SPDX-License-Identifier: GPL-3.0-or-later
// Copyright (C) 2026 Atelier-5
// Copyright (C) 2026 DigitalHome.cloud
// The phone (contract dhc-edge/0.1): the link to the edge, the profile's tiles, and a tile's steps (their screens are
// in actions.js). Plain ES2017, no libraries: old phones run it too. The link, the voice and the start come from
// atl-phone's face.js; the tiles are Omi Assist's. The phone is a peripheral: it shows what the profile and the backend
// say, and sends what the person did; it decides nothing and keeps nothing.
'use strict';

var Q = {};
location.search.slice(1).split('&').forEach(function (kv) { if (kv) { var p = kv.split('='); Q[decodeURIComponent(p[0])] = decodeURIComponent(p[1] || ''); } });
var LANGS = ['en', 'fr', 'de'];
var PHONE_LANG = (navigator.language || 'en').slice(0, 2);
if (LANGS.indexOf(PHONE_LANG) < 0) PHONE_LANG = 'en';
var lang = LANGS.indexOf(Q.lang) >= 0 ? Q.lang : PHONE_LANG;
var profile = null, states = {}, labels = {}, pending = {};
function $(id) { return document.getElementById(id); }
function T(k) { return (TEXTS[lang] || TEXTS.en)[k] || TEXTS.en[k] || k; }
function L(x) {  // a label: text, or {en, fr, de}
  if (x === null || x === undefined) return '';
  if (typeof x !== 'object') return String(x);
  return x[lang] || x.en || x[Object.keys(x)[0]] || '';
}
function el(tag, attrs, kids) {
  var e = document.createElement(tag);
  for (var k in attrs || {}) { if (k === 'text') e.textContent = attrs[k]; else if (k.slice(0, 2) === 'on') e[k] = attrs[k]; else e.setAttribute(k, attrs[k]); }
  (kids || []).forEach(function (c) { if (c) e.appendChild(typeof c === 'string' ? document.createTextNode(c) : c); });
  return e;
}
function setLang(l) {
  var n = LANGS.indexOf(Q.lang) >= 0 ? Q.lang : LANGS.indexOf(l) >= 0 ? l : PHONE_LANG;
  lang = n; document.documentElement.lang = lang;   // the tiles' words break where this language hyphenates
}

// ---- the tiles ----------------------------------------------------------------------------------------------------
function isOn(v) { return v === true || v === 1 || v === 'on' || v === 'true'; }
function tileById(id) { return profile && profile.tiles.filter(function (t) { return t.id === id; })[0]; }
function stateText(t) {  // what a tile shows under its word: its state, as the backend set it
  var v = states[t.id];
  if (pending[t.id]) return T('waiting');
  if (v === undefined || v === null) return '';
  if (t.action === 'toggle') return isOn(v) ? T('on') : T('off');
  if (t.action === 'choice') { var o = t.options.filter(function (x) { return x.id === v; })[0]; return o ? (o.icon ? o.icon + ' ' : '') + L(o.label) : String(v); }
  if (typeof v === 'number') return (Math.round(v * 10) / 10) + (t.unit ? ' ' + t.unit : '');
  return String(v) + (t.unit ? ' ' + t.unit : '');
}
function renderHome() {
  var home = $('home');
  home.innerHTML = '';
  if (!profile) return;
  $('title').textContent = L(profile.title);
  document.title = L(profile.title);
  home.style.gridTemplateColumns = 'repeat(' + profile.columns + ', 1fr)';
  profile.home.forEach(function (id) {
    var t = tileById(id);
    if (!t) return;
    var s = stateText(t), sub = labels[t.id] ? L(labels[t.id]) : '';
    var b = el('button', { class: 'tile c-' + t.color + (t.action === 'toggle' && isOn(states[t.id]) ? ' on' : '') + (pending[t.id] ? ' wait' : ''),
                           'data-tile': t.id }, [
      t.icon ? el('i', { text: t.icon }) : null, el('span', { text: L(t.label) }),
      s || sub ? el('small', {}, [s ? el('b', { text: s }) : null, s && sub ? ' · ' : '', sub]) : null]);
    b.onclick = function () { tap(t, b); };
    home.appendChild(b);
  });
}
function flash(b) { b.classList.add('flash'); setTimeout(function () { b.classList.remove('flash'); }, 250); }
function tap(t, b) {
  flash(b);
  var simple = ['send', 'toggle', 'state', 'say'].indexOf(t.action) >= 0;
  if (t.speak && profile.style === 'tiles' && simple && t.action !== 'say') speak(L(t.label), lang);
  if (navigator.vibrate) navigator.vibrate(30);
  if (t.action === 'send' || t.action === 'state') send({ t: 'tile', tile: t.id });
  else if (t.action === 'say') { speak(L(t.text), lang); send({ t: 'tile', tile: t.id }); }
  else if (t.action === 'toggle') {  // the backend decides: the tile waits for its state
    send({ t: 'tile', tile: t.id, value: !isOn(states[t.id]) });
    pending[t.id] = setTimeout(function () { delete pending[t.id]; renderHome(); }, 4000);
    renderHome();
  } else startFlow(t);
}

// ---- a tile's steps: one screen each (actions.js), then one message --------------------------------------------------
var flow = null;
function startFlow(t) {
  var steps = t.action === 'steps' ? t.steps : [Object.assign({}, t, { id: t.id })];
  flow = { tile: t, steps: steps, i: 0, data: {}, confirm: t.action === 'steps' && t.confirm };
  $('home').style.display = 'none'; $('flow').style.display = 'flex';
  showStep();
}
function closeFlow() {
  if (typeof camStop === 'function') camStop();
  flow = null;
  $('flow').style.display = 'none'; $('home').style.display = 'grid';
  renderHome();
}
function navBar(extra) {  // Cancel, Back (from the second step on), and what the step adds
  var bar = el('div', { class: 'bar' }, [el('button', { class: 'big no', text: '✕', title: T('cancel'), 'aria-label': T('cancel'), onclick: closeFlow })]);
  if (flow.i > 0) bar.appendChild(el('button', { class: 'big no', text: '←', title: T('back'), 'aria-label': T('back'),
                                                 onclick: function () { flow.i = Math.min(flow.i, flow.steps.length) - 1; showStep(); } }));
  (extra || []).forEach(function (x) { bar.appendChild(x); });
  return bar;
}
function showStep() {
  if (typeof camStop === 'function') camStop();
  if (flow.i >= flow.steps.length) return flow.confirm ? review() : finish();
  var s = flow.steps[flow.i], n = flow.steps.length, body = $('body');
  $('crumb').textContent = (flow.tile.icon ? flow.tile.icon + ' ' : '') + L(flow.tile.label);
  $('count').textContent = n > 1 ? T('step') + ' ' + (flow.i + 1) + ' ' + T('of') + ' ' + n : '';
  $('ask').textContent = L(s.prompt || s.label);
  if (flow.tile.speak) speak(L(s.prompt || s.label), lang);
  body.innerHTML = '';
  var run = ACTIONS[s.action];
  if (!run) return next(null);
  run(s, body, next, flow.data[s.id]);
  function next(v) { if (!flow) return; flow.data[s.id] = v; flow.i++; showStep(); }
}
function partText(v) {
  if (v === null || v === undefined || v === '') return T('empty');
  if (typeof v === 'object' && v.code) return v.code;
  if (typeof v === 'object' && v.jpeg) return v.text ? v.text.replace(/\s+/g, ' ').slice(0, 80) : T('photo');
  return String(v);
}
function review() {
  var body = $('body'), list = el('div', { class: 'review' });
  $('count').textContent = ''; $('ask').textContent = T('review');
  if (flow.tile.speak) speak(T('review'), lang);
  flow.steps.forEach(function (s) {
    var v = flow.data[s.id], shown = v;
    if (s.action === 'choice') { var o = s.options.filter(function (x) { return x.id === v; })[0]; if (o) shown = (o.icon ? o.icon + ' ' : '') + L(o.label); }
    if (s.action === 'number' && typeof v === 'number' && s.unit) shown = v + ' ' + s.unit;
    list.appendChild(el('div', {}, [el('b', { text: L(s.label) }), v && v.jpeg ? el('img', { src: 'data:image/jpeg;base64,' + v.jpeg }) : null,
                                    el('span', { text: partText(shown) })]));
  });
  body.innerHTML = '';
  body.appendChild(list);
  body.appendChild(navBar([el('button', { class: 'big go', text: '✓ ' + T('send'), onclick: finish })]));  // Back: the last step
}
function finish() {
  var data = {};
  Object.keys(flow.data).forEach(function (k) { if (flow.data[k] !== undefined) data[k] = flow.data[k]; });
  send({ t: 'tile', tile: flow.tile.id, data: data });
  if (navigator.vibrate) navigator.vibrate(60);
  closeFlow();
  toast('✓ ' + T('sent'), 1500);
}

// ---- what the edge says --------------------------------------------------------------------------------------------
var toastOff = 0;
function toast(text, ms) {
  clearTimeout(toastOff);
  $('toast').textContent = text; $('toast').style.display = text ? 'block' : 'none';
  if (text) toastOff = setTimeout(function () { $('toast').style.display = 'none'; }, ms || 4000);
}
function askCard(m) {  // a question: its answers as big buttons; the answer goes to the backend
  var c = $('card');
  c.innerHTML = '';
  c.appendChild(el('p', { text: L(m.text) }));
  var row = el('div');
  (m.options || []).forEach(function (o) {
    row.appendChild(el('button', { text: (o.icon ? o.icon + ' ' : '') + L(o.label), onclick: function () {
      send({ t: 'answer', id: m.id, value: o.id }); c.style.display = 'none'; hush();
    } }));
  });
  c.appendChild(row);
  c.style.display = 'flex';
  if (m.say) speak(L(m.text), lang);
}
function setProfile(m) {
  profile = m.profile; states = m.states || {}; labels = m.labels || {};
  setLang(m.lang || profile.lang);
  if (flow && !tileById(flow.tile.id)) closeFlow();
  renderHome();
}
function handle(m) {
  if (m.t === 'web' && /^[0-9a-f]{16}$/.test(m.id)) newPages(m.id);
  else if (m.t === 'profile' && m.profile) setProfile(m);
  else if (m.t === 'state') {
    Object.keys(m.states || {}).forEach(function (k) { states[k] = m.states[k]; clearTimeout(pending[k]); delete pending[k]; if ('label' in m) labels[k] = m.label; });
    if (!flow) renderHome();
  }
  else if (m.t === 'say') speak(String(m.text || ''), m.lang || lang);
  else if (m.t === 'toast') toast(L(m.text), m.ms);
  else if (m.t === 'vibrate' && navigator.vibrate) navigator.vibrate(Math.max(0, Math.min(2000, m.ms | 0)));
  else if (m.t === 'ask') askCard(m);
  else if (m.t === 'home') { $('card').style.display = 'none'; if (flow) closeFlow(); }
  else if (m.t === 'open' && ['app.html', 'check.html'].indexOf(m.page) >= 0) location.href = m.page + query(Q);
}

// ---- the link (atl-phone's face.js) ------------------------------------------------------------------------------
var ws = null, retry = 1000;
function send(o) { if (ws && ws.readyState === 1) ws.send(JSON.stringify(o)); else toast(T('nolink'), 3000); }
function caps() {
  return { camera: !!(navigator.mediaDevices && navigator.mediaDevices.getUserMedia), barcode: 'BarcodeDetector' in window,
           tts: 'speechSynthesis' in window, vibrate: 'vibrate' in navigator, wakelock: 'wakeLock' in navigator,
           wasm: typeof WebAssembly === 'object' };
}
function phoneId() {  // a random id kept in this browser: it ties this phone's check report to it, and says nothing about the phone
  try {
    var id = localStorage.getItem('dhc-edge-id');
    if (!/^[0-9a-f]{16}$/.test(id || '')) {
      id = Array.prototype.map.call(crypto.getRandomValues(new Uint8Array(8)), function (b) { return (b + 256).toString(16).slice(1); }).join('');
      localStorage.setItem('dhc-edge-id', id);
    }
    return id;
  } catch (e) { return ''; }
}
function hello() {  // Chrome hides the model in the user agent ("K"); client hints still tell it, on a secure page
  var h = { t: 'hello', id: phoneId(), ua: navigator.userAgent, secure: !!window.isSecureContext, caps: caps(),
            screen: [screen.width, screen.height], lang: PHONE_LANG };
  var uad = navigator.userAgentData;
  (uad && uad.getHighEntropyValues ? uad.getHighEntropyValues(['model']).catch(function () { return {}; }) : Promise.resolve({}))
    .then(function (v) { h.model = v.model || ''; ws.send(JSON.stringify(h)); });
}
function connect() {
  var url = (location.protocol === 'https:' ? 'wss://' : 'ws://') + location.host + '/ws' + (Q.key ? '?key=' + encodeURIComponent(Q.key) : '');
  ws = new WebSocket(url);
  ws.onopen = function () { retry = 1000; $('link').className = 'on'; hello(); };
  ws.onclose = function (e) {
    $('link').className = '';
    if (e.code === 4000) return;  // another phone took over: this one stays quiet
    setTimeout(connect, retry); retry = Math.min(retry * 2, 5000);
  };
  ws.onmessage = function (e) { var m; try { m = JSON.parse(e.data); } catch (x) { return; } handle(m); };
}
function query(q) { return '?' + Object.keys(q).map(function (k) { return encodeURIComponent(k) + '=' + encodeURIComponent(q[k]); }).join('&'); }
var pages = null;  // the fingerprint of the edge's pages, as first got: another one means it restarted with new pages
function newPages(id) {
  if (pages === null || pages === id) { pages = id; return; }
  location.replace(location.pathname + query(Object.assign({}, Q, { autostart: '1' })));
}

// ---- voice (atl-phone's face.js: some phones load their voices late, and name them fr_FR) ------------------------------
var LANG_TAG = { en: 'en-GB', fr: 'fr-FR', de: 'de-DE' }, voicesWait = [];
function voiceFor(l) {
  var tag = LANG_TAG[l] || 'en-GB', vs = speechSynthesis.getVoices(), norm = function (v) { return v.lang.replace('_', '-'); };
  return vs.filter(function (v) { return norm(v) === tag; })[0] || vs.filter(function (v) { return norm(v).slice(0, 2) === tag.slice(0, 2); })[0];
}
if ('speechSynthesis' in window) speechSynthesis.addEventListener('voiceschanged', function () {
  var w = voicesWait; voicesWait = []; w.forEach(function (f) { f(); });
});
function warmVoice() {  // the first words after a load can take seconds to start: wake the voice now, silently
  if (!speechSynthesis.getVoices().length) { voicesWait.push(warmVoice); return; }
  var u = new SpeechSynthesisUtterance(' ');
  u.volume = 0; u.lang = LANG_TAG[lang] || 'en-GB';
  var v = voiceFor(lang);
  if (v) u.voice = v;
  speechSynthesis.speak(u);
}
var speakRun = 0;
function hush() { speakRun++; if ('speechSynthesis' in window) speechSynthesis.cancel(); }
function speak(text, l, again) {
  if (!('speechSynthesis' in window) || !text) return;
  var run = again ? speakRun : ++speakRun;
  if (!speechSynthesis.getVoices().length && !again) {
    var go = function () { if (go) { go = null; if (run === speakRun) speak(text, l, true); } };
    voicesWait.push(go); setTimeout(go, 2000); return;
  }
  speechSynthesis.cancel();
  var u = new SpeechSynthesisUtterance(text), started = false;
  u.lang = LANG_TAG[l] || 'en-GB';
  var v = voiceFor(l);
  if (v) u.voice = v;
  u.onstart = function () { started = true; };
  speechSynthesis.speak(u);
  setTimeout(function () { if (!started && again !== 'retried' && run === speakRun) { speechSynthesis.cancel(); speak(text, l, 'retried'); } }, 3000);
}

// ---- start: full screen, screen on, the voice: they need a tap --------------------------------------------------------
function keepAwake() { if (navigator.wakeLock && document.visibilityState === 'visible') navigator.wakeLock.request('screen').catch(function () {}); }
document.addEventListener('visibilitychange', keepAwake);
function tapped() {
  var e = document.documentElement, fs = e.requestFullscreen || e.webkitRequestFullscreen;
  if (fs && !(document.fullscreenElement || document.webkitFullscreenElement)) { var p = fs.call(e); if (p && p.catch) p.catch(function () {}); }
  if ('speechSynthesis' in window) warmVoice();
}
function start() {
  $('start').style.display = 'none';
  tapped(); keepAwake();
  if (navigator.userActivation && !navigator.userActivation.isActive) document.addEventListener('pointerdown', tapped, { once: true });
  connect();
}
setLang(lang);
$('hint').textContent = T('hint');
if (!window.isSecureContext) $('note').textContent = T('insecure');
$('go').onclick = start;
if (Q.autostart === '1') start();
if ('serviceWorker' in navigator && window.isSecureContext) navigator.serviceWorker.register('sw.js').catch(function () {});  // installable
