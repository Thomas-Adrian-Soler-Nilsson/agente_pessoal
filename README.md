# Agente Pessoal

Agente de voz local para Windows, com conversa em portugues do Brasil, acesso controlado a arquivos, abertura de aplicativos e visao por tela ou webcam.

## Modos

- **Gemini Live**: conversa de voz em tempo real, tela, webcam e acompanhamento continuo.
- **Groq**: conversa por STT/TTS local e selecao de modelo.
- **OpenRouter**: conversa por STT/TTS local e selecao de modelo.
- **NVIDIA**: conversa por STT/TTS local usando a API NVIDIA NIM e selecao de modelo.
- **Automatico**: tenta Groq, OpenRouter e NVIDIA nessa ordem, preservando o contexto.

## Requisitos

- Windows com Python 3.12 ou compativel.
- Microfone e saida de audio.
- Webcam apenas para os recursos de webcam.
- Chaves para os provedores que serao usados.

## Instalacao

No PowerShell, dentro da pasta do projeto:

```powershell
python -m venv .venv
.\.venv\Scripts\Activate.ps1
python -m pip install -r requirements.txt
Copy-Item .env.example .env
```

Edite `.env` apenas localmente e preencha as chaves:

```env
GEMINI_API_KEY=sua_chave_gemini
GROQ_API_KEY=sua_chave_groq
OPENROUTER_API_KEY=sua_chave_openrouter
NVIDIA_API_KEY=sua_chave_nvidia
FISH_API_KEY=sua_chave_fish
FISH_VOICE_ID=id_da_sua_voz_fish
FISH_VOICES=Voz principal=id_1,Voz alternativa=id_2
```

Nunca envie `.env` para o Git. Ele ja esta protegido pelo `.gitignore`.

## Executar

```powershell
.\.venv\Scripts\Activate.ps1
python app.py
```

Escolha o provedor no menu. Groq, OpenRouter e NVIDIA exibem os modelos configurados em `GROQ_MODELS`, `OPENROUTER_MODELS` e `NVIDIA_MODELS`, separados por virgulas. Os modelos padrao podem ser alterados com `GROQ_MODEL`, `OPENROUTER_MODEL` e `NVIDIA_MODEL`.

O TTS tenta interromper a fala quando detecta sua voz. Ajuste a sensibilidade se necessario:

```env
TTS_INTERRUPT_THRESHOLD=0.08
```

Valores maiores reduzem interrupcoes causadas pelo ruido ou pelo proprio alto-falante.

Para evitar que o som do proprio computador interrompa a resposta, a interrupcao por voz fica desativada por padrao. Para reativar:

```env
TTS_INTERRUPT_ENABLED=true
TTS_INTERRUPT_DELAY=0.7
```

Durante uma resposta falada, pressione `Esc` para interromper imediatamente sem encerrar o agente. A interrupcao por voz pode ser ativada nas variaveis acima.

O TTS usa Edge TTS por padrao. Para usar Fish Audio, instale as dependencias e configure:

```env
TTS_PROVIDER=fish
FISH_API_KEY=sua_chave_fish
FISH_VOICE_ID=id_da_sua_voz_fish
FISH_MODEL=s2.1-pro-free
```

Ao iniciar uma sessao com Fish Audio, o agente exibe as vozes configuradas e permite escolher uma. Use `FISH_VOICES` no formato `Nome=reference_id`, separado por virgulas. Para voltar ao Edge TTS, use `TTS_PROVIDER=edge` ou remova essa variavel. O texto enviado ao Fish Audio preserva tags de emocao, como `[excited]`.

A ferramenta de leitura extrai texto de arquivos `.txt`, `.md`, codigo, `.pdf` e `.docx`. PDFs escaneados que contem apenas imagens precisam de OCR e ainda nao sao extraidos automaticamente.

## Ferramentas locais

Os providers de texto compartilham as ferramentas de computador, arquivos, tela e webcam. Por seguranca, os arquivos ficam limitados a Desktop, Documents, Downloads e OneDrive, e operacoes destrutivas nao sao oferecidas.

## Seguranca

- Chaves, ambientes virtuais, caches, audios e capturas locais sao ignorados pelo Git.
- Nao coloque tokens no README, no codigo ou em commits.
- Se uma chave for exposta, revogue-a no painel do provedor e gere outra.
- Revise o resultado de `git status --short` antes de qualquer `git push`.

## Git

Inicialize o repositorio e confira os arquivos ignorados:

```powershell
git init
git status --short
git status --short --ignored
```

O primeiro commit pode ser criado depois de revisar o status:

```powershell
git add .
git commit -m "Inicializa agente pessoal"
```

Este projeto nao define um repositorio remoto. Configure o remote somente depois de confirmar que nenhum segredo aparece no staging.
