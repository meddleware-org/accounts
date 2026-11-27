<#-- webauthn-register.ftl: registering a key (the first enrolment through the bootstrap path, or an extra key). The label is a real field, not a browser prompt. -->
<#import "template.ftl" as layout>
<@layout.registrationLayout; section>
    <#if section = "header">
        ${msg("webauthn-registration-title")}
    <#elseif section = "form">
        <form id="register" action="${url.loginAction}" method="post">
            <input type="hidden" id="clientDataJSON" name="clientDataJSON">
            <input type="hidden" id="attestationObject" name="attestationObject">
            <input type="hidden" id="publicKeyCredentialId" name="publicKeyCredentialId">
            <input type="hidden" id="transports" name="transports">
            <input type="hidden" id="authenticatorAttachment" name="authenticatorAttachment">
            <input type="hidden" id="error" name="error">
            <div class="field">
                <label for="authenticatorLabel">${msg("webauthn-registration-init-label-prompt")}</label>
                <input id="authenticatorLabel" name="authenticatorLabel" type="text" value="${msg("webauthn-registration-init-label")}" autocomplete="off">
            </div>
        </form>
        <#-- The server's values, for webauthn.js (excludeCredentialIds: the keys already registered). -->
        <div id="kc-webauthn-data" hidden
             data-challenge="${challenge}" data-userid="${userid}" data-username="${username}" data-signature-algorithms="<#list signatureAlgorithms as sigAlg>${sigAlg?c}<#sep>,</#list>"
             data-rp-entity-name="${rpEntityName}" data-rp-id="${rpId}" data-attestation-conveyance-preference="${attestationConveyancePreference}"
             data-authenticator-attachment="${authenticatorAttachment}" data-require-resident-key="${requireResidentKey}" data-resident-key="${residentKey}"
             data-user-verification-requirement="${userVerificationRequirement}" data-create-timeout="${createTimeout}" data-exclude-credential-ids="${excludeCredentialIds}"></div>
        <button id="registerWebAuthn" class="button button-primary" type="button">${msg("doRegisterSecurityKey")}</button>
        <#if !isSetRetry?has_content && isAppInitiatedAction?has_content>
            <form id="kc-webauthn-settings-form" action="${url.loginAction}" method="post">
                <button id="cancelWebAuthnAIA" class="button button-secondary" type="submit" name="cancel-aia" value="true">${msg("doCancel")}</button>
            </form>
        </#if>
    </#if>
</@layout.registrationLayout>
