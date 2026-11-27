<#-- select-authenticator.ftl: "Try another way": the ways this flow offers (the security key, or a one-time password for a first enrolment), as plain buttons. -->
<#import "template.ftl" as layout>
<@layout.registrationLayout displayInfo=false; section>
    <#if section = "header">
        ${msg("loginChooseAuthenticator")}
    <#elseif section = "form">
        <form id="kc-select-credential-form" action="${url.loginAction}" method="post">
            <#list auth.authenticationSelections as authenticationSelection>
                <button class="button button-secondary" type="submit" name="authenticationExecution" value="${authenticationSelection.authExecId}">${msg(authenticationSelection.displayName)}</button>
            </#list>
        </form>
    </#if>
</@layout.registrationLayout>
