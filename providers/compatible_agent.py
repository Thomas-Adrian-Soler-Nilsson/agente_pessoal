import json
import time
from typing import Callable

SYSTEM_PROMPT = """
Você é o agente pessoal do Thomas. Fale em português do Brasil.
Seja natural, informal, inteligente e levemente irônico, sem ser ofensivo.
Use as ferramentas quando forem necessárias e nunca invente conteúdo de arquivos.
Não exclua arquivos, formate nada nem execute comandos destrutivos.
Como suas respostas serão faladas, seja conciso e evite listas gigantes.
Quando uma sessão usar Fish Audio, os marcadores de emoção serão adicionados
pela personalidade selecionada e devem ser preservados na resposta.

Use open_directory para abrir uma pasta no Explorador de Arquivos.
Para Downloads, passe "Downloads" ou "OneDrive\\Downloads".
Use open_application apenas para abrir aplicativos.
Use search_files quando o usuário quiser encontrar arquivos; a busca aceita
mais de uma palavra e deve receber apenas os termos importantes do nome.
Sem pasta específica, use path "~" para procurar nas pastas permitidas.
Se encontrar o arquivo, use read_file com o caminho retornado.
Use list_directory para mostrar o conteúdo de uma pasta.
Considere sempre o resultado da ferramenta como a fonte da verdade. Nunca
invente nomes, tipos ou conteúdos de arquivos. Se o resultado estiver vazio,
informe que não encontrou dados e peça um caminho ou nome mais específico.
Depois de uma operação de arquivo, descreva somente o que foi retornado agora.
"""


def build_tools():
    definitions = [
        ("open_application", "Abre um aplicativo instalado no computador.", {"application": {"type": "string"}}, ["application"]),
        ("open_directory", "Abre uma pasta no Explorador de Arquivos.", {"path": {"type": "string"}}, ["path"]),
        ("open_url", "Abre uma URL no navegador.", {"url": {"type": "string"}}, ["url"]),
        ("list_directory", "Lista arquivos e pastas de um diretório.", {"path": {"type": "string"}}, ["path"]),
        ("search_files", "Procura arquivos pelo nome em uma pasta.", {"query": {"type": "string"}, "path": {"type": "string"}}, ["query"]),
        ("read_file", "Lê o conteúdo extraível de arquivos TXT, PDF, DOCX e formatos de texto permitidos.", {"path": {"type": "string"}}, ["path"]),
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

    def set_personality(self, personality: str):
        if not personality:
            return
        instruction = (
            "\n\nINSTRUÇÃO PRIORITÁRIA DE ROLEPLAY - PERSONA SELECIONADA:"
            + personality
            + "\nEsta instrução substitui a identidade genérica de agente pessoal, "
            "mas não substitui as regras de segurança, privacidade e uso de ferramentas. "
            "Mantenha a persona sem perder precisão, segurança e concisão."
        )
        if self.messages and self.messages[0].get("role") == "system":
            self.messages[0]["content"] += instruction

    def _shrink_context(self, max_chars: int = 2500):
        for message in self.messages:
            content = message.get("content")
            if isinstance(content, str) and len(content) > max_chars:
                message["content"] = (
                    content[:max_chars]
                    + "\n\n[TRUNCADO PARA CABER NO LIMITE DO MODELO]"
                )

    def _is_too_large(self, error) -> bool:
        status = getattr(error, "status_code", None)
        text = str(error).lower()
        return status == 413 or "request too large" in text or "tokens per minute" in text

    def _completion(self, **kwargs):
        for attempt in range(2):
            try:
                return self.client.chat.completions.create(**kwargs)
            except Exception as error:
                if self._is_too_large(error) and attempt == 0:
                    print("\n⚠️ Pedido grande demais. Enviando um resumo menor do arquivo...")
                    self._shrink_context()
                    kwargs["messages"] = self.messages
                    continue
                if getattr(error, "status_code", None) != 429 or attempt == 1:
                    raise
                print("\n⚠️ Limite temporário atingido. Tentando novamente em 5 segundos...")
                time.sleep(5)

    def _execute_tool_calls(self, tool_calls):
        payload = [
            {
                "id": call.id,
                "type": "function",
                "function": {"name": call.function.name, "arguments": call.function.arguments},
            }
            for call in tool_calls
        ]
        self.messages.append({"role": "assistant", "content": "", "tool_calls": payload})
        for call in tool_calls:
            try:
                arguments = json.loads(call.function.arguments or "{}")
                result = self.tool_executor(call.function.name, arguments)
            except Exception as error:
                result = f"Erro ao executar {call.function.name}: {error}"
            print(f"\n🔧 IA → {call.function.name}()")
            if isinstance(result, dict) and result.get("type") == "image":
                self.messages.append(
                    {
                        "role": "tool",
                        "tool_call_id": call.id,
                        "content": result.get("description", "Imagem capturada."),
                    }
                )
                self.messages.append(
                    {
                        "role": "user",
                        "content": [
                            {"type": "text", "text": "Analise esta imagem e responda à solicitação original."},
                            {"type": "image_url", "image_url": {"url": f"data:image/jpeg;base64,{result['data']}"}},
                        ],
                    }
                )
                continue
            if not isinstance(result, str):
                result = json.dumps(result, ensure_ascii=False)
            self.messages.append({"role": "tool", "tool_call_id": call.id, "content": result})

    def ask_stream(self, user_message: str):
        self.messages.append({"role": "user", "content": user_message})
        for round_index in range(5):
            allow_tools = round_index < 4
            kwargs = {
                "model": self.model,
                "messages": self.messages,
                "temperature": 0.7,
                "max_completion_tokens": 300,
            }
            if allow_tools:
                kwargs["tools"] = self.tools
                kwargs["tool_choice"] = "auto"
            response = self._completion(**kwargs)
            message = response.choices[0].message
            if allow_tools and message.tool_calls:
                self._execute_tool_calls(message.tool_calls)
                continue

            content = (message.content or "").strip()
            self.messages.append({"role": "assistant", "content": content})
            if content:
                yield content
                return
            yield "Não consegui gerar uma resposta agora. Tente novamente ou reformule o pedido."
            return
