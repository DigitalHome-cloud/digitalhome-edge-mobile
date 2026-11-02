// SPDX-License-Identifier: GPL-3.0-or-later
// Copyright (C) 2026 Atelier-5
// Copyright (C) 2026 DigitalHome.cloud
// A step's screen, one per action (contract STEP_ACTIONS): ACTIONS[action](step, body, done, before) draws it in body
// and calls done(part) when the person is through; navBar() (app.js) adds Cancel and Back. A part is what the edge
// gets: text, a number, an option's id, {code, format}, or {jpeg, w, h, text}. The camera's picture stays on the phone
// except the photo the person takes for a photo step; codes and the type plate's text are read here, on the phone
// (BarcodeDetector or ZXing; Tesseract.js, as atl-phone's Omi Assist reads a letter).
'use strict';

var MAX_PHOTO_B64 = 1400 * 1024;   // protocol.MAX_PHOTO
var TESS = 'vendor/tesseract', OCR_LANG = { en: 'eng', fr: 'fra', de: 'deu' };

// ---- the back camera: one stream at a time, closed when its step ends ---------------------------------------------------
var media = { stream: null, scan: 0 };
function camOpen(width) {
  camStop();
  if (!(navigator.mediaDevices && navigator.mediaDevices.getUserMedia)) return Promise.reject({ name: 'NoCamera' });
  return navigator.mediaDevices.getUserMedia({ video: { facingMode: 'environment', width: { ideal: width || 1920 } }, audio: false })
    .then(function (s) { media.stream = s; return s; });
}
function camStop() {
  media.scan++;   // a scan loop that is running ends
  if (media.stream) { media.stream.getTracks().forEach(function (k) { k.stop(); }); media.stream = null; }
}
function videoOf(stream) {
  var v = el('video', { playsinline: '', muted: '', autoplay: '' });
  v.muted = true; v.srcObject = stream; v.play().catch(function () {});
  return v;
}
function camFailed(body, s, done, e) {
  body.appendChild(el('p', { class: 'note', text: T('nocam') + ' (' + ((e && e.name) || e) + ')' + (window.isSecureContext ? '' : ' — ' + T('insecure')) }));
  body.appendChild(navBar([el('button', { class: 'big', text: T('skip'), onclick: function () { done(null); } })]));
}
function script(src) {
  return new Promise(function (ok, no) { var s = document.createElement('script'); s.src = src; s.onload = ok; s.onerror = function () { no({ name: 'NoLibrary' }); }; document.head.appendChild(s); });
}

var ACTIONS = {};

// ---- choice: the options as tiles ------------------------------------------------------------------------------------
ACTIONS.choice = function (s, body, done, before) {
  var grid = el('div', { class: 'grid' });
  if (s.options.length > 6) grid.style.gridTemplateColumns = '1fr 1fr 1fr';
  s.options.forEach(function (o) {
    var b = el('button', { class: 'tile' + (o.id === before ? ' on' : '') }, [o.icon ? el('i', { text: o.icon }) : null, el('span', { text: L(o.label) })]);
    b.onclick = function () { flash(b); if (flow && flow.tile.speak) speak(L(o.label), lang); setTimeout(function () { done(o.id); }, 200); };
    grid.appendChild(b);
  });
  body.appendChild(grid);
  body.appendChild(navBar());
};

// ---- number: big, with - and + ---------------------------------------------------------------------------------------
ACTIONS.number = function (s, body, done, before) {
  var v = typeof before === 'number' ? before : s['default'];
  var shown = el('b', { text: '' });
  function show() { shown.textContent = (Math.round(v * 1000) / 1000) + (s.unit ? ' ' + s.unit : ''); }
  function by(d) { v = Math.max(s.min, Math.min(s.max, v + d)); show(); if (navigator.vibrate) navigator.vibrate(15); }
  body.appendChild(el('div', { class: 'num' }, [el('button', { text: '−', onclick: function () { by(-s.step); } }), shown,
                                                el('button', { text: '+', onclick: function () { by(s.step); } })]));
  show();
  body.appendChild(navBar([el('button', { class: 'big go', text: T('next'), onclick: function () { done(v); } })]));
};

// ---- text: a note, typed (or dictated with the keyboard's microphone) ---------------------------------------------------
ACTIONS.text = function (s, body, done, before) {
  var a = el('textarea', { maxlength: String(s.max || 200), rows: '3' });
  a.value = typeof before === 'string' ? before : '';
  body.appendChild(a);
  body.appendChild(navBar([el('button', { class: 'big go', text: T('next'), onclick: function () { done(a.value.trim()); } })]));
  setTimeout(function () { a.focus(); }, 100);
};

// ---- scan: a barcode or QR code, read on the phone -------------------------------------------------------------------
function codeReader(formats) {  // a function(video) -> Promise of {code, format} or null
  if ('BarcodeDetector' in window) {
    return BarcodeDetector.getSupportedFormats().then(function (have) {
      var use = formats && formats.length ? formats.filter(function (f) { return have.indexOf(f) >= 0; }) : have;
      if (!use.length) throw { name: 'NoFormat' };
      var d = new BarcodeDetector({ formats: use });
      return function (v) { return d.detect(v).then(function (r) { return r.length ? { code: String(r[0].rawValue), format: r[0].format } : null; }); };
    }).catch(function () { return zxingReader(formats); });   // Play services missing: BarcodeDetector knows no format
  }
  return zxingReader(formats);
}
function zxingReader(formats) {
  return (window.ZXing ? Promise.resolve() : script('vendor/zxing/zxing.min.js')).then(function () {
    var reader = new ZXing.MultiFormatReader(), c = document.createElement('canvas');
    if (formats && formats.length) {
      var hints = new Map();
      hints.set(ZXing.DecodeHintType.POSSIBLE_FORMATS, formats.map(function (f) { return ZXing.BarcodeFormat[f.toUpperCase()]; })
        .filter(function (f) { return f !== undefined; }));
      reader.setHints(hints);
    }
    return function (v) {
      var w = Math.min(v.videoWidth, 960), h = Math.round(v.videoHeight * w / (v.videoWidth || 1));
      if (!w || !h) return Promise.resolve(null);
      c.width = w; c.height = h; c.getContext('2d').drawImage(v, 0, 0, w, h);
      try {
        var r = reader.decode(new ZXing.BinaryBitmap(new ZXing.HybridBinarizer(new ZXing.HTMLCanvasElementLuminanceSource(c))));
        return Promise.resolve({ code: r.getText(), format: String(ZXing.BarcodeFormat[r.getBarcodeFormat()]).toLowerCase() });
      } catch (e) { return Promise.resolve(null); }   // NotFoundException: no code in this picture
    };
  });
}
ACTIONS.scan = function (s, body, done) {
  var box = el('div', { class: 'scanbox' }), note = el('p', { class: 'note', text: T('scanning') });
  body.appendChild(box); body.appendChild(note);
  var extra = s.manual ? [el('button', { class: 'big', text: '⌨ ' + T('typeit'), onclick: typed })] : [];
  body.appendChild(navBar(extra));
  function typed() {
    camStop();
    body.innerHTML = '';
    var i = el('input', { class: 'code', type: 'text', inputmode: 'text', autocomplete: 'off' });
    body.appendChild(i);
    body.appendChild(navBar([el('button', { class: 'big go', text: T('ok'), onclick: function () {
      if (i.value.trim()) done({ code: i.value.trim(), format: 'typed' });
    } })]));
    setTimeout(function () { i.focus(); }, 100);
  }
  var run = media.scan + 1;
  Promise.all([camOpen(1280), codeReader(s.formats)]).then(function (r) {
    if (run !== media.scan) return;
    var v = videoOf(r[0]), read = r[1];
    box.appendChild(v);
    (function look() {
      if (run !== media.scan) return;
      (v.readyState >= 2 ? read(v) : Promise.resolve(null)).then(function (c) {
        if (run !== media.scan) return;
        if (c && c.code) { if (navigator.vibrate) navigator.vibrate(80); camStop(); return done(c); }
        setTimeout(look, 200);
      }).catch(function () { setTimeout(look, 500); });
    })();
  }).catch(function (e) { if (run === media.scan) { box.remove(); note.textContent = T('nocam') + ' (' + ((e && e.name) || e) + ')'; } });
};

// ---- photo: the person takes it, sees it, keeps it; with ocr, the text on it is read here --------------------------------
function jpegOf(v, maxPx) {
  var w = v.videoWidth, h = v.videoHeight, k = Math.min(1, maxPx / Math.max(w, h));
  var c = document.createElement('canvas');
  c.width = Math.round(w * k); c.height = Math.round(h * k);
  c.getContext('2d').drawImage(v, 0, 0, c.width, c.height);
  var q = 0.85, b64;
  do { b64 = c.toDataURL('image/jpeg', q).split(',')[1]; q -= 0.15; } while (b64.length > MAX_PHOTO_B64 && q > 0.2);
  return { canvas: c, part: { jpeg: b64, w: c.width, h: c.height } };
}
var tess = {};
function tesseract(code) {
  if (!tess[code]) {
    var base = new URL(TESS + '/', location.href).href;
    tess[code] = (window.Tesseract ? Promise.resolve() : script(TESS + '/tesseract.min.js')).then(function () {
      return Tesseract.createWorker(code, 1, { workerPath: base + 'worker.min.js', corePath: base, langPath: base + 'lang',
                                               workerBlobURL: false, gzip: true, cacheMethod: 'none' });
    });
    tess[code].catch(function () { delete tess[code]; });
  }
  return tess[code];
}
function ocr(canvas) {  // the lines Tesseract is sure enough of (as Omi's reader)
  var code = lang === 'en' ? 'eng' : OCR_LANG[lang] + '+eng';
  return tesseract(code).then(function (w) { return w.recognize(canvas); }).then(function (res) {
    return ((res.data || {}).lines || []).filter(function (x) { return x.confidence >= 40 && /[A-Za-zÀ-ÿ0-9]{2}/.test(x.text); })
      .map(function (x) { return x.text.trim(); }).join('\n');
  });
}
ACTIONS.photo = function (s, body, done) {
  var run = media.scan + 1;
  camOpen(1920).then(function (stream) {
    if (run !== media.scan) return;
    var v = videoOf(stream);
    body.appendChild(v);
    body.appendChild(navBar([el('button', { class: 'big go', text: '📸 ' + T('shoot'), onclick: shoot })]));
    function shoot() {
      if (!v.videoWidth) return;
      var got = jpegOf(v, s.max_px);
      camStop();
      body.innerHTML = '';
      body.appendChild(el('img', { class: 'shot', src: 'data:image/jpeg;base64,' + got.part.jpeg }));
      var again = el('button', { class: 'big', text: '↺ ' + T('retake'), onclick: function () { body.innerHTML = ''; ACTIONS.photo(s, body, done); } });
      if (!s.ocr) return body.appendChild(navBar([again, el('button', { class: 'big go', text: '✓ ' + T('use'), onclick: function () { done(got.part); } })]));
      var note = el('p', { class: 'note', text: T('reading') }), text = el('textarea', { rows: '3', maxlength: '2000' }), use;
      body.appendChild(note);
      body.appendChild(navBar([again, use = el('button', { class: 'big go', text: '✓ ' + T('use'), disabled: '', onclick: function () {
        got.part.text = text.value.trim(); done(got.part);
      } })]));
      if (flow && flow.tile.speak) speak(T('reading'), lang);
      ocr(got.canvas).then(function (t) {
        text.value = t; note.textContent = t ? T('textok') : T('notext');
        body.insertBefore(text, body.lastChild); use.removeAttribute('disabled');
      }).catch(function (e) {
        note.textContent = T('notext') + ' (' + ((e && e.name) || e) + ')'; body.insertBefore(text, body.lastChild); use.removeAttribute('disabled');
      });
    }
  }).catch(function (e) { if (run === media.scan) camFailed(body, s, done, e); });
};
