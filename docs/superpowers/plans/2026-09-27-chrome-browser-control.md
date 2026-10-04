# Chrome Browser Control Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox syntax for tracking.

**Goal:** Let the agent operate tabs in the user's existing Chrome profile through a local extension and report verified action outcomes.

**Architecture:** A Manifest V3 extension owns Chrome tab selection and CDP actions. Chrome starts a packaged Native Messaging host, which relays correlated JSON messages to a per-user local broker in the running Python app. The Python adapter exposes normalized tools and keeps the extension disconnected from provider APIs.

**Tech Stack:** Python 3.12, Chrome Manifest V3, chrome.debugger/CDP, Chrome Native Messaging, Windows PowerShell, PyInstaller.

**Spec:** docs/superpowers/specs/2026-09-27-browser-tools-design.md

## Global Constraints

- Reuse the already-running Chrome profile; never launch or silently select another browser profile.
- Ask for a fresh inspection after stale element references; do not retarget a changed page automatically.
- Report success only when the browser action and its postcondition are observed; otherwise return failure or uncertain.
- Require explicit app-UI approval for actions that submit external data or cause consequential external changes; the model cannot approve its own action.
- Do not read or transmit cookies, passwords, or browser storage; do not log page text or authentication state.
- Register the Native Messaging host for the current Windows user and allow only the extension's fixed ID.
- Keep browser tool actions sequential and bind each request/response to a request ID and tab ID.

## Review Focus

- Chrome restarts or extension service-worker suspension while a tool is waiting: return a bridge-disconnected error and allow a later reconnect.
- User closes or navigates a selected tab during an action: report tab-closed or stale-reference status without operating another tab.
- Chrome internal pages, extension pages, and enterprise policy restrictions: return a specific unsupported/denied result.
- New tabs, popups, and cross-origin frames: report which tab/frame was inspected and never assume the original tab changed.
- Native Messaging output exceeding Chrome's size limit or containing non-UTF-8/page data: bound payloads, frame JSON correctly, and keep stdout protocol-only.

---

### Task 1: Define browser result protocol and Python broker

**Files:**
- Create: tools/browser_protocol.py
- Create: tools/browser_bridge.py
- Modify: tools/browser.py

**Interfaces:**
- Produces BrowserResult mapping: status, request_id, operation, tab, before, after, observation, error_code, retry_hint.
- Produces BrowserBridgeClient.execute(operation: str, arguments: dict, timeout: float = 30) -> BrowserResult.
- BrowserTools methods return BrowserResult mappings, preserving current public method names where practical.

- [ ] Define protocol version, request IDs, bounded payload sizes, allowed operation names, status values, and stable error codes and confirmation_required status in browser_protocol.py.
- [ ] Implement one authenticated per-user broker session and a correlated request/reply queue in browser_bridge.py; handle disconnect, timeout, and reconnect without accepting stale replies.
- [ ] Refactor BrowserTools in tools/browser.py into the Python-facing adapter; return explicit setup-needed status when no extension host is connected.
- [ ] Review protocol framing, input bounds, and action result serialization against the design document.

### Task 2: Add the Native Messaging host and setup lifecycle

**Files:**
- Create: tools/browser_native_host.py
- Create: tools/install_browser_bridge.ps1
- Create: tools/uninstall_browser_bridge.ps1
- Modify: requirements.txt
- Create: browser_extension/manifest.json

**Interfaces:**
- Native host reads/writes Chrome's length-prefixed UTF-8 JSON protocol and relays messages to the authenticated local broker.
- Installer builds the host executable, registers a host manifest under HKCU, and reports the extension ID/path required by Chrome.
- Uninstaller removes only the host registration and generated build artifacts owned by this feature.

- [ ] Implement binary-safe Native Messaging framing, extension-origin validation, payload limits, and stderr-only diagnostics in browser_native_host.py.
- [ ] Add the fixed public extension key/ID and required debugger, tabs, and nativeMessaging permissions to the MV3 manifest.
- [ ] Add PyInstaller as the host build dependency and make the setup script produce the host executable and exact-allowlist host manifest.
- [ ] Register/unregister the host under HKCU only; make setup and removal idempotent and print clear manual Chrome load-unpacked steps.
- [ ] Review generated paths and registry values; ensure uninstall is scoped to this feature's exact key and output directory.

### Task 3: Implement Chrome tab operations and semantic inspection

**Files:**
- Create: browser_extension/service_worker.js
- Create: browser_extension/popup.html
- Create: browser_extension/popup.js
- Modify: browser_extension/manifest.json

**Interfaces:**
- Service worker accepts versioned request objects and replies with the same request ID plus a BrowserResult payload.
- Operations: list_tabs, inspect, click, fill, select, press, navigate, open_tab, wait, back, screenshot, download.
- Inspection references are tab-scoped and valid only for the current inspected document/generation.

- [ ] Connect the service worker to Native Messaging, validate messages and sender context, and report connected/disconnected state in the popup.
- [ ] Implement tab listing and explicit tab targeting; open navigation in a new tab unless an existing tab ID is explicitly provided.
- [ ] Inspect visible text and interactive controls using supported Accessibility/DOM/CDP domains; return bounded roles, accessible names, labels, placeholders, types, and hrefs with fresh references.
- [ ] Implement semantic actions and reject unknown/stale references instead of guessing another target.
- [ ] Gate form submissions and consequential external actions behind app-UI approval; never accept model-provided approval as authorization.
- [ ] Capture before/after observations and return success, failure, or uncertain according to the verified postcondition; detect popup/new-tab changes.
- [ ] Bound screenshot and page observation sizes and expose clear unsupported-page, policy-denied, detached, and timeout outcomes.

### Task 4: Wire browser tools through the app and model prompt

**Files:**
- Modify: app.py
- Modify: providers/compatible_agent.py
- Modify: ui/ui.py only if needed for readable structured result summaries
- Modify: README.md

**Interfaces:**
- LocalToolExecutor delegates browser operations to BrowserTools and preserves result mappings for the existing JSON tool-result serializer.
- Tool schemas take explicit tab_id and fresh element_ref where applicable; role/name fallbacks are optional and bounded.
- System guidance uses choose tab → inspect → act → verify and distinguishes confirmed, failed, and uncertain outcomes.

- [ ] Wire list-tabs, inspect, semantic interaction, tab navigation, wait/back, screenshot, and download schemas to the adapter.
- [ ] Remove or clearly deprecate generic CSS/co-ordinate-first browser guidance; retain coordinate actions only as explicit visual fallback.
- [ ] Keep browser calls out of parallel execution and ensure result mappings survive UI display and provider serialization.
- [ ] Implement an explicit approval prompt/resume path for confirmation_required browser actions.
- [ ] Update setup, permissions, supported Chrome pages, reconnect, and troubleshooting documentation.
- [ ] Review the complete tool path from schema through app executor, bridge, extension, and normalized response.

### Task 5: Integrate the existing research-in-site operation

**Files:**
- Modify: tools/browser.py
- Modify: browser_extension/service_worker.js
- Modify: providers/compatible_agent.py
- Modify: app.py

**Interfaces:**
- browser_search_site(query: str, tab_id: int, max_pages: int = 5) -> BrowserResult with strategy, visited URLs, page limit, matches, and incomplete pages.

- [ ] Make site search use the selected site's search controls when discoverable, otherwise return site-scoped discovery results with the exact fallback strategy recorded.
- [ ] Restore/retain the user's selected tab and report pages that failed or were inaccessible; do not claim exhaustive search beyond the page limit.
- [ ] Update the model instructions to inspect the site first, request bounded search, and report scope/coverage from the tool result.

---
