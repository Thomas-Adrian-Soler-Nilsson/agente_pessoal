import json
import time
from typing import Callable

SYSTEM_PROMPT = """
Você é o agente pessoal do Thomas. Fale em português do Brasil.
Seja natural, informal, inteligente e levemente irônico, sem ser ofensivo.
Use as ferramentas quando forem necessárias e nunca invente conteúdo de arquivos.
Não exclua arquivos, formate nada nem execute comandos destrutivos.
Como suas respostas serão faladas, seja conciso e evite listas gigantes.

Use open_directory para abrir uma pasta no Explorador de Arquivos.
Para Downloads, passe "Downloads" ou "OneDrive\\Downloads".
Use open_application apenas para abrir aplicativos.
"""


def build_tools():
    definitions = [
        ("open_application", "Abre um aplicativo instalado no computador.", {"application": {"type": "string"}}, ["application"]),
        ("open_directory", "Abre uma pasta no Explorador de Arquivos.", {"path": {"type": "string"}}, ["path"]),
        ("open_url", "Abre uma URL no navegador.", {"url": {"type": "string"}}, ["url"]),
        ("list_directory", "Lista arquivos e pastas de um diretório.", {"path": {"type": "string"}}, ["path"]),
        ("search_files", "Procura arquivos pelo nome em uma pasta.", {"query": {"type": "string"}, "path": {"type": "string"}}, ["query"]),
        ("read_file", "Lê o conteúdo de um arquivo de texto.", {"path": {"type": "string"}}, ["path"]),
        ("get_file_info", "Obtém informações de um arquivo.", {"path": {"type": "string"}}, ["path"]),
        ("capture_screen", "Captura a tela atual do computador.", {}, []),
        ("capture_webcam", "Captura uma imagem atual da webcam.", {}, []),
    ]
    return [{"type": "function", "function": {"name": name, "description": description, "parameters": {"type": "object", "properties": properties, "required": required}}} for name, description, properties, required in definitions]


class CompatibleAgent:
    def __init__(self, client, model: str, tool_executor: Callable, messages=None):
        self.client = client
        self.model = model
        self.tool_executor = tool_executor
        self.tools = build_tools()
        self.messages = messages if messages is not None else [{"role": "system", "content": SYSTEM_PROMPT}]

    def _completion(self, **kwargs):
        for attempt in range(2):
            try:
                return self.client.chat.completions.create(**kwargs)
            except Exception as error:
                if getattr(error, "status_code", None) != 429 or attempt == 1:
                    raise
                print("\n⚠️ Limite temporário atingido. Tentando novamente em 5 segundos...")
                time.sleep(5)

    def ask_stream(self, user_message: str):
        self.messages.append({"role": "user", "content": user_message})
        response = self._completion(model=self.model, messages=self.messages, tools=self.tools, tool_choice="auto", temperature=0.7, max_completion_tokens=250)
        message = response.choices[0].message
        if not message.tool_calls:
            content = (message.content or "").strip()
            self.messages.append({"role": "assistant", "content": content})
            if content:
                yield content
            return

        tool_calls = [{"id": call.id, "type": "function", "function": {"name": call.function.name, "arguments": call.function.arguments}} for call in message.tool_calls]
        self.messages.append({"role": "assistant", "content": message.content or "", "tool_calls": tool_calls})
        for call in message.tool_calls:
            try:
                arguments = json.loads(call.function.arguments or "{}")
                result = self.tool_executor(call.function.name, arguments)
            except Exception as error:
                result = f"Erro ao executar {call.function.name}: {error}"
            print(f"\n🔧 IA → {call.function.name}()")
            if isinstance(result, dict) and result.get("type") == "image":
                self.messages.append({"role": "tool", "tool_call_id": call.id, "content": result.get("description", "Imagem capturada.")})
                self.messages.append({"role": "user", "content": [{"type": "text", "text": "Analise esta imagem e responda à solicitação original."}, {"type": "image_url", "image_url": {"url": f"data:image/jpeg;base64,{result['data']}"}}]})
            else:
                if not isinstance(result, str):
                    result = json.dumps(result, ensure_ascii=False)
                self.messages.append({"role": "tool", "tool_call_id": call.id, "content": result})

        final_stream = self._completion(model=self.model, messages=self.messages, tools=self.tools, tool_choice="auto", temperature=0.75, max_completion_tokens=300, stream=True)
        collected = []
        for chunk in final_stream:
            if not chunk.choices:
                continue
            content = chunk.choices[0].delta.content
            if content:
                collected.append(content)
                yield content
        self.messages.append({"role": "assistant", "content": "".join(collected).strip()})
