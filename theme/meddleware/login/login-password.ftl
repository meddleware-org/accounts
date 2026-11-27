<#-- login-password.ftl: the one-time password of the bootstrap path (first enrolment of a key, or break-glass); never shown to a user who has a key. -->
<#import "template.ftl" as layout>
<@layout.registrationLayout displayMessage=!messagesPerField.existsError('password'); section>
    <#if section = "header">
        ${msg("doLogIn")}
    <#elseif section = "form">
        <form id="kc-form-login" action="${url.loginAction}" method="post">
            <div class="field">
                <label for="password">${msg("password")}</label>
                <input id="password" name="password" type="password" autofocus autocomplete="current-password" required
                       aria-invalid="<#if messagesPerField.existsError('password')>true<#else>false</#if>"<#if messagesPerField.existsError('password')> aria-describedby="input-error-password"</#if>>
                <#if messagesPerField.existsError('password')>
                    <p id="input-error-password" class="field-error" role="alert">${kcSanitize(messagesPerField.get('password'))?no_esc}</p>
                </#if>
            </div>
            <button id="kc-login" class="button button-primary" name="login" type="submit">${msg("doLogIn")}</button>
        </form>
    </#if>
</@layout.registrationLayout>
