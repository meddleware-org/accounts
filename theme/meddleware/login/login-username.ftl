<#-- login-username.ftl: step one of the platform's passkey-only sign-in: the username. -->
<#import "template.ftl" as layout>
<@layout.registrationLayout displayMessage=!messagesPerField.existsError('username'); section>
    <#if section = "header">
        ${msg("loginAccountTitle")}
    <#elseif section = "form">
        <form id="kc-form-login" action="${url.loginAction}" method="post">
            <div class="field">
                <label for="username">${msg("username")}</label>
                <#-- autocomplete=username lets a password manager or the browser offer the saved name; the field is the first thing focused. -->
                <input id="username" name="username" type="text" value="${(login.username!'')}" autofocus autocomplete="username" dir="ltr" required
                       aria-invalid="<#if messagesPerField.existsError('username')>true<#else>false</#if>"<#if messagesPerField.existsError('username')> aria-describedby="input-error-username"</#if>>
                <#if messagesPerField.existsError('username')>
                    <p id="input-error-username" class="field-error" role="alert">${kcSanitize(messagesPerField.get('username'))?no_esc}</p>
                </#if>
            </div>
            <button id="kc-login" class="button button-primary" name="login" type="submit">${msg("doContinue")}</button>
        </form>
    </#if>
</@layout.registrationLayout>
