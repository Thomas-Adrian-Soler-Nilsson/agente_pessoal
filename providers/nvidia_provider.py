import os

from dotenv import load_dotenv
from openai import OpenAI

from .compatible_agent import CompatibleAgent

load_dotenv()

DEFAULT_NVIDIA_MODELS = [
    "moonshotai/kimi-k3",
    "deepseek-ai/deepseek-v4-pro-0813",
    "deepseek-ai/deepseek-v4-flash-0731",
    "nvidia/nemotron-3.5-lightning-30b-a3b",
    "meta/muse-glimmer-30b",
    "poolside/laguna-xs-2.1",
    "google/diffusiongemma-26b-a4b-it",
    "nvidia/nemotron-3-ultra-550b-a55b",
    "nvidia/nemotron-3-nano-omni-30b-a3b-reasoning",
    "google/gemma-4-31b-it",
    "nvidia/nemotron-3-super-120b-a12b",
    "openai/gpt-oss-20b",
    "mistralai/mistral-nemotron",
    "meta/llama-3.2-11b-vision-instruct",
    "meta/llama-3.2-90b-vision-instruct",
]

# ================================================================
# NÃO INCLUÍDOS DE PROPÓSITO
# ================================================================
# Estes apareceram no catálogo do build.nvidia.com mas NÃO são modelos
# de chat/texto com tool-calling — usam endpoints especializados
# diferentes de /chat/completions (tradução, TTS, embeddings, safety,
# vídeo, percepção automotiva, áudio). Selecioná-los neste menu de
# texto resultaria em erro na primeira chamada. Ficam documentados
# aqui só pra referência futura, caso um dia o agente ganhe uma
# ferramenta dedicada pra alguma dessas modalidades:
#
#   nvidia/riva-translate-4b-instruct-v2      (tradução)
#   nvidia/riva-translate-4b-instruct-v1_1    (tradução)
#   nvidia/ising-calibration-1.5-31b          (VLM nichado: gráficos de calibração quântica)
#   nvidia/ising-calibration-1-35b-a3b        (idem, versão anterior)
#   nvidia/nemotron-3-embed-1b                (embeddings, não gera texto)
#   nvidia/nemotron-3.5-content-safety        (classificador de segurança)
#   nvidia/llama-3.1-nemotron-safety-guard-8b-v3 (classificador de segurança)
#   meta/llama-guard-4-12b                    (classificador de segurança)
#   nvidia/cosmos3-nano                       (geração de vídeo)
#   nvidia/cosmos3-nano-reasoner              (VLM de vídeo/mundo físico, nichado)
#   nvidia/cosmos-transfer2.5-2b              (geração de vídeo)
#   nvidia/cosmos-transfer1-7b                (geração de vídeo; deprecando)
#   nvidia/synthetic-video-detector           (detecção de deepfake)
#   nvidia/active-speaker-detection           (rastreamento de vídeo)
#   nvidia/nemotron-voicechat                 (voz-para-voz, não é chat de texto)
#   nvidia/magpie-tts-zeroshot                (TTS)
#   nvidia/bnr                                (remoção de ruído em áudio)
#   nvidia/studiovoice                        (realce de áudio)
#   nvidia/streampetr                         (percepção 3D veículo autônomo)
#   nvidia/sparsedrive                        (stack de direção autônoma)
#   nvidia/bevformer                          (percepção 3D veículo autônomo)
#   google/google-paligemma                   (VLM base, não é bem um assistente de chat)
#   minimaxai/minimax-m3                      (multimodal com tool-calling, mas com
#                                               "Deprecation in 3d" no catálogo — evitar
#                                               escolher um endpoint prestes a sumir)


RETIRED_NVIDIA_MODELS = {
    "z-ai/glm-5.2",
}


def available_models():
    configured = os.getenv("NVIDIA_MODELS", "")
    models = [model.strip() for model in configured.split(",") if model.strip()] or DEFAULT_NVIDIA_MODELS
    return [model for model in models if model not in RETIRED_NVIDIA_MODELS]


class NvidiaAgent:
    def __init__(self, tool_executor, model=None, messages=None):
        api_key = os.getenv("NVIDIA_API_KEY")
        if not api_key:
            raise ValueError("NVIDIA_API_KEY não encontrada no .env")
        requested_model = model or os.getenv("NVIDIA_MODEL")
        self.model = (
            requested_model
            if requested_model and requested_model not in RETIRED_NVIDIA_MODELS
            else available_models()[0]
        )
        client = OpenAI(
            api_key=api_key,
            base_url="https://integrate.api.nvidia.com/v1",
        )
        self.agent = CompatibleAgent(client, self.model, tool_executor, messages)

    def ask_stream(self, text: str, cancel_event=None):
        return self.agent.ask_stream(text, cancel_event=cancel_event)

    def set_personality(self, personality: str):
        self.agent.set_personality(personality)