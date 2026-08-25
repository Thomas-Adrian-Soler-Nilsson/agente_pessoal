# Agente Pessoal

![Python](https://img.shields.io/badge/Python-3.12+-blue?logo=python&logoColor=white)
![Groq](https://img.shields.io/badge/Groq-API-orange)
![OpenRouter](https://img.shields.io/badge/OpenRouter-API-6c5ce7)
![NVIDIA](https://img.shields.io/badge/NVIDIA-NIM-76b900?logo=nvidia&logoColor=white)
![Hugging Face](https://img.shields.io/badge/Hugging%20Face-Inference%20API-yellow?logo=huggingface&logoColor=black)
![Status](https://img.shields.io/badge/status-em%20desenvolvimento-yellow)

Assistente pessoal de voz para Windows, desenvolvido em Python, com múltiplos provedores de IA, memória de conversa, memória persistente, ferramentas locais, visão e geração de imagens.

> Projeto pessoal voltado à construção de um agente de IA capaz de conversar naturalmente, manter contexto, lembrar informações relevantes, utilizar ferramentas e interagir com o computador de forma controlada.

---

## Sumário

- [Sobre o projeto](#sobre-o-projeto)
- [Principais funcionalidades](#principais-funcionalidades)
- [Arquitetura](#arquitetura)
- [Provedores de IA](#provedores-de-ia)
- [Memória](#memória)
- [Ferramentas](#ferramentas)
- [Geração de imagens](#geração-de-imagens)
- [Estrutura do projeto](#estrutura-do-projeto)
- [Requisitos](#requisitos)
- [Instalação](#instalação)
- [Configuração](#configuração)
- [Como usar](#como-usar)
- [Configuração de voz](#configuração-de-voz)
- [Interrupção da fala](#interrupção-da-fala)
- [Segurança e privacidade](#segurança-e-privacidade)
- [Status do projeto](#status-do-projeto)
- [Próximos passos](#próximos-passos)
- [Autor](#autor)
- [Licença](#licença)

---

## Sobre o projeto

O **Agente Pessoal** começou como um assistente de voz para Windows e está evoluindo para uma arquitetura de agente pessoal capaz de combinar diferentes modelos de linguagem, memória e ferramentas.

Em vez de depender de um único modelo, o projeto permite escolher entre diferentes provedores e modelos. O agente recebe a solicitação, mantém o contexto necessário e pode decidir quando uma ferramenta deve ser utilizada.

Entre as ações disponíveis estão abertura de aplicativos e URLs, busca e leitura de arquivos, captura de tela e webcam, recuperação de memórias e geração de imagens.

---

## Principais funcionalidades

### Conversa por voz

O pipeline de voz combina reconhecimento de fala, processamento pelo modelo e síntese de voz:

```text
Microfone
   ↓
STT
   ↓
Modelo de IA
   ↓
TTS
   ↓
Resposta por voz
```

Atualmente há suporte para:

- Groq Whisper;
- Fish Audio ASR;
- Whisper local com `faster-whisper`;
- Fish Audio TTS;
- Edge TTS;
- Gemini TTS;
- streaming das respostas;
- interrupção manual da fala com `Esc`;
- interrupção automática por detecção de voz.

### Múltiplos provedores

O agente pode trabalhar com diferentes serviços de IA, permitindo trocar o modelo sem alterar a estrutura principal da aplicação.

- Gemini Live;
- Groq;
- OpenRouter;
- NVIDIA NIM;
- modo automático;
- seleção de modelos nos provedores compatíveis.

---

## Arquitetura

A aplicação é organizada em camadas independentes para facilitar a evolução do agente.

```text
                         ┌──────────────────┐
                         │      Usuário     │
                         └────────┬─────────┘
                                  │
                                  ▼
                         ┌──────────────────┐
                         │   STT / Áudio    │
                         └────────┬─────────┘
                                  │
                                  ▼
                    ┌──────────────────────────┐
                    │       Agente / LLM       │
                    │  contexto + ferramentas  │
                    └───────────┬──────────────┘
                                │
              ┌─────────────────┼─────────────────┐
              ▼                 ▼                 ▼
       ┌─────────────┐   ┌─────────────┐   ┌─────────────┐
       │   Memória   │   │ Ferramentas │   │   Imagens   │
       │ momentânea  │   │ computador  │   │ Hugging Face│
       │ + temporal  │   │ arquivos    │   │             │
       └─────────────┘   │ tela/webcam │   └─────────────┘
                         └─────────────┘
                                │
                                ▼
                         ┌──────────────────┐
                         │       TTS        │
                         │ Fish / Edge /    │
                         │ Gemini           │
                         └────────┬─────────┘
                                  │
                                  ▼
                         ┌──────────────────┐
                         │     Resposta     │
                         └──────────────────┘
```

Essa separação permite trocar o provedor de IA, o sistema de voz ou uma ferramenta sem precisar reconstruir o restante da aplicação.

---

## Provedores de IA

### Gemini Live

Modo de conversa em tempo real utilizando a infraestrutura do Gemini Live, com suporte a voz e recursos multimodais.

### Groq

Integração baseada em chat completions, com seleção de modelos e suporte ao Groq Whisper para reconhecimento de voz.

### OpenRouter

Permite utilizar diferentes modelos por meio de uma API compatível com o formato de chat completions.

### NVIDIA

Integração com NVIDIA NIM para utilização de diferentes modelos disponibilizados pela plataforma.

### Automático

Modo destinado ao roteamento entre os provedores configurados.

---

## Memória

O agente possui duas camadas de memória, cada uma com uma função diferente.

### Memória momentânea

Mantém o contexto da conversa atual enquanto o programa está em execução.

Ela permite que o agente compreenda referências como:

> "E aquilo que eu te falei antes?"

sem precisar armazenar cada mensagem permanentemente.

### Memória temporal

É uma memória persistente armazenada localmente. Ela continua disponível depois que o programa é encerrado.

A própria IA decide quando uma informação possui valor suficiente para ser armazenada. Quando necessário, ela pode utilizar as ferramentas `save_memory` e `search_memory`.

A memória temporal permite:

- salvar informações importantes;
- pesquisar memórias relevantes;
- classificar informações por categoria;
- atribuir importância às memórias;
- atualizar informações existentes;
- remover informações;
- definir expiração quando necessário;
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

A memória persistente permanece local e não deve ser enviada ao repositório.

---

## Ferramentas

O sistema utiliza ferramentas estruturadas para permitir que o modelo execute ações específicas sem receber acesso irrestrito ao computador.

### Sistema e aplicativos

- Abrir aplicativos instalados;
- abrir diretórios no Explorador de Arquivos;
- abrir URLs no navegador.

### Arquivos

- listar diretórios;
- procurar arquivos;
- ler arquivos de formatos suportados;
- consultar informações de arquivos.

### Visão

- capturar a tela atual;
- capturar uma imagem da webcam;
- enviar imagens capturadas para análise quando suportado pelo provedor.

### Memória

- `save_memory` para armazenar informações importantes;
- `search_memory` para recuperar informações persistentes.

### Imagens

- `generate_image` para gerar imagens utilizando a Hugging Face Inference API.

As ferramentas possuem regras definidas no prompt do agente para reduzir comportamentos inesperados e impedir operações destrutivas arbitrárias.

---

## Geração de imagens

O agente também pode transformar uma solicitação em linguagem natural em uma imagem utilizando a **Hugging Face Inference API**.

```text
Usuário
   ↓
Agente interpreta o pedido
   ↓
generate_image()
   ↓
Hugging Face Inference API
   ↓
Modelo de geração
   ↓
Imagem salva localmente
```

Modelo configurado como padrão:

```env
HF_IMAGE_MODEL=black-forest-labs/FLUX.1-schnell
```

Chave da API:

```env
HF_API_KEY=sua_chave_huggingface
```

Exemplo de solicitação:

```text
Crie uma imagem de um robô humanoide futurista em uma cidade brasileira durante a noite.
```

As imagens são salvas localmente, por padrão, em:

```text
Pictures/AgentePessoal/
```

O modelo pode ser alterado pela variável `HF_IMAGE_MODEL` sem modificar o código do agente.

---

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

A estrutura pode mudar conforme novas funcionalidades forem adicionadas.

---

## Requisitos

- Windows 10/11;
- Python 3.12 ou versão compatível com as dependências instaladas;
- microfone para utilização do modo de voz;
- alto-falantes ou fones de ouvido para TTS;
- webcam para as funcionalidades de captura de imagem;
- conexão com internet para os provedores e serviços de IA utilizados.

---

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

Depois, ative novamente o ambiente virtual.

### 3. Instalar as dependências

```powershell
python -m pip install --upgrade pip
pip install -r requirements.txt
```

---

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
HF_IMAGE_MODEL=black-forest-labs/FLUX.1-schnell
```

Nunca publique o arquivo `.env` no GitHub.

---

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

---

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

---

## Interrupção da fala

A reprodução pode ser interrompida manualmente com `Esc`.

A detecção automática de fala durante o TTS pode ser ativada com:

```env
TTS_INTERRUPT_ENABLED=true
TTS_INTERRUPT_DELAY=0.7
TTS_INTERRUPT_THRESHOLD=0.08
```

`TTS_INTERRUPT_THRESHOLD` controla a sensibilidade do microfone. Valores maiores tornam a detecção menos sensível a ruídos.

---

## Segurança e privacidade

O projeto foi desenvolvido para manter dados locais sempre que possível.

- chaves de API são armazenadas no `.env`;
- `.env` e ambientes virtuais são ignorados pelo Git;
- memórias persistentes locais não devem ser publicadas;
- áudios e capturas locais são ignorados pelo Git;
- ferramentas possuem escopo definido;
- o agente não recebe comandos destrutivos arbitrários;
- resultados das ferramentas devem ser tratados como fonte da verdade.

Antes de realizar um commit, confira os arquivos que serão enviados:

```powershell
git status --short
git status --short --ignored
```

---

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

---

## Próximos passos

- [ ] Melhorar a interrupção automática da fala por voz;
- [ ] reduzir a latência do pipeline voz → IA → voz;
- [ ] evoluir a memória temporal;
- [ ] adicionar recuperação semântica para memória de longo prazo;
- [ ] expandir as ferramentas disponíveis para o computador;
- [ ] melhorar o roteamento entre provedores e modelos;
- [ ] criar uma interface gráfica dedicada;
- [ ] gerar uma versão instalável para Windows.

---

## Objetivo do projeto

O objetivo é construir um agente pessoal de IA que vá além de um chatbot tradicional.

O sistema deve ser capaz de conversar naturalmente, manter contexto, lembrar informações relevantes, perceber o ambiente, utilizar ferramentas e executar tarefas de forma controlada, mantendo o usuário no comando.

---

## Autor

**Thomas Adrian Soler Nilsson**

Projeto pessoal desenvolvido em Python e em evolução contínua.

- GitHub: https://github.com/Thomas-Adrian-Soler-Nilsson
- Repositório: https://github.com/Thomas-Adrian-Soler-Nilsson/agente_pessoal

---

## Licença

Nenhuma licença open-source foi definida neste momento. Consulte o autor antes de reutilizar ou redistribuir o projeto.
