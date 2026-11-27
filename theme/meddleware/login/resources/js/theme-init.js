// theme-init.js: follows the system light/dark setting (prefers-color-scheme) by setting data-theme on <html>, before the first paint, as the platform's other sites do, but without writing anything to the browser's storage.
// An external script (no inline script on these pages: the realm's Content-Security-Policy refuses it).
(function () {
  // The media query that says the system prefers a dark scheme.
  var query = window.matchMedia('(prefers-color-scheme: dark)')
  /** Set or clear the attribute the design tokens key their dark values on. */
  function apply(dark) {
    if (dark) document.documentElement.setAttribute('data-theme', 'dark')
    else document.documentElement.removeAttribute('data-theme')
  }
  apply(query.matches)
  // Follow a change of the system setting while the page is open.
  query.addEventListener('change', function (event) { apply(event.matches) })
})()
