import copy
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

DESENVOLVIMENTO MULTILINGUAGEM:
- Use detect_runtimes antes de escolher um runtime quando a linguagem nao estiver clara.
- Use run_code_file para executar um arquivo; ele suporta varios runtimes instalados.
- Prefira run_code_file a execute_file para codigo; execute_file fica para compatibilidade com HTML legado.
- Use run_terminal para testes, builds, git e comandos de desenvolvimento no workspace.
- Use open_terminal somente quando Thomas pedir explicitamente uma janela visível do CMD.
- Use install_dependencies somente quando Thomas pedir para instalar dependencias.
- Use download_file para baixar arquivos HTTP/HTTPS; nao use curl/wget no terminal.
- Depois de editar codigo, valide e execute o teste adequado, analisando codigo de saida, stdout e stderr.
- Nao tente acessar, imprimir ou copiar chaves, tokens, senhas ou arquivos .env.

- Use ferramentas somente quando elas forem realmente necessárias.
- Não repita a mesma chamada de ferramenta com os mesmos argumentos.
- Se uma ferramenta já retornou informação suficiente para responder, pare de usar ferramentas.
- Para análise de código, normalmente uma única leitura do arquivo é suficiente.
- Se read_file já retornou o conteúdo de um caminho nesta solicitação,
  use esse conteúdo em vez de ler o mesmo arquivo novamente.
- Não leia novamente um arquivo apenas para confirmar o conteúdo.
- Não fique em um ciclo de ferramentas tentando obter exatamente a mesma informação.
- Depois de obter dados suficientes, produza a resposta final.
- Para tarefas de criação de código, seja objetivo: faça o menor número de
  chamadas necessárias. Em geral: escreva o arquivo, execute uma vez e só
  corrija se o resultado realmente indicar erro.
- Não use marcadores de emoção como [calm] ou [happy] em chamadas de
  ferramenta nem dentro de código. Eles são reservados à síntese de voz.
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

REGRAS PRÁTICAS DA MEMÓRIA:
- Não salve mensagens inteiras, arquivos, código ou fatos que só valem para a
  solicitação atual.
- Antes de salvar uma preferência, objetivo ou fato recorrente, procure uma
  memória relacionada para evitar duplicatas.
- Se a informação já existir, use update_memory quando Thomas estiver
  corrigindo ou renovando o dado; não salve outra cópia.
- Use list_memory quando Thomas pedir para ver ou organizar suas memórias.
- Use delete_memory somente após um pedido explícito para esquecer/remover.
- Não invente memory_id: obtenha-o com search_memory ou list_memory.

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
  3. Prefira write_file para arquivos pequenos ou médios, pois ele grava de
     forma atômica e evita várias chamadas duplicadas. Use edit_file para uma
     alteração localizada. Use write_file_chunk apenas quando o conteúdo for
     realmente grande ou quando uma chamada única for cortada pelo provedor;
     não fragmente um arquivo desnecessariamente em dezenas de chamadas.
4. Não peça para Thomas copiar e colar manualmente.
5. Confirme o caminho retornado pela ferramenta.

Quando Thomas pedir para executar, testar ou rodar um arquivo:

1. Verifique qual arquivo deve ser executado.
2. Para Python, JavaScript, TypeScript e outros scripts, prefira run_code_file.
   Use execute_file principalmente para abrir HTML no navegador.
3. Analise STDOUT, STDERR e código de saída.
4. Se houver erro, explique o erro.
5. Quando possível, corrija o arquivo usando edit_file ou write_file_chunk.
6. Execute novamente para validar a correção.

Para programas interativos que usam input(), nunca execute o processo sem dados.
Use input_text com entradas de teste completas ou passe argumentos de linha de
comando. Se um processo exceder o timeout, nao repita o mesmo comando: analise
se ele ficou esperando stdin, corrija a chamada e tente uma unica vez.
Depois de uma execucao com Exit code diferente de 0, nao repita a mesma chamada
sem alterar o comando, os argumentos ou o arquivo responsavel pelo erro.

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
CHECKLIST OBRIGATORIO DE CODIGO:
- Nao diga que algo foi executado apenas porque foi escrito.
- Se Thomas pedir para rodar, faca pelo menos uma chamada de execucao e leia o resultado.
- Se o resultado tiver Status: failure ou Status: timeout, corrija a causa antes de responder.
- Nao faca tres tentativas equivalentes: altere o comando, forneca stdin ou corrija o arquivo.
- Para uma calculadora ou script interativo, prefira argumentos de teste ou input_text e
  confirme um resultado deterministico, como `Resultado: 8`.

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

Para modelos 3D, use generate_3d_rodin ou generate_3d_trify quando houver
uma chave do respectivo provedor configurada. Essas ferramentas aceitam um
prompt ou image_path e fazem o polling até o arquivo GLB ficar disponível.
Quando Thomas quiser uma opção gratuita sem chave, use generate_3d_free.
Ela gera um rascunho GLB a partir de um único prompt.
Quando houver NVIDIA_API_KEY ou NVIDIA_TRELLIS_API_KEY, use
generate_3d_nvidia para chamar o NVIDIA TRELLIS; ele aceita texto ou imagem
e retorna um GLB diretamente.
Use generate_3d_local somente quando TRIPOSR_PATH estiver configurado.

REGRA 3D: para um pedido comum de gerar um modelo 3D, use generate_3d_auto.
Ela prioriza NVIDIA TRELLIS quando houver chave configurada e usa three.ws
como fallback gratuito. Use
generate_3d_free somente quando Thomas pedir explicitamente a opcao sem chave.
Se uma ferramenta 3D retornar erro de indisponibilidade, pare de tentar outras
ferramentas 3D e informe o erro ao Thomas; nao pesquise na web para substituir
uma falha de geraÃ§ao.

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
MAX_TOOL_ROUNDS = 12


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
    "list_memory",
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
                "Ferramenta legada para abrir HTML no navegador. "
                "Para Python, JavaScript, TypeScript e qualquer codigo executavel, "
                "use run_code_file; nao use execute_file para scripts. "
                "Use execute_file somente em arquivos HTML (.html/.htm). "
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
            "run_terminal",
            (
                "Executa um comando de terminal no diretorio informado, com timeout e saida limitada. "
                "Use para testes, builds e comandos de desenvolvimento. Comandos destrutivos, downloads "
                "via shell e acesso a segredos sao bloqueados; use as ferramentas dedicadas. "
                "Para processos interativos, envie input_text ou o processo pode aguardar ate o timeout."
            ),
            {
                "command": {"type": "string", "description": "Comando de terminal a executar."},
                "cwd": {"type": "string", "description": "Diretorio de trabalho dentro das pastas permitidas."},
                "timeout": {"type": "integer", "description": "Limite em segundos; padrao 120."},
                "input_text": {"type": "string", "description": "Texto opcional enviado ao stdin do processo; use para programas interativos."},
            },
            ["command"],
        ),
        (
            "open_terminal",
            (
                "Abre um CMD visível para Thomas acompanhar um comando. Use somente quando ele pedir "
                "explicitamente para abrir o terminal, executar visivelmente ou acompanhar a execução."
            ),
            {
                "command": {"type": "string", "description": "Comando a executar no CMD visível."},
                "cwd": {"type": "string", "description": "Diretório de trabalho dentro das pastas permitidas."},
            },
            ["command"],
        ),
        (
            "detect_runtimes",
            "Detecta linguagens, compiladores, runtimes e gerenciadores de pacotes disponiveis no PATH.",
            {},
            [],
        ),
        (
            "run_code_file",
            (
                "Executa um arquivo de codigo usando o runtime correspondente. Suporta Python, JavaScript, TypeScript, "
                "Go, Rust, C, C++, Java, Kotlin, Ruby, PHP, Perl, Lua, R, Swift, Dart, Elixir, PowerShell, Bash e batch "
                "quando os compiladores/runtimes estiverem instalados."
            ),
            {
                "path": {"type": "string", "description": "Arquivo de codigo a executar."},
                "arguments": {"type": "string", "description": "Argumentos opcionais do programa."},
                "timeout": {"type": "integer", "description": "Limite em segundos; padrao 120."},
                "input_text": {"type": "string", "description": "Texto opcional enviado ao stdin; use para scripts que pedem input()."},
            },
            ["path"],
        ),
        (
            "install_dependencies",
            (
                "Instala dependencias de um projeto ou pacotes explicitos. Detecta requirements.txt, pyproject.toml, "
                "package.json, Cargo.toml, go.mod, composer.json, Maven e Gradle. So use quando Thomas pedir instalacao."
            ),
            {
                "path": {"type": "string", "description": "Pasta do projeto; padrao workspace."},
                "manager": {"type": "string", "description": "auto, pip, npm, pnpm, yarn, cargo, go, dotnet, gem, composer, maven ou gradle."},
                "packages": {"type": "string", "description": "Pacotes separados por espaco; opcional com manager=auto."},
                "dev": {"type": "boolean", "description": "Instala como dependencia de desenvolvimento quando suportado."},
                "timeout": {"type": "integer", "description": "Limite em segundos; padrao 900."},
            },
            [],
        ),
        (
            "download_file",
            (
                "Baixa um arquivo HTTP/HTTPS para uma pasta permitida, com limite de 100 MB. "
                "Use para assets e arquivos de projeto; nao exponha tokens na URL."
            ),
            {
                "url": {"type": "string", "description": "URL HTTP ou HTTPS."},
                "path": {"type": "string", "description": "Caminho de destino dentro das pastas permitidas."},
                "overwrite": {"type": "boolean", "description": "Permite substituir um arquivo existente."},
                "timeout": {"type": "integer", "description": "Limite em segundos; padrao 120."},
            },
            ["url", "path"],
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
            "generate_3d_local",
            (
                "Gera um modelo 3D localmente usando TripoSR, sem consumir "
                "créditos de API. Requer uma imagem de referência e "
                "TRIPOSR_PATH configurado."
            ),
            {
                "image_path": {
                    "type": "string",
                    "description": "Caminho de uma imagem PNG, JPG ou WEBP do objeto.",
                },
                "timeout": {
                    "type": "integer",
                    "description": "Tempo máximo em segundos; padrão 900.",
                },
            },
            ["image_path"],
        ),
        (
            "generate_3d_rodin",
            (
                "Gera um modelo 3D hospedado pela Hyper3D/Rodin, sem instalar "
                "um modelo local. Aceita prompt ou image_path. Requer "
                "RODIN_API_KEY e pode consumir créditos do provedor."
            ),
            {
                "prompt": {
                    "type": "string",
                    "description": "Descrição textual do objeto; opcional se image_path for informado.",
                },
                "image_path": {
                    "type": "string",
                    "description": "Caminho opcional de uma imagem PNG, JPG ou WEBP do objeto.",
                },
            },
            [],
        ),
        (
            "generate_3d_trify",
            (
                "Gera um modelo 3D hospedado pela Trify3D, sem instalar um "
                "modelo local. Aceita prompt ou image_path. Requer "
                "TRIFY3D_API_KEY com permissão de escrita e pode consumir "
                "créditos do provedor."
            ),
            {
                "prompt": {
                    "type": "string",
                    "description": "Descrição textual do objeto; opcional se image_path for informado.",
                },
                "image_path": {
                    "type": "string",
                    "description": "Caminho opcional de uma imagem PNG, JPG ou WEBP do objeto.",
                },
            },
            [],
        ),
        (
            "generate_3d_free",
            (
                "Gera gratuitamente um rascunho 3D GLB via three.ws, sem API "
                "key, conta ou instalação local. Aceita somente um prompt de "
                "um único objeto; a qualidade é de protótipo e há limite por IP."
            ),
            {
                "prompt": {
                    "type": "string",
                    "description": "Descrição de um único objeto, entre 3 e 1000 caracteres.",
                },
                "timeout": {
                    "type": "integer",
                    "description": "Tempo máximo em segundos; padrão 600.",
                },
            },
            ["prompt"],
        ),
        (
            "generate_3d_nvidia",
            (
                "Gera um modelo 3D GLB com o NVIDIA TRELLIS hospedado. Aceita "
                "prompt de até 77 caracteres ou image_path. Requer "
                "NVIDIA_TRELLIS_API_KEY ou NVIDIA_API_KEY; a API pode ter "
                "limites de uso do plano de desenvolvimento."
            ),
            {
                "prompt": {
                    "type": "string",
                    "description": "Descrição curta do objeto, até 77 caracteres; opcional se image_path for informado.",
                },
                "image_path": {
                    "type": "string",
                    "description": "Caminho opcional de imagem PNG, JPG ou WEBP do objeto.",
                },
                "timeout": {
                    "type": "integer",
                    "description": "Tempo máximo em segundos; padrão 900.",
                },
            },
            [],
        ),
        (
            "generate_3d_auto",
            (
                "Ferramenta PRINCIPAL para qualquer pedido comum de geraÃ§Ã£o 3D. "
                "Prioriza NVIDIA TRELLIS quando houver chave configurada e usa "
                "three.ws gratuito como fallback para prompts "
                "de texto. Aceita prompt ou imagem."
            ),
            {
                "prompt": {
                    "type": "string",
                    "description": "DescriÃ§Ã£o do objeto; para NVIDIA TRELLIS, prefira atÃ© 77 caracteres.",
                },
                "image_path": {
                    "type": "string",
                    "description": "Caminho opcional da imagem de referÃªncia.",
                },
                "timeout": {
                    "type": "integer",
                    "description": "Tempo mÃ¡ximo em segundos; padrÃ£o definido pelo backend.",
                },
            },
            [],
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
                "expires_at": {
                    "type": "string",
                    "description": "Data ISO opcional para fatos temporários.",
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
        (
            "list_memory",
            "Lista memórias persistentes, opcionalmente por categoria. Use quando Thomas pedir para consultar ou organizar a memória.",
            {
                "category": {"type": "string"},
                "limit": {"type": "integer", "minimum": 1, "maximum": 100},
            },
            [],
        ),
        (
            "update_memory",
            "Atualiza uma memória existente. Use somente para corrigir ou renovar uma informação identificada pelo ID.",
            {
                "memory_id": {"type": "string"},
                "content": {"type": "string"},
                "category": {"type": "string"},
                "importance": {"type": "number", "minimum": 0, "maximum": 1},
                "expires_at": {"type": "string"},
            },
            ["memory_id"],
        ),
        (
            "delete_memory",
            "Remove uma memória persistente. Use somente quando Thomas pedir explicitamente para esquecer ou apagar uma informação.",
            {"memory_id": {"type": "string"}},
            ["memory_id"],
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
        self._operation_view_open = False

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

    def _shrink_context(self, max_chars: int = 8000):
        """Cria um payload compacto sem destruir o histórico local completo."""
        compacted = copy.deepcopy(self.messages)
        for message in compacted:
            # Só resultados de ferramentas podem ser compactados. O histórico
            # original, incluindo mensagens do usuário e respostas do agente,
            # permanece intacto em self.messages para a próxima rodada.
            if message.get("role") != "tool":
                continue
            content = message.get("content")
            if not isinstance(content, str) or len(content) <= max_chars:
                continue
            half = max_chars // 2
            message["content"] = (
                content[:half]
                + "\n\n[RESULTADO COMPACTADO SÓ PARA ESTA TENTATIVA; "
                "O HISTÓRICO LOCAL COMPLETO FOI PRESERVADO]\n\n"
                + content[-half:]
            )
        return compacted

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

    @staticmethod
    def _message_text(message) -> str:
        """Extrai texto sem quebrar em providers que retornam blocos/listas."""
        content = getattr(message, "content", None)
        if isinstance(content, list):
            parts = []
            for part in content:
                if isinstance(part, str):
                    parts.append(part)
                elif isinstance(part, dict) and part.get("text"):
                    parts.append(str(part["text"]))
                elif getattr(part, "text", None):
                    parts.append(str(part.text))
            content = "\n".join(parts)
        return str(content or "")

    # ============================================================
    # COMPLETION
    # ============================================================

    def _completion(self, cancel_event=None, **kwargs):
        request_kwargs = dict(kwargs)
        for attempt in range(2):
            if cancel_event is not None and cancel_event.is_set():
                raise CancellationRequested()

            try:
                # OpenAI-compatible providers use the newer
                # ``max_completion_tokens`` name. Hugging Face's
                # InferenceClient still expects ``max_tokens``.
                client_module = type(self.client).__module__
                if (
                    "huggingface_hub" in client_module
                    and "max_completion_tokens" in request_kwargs
                    and "max_tokens" not in request_kwargs
                ):
                    request_kwargs["max_tokens"] = request_kwargs.pop("max_completion_tokens")
                if "huggingface_hub" in client_module:
                    request_kwargs.pop("include_reasoning", None)

                response = self.client.chat.completions.create(
                    **request_kwargs
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

                    request_kwargs["messages"] = self._shrink_context()

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
                    "Tentando novamente em 2 segundos..."
                )

                if cancel_event is not None:
                    if cancel_event.wait(2):
                        raise CancellationRequested()
                else:
                    time.sleep(2)

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
        expires_at = arguments.get("expires_at")

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
            expires_at=expires_at,
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
            return (
                "Nenhuma memória relevante foi encontrada "
                f"para: {query}"
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

    def _list_memory(self, arguments: dict) -> str:
        category = str(arguments.get("category", "")).strip() or None
        try:
            limit = int(arguments.get("limit", 20))
        except (TypeError, ValueError):
            limit = 20
        memories = self.temporal_memory.list_memories(category=category, limit=limit)
        return json.dumps(memories, ensure_ascii=False)

    def _update_memory(self, arguments: dict) -> str:
        memory_id = str(arguments.get("memory_id", "")).strip()
        if not memory_id:
            return "Não foi possível atualizar a memória: informe memory_id."
        fields = {
            key: arguments[key]
            for key in ("content", "category", "importance", "expires_at")
            if key in arguments
        }
        if not fields:
            return "Não foi possível atualizar a memória: nenhum campo foi informado."
        try:
            memory = self.temporal_memory.update(memory_id, **fields)
        except (TypeError, ValueError) as error:
            return f"Erro ao atualizar memória: {error}"
        if memory is None:
            return f"Memória não encontrada: {memory_id}"
        return "Memória atualizada com sucesso: " + json.dumps(memory, ensure_ascii=False)

    def _delete_memory(self, arguments: dict) -> str:
        memory_id = str(arguments.get("memory_id", "")).strip()
        if not memory_id:
            return "Não foi possível remover a memória: informe memory_id."
        if not self.temporal_memory.delete(memory_id):
            return f"Memória não encontrada: {memory_id}"
        return f"Memória removida com sucesso: {memory_id}"

    # ============================================================
    # TOOL CALLS
    # ============================================================

    @staticmethod
    def _canonical_tool_arguments(arguments: dict, tool_name: str = "") -> dict:
        """Normaliza caminhos e comandos para detectar repetições reais."""
        normalized = dict(arguments or {})
        for key in ("path", "cwd"):
            value = normalized.get(key)
            if isinstance(value, str) and value.strip():
                try:
                    normalized[key] = str(Path(value).expanduser().resolve()).lower()
                except (OSError, RuntimeError, TypeError, ValueError):
                    normalized[key] = value.strip().lower()
        if isinstance(normalized.get("command"), str):
            normalized["command"] = " ".join(normalized["command"].split())
        if tool_name == "edit_file":
            normalized.setdefault("expected_replacements", 1)
        if tool_name in {"run_terminal", "run_code_file"}:
            normalized.setdefault("timeout", 120)
            normalized.setdefault("input_text", None)
        return normalized

    def _tool_call_key(self, call) -> str:
        try:
            arguments = parse_tool_arguments(
                call.function.arguments or "{}"
            )

            arguments = self._canonical_tool_arguments(arguments, call.function.name)

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

            elif tool_name == "list_memory":
                result = self._list_memory(arguments)

            elif tool_name == "update_memory":
                result = self._update_memory(arguments)

            elif tool_name == "delete_memory":
                result = self._delete_memory(arguments)

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
            elif tool_name in {"execute_file", "run_code_file", "run_terminal"}:
                result_text = str(result).lower()
                success_markers = (
                    "código de saída: 0",
                    "codigo de saida: 0",
                    "exit code: 0",
                    "process exited with code 0",
                )
                self.operation_state.execution_status = (
                    "passed" if any(marker in result_text for marker in success_markers) else "failed"
                )

            result_text = str(result).strip().lower()
            failure_prefixes = (
                "erro",
                "error",
                "edição não aplicada",
                "ediÃ§Ã£o nÃ£o aplicada",
                "operação bloqueada",
                "operaÃ§Ã£o bloqueada",
            )
            if result_text.startswith(failure_prefixes):
                self.operation_state.record_error(str(result))
            else:
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
        arguments_by_id = {}
        repeated_ids = set()
        pending = []

        for call in tool_calls:

            if cancel_event is not None and cancel_event.is_set():
                return

            tool_key = self._tool_call_key(call)
            self.operation_state.record_tool(call.function.name)

            if tool_key in executed_tool_calls:

                repeated_ids.add(call.id)
                try:
                    arguments_by_id[call.id] = parse_tool_arguments(
                        call.function.arguments or "{}"
                    )
                except ToolArgumentsError:
                    arguments_by_id[call.id] = {}

                results_by_id[call.id] = tool_results.get(tool_key) or (
                    "Esta mesma ferramenta com os mesmos argumentos "
                    "já foi executada nesta solicitação. "
                    "Use o resultado anterior em vez de repetir a chamada."
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
                arguments_by_id[call.id] = {}

                continue

            executed_tool_calls.add(tool_key)
            arguments_by_id[call.id] = arguments
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

        for call, tool_key, arguments in sequential_batch:

            if cancel_event is not None and cancel_event.is_set():
                return

            result = self._run_tool(
                call.function.name,
                arguments,
            )

            tool_results[tool_key] = result
            results_by_id[call.id] = result


        # A interface mostra cada chamada uma única vez, na ordem em que o
        # modelo a pediu, mesmo quando leituras foram executadas em paralelo.
        if not self._operation_view_open:
            ui.chat_operation_header(self.operation_state.objective)
            self._operation_view_open = True
        for call in tool_calls:
            ui.chat_tool(
                call.function.name,
                repeated=call.id in repeated_ids,
                arguments=arguments_by_id.get(call.id),
                result=results_by_id.get(call.id, "Erro interno: resultado da ferramenta não encontrado."),
            )

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

        # O estado de inspeção pertence a esta solicitação. Mantê-lo entre
        # mensagens fazia uma leitura antiga parecer coberta pela inspeção
        # atual e confundia tanto o modelo quanto a interface.
        self._inspected_roots.clear()
        self.operation_state.reset(user_message)
        self._operation_view_open = False

        executed_tool_calls = set()
        tool_results = {}
        json_recovery_attempts = 0
        empty_response_retries = 0

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
                self._message_text(message)
            )

            if cancel_event is not None and cancel_event.is_set():
                return

            if content:
                self.messages.append(
                    {
                        "role": "assistant",
                        "content": content,
                    }
                )
                if self._operation_view_open:
                    ui.chat_operation_summary(self.operation_state.summary())
                yield content
                return

            if empty_response_retries < 2:
                empty_response_retries += 1
                ui.chat_notice(
                    "O provider retornou uma resposta vazia. "
                    "Continuando com o contexto e as ferramentas já disponíveis."
                )
                # Não adiciona uma mensagem de assistente vazia. Uma mensagem
                # vazia depois de um tool result faz alguns providers
                # OpenAI-compatible rejeitarem a próxima edição. O usuário de
                # recuperação é curto, preserva todo o histórico e orienta o
                # modelo a continuar a tarefa, não a recomeçar.
                self.messages.append(
                    {
                        "role": "user",
                        "content": (
                            "Continue a tarefa a partir dos resultados das ferramentas "
                            "já executadas. Preserve o contexto e, se a solicitação "
                            "for de código, faça agora a edição necessária; não gere "
                            "um resumo ainda."
                        ),
                    }
                )
                continue

            ui.chat_notice(
                "O provider continuou sem texto após as tentativas de continuação. "
                "Gerando um resumo de recuperação."
            )
            break

        if cancel_event is not None and cancel_event.is_set():
            return

        # O resumo final precisa de uma instrução explícita. Sem ela, alguns
        # modelos recebem apenas o último resultado de ferramenta e retornam
        # content vazio ou tentam iniciar outra leitura do zero.
        self.messages.append(
            {
                "role": "user",
                "content": (
                    "Conclua a solicitação original usando todo o contexto e os "
                    "resultados já presentes nesta conversa. Se ainda faltar uma "
                    "alteração de código necessária, faça-a com a ferramenta; "
                    "caso contrário, responda com um resumo curto do que foi feito."
                ),
            }
        )

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
                self._message_text(final_message)
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

            has_tool_history = any(
                message.get("role") == "tool"
                for message in self.messages
                if isinstance(message, dict)
            )
            if self._is_tool_choice_conflict(error) or has_tool_history:

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
                            self._message_text(final_message)
                        )

                    else:
                        content = self._clean_model_output(
                            self._message_text(retry_message)
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
            if self._operation_view_open:
                ui.chat_operation_summary(self.operation_state.summary())
            yield content
        else:
            content = (
                "A operação terminou, mas o provedor não retornou um resumo. "
                "O estado abaixo mostra o que foi lido e alterado."
            )
            if self._operation_view_open:
                ui.chat_operation_summary(self.operation_state.summary())
            yield content
