# Agente Pessoal

![Python](https://img.shields.io/badge/Python-3.12+-blue?logo=python&logoColor=white)
![Groq](https://img.shields.io/badge/Groq-API-orange)
![OpenRouter](https://img.shields.io/badge/OpenRouter-API-6c5ce7)
![NVIDIA](https://img.shields.io/badge/NVIDIA-NIM-76b900?logo=nvidia&logoColor=white)
![Hugging Face](https://img.shields.io/badge/Hugging%20Face-Inference%20API-yellow?logo=huggingface&logoColor=black)
![Status](https://img.shields.io/badge/status-em%20desenvolvimento-yellow)

Assistente pessoal para Windows, feito em Python. Ele conversa por texto ou voz, usa provedores de IA configuráveis e pode executar ferramentas locais, consultar memória e operar abas do Chrome pela extensão.

Este repositório está em desenvolvimento. Recursos que dependem de APIs externas exigem uma chave válida, disponibilidade do provedor e, em alguns casos, créditos. Consulte [Limitações e privacidade](#limitações-e-privacidade) antes de enviar conteúdo a um serviço externo.

---

## Sumário

- [Início rápido](#início-rápido)
- [Recursos](#recursos)
- [Arquitetura](#arquitetura)
- [Provedores de IA](#provedores-de-ia)
- [Ferramentas](#ferramentas)
- [Chrome e screenshots](#chrome-e-screenshots)
- [Memória](#memória)
- [Voz](#voz)
- [Geração de imagens](#geração-de-imagens)
- [Geração 3D](#geração-3d)
- [Estrutura do projeto](#estrutura-do-projeto)
- [Requisitos](#requisitos)
- [Instalação](#instalação)
- [Configuração](#configuração)
- [Como usar](#como-usar)
- [Testes e contribuição](#testes-e-contribuição)
- [Estado do projeto](#estado-do-projeto)
- [Limitações e privacidade](#limitações-e-privacidade)
- [Autor](#autor)
- [Licença](#licença)

---

## Início rápido

No Windows, com Python 3.12 instalado, abra o PowerShell na pasta do projeto:

```powershell
py -3.12 -m venv .venv
.\.venv\Scripts\Activate.ps1
python -m pip install --upgrade pip
python -m pip install -r requirements.txt
Copy-Item .env.example .env
```

Edite `.env` e configure a chave do provedor que pretende usar. Depois inicie:

```powershell
.\Iniciar_Agente.bat
```

Também é possível iniciar diretamente com `python app.py`. A primeira execução mostra os menus de provedor, voz e privacidade da análise visual.

## Recursos

- Chat por texto e modo de voz, com opções de STT e TTS.
- Seleção de modelo entre provedores configurados.
- Ferramentas para arquivos, aplicativos, pesquisa na web e navegador.
- Memória de conversa e memória persistente local.
- Captura de tela e webcam.
- Geração de imagens e ferramentas de geração 3D, algumas dependentes de serviços e créditos externos.
- Extensão Chrome local para inspeção e interação com abas HTTP/HTTPS.

O conjunto efetivamente disponível depende das chaves, modelos instalados e opções configuradas no computador.

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

O menu principal oferece Gemini (API ou Live), Groq, Mistral, Token Harbor, OpenRouter, NVIDIA, Ollama, Hugging Face e Automático. O catálogo de modelos é carregado conforme o provedor e a configuração local; provedores remotos podem exigir chave e cobrança/créditos.

O modo **Automático** tenta Token Harbor quando há uma chave configurada e, em seguida, Groq, Mistral, OpenRouter, NVIDIA e Hugging Face. Ele não seleciona Gemini nem Ollama automaticamente. Para esses provedores, escolha a opção diretamente no menu.

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

- `save_memory` para armazenar informações importantes, com deduplicação;
- `search_memory` para recuperar informações persistentes por relevância;
- `list_memory`, `update_memory` e `delete_memory` para organizar a base com
  confirmação explícita do usuário quando necessário;
- expiração automática de fatos temporários e recuperação de JSON corrompido.

### Imagens

- `generate_image` para gerar imagens utilizando a Hugging Face Inference API.

### Pesquisa e navegador

- `web_search` encontra fontes públicas; `web_open` lê uma página; `deep_search` compara fontes e `code_search` prioriza documentação e repositórios.
- As ferramentas `browser_*` operam abas HTTP/HTTPS da sessão Chrome por meio da extensão local. `browser_inspect` lê o estado e retorna referências de elementos; a extensão valida essas referências antes de clicar ou preencher. `browser_visual_click` captura, analisa e tenta um único clique visual. O screenshot aparece como prévia colorida no terminal e é enviado ao provedor visual selecionado; no fallback, a mesma imagem pode ser enviada a mais de um provedor. Cada solicitação tem um orçamento de 3 falhas de browser e abre no máximo 1 aba; quando o limite é atingido, a resposta final informa o `error_code` real.
- Para instalar a integração no Windows, execute `tools\install_browser_bridge.ps1` no PowerShell a partir da raiz. Em `chrome://extensions`, habilite o modo do desenvolvedor e use **Carregar sem compactação** apontando para `browser_extension/`. Inicie/reinicie o agente e confira o popup da extensão. Para remover o host registrado, execute `tools\uninstall_browser_bridge.ps1`.
- O Chrome não permite controlar páginas internas como `chrome://extensions`. Capturas antigas, mudanças de aba, navegação, rolagem ou viewport podem invalidar um clique. Campos de senha são bloqueados. Enviar, publicar, comprar, excluir ou confirmar pode exigir autorização explícita.


### Desenvolvimento de software

As ferramentas de desenvolvimento agora cobrem varias linguagens usando os
runtimes instalados no computador:

- `detect_runtimes` identifica Python, Node, Go, Rust, Java, .NET, Ruby, PHP e outros;
- `run_code_file` executa scripts e arquivos compilaveis por extensao;
- `run_terminal` executa testes, builds e comandos de desenvolvimento no workspace,
  aceitando `input_text` para programas interativos;
- `install_dependencies` detecta requirements.txt, pyproject.toml, package.json,
  Cargo.toml, go.mod, Maven, Gradle e Composer;
- `download_file` baixa assets HTTP/HTTPS para pastas permitidas, com limite de 100 MB.

Comandos destrutivos, downloads via shell e referencias diretas a segredos sao
bloqueados. Instalacoes de dependencias continuam sendo acao explicita.
As execucoes retornam `Exit code` e `Status`; processos interativos devem
receber entradas de teste em vez de serem iniciados sem stdin.

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

## Geração 3D

Há ferramentas de geração 3D locais e hospedadas. Os serviços hospedados podem consumir créditos; a instalação do TripoSR é opcional e separada.

### TripoSR local

O agente também pode gerar um modelo 3D localmente usando o TripoSR, sem consumir créditos de API. Esse backend funciona a partir de uma imagem de referência e requer uma instalação separada do repositório oficial.

```env
TRIPOSR_PATH=C:\\caminho\\para\\TripoSR
TRIPOSR_PYTHON=C:\\caminho\\para\\TripoSR\\.venv\\Scripts\\python.exe
TRIPOSR_DEVICE=cuda:0
TRIPOSR_TIMEOUT=900
```

Depois de clonar e instalar o TripoSR conforme a documentação oficial, peça ao agente para usar a ferramenta local ou informe uma imagem de referência, por exemplo:

```text
Gere um modelo 3D local usando a imagem C:\\imagens\\foguete.png
```

O resultado GLB e o visualizador HTML são salvos em `Pictures/AgentePessoal/TripoSR/`.

### Geração 3D hospedada: Hyper3D/Rodin e Trify3D

Também é possível gerar modelos 3D sem clonar ou instalar outro projeto. O
agente chama as APIs hospedadas, acompanha o processamento e salva o GLB e um
visualizador HTML em `Pictures/AgentePessoal/Hosted3D/`.

Configure no `.env` apenas o provedor que quiser usar:

```env
RODIN_API_KEY=...
RODIN_TIER=Gen-2.5-Medium
RODIN_QUALITY=medium
RODIN_TIMEOUT=1200

TRIFY3D_API_KEY=...
TRIFY3D_MODE=quality
TRIFY3D_STYLE=realistic
TRIFY3D_TIMEOUT=1200
```

Exemplos de pedidos:

```text
Gere um modelo 3D de um foguete usando Rodin.
Gere um modelo 3D de uma cadeira usando Trify3D.
Gere um 3D usando Rodin a partir da imagem C:\imagens\objeto.png.
```

Rodin e Trify3D são serviços hospedados: exigem uma chave válida e podem
consumir créditos do respectivo provedor. A integração trata polling, timeout,
limite de requisições, erros de crédito e download do modelo. Para o Trify3D,
a chave precisa ter permissão de escrita para iniciar uma geração.

### Opção gratuita sem API key: three.ws

Para testar texto→3D sem criar conta, use a ferramenta gratuita integrada
`generate_3d_free`. Ela chama o endpoint público do three.ws, acompanha a fila
e salva o GLB no mesmo diretório `Hosted3D`. A faixa gratuita gera um rascunho
de um único objeto, somente em GLB, sem rigging e com limite por IP.

```text
Gere gratuitamente um 3D de um foguete usando a ferramenta sem API key.
```

Essa opção é indicada para protótipos; Rodin/Trify3D continuam disponíveis
quando você tiver créditos ou chaves próprias.

### NVIDIA TRELLIS

Se você criou uma chave no NVIDIA Build, o agente também pode usar o endpoint
oficial do TRELLIS. Ele aceita texto ou imagem e retorna um GLB. Configure a
chave específica ou reutilize `NVIDIA_API_KEY`:

```env
NVIDIA_TRELLIS_API_KEY=...
# ou NVIDIA_API_KEY=...
NVIDIA_TRELLIS_TIMEOUT=900
```

Exemplos:

```text
Gere um 3D usando NVIDIA TRELLIS: foguete espacial vermelho.
Gere um 3D usando NVIDIA TRELLIS a partir da imagem C:\imagens\objeto.png.
```

O arquivo é salvo em `Pictures/AgentePessoal/Hosted3D/`. O endpoint hospedado
é síncrono e devolve o GLB em base64; a ferramenta decodifica o resultado e
cria o visualizador HTML automaticamente.

## Estrutura do projeto

```text
agente_pessoal/
├── agent/              # agente e contratos
├── audio/              # microfone, STT e TTS
├── avatar/             # Live2D opcional e assets
├── browser_extension/  # extensão Chrome Manifest V3
├── gemini_live/        # cliente Gemini Live
├── memory/             # memória temporal local
├── providers/          # provedores, roteamento e visão
├── screen/             # captura de tela
├── tests/              # testes Python
├── tools/              # navegador, arquivos, pesquisa e geração
├── ui/                 # interface Rich no terminal
├── webcam/             # captura de webcam
├── app.py              # entrada da aplicação
├── Iniciar_Agente.bat  # inicializador Windows
├── requirements.txt
└── README.md
```

Saídas geradas ficam em `Pictures/AgentePessoal/`; a memória privada fica em `memory/memory.json`. Esses dados locais não devem ser commitados.

---

## Requisitos

- Windows 10 ou 11.
- Python 3.12 e o launcher `py`.
- Internet e uma chave para cada serviço remoto que você escolher.
- Microfone/alto-falantes são opcionais para a conversa por voz; webcam só é necessária para captura de webcam ou Gemini Live.
- Node.js é opcional e necessário apenas para executar os testes da extensão.

---

## Instalação

### 1. Baixar o projeto

```powershell
git clone https://github.com/Thomas-Adrian-Soler-Nilsson/agente_pessoal.git
cd agente_pessoal
```

Se você já tem uma cópia do repositório, abra o PowerShell nessa pasta e pule o clone.

### 2. Criar e ativar o ambiente virtual

```powershell
py -3.12 -m venv .venv
.\.venv\Scripts\Activate.ps1
```

Se o PowerShell bloquear a ativação, permita scripts somente nesta janela e tente novamente:

```powershell
Set-ExecutionPolicy -Scope Process -ExecutionPolicy RemoteSigned
.\.venv\Scripts\Activate.ps1
```

### 3. Instalar dependências e criar configuração local

```powershell
python -m pip install --upgrade pip
python -m pip install -r requirements.txt
Copy-Item .env.example .env
```

---

## Configuração

Edite `.env` e preencha somente as chaves dos serviços que pretende usar. O arquivo `.env.example` documenta as variáveis aceitas e não contém segredos.

| Serviço | Variável | Uso |
| --- | --- | --- |
| Gemini | `GEMINI_API_KEY` | Gemini API, Gemini Live e Gemini TTS |
| Groq | `GROQ_API_KEY` | Chat Groq, Whisper STT e visão Groq |
| Mistral | `MISTRAL_API_KEY` | Chat Mistral |
| Token Harbor | `TOKENHARBOR_API_KEY` | Modelos compatíveis com OpenAI |
| OpenRouter | `OPENROUTER_API_KEY` | Chat e modelos visuais OpenRouter |
| NVIDIA | `NVIDIA_API_KEY` | NVIDIA NIM e, opcionalmente, TRELLIS |
| Ollama | `OLLAMA_BASE_URL` | Ollama local; para Ollama Cloud configure também `OLLAMA_API_KEY` |
| Hugging Face | `HF_TOKEN` ou `HF_API_KEY` | Chat, geração de imagens, TTS e outros modelos compatíveis |
| Fish Audio | `FISH_API_KEY` | Fish ASR e TTS |

Para voz, defina `STT_PROVIDER` (`local`, `groq` ou `fish`) e `TTS_PROVIDER` (`edge`, `fish`, `gemini` ou `huggingface`). O app também pergunta essas opções durante a inicialização.

Para análise de screenshots, configure ao menos um provedor visual. `VISION_MODEL_ORDER` aceita IDs `provedor/modelo` separados por vírgulas; deixe vazio para usar a ordem automática disponível no app. A imagem pode ser enviada a mais de um provedor se o fallback for necessário.

Exemplos de modelos e variáveis opcionais estão em `.env.example`. Não coloque chaves no código, no README ou em issues públicas. O `.gitignore` mantém `.env` fora do Git.

---

## Como usar

Inicie o app com o ambiente virtual ativo:

```powershell
python app.py
# ou
.\Iniciar_Agente.bat
```

Escolha um modo no menu. As opções atuais são Gemini, Groq, Mistral, Token Harbor, OpenRouter, NVIDIA, Ollama, Hugging Face e Automático. Gemini abre uma escolha entre Gemini API e Gemini Live. Os modelos disponíveis dependem da configuração local e do catálogo do provedor.

Depois, selecione STT e TTS. Para usar só texto, digite a solicitação no prompt. Durante a resposta, pressione `Esc` para interromper o raciocínio; digite `/voz` para iniciar uma interação por voz quando disponível.

### Avatar opcional

O avatar Live2D é opcional e fica desligado por padrão. Confirme a opção no menu para tentar carregá-lo; os arquivos de modelo precisam estar presentes em `avatar/models/`.

---

## Voz

O modo texto pergunta qual STT e TTS usar no início. `STT_PROVIDER` e `TTS_PROVIDER` em `.env` definem os valores padrão quando aplicável; os provedores também podem exigir suas chaves de API.

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

A reprodução/resposta pode ser interrompida manualmente com `Esc`. No modo texto, digite `/voz` para iniciar a entrada pelo microfone.

## Comandos do modo texto

| Comando | Efeito |
| --- | --- |
| `/voz` | inicia a entrada pelo microfone |
| `/loop [n]` | o agente continua sozinho por `n` rodadas depois da sua próxima mensagem (padrão 5, máximo 50) |
| `/loop off` | encerra o modo autônomo |
| `/goal <objetivo>` | define o objetivo e **já começa a trabalhar nele sozinho** por até 10 rodadas |
| `/goal off` | remove o objetivo e encerra o modo autônomo |
| `/verboso` | alterna entre o resumo legível e o JSON completo das ações |
| `/ajuda` | lista os comandos |

No modo autônomo cada rodada é enviada automaticamente, sem passar pelo prompt, e aparece no terminal como `Você › …` para você ver o que foi pedido. `Esc` interrompe o raciocínio e encerra o modo autônomo. O agente para sozinho quando responde começando com `OBJETIVO CONCLUÍDO` ou `TAREFA CONCLUÍDA`, ou quando o limite de rodadas acaba.

Durante a execução, cada ferramenta mostra uma linha `⚙ nome_da_ferramenta` **antes** de rodar (importante em capturas com análise visual, que levam segundos) e, ao terminar, um cartão com uma linha de resumo como `press · Enter · / → /a/chat/s/af7acbf0…`. Para ver o JSON cru de cada resposta, use `/verboso`.

### Tema visual

A CLI usa um esquema convencional e organizado — uma cor por papel — e o **vermelho fica reservado para a coruja** (a identidade visual do agente) e para o estado de falha:

| Elemento | Cor | Onde aparece |
| --- | --- | --- |
| Coruja (banner) | gradiente **vermelho** `#FA0716`–`#F95C34` | logo de abertura |
| Marca (`brand`) | azul `#38BDF8` | réguas, molduras, títulos de seção |
| Sucesso (`ok`) | verde `#4ADE80` | `✔` e status CONCLUÍDA |
| Aviso (`warn`) | âmbar `#FBBF24` | `⚠` e ferramenta repetida |
| Falha (`error`) | vermelho `#F87171` | `✖` e status FALHOU |
| Informação (`info`) / usuário | azul claro `#7DD3FC` | `ℹ`, `⚙`, prompt `Você ›` |
| Agente | violeta `#C4B5FD` | prefixo das respostas |
| Destaque (`accent`) | branco suave `#F1F5F9` | nomes de ferramenta e títulos de painel |
| Secundário (`muted`) | cinza `#9CA3AF` | textos de apoio |

Há dois gradientes, com papéis separados: `owl` (vermelho, só na coruja) e `chrome` (azul calmo, em réguas, molduras e no título do banner). Eles não se misturam — `tests/test_theme_palette.py` verifica isso. A borda das respostas alterna entre seis tons frios e calmos (azul, azul claro, violeta, água, índigo e azul suave), então duas mensagens seguidas não ficam idênticas sem virar arco-íris. O realce de código dos cartões usa o `monokai` padrão, que já tem fundo escuro próprio (sem ele o pygments usaria o fundo claro padrão e o texto claro ficaria ilegível).

As cores ficam todas em `ui/ui.py`: `THEME`, `BORDER_COLORS` e `_GRADIENTES`. `tests/test_theme_palette.py` trava o esquema: falha se alguém deixar a interface vermelha, se dois estados ficarem com a mesma cor ou se o vermelho aparecer fora da coruja e da falha.

### Animação e terminais problemáticos

O banner (coruja) e o indicador `● pensando...` são desenhados **uma única vez, sem animação**. Motivo medido: o `cmd.exe` não reposiciona o cursor como o rich espera, então cada quadro da animação ficava na tela e o logo aparecia empilhado dezenas de vezes.

Se o seu terminal se comportar bem e você quiser o gradiente animado:

```env
AGENTE_ANIMACAO=1
```

Com a animação ligada ela só roda em terminal com ≥ 40 colunas e ≥ 14 linhas, e **para sozinha** se a janela for redimensionada ou minimizada no meio dela. Para forçar o modo estático mesmo com a animação ligada:

```env
AGENTE_SEM_ANIMACAO=1
```

A detecção automática de fala durante o TTS pode ser ativada com:

```env
TTS_INTERRUPT_ENABLED=true
TTS_INTERRUPT_DELAY=0.7
TTS_INTERRUPT_THRESHOLD=0.08
```

`TTS_INTERRUPT_THRESHOLD` controla a sensibilidade do microfone. Valores maiores tornam a detecção menos sensível a ruídos.

---

## Chrome e screenshots

`browser_screenshot` captura uma aba HTTP/HTTPS do Chrome. O screenshot aparece como prévia colorida no CMD antes da análise; a prévia é renderizada em memória e não cria um arquivo no repositório. A imagem é enviada ao modelo visual escolhido, que retorna um alvo em coordenadas normalizadas de 0 a 1000; o agente converte essas coordenadas para pixels da imagem. Em fallback, provedores adicionais podem receber a mesma imagem.

Na inicialização do modo texto, escolha fallback automático, ordem personalizada para a sessão, um provedor fixo ou desative a análise. Para definir uma ordem padrão, configure `VISION_MODEL_ORDER` com IDs disponíveis `provedor/modelo` separados por vírgula:

```env
VISION_MODEL_ORDER=groq/qwen/qwen3.8-27b,gemini/gemma-4-31b-it,openrouter/google/gemma-4-31b-it:free
```

As rotas remotas aparecem quando as respectivas chaves estão configuradas. O Ollama local detecta modelos instalados com visão; `OLLAMA_LOCAL_VISION_MODEL` pode indicar um modelo específico. Para Ollama Cloud, configure `OLLAMA_API_KEY` e, opcionalmente, `OLLAMA_CLOUD_VISION_MODEL` e `OLLAMA_CLOUD_BASE_URL`. Os catálogos podem ser limitados com `OPENROUTER_VISION_MODELS`, `GEMINI_VISION_MODELS` e `GROQ_VISION_MODEL`.

Cada clique visual usa um `screenshot_id` e passa por validações de aba, URL, viewport e alvo. Um alvo ausente, ambíguo, uma página alterada ou um provedor indisponível interrompem a ação sem clicar. Ações externas podem pedir confirmação. Para páginas sensíveis, escolha um provedor local ou desative a análise.

---

## Limitações e privacidade

O projeto usa serviços locais e remotos. A chave e o modelo selecionados determinam para onde texto, áudio ou screenshots são enviados.

- Não compartilhe `.env`, `memory/memory.json`, perfis do navegador ou arquivos locais de sessão.
- A prévia do screenshot no terminal é temporária; a análise remota pode enviar a mesma captura a mais de um provedor de fallback.
- A extensão só opera em páginas HTTP/HTTPS e não controla páginas internas do Chrome.
- Campos de senha são bloqueados. Envios, compras, exclusões e outras ações externas podem exigir confirmação.
- A análise visual depende de quota, rede e disponibilidade dos provedores. Falhas/timeout significam que nenhuma coordenada utilizável foi produzida.

Antes de realizar um commit, confira os arquivos que serão enviados:

```powershell
git status --short
git status --short --ignored
```

---

## Testes e contribuição

Ative o ambiente virtual antes de executar os testes Python:

```powershell
python -m pytest -q
```

Os testes da extensão usam `node:test`:

```powershell
node --test browser_extension/field_policy.test.js browser_extension/service_worker_connection.test.js browser_extension/visual_state_guard.test.js
```

Ao contribuir, atualize `.env.example` e este README quando mudar variáveis, opções de menu, comandos ou comportamento visível. Não inclua chaves, memória local, perfis Chrome, logs ou saídas geradas. Execute os testes relevantes e revise `git status --short --ignored` antes de enviar alterações.

---

## Estado do projeto
## Licença

O projeto está em desenvolvimento. A disponibilidade de cada recurso depende das dependências, chaves de API, modelos locais e serviços de terceiros configurados.

---

## Autor

**Thomas Adrian Soler Nilsson**

Projeto pessoal desenvolvido em Python e em evolução contínua.

- GitHub: https://github.com/Thomas-Adrian-Soler-Nilsson
- Repositório: https://github.com/Thomas-Adrian-Soler-Nilsson/agente_pessoal

---

Nenhuma licença open-source foi definida neste momento. Consulte o autor antes de reutilizar ou redistribuir o projeto.
