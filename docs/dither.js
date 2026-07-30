/* Floyd–Steinberg dithering shared by the hosted emulator and parity tests.
 * Input: array-like grayscale values (0..255). Output: Uint8Array where
 * 1 is white and 0 is black, matching Pillow mode "1" pixel semantics.
 */
(function (root, factory) {
  "use strict";
  var api = factory();
  if (typeof module === "object" && module.exports) module.exports = api;
  root.dither = api.dither;
})(typeof globalThis !== "undefined" ? globalThis : this, function () {
  "use strict";

  function dither(gray, width, height) {
    if (gray.length !== width * height) {
      throw new RangeError("grayscale buffer length does not match width × height");
    }
    var buf = Float32Array.from(gray);
    var out = new Uint8Array(width * height);

    for (var y = 0; y < height; y += 1) {
      for (var x = 0; x < width; x += 1) {
        var i = y * width + x;
        var oldValue = buf[i];
        var newValue = oldValue < 128 ? 0 : 255;
        out[i] = newValue ? 1 : 0;
        var error = oldValue - newValue;

        if (x + 1 < width) buf[i + 1] += error * 7 / 16;
        if (y + 1 < height) {
          if (x > 0) buf[i + width - 1] += error * 3 / 16;
          buf[i + width] += error * 5 / 16;
          if (x + 1 < width) buf[i + width + 1] += error / 16;
        }
      }
    }
    return out;
  }

  return { dither: dither };
});
