// webauthn.js: the WebAuthn calls of the sign-in and key-registration pages (the platform's replacement for Keycloak's own inline scripts, which the Content-Security-Policy refuses).
// The server-side values are read from data-* attributes of the element #kc-webauthn-data (rendered by the templates); the button that starts a call is #authenticateWebAuthnButton or #registerWebAuthn.
// The result goes into the hidden fields of the page's form and the form is submitted, exactly as Keycloak's own scripts do, so the server-side authenticators are unchanged.

/** base64url text (padding optional) to bytes. */
function b64uToBytes(text) {
  // base64url uses - and _ where base64 uses + and /; restore them, then the padding atob needs.
  var base64 = text.replace(/-/g, '+').replace(/_/g, '/')
  while (base64.length % 4) base64 += '='
  // atob gives one character per byte; copy them into a typed array.
  var binary = atob(base64)
  var bytes = new Uint8Array(binary.length)
  for (var i = 0; i < binary.length; i++) bytes[i] = binary.charCodeAt(i)
  return bytes
}

/** bytes (an ArrayBuffer or view) to base64url text without padding. */
function bytesToB64u(buffer) {
  // One character per byte, then btoa, then the URL-safe alphabet without padding (what the server expects).
  var bytes = new Uint8Array(buffer)
  var binary = ''
  for (var i = 0; i < bytes.length; i++) binary += String.fromCharCode(bytes[i])
  return btoa(binary).replace(/\+/g, '-').replace(/\//g, '_').replace(/=+$/, '')
}

/** a form field by id. */
function field(id) { return document.getElementById(id) }

/** report an error to the server (it shows its own message) by submitting the form with the error field set. */
function fail(formId, error) {
  // The server reads this field and shows its own message for the failure.
  field('error').value = String(error)
  field(formId).requestSubmit()
}

/** navigator.credentials.get() for the sign-in page, then submit the assertion. */
async function authenticate(data) {
  if (!window.PublicKeyCredential) { fail('webauth', 'WebAuthnUnsupportedBrowser'); return }
  // The request: the relying party, the server's one-time challenge, and (below) the timeout, the allowed keys and the user-verification rule from the realm's policy.
  var publicKey = { rpId: data.rpId, challenge: b64uToBytes(data.challenge) }
  if (Number(data.createTimeout) !== 0) publicKey.timeout = Number(data.createTimeout) * 1000
  // The credentials the user has (when the user is already identified): the browser offers only these.
  if (data.isUserIdentified === 'true' && data.credentialIds) {
    publicKey.allowCredentials = data.credentialIds.split(',').filter(Boolean).map(function (id) { return { type: 'public-key', id: b64uToBytes(id) } })
  }
  if (data.userVerification !== 'not specified') publicKey.userVerification = data.userVerification
  // Ask the browser, which asks the key (the person touches it and verifies with their PIN or biometric); then hand the signed assertion to the server through the form.
  try {
    var result = await navigator.credentials.get({ publicKey: publicKey })
    field('clientDataJSON').value = bytesToB64u(result.response.clientDataJSON)
    field('authenticatorData').value = bytesToB64u(result.response.authenticatorData)
    field('signature').value = bytesToB64u(result.response.signature)
    field('credentialId').value = result.id
    if (result.response.userHandle) field('userHandle').value = bytesToB64u(result.response.userHandle)
    field('webauth').requestSubmit()
  } catch (error) {
    fail('webauth', error)
  }
}

/** navigator.credentials.create() for the key-registration page, then submit the attestation with the label the person typed. */
async function register(data) {
  if (!window.PublicKeyCredential) { fail('register', 'WebAuthnUnsupportedBrowser'); return }
  // The signature algorithms the realm accepts (ES256 and RS256 by default); ES256 alone when none is listed.
  var algorithms = data.signatureAlgorithms ? data.signatureAlgorithms.split(',').filter(Boolean).map(Number) : []
  if (algorithms.length === 0) algorithms = [-7]
  // The creation request: the server's challenge, who the relying party and the user are, and the algorithms.
  var publicKey = {
    challenge: b64uToBytes(data.challenge),
    rp: { id: data.rpId, name: data.rpEntityName },
    user: { id: b64uToBytes(data.userid), name: data.username, displayName: data.username },
    pubKeyCredParams: algorithms.map(function (alg) { return { type: 'public-key', alg: alg } })
  }
  if (data.attestationConveyancePreference !== 'not specified') publicKey.attestation = data.attestationConveyancePreference
  // The authenticator selection from the realm's policy: attachment, resident key (passkey), and user verification, each only when the realm specifies it.
  var selection = {}
  var selected = false
  if (data.authenticatorAttachment !== 'not specified') { selection.authenticatorAttachment = data.authenticatorAttachment; selected = true }
  if (data.residentKey && data.residentKey !== 'not specified') {
    selection.residentKey = data.residentKey
    selection.requireResidentKey = data.residentKey === 'required'
    selected = true
  } else if (data.requireResidentKey === 'Yes') {
    selection.residentKey = 'required'
    selection.requireResidentKey = true
    selected = true
  }
  if (data.userVerificationRequirement !== 'not specified') { selection.userVerification = data.userVerificationRequirement; selected = true }
  if (selected) publicKey.authenticatorSelection = selection
  if (Number(data.createTimeout) !== 0) publicKey.timeout = Number(data.createTimeout) * 1000
  // Keys already registered are excluded, so the same physical key cannot be registered twice.
  var excluded = (data.excludeCredentialIds || '').split(',').filter(Boolean)
  if (excluded.length > 0) publicKey.excludeCredentials = excluded.map(function (id) { return { type: 'public-key', id: b64uToBytes(id) } })
  // Ask the browser to make the credential; then put the attestation and the key's identifiers into the form and submit it.
  try {
    var result = await navigator.credentials.create({ publicKey: publicKey })
    field('clientDataJSON').value = bytesToB64u(result.response.clientDataJSON)
    field('attestationObject').value = bytesToB64u(result.response.attestationObject)
    field('publicKeyCredentialId').value = bytesToB64u(result.rawId)
    if (typeof result.response.getTransports === 'function') field('transports').value = (result.response.getTransports() || []).join()
    if (result.authenticatorAttachment) field('authenticatorAttachment').value = result.authenticatorAttachment
    field('register').requestSubmit()
  } catch (error) {
    fail('register', error)
  }
}

// Wire the page: the data element says which page this is; the button click is the user gesture the browser requires.
var data = field('kc-webauthn-data')
if (data) {
  var d = data.dataset
  var sign = field('authenticateWebAuthnButton')
  var enrol = field('registerWebAuthn')
  if (sign) sign.addEventListener('click', function () { authenticate(d) }, { once: true })
  if (enrol) enrol.addEventListener('click', function () { register(d) }, { once: true })
  // A failed call is retried by the server's error page (a form post), never by calling again here.
}

// The Try again button of the error page submits its form (replaces Keycloak's inline refreshPage()).
var retry = field('kc-try-again')
if (retry) {
  retry.addEventListener('click', function () {
    field('isSetRetry').value = 'retry'
    field('executionValue').value = retry.dataset.execution
    field('kc-error-credential-form').requestSubmit()
  })
}
