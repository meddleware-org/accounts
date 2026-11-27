<#-- info.ftl: an information page (for example, "you are signed out"), with the next step when the server offers one. -->
<#import "template.ftl" as layout>
<@layout.registrationLayout displayMessage=false; section>
    <#if section = "header">
        <#if messageHeader??>${kcSanitize(messageHeader)?no_esc}<#else>${kcSanitize(message.summary)?no_esc}</#if>
    <#elseif section = "form">
        <div id="kc-info-message">
            <p class="instruction">${kcSanitize(message.summary)?no_esc}<#if requiredActions??><#list requiredActions><b><#items as reqActionItem>${kcSanitize(msg("requiredAction.${reqActionItem}"))?no_esc}<#sep>, </#items></b></#list></#if></p>
            <#if skipLink??>
            <#elseif pageRedirectUri?has_content>
                <p><a href="${pageRedirectUri}">${msg("backToApplication")}</a></p>
            <#elseif actionUri?has_content>
                <p><a href="${actionUri}">${msg("proceedWithAction")}</a></p>
            <#elseif (client.baseUrl)?has_content>
                <p><a href="${client.baseUrl}">${msg("backToApplication")}</a></p>
            </#if>
        </div>
    </#if>
</@layout.registrationLayout>
