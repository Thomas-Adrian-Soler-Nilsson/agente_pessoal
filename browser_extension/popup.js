const statusElement = document.getElementById("status");
const hintElement = document.getElementById("hint");
const reconnectButton = document.getElementById("reconnect");

function render(state) {
	if (state?.state === "connected") {
		statusElement.textContent = "Conectado ao Agente Pessoal.";
		hintElement.textContent = "O navegador está pronto para receber ações.";
		reconnectButton.textContent = "Conectado";
		reconnectButton.disabled = true;
		return;
	}
	if (state?.state === "connecting") {
		statusElement.textContent = "Conectando ao app…";
		hintElement.textContent = "Se o app estiver abrindo, a conexão deve voltar sozinha.";
		reconnectButton.textContent = "Conectando…";
		reconnectButton.disabled = true;
		return;
	}
	statusElement.textContent = "Agente Pessoal desconectado.";
	hintElement.textContent = state?.error
		? "Abra o app; a extensão tentará novamente automaticamente. Motivo: " + state.error
		: "Abra o app para conectar. A extensão tentará novamente em segundo plano.";
	reconnectButton.textContent = "Tentar conectar agora";
	reconnectButton.disabled = false;
}

async function refresh() {
	try {
		render(await chrome.runtime.sendMessage({ type: "bridge-status" }));
	} catch (_) {
		render({ state: "disconnected" });
	}
}

reconnectButton.addEventListener("click", async () => {
	reconnectButton.disabled = true;
	render({ state: "connecting" });
	try {
		await chrome.runtime.sendMessage({ type: "bridge-reconnect" });
	} catch (_) {
		render({ state: "disconnected" });
	}
	await refresh();
});

refresh();
setInterval(refresh, 750);