const assert = require("node:assert/strict");
const fs = require("node:fs");
const path = require("node:path");
const test = require("node:test");
const vm = require("node:vm");

function makeEvent() {
  const listeners = [];
  return {
    addListener(listener) { listeners.push(listener); },
    fire(...args) { for (const listener of listeners) listener(...args); },
  };
}

function createWorker() {
  const nativePorts = [];
  const alarmCalls = [];
  const onMessage = makeEvent();
  const onAlarm = makeEvent();
  const runtime = {
    id: "test-extension",
    lastError: null,
    onStartup: makeEvent(),
    onInstalled: makeEvent(),
    onMessage,
    connectNative() {
      const port = { onMessage: makeEvent(), onDisconnect: makeEvent(), postMessage() {} };
      nativePorts.push(port);
      return port;
    },
  };
  const chrome = {
    runtime,
    alarms: {
      onAlarm,
      create(name, options) { alarmCalls.push({ type: "create", name, options }); },
      clear(name) { alarmCalls.push({ type: "clear", name }); },
    },
    action: { onClicked: makeEvent() },
    storage: { session: { async set() {}, async get() { return {}; } } },
  };
  const context = vm.createContext({
    chrome,
    importScripts() {},
    console,
    setTimeout,
    clearTimeout,
  });
  const source = fs.readFileSync(path.join(__dirname, "service_worker.js"), "utf8");
  vm.runInContext(source, context);

  function status() {
    let response;
    onMessage.fire({ type: "bridge-status" }, {}, value => { response = value; });
    return response;
  }

  return { alarmCalls, chrome, nativePorts, onAlarm, status };
}

test("reports connected only after Native Host confirms the app broker handshake", () => {
  const worker = createWorker();

  assert.equal(worker.status().state, "connecting");
  assert.equal(worker.status().connected, false);

  worker.nativePorts[0].onMessage.fire({ type: "ready" });

  assert.equal(worker.status().state, "connected");
  assert.equal(worker.status().connected, true);
  assert.ok(worker.alarmCalls.some(call => call.type === "clear" && call.name === "bridge-reconnect"));
});

test("schedules automatic reconnect after disconnect and retries when the alarm fires", () => {
  const worker = createWorker();
  const firstPort = worker.nativePorts[0];

  worker.chrome.runtime.lastError = { message: "Native host exited" };
  firstPort.onDisconnect.fire();

  assert.equal(worker.status().state, "disconnected");
  assert.match(worker.status().error, /Native host exited/);
  assert.ok(worker.alarmCalls.some(call => call.type === "create" && call.name === "bridge-reconnect"));

  worker.chrome.runtime.lastError = null;
  worker.onAlarm.fire({ name: "bridge-reconnect" });

  assert.equal(worker.nativePorts.length, 2);
  assert.equal(worker.status().state, "connecting");
});

test("keeps automatic reconnect delay at one minute or less", () => {
  const worker = createWorker();

  for (let attempt = 0; attempt < 7; attempt++) {
    worker.chrome.runtime.lastError = { message: "Native host exited" };
    worker.nativePorts.at(-1).onDisconnect.fire();
    const retry = worker.alarmCalls.filter(call => call.type === "create" && call.name === "bridge-reconnect").at(-1);
    assert.ok(retry.options.delayInMinutes <= 1);
    worker.chrome.runtime.lastError = null;
    worker.onAlarm.fire({ name: "bridge-reconnect" });
  }
});