// theme-check.mjs: browser half of tests/theme.sh. Drives every page of the platform's passkey-only sign-in in Chromium (a virtual security key), and on each page checks:
//   - accessibility with axe (WCAG 2.0/2.1/2.2 A and AA, and the enhanced 7:1 contrast rule the platform holds itself to), in the light and in the dark scheme;
//   - no Content-Security-Policy violation (a `securitypolicyviolation` event or a console message about one): the realm sends a strict policy, so an inline script or style would show here;
//   - nothing in localStorage or sessionStorage, and only Keycloak's own cookies.
// It writes a screenshot of every page and scheme to $OUT/shots. Keycloak's own account console is disabled in this realm (it cannot run under the policy); keys are enrolled through the sign-in flow.
//
// Environment: KC (Keycloak's public base URL as the browser sees it), USER and PASSWORD (a user in the bootstrap state), OUT (directory for screenshots), HOST_RULES (Chromium host mapping),
// APPLY (realm/apply.py, run with the environment of this process to close the bootstrap path after the key is enrolled), PLAYWRIGHT_FROM (a package.json beside node_modules holding playwright-core and @axe-core/playwright). Prints one PASS/FAIL line per check and exits 1 on any failure.
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
  document.addEventListener('securitypolicyviolation', (e) => window.__csp.push(`${e.violatedDirective} ${e.blockedURI || 'inline'} on ${e.documentURI.slice(0, 80)} sample: ${(e.sample || '').slice(0, 60)}`))
})

/**
 * inspect: run the checks on the current page under a name; `a11y` false skips axe (Keycloak's own account console).
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
const back = (u) => u.href.startsWith(`${KC}/enrolled`)

console.log('1. username step')
const first = await page.goto(SIGN_IN)
const csp = (first?.headers()['content-security-policy'] ?? '')
check('the realm sends the strict Content-Security-Policy', csp.includes("default-src 'none'") && csp.includes("script-src 'self'") && csp.includes("style-src 'self'") && !csp.includes('unsafe-inline'), csp.slice(0, 160))
// Show what the page says when the username field never appears (a template error shows as an error page).
await page.waitForSelector('#username', { timeout: 15000 }).catch(async () => { console.log('  page text:', (await page.locator('body').innerText()).replace(/\n+/g, ' | ').slice(0, 300), page.url().slice(0, 100)) })
await inspect('username')

console.log('2. an unknown username shows its error in place')
await page.fill('#username', 'nobody-here')
await page.click('#kc-login')
await page.waitForSelector('#input-error-username, .field-error')
await inspect('username-error')

console.log('3. the bootstrap password step')
await page.fill('#username', env.USER)
await page.click('#kc-login')
await page.waitForSelector('#password')
check('the page names who is signing in, with a way back', (await page.locator('#kc-attempted-username').innerText()) === env.USER && (await page.locator('#reset-login').count()) === 1)
await inspect('password')

console.log('4. key registration')
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

// The key is enrolled: close the bootstrap path (delete the password, clear the marker), as an operator would, so the next sign-in is passkey-only.
execFileSync('python3', [env.APPLY, '--finish', env.USER], { env })
console.log('6. sign-out confirmation')
await page.goto(`${KC}/realms/meddleware/protocol/openid-connect/logout`)
await page.waitForSelector('#kc-logout')
await inspect('logout-confirm')
await page.click('#kc-logout')
await page.waitForTimeout(800)
await inspect('logged-out')

console.log('7. ONE press signs in: the username and a single click, no second click on the key page')
await page.goto(SIGN_IN)
await page.waitForSelector('#username')
await page.fill('#username', env.USER)
await page.click('#kc-login')
// The key page opens the prompt by itself and the virtual key answers: the browser must arrive back at the application with a code, with no further click from the test.
await page.waitForURL(back, { timeout: 30000 })
check('one click: the passkey signs in with no second click (no password asked)', new URL(page.url()).searchParams.has('code'))
await page.goto(`${KC}/realms/meddleware/protocol/openid-connect/logout`)
await page.click('#kc-logout')
await page.waitForTimeout(800)

console.log('8. when the key prompt cannot complete, the page says so and the button tries again')
// A key that cannot verify the user makes the automatic prompt fail the way a cancelled one does (NotAllowedError): the page must stay, say so in its live region, and offer the button.
await cdp.send('WebAuthn.setUserVerified', { authenticatorId, isUserVerified: false })
await page.goto(SIGN_IN)
await page.waitForSelector('#username')
await page.fill('#username', env.USER)
await page.click('#kc-login')
await page.waitForSelector('#authenticateWebAuthnButton')
await page.waitForFunction(() => document.getElementById('kc-webauthn-status')?.textContent.includes('not used'), null, { timeout: 15000 })
check('the page stays and says the key was not used (a live region), not an error page', page.url().includes('login-actions') && (await page.locator('#kc-webauthn-status[role="status"]').count()) === 1)
await inspect('passkey')
await cdp.send('WebAuthn.setUserVerified', { authenticatorId, isUserVerified: true })
await page.click('#authenticateWebAuthnButton')
await page.waitForURL(back, { timeout: 30000 })
check('pressing the button tries again and signs in', new URL(page.url()).searchParams.has('code'))

console.log('9. the colour-scheme switch')
await page.goto(`${KC}/realms/meddleware/protocol/openid-connect/logout`)
await page.click('#kc-logout')
await page.goto(SIGN_IN)
await page.waitForSelector('#username')
await page.emulateMedia({ colorScheme: 'light' })
const radios = await page.locator('input[name="mw-theme"]').evaluateAll((r) => r.map((x) => `${x.value}:${x.checked}`))
check('three native radios, System checked by default', JSON.stringify(radios) === JSON.stringify(['system:true', 'light:false', 'dark:false']), JSON.stringify(radios))
check('before any choice nothing is stored', (await page.evaluate(() => Object.keys(sessionStorage).length + Object.keys(localStorage).length)) === 0)
await page.check('input[name="mw-theme"][value="dark"]')
check('choosing Dark shows the dark scheme at once, even though the system is light', (await page.getAttribute('html', 'data-theme')) === 'dark' && (await page.getAttribute('html', 'data-scheme')) === 'dark')
const stored = await page.evaluate(() => ({ session: Object.fromEntries(Object.entries(sessionStorage)), local: Object.keys(localStorage) }))
check('and stores only mw-color-mode=dark, for this tab (sessionStorage), nothing else', JSON.stringify(stored) === JSON.stringify({ session: { 'mw-color-mode': 'dark' }, local: [] }), JSON.stringify(stored))
await page.screenshot({ path: `${env.OUT}/shots/username-forced-dark.png`, fullPage: true })
const forced = await new AxeBuilder({ page }).withTags(['wcag2a', 'wcag2aa', 'wcag21a', 'wcag21aa', 'wcag22aa', 'best-practice']).withRules(['color-contrast-enhanced']).analyze()
check('axe finds nothing in the forced dark scheme either', forced.violations.length === 0, forced.violations.map((v) => v.id).join(','))
await page.goto(SIGN_IN)
await page.waitForSelector('#username')
check('the choice carries to the next page of the visit', (await page.getAttribute('html', 'data-theme')) === 'dark' && (await page.locator('input[name="mw-theme"][value="dark"]').isChecked()))
await page.check('input[name="mw-theme"][value="system"]')
check('choosing System forgets it: back to the light system scheme, storage empty again', (await page.getAttribute('html', 'data-theme')) === null && (await page.evaluate(() => Object.keys(sessionStorage).length)) === 0)

console.log('10. the generic error page')
await page.goto(`${KC}/realms/meddleware/protocol/openid-connect/auth?client_id=does-not-exist&response_type=code&redirect_uri=https%3A%2F%2Fexample.test%2F`)
await page.waitForSelector('#kc-error-message')
await inspect('error')

await browser.close()
console.log(failed === 0 ? '  theme check: ALL PASSED' : `  theme check: ${failed} FAILED`)
process.exit(failed === 0 ? 0 : 1)
