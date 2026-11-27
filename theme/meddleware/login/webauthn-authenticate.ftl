<#-- webauthn-authenticate.ftl: the sign-in page: the security key (no username is asked: the key says who is signing in). The values the script needs are data attributes, never inline script. -->
<#import "template.ftl" as layout>
<@layout.registrationLayout; section>
    <#if section = "header">
        ${msg("webauthn-login-title")}
    <#elseif section = "form">
        <div id="kc-form-webauthn">
            <#-- The assertion goes into this form (hidden fields), which webauthn.js submits. -->
            <form id="webauth" action="${url.loginAction}" method="post" hidden>
                <input type="hidden" id="clientDataJSON" name="clientDataJSON">
                <input type="hidden" id="authenticatorData" name="authenticatorData">
                <input type="hidden" id="signature" name="signature">
                <input type="hidden" id="credentialId" name="credentialId">
                <input type="hidden" id="userHandle" name="userHandle">
                <input type="hidden" id="error" name="error">
            </form>
            <#-- The server's values, for webauthn.js. credentialIds are this user's registered keys (the browser offers only those). -->
            <div id="kc-webauthn-data" hidden
                 data-is-user-identified="${isUserIdentified}" data-challenge="${challenge}" data-user-verification="${userVerification}" data-rp-id="${rpId}"
                 data-create-timeout="${createTimeout}" data-msg-waiting="${msg("webauthnWaiting")}" data-msg-retry="${msg("webauthnRetry")}" data-credential-ids="<#if authenticators??><#list authenticators.authenticators as authenticator>${authenticator.credentialId}<#sep>,</#list></#if>"></div>
            <p>${msg("webauthn-passwordless-help-text")}</p>
            <#-- The browser's key prompt opens by itself; this line says what is happening (a polite live region), and the button starts it again if it did not open or was cancelled. -->
            <p id="kc-webauthn-status" class="status" role="status" aria-live="polite"></p>
            <button id="authenticateWebAuthnButton" class="button button-primary" type="button" autofocus>${msg("webauthn-doAuthenticate")}</button>
        </div>
    </#if>
</@layout.registrationLayout>
