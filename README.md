# 🤖 Agente Pessoal

> Um assistente de voz para Windows, construído em Python, com múltiplos provedores de IA, memória de conversa, memória persistente, ferramentas locais, visão por tela/webcam e geração de imagens.

<p align="center">
  <strong>🎤 Voz</strong> · <strong>🧠 Memória</strong> · <strong>👁️ Visão</strong> · <strong>🖥️ Automação</strong> · <strong>🎨 Imagens</strong>
</p>

---

## ✨ Sobre o projeto

O **Agente Pessoal** nasceu como um assistente de voz local para Windows e está evoluindo para uma arquitetura de agente pessoal capaz de combinar diferentes modelos e serviços de IA.

A ideia é separar as responsabilidades: o modelo de linguagem decide o que fazer, enquanto ferramentas específicas executam ações no computador, consultam arquivos, capturam imagens, geram imagens ou acessam memórias.

O projeto atualmente suporta **Gemini Live, Groq, OpenRouter e NVIDIA**, permitindo escolher o provedor e, quando disponível, o modelo utilizado.

---

## 🚀 Principais funcionalidades

### 🎙️ Conversa por voz

- Reconhecimento de voz com:
  - **Groq Whisper**
  - **Fish Audio ASR**
  - **Whisper local com faster-whisper**
- Respostas faladas com:
  - **Fish Audio TTS**
  - **Edge TTS**
  - **Gemini TTS**
- Streaming da resposta do modelo para o TTS.
- Interrupção da fala por `Esc`.
- Suporte experimental à interrupção da fala por detecção de voz no microfone.

### 🧠 Memória

O agente possui duas camadas de memória:

**Memória momentânea**

Mantém o contexto da conversa atual enquanto o agente está sendo executado.

**Memória temporal/persistente**

Armazenada localmente em JSON e preservada mesmo depois de fechar o programa. O próprio modelo decide quando uma informação merece ser lembrada.

A memória temporal pode:

- salvar informações importantes;
- pesquisar memórias relevantes;
- evitar duplicações;
- classificar informações por categoria;
- atribuir importância de `0.0` a `1.0`;
- atualizar memórias;
- remover memórias;
- expirar informações quando configurado;
- lidar com pequenas variações de palavras e erros comuns de transcrição.

Exemplo de categorias:

```text
project
preference
goal
person
configuration
fact
general
```

Exemplo de comportamento:

```text
Você: Quero transformar o Agente Pessoal em um produto.

Agente:
🧠 IA → memória salva [goal]

"Thomas quer transformar o Agente Pessoal em produto pessoal."
```

> A memória local fica em `memory/memory.json` e é ignorada pelo Git para não enviar dados pessoais ao repositório.

### 👁️ Visão

O agente pode utilizar ferramentas para:

- capturar a tela atual;
- capturar a webcam;
- analisar imagens retornadas pelas ferramentas.

### 🖥️ Ferramentas do computador

O modelo pode utilizar ferramentas para:

- abrir aplicativos;
- abrir diretórios;
- abrir URLs;
- listar diretórios;
- procurar arquivos;
- ler arquivos;
- consultar informações de arquivos.

As operações de arquivos possuem restrições de segurança e não oferecem comandos destrutivos arbitrários.

### 🎨 Geração de imagens

O agente possui uma ferramenta de geração de imagens integrada à **Hugging Face Inference API**.

Quando o usuário pede para criar uma imagem, o modelo pode chamar `generate_image`, gerar um prompt detalhado e salvar o resultado localmente.

Por padrão, as imagens são salvas em:

```text
Pictures/AgentePessoal/
```

O modelo de imagem pode ser configurado pelo `.env`.

---

## 🧩 Provedores de IA

### Gemini Live

Modo de conversa em tempo real com voz nativa, tela e webcam.

### Groq

Modo compatível com chat completions, com seleção de modelo e integração com Groq Whisper para STT.

### OpenRouter

Permite utilizar diferentes modelos através da API compatível com OpenAI e selecionar o modelo no início da sessão.

### NVIDIA

Integração com a API NVIDIA NIM, também com seleção de modelo.

### Automático

Modo que permite tentar os provedores configurados automaticamente, preservando o contexto da conversa.

---

## 🏗️ Arquitetura

```text
                    ┌──────────────────────┐
                    │      Usuário         │
                    │   🎤 Voz / Texto     │
                    └──────────┬───────────┘
                               │
                               ▼
                    ┌──────────────────────┐
                    │      STT / Input     │
                    │ Groq / Fish / Local  │
                    └──────────┬───────────┘
                               │
                               ▼
                    ┌──────────────────────┐
                    │    Agente / LLM      │
                    │ Groq / OpenRouter /  │
                    │ NVIDIA / Gemini      │
                    └───────┬───────┬──────┘
                            │       │
                ┌───────────┘       └────────────┐
                ▼                                ▼
       ┌─────────────────┐              ┌─────────────────┐
       │     Memória     │              │    Ferramentas  │
       │ momentânea +    │              │ PC / arquivos / │
       │ temporal        │              │ tela / webcam   │
       └─────────────────┘              └────────┬────────┘
                                                 │
                                                 ▼
                                      ┌────────────────────┐
                                      │ Geração de imagem  │
                                      │ Hugging Face        │
                                      └────────────────────┘
                            │
                            ▼
                    ┌──────────────────────┐
                    │       TTS            │
                    │ Fish / Edge / Gemini │
                    └──────────┬───────────┘
                               │
                               ▼
                         🔊 Resposta
```

---

## 📁 Estrutura do projeto

```text
agente_pessoal/
│
├── agent/
│   └── agent.py
│
├── audio/
│   ├── microphone.py
│   ├── speech_to_text.py
│   └── text_to_speech.py
│
├── gemini_live/
│   └── client.py
│
├── memory/
│   └── temporal_memory.py
│
├── providers/
│   ├── compatible_agent.py
│   ├── groq_provider.py
│   ├── nvidia_provider.py
│   ├── openrouter_provider.py
│   └── router.py
│
├── screen/
│   └── screen.py
│
├── tools/
│   ├── computer.py
│   ├── files.py
│   └── image_generation.py
│
├── ui/
│   └── ui.py
│
├── webcam/
│   └── webcam.py
│
├── app.py
├── .env.example
├── .gitignore
└── requirements.txt
```

---

## 🛠️ Tecnologias

- **Python 3.12+**
- Google Gemini / Gemini Live
- Groq API
- OpenRouter API
- NVIDIA NIM
- Fish Audio
- Hugging Face Inference API
- faster-whisper
- Edge TTS
- OpenCV
- Pillow
- PyAutoGUI
- pygame
- sounddevice
- python-dotenv
- Rich
- pypdf
- python-docx

As dependências atualmente utilizadas ficam centralizadas em `requirements.txt`.

---

## ⚙️ Instalação

### 1. Clone o projeto

```powershell
git clone https://github.com/Thomas-Adrian-Soler-Nilsson/agente_pessoal.git
cd agente_pessoal
```

### 2. Crie o ambiente virtual

```powershell
python -m venv .venv
.\.venv\Scripts\Activate.ps1
```

### 3. Instale as dependências

```powershell
python -m pip install -r requirements.txt
```

### 4. Configure as variáveis de ambiente

```powershell
Copy-Item .env.example .env
```

Depois edite o `.env` e adicione somente as chaves dos serviços que pretende utilizar.

Exemplo:

```env
GEMINI_API_KEY=sua_chave_gemini
GROQ_API_KEY=sua_chave_groq
OPENROUTER_API_KEY=sua_chave_openrouter
NVIDIA_API_KEY=sua_chave_nvidia
FISH_API_KEY=sua_chave_fish
FISH_VOICE_ID=id_da_sua_voz_fish
HF_API_KEY=sua_chave_huggingface
```

> **Nunca publique seu `.env`.** O arquivo já está protegido pelo `.gitignore`.

---

## ▶️ Executando

```powershell
.\.venv\Scripts\Activate.ps1
python app.py
```

O programa apresenta um menu para escolher o modo:

```text
======================================
           AGENTE PESSOAL
======================================

[1] Gemini Live
[2] Groq
[3] OpenRouter
[4] NVIDIA
[5] Automático
```

Nos provedores compatíveis, o agente também permite selecionar o modelo disponível/configurado.

---

## 🔊 Configuração de voz

### Edge TTS

É o modo mais simples para TTS local:

```env
TTS_PROVIDER=edge
```

### Fish Audio

```env
TTS_PROVIDER=fish
FISH_API_KEY=sua_chave
FISH_VOICE_ID=seu_reference_id
FISH_MODEL=s2.1-pro-free
```

Também é possível configurar várias vozes:

```env
FISH_VOICES=Goku=id_1,Lula=id_2,Voz personalizada=id_3
```

O agente apresenta as vozes disponíveis durante a inicialização e permite escolher uma.

### Gemini TTS

```env
TTS_PROVIDER=gemini
GEMINI_API_KEY=sua_chave
GEMINI_TTS_MODEL=gemini-2.5-flash-preview-tts
GEMINI_TTS_VOICE=Kore
```

---

## 🎤 Interrupção da fala

Durante uma resposta falada, `Esc` pode interromper imediatamente a reprodução.

A interrupção automática por voz pode ser ativada com:

```env
TTS_INTERRUPT_ENABLED=true
TTS_INTERRUPT_DELAY=0.7
TTS_INTERRUPT_THRESHOLD=0.08
```

O `TTS_INTERRUPT_THRESHOLD` controla a sensibilidade do microfone. Valores maiores tendem a reduzir interrupções causadas por ruído ou pelo próprio áudio do computador.

---

## 🎨 Geração de imagens

Configure a Hugging Face no `.env`:

```env
HF_API_KEY=sua_chave
HF_IMAGE_MODEL=black-forest-labs/FLUX.1-schnell
```

Depois, basta pedir ao agente algo como:

```text
Crie uma imagem de um robô humanoide futurista em uma cidade brasileira à noite.
```

O agente pode transformar a solicitação em um prompt detalhado, chamar a ferramenta de geração e abrir a imagem resultante.

---

## 🔐 Segurança e privacidade

O projeto foi pensado para manter o máximo possível de dados locais.

- Chaves de API ficam no `.env`.
- `.env`, ambientes virtuais e caches são ignorados pelo Git.
- A memória persistente local é ignorada pelo Git.
- Áudios e capturas locais são ignorados pelo Git.
- Ferramentas de arquivos possuem escopo controlado.
- Não são oferecidos comandos destrutivos arbitrários.
- O modelo não deve inventar conteúdo de arquivos: resultados das ferramentas são tratados como fonte da verdade.

Antes de publicar alterações:

```powershell
git status --short
git status --short --ignored
```

Confira principalmente se nenhuma chave, áudio, captura ou memória pessoal entrou no staging.

---

## 🧪 Status do projeto

**Em desenvolvimento ativo.**

### Implementado

- [x] Agente de voz para Windows
- [x] Gemini Live
- [x] Groq
- [x] OpenRouter
- [x] NVIDIA
- [x] Seleção de modelos
- [x] STT local / Groq / Fish
- [x] TTS Edge / Fish / Gemini
- [x] Personas para vozes Fish
- [x] Memória momentânea de conversa
- [x] Memória temporal persistente
- [x] Busca de memória por ferramenta
- [x] Decisão do modelo sobre quando salvar memória
- [x] Ferramentas de arquivos
- [x] Abertura de aplicativos e URLs
- [x] Captura de tela
- [x] Captura de webcam
- [x] Geração de imagens via Hugging Face
- [x] Streaming de respostas para TTS
- [x] Interrupção manual da fala

### Próximos passos

- [ ] Melhorar a interrupção por voz durante o TTS
- [ ] Evoluir a memória temporal para uma memória mais inteligente
- [ ] Adicionar memória de longo prazo com recuperação semântica
- [ ] Melhorar latência do pipeline voz → IA → voz
- [ ] Expandir ferramentas do computador
- [ ] Melhorar o sistema de agentes e roteamento de modelos
- [ ] Criar uma interface gráfica dedicada
- [ ] Empacotar uma versão instalável para Windows

---

## 📌 Filosofia do projeto

O objetivo não é apenas criar um chatbot que fala.

A proposta é construir um **agente pessoal de verdade**: um sistema capaz de conversar, lembrar, perceber o ambiente, utilizar ferramentas e executar tarefas de forma controlada, mantendo o usuário no comando.

---

## 👨‍💻 Autor

**Thomas Adrian Soler Nilsson**

Projeto pessoal desenvolvido em Python e em evolução contínua.

- GitHub: https://github.com/Thomas-Adrian-Soler-Nilsson
- Repositório: https://github.com/Thomas-Adrian-Soler-Nilsson/agente_pessoal

---

## 📄 Licença

Nenhuma licença open-source foi definida neste momento. Consulte o autor antes de reutilizar ou redistribuir o projeto.
