const assert = require("node:assert/strict");
const { test } = require("node:test");
const fs = require("node:fs");
const { webcrypto } = require("node:crypto");
const vm = require("node:vm");

const visualStateGuard = require("./visual_state_guard.js");

function makeSnapshot(documentModels) {
  const strings = [];
  const indexes = new Map();
  const add = value => {
    const text = String(value ?? "");
    if (!indexes.has(text)) {
      indexes.set(text, strings.length);
      strings.push(text);
    }
    return indexes.get(text);
  };
  const documents = documentModels.map(model => {
    const nodeNames = ["#document", "HTML", "BODY"];
    const nodeValues = ["", "", ""];
    const parentIndex = [-1, 0, 1];
    const attributes = [[], [], []];
    const layoutNodeIndex = [];
    const bounds = [];
    const styles = [];
    const clickable = [];
    const inputValue = { index: [], value: [] };
    const inputChecked = { index: [] };
    const optionSelected = { index: [] };
    const shadowRootType = { index: [], value: [] };

    for (const control of model.controls || []) {
      const nodeIndex = nodeNames.length;
      nodeNames.push(control.tag.toUpperCase());
      nodeValues.push("");
      parentIndex.push(2);
      const flatAttributes = [];
      for (const [name, value] of Object.entries(control.attrs || {})) flatAttributes.push(add(name), add(value));
      attributes.push(flatAttributes);
      if (control.clickable !== false) clickable.push(nodeIndex);
      if (control.shadow) shadowRootType.index.push(nodeIndex), shadowRootType.value.push(add("open"));
      if (control.value !== undefined) inputValue.index.push(nodeIndex), inputValue.value.push(add(control.value));
      if (control.checked) inputChecked.index.push(nodeIndex);
      if (control.selected) optionSelected.index.push(nodeIndex);

      if (control.text) {
        nodeNames.push("#text");
        nodeValues.push(control.text);
        parentIndex.push(nodeIndex);
        attributes.push([]);
      }

      layoutNodeIndex.push(nodeIndex);
      bounds.push(control.bounds || [10, 20, 100, 32]);
      styles.push(["block", "visible", "1", "auto", "pointer", "auto"].map(add));
    }

    return {
      frameId: add(model.frameId),
      documentURL: add(model.url),
      scrollOffsetX: model.scrollX || 0,
      scrollOffsetY: model.scrollY || 0,
      nodes: {
        nodeName: nodeNames.map(add),
        nodeValue: nodeValues.map(add),
        parentIndex,
        attributes,
        isClickable: { index: clickable },
        inputValue,
        inputChecked,
        optionSelected,
        shadowRootType,
      },
      layout: { nodeIndex: layoutNodeIndex, bounds, styles },
    };
  });
  return { strings, documents };
}

async function stateFor(models, viewport = { width: 800, height: 600, dpr: 1 }) {
  return visualStateGuard.signatureFromSnapshot(makeSnapshot(models), viewport, webcrypto);
}

test("inspection prioritizes message fields over generic buttons", async () => {
  const event = { addListener() {} };
  const tab = { id: 9, title: "DeepSeek", url: "https://chat.deepseek.com/", active: true, windowId: 1 };
  const nodes = Array.from({ length: 85 }, (_, index) => ({
    role: { value: "button" },
    name: { value: "Botão " + index },
    backendDOMNodeId: index + 1,
    frameId: "main-frame",
    htmlTag: "button",
    properties: [],
  }));
  nodes.push({
    role: { value: "textbox" },
    name: { value: "Mensagem para DeepSeek" },
    backendDOMNodeId: 100,
    frameId: "main-frame",
    htmlTag: "div",
    properties: [],
  });
  const chrome = {
    runtime: {
      onStartup: event, onInstalled: event, onMessage: event, id: "test-extension",
      connectNative() { return { onMessage: event, onDisconnect: event, postMessage() {} }; },
    },
    alarms: { onAlarm: event, create() {} },
    action: { onClicked: event },
    storage: { session: { async get() { return {}; }, async set() {} } },
    tabs: { async get() { return tab; } },
    debugger: {
      async sendCommand(_target, method) {
        if (method === "Runtime.evaluate") return { result: { value: "" } };
        if (method === "Page.getFrameTree") return { frameTree: { frame: { id: "main-frame", loaderId: "loader-1" } } };
        if (method === "Accessibility.getFullAXTree") return { nodes };
        if (method === "DOM.describeNode") return { node: { attributes: [] } };
        return {};
      },
    },
  };
  const context = vm.createContext({ chrome, crypto: webcrypto, importScripts() {}, console, setTimeout, clearTimeout });
  vm.runInContext(fs.readFileSync("browser_extension/service_worker.js", "utf8"), context);

  const inspection = await vm.runInContext("inspectTab(9)", context);

  assert.equal(inspection.data.elements[0].role, "textbox");
  assert.equal(inspection.data.elements[0].name, "Mensagem para DeepSeek");
});

test("retains references across inspections and rebinds a replaced composer node", async () => {
  const event = { addListener() {} };
  const tab = { id: 9, title: "DeepSeek", url: "https://chat.deepseek.com/", active: true, windowId: 1 };
  const session = {};
  const commands = [];
  let backendId = 100;
  const textbox = () => ({
    role: { value: "textbox" },
    name: { value: "Mensagem para DeepSeek" },
    backendDOMNodeId: backendId,
    frameId: "main-frame",
    htmlTag: "div",
    properties: [],
  });
  const chrome = {
    runtime: {
      onStartup: event, onInstalled: event, onMessage: event, id: "test-extension",
      connectNative() { return { onMessage: event, onDisconnect: event, postMessage() {} }; },
    },
    alarms: { onAlarm: event, create() {} },
    action: { onClicked: event },
    storage: {
      session: {
        async get(key) { return { [key]: session[key] }; },
        async set(values) { Object.assign(session, values); },
      },
    },
    tabs: { async get() { return tab; } },
    debugger: {
      async sendCommand(_target, method, params = {}) {
        commands.push({ method, params });
        if (method === "Runtime.evaluate") return { result: { value: "" } };
        if (method === "Page.getFrameTree") return { frameTree: { frame: { id: "main-frame", loaderId: "loader-1" } } };
        if (method === "Accessibility.getFullAXTree") return { nodes: [textbox()] };
        if (method === "DOM.describeNode") {
          if (params.backendNodeId !== backendId) return {};
          return { node: { nodeId: "dom-" + backendId, nodeName: "DIV", attributes: ["role", "textbox", "placeholder", "Mensagem para DeepSeek"] } };
        }
        if (method === "DOM.resolveNode") return { object: { objectId: "object-" + params.backendNodeId } };
        if (method === "Runtime.callFunctionOn") return { result: { value: true } };
        return {};
      },
    },
  };
  const context = vm.createContext({
    chrome,
    crypto: webcrypto,
    isPasswordField: require("./field_policy.js").isPasswordField,
    importScripts() {},
    console,
    setTimeout,
    clearTimeout,
  });
  vm.runInContext(fs.readFileSync("browser_extension/service_worker.js", "utf8"), context);

  const firstInspection = await vm.runInContext("inspectTab(9)", context);
  const oldRefId = firstInspection.data.elements[0].element_ref;
  backendId = 200;
  await vm.runInContext("inspectTab(9)", context);

  const oldRef = await vm.runInContext("getRef(9, " + JSON.stringify(oldRefId) + ")", context);
  context.refsForTest = oldRef;
  const result = await vm.runInContext("fillRef(9, refsForTest, 'Oi')", context);

  assert.deepEqual(JSON.parse(JSON.stringify(result)), { filled: true, value_length: 2 });
  assert.equal(oldRef.backendId, 200);
  assert.ok(commands.some(command => command.method === "DOM.resolveNode" && command.params.backendNodeId === 200));
  assert.ok(commands.some(command => command.method === "Runtime.callFunctionOn"));
});

test("detects a visible control moving between screenshot and click", async () => {
  const captured = await stateFor([{ frameId: "main", url: "https://example.test", controls: [
    { tag: "button", text: "Entrar", attrs: { "aria-label": "Entrar" }, bounds: [10, 20, 100, 32] },
  ] }]);
  const moved = await stateFor([{ frameId: "main", url: "https://example.test", controls: [
    { tag: "button", text: "Entrar", attrs: { "aria-label": "Entrar" }, bounds: [10, 150, 100, 32] },
  ] }]);

  assert.equal(visualStateGuard.sameVisualState(captured, moved), false);
});

test("detects a control replacement or relabel inside a shadow tree", async () => {
  const captured = await stateFor([{ frameId: "main", url: "https://example.test", controls: [
    { tag: "button", text: "Continuar", attrs: { id: "continue" }, shadow: true },
  ] }]);
  const replaced = await stateFor([{ frameId: "main", url: "https://example.test", controls: [
    { tag: "button", text: "Cancelar", attrs: { id: "cancel" }, shadow: true },
  ] }]);

  assert.equal(visualStateGuard.sameVisualState(captured, replaced), false);
});

test("detects a same-document control changing in a child frame", async () => {
  const captured = await stateFor([
    { frameId: "main", url: "https://example.test", controls: [{ tag: "iframe", bounds: [0, 100, 500, 300] }] },
    { frameId: "child", url: "https://child.test", controls: [{ tag: "button", text: "Confirmar" }] },
  ]);
  const changedChild = await stateFor([
    { frameId: "main", url: "https://example.test", controls: [{ tag: "iframe", bounds: [0, 100, 500, 300] }] },
    { frameId: "child", url: "https://child.test", controls: [{ tag: "button", text: "Cancelar" }] },
  ]);

  assert.equal(visualStateGuard.sameVisualState(captured, changedChild), false);
});

test("detects native checkbox and ARIA toggle state changes at the same coordinates", async () => {
  const captured = await stateFor([{ frameId: "main", url: "https://example.test", controls: [
    { tag: "input", attrs: { type: "checkbox", id: "terms", "aria-checked": "false" }, checked: false },
    { tag: "button", text: "Ativar", attrs: { id: "toggle", "aria-pressed": "false", "aria-expanded": "false" }, bounds: [150, 20, 100, 32] },
  ] }]);
  const changed = await stateFor([{ frameId: "main", url: "https://example.test", controls: [
    { tag: "input", attrs: { type: "checkbox", id: "terms", "aria-checked": "true" }, checked: true },
    { tag: "button", text: "Ativar", attrs: { id: "toggle", "aria-pressed": "true", "aria-expanded": "true" }, bounds: [150, 20, 100, 32] },
  ] }]);

  assert.equal(visualStateGuard.sameVisualState(captured, changed), false);
});

test("does not include current input values in the stored SHA-256 signature", async () => {
  const base = { frameId: "main", url: "https://example.test", controls: [
    { tag: "input", attrs: { type: "email", name: "email", value: "first@example.test" }, value: "first@example.test" },
  ] };
  const captured = await stateFor([base]);
  const changed = await stateFor([{ ...base, controls: [{ ...base.controls[0], value: "second@example.test", attrs: { ...base.controls[0].attrs, value: "second@example.test" } }] }]);

  assert.equal(visualStateGuard.sameVisualState(captured, changed), true);
  assert.match(captured, /^[0-9a-f]{64}$/);
  assert.doesNotMatch(captured, /first|second|example/);
});

test("fails closed for missing snapshots and snapshots above the size limit", async () => {
  assert.equal(await visualStateGuard.signatureFromSnapshot({ strings: [], documents: [] }, {}, webcrypto), "");
  assert.equal(visualStateGuard.sameVisualState("captured", ""), false);
  const missingStyles = makeSnapshot([{ frameId: "main", url: "https://example.test", controls: [
    { tag: "button", text: "Abrir" },
  ] }]);
  missingStyles.documents[0].layout.styles = [];
  assert.equal(await visualStateGuard.signatureFromSnapshot(missingStyles, {}, webcrypto), "");
  const oversized = makeSnapshot([{ frameId: "main", url: "https://example.test", controls: [] }]);
  oversized.documents[0].nodes.nodeName = new Array(30001).fill(0);
  oversized.documents[0].nodes.parentIndex = new Array(30001).fill(-1);
  assert.equal(await visualStateGuard.signatureFromSnapshot(oversized, {}, webcrypto), "");
});

test("service worker refuses dispatch when native toggle state changes after capture", async () => {
  const viewport = { width: 800, height: 600, dpr: 1 };
  const storedState = await stateFor([{ frameId: "main", url: "https://example.test", controls: [
    { tag: "input", attrs: { type: "checkbox", id: "subscribe", "aria-checked": "false" }, checked: false },
  ] }], viewport);
  const changedSnapshot = makeSnapshot([{ frameId: "main", url: "https://example.test", controls: [
    { tag: "input", attrs: { type: "checkbox", id: "subscribe", "aria-checked": "true" }, checked: true },
  ] }]);
  const issuedCommands = [];
  const event = { addListener() {} };
  const tab = { id: 9, title: "Example", url: "https://example.test", active: false, windowId: 1 };
  const stored = {
    screenshot_id: "shot-1", tab_id: 9, captured_at: Date.now(), width: 800, height: 600,
    css_width: 800, css_height: 600, dpr: 1, scale_x: 1, scale_y: 1,
    url: tab.url, loader_id: "loader-1", scroll_x: 0, scroll_y: 0,
    visual_state: storedState, visual_state_complete: true,
  };
  const storedSnapshots = { "shot-1": stored };
  const chrome = {
    runtime: {
      onStartup: event, onInstalled: event, onMessage: event, id: "test-extension",
      connectNative() { return { onMessage: event, onDisconnect: event, postMessage() {} }; },
    },
    alarms: { onAlarm: event, create() {} },
    action: { onClicked: event },
    storage: { session: { async get(key) { return { [key]: key === "visuals:9" ? storedSnapshots : undefined }; }, async set() {} } },
    tabs: { async get() { return tab; } },
    debugger: {
      async sendCommand(_target, method) {
        issuedCommands.push(method);
        if (method === "Page.getFrameTree") return { frameTree: { frame: { id: "main-frame", loaderId: "loader-1" } } };
        if (method === "Runtime.evaluate") return { result: { value: { url: tab.url, scroll_x: 0, scroll_y: 0, css_width: 800, css_height: 600, dpr: 1 } } };
        if (method === "DOMSnapshot.captureSnapshot") return changedSnapshot;
        return {};
      },
    },
  };
  const guard = {
    ...visualStateGuard,
    signatureFromSnapshot(snapshot, metrics) { return visualStateGuard.signatureFromSnapshot(snapshot, metrics, webcrypto); },
  };
  const context = vm.createContext({
    chrome,
    crypto: webcrypto,
    visualStateGuard: guard,
    fieldPolicy: {},
    importScripts() {},
    console,
    setTimeout,
    clearTimeout,
  });
  vm.runInContext(fs.readFileSync("browser_extension/service_worker.js", "utf8"), context);

  await assert.rejects(
    vm.runInContext("clickAt(9, { screenshot_id: 'shot-1', x: 50, y: 36 })", context),
    /page_changed_since_screenshot/
  );
  assert.ok(issuedCommands.includes("DOMSnapshot.captureSnapshot"));
  assert.equal(issuedCommands.some(method => method === "Input.dispatchMouseEvent"), false);
});

test("service worker allows a changed page only when the requested target remains under the screenshot point", async () => {
  const viewport = { width: 800, height: 600, dpr: 1 };
  const capturedModels = [{ frameId: "main", url: "https://example.test", controls: [
    { tag: "input", attrs: { type: "checkbox", id: "subscribe", "aria-checked": "false" }, checked: false, bounds: [10, 20, 100, 32] },
    { tag: "a", text: "Minha Conta", attrs: { href: "/account" }, bounds: [10, 120, 160, 36] },
  ] }];
  const storedState = await stateFor(capturedModels, viewport);
  const changedSnapshot = makeSnapshot([{ frameId: "main", url: "https://example.test", controls: [
    { tag: "input", attrs: { type: "checkbox", id: "subscribe", "aria-checked": "true" }, checked: true, bounds: [10, 20, 100, 32] },
    { tag: "a", text: "Minha Conta", attrs: { href: "/account" }, bounds: [10, 120, 160, 36] },
  ] }]);
  const issuedCommands = [];
  const event = { addListener() {} };
  const tab = { id: 9, title: "Example", url: "https://example.test", active: false, windowId: 1 };
  const stored = {
    screenshot_id: "shot-2", tab_id: 9, captured_at: Date.now(), width: 800, height: 600,
    css_width: 800, css_height: 600, dpr: 1, scale_x: 1, scale_y: 1,
    url: tab.url, loader_id: "loader-2", scroll_x: 0, scroll_y: 0,
    visual_state: storedState, visual_state_complete: true,
  };
  const storedSnapshots = {
    "shot-2": stored,
    "shot-new": { ...stored, screenshot_id: "shot-new", captured_at: Date.now() },
  };
  const chrome = {
    runtime: {
      onStartup: event, onInstalled: event, onMessage: event, id: "test-extension",
      connectNative() { return { onMessage: event, onDisconnect: event, postMessage() {} }; },
    },
    alarms: { onAlarm: event, create() {} },
    action: { onClicked: event },
    storage: { session: { async get(key) { return { [key]: key === "visuals:9" ? storedSnapshots : undefined }; }, async set() {} } },
    tabs: { async get() { return tab; } },
    debugger: {
      async sendCommand(_target, method, params = {}) {
        issuedCommands.push(method);
        if (method === "Page.getFrameTree") return { frameTree: { frame: { id: "main-frame", loaderId: "loader-2" } } };
        if (method === "Runtime.evaluate") {
          if (String(params.expression || "").includes("scroll_x")) {
            return { result: { value: { url: tab.url, scroll_x: 0, scroll_y: 0, css_width: 800, css_height: 600, dpr: 1 } } };
          }
          return { result: { value: { tag: "A", label: "Minha Conta", aria: "", attributes: ["href", "/account"] } } };
        }
        if (method === "DOMSnapshot.captureSnapshot") return changedSnapshot;
        return {};
      },
    },
  };
  const guard = {
    ...visualStateGuard,
    signatureFromSnapshot(snapshot, metrics) { return visualStateGuard.signatureFromSnapshot(snapshot, metrics, webcrypto); },
  };
  const context = vm.createContext({
    chrome,
    crypto: webcrypto,
    visualStateGuard: guard,
    fieldPolicy: {},
    importScripts() {},
    console,
    setTimeout,
    clearTimeout,
  });
  vm.runInContext(fs.readFileSync("browser_extension/service_worker.js", "utf8"), context);

  await assert.rejects(
    vm.runInContext("clickAt(9, { screenshot_id: 'shot-2', x: 50, y: 138, expected_label: 'Outro controle' })", context),
    /page_changed_since_screenshot/
  );
  assert.equal(issuedCommands.some(method => method === "Input.dispatchMouseEvent"), false);

  const result = await vm.runInContext(
    "clickAt(9, { screenshot_id: 'shot-2', x: 50, y: 138, expected_label: 'Minha Conta' })",
    context,
  );
  assert.equal(result.clicked, true);
  assert.ok(issuedCommands.includes("Input.dispatchMouseEvent"));

  stored.visual_state_complete = false;
  stored.visual_state = "";
  await assert.rejects(
    vm.runInContext("clickAt(9, { screenshot_id: 'shot-2', x: 50, y: 138, expected_label: 'Outro controle' })", context),
    /visual_state_unavailable/
  );
  const unstableCaptureResult = await vm.runInContext(
    "clickAt(9, { screenshot_id: 'shot-2', x: 50, y: 138, expected_label: 'Minha Conta' })",
    context,
  );
  assert.equal(unstableCaptureResult.clicked, true);

  const unlabeledTargetResult = await vm.runInContext(
    "clickAt(9, { screenshot_id: 'shot-2', x: 50, y: 138, expected_label: '' })",
    context,
  );
  assert.equal(unlabeledTargetResult.clicked, true);
});

test("service worker permits a placeholder-labelled editable target after unrelated page changes", async () => {
  const viewport = { width: 800, height: 600, dpr: 1 };
  const capturedModels = [{ frameId: "main", url: "https://example.test", controls: [
    { tag: "div", attrs: { role: "textbox", contenteditable: "true", "data-placeholder": "Mensagem para DeepSeek" }, bounds: [10, 320, 700, 48] },
  ] }];
  const storedState = await stateFor(capturedModels, viewport);
  const changedSnapshot = makeSnapshot([{ frameId: "main", url: "https://example.test", controls: [
    { tag: "input", attrs: { type: "checkbox", id: "subscribe", "aria-checked": "true" }, checked: true, bounds: [10, 20, 100, 32] },
    { tag: "div", attrs: { role: "textbox", contenteditable: "true", "data-placeholder": "Mensagem para DeepSeek" }, bounds: [10, 320, 700, 48] },
  ] }]);

  const event = { addListener() {} };
  const tab = { id: 9, title: "Example", url: "https://example.test", active: false, windowId: 1 };
  const stored = {
    screenshot_id: "shot-drift", tab_id: 9, captured_at: Date.now(), width: 800, height: 600,
    css_width: 800, css_height: 600, dpr: 1, scale_x: 1, scale_y: 1,
    url: tab.url, loader_id: "loader-drift", scroll_x: 0, scroll_y: 0,
    visual_state: storedState, visual_state_complete: true,
  };
  const chrome = {
    runtime: {
      onStartup: event, onInstalled: event, onMessage: event, id: "test-extension",
      connectNative() { return { onMessage: event, onDisconnect: event, postMessage() {} }; },
    },
    alarms: { onAlarm: event, create() {} },
    action: { onClicked: event },
    storage: { session: { async get(key) { return { [key]: key === "visuals:9" ? { "shot-drift": stored } : undefined }; }, async set() {} } },
    tabs: { async get() { return tab; } },
    debugger: {
      async sendCommand(_target, method, params = {}) {
        if (method === "Page.getFrameTree") return { frameTree: { frame: { id: "main-frame", loaderId: "loader-drift" } } };
        if (method === "Runtime.evaluate") {
          if (String(params.expression || "").includes("scroll_x")) {
            return { result: { value: { url: tab.url, scroll_x: 0, scroll_y: 0, css_width: 800, css_height: 600, dpr: 1 } } };
          }
          assert.doesNotThrow(() => new Function("return " + params.expression));
          return { result: { value: { tag: "DIV", label: "", aria: "", placeholder: "Mensagem para DeepSeek", contenteditable: true, attributes: ["role", "textbox", "contenteditable", "true", "data-placeholder", "Mensagem para DeepSeek"] } } };
        }
        if (method === "DOMSnapshot.captureSnapshot") return changedSnapshot;
        return {};
      },
    },
  };

  const context = vm.createContext({
    chrome,
    crypto: webcrypto,
    visualStateGuard,
    fieldPolicy: {},
    importScripts() {},
    console,
    setTimeout,
    clearTimeout,
  });
  vm.runInContext(fs.readFileSync("browser_extension/service_worker.js", "utf8"), context);

  const result = await vm.runInContext(
    "clickAt(9, { screenshot_id: 'shot-drift', x: 50, y: 340, expected_label: 'Mensagem para DeepSeek' })",
    context,
  );
  assert.equal(result.clicked, true);
});
