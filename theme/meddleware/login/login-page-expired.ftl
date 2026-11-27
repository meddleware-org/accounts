<#-- login-page-expired.ftl: the sign-in took too long or was reopened: start again, or continue where it stopped. -->
<#import "template.ftl" as layout>
<@layout.registrationLayout displayMessage=false; section>
    <#if section = "header">
        ${msg("pageExpiredTitle")}
    <#elseif section = "form">
        <div id="kc-page-expired">
            <p>${msg("pageExpiredMsg1")} <a id="loginRestartLink" href="${url.loginRestartFlowUrl}">${msg("doClickHere")}</a>.</p>
            <p>${msg("pageExpiredMsg2")} <a id="loginContinueLink" href="${url.loginAction}">${msg("doClickHere")}</a>.</p>
        </div>
    </#if>
</@layout.registrationLayout>
