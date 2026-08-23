# Agente Pessoal

![Python](https://img.shields.io/badge/Python-3.12+-blue?logo=python&logoColor=white)
![Groq](https://img.shields.io/badge/Groq-API-orange)
![OpenRouter](https://img.shields.io/badge/OpenRouter-API-6c5ce7)
![NVIDIA](https://img.shields.io/badge/NVIDIA-NIM-76b900?logo=nvidia&logoColor=white)
![Status](https://img.shields.io/badge/status-em%20desenvolvimento-yellow)

Assistente pessoal de voz para Windows, desenvolvido em Python, com múltiplos provedores de IA, memória de conversa, memória persistente, ferramentas locais, captura de tela e webcam e geração de imagens.

> Projeto pessoal desenvolvido para explorar a construção de um agente de IA capaz de conversar, lembrar informações, utilizar ferramentas e interagir com o computador de forma controlada.

## Sumário

- [Sobre o projeto](#sobre-o-projeto)
- [Principais funcionalidades](#principais-funcionalidades)
- [Provedores de IA](#provedores-de-ia)
- [Memória](#memória)
- [Ferramentas](#ferramentas)
- [Estrutura do projeto](#estrutura-do-projeto)
- [Requisitos](#requisitos)
- [Instalação](#instalação)
- [Configuração](#configuração)
- [Como usar](#como-usar)
- [Geração de imagens](#geração-de-imagens)
- [Interrupção da fala](#interrupção-da-fala)
- [Segurança e privacidade](#segurança-e-privacidade)
- [Status do projeto](#status-do-projeto)
- [Próximos passos](#próximos-passos)
- [Licença](#licença)

## Sobre o projeto

O **Agente Pessoal** começou como um assistente de voz para Windows e está evoluindo para uma arquitetura de agente pessoal capaz de combinar diferentes modelos de linguagem, memória e ferramentas.

O modelo de IA é responsável por interpretar a solicitação e decidir quando utilizar uma ferramenta. As ferramentas executam ações específicas, como abrir aplicativos, procurar arquivos, capturar a tela, acessar a webcam, pesquisar memórias ou gerar imagens.

O projeto atualmente possui integração com **Gemini Live, Groq, OpenRouter e NVIDIA**, permitindo selecionar o provedor e, nos provedores compatíveis, o modelo utilizado.

## Principais funcionalidades

### Conversa por voz

- Reconhecimento de voz com Groq Whisper, Fish Audio ASR ou Whisper local com `faster-whisper`.
- Síntese de voz com Fish Audio, Edge TTS ou Gemini TTS.
- Streaming das respostas do modelo para o sistema de TTS.
- Interrupção manual da fala com `Esc`.
- Suporte à interrupção automática por detecção de voz no microfone.

### Múltiplos provedores

- Gemini Live.
- Groq.
- OpenRouter.
- NVIDIA NIM.
- Modo automático de seleção de provedor.
- Seleção de modelos nos provedores compatíveis.

### Memória

O agente possui duas camadas de memória.

**Memória momentânea**

Mantém o contexto da conversa atual durante a execução do agente.

**Memória temporal**

Armazenada localmente e preservada depois que o programa é encerrado. O próprio modelo decide quando uma informação possui valor suficiente para ser armazenada.

A memória temporal permite:

- salvar informações importantes;
- pesquisar memórias relevantes;
- classificar informações por categoria;
- atribuir importância às memórias;
- atualizar informações existentes;
- remover informações;
- definir expiração para memórias quando necessário;
- lidar com pequenas variações de termos e erros de transcrição.

Categorias utilizadas atualmente:

```text
project
preference
goal
person
configuration
fact
general
```

Exemplo:

```text
Você: Quero transformar o Agente Pessoal em um produto.

Agente:
IA → memória salva [goal]

"Thomas quer transformar o Agente Pessoal em produto pessoal."
```

A memória persistente fica armazenada localmente e não deve ser enviada ao repositório.

## Provedores de IA

### Gemini Live

Modo de conversa em tempo real utilizando a infraestrutura do Gemini Live, com suporte a voz e recursos de interação multimodal.

### Groq

Integração baseada em chat completions, com seleção de modelos e suporte ao Groq Whisper para reconhecimento de voz.

### OpenRouter

Permite utilizar diferentes modelos através de uma API compatível com o formato de chat completions.

### NVIDIA

Integração com NVIDIA NIM para utilização de diferentes modelos disponíveis na plataforma.

### Automático

Modo que permite utilizar os provedores configurados de acordo com a configuração do projeto.

## Ferramentas

O agente possui um sistema de ferramentas que permite ao modelo executar ações específicas.

### Sistema e aplicativos

- Abrir aplicativos instalados.
- Abrir diretórios no Explorador de Arquivos.
- Abrir URLs no navegador.

### Arquivos

- Listar diretórios.
- Procurar arquivos.
- Ler arquivos de formatos suportados.
- Consultar informações de arquivos.

### Visão

- Capturar a tela atual.
- Capturar uma imagem da webcam.
- Enviar imagens capturadas para análise do modelo quando suportado pelo provedor.

### Memória

- `save_memory` para armazenar informações importantes.
- `search_memory` para pesquisar informações persistentes.

### Imagens

- `generate_image` para gerar imagens através da Hugging Face Inference API.

As ferramentas possuem regras de utilização definidas no prompt do agente para evitar operações destrutivas e reduzir comportamentos inesperados.

## Arquitetura

```text
Usuário
   |
   v
STT / Entrada
   |
   v
Agente / Modelo de IA
   |
   +--------------------+
   |                    |
   v                    v
Memória              Ferramentas
momentânea +         computador / arquivos /
temporal             tela / webcam
   |                    |
   |                    v
   |              Geração de imagem
   |              Hugging Face
   |
   +--------------------+
            |
            v
           TTS
   Fish / Edge / Gemini
            |
            v
         Resposta
```

## Estrutura do projeto

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
├── requirements.txt
└── README.md
```

A estrutura pode mudar conforme novas funcionalidades forem adicionadas ao projeto.

## Requisitos

- Windows 10/11.
- Python 3.12 ou versão compatível com as dependências instaladas.
- Microfone para utilização do modo de voz.
- Alto-falantes ou fones de ouvido para TTS.
- Webcam somente para as funcionalidades de captura de imagem.
- Conexão com internet para os provedores e serviços de IA utilizados.

## Instalação

### 1. Clonar o repositório

```powershell
git clone https://github.com/Thomas-Adrian-Soler-Nilsson/agente_pessoal.git
cd agente_pessoal
```

### 2. Criar o ambiente virtual

```powershell
python -m venv .venv
.\.venv\Scripts\Activate.ps1
```

Se o PowerShell bloquear a execução de scripts:

```powershell
Set-ExecutionPolicy -ExecutionPolicy RemoteSigned -Scope CurrentUser
```

Depois ative novamente o ambiente virtual.

### 3. Instalar as dependências

```powershell
python -m pip install --upgrade pip
pip install -r requirements.txt
```

## Configuração

Crie o arquivo `.env` a partir do exemplo disponível no projeto:

```powershell
Copy-Item .env.example .env
```

Configure somente os serviços que pretende utilizar.

Exemplo:

```env
GEMINI_API_KEY=sua_chave_gemini
GROQ_API_KEY=sua_chave_groq
OPENROUTER_API_KEY=sua_chave_openrouter
NVIDIA_API_KEY=sua_chave_nvidia
FISH_API_KEY=sua_chave_fish
FISH_VOICE_ID=seu_reference_id
HF_API_KEY=sua_chave_huggingface
```

Nunca publique o arquivo `.env` no GitHub.

## Como usar

Com o ambiente virtual ativado:

```powershell
python app.py
```

O programa apresenta um menu semelhante a:

```text
======================================
           AGENTE PESSOAL
======================================

[1] Gemini Live

[2] Groq
    ├── seleção de modelo

[3] OpenRouter
    ├── seleção de modelo

[4] NVIDIA
    ├── seleção de modelo

[5] Automático
```

Depois da escolha do provedor, o programa solicita as configurações de STT e TTS disponíveis.

## Configuração de voz

### Edge TTS

Para utilizar o TTS local:

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

### Gemini TTS

```env
TTS_PROVIDER=gemini
GEMINI_API_KEY=sua_chave
GEMINI_TTS_MODEL=gemini-2.5-flash-preview-tts
GEMINI_TTS_VOICE=Kore
```

## Geração de imagens

A geração de imagens utiliza a Hugging Face Inference API.

Configure no `.env`:

```env
HF_API_KEY=sua_chave
HF_IMAGE_MODEL=black-forest-labs/FLUX.1-schnell
```

Depois, o agente pode gerar uma imagem quando o usuário fizer uma solicitação compatível.

Exemplo:

```text
Crie uma imagem de um robô humanoide futurista em uma cidade brasileira durante a noite.
```

As imagens são salvas localmente no diretório configurado pelo gerador, por padrão dentro de:

```text
Pictures/AgentePessoal/
```

## Interrupção da fala

A reprodução pode ser interrompida manualmente com `Esc`.

A detecção automática de fala durante o TTS pode ser ativada com:

```env
TTS_INTERRUPT_ENABLED=true
TTS_INTERRUPT_DELAY=0.7
TTS_INTERRUPT_THRESHOLD=0.08
```

`TTS_INTERRUPT_THRESHOLD` controla a sensibilidade do microfone. Valores maiores tornam a detecção menos sensível a ruídos.

## Segurança e privacidade

O projeto foi desenvolvido para manter dados locais sempre que possível.

- Chaves de API são armazenadas no `.env`.
- `.env` e ambientes virtuais são ignorados pelo Git.
- Memórias persistentes locais não devem ser publicadas.
- Áudios e capturas locais são ignorados pelo Git.
- As ferramentas de arquivos possuem escopo definido.
- O agente não recebe comandos destrutivos arbitrários.
- Resultados das ferramentas devem ser tratados como fonte da verdade.

Antes de realizar um commit, confira os arquivos que serão enviados:

```powershell
git status --short
git status --short --ignored
```

## Status do projeto

**Em desenvolvimento.**

### Implementado

- [x] Agente de voz para Windows
- [x] Gemini Live
- [x] Groq
- [x] OpenRouter
- [x] NVIDIA
- [x] Seleção de modelos
- [x] STT local, Groq e Fish Audio
- [x] TTS Edge, Fish Audio e Gemini
- [x] Personas para vozes Fish Audio
- [x] Memória momentânea da conversa
- [x] Memória temporal persistente
- [x] Busca de memória através de ferramenta
- [x] Decisão do modelo sobre quando salvar uma memória
- [x] Ferramentas para arquivos
- [x] Abertura de aplicativos e URLs
- [x] Captura de tela
- [x] Captura de webcam
- [x] Geração de imagens via Hugging Face
- [x] Streaming de respostas para TTS
- [x] Interrupção manual da fala

## Próximos passos

- [ ] Melhorar a interrupção automática da fala por voz.
- [ ] Melhorar a latência do pipeline voz → IA → voz.
- [ ] Evoluir a memória temporal.
- [ ] Adicionar memória de longo prazo com recuperação semântica.
- [ ] Expandir as ferramentas disponíveis para o computador.
- [ ] Melhorar o roteamento entre provedores e modelos.
- [ ] Criar uma interface gráfica dedicada.
- [ ] Gerar uma versão instalável para Windows.

## Objetivo do projeto

O objetivo é construir um agente pessoal de IA que vá além de um chatbot tradicional.

O sistema deve ser capaz de conversar naturalmente, manter contexto, lembrar informações relevantes, perceber o ambiente, utilizar ferramentas e executar tarefas de forma controlada, mantendo o usuário no comando.

## Autor

**Thomas Adrian Soler Nilsson**

Projeto pessoal desenvolvido em Python e em evolução contínua.

- GitHub: https://github.com/Thomas-Adrian-Soler-Nilsson
- Repositório: https://github.com/Thomas-Adrian-Soler-Nilsson/agente_pessoal

## Licença

Nenhuma licença open-source foi definida neste momento. Consulte o autor antes de reutilizar ou redistribuir o projeto.
