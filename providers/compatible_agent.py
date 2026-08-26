import json
import time
from typing import Callable

from ui import ui
from memory.temporal_memory import TemporalMemory


SYSTEM_PROMPT = """
Você é o agente pessoal do Thomas. Fale em português do Brasil.
Seja natural, informal, inteligente e levemente irônico, sem ser ofensivo.
Use as ferramentas quando forem necessárias e nunca invente conteúdo de arquivos.
Não exclua arquivos, formate nada nem execute comandos destrutivos.
Como suas respostas serão faladas, seja conciso e evite listas gigantes.

REGRAS DE FERRAMENTAS:

- Use ferramentas somente quando elas forem realmente necessárias.
- Não repita a mesma chamada de ferramenta com os mesmos argumentos.
- Se uma ferramenta já retornou informação suficiente para responder, pare de usar ferramentas.
- Para análise de código, normalmente uma única leitura do arquivo é suficiente.
- Se read_file já retornou o conteúdo de um caminho nesta solicitação,
  use esse conteúdo em vez de ler o mesmo arquivo novamente.
- Não leia novamente um arquivo apenas para confirmar o conteúdo.
- Não fique em um ciclo de ferramentas tentando obter exatamente a mesma informação.
- Depois de obter dados suficientes, produza a resposta final.

MEMÓRIA TEMPORAL:
Você possui uma memória temporal persistente local.
A memória temporal sobrevive ao encerramento do programa.

Você deve decidir por conta própria quando uma informação merece ser
lembrada para conversas futuras.

SALVE informações quando forem realmente úteis no futuro, como:
- preferências do Thomas;
- projetos que ele está desenvolvendo;
- objetivos;
- decisões importantes;
- configurações e preferências do agente;
- informações recorrentes sobre pessoas, projetos ou atividades;
- fatos pessoais relevantes para ajudar Thomas futuramente.

NÃO salve:
- conversa casual;
- perguntas comuns;
- informações que só fazem sentido naquele momento;
- respostas temporárias;
- informações irrelevantes;
- conteúdo inteiro de arquivos apenas porque foi lido.

Se Thomas disser explicitamente "lembra disso", "guarda isso",
"quero que você lembre" ou equivalente, trate isso como uma solicitação
explícita para salvar a informação.

Ao salvar uma memória:
- escreva uma informação curta e útil;
- não copie a conversa inteira;
- escolha uma categoria adequada;
- atribua uma importância entre 0.0 e 1.0.

Categorias recomendadas:
project
preference
goal
person
configuration
fact
general

Use search_memory quando uma pergunta depender de algo que pode ter sido
lembrado anteriormente.

A memória temporal NÃO substitui a memória da conversa atual.
Use a conversa atual para contexto imediato e a memória temporal para
informações persistentes.

Use open_directory para abrir uma pasta no Explorador de Arquivos.
Para Downloads, passe "Downloads" ou "OneDrive\\Downloads".
Use open_application apenas para abrir aplicativos.
Use search_files quando o usuário quiser encontrar arquivos; a busca aceita
mais de uma palavra e deve receber apenas os termos importantes do nome.
Sem pasta específica, use path "~" para procurar nas pastas permitidas.
Se encontrar o arquivo, use read_file com o caminho retornado.
Use list_directory para mostrar o conteúdo de uma pasta.

CRIAÇÃO E EXECUÇÃO DE CÓDIGO:

Quando Thomas pedir para criar código e salvar em arquivo:

1. Gere o código.
2. Escolha um caminho apropriado.
3. Use write_file para criar o arquivo.
4. Não peça para Thomas copiar e colar manualmente.
5. Confirme o caminho retornado pela ferramenta.

Quando Thomas pedir para executar, testar ou rodar um arquivo:

1. Verifique qual arquivo deve ser executado.
2. Use execute_file.
3. Analise STDOUT, STDERR e código de saída.
4. Se houver erro, explique o erro.
5. Quando possível, corrija o arquivo usando write_file.
6. Execute novamente para validar a correção.

Para páginas HTML:
- crie os arquivos necessários;
- use execute_file no index.html para abrir no navegador.

Para projetos com múltiplos arquivos:
- crie cada arquivo necessário individualmente;
- mantenha todos na mesma pasta do projeto;
- depois execute o arquivo de entrada apropriado.

Nunca diga para Thomas criar manualmente um arquivo que você consegue criar usando write_file.

Use web_search como primeira opção sempre que Thomas pedir para
pesquisar, procurar ou ler conteúdo da internet. É rápida, não depende
de navegador instalado e não trava a sessão de voz.
Use browser_navigate apenas quando web_search falhar,
ou quando o site exigir interação real.

Use deep_search apenas quando Thomas pedir explicitamente uma pesquisa
profunda, completa, detalhada, aprofundada, ou quiser comparar
informações de várias fontes diferentes.
Para perguntas simples e rápidas, prefira sempre web_search.

Você pode chamar ferramentas de pesquisa mais de uma vez na mesma resposta
quando a primeira busca não trouxer informação suficiente, mas evite
repetir exatamente a mesma consulta.

Use generate_image quando Thomas pedir para criar, gerar ou desenhar uma
imagem. Escreva um prompt descritivo e detalhado.

Considere sempre o resultado da ferramenta como a fonte da verdade.
Nunca invente nomes, tipos ou conteúdos de arquivos.
Se o resultado estiver vazio, informe que não encontrou dados e peça um
caminho ou nome mais específico.

Depois de uma operação de arquivo, descreva somente o que foi retornado agora.
"""


MAX_TOOL_ROUNDS = 4


def build_tools():
    definitions = [
        (
            "open_application",
            "Abre um aplicativo instalado no computador.",
            {
                "application": {
                    "type": "string"
                }
            },
            ["application"],
        ),
        (
            "open_directory",
            "Abre uma pasta no Explorador de Arquivos.",
            {
                "path": {
                    "type": "string"
                }
            },
            ["path"],
        ),
        (
            "open_url",
            "Abre uma URL no navegador.",
            {
                "url": {
                    "type": "string"
                }
            },
            ["url"],
        ),
        (
            "web_search",
            (
                "Pesquisa um termo na internet via requisição HTTP direta "
                "e retorna o conteúdo do resultado com a URL de origem."
            ),
            {
                "query": {
                    "type": "string",
                    "description": "Termos da pesquisa.",
                }
            },
            ["query"],
        ),
        (
            "deep_search",
            (
                "Faz uma pesquisa profunda na web, lendo várias fontes "
                "para dar uma resposta completa e bem embasada."
            ),
            {
                "query": {
                    "type": "string",
                    "description": "Termos da pesquisa profunda.",
                }
            },
            ["query"],
        ),
        (
            "code_search",
            (
                "Pesquisa técnica focada em programação, bibliotecas, "
                "pacotes Python, documentação, Stack Overflow e GitHub."
            ),
            {
                "query": {
                    "type": "string",
                    "description": "Nome do pacote/lib ou pergunta técnica.",
                }
            },
            ["query"],
        ),
        (
            "browser_navigate",
            "Abre uma página em uma sessão persistente do navegador.",
            {
                "url": {
                    "type": "string"
                }
            },
            ["url"],
        ),
        (
            "browser_read",
            "Lê o texto visível da página atualmente aberta.",
            {
                "max_chars": {
                    "type": "integer"
                }
            },
            [],
        ),
        (
            "browser_click",
            "Clica em um elemento da página usando um seletor.",
            {
                "selector": {
                    "type": "string"
                }
            },
            ["selector"],
        ),
        (
            "browser_fill",
            "Preenche um campo da página usando um seletor.",
            {
                "selector": {
                    "type": "string"
                },
                "value": {
                    "type": "string"
                },
            },
            ["selector", "value"],
        ),
        (
            "list_directory",
            "Lista arquivos e pastas de um diretório.",
            {
                "path": {
                    "type": "string"
                }
            },
            ["path"],
        ),
        (
            "search_files",
            "Procura arquivos pelo nome em uma pasta.",
            {
                "query": {
                    "type": "string"
                },
                "path": {
                    "type": "string"
                },
            },
            ["query"],
        ),
        (
            "read_file",
            (
                "Lê o conteúdo extraível de arquivos TXT, PDF, DOCX "
                "e formatos de texto permitidos. "
                "Não repita a leitura do mesmo caminho na mesma solicitação "
                "quando o conteúdo já tiver sido retornado."
            ),
            {
                "path": {
                    "type": "string"
                }
            },
            ["path"],
        ),
        (
            "write_file",
            (
                "Cria ou sobrescreve um arquivo dentro das pastas "
                "permitidas pelo agente. Use quando Thomas pedir para "
                "criar, salvar, atualizar ou escrever código em um arquivo. "
                "O conteúdo deve ser fornecido integralmente. "
                "Não peça para Thomas copiar e colar manualmente."
            ),
            {
                "path": {
                    "type": "string",
                    "description": (
                        "Caminho completo ou relativo do arquivo."
                    ),
                },
                "content": {
                    "type": "string",
                    "description": (
                        "Conteúdo completo que será gravado no arquivo."
                    ),
                },
            },
            ["path", "content"],
        ),
        (
            "execute_file",
            (
                "Executa um arquivo usando um runtime permitido. "
                "Use depois de criar ou modificar um programa quando "
                "Thomas pedir para executar, testar ou rodar o arquivo. "
                "Python (.py), JavaScript (.js) e HTML (.html/.htm) "
                "são suportados diretamente."
            ),
            {
                "path": {
                    "type": "string",
                    "description": (
                        "Caminho do arquivo que será executado."
                    ),
                },
            },
            ["path"],
        ),
        (
            "get_file_info",
            "Obtém informações de um arquivo.",
            {
                "path": {
                    "type": "string"
                }
            },
            ["path"],
        ),
        (
            "capture_screen",
            "Captura a tela atual do computador.",
            {},
            [],
        ),
        (
            "capture_webcam",
            "Captura uma imagem atual da webcam.",
            {},
            [],
        ),
        (
            "generate_image",
            (
                "Gera uma imagem a partir de uma descrição "
                "usando a Hugging Face Inference API."
            ),
            {
                "prompt": {
                    "type": "string",
                    "description": "Descrição detalhada da imagem.",
                }
            },
            ["prompt"],
        ),
        (
            "save_memory",
            (
                "Salva uma informação importante sobre Thomas "
                "na memória temporal persistente."
            ),
            {
                "content": {
                    "type": "string",
                    "description": "Informação curta e útil.",
                },
                "category": {
                    "type": "string",
                    "enum": [
                        "project",
                        "preference",
                        "goal",
                        "person",
                        "configuration",
                        "fact",
                        "general",
                    ],
                },
                "importance": {
                    "type": "number",
                    "minimum": 0,
                    "maximum": 1,
                },
            },
            ["content", "category", "importance"],
        ),
        (
            "search_memory",
            (
                "Pesquisa informações previamente armazenadas "
                "na memória temporal persistente."
            ),
            {
                "query": {
                    "type": "string",
                    "description": "Termos importantes para procurar.",
                },
                "limit": {
                    "type": "integer",
                    "minimum": 1,
                    "maximum": 10,
                },
            },
            ["query"],
        ),
    ]

    return [
        {
            "type": "function",
            "function": {
                "name": name,
                "description": description,
                "parameters": {
                    "type": "object",
                    "properties": properties,
                    "required": required,
                },
            },
        }
        for name, description, properties, required in definitions
    ]


class CompatibleAgent:

    def __init__(
        self,
        client,
        model: str,
        tool_executor: Callable,
        messages=None,
    ):
        self.client = client
        self.model = model
        self.tool_executor = tool_executor

        self.tools = build_tools()

        self.temporal_memory = TemporalMemory()

        self.messages = (
            messages
            if messages is not None
            else [
                {
                    "role": "system",
                    "content": SYSTEM_PROMPT,
                }
            ]
        )

    def set_personality(self, personality: str):
        if not personality:
            return

        instruction = (
            "\n\n"
            "INSTRUÇÃO PRIORITÁRIA DE ROLEPLAY - PERSONA SELECIONADA:"
            + personality
            + "\nEsta instrução substitui a identidade genérica de agente pessoal, "
            "mas não substitui as regras de segurança, privacidade e uso de ferramentas. "
            "Mantenha a persona sem perder precisão, segurança e concisão."
        )

        if (
            self.messages
            and self.messages[0].get("role") == "system"
        ):
            self.messages[0]["content"] += instruction

    # ============================================================
    # CONTEXTO
    # ============================================================

    def _shrink_context(self, max_chars: int = 2500):
        for message in self.messages:
            content = message.get("content")

            if (
                isinstance(content, str)
                and len(content) > max_chars
            ):
                message["content"] = (
                    content[:max_chars]
                    + "\n\n[TRUNCADO PARA CABER NO LIMITE DO MODELO]"
                )

    def _is_too_large(self, error) -> bool:
        """
        Detecta erros de contexto/payload grande.
        """

        text = str(error).lower()

        indicators = (
            "context length",
            "maximum context",
            "max context",
            "context window",
            "too many tokens",
            "token limit",
            "request too large",
            "payload too large",
            "prompt is too long",
            "maximum tokens",
            "413",
        )

        return any(
            indicator in text
            for indicator in indicators
        )

    def _is_tool_choice_conflict(self, error) -> bool:
        text = str(error).lower()

        return (
            "tool choice is none" in text
            and "called a tool" in text
        )

    # ============================================================
    # LIMPEZA DE RESPOSTA
    # ============================================================

    @staticmethod
    def _clean_model_output(content: str) -> str:
        if not content:
            return ""

        end_tokens = (
            "<|endoftext|>",
            "<|end|>",
            "<|return|>",
            "<|eot_id|>",
            "<|eom_id|>",
        )

        for token in end_tokens:
            if token in content:
                content = content.split(
                    token,
                    1,
                )[0]

        special_tokens = (
            "<|start|>",
            "<|assistant|>",
            "<|user|>",
            "<|system|>",
            "<|channel|>",
            "<|message|>",
            "<|analysis|>",
            "<|final|>",
        )

        for token in special_tokens:
            content = content.replace(
                token,
                "",
            )

        return content.strip()

    # ============================================================
    # COMPLETION
    # ============================================================

    def _completion(self, **kwargs):
        for attempt in range(2):
            try:
                return self.client.chat.completions.create(
                    **kwargs
                )

            except Exception as error:

                if (
                    self._is_too_large(error)
                    and attempt == 0
                ):
                    ui.warn(
                        "Pedido grande demais. "
                        "Reduzindo o contexto e tentando novamente..."
                    )

                    self._shrink_context()

                    kwargs["messages"] = self.messages

                    continue

                status_code = getattr(
                    error,
                    "status_code",
                    None,
                )

                if (
                    status_code != 429
                    or attempt == 1
                ):
                    raise

                ui.warn(
                    "Limite temporário atingido. "
                    "Tentando novamente em 5 segundos..."
                )

                time.sleep(5)

    # ============================================================
    # MEMÓRIA
    # ============================================================

    def _save_memory(
        self,
        arguments: dict,
    ) -> str:

        content = str(
            arguments.get(
                "content",
                "",
            )
        ).strip()

        category = str(
            arguments.get(
                "category",
                "general",
            )
        ).strip()

        importance = arguments.get(
            "importance",
            0.5,
        )

        if not content:
            return (
                "Não foi possível salvar a memória: "
                "o conteúdo está vazio."
            )

        try:
            importance = float(
                importance
            )
        except (
            TypeError,
            ValueError,
        ):
            importance = 0.5

        importance = max(
            0.0,
            min(
                1.0,
                importance,
            ),
        )

        memory = self.temporal_memory.add(
            content=content,
            category=category,
            importance=importance,
        )

        ui.console.print(
            f"\n[info]🧠 IA → memória salva[/info] "
            f"[muted]\\[{memory['category']}][/muted]"
        )

        return (
            "Memória salva com sucesso. "
            f"ID: {memory['id']}"
        )

    def _search_memory(
        self,
        arguments: dict,
    ) -> str:

        query = str(
            arguments.get(
                "query",
                "",
            )
        ).strip()

        if not query:
            return (
                "Nenhum termo de pesquisa foi informado."
            )

        try:
            limit = int(
                arguments.get(
                    "limit",
                    8,
                )
            )
        except (
            TypeError,
            ValueError,
        ):
            limit = 8

        limit = max(
            1,
            min(
                10,
                limit,
            ),
        )

        memories = self.temporal_memory.search(
            query=query,
            limit=limit,
        )

        if not memories:
            ui.console.print(
                f"\n[info]🧠 IA → memória:[/info] "
                f"nenhum resultado para '{query}'"
            )

            return (
                "Nenhuma memória relevante foi encontrada "
                f"para: {query}"
            )

        ui.console.print(
            f"\n[info]🧠 IA → memória:[/info] "
            f"{len(memories)} resultado(s)"
        )

        result = []

        for memory in memories:
            result.append(
                {
                    "id": memory.get("id"),
                    "category": memory.get(
                        "category",
                        "general",
                    ),
                    "content": memory.get(
                        "content",
                        "",
                    ),
                    "importance": memory.get(
                        "importance",
                        0.5,
                    ),
                }
            )

        return json.dumps(
            result,
            ensure_ascii=False,
        )

    # ============================================================
    # TOOL CALLS
    # ============================================================

    def _tool_call_key(self, call) -> str:
        try:
            arguments = json.loads(
                call.function.arguments or "{}"
            )

            normalized_arguments = json.dumps(
                arguments,
                ensure_ascii=False,
                sort_keys=True,
            )

        except Exception:
            normalized_arguments = (
                call.function.arguments or "{}"
            )

        return (
            f"{call.function.name}:"
            f"{normalized_arguments}"
        )

    def _execute_tool_calls(
        self,
        tool_calls,
        executed_tool_calls=None,
    ):

        if executed_tool_calls is None:
            executed_tool_calls = set()

        payload = [
            {
                "id": call.id,
                "type": "function",
                "function": {
                    "name": call.function.name,
                    "arguments": call.function.arguments,
                },
            }
            for call in tool_calls
        ]

        self.messages.append(
            {
                "role": "assistant",
                "content": "",
                "tool_calls": payload,
            }
        )

        for call in tool_calls:

            tool_key = self._tool_call_key(
                call
            )

            if tool_key in executed_tool_calls:

                result = (
                    "Esta mesma ferramenta com os mesmos argumentos "
                    "já foi executada nesta solicitação. "
                    "Use o resultado anterior em vez de repetir a chamada."
                )

                ui.console.print(
                    f"\n[warn]🔁 Ferramenta repetida ignorada:[/warn] "
                    f"{call.function.name}()"
                )

            else:

                executed_tool_calls.add(
                    tool_key
                )

                try:

                    arguments = json.loads(
                        call.function.arguments or "{}"
                    )

                    tool_name = call.function.name

                    if tool_name == "save_memory":

                        result = self._save_memory(
                            arguments
                        )

                    elif tool_name == "search_memory":

                        result = self._search_memory(
                            arguments
                        )

                    else:

                        result = self.tool_executor(
                            tool_name,
                            arguments,
                        )

                except Exception as error:

                    result = (
                        f"Erro ao executar "
                        f"{call.function.name}: {error}"
                    )

                ui.console.print(
                    f"\n[info]🔧 IA →[/info] "
                    f"[bold]{call.function.name}()[/bold]"
                )

            # ========================================================
            # IMAGEM
            # ========================================================

            if (
                isinstance(result, dict)
                and result.get("type") == "image"
            ):

                self.messages.append(
                    {
                        "role": "tool",
                        "tool_call_id": call.id,
                        "content": result.get(
                            "description",
                            "Imagem capturada.",
                        ),
                    }
                )

                self.messages.append(
                    {
                        "role": "user",
                        "content": [
                            {
                                "type": "text",
                                "text": (
                                    "Analise esta imagem e responda "
                                    "à solicitação original."
                                ),
                            },
                            {
                                "type": "image_url",
                                "image_url": {
                                    "url": (
                                        "data:image/jpeg;base64,"
                                        + result["data"]
                                    )
                                },
                            },
                        ],
                    }
                )

                continue

            # ========================================================
            # NORMALIZAÇÃO
            # ========================================================

            if not isinstance(
                result,
                str,
            ):
                result = json.dumps(
                    result,
                    ensure_ascii=False,
                )

            self.messages.append(
                {
                    "role": "tool",
                    "tool_call_id": call.id,
                    "content": result,
                }
            )

    # ============================================================
    # CHAT
    # ============================================================

    def ask_stream(
        self,
        user_message: str,
    ):

        self.messages.append(
            {
                "role": "user",
                "content": user_message,
            }
        )

        executed_tool_calls = set()

        for round_index in range(
            MAX_TOOL_ROUNDS
        ):

            allow_tools = (
                round_index
                < MAX_TOOL_ROUNDS - 1
            )

            kwargs = {
                "model": self.model,
                "messages": self.messages,
                "temperature": 0.4,
                "max_completion_tokens": 1200,
            }

            # ========================================================
            # GPT-OSS
            # ========================================================

            if self.model in {
                "openai/gpt-oss-20b",
                "openai/gpt-oss-120b",
            }:

                kwargs["include_reasoning"] = False

            # ========================================================
            # TOOLS
            # ========================================================

            if allow_tools:

                kwargs["tools"] = self.tools
                kwargs["tool_choice"] = "auto"

            try:

                response = self._completion(
                    **kwargs
                )

            except Exception as error:

                if self._is_tool_choice_conflict(
                    error
                ):
                    yield (
                        "Desculpa, me perdi tentando usar uma "
                        "ferramenta nessa resposta. "
                        "Pode repetir o pedido de um jeito mais direto?"
                    )
                    return

                raise

            message = (
                response
                .choices[0]
                .message
            )

            # ========================================================
            # TOOL CALL
            # ========================================================

            if (
                allow_tools
                and message.tool_calls
            ):

                previous_count = len(
                    executed_tool_calls
                )

                self._execute_tool_calls(
                    message.tool_calls,
                    executed_tool_calls,
                )

                current_count = len(
                    executed_tool_calls
                )

                if current_count == previous_count:

                    ui.warn(
                        "Nenhuma ferramenta nova foi executada. "
                        "Encerrando o ciclo de ferramentas."
                    )

                    allow_tools = False

                continue

            # ========================================================
            # RESPOSTA FINAL
            # ========================================================

            content = self._clean_model_output(
                message.content or ""
            )

            self.messages.append(
                {
                    "role": "assistant",
                    "content": content,
                }
            )

            if content:

                yield content
                return

            yield (
                "Não consegui gerar uma resposta agora. "
                "Tente novamente ou reformule o pedido."
            )

            return
