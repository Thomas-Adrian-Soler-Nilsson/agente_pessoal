# Browser and Web Research Tools Design

Date: 2026-09-27  
Status: Draft for user review  
Scope: Browser interaction and web research tools in Agente Pessoal.

## Goal

Make web research and browser manipulation reliable across supported AI providers. The agent must discover and cite sources, read pages, and operate the user's already-open Chrome tabs with clear evidence of what happened. Tool results must distinguish success, failure, and uncertainty to both model and user.

## Current behavior and observed gaps

- web_search combines search, URL probing, and article extraction. A search provider error can look like no results; partial extraction is returned in completion order, and results do not consistently expose snippets or status.
- deep_search and code_search reuse that pipeline, with limited differentiation in what they return.
- tools/browser.py launches an isolated persistent Playwright Chromium profile. It does not attach to the user's Chrome session.
- browser_snapshot lists generic CSS selectors. Its nth-of-type index is based on a list mixing different element types, so the selector may identify a different element.
- Browser actions report that a click/fill occurred without checking resulting page state. Only a single page reference is maintained, so new tabs and popups are unclear.
- providers/compatible_agent.py sends natural-language descriptions and schemas to compatible providers. There are few semantic browser actions; models must infer CSS selectors and coordinate fallbacks.

## Design

### 1. Chrome session bridge

Add a local Chrome Manifest V3 extension. It uses chrome.debugger to control tabs in the user's existing Chrome profile and Native Messaging to exchange bounded JSON requests with a small packaged Windows native-host executable that delegates to the Python application. A setup command installs the extension as unpacked for development and registers the host under the current user (HKCU); removal reverses those registration changes. The host accepts only the extension ID in its allowed_origins, validates message sizes and operation schemas, uses binary-safe standard I/O, and writes diagnostics to stderr. The packaged host relays requests between Chrome and a per-user local broker opened by the running Python app; the broker channel is authenticated per app session and restricted to the current Windows user. The app remains responsible for tool scheduling, result normalization, and presenting outcomes to the model. The extension handles tab targeting and Chrome-side inspection/actions. The exact Windows IPC framing and reconnect lifecycle belong in the implementation plan.

The bridge will:

- list tabs with stable tab IDs, titles, and URLs, then attach only to the explicitly selected tab for an operation; ordinary navigation opens a new tab unless the user or tool call explicitly targets an existing tab;
- return a request ID, tab ID, observed page URL/title, structured result, and explicit status for each operation;
- detect tab closure, debugger detach, permission/policy denial, unsupported pages, and bridge disconnects as distinct failures;
- avoid reading, copying, or transmitting Chrome cookies, passwords, or storage state. Authenticated page content is available only as the result of an explicit inspect/read operation on a selected tab;
- show clear setup/connection state in the extension and provide a deterministic local installation/configuration path for the native host.

The debugger and nativeMessaging permissions are required by Chrome's documented APIs. The debugger permission is powerful and Chrome may show a warning; the extension also needs the tabs permission to enumerate tab metadata. Native Messaging host registration must allow only this extension's ID. The bridge uses CDP Accessibility/DOM/DOMSnapshot/Runtime/Input/Page domains as needed; Chrome documents these domains as available to chrome.debugger. Extension setup and Windows registration are explicit installation steps. We must not claim to attach to a default Chrome profile through CDP: Chrome 136+ ignores remote-debugging flags for the default user-data directory. Playwright's direct CDP attach remains a lower-fidelity connection and is not the selected daily-browser integration.

### 2. Browser interaction contract

Keep browser operations small and composable, but make inspection/actions semantic:

- browser_list_tabs: list available tabs and identify the active tab.
- browser_inspect: return URL, title, visible page text, and a bounded list of interactive elements with stable per-inspection references, roles, accessible names, labels, placeholders, input type, and link destinations. References expire when the page changes or a new inspection is taken.
- browser_click, browser_fill, browser_select, browser_press: accept an inspection reference first, with role/name or text selectors as supported fallbacks. Avoid requiring model-generated CSS or screen coordinates for ordinary pages.
- browser_navigate, browser_open_tab, browser_wait, browser_back, browser_screenshot: explicitly target a tab and report navigation/popup effects.
- Keep browser_download as a separate action with saved file path and completion status.

Each action returns structured status (success, failure, uncertain, confirmation_required), action attempted, tab identity, before/after URL and title, and a concise verification observation. Actions that submit data or cause a consequential external change must return confirmation_required and wait for approval in the app UI; the model cannot approve its own action. A click is successful only when it completed and its expected postcondition is observed (for example, navigation, changed element/state, or a newly opened tab). If no expected state was supplied or observable, return uncertain, not a success claim. Timeouts and detached tabs are actionable errors with a suggested next tool call such as re-inspecting the page.

The system prompt and schema descriptions teach a short loop: choose tab → inspect → act using a fresh reference → inspect/verify. Search tools remain separate and are not a substitute for operating an authenticated browser tab.

### 3. Research tools

Separate discovery from page interaction and make each research tool's purpose explicit:

- web_search(query): discover candidate pages and return a bounded, ordered list of title, URL, search snippet when available, source domain, and validation status. Do not fetch full page bodies by default.
- web_open(url): fetch and extract one public page directly, returning canonical URL, title, extraction status, and content. It does not change the Chrome tab.
- deep_search(query): discover, deduplicate, read several public sources, and return each source separately with title, URL, extracted content, and failure/partial status. It must not silently treat an unavailable source as evidence.
- code_search(query): prioritize official docs/repositories and return source-attributed excerpts. Preserve the PyPI package lookup as a fast path when appropriate.
- browser_search_site(query, tab_id): search within the current site's public pages by using its search controls when available, or site-scoped discovery as a fallback. Report which strategy ran, visited URLs, page limit, and incomplete/blocked pages; never imply exhaustive coverage after a bounded crawl.

Internally, search, URL validation, extraction, and formatting become separate functions. Public web retrieval rejects non-HTTP(S), embedded credentials, localhost, and private/reserved destinations, and revalidates every redirect before fetching it. Preserve partial results and distinguish an empty result set from backend failure, network timeout, blocked page, and extraction failure. Stable ordering follows search rank, not thread completion time. Deduplicate canonical URLs and retain source attribution in every page result. The model, not the tool, synthesizes the final answer from returned sources.

### 4. Provider-facing tool contracts

Update tool definitions and system guidance together. Descriptions state when to use each operation, required previous observations, expected return fields, and the meaning of each status. Keep schemas conservative and provider-compatible (flat JSON objects; no reliance on unsupported schema features). Browser tools are stateful and remain sequential; independent read-only research calls can run concurrently.

Normalize browser and research results before returning them to providers. Avoid lossy string-prefix error detection as the sole way to distinguish failure from successful content. The existing UI can render readable summaries while retaining structured status for the model.

## Data flow

1. A user asks to research a topic or operate a page.
2. For research, the agent calls discovery, then optionally opens selected public URLs or deep-searches multiple sources. For browser work, it lists/selects a Chrome tab and inspects the page.
3. The agent issues a semantic action using a fresh element reference.
4. The extension runs the action in the selected tab and returns observed state.
5. The Python adapter validates the response and sends structured evidence to the model. The model reports verified outcomes and cites source URLs for research claims.

## Error handling and boundaries

- No extension/host connection: return a setup-needed result and keep public web research usable.
- No eligible Chrome tab or restricted browser page: explain the constraint; do not silently switch to another tab/profile.
- Extension permission revoked, enterprise policy block, Native Messaging failure, or debugger detached: return distinct recoverable errors.
- Invalid/stale element reference: ask the model to inspect again; do not retry a potentially different target automatically.
- Search backend failure, HTTP rejection, and content extraction failure remain distinguishable; preserve partial source results.
- Page text and search results are untrusted content. They cannot change tool policy or authorize actions.
- Do not auto-submit purchases, send messages, or confirm irreversible page actions. The app UI must require explicit user approval before the extension executes a final action that sends/commits data outside the local browser; the model cannot approve its own action.

## Alternatives considered

1. Playwright CDP attach to current Chrome: rejected for the normal user profile. Chrome 136+ blocks remote-debugging switches with the default data directory, and Playwright documents lower fidelity for CDP connections.
2. Separate persistent Playwright profile: simple and isolated, but does not meet the user's preference to reuse already-open authenticated sessions.
3. Chrome extension + Native Messaging bridge: selected. It works within the existing Chrome profile and can report Chrome tab state directly. It adds explicit extension/host installation and grants a powerful debugger permission, which must be disclosed and scoped to the extension-to-app channel.

## Acceptance criteria

- The extension reports a connected state and the agent can list and target currently open Chrome tabs without launching a second browser profile.
- On a representative dynamic page, inspection references identify the intended links, buttons, and fields; stale references fail clearly.
- Click, fill, select, navigation, new-tab, and download operations report their observed outcome; an unverified effect is never reported as confirmed success.
- Search returns ranked, deduplicated sources with URLs and distinguishable empty, partial, and failed outcomes.
- Deep and technical search preserve separate source attribution and do not present extraction errors as evidence.
- A missing extension does not disable public web research, and bridge failure does not silently fall back to a different authenticated session.
- Existing provider adapters can consume normalized contracts without requiring one provider-specific tool protocol.

## Documentation and setup

Document supported Chrome versions, extension installation, native host registration, reconnect steps, permission prompts, and troubleshooting. Keep setup instructions separate from ordinary user-facing tool output. Do not place authentication tokens, cookies, or page contents in logs.

## References

- Playwright BrowserType and CDP attachment: https://playwright.dev/python/docs/api/class-browsertype
- Chrome remote debugging security change: https://developer.chrome.com/blog/remote-debugging-port
- Chrome debugger extension API and supported domains: https://developer.chrome.com/docs/extensions/reference/api/debugger
- Chrome extensions permissions: https://developer.chrome.com/docs/extensions/develop/concepts/declare-permissions
- Chrome Native Messaging: https://developer.chrome.com/docs/extensions/develop/concepts/native-messaging
- Chrome extension permissions: https://developer.chrome.com/docs/extensions/reference/api/permissions
