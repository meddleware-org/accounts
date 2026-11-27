// theme-switch.js: drives the System / Light / Dark switch in the page footer (native radio buttons; no ARIA is needed). It only calls window.mwColorMode (theme-init.js), which does the storing.
// An external module, deferred, so the switch works with no inline script.

/** The radio buttons of the switch, or none on a page without it. */
var radios = document.querySelectorAll('input[name="mw-theme"]')
if (window.mwColorMode && radios.length) {
  /** The current choice, so the matching radio starts checked. */
  var current = window.mwColorMode.get()
  radios.forEach(function (radio) {
    radio.checked = radio.value === current
    // A change applies at once, with no reload.
    radio.addEventListener('change', function () { if (radio.checked) window.mwColorMode.set(radio.value) })
  })
}
