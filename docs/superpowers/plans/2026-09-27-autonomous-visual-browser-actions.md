# Autonomous Visual Browser Actions Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Let the agent capture and visually click a high-confidence target on an explicitly selected Chrome tab, verify the result, and fill ordinary fields while refusing password fields.

**Architecture:** Add a composite browser tool in `CompatibleAgent` that captures the chosen tab, sends only the current goal and screenshot to `VisionAgent`, executes at most one validated target through the existing confirmation-aware `browser_click_at` path, and inspects the result. Keep password policy in the Chrome extension, shared through a small helper that is unit-testable in Node. Bind visual clicks to a local signature of visible actionable controls so SPA updates invalidate screenshots even when URL and document loader stay the same.

**Tech Stack:** Python `unittest`/pytest-compatible tests, existing browser bridge and VisionAgent, Chrome Manifest V3 service worker, Node's built-in test runner.

**Spec:** `docs/superpowers/specs/2026-09-27-autonomous-visual-browser-actions-design.md`

## Global Constraints

- Use an explicit `tab_id`; screenshot capture must not depend on the tab being active.
- A visual click requires a matching screenshot ID, `targets_found`, and an actionable target with confidence at least `0.72`.
- A visual click also requires the visible actionable page state to match at capture time and immediately before the click.
- Execute no more than one click per `browser_visual_click` call; preserve the existing stale-page and user-confirmation paths.
- Do not send screenshot bytes or full conversation history to the main chat model from the composite tool.
- Reject `input[type=password]` and inputs with `current-password` or `new-password` autocomplete tokens in the extension.
- Never ask the user to provide a password in chat; ordinary values may be filled only when already known.

## Review Focus

- Vision returns no actionable target, a mismatched screenshot ID, or malformed coordinates: assert no click occurs.
- Multiple targets are actionable: select only the highest-confidence target, and do not click on a tie.
- Browser asks for confirmation: preserve that status and token without inspecting as if the click already happened.
- Password metadata appears via type or autocomplete: block before any input event/value change.
- A control moves, is replaced, or is relabeled in the same-document page after capture: reject the stale coordinates before clicking.
- Screenshot capture or click fails/turns uncertain: report the actual state and do not blindly repeat.

---

### Task 1: Composite visual click in the agent

**Files:**
- Modify: `providers/compatible_agent.py`
- Test: `tests/test_agent_contracts.py`

**Interfaces:**
- Consumes: `tool_executor(name: str, arguments: dict)`, `vision_agent.analyze(image: dict, task: str) -> dict`.
- Produces: registered `browser_visual_click(tab_id: int, goal: str)`; result contains `status`, `analysis`, `click`, and `verification` when applicable.

- [x] Add tests asserting the tool schema and screenshot → VisionAgent → exact-coordinate click → inspect order, including preservation of the screenshot ID.
- [x] Add tests that failure, mismatched screenshot ID, no actionable target, and tied top confidence produce no click; confirmation-required results are passed through without a false success.
- [x] Implement the composite helper and dispatch, validating the selected target and returning only structured textual results (never image bytes).
- [x] Update browser guidance to select/reuse a matching tab by ID, prefer `browser_visual_click` for visual controls, and avoid invented URLs, repeated searches, unsupported tools, or password requests.
- [x] Run the focused agent contract tests and verify the results.

### Task 2: Password-field guard in the Chrome extension

**Files:**
- Create: `browser_extension/field_policy.js`
- Modify: `browser_extension/service_worker.js`
- Test: `browser_extension/field_policy.test.js`

**Interfaces:**
- Produces: `isPasswordField(elementMetadata) -> boolean`, imported by the service worker and checked again in the page-side fill function before any focus or value update.

- [x] Add Node tests for `type=password`, autocomplete tokens `current-password` and `new-password`, and ordinary text/textarea controls.
- [x] Run the focused Node tests and verify they fail for the missing policy.
- [x] Implement the shared password classifier and make `fillRef` reject password fields with `password_field_blocked` before dispatching input/change events.
- [x] Run the focused Node tests and `node --check` on the service worker.

### Task 3: Validate the combined change

**Files:**
- Verify: `providers/compatible_agent.py`, `browser_extension/service_worker.js`, and the tests above.

- [x] Run the full Python test suite and the Node field-policy tests.
- [x] Run Python syntax/compile checks and JavaScript syntax checks for modified production files.
- [x] Inspect the final diff and ensure no screenshot data, entered field values, or secrets are logged or returned to the main agent.

### Task 4: Reject stale screenshots after same-document visual changes

**Files:**
- Create: `browser_extension/visual_state_guard.js`
- Modify: `browser_extension/service_worker.js`
- Test: `browser_extension/visual_state_guard.test.js`

- [x] Add a regression test proving a visible control moving or being replaced invalidates the captured state.
- [x] Compute a local one-way signature around screenshot capture and compare it again before dispatching a visual click.
- [x] Exclude field values and retain only the signature in session storage; fail closed if state cannot be collected.
- [x] Verify helper and service-worker syntax plus focused visual/password and agent tests.
- [x] Request a final independent review of the stale-target guard and complete any Important findings.

## Validation Notes

- Focused browser-agent/vision contract tests: 8 passed, 13 deselected, with 4 ambiguity subcases passed.
- Node password policy and visual-state guard tests: 9 passed. Coverage includes same-document movement/replacement, shadow trees, child frames, native/ARIA toggles, input-value privacy, oversized/incomplete snapshots, and worker-level click rejection.
- Python AST parsing, JavaScript syntax checks for the service worker and helpers, and `git diff --check` passed (Git reports only LF/CRLF normalization warnings).
- Full Python suite: 52 passed, 7 failed, 4 subtests passed. Failures are in unrelated existing assumptions/fixtures: automatic-provider fallback expectation; FileTools path boundary expectation; two tests writing to denied fixed paths under the user Desktop; and three legacy BrowserTools tests passing unsupported `user_data_dir`/`headless` constructor arguments.
- Final independent review: no Important findings remain. The reviewer noted the signature is a DOM/control-state fingerprint, not a pixel comparison, and recommended a real-Chrome iframe/shadow smoke test; current integration coverage uses synthetic DevTools snapshots.
