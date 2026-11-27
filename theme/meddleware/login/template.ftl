<#-- template.ftl: the page frame of every login page (the platform's replacement for the PatternFly one). -->
<#-- No inline script, no inline style, no inline event handler, no external host: the realm's Content-Security-Policy would refuse them. -->
<#macro registrationLayout bodyClass="" displayInfo=false displayMessage=true displayRequiredFields=false>
<!DOCTYPE html>
<html lang="${lang}"<#if realm.internationalizationEnabled> dir="${(locale.rtl)?then('rtl','ltr')}"</#if>>
<head>
    <meta charset="utf-8">
    <meta name="viewport" content="width=device-width, initial-scale=1">
    <meta name="color-scheme" content="light dark">
    <#-- A sign-in page carries a session: it must not be cached, and it names no referrer. -->
    <meta name="referrer" content="no-referrer">
    <title>${msg("loginTitle", (realm.displayName!''))}</title>
    <#-- The stylesheets and the blocking theme-init script named in theme.properties. -->
    <#if properties.styles?has_content>
        <#list properties.styles?split(' ') as style>
            <link href="${url.resourcesPath}/${style}" rel="stylesheet">
        </#list>
    </#if>
    <#if properties.scripts?has_content>
        <#list properties.scripts?split(' ') as script>
            <script src="${url.resourcesPath}/${script}"></script>
        </#list>
    </#if>
    <#-- The page's own script (WebAuthn): an external module, deferred, so the page is readable before it runs. -->
    <script type="module" src="${url.resourcesPath}/js/webauthn.js"></script>
</head>
<body data-page-id="login-${pageId}">
<div class="page">
    <header class="brand">
        <#-- The wordmark is text: the platform ships no font file and no image on this page. -->
        <p class="brand-name">${(realm.displayName!'Meddleware')}</p>
    </header>
    <main class="card">
        <h1 id="kc-page-title"><#nested "header"></h1>

        <#-- Who is signing in (after the username step), with a way back to start again: a plain link, no script. -->
        <#if auth?has_content && auth.showUsername() && !auth.showResetCredentials()>
            <p class="who"><span class="who-label">${msg("username")}</span> <strong id="kc-attempted-username">${auth.attemptedUsername}</strong>
                <a id="reset-login" href="${url.loginRestartFlowUrl}">${msg("restartLoginTooltip")}</a></p>
        </#if>

        <#-- The server's message (an error, a warning, an information): announced to assistive technology when it appears. -->
        <#if displayMessage && message?has_content && (message.type != 'warning' || !isAppInitiatedAction??)>
            <div class="alert alert-${message.type}" role="<#if message.type = 'error'>alert<#else>status</#if>">
                <span class="alert-kind">${msg("alertKind." + message.type)}</span>
                <span id="kc-message" class="alert-text">${kcSanitize(message.summary)?no_esc}</span>
            </div>
        </#if>

        <#nested "form">

        <#-- "Try another way" only when the flow offers one (this platform's flow does not): a form button, not a javascript: link. -->
        <#if auth?has_content && auth.showTryAnotherWayLink()>
            <form id="kc-select-try-another-way-form" action="${url.loginAction}" method="post">
                <input type="hidden" name="tryAnotherWay" value="on">
                <button id="try-another-way" class="button button-secondary" type="submit">${msg("doTryAnotherWay")}</button>
            </form>
        </#if>

        <#if displayInfo>
            <div id="kc-info" class="info"><#nested "info"></div>
        </#if>
    </main>
    <footer class="notice">
        <#-- The platform's rights notice for site content: the Kopimi mark (linking to the Kopimi document), the year, the organisation and the statement (docs/legal L-IP-1). -->
        <small><a class="symbol-link" href="https://meddleware.co.uk/legal/powr.broccoli-kopimi.pdf" target="_blank" rel="noopener noreferrer" aria-label="${msg("noticeSymbolLabel")}"><svg viewBox="0 0 24 24" width="1em" height="1em" aria-hidden="true" focusable="false"><path d="M12 4L22 23H2Z" fill="none" stroke="currentColor" stroke-width="1.5"/><text x="12" y="18" text-anchor="middle" dominant-baseline="middle" font-size="11" fill="currentColor">C</text></svg></a> ${.now?string('yyyy')} Meddleware Limited. ${msg("noticeStatement")}</small>
    </footer>
</div>
</body>
</html>
</#macro>
