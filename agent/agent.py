import json
import os
from typing import Callable

from dotenv import load_dotenv
from groq import Groq

from ui import ui


load_dotenv()


SYSTEM_PROMPT = """
Você é o agente pessoal do Thomas.

Você conversa com ele por voz em português do Brasil.

PERSONALIDADE:
- Fale como uma pessoa real.
- Seja natural, informal e espontâneo.
- Respostas simples devem ser curtas.
- Não transforme conversa em relatório.
- Não repita a pergunta.
- Não use listas sem necessidade.
- Evite "Claro!", "Com certeza!" e "Entendi!" repetidamente.
- Pode usar expressões naturais como "ah", "beleza", "olha",
  "sim", "bom" e "mano" quando fizer sentido.
- Não exagere.
- Pense que sua resposta será falada.

FERRAMENTAS:
Você pode acessar a tela e a webcam.

capture_screen:
Use quando precisar saber o que está na tela agora.

capture_webcam:
Use quando precisar ver o ambiente ou o usuário agora.

start_screen_watch:
Use quando o usuário pedir acompanhamento contínuo da tela.

start_webcam_watch:
Use quando o usuário pedir acompanhamento contínuo da webcam.

stop_watch:
Use quando o usuário quiser parar o acompanhamento.

get_latest_observation:
Use quando precisar saber a última observação feita pelo watcher.

get_watch_status:
Use quando precisar saber se existe acompanhamento ativo.

IMPORTANTE:
A decisão de usar ferramentas é sua.
Não espere o Python interpretar palavras-chave.

Quando uma ferramenta de imagem for usada, a imagem será analisada
pelo sistema visual Qwen e você receberá a análise textual dela.

Nunca diga que não consegue ver a tela se a ferramenta de visão
acabou de fornecer uma análise.
"""


class Agent:

    def __init__(
        self,
        tool_executor: Callable,
        tools: list[dict],
    ):

        api_key = os.getenv(
            "GROQ_API_KEY"
        )

        if not api_key:
            raise ValueError(
                "GROQ_API_KEY não encontrada no .env"
            )

        self.client = Groq(
            api_key=api_key
        )

        self.chat_model = (
            "openai/gpt-oss-20b"
        )

        self.vision_model = (
            "qwen/qwen3.6-27b"
        )

        self.tool_executor = (
            tool_executor
        )

        self.tools = tools

        self.messages = [
            {
                "role": "system",
                "content": SYSTEM_PROMPT,
            }
        ]

    # ==========================================================
    # CONVERSA
    # ==========================================================

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

        # ------------------------------------------------------
        # PRIMEIRA FASE:
        # GPT-OSS decide se precisa de ferramenta.
        #
        # Não fazemos streaming aqui porque queremos tool
        # calling estável e rápido.
        # ------------------------------------------------------

        response = (
            self.client
            .chat
            .completions
            .create(
                model=self.chat_model,
                messages=self.messages,
                tools=self.tools,
                tool_choice="auto",
                temperature=0.65,
                max_completion_tokens=250,
                reasoning_effort="low",
                include_reasoning=False,
                stream=False,
            )
        )

        message = (
            response
            .choices[0]
            .message
        )

        # ------------------------------------------------------
        # SEM TOOL
        # ------------------------------------------------------

        if not message.tool_calls:

            content = (
                message.content
                or ""
            ).strip()

            self.messages.append(
                {
                    "role": "assistant",
                    "content": content,
                }
            )

            if content:
                yield content

            return

        # ------------------------------------------------------
        # REGISTRAR TOOL CALLS
        # ------------------------------------------------------

        tool_calls_payload = []

        for call in message.tool_calls:

            tool_calls_payload.append(
                {
                    "id": call.id,
                    "type": "function",
                    "function": {
                        "name": (
                            call.function.name
                        ),
                        "arguments": (
                            call.function.arguments
                        ),
                    },
                }
            )

        self.messages.append(
            {
                "role": "assistant",
                "content": (
                    message.content
                    or ""
                ),
                "tool_calls": (
                    tool_calls_payload
                ),
            }
        )

        # ------------------------------------------------------
        # EXECUTAR
        # ------------------------------------------------------

        for call in message.tool_calls:

            name = call.function.name

            try:
                arguments = json.loads(
                    call.function.arguments
                    or "{}"
                )
            except json.JSONDecodeError:
                arguments = {}

            ui.console.print(
                f"\n[info]🔧 IA →[/info] [bold]{name}()[/bold]"
            )

            result = (
                self.tool_executor(
                    name,
                    arguments,
                )
            )

            # ==================================================
            # IMAGEM
            # ==================================================

            if (
                isinstance(result, dict)
                and result.get("type") == "image"
            ):

                vision = (
                    self.analyze_image(
                        image_base64=result["data"],
                        user_question=user_message,
                        source=name,
                    )
                )

                self.messages.append(
                    {
                        "role": "tool",
                        "tool_call_id": call.id,
                        "content": (
                            f"{result.get('description', '')}\n"
                            f"Análise visual:\n{vision}"
                        ),
                    }
                )

            # ==================================================
            # RESULTADO NORMAL
            # ==================================================

            else:

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

        # ------------------------------------------------------
        # SEGUNDA FASE:
        # resposta final em streaming.
        #
        # Agora não damos tools novamente porque já executamos
        # as ferramentas necessárias.
        # ------------------------------------------------------

        final_stream = (
            self.client
            .chat
            .completions
            .create(
                model=self.chat_model,
                messages=self.messages,
                temperature=0.75,
                max_completion_tokens=300,
                reasoning_effort="low",
                include_reasoning=False,
                stream=True,
            )
        )

        collected = []

        for chunk in final_stream:

            if not chunk.choices:
                continue

            content = (
                chunk
                .choices[0]
                .delta
                .content
            )

            if content:

                collected.append(
                    content
                )

                yield content

        final_text = "".join(
            collected
        ).strip()

        self.messages.append(
            {
                "role": "assistant",
                "content": final_text,
            }
        )

    # ==========================================================
    # VISÃO
    # ==========================================================

    def analyze_image(
        self,
        image_base64: str,
        user_question: str,
        source: str,
    ) -> str:

        if source == "capture_screen":

            instruction = """
Analise a tela atual.

Identifique:
- aplicativo/jogo/site atual;
- o que o usuário está fazendo;
- texto importante;
- erros;
- informações relevantes para a pergunta.

Não descreva a tela inteira.
Se houver pouco contexto, apenas diga o que realmente consegue ver.
"""

        elif source == "capture_webcam":

            instruction = """
Analise a imagem da webcam.

Observe somente:
- pessoas;
- objetos;
- ambiente;
- eventos relevantes para a pergunta.

Não faça uma descrição desnecessariamente longa.
"""

        else:

            instruction = """
Analise a imagem e responda apenas ao que for relevante.
"""

        prompt = f"""
Você é o sistema de visão de um agente pessoal.

Pergunta do usuário:
{user_question}

Instrução:
{instruction}

Regras:
- seja objetivo;
- não invente;
- não diga que não tem acesso à imagem;
- responda em português do Brasil.
"""

        response = (
            self.client
            .chat
            .completions
            .create(
                model=self.vision_model,
                messages=[
                    {
                        "role": "user",
                        "content": [
                            {
                                "type": "text",
                                "text": prompt,
                            },
                            {
                                "type": "image_url",
                                "image_url": {
                                    "url": (
                                        "data:image/jpeg;base64,"
                                        f"{image_base64}"
                                    )
                                },
                            },
                        ],
                    }
                ],
                temperature=0.2,
                max_completion_tokens=120,
                reasoning_effort="none",
                reasoning_format="hidden",
                stream=False,
            )
        )

        return (
            response
            .choices[0]
            .message
            .content
            .strip()
        )
