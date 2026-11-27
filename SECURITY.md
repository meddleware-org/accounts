# Security Policy

## Scope

This policy covers the image built here and the realm script:

- A configuration the realm script produces that is weaker than the README states: a password or email path in the browser flow, user verification not required, PKCE not enforced for a client, a secret written to git, to a log or to standard output other than the one-time operator password.
- An image that starts with a writable root filesystem requirement, runs as root, or carries a fixable critical or high vulnerability in what this repository adds.
- A flaw in the publishing workflow that lets an unsigned or unattested image be released.

It does not cover Keycloak itself (report to the [Keycloak project](https://www.keycloak.org/security)) or the services that use the provider.

## Reporting a vulnerability

Report privately through GitHub's "Report a vulnerability" (Security tab of this repository) or by email to the address in the organisation profile. Please include the version and the steps.
You will get an answer within seven days. Please do not open a public issue for a vulnerability.

## Supported versions

Until the platform's mainnet launch only the latest release is supported.
