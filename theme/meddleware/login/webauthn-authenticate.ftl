<#-- webauthn-authenticate.ftl: step two of the sign-in: the security key. The values the script needs are data attributes, never inline script. -->
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
                 data-create-timeout="${createTimeout}" data-credential-ids="<#if authenticators??><#list authenticators.authenticators as authenticator>${authenticator.credentialId}<#sep>,</#list></#if>"></div>
            <p>${msg("webauthn-passwordless-help-text")}</p>
            <button id="authenticateWebAuthnButton" class="button button-primary" type="button" autofocus>${msg("webauthn-doAuthenticate")}</button>
        </div>
    </#if>
</@layout.registrationLayout>
