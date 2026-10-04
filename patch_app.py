import sys

with open('app.py', 'r', encoding='utf-8') as f:
    code = f.read()

old_web_open = 'return open_public_page(arguments.get("url", ""), arguments.get("max_chars", 12000))'
new_web_open = 'return open_public_page(arguments.get("url", ""), arguments.get("max_chars", 12000), arguments.get("focus_query", ""))'

if old_web_open in code:
    code = code.replace(old_web_open, new_web_open)
    with open('app.py', 'w', encoding='utf-8') as f:
        f.write(code)
    print('app.py patched')
else:
    print('old_web_open not found')
