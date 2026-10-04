importScripts("field_policy.js", "visual_state_guard.js");

const HOST = "com.agente_pessoal.browser";
const PROTOCOL = 1;
const MAX_TEXT = 12000;
const VISUAL_SNAPSHOT_TTL_MS = 120000;
const MAX_VISUAL_SNAPSHOTS_PER_TAB = 8;
const ELEMENT_REF_TTL_MS = 120000;
const MAX_ELEMENT_REFS_PER_TAB = 256;
const RECONNECT_ALARM = "bridge-reconnect";
const RECONNECT_DELAYS_MINUTES = [0.5, 0.5, 1, 1];
let nativePort = null;
let reconnecting = false;
let bridgeConnected = false;
let connectionError = "";
let reconnectAttempts = 0;
const confirmations = new Map();

function setConnectionState(connected, error = "") {
  bridgeConnected = connected;
  connectionError = error;
  chrome.storage.session.set({ bridgeConnected, bridgeConnectionError: connectionError });
}

function connectionStatus() {
  return {
    connected: bridgeConnected,
    state: bridgeConnected ? "connected" : nativePort ? "connecting" : "disconnected",
    error: connectionError,
  };
}

function scheduleReconnect() {
  const index = Math.min(reconnectAttempts, RECONNECT_DELAYS_MINUTES.length - 1);
  chrome.alarms.create(RECONNECT_ALARM, { delayInMinutes: RECONNECT_DELAYS_MINUTES[index] });
  reconnectAttempts = Math.min(reconnectAttempts + 1, RECONNECT_DELAYS_MINUTES.length - 1);
}

function connectNative() {
  if (nativePort || reconnecting) return Boolean(nativePort);
  reconnecting = true;
  setConnectionState(false);
  try {
    const port = chrome.runtime.connectNative(HOST);
    nativePort = port;
    port.onMessage.addListener((message) => {
      if (message?.type === "ready") {
        if (nativePort !== port) return;
        reconnectAttempts = 0;
        setConnectionState(true);
        chrome.alarms.clear(RECONNECT_ALARM);
        return;
      }
      if (message?.type !== "request" || message.version !== PROTOCOL) return;
      if (!bridgeConnected) return;
      handleRequest(message).then((response) => {
        if (nativePort === port) port.postMessage(response);
      }).catch((error) => {
        if (nativePort === port) port.postMessage(failure(message, "browser_exception:" + String(error?.message || error)));
      });
    });
    port.onDisconnect.addListener(() => {
      if (nativePort === port) {
        nativePort = null;
        const error = chrome.runtime.lastError?.message || "Native Host desconectado.";
        setConnectionState(false, error);
        scheduleReconnect();
      }
      reconnecting = false;
    });
    reconnecting = false;
    return true;
  } catch (error) {
    reconnecting = false;
    nativePort = null;
    setConnectionState(false, String(error?.message || error));
    scheduleReconnect();
    return false;
  }
}

function startBridge() {
  chrome.alarms.create(RECONNECT_ALARM, { delayInMinutes: 0.5 });
  connectNative();
}

chrome.runtime.onStartup.addListener(startBridge);
chrome.runtime.onInstalled.addListener(startBridge);
chrome.alarms.onAlarm.addListener((alarm) => {
  if (alarm.name === RECONNECT_ALARM && !nativePort) connectNative();
});
chrome.action.onClicked.addListener(() => connectNative());
chrome.runtime.onMessage.addListener((message, _sender, sendResponse) => {
  if (message?.type === "bridge-status") {
    sendResponse({ ...connectionStatus(), extensionId: chrome.runtime.id });
    return false;
  }
  if (message?.type === "bridge-reconnect") {
    connectNative();
    sendResponse({ ...connectionStatus(), extensionId: chrome.runtime.id });
    return false;
  }
  return false;
});
startBridge();

function failure(request, errorCode, retryHint = "browser_list_tabs") {
  return { type: "response", request_id: request.request_id, status: "failure", operation: request.operation, tab: {}, before: {}, after: {}, observation: "", error_code: errorCode, retry_hint: retryHint, data: null };
}
function safeUrl(url) { return typeof url === "string" && /^https?:\/\//i.test(url); }
function shortTab(tab) { return { id: tab.id, title: String(tab.title || "").slice(0, 250), url: String(tab.url || "").slice(0, 1500), active: Boolean(tab.active), window_id: tab.windowId }; }
async function tabFor(id) {
  if (!Number.isInteger(Number(id))) throw new Error("tab_id_required");
  const tab = await chrome.tabs.get(Number(id));
  if (!tab || tab.id == null || !safeUrl(tab.url || "")) throw new Error("unsupported_page");
  return tab;
}
async function attach(tabId) {
  await chrome.debugger.attach({ tabId }, "1.3");
  for (const [method, params] of [["Page.enable", {}], ["Runtime.enable", {}], ["DOM.enable", {}], ["Accessibility.enable", {}]]) {
    try { await chrome.debugger.sendCommand({ tabId }, method, params); } catch (_) {}
  }
}
async function detach(tabId) { try { await chrome.debugger.detach({ tabId }); } catch (_) {} }
async function cdp(tabId, method, params = {}) { return chrome.debugger.sendCommand({ tabId }, method, params); }
async function pageState(tabId) {
  const tab = await chrome.tabs.get(tabId);
  let text = "";
  try {
    const out = await cdp(tabId, "Runtime.evaluate", { expression: "document.body ? document.body.innerText.slice(0," + MAX_TEXT + ") : ''", returnByValue: true, awaitPromise: true });
    text = out?.result?.value || "";
  } catch (_) {}
  return { url: tab.url || "", title: tab.title || "", text };
}
async function currentFrame(tabId) {
  const out = await cdp(tabId, "Page.getFrameTree");
  return out?.frameTree?.frame || {};
}
function valueOf(item) { return item && typeof item === "object" && "value" in item ? item.value : ""; }
function normalizeRole(role) { return String(valueOf(role) || "").toLowerCase(); }
function normalizeName(name) { return String(valueOf(name) || "").replace(/\s+/g, " ").trim().slice(0, 200); }
const INTERACTIVE = new Set(["link", "button", "textbox", "searchbox", "combobox", "checkbox", "radio", "switch", "option", "menuitem", "tab"]);
async function inspectTab(tabId, maxChars = MAX_TEXT) {
  const before = await pageState(tabId);
  const frame = await currentFrame(tabId);
  const tree = await cdp(tabId, "Accessibility.getFullAXTree", { frameId: frame.id });
  const loaderId = frame.loaderId || "";
  const refsKey = "refs:" + tabId;
  const previous = (await chrome.storage.session.get(refsKey))[refsKey];
  const refs = previous?.url === before.url && previous?.loader_id === loaderId
    ? { ...(previous.refs || {}) }
    : {};
  const elements = [];
  const candidates = (tree.nodes || []).filter((node) => {
    return INTERACTIVE.has(normalizeRole(node.role)) && node.backendDOMNodeId;
  });
  const priority = (node) => {
    const role = normalizeRole(node.role);
    if (["textbox", "searchbox", "combobox"].includes(role)) return 0;
    if (normalizeName(node.name)) return 1;
    return 2;
  };
  candidates.sort((left, right) => priority(left) - priority(right));
  for (const node of candidates.slice(0, 80)) {
    const role = normalizeRole(node.role);
    const name = normalizeName(node.name);
    const backendId = node.backendDOMNodeId;
    if (!INTERACTIVE.has(role) || !backendId || elements.length >= 80) continue;
    let details = {};
    try {
      const described = await cdp(tabId, "DOM.describeNode", { backendNodeId: backendId, depth: 0, pierce: true });
      const attrs = described?.node?.attributes || [];
      for (let i = 0; i < attrs.length; i += 2) details[attrs[i]] = attrs[i + 1];
    } catch (_) {}
    const elementRef = crypto.randomUUID();
    refs[elementRef] = { backendId, frameId: node.frameId || frame.id, role, name, tag: node.htmlTag || "", type: details.type || "", href: details.href || "", action: details.formaction || "", formMethod: details.formmethod || "", placeholder: details.placeholder || "", ariaLabel: details["aria-label"] || "", captured_at: Date.now() };
    elements.push({ element_ref: elementRef, role, name, tag: refs[elementRef].tag, type: refs[elementRef].type, placeholder: refs[elementRef].placeholder, href: refs[elementRef].href, disabled: Boolean(valueOf(node.properties?.find(p => p.name === "disabled")?.value)) });
  }
  const retainedRefs = Object.entries(refs)
    .filter(([, ref]) => ref && Date.now() - ref.captured_at <= ELEMENT_REF_TTL_MS)
    .sort((left, right) => left[1].captured_at - right[1].captured_at)
    .slice(-MAX_ELEMENT_REFS_PER_TAB);
  await chrome.storage.session.set({ [refsKey]: { url: before.url, loader_id: loaderId, refs: Object.fromEntries(retainedRefs) } });
  return { before, data: { url: before.url, title: before.title, text: before.text.slice(0, Math.max(500, Math.min(Number(maxChars) || MAX_TEXT, MAX_TEXT))), elements } };
}
async function getRef(tabId, ref) {
  const key = "refs:" + tabId;
  const state = (await chrome.storage.session.get(key))[key];
  const element = state?.refs?.[ref];
  if (!element || Date.now() - element.captured_at > ELEMENT_REF_TTL_MS) throw new Error("stale_element_reference");
  const tab = await chrome.tabs.get(tabId);
  if (tab.url !== state.url) throw new Error("stale_element_reference");
  const frame = await currentFrame(tabId);
  if ((frame.loaderId || "") !== state.loader_id) throw new Error("stale_element_reference");
  return element;
}
function attributesFromNode(node) {
  const attrs = {};
  for (let i = 0; i < (node.attributes || []).length; i += 2) attrs[node.attributes[i].toLowerCase()] = node.attributes[i + 1];
  return attrs;
}
async function rebindElementRef(tabId, ref) {
  const tree = await cdp(tabId, "Accessibility.getFullAXTree", { frameId: ref.frameId });
  const expectedRole = String(ref.role || "").toLowerCase();
  const expectedName = String(ref.name || "").replace(/\s+/g, " ").trim().toLowerCase();
  const hasStableIdentity = Boolean(expectedName || ref.ariaLabel || ref.placeholder || ref.href || ref.type);
  if (!hasStableIdentity) return null;

  const matches = [];
  for (const candidate of tree.nodes || []) {
    if (!candidate.backendDOMNodeId || normalizeRole(candidate.role) !== expectedRole) continue;
    const candidateName = normalizeName(candidate.name).toLowerCase();
    if (expectedName && candidateName !== expectedName) continue;
    if (candidate.frameId && candidate.frameId !== ref.frameId) continue;
    let described;
    try {
      described = await cdp(tabId, "DOM.describeNode", { backendNodeId: candidate.backendDOMNodeId, depth: 0, pierce: true });
    } catch (_) {
      continue;
    }
    const attrs = attributesFromNode(described?.node || {});
    if (ref.ariaLabel && attrs["aria-label"] !== ref.ariaLabel) continue;
    if (ref.placeholder && attrs.placeholder !== ref.placeholder) continue;
    if (ref.href && attrs.href !== ref.href) continue;
    if (ref.type && attrs.type !== ref.type) continue;
    matches.push({ backendId: candidate.backendDOMNodeId, node: described?.node });
  }
  if (matches.length === 1) return matches[0];
  return matches.find(match => match.backendId === ref.backendId) || null;
}
async function nodeDescription(tabId, ref) {
  try {
    const out = await cdp(tabId, "DOM.describeNode", { backendNodeId: ref.backendId, depth: 1, pierce: true });
    // DOM.describeNode não rastreia nós (nodeId volta sempre 0) e ainda devolve
    // nós JÁ REMOVIDOS do documento, sem lançar. A prova de vida é isConnected no
    // objeto resolvido: sem ela, fill/click escreveriam num nó morto e reportariam
    // sucesso sem tocar a página.
    if (out?.node) {
      const object = await cdp(tabId, "DOM.resolveNode", { backendNodeId: ref.backendId });
      if (object?.object?.objectId) {
        const alive = await cdp(tabId, "Runtime.callFunctionOn", { objectId: object.object.objectId, functionDeclaration: "function(){return this.isConnected===true;}", returnByValue: true });
        if (alive?.result?.value === true) return out.node;
      }
    }
  } catch (_) {}
  const rebound = await rebindElementRef(tabId, ref);
  if (!rebound?.node) throw new Error("stale_element_reference");
  ref.backendId = rebound.backendId;
  return rebound.node;
}
function riskyElement(ref, node) {
  const attrs = {};
  for (let i = 0; i < (node.attributes || []).length; i += 2) attrs[node.attributes[i].toLowerCase()] = node.attributes[i + 1];
  const label = (ref.name + " " + ref.ariaLabel + " " + (node.nodeValue || "")).toLowerCase();
  const form = node.attributes?.includes("form") || node.nodeName === "BUTTON";
  const riskyWords = /\b(send|submit|publish|pay|buy|purchase|delete|remove|confirm|place order|enviar|publicar|pagar|comprar|excluir|remover|confirmar|finalizar)\b/i.test(label);
  const searchForm = /search|buscar|pesquisar|query|consulta/i.test(label) || /search/i.test(attrs.type || "");
  return !searchForm && (String(attrs.type || "").toLowerCase() === "submit" || riskyWords || (form && String(attrs.type || "").toLowerCase() === "submit"));
}
async function clickRef(tabId, ref, confirmationToken = "", elementRef = "") {
  const node = await nodeDescription(tabId, ref);
  const token = confirmationToken && confirmations.get(confirmationToken);
  if (token && token.expires <= Date.now()) confirmations.delete(confirmationToken);
  // A comparacao e' pelo element_ref (texto), nao pelo objeto: cada requisicao
  // le as referencias do chrome.storage.session e recebe um objeto NOVO, entao
  // "token.ref !== ref" era sempre verdadeiro e a confirmacao nunca valia.
  if (riskyElement(ref, node) && (!token || token.expires <= Date.now() || token.tabId !== tabId || !elementRef || token.elementRef !== elementRef)) {
    const id = crypto.randomUUID();
    confirmations.set(id, { tabId, elementRef, expires: Date.now() + 60000 });
    return { confirmation_required: true, confirmation_token: id, label: ref.name || ref.ariaLabel || ref.tag || "ação" };
  }
  if (confirmationToken) confirmations.delete(confirmationToken);
  const model = await cdp(tabId, "DOM.getBoxModel", { backendNodeId: ref.backendId });
  const quad = model?.model?.content || [];
  if (quad.length < 8) throw new Error("element_not_visible");
  const xs = [quad[0], quad[2], quad[4], quad[6]], ys = [quad[1], quad[3], quad[5], quad[7]];
  const x = xs.reduce((a, b) => a + b, 0) / 4, y = ys.reduce((a, b) => a + b, 0) / 4;
  await cdp(tabId, "Input.dispatchMouseEvent", { type: "mousePressed", x, y, button: "left", clickCount: 1 });
  await cdp(tabId, "Input.dispatchMouseEvent", { type: "mouseReleased", x, y, button: "left", clickCount: 1 });
  return { clicked: true };
}
async function fillRef(tabId, ref, value, isSelect = false) {
  const node = await nodeDescription(tabId, ref);
  const attributes = {};
  for (let i = 0; i < (node.attributes || []).length; i += 2) attributes[node.attributes[i].toLowerCase()] = node.attributes[i + 1];
  if (!isSelect && isPasswordField({ nodeName: node.nodeName, type: attributes.type, autocomplete: attributes.autocomplete })) {
    throw new Error("password_field_blocked");
  }
  const object = await cdp(tabId, "DOM.resolveNode", { backendNodeId: ref.backendId });
  if (!object?.object?.objectId) throw new Error("stale_element_reference");
  const passwordGuard = "if((" + isPasswordField.toString() + ")(this)) throw new Error('password_field_blocked');";
  const fn = isSelect
    ? "function(v){ if(this.tagName!=='SELECT') throw new Error('not_a_select'); const setter=Object.getOwnPropertyDescriptor(HTMLSelectElement.prototype,'value')?.set; if(!setter) throw new Error('not_selectable'); setter.call(this,v); this.dispatchEvent(new Event('input',{bubbles:true})); this.dispatchEvent(new Event('change',{bubbles:true})); return this.value===v; }"
    : "function(v){ " + passwordGuard + " if(!(['INPUT','TEXTAREA'].includes(this.tagName)||this.isContentEditable)) throw new Error('not_fillable'); this.focus(); if(this.isContentEditable){ const r=document.createRange(); r.selectNodeContents(this); const s=getSelection(); s.removeAllRanges(); s.addRange(r); document.execCommand('insertText',false,v); } else {const proto=this.tagName==='TEXTAREA'?HTMLTextAreaElement.prototype:HTMLInputElement.prototype; const setter=Object.getOwnPropertyDescriptor(proto,'value')?.set; if(!setter) throw new Error('not_fillable'); setter.call(this,v);} this.dispatchEvent(new Event('input',{bubbles:true})); this.dispatchEvent(new Event('change',{bubbles:true})); return this.isContentEditable ? this.textContent.includes(v) : this.value===v; }";
  const result = await cdp(tabId, "Runtime.callFunctionOn", { objectId: object.object.objectId, functionDeclaration: fn, arguments: [{ value: String(value || "") }], returnByValue: true, awaitPromise: true });
  const exception = result?.exceptionDetails?.exception?.description || result?.exceptionDetails?.text || "";
  if (exception.includes("password_field_blocked")) throw new Error("password_field_blocked");
  if (result?.exceptionDetails || result?.result?.value !== true) throw new Error("fill_not_verified");
  return { filled: true, value_length: String(value || "").length };
}
async function pressKey(tabId, key, allowSubmit = false) {
  // allowSubmit vem do app quando o usuario desligou a confirmacao de acoes
  // arriscadas; sem isso o Enter num formulario com botao "Enviar" seria
  // recusado mesmo com o usuario tendo pedido para nao confirmar.
  if (key === "Enter" && !allowSubmit) {
    const active = await cdp(tabId, "Runtime.evaluate", { expression: "(()=>{const e=document.activeElement;const f=e&&e.form;const b=f&&f.querySelector('button[type=submit],input[type=submit]');return b?{type:b.type,label:(b.innerText||b.value||b.getAttribute('aria-label')||'').slice(0,100)}:null})()", returnByValue: true });
    const submit = active?.result?.value;
    if (submit && /\b(send|submit|publish|pay|buy|purchase|delete|remove|confirm|order|enviar|publicar|pagar|comprar|excluir|remover|confirmar|finalizar)\b/i.test(submit.label || "")) throw new Error("submit_requires_button_confirmation");
  }
  const KEYS = {
    Enter:{code:"Enter",vk:13,text:"\r"}, Tab:{code:"Tab",vk:9}, Escape:{code:"Escape",vk:27},
    Backspace:{code:"Backspace",vk:8}, Delete:{code:"Delete",vk:46},
    ArrowDown:{code:"ArrowDown",vk:40}, ArrowUp:{code:"ArrowUp",vk:38},
    ArrowLeft:{code:"ArrowLeft",vk:37}, ArrowRight:{code:"ArrowRight",vk:39},
    Home:{code:"Home",vk:36}, End:{code:"End",vk:35}, PageDown:{code:"PageDown",vk:34}, PageUp:{code:"PageUp",vk:33}
  };
  const k = KEYS[key];
  if (!k) throw new Error("unsupported_key");
  const base = { key, code:k.code, windowsVirtualKeyCode:k.vk, nativeVirtualKeyCode:k.vk };
  await cdp(tabId, "Input.dispatchKeyEvent", { ...base, type: k.text ? "keyDown" : "rawKeyDown", text: k.text });
  await cdp(tabId, "Input.dispatchKeyEvent", { ...base, type: "keyUp" });
  return { key };
}
async function waitFor(tabId, args) {
  const deadline = Date.now() + Math.max(500, Math.min(Number(args.timeout) * 1000 || 10000, 20000));
  let state;
  while (Date.now() < deadline) {
    state = await pageState(tabId);
    if ((!args.text || state.text.toLowerCase().includes(String(args.text).toLowerCase())) && (!args.url_contains || state.url.includes(args.url_contains))) return state;
    await new Promise(resolve => setTimeout(resolve, 200));
  }
  throw new Error("wait_condition_timeout");
}
async function back(tabId) {
  const history = await cdp(tabId, "Page.getNavigationHistory");
  const current = history.entries?.findIndex(entry => entry.id === history.currentIndex);
  const index = history.currentIndex;
  if (!Number.isInteger(index) || index <= 0) throw new Error("no_previous_page");
  await cdp(tabId, "Page.navigateToHistoryEntry", { entryId: history.entries[index - 1].id });
  await new Promise(resolve => setTimeout(resolve, 250));
  return pageState(tabId);
}
async function visualPageMetrics(tabId) {
  const tab = await chrome.tabs.get(tabId);
  const frame = await currentFrame(tabId);
  const evaluated = await cdp(tabId, "Runtime.evaluate", {
    expression: "(()=>({url:location.href,scroll_x:scrollX,scroll_y:scrollY,css_width:innerWidth,css_height:innerHeight,dpr:devicePixelRatio||1}))()",
    returnByValue: true
  });
  const metrics = evaluated?.result?.value;
  if (!metrics || !Number.isFinite(metrics.css_width) || !Number.isFinite(metrics.css_height)) throw new Error("visual_metrics_unavailable");
  return { tab, frame, metrics };
}
async function visualStateSignature(tabId, metrics = {}) {
  try {
    const snapshot = await cdp(tabId, "DOMSnapshot.captureSnapshot", {
      computedStyles: ["display", "visibility", "opacity", "pointer-events", "cursor", "z-index"],
      includePaintOrder: false,
      includeDOMRects: false
    });
    return await visualStateGuard.signatureFromSnapshot(snapshot, {
      width: metrics.css_width,
      height: metrics.css_height,
      scrollX: metrics.scroll_x,
      scrollY: metrics.scroll_y,
      dpr: metrics.dpr
    });
  } catch (_) {
    return "";
  }
}
async function storeVisualSnapshot(tabId, snapshot) {
  const key = "visuals:" + tabId;
  const now = Date.now();
  const existing = (await chrome.storage.session.get(key))[key] || {};
  const recent = Object.entries(existing).filter(([, item]) =>
    item && item.tab_id === tabId && now - item.captured_at <= VISUAL_SNAPSHOT_TTL_MS
  );
  recent.push([snapshot.screenshot_id, snapshot]);
  recent.sort((left, right) => left[1].captured_at - right[1].captured_at);
  while (recent.length > MAX_VISUAL_SNAPSHOTS_PER_TAB) recent.shift();
  await chrome.storage.session.set({ [key]: Object.fromEntries(recent) });
}
async function getVisualSnapshot(tabId, screenshotId) {
  const key = "visuals:" + tabId;
  const snapshots = (await chrome.storage.session.get(key))[key] || {};
  const stored = snapshots[screenshotId];
  if (!stored || stored.tab_id !== tabId || stored.screenshot_id !== screenshotId
    || Date.now() - stored.captured_at > VISUAL_SNAPSHOT_TTL_MS) return null;
  return stored;
}
function jpegDimensions(base64) {
  let bytes;
  try { bytes = atob(base64 || ""); } catch (_) { return null; }
  const frameMarkers = new Set([0xc0, 0xc1, 0xc2, 0xc3, 0xc5, 0xc6, 0xc7, 0xc9, 0xca, 0xcb, 0xcd, 0xce, 0xcf]);
  let offset = 2;
  while (offset + 9 < bytes.length) {
    if (bytes.charCodeAt(offset) !== 0xff) { offset++; continue; }
    while (bytes.charCodeAt(offset) === 0xff) offset++;
    const marker = bytes.charCodeAt(offset++);
    if (marker === 0xd8 || marker === 0xd9 || (marker >= 0xd0 && marker <= 0xd7)) continue;
    if (offset + 1 >= bytes.length) return null;
    const length = (bytes.charCodeAt(offset) << 8) | bytes.charCodeAt(offset + 1);
    if (frameMarkers.has(marker) && offset + 7 < bytes.length) {
      return { width: (bytes.charCodeAt(offset + 5) << 8) | bytes.charCodeAt(offset + 6), height: (bytes.charCodeAt(offset + 3) << 8) | bytes.charCodeAt(offset + 4) };
    }
    if (length < 2) return null;
    offset += length;
  }
  return null;
}
async function screenshot(tabId) {
  const visual = await visualPageMetrics(tabId);
  const stateBeforeCapture = await visualStateSignature(tabId, visual.metrics);
  let shot, quality = 65;
  for (; quality >= 30; quality -= 15) {
    shot = await cdp(tabId, "Page.captureScreenshot", { format: "jpeg", quality, fromSurface: true, captureBeyondViewport: false });
    if ((shot.data || "").length <= 700000) break;
  }
  const stateAfterCapture = await visualStateSignature(tabId, visual.metrics);
  const visualStateComplete = visualStateGuard.sameVisualState(stateBeforeCapture, stateAfterCapture);
  if ((shot.data || "").length > 700000) throw new Error("screenshot_too_large");
  const screenshotId = crypto.randomUUID();
  const dpr = Math.max(0.5, Math.min(Number(visual.metrics.dpr) || 1, 4));
  const jpegSize = jpegDimensions(shot.data);
  const width = jpegSize?.width || Math.round(visual.metrics.css_width * dpr);
  const height = jpegSize?.height || Math.round(visual.metrics.css_height * dpr);
  const snapshot = {
    screenshot_id: screenshotId,
    tab_id: tabId,
    url: visual.tab.url || visual.metrics.url || "",
    loader_id: visual.frame.loaderId || "",
    scroll_x: visual.metrics.scroll_x,
    scroll_y: visual.metrics.scroll_y,
    css_width: visual.metrics.css_width,
    css_height: visual.metrics.css_height,
    dpr,
    scale_x: width / visual.metrics.css_width,
    scale_y: height / visual.metrics.css_height,
    width,
    height,
    captured_at: Date.now(),
    visual_state: visualStateComplete ? stateAfterCapture : "",
    visual_state_complete: visualStateComplete
  };
  await storeVisualSnapshot(tabId, snapshot);
  return {
    type: "image",
    mime_type: "image/jpeg",
    data: shot.data,
    screenshot_id: screenshotId,
    width,
    height,
    css_width: snapshot.css_width,
    css_height: snapshot.css_height,
    device_scale_factor: dpr,
    description: "Screenshot visual do Chrome."
  };
}
async function clickAt(tabId, args) {
  const x = Number(args.x), y = Number(args.y);
  if (!Number.isFinite(x) || !Number.isFinite(y)) throw new Error("invalid_coordinates");
  const stored = await getVisualSnapshot(tabId, args.screenshot_id);
  if (!stored) throw new Error("stale_screenshot");
  if (x < 0 || y < 0 || x >= stored.width || y >= stored.height) throw new Error("coordinates_out_of_bounds");
  const visual = await visualPageMetrics(tabId);
  const m = visual.metrics;
  const same = (visual.tab.url || m.url) === stored.url
    && (visual.frame.loaderId || "") === stored.loader_id
    && Math.abs(m.scroll_x - stored.scroll_x) < 1
    && Math.abs(m.scroll_y - stored.scroll_y) < 1
    && Math.abs(m.css_width - stored.css_width) < 1
    && Math.abs(m.css_height - stored.css_height) < 1
    && Math.abs((Number(m.dpr) || 1) - stored.dpr) < 0.02;
  if (!same) throw new Error("page_changed_since_screenshot");
  const visualStateAvailable = stored.visual_state_complete === true;
  const currentVisualState = visualStateAvailable ? await visualStateSignature(tabId, m) : "";
  const visualStateMatches = visualStateAvailable
    && visualStateGuard.sameVisualState(stored.visual_state, currentVisualState);
  const cssX = x / stored.scale_x, cssY = y / stored.scale_y;
  const expression = "(()=>{const e=document.elementFromPoint(" + cssX + "," + cssY + ");if(!e)return null;const selector='button,a,input,textarea,select,label,[role=button],[role=link],[role=textbox],[contenteditable=true],[contenteditable=\"\"]';let t=null,n=e;while(n){t=n.closest?.(selector)||null;if(t)break;const root=n.getRootNode?.();n=root?.host||null}t=t||e;const tag=(t.tagName||'').toUpperCase();const aria=t.getAttribute('aria-label')||'';const placeholder=t.getAttribute('placeholder')||t.getAttribute('data-placeholder')||t.getAttribute('data-lexical-placeholder')||'';const label=(aria||t.getAttribute('title')||placeholder||(['INPUT','TEXTAREA'].includes(tag)?'':(t.innerText||''))).trim().slice(0,200);return {tag,label,aria,placeholder,role:t.getAttribute('role')||'',contenteditable:Boolean(t.isContentEditable||t.getAttribute('contenteditable')==='true'||t.getAttribute('contenteditable')===''),attributes:Array.from(t.attributes||[]).flatMap(a=>[a.name,a.value])}})()";
  const evaluated = await cdp(tabId, "Runtime.evaluate", { expression, returnByValue: true });
  const target = evaluated?.result?.value;
  const ref = target ? { name: target.label || "", ariaLabel: target.aria || "", tag: target.tag || "" } : { name: "", ariaLabel: "", tag: "" };
  const node = target ? { nodeName: target.tag || "", nodeValue: target.label || "", attributes: target.attributes || [] } : {};
  const expectedLabel = String(args.expected_label || "").normalize("NFKC").replace(/\s+/g, " ").trim().toLowerCase();
  const actualLabel = String(ref.name || ref.ariaLabel || target?.placeholder || "").normalize("NFKC").replace(/\s+/g, " ").trim().toLowerCase();
  const placeholder = String(target?.placeholder || "").normalize("NFKC").replace(/\s+/g, " ").trim().toLowerCase();
  const expectedTargetStillPresent = Boolean(expectedLabel && (actualLabel === expectedLabel || placeholder === expectedLabel));
  const labelDriftStillMatches = Boolean(
    expectedLabel && actualLabel && (
      actualLabel.includes(expectedLabel)
      || expectedLabel.includes(actualLabel)
    )
  );
  const actualTag = String(target?.tag || "").toUpperCase();
  const editableTarget = Boolean(target?.contenteditable || String(target?.role || "").toLowerCase() === "textbox");
  const sameControlFamily = Boolean(
    target && actualTag && (["A", "BUTTON", "INPUT", "TEXTAREA", "SELECT", "LABEL"].includes(actualTag) || (actualTag === "DIV" && editableTarget))
      && (
        (!expectedLabel && (target.label || target.aria || target.attributes?.includes("href") || target.attributes?.includes("role")))
        || (expectedLabel && labelDriftStillMatches)
      )
  );
  const targetStillUnderPoint = Boolean(
    target && (
      expectedTargetStillPresent
      || labelDriftStillMatches
      || (!expectedLabel && (target.tag || target.label || target.aria))
      || sameControlFamily
    )
  );
  if (!visualStateMatches && !targetStillUnderPoint) {
    throw new Error(visualStateAvailable ? "page_changed_since_screenshot" : "visual_state_unavailable");
  }
  const confirmationToken = String(args.confirmation_token || "");
  const pending = confirmationToken && confirmations.get(confirmationToken);
  if (pending && pending.expires <= Date.now()) confirmations.delete(confirmationToken);
  const matches = pending && pending.visual === true && pending.expires > Date.now()
    && pending.tabId === tabId && pending.screenshotId === stored.screenshot_id
    && pending.x === x && pending.y === y;
  if (target && riskyElement(ref, node) && !matches) {
    const token = crypto.randomUUID();
    confirmations.set(token, { visual: true, tabId, screenshotId: stored.screenshot_id, x, y, expires: Date.now() + 60000 });
    return { confirmation_required: true, confirmation_token: token, label: ref.name || ref.ariaLabel || ref.tag || "ação visual" };
  }
  if (confirmationToken) confirmations.delete(confirmationToken);
  await cdp(tabId, "Input.dispatchMouseEvent", { type: "mouseMoved", x: cssX, y: cssY });
  await cdp(tabId, "Input.dispatchMouseEvent", { type: "mousePressed", x: cssX, y: cssY, button: "left", clickCount: 1 });
  await cdp(tabId, "Input.dispatchMouseEvent", { type: "mouseReleased", x: cssX, y: cssY, button: "left", clickCount: 1 });
  return { clicked: true, x, y, css_x: cssX, css_y: cssY, target: ref.name || ref.ariaLabel || ref.tag || "área da página" };
}
async function download(tabId, ref, confirmationToken = "", elementRef = "") {
  const node = await nodeDescription(tabId, ref);
  const attrs = {};
  for (let i = 0; i < (node.attributes || []).length; i += 2) attrs[node.attributes[i].toLowerCase()] = node.attributes[i + 1];
  const rawHref = attrs.href || "";
  if (!rawHref) throw new Error("element_has_no_download_url");
  const href = new URL(rawHref, (await chrome.tabs.get(tabId)).url).href;
  if (!safeUrl(href)) throw new Error("unsupported_download_url");
  if (riskyElement(ref, node) && !confirmationToken) return clickRef(tabId, ref, "", elementRef);
  const created = new Promise((resolve, reject) => {
    const timer = setTimeout(() => { chrome.downloads.onCreated.removeListener(listener); reject(new Error("download_not_started")); }, 30000);
    function listener(item) { if (item.url === href || item.finalUrl === href) { clearTimeout(timer); chrome.downloads.onCreated.removeListener(listener); resolve(item.id); } }
    chrome.downloads.onCreated.addListener(listener);
  });
  const clicked = await clickRef(tabId, ref, confirmationToken, elementRef);
  if (clicked.confirmation_required) return clicked;
  const id = await created;
  const finished = new Promise((resolve, reject) => {
    const timer = setTimeout(() => { chrome.downloads.onChanged.removeListener(listener); reject(new Error("download_timeout")); }, 120000);
    function listener(delta) { if (delta.id !== id) return; if (delta.state?.current === "complete") { clearTimeout(timer); chrome.downloads.onChanged.removeListener(listener); resolve(); } if (delta.state?.current === "interrupted") { clearTimeout(timer); chrome.downloads.onChanged.removeListener(listener); reject(new Error("download_interrupted")); } }
    chrome.downloads.onChanged.addListener(listener);
  });
  await finished;
  const [item] = await chrome.downloads.search({ id });
  return { file_path: item?.filename || "", download_id: id, url: item?.finalUrl || href };
}
function responseBase(request, status, fields = {}) {
  return { type: "response", request_id: request.request_id, status, operation: request.operation, tab: fields.tab || {}, before: fields.before || {}, after: fields.after || {}, observation: fields.observation || "", error_code: fields.error_code || "", retry_hint: fields.retry_hint || "", data: fields.data ?? null };
}
function waitForTabComplete(tabId, timeout) {
  return new Promise(resolve => {
    let done = false;
    const finish = (loaded = true) => { if (done) return; done = true; clearTimeout(timer); chrome.tabs.onUpdated.removeListener(listener); resolve(loaded); };
    const listener = (id, change) => { if (id === tabId && change.status === "complete") finish(); };
    const timer = setTimeout(() => finish(false), timeout);
    chrome.tabs.onUpdated.addListener(listener);
  });
}
async function handleRequest(request) {
  const args = request.arguments || {};
  if (request.operation === "list_tabs") {
    const tabs = await chrome.tabs.query({});
    return responseBase(request, "success", { observation: "Abas disponíveis no perfil Chrome atual.", data: { tabs: tabs.filter(t => safeUrl(t.url || "")).map(shortTab) } });
  }
  if (request.operation === "open_tab") {
    if (args.url && !safeUrl(args.url)) return responseBase(request, "failure", { error_code: "unsupported_url", retry_hint: "Provide an http or https URL." });
    let windowId = chrome.windows.WINDOW_ID_CURRENT;
    if (args.incognito) {
      const incognitoWindows = await chrome.windows.getAll({ windowTypes: ['normal'] }).then(ws => ws.filter(w => w.incognito));
      if (incognitoWindows.length > 0) {
        windowId = incognitoWindows[0].id;
      } else {
        const newWin = await chrome.windows.create({ url: args.url || "chrome://newtab", incognito: true });
        const newTab = newWin.tabs && newWin.tabs[0] ? newWin.tabs[0] : (await chrome.tabs.query({ windowId: newWin.id }))[0];
        return responseBase(request, "success", { tab: shortTab(newTab), after: { url: newTab.url || args.url, title: newTab.title || "" }, observation: "Nova aba anônima aberta." });
      }
    }
    const tab = await chrome.tabs.create({ url: args.url || "chrome://newtab", active: true, windowId: args.incognito ? windowId : undefined });
    return responseBase(request, "success", { tab: shortTab(tab), after: { url: tab.url || "", title: tab.title || "" }, observation: args.incognito ? "Nova aba anônima aberta." : "Nova aba aberta no perfil Chrome atual." });
  }
  if (request.operation === "navigate" && args.tab_id == null) {
    if (!safeUrl(args.url)) return responseBase(request, "failure", { error_code: "unsupported_url", retry_hint: "Use browser_open_tab or provide an http(s) URL." });
    const opened = await chrome.tabs.create({ url: args.url, active: true });
    return responseBase(request, "success", { tab: shortTab(opened), after: { url: opened.url || args.url, title: opened.title || "" }, observation: "URL aberta em uma nova aba do perfil Chrome atual." });
  }
  const tab = await tabFor(args.tab_id);
  const beforeTab = shortTab(tab);
  if (request.operation === "navigate" && !safeUrl(args.url)) return responseBase(request, "failure", { tab: beforeTab, error_code: "unsupported_url", retry_hint: "Use browser_open_tab or provide an http(s) URL." });
  await attach(tab.id);
  try {
    const before = await pageState(tab.id);
    let data = null, observation = "", status = "success";
    if (request.operation === "inspect") {
      const inspected = await inspectTab(tab.id, args.max_chars);
      data = inspected.data; observation = "Inspeção atual da aba; referências válidas somente para este documento.";
    } else if (request.operation === "click") {
      const tabsBefore = await chrome.tabs.query({ windowId: tab.windowId });
      const ref = await getRef(tab.id, args.element_ref);
      const action = await clickRef(tab.id, ref, args.confirmation_token || "", args.element_ref);
      if (action.confirmation_required) return responseBase(request, "confirmation_required", { tab: beforeTab, before, observation: "Esta ação pode enviar ou confirmar dados fora do navegador.", data: action, error_code: "user_confirmation_required" });
      await new Promise(resolve => setTimeout(resolve, 120));
      const after = await pageState(tab.id);
      const tabsAfter = await chrome.tabs.query({ windowId: tab.windowId });
      const newTabs = tabsAfter.filter(item => !tabsBefore.some(old => old.id === item.id)).map(shortTab);
      const changed = before.url !== after.url || before.title !== after.title || before.text !== after.text || newTabs.length > 0;
      status = changed ? "success" : "uncertain";
      return responseBase(request, status, { tab: shortTab(await chrome.tabs.get(tab.id)), before, after, observation: changed ? "Clique executado; estado visível ou conjunto de abas mudou." : "Clique enviado, mas nenhuma mudança de estado foi observada.", error_code: changed ? "" : "postcondition_not_observed", retry_hint: changed ? "" : "browser_inspect", data: newTabs.length ? { opened_tabs: newTabs } : null });
    } else if (request.operation === "fill" || request.operation === "select") {
      const ref = await getRef(tab.id, args.element_ref);
      data = await fillRef(tab.id, ref, args.value, request.operation === "select");
      const after = await pageState(tab.id);
      return responseBase(request, "success", { tab: shortTab(await chrome.tabs.get(tab.id)), before, after, observation: request.operation === "fill" ? "Campo preenchido e valor confirmado no elemento." : "Opção selecionada e valor confirmado no elemento.", data });
    } else if (request.operation === "press") {
      data = await pressKey(tab.id, args.key || "Enter", args.allow_submit === true);
      await new Promise(resolve => setTimeout(resolve, 250));
      const after = await pageState(tab.id);
      const changed = before.url !== after.url || before.title !== after.title || before.text !== after.text;
      return responseBase(request, changed ? "success" : "uncertain", { tab: shortTab(await chrome.tabs.get(tab.id)), before, after, observation: changed ? "Tecla pressionada e mudança de página observada." : "Tecla enviada sem mudança observável.", error_code: changed ? "" : "postcondition_not_observed", retry_hint: changed ? "" : "browser_inspect", data });
    } else if (request.operation === "navigate") {
      const event = waitForTabComplete(tab.id, 12000);
      const nav = await cdp(tab.id, "Page.navigate", { url: args.url });
      const loaded = await event;
      if (nav?.errorText) throw new Error("navigation_failed:" + nav.errorText);
      status = loaded ? "success" : "uncertain";
      if (!loaded) observation = "Chrome aceitou a URL, mas o carregamento não foi confirmado no prazo.";
    } else if (request.operation === "wait") {
      data = await waitFor(tab.id, args);
      observation = "Condição de página observada.";
    } else if (request.operation === "back") {
      data = await back(tab.id);
    } else if (request.operation === "click_at") {
      const tabsBefore = await chrome.tabs.query({ windowId: tab.windowId });
      const action = await clickAt(tab.id, args);
      if (action.confirmation_required) return responseBase(request, "confirmation_required", { tab: beforeTab, before, observation: "O alvo visual pode enviar ou confirmar dados fora do navegador.", data: action, error_code: "user_confirmation_required" });
      await new Promise(resolve => setTimeout(resolve, 120));
      const after = await pageState(tab.id);
      const tabsAfter = await chrome.tabs.query({ windowId: tab.windowId });
      const newTabs = tabsAfter.filter(item => !tabsBefore.some(old => old.id === item.id)).map(shortTab);
      const changed = before.url !== after.url || before.title !== after.title || before.text !== after.text || newTabs.length > 0;
      return responseBase(request, changed ? "success" : "uncertain", { tab: shortTab(await chrome.tabs.get(tab.id)), before, after, observation: changed ? "Clique nas coordenadas da captura enviado; mudança visível observada." : "Clique enviado, mas nenhuma mudança de estado foi observada.", error_code: changed ? "" : "postcondition_not_observed", retry_hint: changed ? "" : "browser_inspect", data: { ...action, opened_tabs: newTabs } });
    } else if (request.operation === "screenshot") {
      data = await screenshot(tab.id);
    } else if (request.operation === "download") {
      const ref = await getRef(tab.id, args.element_ref);
      data = await download(tab.id, ref, args.confirmation_token || "", args.element_ref);
      if (data?.confirmation_required) return responseBase(request, "confirmation_required", { tab: beforeTab, before, observation: "Este download ou ação exige confirmação explícita.", data, error_code: "user_confirmation_required" });
    } else if (request.operation === "search_site") {
      return responseBase(request, "failure", { tab: beforeTab, before, error_code: "site_search_not_available", retry_hint: "Use web_search with a site:domain query, then web_open on selected public results." });
    } else if (request.operation === "close_tab") {
      try {
        await chrome.tabs.remove(tab.id);
        return responseBase(request, "success", { before, observation: "Aba fechada." });
      } catch (err) {
        return responseBase(request, "failure", { before, error_code: "close_tab_failed" });
      }
    } else {
      return responseBase(request, "failure", { tab: beforeTab, before, error_code: "unsupported_operation" });
    }
    await new Promise(resolve => setTimeout(resolve, 250));
    const after = await pageState(tab.id);
    return responseBase(request, status, { tab: shortTab(await chrome.tabs.get(tab.id)), before, after, observation: observation || "Ação concluída; estado da página atualizado.", data });
  } catch (error) {
    const code = String(error?.message || error);
    const retry = code.includes("screenshot") || code.includes("coordinates_out_of_bounds") ? "browser_screenshot" : code.includes("stale") || code.includes("visible") ? "browser_inspect" : "browser_list_tabs";
    return responseBase(request, "failure", { tab: beforeTab, error_code: code.slice(0, 160), retry_hint: retry, observation: "A operação não foi concluída: " + code });
  } finally {
    await detach(tab.id);
  }
}
