# Third-party code

- `qrcode.js`: QR Code Generator for JavaScript 1.4.4, Copyright (c) 2009 Kazuhiko Arase, MIT license
  (notice in the file's header). From the npm package `qrcode-generator`, unchanged. The setup page draws the phone's
  address with it. "QR Code" is a registered trademark of DENSO WAVE INCORPORATED.

- `zxing/zxing.min.js`: ZXing for JavaScript 0.21.3, Copyright the ZXing authors, Apache License 2.0
  (`zxing/LICENSE`): `umd/index.min.js` of the npm package `@zxing/library`, unchanged
  (sha256 d7cc8f69dd70bdcf3ac00c9ae572bf2acb9f4132ba379c72df842e4db918652d). The scan steps' code reader when the
  phone's Chrome has no BarcodeDetector (no Google Play services, or a desktop browser).

- `tesseract/`: Tesseract.js 5.1.1, Copyright (c) 2016 Kevin Kwok and the Tesseract.js contributors, Apache License 2.0
  (`tesseract/LICENSE`): `tesseract.min.js` and `worker.min.js` from the npm package `tesseract.js` (`dist/`), unchanged;
  its core `tesseract-core-simd-lstm.wasm.js` and `tesseract-core-lstm.wasm.js` (Tesseract OCR compiled to WebAssembly,
  Apache License 2.0, `tesseract/LICENSE-core`) from the npm package `tesseract.js-core` 5.1.1, unchanged. Reads the type
  plate on the phone (photo steps with "ocr"). Copied from atl-phone, where Omi Assist reads letters with it.
- `tesseract/lang/`: the German, English and French models `deu`, `eng`, `fra` (`4.0.0_best_int`) from the npm packages
  `@tesseract.js-data/<lang>` 1.0.0, unchanged; they are Tesseract's own trained data (github.com/tesseract-ocr/tessdata_best,
  Apache License 2.0).
