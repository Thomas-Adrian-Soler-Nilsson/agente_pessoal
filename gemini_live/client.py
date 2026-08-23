import asyncio
import os
import threading

import numpy as np
import sounddevice as sd

from dotenv import load_dotenv
from google import genai
from google.genai import types


from tools.computer import ComputerTools
from tools.files import FileTools


load_dotenv()


MODEL = (
    "gemini-3.1-flash-live-preview"
)


SYSTEM_INSTRUCTION = """
Você é o agente pessoal do Thomas.

Você não deve parecer um assistente corporativo.
Você é uma parceira pessoal inteligente, informal,
ligeiramente irônica e sarcástica.

PERSONALIDADE:

- Fale em português brasileiro.
- Seja natural.
- Seja espontânea.
- Pode brincar com Thomas.
- Pode fazer comentários sarcásticos leves.
- Pode provocar de maneira amigável.
- Não seja ofensiva.
- Não seja grosseira de verdade.
- Não faça sarcasmo em momentos sérios.
- Não transforme toda frase em uma piada.
- O humor deve parecer espontâneo.
- Não fique repetindo "mano" em toda frase.
- Não use "Claro!", "Com certeza!" e "Entendi!" toda hora.
- Não fale como tutorial.
- Não diga coisas como "Como posso ajudá-lo hoje?".
- Prefira conversar normalmente.

EXEMPLOS DE PERSONALIDADE:

Thomas:
"Abre o Chrome pra mim."

Você:
"Ué, até que enfim uma tarefa digna. Abrindo."

Thomas:
"O que tem nessa pasta?"

Você:
"Tem arquivo pra caramba. Organização aparentemente foi
considerada opcional por aqui."

Thomas:
"Tá funcionando?"

Você:
"Milagre, mas tá."

Esses são exemplos de estilo, não frases obrigatórias.

========================================
AUTONOMIA
========================================

Você possui acesso a ferramentas do computador.

Você pode:

- abrir aplicativos;
- abrir sites;
- pesquisar na internet;
- listar arquivos;
- procurar arquivos;
- ler arquivos;
- obter informações sobre arquivos;
- ver a tela;
- ver a webcam;
- acompanhar continuamente a tela;
- acompanhar continuamente a webcam.

Você decide quando usar essas ferramentas.

Não peça confirmação para ações comuns e reversíveis
que Thomas pediu explicitamente.

Não apague arquivos.
Não exclua arquivos.
Não formate nada.
Não desinstale programas.
Não execute comandos destrutivos.

========================================
ABRIR APLICATIVOS
========================================

Se Thomas disser:

"abre o Chrome"

use open_application.

Se disser:

"abre o VS Code"

use open_application.

Você pode entender nomes naturais dos aplicativos.

Se Thomas pedir para abrir uma pasta no Explorador,
use open_directory. Para Downloads, use "Downloads".

========================================
ARQUIVOS
========================================

Se Thomas pedir:

"acha meu trabalho"

use search_files.

Se pedir:

"o que tem na minha pasta Downloads?"

use list_directory.

Se pedir:

"lê esse arquivo"

use read_file.

Se precisar descobrir o arquivo primeiro,
pesquise antes.

Não invente conteúdo de arquivos.

========================================
WEB
========================================

Você possui Google Search integrado.

Quando Thomas pedir para pesquisar algo,
use Google Search.

Exemplo:

"pesquisa quanto está o preço da RTX 5070"

→ use Google Search.

Depois explique o resultado naturalmente.

Não finja que pesquisou se não pesquisou.

========================================
VISÃO
========================================

Você pode olhar a tela e webcam.

Use a visão quando necessário.

Se Thomas estiver pedindo ajuda sobre algo que aparece
na tela, olhe a tela.

Se estiver pedindo para acompanhar continuamente,
ative o watcher apropriado.

========================================
CONVERSA
========================================

Não faça respostas enormes.

Por voz:

- respostas simples: 1-2 frases;
- tarefas: diga o que está fazendo;
- depois entregue o resultado.

Se uma ferramenta resolver a tarefa,
use a ferramenta em vez de explicar como Thomas poderia
fazer manualmente.
"""


FUNCTION_DECLARATIONS = [

    {
        "name": "open_application",
        "description": (
            "Abre um aplicativo instalado no computador. "
            "Use quando Thomas pedir para abrir um programa."
        ),
        "parameters": {
            "type": "object",
            "properties": {
                "application": {
                    "type": "string",
                    "description": (
                        "Nome do aplicativo."
                    ),
                }
            },
            "required": [
                "application"
            ],
        },
    },

    {
        "name": "open_url",
        "description": (
            "Abre uma URL no navegador."
        ),
        "parameters": {
            "type": "object",
            "properties": {
                "url": {
                    "type": "string",
                }
            },
            "required": [
                "url"
            ],
        },
    },

    {
        "name": "open_directory",
        "description": (
            "Abre uma pasta no Explorador de Arquivos."
        ),
        "parameters": {
            "type": "object",
            "properties": {
                "path": {
                    "type": "string",
                    "description": "Caminho da pasta, como Downloads.",
                }
            },
            "required": [
                "path"
            ],
        },
    },

    {
        "name": "list_directory",
        "description": (
            "Lista os arquivos e pastas de um diretório."
        ),
        "parameters": {
            "type": "object",
            "properties": {
                "path": {
                    "type": "string",
                    "description": (
                        "Caminho da pasta."
                    ),
                }
            },
            "required": [
                "path"
            ],
        },
    },

    {
        "name": "search_files",
        "description": (
            "Procura arquivos pelo nome dentro de uma pasta."
        ),
        "parameters": {
            "type": "object",
            "properties": {
                "query": {
                    "type": "string",
                },
                "path": {
                    "type": "string",
                },
            },
            "required": [
                "query"
            ],
        },
    },

    {
        "name": "read_file",
        "description": (
            "Lê o conteúdo extraível de arquivos de texto, PDF e DOCX."
        ),
        "parameters": {
            "type": "object",
            "properties": {
                "path": {
                    "type": "string",
                }
            },
            "required": [
                "path"
            ],
        },
    },

    {
        "name": "get_file_info",
        "description": (
            "Obtém informações sobre um arquivo."
        ),
        "parameters": {
            "type": "object",
            "properties": {
                "path": {
                    "type": "string",
                }
            },
            "required": [
                "path"
            ],
        },
    },

    {
        "name": "capture_screen",
        "description": (
            "Captura imediatamente a tela atual."
        ),
        "parameters": {
            "type": "object",
            "properties": {},
        },
    },

    {
        "name": "capture_webcam",
        "description": (
            "Captura imediatamente a webcam."
        ),
        "parameters": {
            "type": "object",
            "properties": {},
        },
    },

    {
        "name": "start_screen_watch",
        "description": (
            "Começa a acompanhar continuamente "
            "a tela do computador."
        ),
        "parameters": {
            "type": "object",
            "properties": {},
        },
    },

    {
        "name": "start_webcam_watch",
        "description": (
            "Começa a acompanhar continuamente "
            "a webcam."
        ),
        "parameters": {
            "type": "object",
            "properties": {},
        },
    },

    {
        "name": "stop_watch",
        "description": (
            "Para o acompanhamento contínuo."
        ),
        "parameters": {
            "type": "object",
            "properties": {},
        },
    },
]


class GeminiLive:

    def __init__(
        self,
        screen,
        webcam,
        tts=None,
    ):

        api_key = os.getenv(
            "GEMINI_API_KEY"
        )

        if not api_key:
            raise ValueError(
                "GEMINI_API_KEY não encontrada no .env"
            )

        self.client = genai.Client(
            api_key=api_key
        )

        self.screen = screen
        self.webcam = webcam

        self.computer = (
            ComputerTools()
        )

        self.files = (
            FileTools()
        )

        self.session = None
        self.loop = None

        self.running = False

        self.watch_mode = None
        self.video_thread = None
        self.video_stop = (
            threading.Event()
        )

        self.input_stream = None
        self.audio_output = None
        self.external_tts = tts

        self.input_transcript = ""
        self.output_transcript = ""

    # ==========================================================
    # TOOL EXECUTOR
    # ==========================================================

    async def handle_tool_call(
        self,
        tool_call,
    ):

        responses = []

        for call in (
            tool_call.function_calls
        ):

            name = call.name

            print(
                f"\n🔧 Gemini → {name}()"
            )

            arguments = (
                call.args or {}
            )

            try:

                # ----------------------------------------------
                # COMPUTADOR
                # ----------------------------------------------

                if name == "open_application":

                    result = (
                        self.computer
                        .open_application(
                            arguments.get(
                                "application",
                                "",
                            )
                        )
                    )

                elif name == "open_url":

                    result = (
                        self.computer
                        .open_url(
                            arguments.get(
                                "url",
                                "",
                            )
                        )
                    )

                elif name == "open_directory":

                    result = (
                        self.computer
                        .open_directory(
                            arguments.get(
                                "path",
                                "~",
                            )
                        )
                    )

                # ----------------------------------------------
                # ARQUIVOS
                # ----------------------------------------------

                elif name == "list_directory":

                    result = (
                        self.files
                        .list_directory(
                            arguments.get(
                                "path",
                                "~",
                            )
                        )
                    )

                elif name == "search_files":

                    result = (
                        self.files
                        .search_files(
                            arguments.get(
                                "query",
                                "",
                            ),
                            arguments.get(
                                "path",
                                "~",
                            ),
                        )
                    )

                elif name == "read_file":

                    result = (
                        self.files
                        .read_file(
                            arguments.get(
                                "path",
                                "",
                            )
                        )
                    )

                elif name == "get_file_info":

                    result = (
                        self.files
                        .get_file_info(
                            arguments.get(
                                "path",
                                "",
                            )
                        )
                    )

                # ----------------------------------------------
                # SCREEN
                # ----------------------------------------------

                elif name == "capture_screen":

                    image = (
                        self.screen.capture(
                            as_bytes=True
                        )
                    )

                    await self.session.send_realtime_input(
                        video=types.Blob(
                            data=image,
                            mime_type="image/jpeg",
                        )
                    )

                    result = (
                        "A captura atual da "
                        "tela foi enviada."
                    )

                # ----------------------------------------------
                # WEBCAM
                # ----------------------------------------------

                elif name == "capture_webcam":

                    image = (
                        self.webcam.capture(
                            as_bytes=True
                        )
                    )

                    await self.session.send_realtime_input(
                        video=types.Blob(
                            data=image,
                            mime_type="image/jpeg",
                        )
                    )

                    result = (
                        "A captura atual da "
                        "webcam foi enviada."
                    )

                # ----------------------------------------------
                # WATCH
                # ----------------------------------------------

                elif name == "start_screen_watch":

                    self.start_watch(
                        "screen"
                    )

                    result = (
                        "Acompanhamento contínuo "
                        "da tela ativado."
                    )

                elif name == "start_webcam_watch":

                    self.start_watch(
                        "webcam"
                    )

                    result = (
                        "Acompanhamento contínuo "
                        "da webcam ativado."
                    )

                elif name == "stop_watch":

                    self.stop_watch()

                    result = (
                        "Acompanhamento parado."
                    )

                else:

                    result = (
                        f"Tool desconhecida: {name}"
                    )

            except Exception as error:

                result = (
                    f"Erro ao executar {name}: "
                    f"{error}"
                )

            responses.append(
                types.FunctionResponse(
                    id=call.id,
                    name=name,
                    response={
                        "result": result
                    },
                )
            )

        if responses:

            await self.session.send_tool_response(
                function_responses=responses
            )

    # ==========================================================
    # WATCHER
    # ==========================================================

    def start_watch(
        self,
        mode: str,
    ):

        self.stop_watch(
            silent=True
        )

        self.watch_mode = mode

        self.video_stop.clear()

        self.video_thread = (
            threading.Thread(
                target=self._video_loop,
                daemon=True,
            )
        )

        self.video_thread.start()

        print(
            f"\n👁 Acompanhando: {mode}"
        )

    def stop_watch(
        self,
        silent=False,
    ):

        was_active = (
            self.watch_mode is not None
        )

        self.watch_mode = None

        self.video_stop.set()

        if (
            self.video_thread
            and self.video_thread.is_alive()
        ):

            self.video_thread.join(
                timeout=1.0
            )

        self.video_thread = None

        if was_active and not silent:

            print(
                "\n⏹ Acompanhamento parado."
            )

    def _video_loop(self):

        # Live API usa aproximadamente 1 frame/s.
        while (
            not self.video_stop.is_set()
            and self.session is not None
        ):

            try:

                if (
                    self.watch_mode
                    == "screen"
                ):

                    frame = (
                        self.screen.capture(
                            as_bytes=True
                        )
                    )

                elif (
                    self.watch_mode
                    == "webcam"
                ):

                    frame = (
                        self.webcam.capture(
                            as_bytes=True
                        )
                    )

                else:

                    self.video_stop.wait(
                        0.25
                    )

                    continue

                asyncio.run_coroutine_threadsafe(
                    self.session.send_realtime_input(
                        video=types.Blob(
                            data=frame,
                            mime_type="image/jpeg",
                        )
                    ),
                    self.loop,
                )

            except Exception as error:

                if not self.video_stop.is_set():

                    print(
                        f"\n⚠️ Watch: {error}"
                    )

            self.video_stop.wait(
                1.0
            )

    # ==========================================================
    # MICROFONE
    # ==========================================================

    def _audio_callback(
        self,
        indata,
        frames,
        time_info,
        status,
    ):

        if (
            self.session is None
            or self.loop is None
        ):
            return

        data = (
            indata[:, 0]
            .copy()
            .astype(
                np.int16
            )
            .tobytes()
        )

        try:

            asyncio.run_coroutine_threadsafe(
                self.session
                .send_realtime_input(
                    audio=types.Blob(
                        data=data,
                        mime_type=(
                            "audio/pcm;rate=16000"
                        ),
                    )
                ),
                self.loop,
            )

        except Exception:
            pass

    # ==========================================================
    # AUDIO
    # ==========================================================

    def _play_audio(
        self,
        data: bytes,
    ):

        samples = np.frombuffer(
            data,
            dtype=np.int16,
        )

        if not len(samples) or self.external_tts is not None:
            return

        if self.audio_output is None:

            self.audio_output = (
                sd.OutputStream(
                    samplerate=24000,
                    channels=1,
                    dtype="int16",
                    blocksize=960,
                )
            )

            self.audio_output.start()

        self.audio_output.write(
            samples.reshape(
                -1,
                1,
            )
        )

    def _stop_audio(self):

        if self.audio_output:

            try:
                self.audio_output.stop()
                self.audio_output.close()
            except Exception:
                pass

            self.audio_output = None

    # ==========================================================
    # RECEIVE
    # ==========================================================

    async def _receive_turn(
        self,
    ):

        async for response in (
            self.session.receive()
        ):

            if response.go_away:

                print(
                    "\n⚠️ Gemini encerrou a conexão."
                )

                return False

            server = (
                response.server_content
            )

            if server:

                # ------------------------------------------
                # INTERRUPÇÃO
                # ------------------------------------------

                if server.interrupted:

                    self._stop_audio()
                    if self.external_tts is not None:
                        self.external_tts.stop()

                    self.output_transcript = ""

                    print(
                        "\n🛑 Interrompido."
                    )

                # ------------------------------------------
                # AUDIO
                # ------------------------------------------

                if server.model_turn:

                    for part in (
                        server
                        .model_turn
                        .parts
                    ):

                        if (
                            part.inline_data
                            and isinstance(
                                part.inline_data.data,
                                bytes,
                            )
                        ):

                            self._play_audio(
                                part.inline_data.data
                            )

                # ------------------------------------------
                # USER TRANSCRIPT
                # ------------------------------------------

                if (
                    server.input_transcription
                    and server.input_transcription.text
                ):

                    self.input_transcript += (
                        server
                        .input_transcription
                        .text
                    )

                # ------------------------------------------
                # OUTPUT TRANSCRIPT
                # ------------------------------------------

                if (
                    server.output_transcription
                    and server.output_transcription.text
                ):

                    self.output_transcript += (
                        server
                        .output_transcription
                        .text
                    )

                # ------------------------------------------
                # TURN COMPLETE
                # ------------------------------------------

                if server.turn_complete:

                    if self.input_transcript.strip():

                        print(
                            f"\nVocê: "
                            f"{self.input_transcript.strip()}"
                        )

                    if self.output_transcript.strip():

                        print(
                            f"Agente: "
                            f"{self.output_transcript.strip()}"
                        )
                        if self.external_tts is not None:
                            await asyncio.to_thread(
                                self.external_tts.speak,
                                self.output_transcript.strip(),
                            )

                    self.input_transcript = ""
                    self.output_transcript = ""

                    return True

            # ----------------------------------------------
            # TOOL CALL
            # ----------------------------------------------

            if response.tool_call:

                await self.handle_tool_call(
                    response.tool_call
                )

        return True

    # ==========================================================
    # RUN
    # ==========================================================

    async def run(self):

        self.loop = (
            asyncio.get_running_loop()
        )

        config = types.LiveConnectConfig(

            response_modalities=[
                "AUDIO"
            ],

            system_instruction=types.Content(
                parts=[
                    types.Part(
                        text=SYSTEM_INSTRUCTION
                    )
                ]
            ),

            speech_config={
                "voice_config": {
                    "prebuilt_voice_config": {
                        "voice_name": "Kore"
                    }
                }
            },

            tools=[
                {
                    "google_search": {}
                },
                {
                    "function_declarations":
                        FUNCTION_DECLARATIONS
                },
            ],

            input_audio_transcription={},

            output_audio_transcription={},

            thinking_config=types.ThinkingConfig(
                thinking_level="minimal"
            ),
        )

        print(
            "🔗 Conectando ao Gemini Live..."
        )

        async with (
            self.client
            .aio
            .live
            .connect(
                model=MODEL,
                config=config,
            ) as session
        ):

            self.session = session
            self.running = True

            print(
                "✅ Gemini Live conectado."
            )

            self.input_stream = (
                sd.InputStream(
                    samplerate=16000,
                    channels=1,
                    dtype="int16",
                    blocksize=640,
                    callback=self._audio_callback,
                )
            )

            self.input_stream.start()

            print(
                "🎤 Microfone ativo."
            )

            try:

                while self.running:

                    alive = (
                        await self._receive_turn()
                    )

                    if not alive:
                        break

                    await asyncio.sleep(0)

            finally:

                self.running = False

                self.stop_watch(
                    silent=True
                )

                if self.input_stream:

                    try:
                        self.input_stream.stop()
                        self.input_stream.close()
                    except Exception:
                        pass

                    self.input_stream = None

                self._stop_audio()

                self.session = None

    # ==========================================================
    # CLOSE
    # ==========================================================

    def close(self):

        self.running = False

        self.stop_watch(
            silent=True
        )

        self._stop_audio()
        if self.external_tts is not None:
            self.external_tts.stop()

        self.session = None