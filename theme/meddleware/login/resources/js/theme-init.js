// theme-init.js: sets the light or dark scheme before the first paint (this script is blocking and external: the realm's Content-Security-Policy refuses inline script).
// The scheme is the person's choice for this visit if they made one with the switch in the page footer, otherwise the system setting (prefers-color-scheme), as on the platform's other sites.
// A choice is kept in sessionStorage (this tab only, gone when it closes, never sent anywhere) and ONLY after the person picks Light or Dark: picking System removes it, and a person who never touches
// the switch has nothing stored. It exists so the choice survives the several pages of one sign-in. theme-switch.js drives the switch and uses window.mwColorMode.
(function () {
  /** The storage key (the same name the platform's other sites use for this preference). */
  var KEY = 'mw-color-mode'
  /** The media query that says the system prefers a dark scheme. */
  var query = window.matchMedia('(prefers-color-scheme: dark)')

  /** The saved choice ('light' or 'dark'), or '' for "follow the system". Storage can be blocked: that means "follow the system". */
  function saved() {
    try {
      var value = window.sessionStorage.getItem(KEY)
      return value === 'light' || value === 'dark' ? value : ''
    } catch (e) { return '' }
  }

  /** Show the scheme: data-theme="dark" is what the design tokens key their dark values on; data-scheme tells the browser's own controls which scheme to draw. */
  function apply() {
    var choice = saved()
    var dark = choice ? choice === 'dark' : query.matches
    if (dark) document.documentElement.setAttribute('data-theme', 'dark')
    else document.documentElement.removeAttribute('data-theme')
    document.documentElement.setAttribute('data-scheme', dark ? 'dark' : 'light')
  }

  /** Remember a choice ('light' or 'dark') for this tab, or forget it ('system'), then show it. */
  function set(mode) {
    try {
      if (mode === 'light' || mode === 'dark') window.sessionStorage.setItem(KEY, mode)
      else window.sessionStorage.removeItem(KEY)
    } catch (e) { /* storage blocked: the choice lasts only for this page */ }
    apply()
  }

  apply()
  // While no choice is saved the page follows a change of the system setting.
  query.addEventListener('change', function () { if (!saved()) apply() })
  window.mwColorMode = { get: function () { return saved() || 'system' }, set: set }
})()
