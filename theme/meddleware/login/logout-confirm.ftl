<#-- logout-confirm.ftl: asks before ending the session when the application sent no id_token_hint. No inline handler: a form post, once. -->
<#import "template.ftl" as layout>
<@layout.registrationLayout; section>
    <#if section = "header">
        ${msg("logoutConfirmTitle")}
    <#elseif section = "form">
        <div id="kc-logout-confirm">
            <p class="instruction">${msg("logoutConfirmHeader")}</p>
            <form action="${url.logoutConfirmAction}" method="post">
                <input type="hidden" name="session_code" value="${logoutConfirm.code}">
                <button id="kc-logout" class="button button-primary" name="confirmLogout" type="submit">${msg("doLogout")}</button>
            </form>
            <#if !logoutConfirm.skipLink && (client.baseUrl)?has_content>
                <p><a href="${client.baseUrl}">${msg("backToApplication")}</a></p>
            </#if>
        </div>
    </#if>
</@layout.registrationLayout>
