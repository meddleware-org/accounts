// theme-check.mjs: browser half of tests/theme.sh. Drives every page of the platform's passkey-first sign-in in Chromium (a virtual security key), and on each page checks:
//   - accessibility with axe (WCAG 2.0/2.1/2.2 A and AA, and the enhanced 7:1 contrast rule the platform holds itself to), in the light and in the dark scheme;
//   - no Content-Security-Policy violation (a `securitypolicyviolation` event or a console message about one): the realm sends a strict policy, so an inline script or style would show here;
//   - nothing in localStorage or sessionStorage (until the person picks a colour scheme), and only Keycloak's own cookies.
// And the behaviour the design promises: a key signs in with no username and no click (one press at most); a wrong username and a wrong password for a real user give the SAME message (no account
// enumeration); the page says so, and the button retries, when the key prompt cannot complete; the colour switch works and stores only what it says; the theme's files carry a version query string
// (so a browser never keeps the previous release's CSS or script). It writes a screenshot of every page and scheme to $OUT/shots.
//
// Environment: KC (Keycloak's public base URL as the browser sees it), USER and PASSWORD (a user in the bootstrap state), OUT (directory for screenshots), HOST_RULES (Chromium host mapping),
// KC_API (Keycloak as this process reaches it, for the token request), APPLY (realm/apply.py, run with this process's environment to close the bootstrap path), THEME_VERSION (the version in theme.properties), PLAYWRIGHT_FROM (a package.json beside node_modules holding
// playwright-core and @axe-core/playwright). Prints one PASS/FAIL line per check and exits 1 on any failure.
import { createRequire } from 'node:module'
import fs from 'node:fs'
import { execFileSync } from 'node:child_process'

const env = process.env
const require = createRequire(env.PLAYWRIGHT_FROM)
const { chromium } = require('playwright-core')
const { AxeBuilder } = require('@axe-core/playwright')
const KC = env.KC
let failed = 0
/** check: print and count one assertion. */
const check = (name, ok, detail = '') => { if (!ok) failed++; console.log(`  ${ok ? 'PASS' : 'FAIL'}  ${name}${ok ? '' : ` (${detail})`}`) }
fs.mkdirSync(`${env.OUT}/shots`, { recursive: true })

const browser = await chromium.launch({ headless: true, args: [`--host-resolver-rules=${env.HOST_RULES}`] })
const ctx = await browser.newContext()
const page = await ctx.newPage()
const cdp = await ctx.newCDPSession(page)
await cdp.send('WebAuthn.enable')
const { authenticatorId } = await cdp.send('WebAuthn.addVirtualAuthenticator', { options: { protocol: 'ctap2', ctap2Version: 'ctap2_1', transport: 'usb', hasResidentKey: true, hasUserVerification: true, isUserVerified: true, automaticPresenceSimulation: true } })
// Every CSP violation, from the browser's own event (collected in the page) and from the console.
const consoleCsp = []
page.on('console', (m) => { if (/content security policy/i.test(m.text())) consoleCsp.push(m.text().slice(0, 200)) })
await ctx.addInitScript(() => {
  window.__csp = []
  document.addEventListener('securitypolicyviolation', (e) => window.__csp.push(`${e.violatedDirective} ${e.blockedURI || 'inline'} on ${e.documentURI.slice(0, 80)}`))
})

/**
 * inspect: run the checks on the current page under a name; `a11y` false skips axe and screenshots.
 * @param {string} name - the page's name, used in messages and file names
 * @param {boolean} a11y - whether to run axe and take screenshots in both schemes
 */
async function inspect(name, a11y = true) {
  await page.waitForLoadState('load')
  await page.waitForTimeout(400)
  const violations = await page.evaluate(() => { const v = window.__csp || []; window.__csp = []; return v })
  const seen = consoleCsp.splice(0)
  // Keycloak itself appends one inline `history.replaceState(...)` script to the response of every form post (it only hides the one-time session code from the browser history; it cannot be turned off).
  // The policy refuses it, which is harmless, so exactly that script is expected: one violation per such script. Anything else is a failure.
  const history = await page.evaluate(() => [...document.scripts].filter((x) => !x.src && /^\s*if \(typeof history\.replaceState/.test(x.text)).length)
  const unexpected = Math.max(0, violations.length - history)
  if (unexpected) console.log('  inline scripts present: ' + JSON.stringify(await page.evaluate(() => [...document.scripts].filter((x) => !x.src).map((x) => x.outerHTML.slice(0, 160)))))
  check(`${name}: no Content-Security-Policy violation (Keycloak's own history script excepted)`, unexpected === 0, JSON.stringify([...violations, ...seen]).slice(0, 300))
  const stored = await page.evaluate(() => ({ local: Object.keys(localStorage), session: Object.keys(sessionStorage) }))
  check(`${name}: nothing in localStorage or sessionStorage`, stored.local.length === 0 && stored.session.length === 0, JSON.stringify(stored))
  if (!a11y) return
  for (const scheme of ['light', 'dark']) {
    await page.emulateMedia({ colorScheme: scheme })
    await page.waitForTimeout(150)
    const result = await new AxeBuilder({ page }).withTags(['wcag2a', 'wcag2aa', 'wcag21a', 'wcag21aa', 'wcag22aa', 'best-practice']).withRules(['color-contrast-enhanced']).analyze()
    const bad = result.violations.map((v) => `${v.id} (${v.nodes.length})`)
    check(`${name} (${scheme}): axe finds nothing`, bad.length === 0, bad.join(', '))
    await page.screenshot({ path: `${env.OUT}/shots/${name}-${scheme}.png`, fullPage: true })
  }
  await page.emulateMedia({ colorScheme: 'light' })
}

// Any application's sign-in will do: the test client `enrol` (PKCE S256) sends the browser to /enrolled afterwards.
const SIGN_IN = `${KC}/realms/meddleware/protocol/openid-connect/auth?client_id=enrol&response_type=code&scope=openid&redirect_uri=${encodeURIComponent(`${KC}/enrolled`)}&state=s&code_challenge=E9Melhoa2OwvFrEMTJguCHaoeK1t8URWbuGJSstw-cM&code_challenge_method=S256`
// The one-time-password page (first enrolment, break-glass) is reached only through the client `bootstrap`, whose flow-binding override selects that flow.
const BOOT = SIGN_IN.replace('client_id=enrol', 'client_id=bootstrap')
const back = (u) => u.href.startsWith(`${KC}/enrolled`)
/** signOut: end the session (the confirmation page, then its button). */
async function signOut() {
  await page.goto(`${KC}/realms/meddleware/protocol/openid-connect/logout`)
  await page.click('#kc-logout')
  await page.waitForTimeout(600)
}

console.log('1. the first page is the key page: no username is asked, and no other way is offered')
// No key is registered yet, so the automatic prompt cannot complete: the page stays and says so.
const first = await page.goto(SIGN_IN)
const csp = (first?.headers()['content-security-policy'] ?? '')
check('the realm sends the strict Content-Security-Policy', csp.includes("default-src 'none'") && csp.includes("script-src 'self'") && csp.includes("style-src 'self'") && !csp.includes('unsafe-inline'), csp.slice(0, 160))
await page.waitForSelector('#authenticateWebAuthnButton', { timeout: 15000 }).catch(async () => { console.log('  first page says:', page.url().slice(0, 110), (await page.locator('body').innerText()).replace(/\n+/g, ' | ').slice(0, 300)) })
check('no username field on the first page (nothing to enumerate), no password field, no "try another way"', (await page.locator('#username, #password, #try-another-way').count()) === 0)
await page.waitForFunction(() => document.getElementById('kc-webauthn-status')?.textContent.includes('not used'), null, { timeout: 15000 })
// The theme's files carry ?v=<version>, and the stylesheet really applies (the fieldset's border is the theme's 0, not the browser default).
const urls = await page.evaluate(() => [...document.querySelectorAll('link[rel=stylesheet], script[src]')].map((e) => e.href || e.src).filter((u) => u.includes('/login/meddleware/')))
check(`the theme's stylesheets and scripts carry ?v=${env.THEME_VERSION}`, urls.length >= 4 && urls.every((u) => u.includes(`?v=${env.THEME_VERSION}`)), urls.join(' '))
check('the theme\'s stylesheet is applied (the colour-scheme fieldset has no border)', (await page.evaluate(() => getComputedStyle(document.getElementById('kc-theme-switch')).borderTopWidth)) === '0px')
await inspect('passkey-no-key')

console.log('2. the one-time-password page (first enrolment or break-glass), reached through the bootstrap client')
await page.goto(BOOT)
await page.waitForSelector('#password')
await inspect('login')

console.log('3. a wrong username and a wrong password give the same message')
await page.fill('#username', 'nobody-here')
await page.fill('#password', 'not-the-password')
await page.click('#kc-login')
await page.waitForSelector('#kc-message')
const unknown = (await page.locator('#kc-message').innerText()).trim()
await inspect('login-error-unknown-user')
await page.fill('#username', env.USER)
await page.fill('#password', 'not-the-password')
await page.click('#kc-login')
await page.waitForSelector('#kc-message')
const wrongPassword = (await page.locator('#kc-message').innerText()).trim()
check('an unknown user and a wrong password: the same text', unknown === wrongPassword && unknown.length > 0, `${unknown} | ${wrongPassword}`)
check('and the text names both parts and does not say the user does not exist', /username/i.test(unknown) && /password/i.test(unknown) && !/not found|exist|unknown|no such/i.test(unknown), unknown)

console.log('4. key registration')
await page.fill('#username', env.USER)
await page.fill('#password', env.PASSWORD)
await page.click('#kc-login')
await page.waitForSelector('#registerWebAuthn')
check('the key label is a real, labelled field with a default', (await page.locator('label[for="authenticatorLabel"]').count()) === 1 && (await page.inputValue('#authenticatorLabel')).length > 0)
await inspect('register')
await page.fill('#authenticatorLabel', 'theme-test-key')
await page.click('#registerWebAuthn')
await page.waitForURL(back, { timeout: 30000 })
console.log('5. cookies and the disabled account console')
const account = await page.goto(`${KC}/realms/meddleware/account/`)
check('Keycloak\'s account console is disabled', !(await page.locator('body').innerText()).includes('Loading the Account Console'), String(account?.status()))
const cookies = (await ctx.cookies()).map((c) => c.name)
check('only Keycloak\'s own cookies are set', cookies.every((n) => /^(AUTH_SESSION_ID|KC_|KEYCLOAK_)/.test(n)), cookies.join(','))
// The key is enrolled: close the bootstrap path (delete the password, clear the marker), as an operator would.
execFileSync('python3', [env.APPLY, '--finish', env.USER], { env })

console.log('6. sign-out confirmation')
await page.goto(`${KC}/realms/meddleware/protocol/openid-connect/logout`)
await page.waitForSelector('#kc-logout')
await inspect('logout-confirm')
await page.click('#kc-logout')
await page.waitForTimeout(800)
await inspect('logged-out')

console.log('7. the key alone signs in: no username, no click')
await page.goto(SIGN_IN)
await page.waitForURL(back, { timeout: 30000 })
check('the key page opened the prompt by itself and the key signed in (no username, no click, no password)', new URL(page.url()).searchParams.has('code'))
// The sign-in is phishing-resistant: the ID token says acr = phr (level 2). The code is exchanged here like an application would (PKCE verifier of the RFC 7636 example challenge).
const code = new URL(page.url()).searchParams.get('code')
const tokens = await (await fetch(`${env.KC_API}/realms/meddleware/protocol/openid-connect/token`, { method: 'POST', headers: { 'content-type': 'application/x-www-form-urlencoded' },
  body: new URLSearchParams({ grant_type: 'authorization_code', client_id: 'enrol', code, redirect_uri: `${KC}/enrolled`, code_verifier: 'dBjftJeZ4CVP-mB92K27uhbUJU1p1r_wW1gFWFOEjXk' }) })).json()
const claims = tokens.id_token ? JSON.parse(Buffer.from(tokens.id_token.split('.')[1], 'base64url').toString()) : {}
check('the ID token of a key sign-in has acr = phr', claims.acr === 'phr', JSON.stringify(claims.acr ?? tokens))
await signOut()

console.log('8. the password path is closed once the bootstrap path is finished')
await page.goto(BOOT)
await page.waitForSelector('#password')
await page.fill('#username', env.USER)
await page.fill('#password', env.PASSWORD)
await page.click('#kc-login')
await page.waitForSelector('#kc-message')
check('the old one-time password no longer works', !page.url().startsWith(`${KC}/enrolled`))

console.log('9. when the key prompt cannot complete, the page says so and the button tries again')
// A key that cannot verify the user makes the automatic prompt fail the way a cancelled one does (NotAllowedError).
await cdp.send('WebAuthn.setUserVerified', { authenticatorId, isUserVerified: false })
await page.goto(SIGN_IN)
await page.waitForFunction(() => document.getElementById('kc-webauthn-status')?.textContent.includes('not used'), null, { timeout: 15000 })
check('the page stays and says the key was not used (a live region), not an error page', page.url().includes('/protocol/openid-connect/auth') && (await page.locator('#kc-webauthn-status[role="status"]').count()) === 1)
await inspect('passkey')
await cdp.send('WebAuthn.setUserVerified', { authenticatorId, isUserVerified: true })
await page.click('#authenticateWebAuthnButton')
await page.waitForURL(back, { timeout: 30000 })
check('pressing the button tries again and signs in', new URL(page.url()).searchParams.has('code'))

console.log('10. the colour-scheme switch')
await signOut()
await cdp.send('WebAuthn.setUserVerified', { authenticatorId, isUserVerified: false })
await page.goto(SIGN_IN)
await page.waitForSelector('#kc-theme-switch')
await page.emulateMedia({ colorScheme: 'light' })
const radios = await page.locator('input[name="mw-theme"]').evaluateAll((r) => r.map((x) => `${x.value}:${x.checked}`))
check('three native radios, System checked by default', JSON.stringify(radios) === JSON.stringify(['system:true', 'light:false', 'dark:false']), JSON.stringify(radios))
check('before any choice nothing is stored', (await page.evaluate(() => Object.keys(sessionStorage).length + Object.keys(localStorage).length)) === 0)
await page.check('input[name="mw-theme"][value="dark"]')
check('choosing Dark shows the dark scheme at once, even though the system is light', (await page.getAttribute('html', 'data-theme')) === 'dark' && (await page.getAttribute('html', 'data-scheme')) === 'dark')
check('and the page really turns dark (the background colour changed)', (await page.evaluate(() => getComputedStyle(document.body).backgroundColor)) !== 'rgb(247, 243, 240)' && (await page.evaluate(() => getComputedStyle(document.body).backgroundColor)).replace(/\s/g, '') !== 'rgb(247,243,240)')
const stored = await page.evaluate(() => ({ session: Object.fromEntries(Object.entries(sessionStorage)), local: Object.keys(localStorage) }))
check('and stores only mw-color-mode=dark, for this tab (sessionStorage), nothing else', JSON.stringify(stored) === JSON.stringify({ session: { 'mw-color-mode': 'dark' }, local: [] }), JSON.stringify(stored))
await page.screenshot({ path: `${env.OUT}/shots/passkey-forced-dark.png`, fullPage: true })
const forced = await new AxeBuilder({ page }).withTags(['wcag2a', 'wcag2aa', 'wcag21a', 'wcag21aa', 'wcag22aa', 'best-practice']).withRules(['color-contrast-enhanced']).analyze()
check('axe finds nothing in the forced dark scheme either', forced.violations.length === 0, forced.violations.map((v) => v.id).join(','))
await page.goto(SIGN_IN)
await page.waitForSelector('#kc-theme-switch')
check('the choice carries to the next page of the visit', (await page.getAttribute('html', 'data-theme')) === 'dark' && (await page.locator('input[name="mw-theme"][value="dark"]').isChecked()))
await page.check('input[name="mw-theme"][value="system"]')
check('choosing System forgets it: back to the light system scheme, storage empty again', (await page.getAttribute('html', 'data-theme')) === null && (await page.evaluate(() => Object.keys(sessionStorage).length)) === 0)

console.log('11. the generic error page')
await page.goto(`${KC}/realms/meddleware/protocol/openid-connect/auth?client_id=does-not-exist&response_type=code&redirect_uri=https%3A%2F%2Fexample.test%2F`)
await page.waitForSelector('#kc-error-message')
await inspect('error')

await browser.close()
console.log(failed === 0 ? '  theme check: ALL PASSED' : `  theme check: ${failed} FAILED`)
process.exit(failed === 0 ? 0 : 1)
