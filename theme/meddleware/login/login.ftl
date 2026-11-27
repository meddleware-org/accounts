<#-- login.ftl: the one-time-password sign-in (first enrolment of a key, or break-glass): username and password on ONE page, so a wrong username and a wrong password give the same message (no account enumeration). -->
<#import "template.ftl" as layout>
<@layout.registrationLayout displayMessage=false; section>
    <#if section = "header">
        ${msg("loginAccountTitle")}
    <#elseif section = "form">
        <#-- The server's message is the generic one ("Invalid username or password."), shown once, whatever was wrong. -->
        <#if message?has_content && (message.type = 'error')>
            <div class="alert alert-error" role="alert"><span class="alert-kind">${msg("alertKind.error")}</span> <span id="kc-message" class="alert-text">${kcSanitize(message.summary)?no_esc}</span></div>
        </#if>
        <form id="kc-form-login" action="${url.loginAction}" method="post">
            <div class="field">
                <label for="username">${msg("username")}</label>
                <input id="username" name="username" type="text" value="${(login.username!'')}" autofocus autocomplete="username" dir="ltr" required aria-invalid="<#if message?has_content && message.type = 'error'>true<#else>false</#if>">
            </div>
            <div class="field">
                <label for="password">${msg("password")}</label>
                <input id="password" name="password" type="password" autocomplete="current-password" required aria-invalid="<#if message?has_content && message.type = 'error'>true<#else>false</#if>">
            </div>
            <input type="hidden" id="id-hidden-input" name="credentialId" <#if auth.selectedCredential?has_content>value="${auth.selectedCredential}"</#if>>
            <button id="kc-login" class="button button-primary" name="login" type="submit">${msg("doSignIn")}</button>
        </form>
    </#if>
</@layout.registrationLayout>
