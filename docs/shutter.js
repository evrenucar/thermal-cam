/* Distinguish a quick shutter tap from a deliberate hold.
 * Shared as a small module so the timing contract can be tested without a DOM.
 */
(function (root, factory) {
  "use strict";
  var api = factory();
  if (typeof module === "object" && module.exports) module.exports = api;
  root.createShutterGesture = api.createShutterGesture;
})(typeof globalThis !== "undefined" ? globalThis : this, function () {
  "use strict";

  function createShutterGesture(options) {
    options = options || {};
    var holdMs = options.holdMs == null ? 650 : options.holdMs;
    var onTap = options.onTap || function () {};
    var onHold = options.onHold || function () {};
    var schedule = options.setTimeout || setTimeout;
    var cancelTimer = options.clearTimeout || clearTimeout;
    var timer = null;
    var pressed = false;
    var held = false;

    function press() {
      if (pressed) return;
      pressed = true;
      held = false;
      timer = schedule(function () {
        timer = null;
        if (!pressed) return;
        held = true;
        onHold();
      }, holdMs);
    }

    function release() {
      if (!pressed) return;
      pressed = false;
      if (timer !== null) {
        cancelTimer(timer);
        timer = null;
      }
      if (!held) onTap();
      held = false;
    }

    function cancel() {
      pressed = false;
      held = false;
      if (timer !== null) {
        cancelTimer(timer);
        timer = null;
      }
    }

    return { press: press, release: release, cancel: cancel };
  }

  return { createShutterGesture: createShutterGesture };
});
