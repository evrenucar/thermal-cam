/* Print geometry shared by the emulator and its hardware-free contracts. */
(function (root, factory) {
  "use strict";
  var api = factory();
  if (typeof module === "object" && module.exports) module.exports = api;
  root.lengthwisePrintLayout = api.lengthwisePrintLayout;
})(typeof globalThis !== "undefined" ? globalThis : this, function () {
  "use strict";

  function lengthwisePrintLayout(imageWidth, imageHeight, printerWidth) {
    if (!(imageWidth > 0 && imageHeight > 0 && printerWidth > 0)) {
      throw new RangeError("image and printer dimensions must be positive");
    }
    // Rotate the landscape frame so its short edge spans the print head. The
    // long edge then travels along the paper feed and uses the largest possible
    // scale without cropping the captured composition.
    return {
      width: printerWidth,
      height: Math.round(printerWidth * imageWidth / imageHeight),
      rotation: 90
    };
  }

  return { lengthwisePrintLayout: lengthwisePrintLayout };
});
