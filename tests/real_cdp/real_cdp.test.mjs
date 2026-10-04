// Testes OBRIGATÓRIOS contra Chrome REAL, isolado (seção 5 da missão).
// Carregam o service_worker.js de produção numa VM e falam CDP com um
// Chrome headless em perfil temporário. Nenhum site real é aberto.
//
// Rodar: node --test tests/real_cdp/
import assert from "node:assert/strict";
import path from "node:path";
import test from "node:test";
import { fileURLToPath } from "node:url";

import { Cdp, cdpHttpJson, launchChrome, startStaticServer } from "./chrome_cdp.mjs";
import { createWorkerContext } from "./worker_context.mjs";

const pageDir = path.join(path.dirname(fileURLToPath(import.meta.url)), "page");

let chrome;
let cdp;
let server;
let worker;
let tabId;
let session;

// CDP direto (fora do shim), com sessão própria na aba de teste.
function direct(method, params = {}) {
  return cdp.send(method, params, session);
}

// O alvo criado pelo Chrome começa em about:blank, cujo document.readyState já
// é "complete": esperar só por readyState retorna ANTES de a página de teste
// commitar (medido: o commit leva ~1-2,5 s num perfil novo). Por isso exigimos
// também que location.href seja o da página esperada.
async function waitReady(tabId, expectedPath) {
  await worker.debugger.attach({ tabId });
  try {
    for (let attempt = 0; attempt < 80; attempt++) {
      const out = await worker.evaluate(tabId, "JSON.stringify({href:location.href,ready:document.readyState})");
      let state = {};
      try { state = JSON.parse(out?.result?.value || "{}"); } catch (_) {}
      if (state.ready === "complete" && String(state.href).includes(expectedPath)) return;
      await new Promise((resolve) => setTimeout(resolve, 250));
    }
    throw new Error("página de teste não carregou: " + expectedPath);
  } finally {
    await worker.debugger.detach({ tabId });
  }
}

// A árvore de acessibilidade do Chrome também é serializada de forma assíncrona
// após o primeiro Accessibility.enable. Esperamos o nó existir de verdade em vez
// de consultar uma árvore ainda vazia (senão o teste mede about:blank).
async function waitForAxNode(role, name, timeoutMs = 15000) {
  const deadline = Date.now() + timeoutMs;
  let seen = [];
  while (Date.now() < deadline) {
    const tree = await direct("Accessibility.getFullAXTree", {});
    seen = (tree.nodes || []).filter((node) => node.backendDOMNodeId)
      .map((node) => [String(node.role?.value || ""), String(node.name?.value || "")]);
    if (seen.some(([nodeRole, nodeName]) => nodeRole.toLowerCase() === role && nodeName === name)) return;
    await new Promise((resolve) => setTimeout(resolve, 300));
  }
  throw new Error(`AX tree não serializou ${role} "${name}" em ${timeoutMs}ms; vi: ` + JSON.stringify(seen.slice(0, 20)));
}

async function request(operation, args = {}) {
  const response = await worker.handleRequest({
    type: "request",
    request_id: "req-" + Math.random().toString(16).slice(2),
    version: 1,
    operation,
    arguments: args,
  });
  return response;
}

async function inspect() {
  const response = await request("inspect", { tab_id: tabId, max_chars: 4000 });
  assert.equal(response.status, "success", "inspect deve funcionar: " + JSON.stringify(response).slice(0, 400));
  return response.data;
}

function refFor(elements, role, name) {
  const found = elements.find((item) => item.role === role && item.name === name);
  assert.ok(found, `elemento ${role} "${name}" deve aparecer no inspect; vi: ` + JSON.stringify(elements));
  return found.element_ref;
}

async function events() {
  const out = await direct("Runtime.evaluate", { expression: "JSON.stringify(window.__events)", returnByValue: true });
  return JSON.parse(out.result.value);
}

test.before(async () => {
  chrome = await launchChrome();
  const version = await cdpHttpJson(chrome.httpBase, "/json/version");
  cdp = await Cdp.connect(version.webSocketDebuggerUrl);
  server = await startStaticServer(pageDir);
  worker = createWorkerContext(cdp);

  const opened = await request("open_tab", { url: server.baseUrl + "index.html" });
  assert.equal(opened.status, "success", "open_tab deve funcionar: " + JSON.stringify(opened).slice(0, 300));
  tabId = opened.tab.id;
  await waitReady(tabId, "index.html");

  session = (await cdp.send("Target.attachToTarget", { targetId: worker.tabs.targetIdOf(tabId), flatten: true })).sessionId;
  for (const [method, params] of [["Page.enable", {}], ["Runtime.enable", {}], ["DOM.enable", {}], ["Accessibility.enable", {}]]) {
    await direct(method, params);
  }
  await waitForAxNode("textbox", "Mensagem");
});

test.after(async () => {
  try { if (cdp) cdp.close(); } catch (_) {}
  try { if (chrome) await chrome.close(); } catch (_) {}
  try { if (server) await server.close(); } catch (_) {}
});

test("5.1 PASSO 0: nodeId de DOM.describeNode num Chrome real (hipótese A)", async () => {
  const tree = await direct("Accessibility.getFullAXTree", {});
  const target = (tree.nodes || []).find((node) =>
    String(node.role?.value || "").toLowerCase() === "textbox" && String(node.name?.value || "") === "Mensagem");
  assert.ok(target?.backendDOMNodeId, "textbox 'Mensagem' deve existir na AX tree real");

  const described = await direct("DOM.describeNode", { backendNodeId: target.backendDOMNodeId, depth: 1, pierce: true });
  const nodeId = described?.node?.nodeId;
  console.log("[PASSO 0] DOM.describeNode retornou nodeId =", JSON.stringify(nodeId), "(backendNodeId =", target.backendDOMNodeId + ")");
  // Hipótese A: nodeId volta 0/ausente porque describeNode não rastreia nós.
  assert.ok(!nodeId, `hipótese A exige nodeId 0/ausente; observado: ${JSON.stringify(nodeId)}`);
});

test("5.2 fill por element_ref preenche textarea e contenteditable com evento input", async () => {
  const data = await inspect();
  const msgRef = refFor(data.elements, "textbox", "Mensagem");
  const editorRef = refFor(data.elements, "textbox", "Editor");

  const filled = await request("fill", { tab_id: tabId, element_ref: msgRef, value: "Olá Thomas" });
  assert.equal(filled.status, "success", "fill na textarea deve ter sucesso; resposta: " + JSON.stringify(filled).slice(0, 500));

  const value = await direct("Runtime.evaluate", { expression: "document.getElementById('msg').value", returnByValue: true });
  assert.equal(value.result.value, "Olá Thomas", "valor deve estar no campo real");

  const editorFilled = await request("fill", { tab_id: tabId, element_ref: editorRef, value: "texto editável" });
  assert.equal(editorFilled.status, "success", "fill no contenteditable deve ter sucesso; resposta: " + JSON.stringify(editorFilled).slice(0, 500));

  const editorValue = await direct("Runtime.evaluate", { expression: "document.getElementById('editor').textContent", returnByValue: true });
  assert.ok(String(editorValue.result.value).includes("texto editável"), "contenteditable deve conter o valor");

  const logged = await events();
  assert.ok(logged.some((e) => e.type === "input" && e.value.includes("Olá Thomas")), "evento input da textarea deve disparar: " + JSON.stringify(logged));
  assert.ok(logged.some((e) => e.type === "input" && e.value.includes("texto editável")), "evento input do contenteditable deve disparar");
});

test("5.3 Enter com code/vk/text chega como keyCode 13; formato antigo não", async () => {
  const data = await inspect();
  const msgRef = refFor(data.elements, "textbox", "Mensagem");
  await request("fill", { tab_id: tabId, element_ref: msgRef, value: "mensagem para enviar" });

  // Formato ANTIGO (só key): referência para comparação.
  const before = (await events()).length;
  await direct("Input.dispatchKeyEvent", { type: "keyDown", key: "Enter" });
  await direct("Input.dispatchKeyEvent", { type: "keyUp", key: "Enter" });
  const oldFormat = (await events()).slice(before);
  console.log("[5.3] evento do formato antigo (só key):", JSON.stringify(oldFormat));

  // Formato NOVO via service_worker real (operação press).
  const before2 = (await events()).length;
  const pressed = await request("press", { tab_id: tabId, key: "Enter" });
  assert.ok(pressed.status === "success" || pressed.status === "uncertain", "press deve executar: " + JSON.stringify(pressed).slice(0, 400));
  const newFormat = (await events()).slice(before2);
  console.log("[5.3] evento do formato novo (code/vk/text):", JSON.stringify(newFormat));

  assert.ok(newFormat.some((e) => e.type === "keydown" && e.key === "Enter" && e.keyCode === 13 && e.code === "Enter"),
    "listener da página deve registrar Enter com keyCode 13 e code Enter: " + JSON.stringify(newFormat));
  assert.notEqual(oldFormat.find((e) => e.type === "keydown")?.keyCode, 13,
    "formato antigo não deve entregar keyCode 13 (é esta a diferença que quebra sites React)");
});

test("5.4 campo de senha continua bloqueado (password_field_blocked)", async () => {
  const data = await inspect();
  const password = data.elements.find((item) => item.type === "password");
  assert.ok(password, "input de senha deve aparecer no inspect para ser testado");
  const response = await request("fill", { tab_id: tabId, element_ref: password.element_ref, value: "segredo" });
  assert.equal(response.status, "failure");
  assert.equal(response.error_code, "password_field_blocked", "erro real: " + JSON.stringify(response).slice(0, 300));
});

test("5.5 rebindElementRef recupera o campo após re-render de SPA", async () => {
  const data = await inspect();
  const msgRef = refFor(data.elements, "textbox", "Mensagem");

  await direct("Runtime.evaluate", { expression: "window.__replaceMessageField()", returnByValue: true });
  const valueNow = await direct("Runtime.evaluate", { expression: "document.getElementById('msg').value", returnByValue: true });

  const refilled = await request("fill", { tab_id: tabId, element_ref: msgRef, value: "nova mensagem" });
  assert.equal(refilled.status, "success", "fill deve reencontrar o campo novo por papel+nome; resposta: " + JSON.stringify(refilled).slice(0, 500));

  const valueAfter = await direct("Runtime.evaluate", { expression: "document.getElementById('msg').value", returnByValue: true });
  assert.equal(valueAfter.result.value, "nova mensagem", "o campo NOVO deve ter o valor (não o nó antigo)");
  assert.ok(valueNow.result.value !== "nova mensagem", "campo velho não deveria já ter a nova mensagem");
});

test("5.6 screenshot grande: loop de qualidade entrega ≤700000 chars e JPEG decodifica", async () => {
  const navigated = await request("navigate", { tab_id: tabId, url: server.baseUrl + "big.html" });
  assert.ok(navigated.status === "success" || navigated.status === "uncertain", "navegação: " + JSON.stringify(navigated).slice(0, 300));
  await waitReady(tabId, "big.html");

  // Pré-condição que impede este teste de virar verde por acidente: a captura em
  // quality 65 precisa estourar o limite, senão o loop nunca é exercitado (com a
  // fixture antiga, de 1280x900, q65 dava 644244 chars e o código ANTIGO passava).
  const rawAt65 = await direct("Page.captureScreenshot", { format: "jpeg", quality: 65, fromSurface: true, captureBeyondViewport: false });
  console.log("[5.6] captura crua em q65 =", String(rawAt65.data || "").length, "chars");
  assert.ok(String(rawAt65.data || "").length > 700000,
    "a fixture precisa exceder 700000 chars em q65 para forçar o loop de qualidade; foi " + String(rawAt65.data || "").length);

  const shot = await request("screenshot", { tab_id: tabId });
  assert.equal(shot.status, "success", "screenshot deve ter sucesso; resposta: " + JSON.stringify(shot).slice(0, 300));
  const data = String(shot.data?.data || "");
  console.log("[5.6] screenshot base64 length =", data.length, "dimensões:", shot.data?.width + "x" + shot.data?.height);
  assert.ok(data.length > 0 && data.length <= 700000, "base64 deve caber em 700000 chars; foi " + data.length);
  assert.ok(shot.data?.width > 0 && shot.data?.height > 0, "dimensões devem decodificar do JPEG real");
});

test("5.7 SPA muda a URL: ref antiga é stale de forma legítima e o novo inspect recupera", async () => {
  // Reproduz o fluxo real do DeepSeek: /  ->  /a/chat/s/<id> após enviar.
  // 5.6 deixou a aba em big.html; voltamos para a página com o textbox.
  const back = await request("navigate", { tab_id: tabId, url: server.baseUrl + "index.html" });
  assert.ok(back.status === "success" || back.status === "uncertain", "navegação: " + JSON.stringify(back).slice(0, 300));
  await waitReady(tabId, "index.html");

  const before = await inspect();
  const oldRef = refFor(before.elements, "textbox", "Mensagem");

  const href = (await direct("Runtime.evaluate", { expression: "window.__spaNavigate('12345')", returnByValue: true })).result.value;
  console.log("[5.7] URL após pushState =", href);

  const staleFill = await request("fill", { tab_id: tabId, element_ref: oldRef, value: "não deve entrar" });
  assert.equal(staleFill.status, "failure", "ref de outra URL deve ser recusada; resposta: " + JSON.stringify(staleFill).slice(0, 300));
  assert.equal(staleFill.error_code, "stale_element_reference");

  const after = await inspect();
  const freshRef = refFor(after.elements, "textbox", "Mensagem");
  const freshFill = await request("fill", { tab_id: tabId, element_ref: freshRef, value: "mensagem após SPA" });
  assert.equal(freshFill.status, "success", "ref nova depois do inspect deve preencher; resposta: " + JSON.stringify(freshFill).slice(0, 300));

  const value = await direct("Runtime.evaluate", { expression: "document.getElementById('msg').value", returnByValue: true });
  assert.equal(value.result.value, "mensagem após SPA");

  // Volta o documento para a URL original e limpa o valor para não afetar
  // quem rodar depois (o runner do node executa os testes em ordem).
  await direct("Runtime.evaluate", { expression: "history.replaceState({}, '', '/index.html'); document.getElementById('msg').value = '';", returnByValue: true });
  await inspect();
});

test("5.8 ação arriscada: a confirmação devolve token e ele é aceito na 2ª tentativa", async () => {
  // Bug real encontrado no log do usuário: ele respondia "s" e a extensão pedia
  // confirmação de novo, porque o token era validado comparando o OBJETO da
  // referência (que é relido do storage a cada requisição) em vez do element_ref.
  const back = await request("navigate", { tab_id: tabId, url: server.baseUrl + "index.html" });
  assert.ok(back.status === "success" || back.status === "uncertain", "navegação: " + JSON.stringify(back).slice(0, 300));
  await waitReady(tabId, "index.html");

  const data = await inspect();
  const enviar = data.elements.find((item) => item.role === "button" && item.name === "Enviar");
  assert.ok(enviar, "o botão 'Enviar' precisa aparecer no inspect: " + JSON.stringify(data.elements));

  const primeira = await request("click", { tab_id: tabId, element_ref: enviar.element_ref });
  assert.equal(primeira.status, "confirmation_required", "resposta: " + JSON.stringify(primeira).slice(0, 400));
  assert.equal(primeira.error_code, "user_confirmation_required");
  const token = primeira.data?.confirmation_token;
  assert.ok(token, "a confirmação precisa devolver um token");

  const antes = await events();
  assert.ok(!antes.some((e) => e.type === "clicked"), "nada pode ser clicado antes da autorização");

  const segunda = await request("click", {
    tab_id: tabId,
    element_ref: enviar.element_ref,
    confirmation_token: token,
  });
  // O clique sem mudança visível devolve "uncertain" (postcondition_not_observed),
  // que é o comportamento honesto da extensão. O que importa aqui é que a
  // confirmação NÃO foi pedida de novo.
  assert.ok(
    segunda.status === "success" || segunda.status === "uncertain",
    "a 2ª tentativa precisa executar o clique: " + JSON.stringify(segunda).slice(0, 500),
  );
  assert.notEqual(
    segunda.error_code, "user_confirmation_required",
    "o token precisa ser aceito em vez de pedir confirmação de novo: " + JSON.stringify(segunda).slice(0, 500),
  );

  const depois = await events();
  assert.ok(
    depois.some((e) => e.type === "clicked" && e.id === "enviar"),
    "o botão precisa ter sido clicado de fato: " + JSON.stringify(depois),
  );
});

test("5.9 press com allow_submit não é barrado pelo guard de envio", async () => {
  const back = await request("navigate", { tab_id: tabId, url: server.baseUrl + "index.html" });
  assert.ok(back.status === "success" || back.status === "uncertain", "navegação: " + JSON.stringify(back).slice(0, 300));
  await waitReady(tabId, "index.html");

  const data = await inspect();
  const msgRef = refFor(data.elements, "textbox", "Mensagem");
  await request("fill", { tab_id: tabId, element_ref: msgRef, value: "teste de envio" });

  const normal = await request("press", { tab_id: tabId, key: "Enter" });
  assert.ok(normal.status === "success" || normal.status === "uncertain", "press normal: " + JSON.stringify(normal).slice(0, 300));

  const liberado = await request("press", { tab_id: tabId, key: "Enter", allow_submit: true });
  assert.ok(liberado.status === "success" || liberado.status === "uncertain", "press com allow_submit: " + JSON.stringify(liberado).slice(0, 300));
});

test("extra: inspect lista botão sem nome (evidência da seção 6)", async () => {
  // 5.6 deixou a aba em big.html; este teste precisa da página com o botão sem nome.
  const navigated = await request("navigate", { tab_id: tabId, url: server.baseUrl + "index.html" });
  assert.ok(navigated.status === "success" || navigated.status === "uncertain", "navegação de volta: " + JSON.stringify(navigated).slice(0, 300));
  await waitReady(tabId, "index.html");

  const data = await inspect();
  const unnamed = data.elements.filter((item) => item.role === "button" && !item.name);
  console.log("[seção 6] botões sem nome no inspect:", JSON.stringify(unnamed));
  assert.ok(unnamed.length >= 1, "botão sem nome deve constar no inspect; vi: " + JSON.stringify(data.elements));
});
