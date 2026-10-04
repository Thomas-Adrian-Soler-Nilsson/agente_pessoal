// Cliente CDP mínimo sobre WebSocket nativo do Node (sem dependências)
// e lançador de um Chrome/Chromium ISOLADO (perfil temporário, headless).
// Nada aqui toca no Chrome do usuário: user-data-dir próprio e porta efêmera.
import { spawn, spawnSync } from "node:child_process";
import { mkdtemp, rm } from "node:fs/promises";
import http from "node:http";
import os from "node:os";
import path from "node:path";
import fs from "node:fs";

const CANDIDATE_CHROME_PATHS = [
  "C:/Program Files/Google/Chrome/Application/chrome.exe",
  "C:/Program Files (x86)/Google/Chrome/Application/chrome.exe",
  "C:/Program Files/Chromium/Application/chrome.exe",
  process.env.CHROME_PATH || "",
].filter(Boolean);

export function findChrome() {
  for (const candidate of CANDIDATE_CHROME_PATHS) {
    if (fs.existsSync(candidate)) return candidate;
  }
  throw new Error("Chrome/Chromium não encontrado. Defina CHROME_PATH.");
}

export class Cdp {
  constructor(ws) {
    this.ws = ws;
    this.nextId = 1;
    this.pending = new Map();
    ws.addEventListener("message", (event) => {
      const message = JSON.parse(event.data);
      if (message.id && this.pending.has(message.id)) {
        const { resolve, reject } = this.pending.get(message.id);
        this.pending.delete(message.id);
        if (message.error) reject(new Error(message.error.message || JSON.stringify(message.error)));
        else resolve(message.result);
      }
    });
  }

  static async connect(url) {
    const ws = new WebSocket(url);
    await new Promise((resolve, reject) => {
      ws.addEventListener("open", resolve, { once: true });
      ws.addEventListener("error", () => reject(new Error("Falha ao abrir WebSocket CDP: " + url)), { once: true });
    });
    return new Cdp(ws);
  }

  send(method, params = {}, sessionId = undefined) {
    const id = this.nextId++;
    const payload = { id, method, params };
    if (sessionId) payload.sessionId = sessionId;
    return new Promise((resolve, reject) => {
      this.pending.set(id, { resolve, reject });
      this.ws.send(JSON.stringify(payload));
      setTimeout(() => {
        if (this.pending.has(id)) {
          this.pending.delete(id);
          reject(new Error("CDP timeout: " + method));
        }
      }, 30000).unref();
    });
  }

  close() {
    try { this.ws.close(); } catch (_) {}
  }
}

export async function launchChrome() {
  const chrome = findChrome();
  const userDir = await mkdtemp(path.join(os.tmpdir(), "agent-real-cdp-"));
  const child = spawn(chrome, [
    "--remote-debugging-port=0",
    "--user-data-dir=" + userDir,
    "--headless=new",
    "--no-first-run",
    "--no-default-browser-check",
    "--disable-extensions",
    "--window-size=1600,1200",
    "about:blank",
  ], { stdio: ["ignore", "ignore", "pipe"] });

  const wsUrl = await new Promise((resolve, reject) => {
    let buffer = "";
    const timer = setTimeout(() => reject(new Error("Chrome não anunciou a porta DevTools em 15s.")), 15000);
    child.stderr.on("data", (chunk) => {
      buffer += chunk.toString();
      const match = buffer.match(/DevTools listening on ws:\/\/127\.0\.0\.1:(\d+)\/\S+/);
      if (match) {
        clearTimeout(timer);
        resolve(`http://127.0.0.1:${match[1]}`);
      }
    });
    child.on("exit", (code) => { clearTimeout(timer); reject(new Error("Chrome saiu cedo com código " + code)); });
  });

  const kill = () => {
    // Mata a ÁRVORE do Chrome de teste; nunca processos do usuário.
    if (process.platform === "win32") spawnSync("taskkill", ["/pid", String(child.pid), "/T", "/F"], { stdio: "ignore" });
    else child.kill("SIGKILL");
  };

  return {
    httpPort: new URL(wsUrl).port,
    httpBase: wsUrl,
    async close() {
      kill();
      await rm(userDir, { recursive: true, force: true }).catch(() => {});
    },
  };
}

export async function cdpHttpJson(base, route) {
  const body = await new Promise((resolve, reject) => {
    http.get(base + route, (res) => {
      let data = "";
      res.on("data", (chunk) => { data += chunk; });
      res.on("end", () => resolve(data));
    }).on("error", reject);
  });
  return JSON.parse(body);
}

export async function startStaticServer(rootDir) {
  const server = http.createServer((req, res) => {
    const url = new URL(req.url, "http://127.0.0.1");
    const file = path.join(rootDir, url.pathname === "/" ? "index.html" : url.pathname);
    fs.readFile(file, (error, data) => {
      if (error) { res.writeHead(404); res.end("not found"); return; }
      res.writeHead(200, { "Content-Type": file.endsWith(".html") ? "text/html; charset=utf-8" : "application/octet-stream" });
      res.end(data);
    });
  });
  await new Promise((resolve) => server.listen(0, "127.0.0.1", resolve));
  return {
    baseUrl: `http://127.0.0.1:${server.address().port}/`,
    close: () => new Promise((resolve) => server.close(resolve)),
  };
}
