// Keyboard shortcuts for the animation page.
//
// Space plays/pauses, the arrow keys step one frame back and forward. The
// shortcuts route into the SAME server handlers the buttons use, so there is
// one implementation of each action and one place where playback state can
// drift.
//
// WHY ONE `kbd_shortcut` TRIGGER AND NOT THE BUTTON NAMES
// ------------------------------------------------------
// The buttons are `@ctrl.set("play_toggle")` etc. - controller METHODS, not
// triggers. trame_server's protocol resolves a client trigger with
// `controller.trigger_fn(name)`, which only knows the functions registered by
// `@ctrl.trigger(name)` (plus the auto `trigger__N` names trame mints for a
// ControllerFunction it hands to a widget). Calling
// trigger('play_toggle', ...) therefore reaches `fn = None`, and the protocol
// does not raise - it logs "Trigger %s seems to be missing" and returns None.
// A shortcut aimed at those names is a silent no-op. The single stable name the
// page does register is `kbd_shortcut`, and it takes the pressed key as its
// only argument.
//
// WHY trigger() AND NOT state.set()
// --------------------------------
// The shortcuts MUST NOT go through the reactive state. trame's state.set
// compares the new value with the cached one and drops the write when they are
// equal (the client-side guard is roughly `if (this.state[name] !== value)`).
// A shortcut that fired a boolean toggle through state would therefore break
// on the SECOND identical press: Space sets "pressed = true", the server flips
// playback on, the user presses Space again, the client computes "pressed =
// true" again, the guard sees no change, the RPC is never sent, and the page
// keeps playing. window.trame.trigger() is an unconditional RPC - it always
// reaches the server, so every press is a real press.
//
// GUARD ORDER MATTERS
// -------------------
// The target check comes BEFORE preventDefault(). The SETUP column has live
// text fields; Space is a space character there, not a play command. A handler
// that called preventDefault() first and looked at the target afterwards would
// swallow the space bar in every input on the page - silently, since a
// prevented keydown looks exactly like a keystroke that did nothing.
//
// NOT COVERED BY THE TEST SUITE
// -----------------------------
// No test dispatches a real keydown event: the suite has no browser. The tests
// prove the server side of the contract (the RPC name exists, each key reaches
// the same handler as its button, the script is registered with the client).
// This file itself is only exercised by a human pressing a key.

(function () {
  'use strict';

  // The keys the page answers to, and the one trigger that dispatches them.
  // The KEY ITSELF is the argument: the server maps it to the button handler.
  var SHORTCUT_TRIGGER = 'kbd_shortcut';
  var KEYS = { ' ': true, ArrowLeft: true, ArrowRight: true };

  function onKeyDown(event) {
    // Modified keys belong to the browser and to the OS, not to us.
    if (event.ctrlKey || event.metaKey || event.altKey) {
      return;
    }

    // A focused editor owns its keys. Checked before preventDefault so that
    // typing a space in the SETUP column still types a space.
    var target = event.target;
    if (target) {
      var tag = (target.tagName || '').toUpperCase();
      if (tag === 'INPUT' || tag === 'TEXTAREA' || tag === 'SELECT' ||
          target.isContentEditable) {
        return;
      }
    }

    if (!Object.prototype.hasOwnProperty.call(KEYS, event.key)) {
      return;
    }

    // Before the page is wired up there is nothing to trigger; do not eat the
    // key in that window.
    if (!window.trame || !window.trame.trigger) {
      return;
    }

    // Only now, once the key is definitely ours, stop the browser's default
    // (Space scrolls the page, the arrows scroll it too).
    event.preventDefault();
    window.trame.trigger(SHORTCUT_TRIGGER, [event.key], {});
  }

  // Capture phase: the shortcuts keep working when a canvas has focus, and no
  // widget can stop propagation before we see the key.
  window.addEventListener('keydown', onKeyDown, true);
})();
