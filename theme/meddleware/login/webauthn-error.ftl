<#-- webauthn-error.ftl: a failed key call: the server's message (shown by the frame) and a button that asks the server to try again. -->
<#import "template.ftl" as layout>
<@layout.registrationLayout; section>
    <#if section = "header">
        ${msg("webauthn-error-title")}
    <#elseif section = "form">
        <form id="kc-error-credential-form" action="${url.loginAction}" method="post">
            <input type="hidden" id="executionValue" name="authenticationExecution">
            <input type="hidden" id="isSetRetry" name="isSetRetry">
            <button id="kc-try-again" class="button button-primary" type="button" name="try-again" data-execution="${execution}">${msg("doTryAgain")}</button>
        </form>
        <#if isAppInitiatedAction??>
            <form id="kc-webauthn-settings-form" action="${url.loginAction}" method="post">
                <button id="cancelWebAuthnAIA" class="button button-secondary" type="submit" name="cancel-aia" value="true">${msg("doCancel")}</button>
            </form>
        </#if>
    </#if>
</@layout.registrationLayout>
