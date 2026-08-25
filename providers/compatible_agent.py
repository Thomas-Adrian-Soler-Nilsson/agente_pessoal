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

Use generate_image quando Thomas pedir para criar, gerar ou desenhar uma
imagem. Escreva um prompt descritivo e detalhado (de preferência em
inglês) a partir do pedido dele.

Use browser_search quando Thomas pedir para pesquisar, procurar ou achar
alguma informação na internet e você não tiver uma URL exata. Essa
ferramenta já pesquisa, abre o primeiro resultado e retorna o conteúdo
lido em uma única chamada — não é necessário chamar outras ferramentas
de navegador depois dela. Sempre cite a URL retornada como fonte.
Use browser_navigate apenas quando Thomas já forneceu ou você já sabe a
URL exata que deve ser aberta. Essa ferramenta já retorna o conteúdo da
página automaticamente, então não é necessário chamar browser_read logo
em seguida na maioria dos casos.
Use browser_read apenas se precisar reler a página atual mais tarde,
depois de já ter navegado ou clicado em algo.
Use browser_click com um seletor CSS para clicar em elementos da página
atualmente aberta na sessão automatizada.
Use browser_fill com um seletor CSS e um valor para preencher campos de
formulário na página atualmente aberta.
A sessão do navegador automatizado é persistente entre pedidos: não é
necessário abrir a página de novo se ela já estiver aberta, a menos que
Thomas peça para navegar para outro lugar.
Use open_url apenas quando o pedido for simplesmente abrir um site no
navegador comum do usuário, sem necessidade de leitura, clique ou
preenchimento automatizado — por exemplo, quando Thomas só quer ver a
página com os próprios olhos.

Considere sempre o resultado da ferramenta como a fonte da verdade.
Nunca invente nomes, tipos ou conteúdos de arquivos.
Se o resultado estiver vazio, informe que não encontrou dados e peça um
caminho ou nome mais específico.

Depois de uma operação de arquivo, descreva somente o que foi retornado agora.
"""


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
            "browser_navigate",
            "Abre uma página em uma sessão persistente do navegador automatizado.",
            {"url": {"type": "string"}},
            ["url"],
        ),
        (
            "browser_search",
            (
                "Pesquisa um termo na web usando o navegador automatizado "
                "e retorna o conteúdo do primeiro resultado, incluindo a "
                "URL de origem (fonte). Use sempre que Thomas pedir para "
                "pesquisar, procurar ou achar informações na internet sem "
                "fornecer uma URL exata."
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
            "browser_read",
            "Lê o texto visível da página atualmente aberta no navegador automatizado.",
            {"max_chars": {"type": "integer"}},
            [],
        ),
        (
            "browser_click",
            "Clica em um elemento da página usando um seletor CSS ou texto compatível.",
            {"selector": {"type": "string"}},
            ["selector"],
        ),
        (
            "browser_fill",
            "Preenche um campo da página usando um seletor CSS.",
            {
                "selector": {"type": "string"},
                "value": {"type": "string"},
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
            "Lê o conteúdo extraível de arquivos TXT, PDF, DOCX e formatos de texto permitidos.",
            {
                "path": {
                    "type": "string"
                }
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
                "Gera uma imagem a partir de uma descrição em texto usando "
                "a API de geração de imagens da Hugging Face, salva o "
                "arquivo localmente e abre para visualização."
            ),
            {
                "prompt": {
                    "type": "string",
                    "description": (
                        "Descrição detalhada da imagem a ser gerada. "
                        "Prefira descrever em inglês para melhores resultados."
                    ),
                }
            },
            ["prompt"],
        ),

        # ========================================================
        # MEMÓRIA TEMPORAL
        # ========================================================

        (
            "save_memory",
            (
                "Salva uma informação importante sobre Thomas na memória "
                "temporal persistente. Use somente quando a informação "
                "for realmente útil em conversas futuras ou quando Thomas "
                "pedir explicitamente para lembrar."
            ),
            {
                "content": {
                    "type": "string",
                    "description": (
                        "Informação curta e útil que deve ser lembrada."
                    ),
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
                    "description": "Categoria da memória.",
                },
                "importance": {
                    "type": "number",
                    "minimum": 0,
                    "maximum": 1,
                    "description": (
                        "Importância da memória entre 0.0 e 1.0."
                    ),
                },
            },
            ["content", "category", "importance"],
        ),
        (
            "search_memory",
            (
                "Pesquisa informações previamente armazenadas na memória "
                "temporal persistente. Use quando a resposta depender de "
                "algo que Thomas possa ter contado anteriormente."
            ),
            {
                "query": {
                    "type": "string",
                    "description": (
                        "Termos importantes para procurar na memória."
                    ),
                },
                "limit": {
                    "type": "integer",
                    "minimum": 1,
                    "maximum": 10,
                    "description": (
                        "Quantidade máxima de memórias retornadas."
                    ),
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


# ============================================================
# SUPORTE A VISÃO
# ============================================================

VISION_MODEL_HINTS = (
    "vision",
    "llava",
    "pixtral",
    "gpt-4o",
    "gpt-4-vision",
    "gemini",
    "claude",
    "llama-3.2-11b-vision",
    "llama-3.2-90b-vision",
    "qwen2-vl",
    "qwen2.5-vl",
)


def model_supports_vision(model: str) -> bool:
    model = (model or "").lower()
    return any(hint in model for hint in VISION_MODEL_HINTS)


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

        # Memória temporal persistente.
        self.temporal_memory = TemporalMemory()

        # Memória momentânea da conversa atual.
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
        status = getattr(
            error,
            "status_code",
            None,
        )

        text = str(error).lower()

        return (
            status == 413
            or "request too large" in text
            or "tokens per minute" in text
        )

    # ============================================================
    # LIMPEZA DE RESPOSTA
    # ============================================================

    @staticmethod
    def _clean_model_output(content: str) -> str:
        """
        Remove tokens especiais que alguns modelos podem retornar.

        Isso é especialmente importante para modelos GPT-OSS,
        pois esses tokens nunca devem chegar ao TTS.
        """

        if not content:
            return ""

        # Tokens que indicam encerramento da geração.
        end_tokens = (
            "<|endoftext|>",
            "<|end|>",
            "<|return|>",
            "<|eot_id|>",
            "<|eom_id|>",
        )

        # Se algum token de encerramento aparecer,
        # tudo depois dele é descartado.
        for token in end_tokens:
            if token in content:
                content = content.split(
                    token,
                    1,
                )[0]

        # Remove tokens especiais restantes.
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
                        "Enviando um resumo menor do contexto..."
                    )

                    self._shrink_context()

                    kwargs["messages"] = self.messages

                    continue

                if (
                    getattr(
                        error,
                        "status_code",
                        None,
                    )
                    != 429
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

    def _execute_tool_calls(
        self,
        tool_calls,
    ):
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

            try:
                arguments = json.loads(
                    call.function.arguments or "{}"
                )

                tool_name = call.function.name

                # ====================================================
                # MEMÓRIA TEMPORAL
                # ====================================================

                if tool_name == "save_memory":
                    result = self._save_memory(
                        arguments
                    )

                elif tool_name == "search_memory":
                    result = self._search_memory(
                        arguments
                    )

                # ====================================================
                # OUTRAS FERRAMENTAS
                # ====================================================

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
                f"\n[info]🔧 IA →[/info] [bold]{call.function.name}()[/bold]"
            )

            # ========================================================
            # IMAGEM
            # ========================================================

            if (
                isinstance(result, dict)
                and result.get("type") == "image"
            ):
                if model_supports_vision(self.model):
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
                else:
                    self.messages.append(
                        {
                            "role": "tool",
                            "tool_call_id": call.id,
                            "content": (
                                result.get(
                                    "description",
                                    "Imagem capturada.",
                                )
                                + " O modelo atual não tem suporte a "
                                "visão, então a imagem não pôde ser "
                                "analisada. Informe a Thomas que ele "
                                "precisa trocar para um modelo com "
                                "suporte a imagens (ex: um modelo "
                                "vision) para que a análise visual "
                                "funcione."
                            ),
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

        for round_index in range(6):

            allow_tools = round_index < 5

            kwargs = {
                "model": self.model,
                "messages": self.messages,
                "temperature": 0.4,
                "max_completion_tokens": 700,
            }

            # ========================================================
            # GPT-OSS
            # ========================================================

            if self.model in {
                "openai/gpt-oss-20b",
                "openai/gpt-oss-120b",
            }:
                # Não queremos que o reasoning seja retornado
                # junto da resposta que será enviada ao TTS.
                kwargs["include_reasoning"] = False

            # ========================================================
            # TOOLS
            # ========================================================

            if allow_tools:
                kwargs["tools"] = self.tools
                kwargs["tool_choice"] = "auto"

            response = self._completion(
                **kwargs
            )

            message = response.choices[0].message

            # ========================================================
            # TOOL CALL
            # ========================================================

            if (
                allow_tools
                and message.tool_calls
            ):
                self._execute_tool_calls(
                    message.tool_calls
                )

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