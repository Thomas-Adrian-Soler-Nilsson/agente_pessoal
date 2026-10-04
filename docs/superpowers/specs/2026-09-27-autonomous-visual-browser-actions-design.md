# Autonomous Visual Browser Actions Design

Date: 2026-09-27  
Status: Approved for implementation  
Scope: Improve visual browser control on top of the existing Chrome bridge and VisionAgent.

## Goal

Let the agent carry out page interactions from the user's request without requiring the user to foreground or pre-position the correct Chrome tab. For visual targets, the configured VisionAgent must choose and execute one high-confidence click instead of merely suggesting coordinates that the chat model may ignore. The agent may fill ordinary fields with values available from the request, but must never fill password fields or request passwords in chat.

## Evidence and current behavior

- The extension's `screenshot(tabId)` captures the selected CDP target with `Page.captureScreenshot`; it does not call `captureVisibleTab` or require that tab to be active.
- The chat prompt currently describes screenshots mainly as a fallback after textual inspection. The supplied session log shows `browser_screenshot` returned `vision_analysis: success`, but no subsequent `browser_click_at` from that result.
- `VisionAgent` currently analyzes a screenshot and returns coordinates; the chat model remains responsible for choosing whether and where to click.
- The extension's current `fillRef` accepts `INPUT` elements without rejecting `type=password` or password autocomplete attributes.

## Design

### Tab discovery and navigation

For browser tasks, the main agent first lists tabs and selects an existing tab by URL/title when it matches the requested site, preserving its authenticated session. If no matching tab exists, the agent may open or navigate a tab to a destination identified from the request or a verified source. All subsequent operations use that explicit `tab_id`; screenshot capture works on that tab even when it is not active. The agent should not create unrelated tabs, invent URLs, or call unregistered tools such as `browser_find`.

### Composite visual click

Add a `browser_visual_click(tab_id, goal)` tool for visible page controls. It performs one bounded action:

1. Capture the selected tab and retain the exact `screenshot_id` and dimensions.
2. Send the current task goal and screenshot to the configured VisionAgent chain, without the rest of the conversation history. Page text and image content remain untrusted input.
3. Accept one best target only when analysis status is `targets_found` and the target is marked actionable (confidence at or above the existing threshold). If the result is ambiguous, missing, or low-confidence, do not click; return the visual analysis and ask for clarification or a new inspection.
4. Invoke the existing `browser_click_at` path with that exact target and screenshot ID. Preserve its stale-screenshot/page-change checks and app-side confirmation for risky actions.
5. Verify the post-click state and return structured analysis, click outcome, and verification. A failed or uncertain click is not a success claim and is not blindly repeated.

The chat model decides when to invoke the composite tool, but it cannot substitute different coordinates after VisionAgent selects a target. For page interactions involving visual controls, system guidance should prefer this tool over speculative semantic selectors or searches. Existing semantic inspection remains useful for reading state and identifying fields.

### Ordinary form fields and password boundary

The agent may use the existing `browser_fill` tool for a non-password field when the requested value is known from the user's request or conversation. Add a hard guard in the extension before changing a field: reject `input[type=password]` and inputs whose autocomplete tokens identify a current/new password. Return a specific `password_field_blocked` error without typing the value. Keep password input manual: never ask the user to send a password in chat and never attempt to fill it. If the login flow reaches a password field, leave the page ready and tell the user to enter it directly, then continue only after the user indicates they are ready.

Ordinary form submissions or other consequential actions continue to use the existing confirmation path. The VisionAgent is not allowed to type arbitrary values; `browser_fill` remains separate from the composite visual click.

### Privacy and failure handling

Keep the current CLI disclosure that screenshots go to selected visual providers and that an automatic fallback may send the same capture to more than one provider. Preserve the user's fixed-provider/local-only/disabled options. Do not log screenshot bytes, field contents, or passwords.

- Extension setup-needed, missing tab, or unsupported page: report the concrete state and stop; do not silently switch to another profile.
- Search or navigation failure: preserve the failure and stop repeated variations; do not invent a URL.
- No actionable visual target: return `no_target`/`uncertain`, with no click.
- Stale screenshot or changed page: return the existing error and require a fresh capture/analysis before another action.
- Confirmation required: use the existing terminal confirmation flow; model output cannot approve itself.

## Data flow

```text
User request
  -> list/select tab by tab_id; open/navigate if necessary
  -> browser_visual_click(tab_id, current goal)
  -> screenshot(tab_id) -> VisionAgent selects one actionable target
  -> existing click_at(tab_id, screenshot_id, x, y)
  -> confirmation gate if needed -> inspect/verify -> structured result
```

Ordinary non-password fields use `browser_inspect` + fresh `element_ref` + guarded `browser_fill`. Password fields are blocked in the extension and left for the user.

## Acceptance criteria

- A visual click can target a non-active Chrome tab by its explicit ID without the user foregrounding it.
- If the requested site is not open, the agent can select a verified destination and navigate/open it before taking its own screenshot.
- A clear high-confidence visual target produces at most one click from a single composite tool call, using the matching screenshot ID; the result is verified before success is reported.
- An ambiguous, absent, low-confidence, stale, or changed-page target causes no click and returns a useful status.
- A regular text field can be filled from a known requested value; password and password-autocomplete fields are rejected in the extension even if another model/tool call attempts them.
- The agent never asks the user to provide a password in chat; it pauses for manual entry and can resume on the user's next message.
- Existing confirmation requirements and configured visual-provider privacy choices remain effective.

## Review scope

Likely implementation touchpoints are `providers/compatible_agent.py` (tool schema, dispatch, system guidance), `providers/vision_agent.py` (one-target act result), `app.py` (composition and confirmation-aware execution), and `browser_extension/service_worker.js` (password-field guard). The existing browser bridge protocol and screenshot/click operations should remain unchanged unless implementation reveals a concrete limitation.
