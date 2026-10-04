// Carrega o service_worker.js REAL da extensão numa VM Node, com um shim de
// chrome.* cujo chrome.debugger fala CDP com um Chrome real (headless,
// perfil temporário). Assim os testes exercitam o código de produção da
// extensão, não uma réplica.
import fs from "node:fs";
import path from "node:path";
import vm from "node:vm";
import { webcrypto } from "node:crypto";
import { fileURLToPath } from "node:url";

const extensionDir = path.resolve(path.dirname(fileURLToPath(import.meta.url)), "../../browser_extension");

function makeEvent() {
  const listeners = [];
  return {
    addListener(listener) { listeners.push(listener); },
    removeListener(listener) {
      const index = listeners.indexOf(listener);
      if (index >= 0) listeners.splice(index, 1);
    },
    fire(...args) { for (const listener of listeners) listener(...args); },
    listenerCount() { return listeners.length; },
  };
}

class TabsShim {
  constructor(cdp) {
    this.cdp = cdp;
    this.nextId = 100;
    this.byId = new Map();
    this.onUpdated = makeEvent();
    this.onRemoved = makeEvent();
  }

  targetIdOf(tabId) {
    const targetId = this.byId.get(Number(tabId));
    if (!targetId) throw new Error("No tab with id: " + tabId);
    return targetId;
  }

  register(targetId) {
    const id = this.nextId++;
    this.byId.set(id, targetId);
    return id;
  }

  async info(targetId) {
    const out = await this.cdp.send("Target.getTargetInfo", { targetId });
    return out.targetInfo;
  }

  async get(id) {
    const targetId = this.byId.get(Number(id));
    if (!targetId) throw new Error("No tab with id: " + id);
    const t = await this.info(targetId);
    if (!t || t.type !== "page") throw new Error("No tab with id: " + id);
    return { id: Number(id), title: t.title, url: t.url, active: true, windowId: 1 };
  }

  async create({ url }) {
    const out = await this.cdp.send("Target.createTarget", { url: url || "about:blank" });
    const id = this.register(out.targetId);
    this.scheduleLoadEvent(id);
    return { id, title: "", url: url || "about:blank", active: true, windowId: 1 };
  }

  async remove(id) {
    const targetId = this.byId.get(Number(id));
    if (!targetId) throw new Error("No tab with id: " + id);
    await this.cdp.send("Target.closeTarget", { targetId });
    this.byId.delete(Number(id));
  }

  async query() {
    const tabs = [];
    for (const [id, targetId] of this.byId) {
      const t = await this.info(targetId).catch(() => null);
      if (t && t.type === "page") tabs.push({ id, title: t.title, url: t.url, active: true, windowId: 1 });
    }
    return tabs;
  }

  // Simplificação documentada: dispara onUpdated({status:'complete'}) após
  // pequeno atraso, em vez de espelhar o ciclo de loading real do Chrome.
  scheduleLoadEvent(id) {
    setTimeout(() => this.onUpdated.fire(id, { status: "complete" }), 400);
  }
}

class DebuggerShim {
  constructor(cdp, tabs) {
    this.cdp = cdp;
    this.tabs = tabs;
    this.sessions = new Map();
  }

  async attach({ tabId }) {
    if (this.sessions.has(Number(tabId))) throw new Error("Already attached");
    const out = await this.cdp.send("Target.attachToTarget", { targetId: this.tabs.targetIdOf(tabId), flatten: true });
    this.sessions.set(Number(tabId), out.sessionId);
  }

  async detach({ tabId }) {
    const sessionId = this.sessions.get(Number(tabId));
    if (!sessionId) return;
    try { await this.cdp.send("Target.detachFromTarget", { sessionId }); } catch (_) {}
    this.sessions.delete(Number(tabId));
  }

  sendCommand({ tabId }, method, params) {
    const sessionId = this.sessions.get(Number(tabId));
    if (!sessionId) return Promise.reject(new Error("Not attached to tab " + tabId));
    return this.cdp.send(method, params, sessionId);
  }
}

export function createWorkerContext(cdp) {
  const tabs = new TabsShim(cdp);
  const debugger_ = new DebuggerShim(cdp, tabs);
  const sessionStore = new Map();

  const storage = {
    session: {
      // O Chrome real serializa o que entra e devolve um objeto NOVO a cada
      // leitura. Sem isso o shim entregava a mesma referencia e escondia bugs de
      // identidade de objeto (como o token de confirmacao que nunca validava).
      async get(keys) {
        const wanted = Array.isArray(keys) ? keys : typeof keys === "string" ? [keys] : Object.keys(keys || {});
        const out = {};
        for (const key of wanted) if (sessionStore.has(key)) out[key] = structuredClone(sessionStore.get(key));
        return out;
      },
      async set(items) {
        for (const [key, value] of Object.entries(items)) sessionStore.set(key, structuredClone(value));
      },
      async remove(keys) { for (const key of [].concat(keys)) sessionStore.delete(key); },
    },
  };

  const chrome = {
    runtime: {
      id: "real-cdp-test",
      lastError: null,
      onStartup: makeEvent(),
      onInstalled: makeEvent(),
      onMessage: makeEvent(),
      connectNative() {
        return { onMessage: makeEvent(), onDisconnect: makeEvent(), postMessage() {} };
      },
    },
    alarms: { onAlarm: makeEvent(), create() {}, clear() {} },
    action: { onClicked: makeEvent() },
    storage,
    windows: {
      WINDOW_ID_CURRENT: -2,
      async getAll() { return []; },
      async create() { throw new Error("windows.create não suportado no teste"); },
    },
    tabs,
    debugger: debugger_,
    downloads: { onCreated: makeEvent(), onChanged: makeEvent(), search: async () => [] },
  };

  const context = vm.createContext({
    chrome,
    console,
    crypto: Object.assign(Object.create(null), webcrypto, { randomUUID: () => webcrypto.randomUUID() }),
    TextEncoder,
    TextDecoder,
    URL,
    atob: (value) => Buffer.from(value, "base64").toString("binary"),
    btoa: (value) => Buffer.from(value, "binary").toString("base64"),
    setTimeout,
    clearTimeout,
    setInterval,
    clearInterval,
    importScripts(...files) {
      for (const file of files) {
        vm.runInContext(fs.readFileSync(path.join(extensionDir, file), "utf8"), context, { filename: file });
      }
    },
  });

  const source = fs.readFileSync(path.join(extensionDir, "service_worker.js"), "utf8");
  vm.runInContext(source, context, { filename: "service_worker.js" });

  return {
    chrome,
    tabs,
    debugger: debugger_,
    // Chama handleRequest do service_worker real direto (mesmo contrato do
    // native host: {type:'request', version, request_id, operation, arguments}).
    handleRequest(request) {
      return context.handleRequest(request);
    },
    evaluate(tabId, expression) {
      return debugger_.sendCommand({ tabId }, "Runtime.evaluate", { expression, returnByValue: true });
    },
  };
}
