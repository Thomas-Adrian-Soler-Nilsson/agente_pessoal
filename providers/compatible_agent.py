import json
import time
import concurrent.futures
from typing import Callable
from pathlib import Path

from ui import ui
from memory.temporal_memory import TemporalMemory
from tools.tool_call_parser import (
    ToolArgumentsError,
    failed_tool_name,
    is_tool_json_error,
    parse_tool_arguments,
    recover_tool_call,
)
from tools.operation_state import OperationState


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
- Quando precisar de várias informações independentes entre si (por
  exemplo, ler 2-3 arquivos diferentes, ou fazer buscas separadas),
  peça todas as chamadas de ferramenta necessárias na mesma resposta
  em vez de uma por vez. Isso reduz o número de rodadas e deixa a
  conversa mais rápida. Só faça chamadas sequenciais quando uma
  realmente depender do resultado da anterior.

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

Antes de alterar um projeto, siga esta ordem: inspecione a estrutura, leia
somente os arquivos relevantes, altere incrementalmente, valide a gravação,
execute quando solicitado e verifique stdout, stderr e código de saída.
Não reconstrua arquivos grandes inteiros se edit_file ou write_file_chunk
resolverem a alteração.

Quando Thomas pedir para criar código e salvar em arquivo:

1. Gere o código.
2. Escolha um caminho apropriado.
3. Use write_file somente para arquivos pequenos. Para HTML, CSS, JS ou
    Python grandes, use write_file_chunk em blocos curtos (no máximo
    ~500 caracteres por chamada) ou edit_file. Blocos maiores arriscam
    cortar a própria chamada de ferramenta no meio do conteúdo.
4. Não peça para Thomas copiar e colar manualmente.
5. Confirme o caminho retornado pela ferramenta.

Quando Thomas pedir para executar, testar ou rodar um arquivo:

1. Verifique qual arquivo deve ser executado.
2. Use execute_file.
3. Analise STDOUT, STDERR e código de saída.
4. Se houver erro, explique o erro.
5. Quando possível, corrija o arquivo usando edit_file ou write_file_chunk.
6. Execute novamente para validar a correção.

Depois de write_file, write_file_chunk ou edit_file, confirme o resultado
com get_file_info ou uma leitura objetiva antes de declarar concluído.

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
Para analisar ou melhorar um projeto, use inspect_project primeiro. Só use
read_file ou read_file_range depois se faltar um trecho específico.
"""


# Uma tarefa real de "melhorar o site" normalmente precisa de:
# inspect_project + 1-2 read_file + várias edit_file/write_file_chunk +
# validate_file + execute_file. Com 4 rodadas, uma inspeção seguida de
# leituras redundantes já esgotava o orçamento antes de qualquer edição
# acontecer, e o modelo chegava na rodada final ainda querendo usar
# ferramentas — o que causava a falha "resumo final falhou".
MAX_TOOL_ROUNDS = 10


class CancellationRequested(Exception):
    pass


# Ferramentas somente-leitura, sem efeitos colaterais e independentes entre
# si. Quando o modelo pede várias delas na mesma resposta, executamos em
# paralelo (thread pool) em vez de uma após a outra. Escrita, navegador e
# execução de arquivo ficam de fora de propósito: têm efeitos colaterais ou
# dependem de estado compartilhado (ex.: a sessão do browser) e precisam
# rodar em sequência, na ordem pedida.
PARALLEL_SAFE_TOOLS = {
    "read_file",
    "read_file_range",
    "get_file_info",
    "list_directory",
    "search_files",
    "web_search",
    "deep_search",
    "code_search",
    "search_memory",
}


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
            "inspect_project",
            (
                "Inspeciona rapidamente um projeto: lista a estrutura imediata "
                "e lê somente arquivos de entrada relevantes. Use primeiro "
                "para analisar ou melhorar um projeto. Não combine com "
                "list_directory/read_file na mesma inspeção."
            ),
            {
                "path": {"type": "string"},
                "max_chars": {"type": "integer"},
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
            "read_file_range",
            "Lê somente um intervalo de linhas de um arquivo grande.",
            {
                "path": {"type": "string"},
                "start_line": {"type": "integer"},
                "end_line": {"type": "integer"},
            },
            ["path"],
        ),
        (
            "write_file",
            (
                "Cria ou sobrescreve um arquivo pequeno dentro das pastas "
                "permitidas pelo agente. Use quando Thomas pedir para "
                "criar um arquivo. Para arquivos grandes, prefira "
                "write_file_chunk ou edit_file."
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
                            "Conteúdo curto. Limite aproximado de 600 caracteres; "
                            "para código grande use write_file_chunk em várias chamadas."
                    ),
                },
            },
            ["path", "content"],
        ),
        (
            "write_file_chunk",
            (
                "Escreve um trecho menor em um arquivo existente ou novo. "
                "Use para dividir arquivos grandes em partes."
            ),
            {
                "path": {"type": "string"},
                "content": {"type": "string"},
                "append": {"type": "boolean"},
            },
            ["path", "content"],
        ),
        (
            "edit_file",
            (
                "Substitui exatamente um trecho existente, preservando o restante. "
                "Use para alterações localizadas e seguras."
            ),
            {
                "path": {"type": "string"},
                "find": {"type": "string"},
                "replace": {"type": "string"},
                "expected_replacements": {"type": "integer"},
            },
            ["path", "find", "replace"],
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
            "validate_file",
            "Valida sintaxe de Python/JavaScript ou estrutura básica de HTML antes da execução.",
            {"path": {"type": "string"}},
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
        self.operation_state = OperationState()
        self._inspected_roots = set()

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

    def _completion(self, cancel_event=None, **kwargs):
        for attempt in range(2):
            if cancel_event is not None and cancel_event.is_set():
                raise CancellationRequested()

            try:
                response = self.client.chat.completions.create(
                    **kwargs
                )

                if cancel_event is not None and cancel_event.is_set():
                    raise CancellationRequested()

                return response

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

                if cancel_event is not None:
                    if cancel_event.wait(5):
                        raise CancellationRequested()
                else:
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

        ui.chat_tool(
            f"memória salva [{memory['category']}]"
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
            ui.chat_tool(
                f"memória: nenhum resultado para '{query}'"
            )

            return (
                "Nenhuma memória relevante foi encontrada "
                f"para: {query}"
            )

        ui.chat_tool(
            f"memória: {len(memories)} resultado(s)"
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
            arguments = parse_tool_arguments(
                call.function.arguments or "{}"
            )

            normalized_arguments = json.dumps(
                arguments,
                ensure_ascii=False,
                sort_keys=True,
            )

        except ToolArgumentsError:
            normalized_arguments = (
                call.function.arguments or "{}"
            )

        return (
            f"{call.function.name}:"
            f"{normalized_arguments}"
        )

    def _was_inspected(self, path: str) -> bool:
        try:
            candidate = Path(path).expanduser().resolve()
            return any(
                candidate.parent == root
                for root in self._inspected_roots
            )
        except (OSError, RuntimeError, TypeError):
            return False

    def _run_tool(
        self,
        tool_name: str,
        arguments: dict,
    ):
        """
        Executa uma única ferramenta (memória ou tool_executor externo)
        e atualiza o estado da operação. Usado tanto no caminho sequencial
        quanto no paralelo.
        """

        try:

            if tool_name == "save_memory":
                result = self._save_memory(arguments)

            elif tool_name == "search_memory":
                result = self._search_memory(arguments)

            else:
                result = self.tool_executor(
                    tool_name,
                    arguments,
                )

            if tool_name == "inspect_project":
                try:
                    self._inspected_roots.add(
                        Path(arguments.get("path", "")).expanduser().resolve()
                    )
                except (OSError, RuntimeError, TypeError):
                    pass

            if tool_name in {"write_file", "write_file_chunk", "edit_file"}:
                self.operation_state.record_modified(arguments.get("path", ""))
            elif tool_name in {"read_file", "read_file_range", "inspect_project"}:
                self.operation_state.record_read(arguments.get("path", ""))
            elif tool_name == "validate_file":
                self.operation_state.validation_status = "passed" if "sucesso" in str(result).lower() else "failed"
            elif tool_name == "execute_file":
                self.operation_state.execution_status = "passed" if "código de saída: 0" in str(result).lower() else "failed"

            self.operation_state.record_success(tool_name)

            return result

        except Exception as error:

            self.operation_state.record_error(error)

            return (
                f"Erro ao executar "
                f"{tool_name}: {error}"
            )

    def _execute_tool_calls(
        self,
        tool_calls,
        executed_tool_calls=None,
        cancel_event=None,
        tool_results=None,
    ):

        if executed_tool_calls is None:
            executed_tool_calls = set()
        if tool_results is None:
            tool_results = {}

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

        # ============================================================
        # SEPARA: já executadas (cache), com erro de parsing, e
        # pendentes de execução real.
        # ============================================================

        results_by_id = {}
        pending = []

        for call in tool_calls:

            if cancel_event is not None and cancel_event.is_set():
                return

            tool_key = self._tool_call_key(call)
            self.operation_state.record_tool(call.function.name)

            if tool_key in executed_tool_calls:

                results_by_id[call.id] = tool_results.get(tool_key) or (
                    "Esta mesma ferramenta com os mesmos argumentos "
                    "já foi executada nesta solicitação. "
                    "Use o resultado anterior em vez de repetir a chamada."
                )

                ui.chat_tool(
                    call.function.name,
                    repeated=True,
                )

                continue

            try:
                arguments = parse_tool_arguments(
                    call.function.arguments or "{}"
                )

            except ToolArgumentsError as error:

                executed_tool_calls.add(tool_key)
                self.operation_state.record_error(error)

                result = (
                    f"Erro ao executar "
                    f"{call.function.name}: {error}"
                )

                tool_results[tool_key] = result
                results_by_id[call.id] = result

                ui.chat_tool(call.function.name)

                continue

            executed_tool_calls.add(tool_key)
            pending.append((call, tool_key, arguments))

        # ============================================================
        # EXECUÇÃO: chamadas somente-leitura e independentes rodam em
        # paralelo; o resto (escrita, navegador, execução) roda em
        # sequência, na ordem em que foram pedidas.
        # ============================================================

        parallel_batch = [
            item for item in pending
            if item[0].function.name in PARALLEL_SAFE_TOOLS
        ]
        sequential_batch = [
            item for item in pending
            if item[0].function.name not in PARALLEL_SAFE_TOOLS
        ]

        if parallel_batch:

            with concurrent.futures.ThreadPoolExecutor(
                max_workers=min(4, len(parallel_batch))
            ) as pool:

                futures = {
                    pool.submit(
                        self._run_tool,
                        call.function.name,
                        arguments,
                    ): (call, tool_key)
                    for call, tool_key, arguments in parallel_batch
                }

                for future in concurrent.futures.as_completed(futures):

                    call, tool_key = futures[future]
                    result = future.result()

                    tool_results[tool_key] = result
                    results_by_id[call.id] = result

                    ui.chat_tool(call.function.name)

        for call, tool_key, arguments in sequential_batch:

            if cancel_event is not None and cancel_event.is_set():
                return

            result = self._run_tool(
                call.function.name,
                arguments,
            )

            tool_results[tool_key] = result
            results_by_id[call.id] = result

            ui.chat_tool(call.function.name)

        # ============================================================
        # ANEXA MENSAGENS na ordem ORIGINAL das chamadas (independente
        # da ordem em que foram executadas de fato).
        # ============================================================

        for call in tool_calls:

            result = results_by_id.get(
                call.id,
                "Erro interno: resultado da ferramenta não encontrado.",
            )

            # --------------------------------------------------------
            # IMAGEM
            # --------------------------------------------------------

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

            # --------------------------------------------------------
            # NORMALIZAÇÃO
            # --------------------------------------------------------

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
        cancel_event=None,
    ):

        if cancel_event is not None and cancel_event.is_set():
            return

        self.messages.append(
            {
                "role": "user",
                "content": user_message,
            }
        )

        executed_tool_calls = set()
        tool_results = {}
        json_recovery_attempts = 0

        for round_index in range(
            MAX_TOOL_ROUNDS
        ):

            if cancel_event is not None and cancel_event.is_set():
                return

            allow_tools = (
                round_index
                < MAX_TOOL_ROUNDS - 1
            )

            kwargs = {
                "model": self.model,
                "messages": self.messages,
                # Decidir QUAL ferramenta chamar e com quais argumentos se
                # beneficia de menos aleatoriedade: fica mais rápido de
                # convergir e reduz repetições/leituras desnecessárias.
                # A rodada final sem ferramentas mantém temperatura maior
                # para soar mais natural.
                "temperature": 0.2 if allow_tools else 0.4,
                # Rodadas com ferramentas liberadas podem precisar gerar um
                # tool call grande (ex.: write_file_chunk com HTML/CSS/JS
                # escapado em JSON). 1200 tokens cortava a geração no meio
                # da string, produzindo JSON truncado e inválido. A rodada
                # final (sem ferramentas) continua enxuta.
                "max_completion_tokens": 4096 if allow_tools else 1200,
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
                    cancel_event=cancel_event,
                    **kwargs
                )

            except CancellationRequested:
                return

            except Exception as error:

                recovered_call = recover_tool_call(error)

                if allow_tools and recovered_call is not None:
                    ui.chat_notice(
                        "Argumentos da ferramenta reparados; continuando."
                    )
                    self._execute_tool_calls(
                        [recovered_call],
                        executed_tool_calls,
                        cancel_event=cancel_event,
                        tool_results=tool_results,
                    )
                    continue

                if (
                    allow_tools
                    and is_tool_json_error(error)
                    and json_recovery_attempts < 2
                ):
                    json_recovery_attempts += 1
                    failed_name = failed_tool_name(error)
                    ui.chat_notice(
                        "A chamada de ferramenta veio com JSON inválido. "
                        "Refazendo em formato seguro."
                    )
                    self.messages.append(
                        {
                            "role": "user",
                            "content": (
                                "A chamada anterior falhou por JSON inválido. "
                                f"Não use {failed_name or 'write_file'} com conteúdo grande. "
                                "Para arquivos grandes, use write_file_chunk em blocos "
                                "curtos ou edit_file para alterações localizadas. "
                                "Continue a tarefa a partir dos arquivos já analisados."
                            ),
                        }
                    )
                    continue

                if self._is_tool_choice_conflict(
                    error
                ):
                    if not allow_tools:
                        kwargs["tools"] = self.tools
                        kwargs["tool_choice"] = "auto"
                        allow_tools = True
                        response = self._completion(
                            cancel_event=cancel_event,
                            **kwargs
                        )
                    else:
                        raise

                else:
                    raise

            message = (
                response
                .choices[0]
                .message
            )

            # ========================================================
            # TOOL CALL
            # ========================================================

            if message.tool_calls:

                redundant_reads = bool(message.tool_calls)
                for pending_call in message.tool_calls:
                    if pending_call.function.name not in {"read_file", "read_file_range"}:
                        redundant_reads = False
                        break
                    try:
                        pending_args = parse_tool_arguments(
                            pending_call.function.arguments or "{}"
                        )
                    except ToolArgumentsError:
                        redundant_reads = False
                        break
                    if not self._was_inspected(pending_args.get("path", "")):
                        redundant_reads = False
                        break

                previous_count = len(
                    executed_tool_calls
                )

                self._execute_tool_calls(
                    message.tool_calls,
                    executed_tool_calls,
                    cancel_event=cancel_event,
                    tool_results=tool_results,
                )

                if redundant_reads:
                    ui.chat_notice(
                        "Arquivos já cobertos pela inspeção; preservando "
                        "rodadas para edição e validação."
                    )
                    # A leitura redundante não encerra a solicitação. O
                    # modelo ainda precisa receber o resultado da ferramenta
                    # e pode precisar editar os arquivos em seguida.
                    # Repetições idênticas continuam sendo interrompidas pelo
                    # teste de `current_count == previous_count` abaixo.

                current_count = len(
                    executed_tool_calls
                )

                if current_count == previous_count:

                    ui.warn(
                        "Nenhuma ferramenta nova foi executada. "
                        "Gerando o resumo com os dados já obtidos."
                    )

                    break

                continue

            # ========================================================
            # RESPOSTA FINAL
            # ========================================================

            content = self._clean_model_output(
                message.content or ""
            )

            if cancel_event is not None and cancel_event.is_set():
                return

            self.messages.append(
                {
                    "role": "assistant",
                    "content": content,
                }
            )

            if content:

                yield content
                return

            ui.chat_notice(
                "O provider retornou uma resposta vazia. Gerando um resumo de recuperação."
            )
            break

        if cancel_event is not None and cancel_event.is_set():
            return

        final_kwargs = {
            "model": self.model,
            "messages": self.messages,
            "temperature": 0.3,
            "max_completion_tokens": 1200,
        }

        if self.model in {
            "openai/gpt-oss-20b",
            "openai/gpt-oss-120b",
        }:
            final_kwargs["include_reasoning"] = False

        try:
            final_response = self._completion(
                cancel_event=cancel_event,
                **final_kwargs,
            )
            final_message = final_response.choices[0].message
            content = self._clean_model_output(
                final_message.content or ""
            )
        except CancellationRequested:
            return
        except Exception as error:

            # ----------------------------------------------------------
            # O modelo ainda insiste em usar uma ferramenta mesmo com o
            # orçamento de rodadas esgotado (ex.: quer editar antes de
            # resumir). Em vez de desistir na hora, damos mais uma
            # rodada controlada de ferramenta e só então pedimos o
            # resumo final novamente.
            # ----------------------------------------------------------

            if self._is_tool_choice_conflict(error):

                try:
                    retry_kwargs = dict(final_kwargs)
                    retry_kwargs["tools"] = self.tools
                    retry_kwargs["tool_choice"] = "auto"

                    retry_response = self._completion(
                        cancel_event=cancel_event,
                        **retry_kwargs,
                    )
                    retry_message = retry_response.choices[0].message

                    if retry_message.tool_calls:

                        self._execute_tool_calls(
                            retry_message.tool_calls,
                            executed_tool_calls,
                            cancel_event=cancel_event,
                            tool_results=tool_results,
                        )

                        final_response = self._completion(
                            cancel_event=cancel_event,
                            **final_kwargs,
                        )
                        final_message = final_response.choices[0].message
                        content = self._clean_model_output(
                            final_message.content or ""
                        )

                    else:
                        content = self._clean_model_output(
                            retry_message.content or ""
                        )

                except CancellationRequested:
                    return

                except Exception as retry_error:
                    ui.chat_notice(
                        "A análise foi concluída, mas o resumo final falhou."
                    )
                    content = (
                        "Analisei os arquivos disponíveis, mas não consegui "
                        "gerar o resumo final agora. Posso continuar a alteração "
                        "a partir do estado já lido."
                    )
                    self.operation_state.record_error(retry_error)

            else:
                ui.chat_notice(
                    "A análise foi concluída, mas o resumo final falhou."
                )
                content = (
                    "Analisei os arquivos disponíveis, mas não consegui "
                    "gerar o resumo final agora. Posso continuar a alteração "
                    "a partir do estado já lido."
                )
                self.operation_state.record_error(error)

        if cancel_event is not None and cancel_event.is_set():
            return

        self.messages.append(
            {
                "role": "assistant",
                "content": content,
            }
        )

        if content:
            yield content
        else:
            yield (
                "Analisei os arquivos disponíveis, mas o provider não retornou "
                "texto. Posso continuar a melhoria a partir do estado já lido."
            )