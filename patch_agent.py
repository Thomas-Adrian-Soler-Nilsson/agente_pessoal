import sys

with open('providers/compatible_agent.py', 'r', encoding='utf-8') as f:
    code = f.read()

# Update web_open description and add focus_query
old_web_open_schema = '''        (
            "web_open",
            "Abre e extrai uma página pública por URL sem alterar a aba do Chrome. Retorna título, URL final, conteúdo e status de extração.",
            {"url": {"type": "string"}, "max_chars": {"type": "integer"}},
            ["url"],
        ),'''

new_web_open_schema = '''        (
            "web_open",
            "Abre e extrai passagens mais relevantes de uma página pública por URL. Retorna a saída formatada em Markdown com os trechos que mais dão 'match' na sua focus_query.",
            {"url": {"type": "string"}, "max_chars": {"type": "integer"}, "focus_query": {"type": "string", "description": "O que você quer extrair desta página? Ex: 'como usar a API'."}},
            ["url"],
        ),'''

if old_web_open_schema in code:
    code = code.replace(old_web_open_schema, new_web_open_schema)
    print('web_open schema patched')
else:
    print('web_open schema not found')

# Update deep_search description
old_deep_schema = '''        (
            "deep_search",
            (
                "Pesquisa várias fontes públicas, lê cada uma e retorna conteúdo/status por URL. Use quando pedirem aprofundamento/comparação."
            ),
            {
                "query": {'''

new_deep_schema = '''        (
            "deep_search",
            (
                "Pesquisa várias fontes públicas, lê as passagens mais relevantes de cada uma e retorna os excertos formatados em Markdown limpo. Economiza tokens focando apenas na resposta."
            ),
            {
                "query": {'''

if old_deep_schema in code:
    code = code.replace(old_deep_schema, new_deep_schema)
    print('deep_search schema patched')
else:
    print('deep_search schema not found')

with open('providers/compatible_agent.py', 'w', encoding='utf-8') as f:
    f.write(code)

