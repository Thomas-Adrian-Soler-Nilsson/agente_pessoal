# Agente Pessoal

Agente de voz local para Windows, com conversa em portugues do Brasil, acesso controlado a arquivos, abertura de aplicativos e visao por tela ou webcam.

## Modos

- **Gemini Live**: conversa de voz em tempo real, tela, webcam e acompanhamento continuo.
- **Groq**: conversa por STT/TTS local e selecao de modelo.
- **OpenRouter**: conversa por STT/TTS local e selecao de modelo.
- **Automatico**: tenta Groq primeiro e usa OpenRouter como fallback, preservando o contexto.

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
```

Nunca envie `.env` para o Git. Ele ja esta protegido pelo `.gitignore`.

## Executar

```powershell
.\.venv\Scripts\Activate.ps1
python app.py
```

Escolha o provedor no menu. Groq e OpenRouter exibem os modelos configurados em `GROQ_MODELS` e `OPENROUTER_MODELS`, separados por virgulas. O modelo padrao pode ser alterado com `GROQ_MODEL` e `OPENROUTER_MODEL`.

O TTS tenta interromper a fala quando detecta sua voz. Ajuste a sensibilidade se necessario:

```env
TTS_INTERRUPT_THRESHOLD=0.08
```

Valores maiores reduzem interrupcoes causadas pelo ruido ou pelo proprio alto-falante.

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
