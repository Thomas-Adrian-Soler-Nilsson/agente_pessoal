import sys

with open('tools/web_research.py', 'r', encoding='utf-8') as f:
    code = f.read()

# Imports to add
imports = '''
import re
import math
from bs4 import BeautifulSoup
'''

if 'from bs4' not in code:
    code = code.replace('import requests\n', 'import requests\n' + imports)

# Function to add
passage_logic = '''
def _score_passage(passage: str, terms: list[str]) -> float:
    if not terms:
        return 1.0
    passage_lower = passage.lower()
    score = 0.0
    for term in terms:
        count = passage_lower.count(term)
        if count > 0:
            score += (1.0 + math.log(count)) * len(term)
    return score

def _extract_relevant_passages(text: str, query: str, max_chars: int) -> str:
    if not text:
        return ""
    text = re.sub(r'\\n{3,}', '\\n\\n', text)
    blocks = [b.strip() for b in text.split('\\n\\n') if len(b.strip()) > 20]
    if not blocks:
        blocks = [b.strip() for b in text.split('\\n') if len(b.strip()) > 20]
    if not blocks:
        return text[:max_chars]
        
    if not query:
        result = []
        current_len = 0
        for b in blocks:
            if current_len + len(b) > max_chars and result:
                break
            result.append(b)
            current_len += len(b) + 2
        return "\\n\\n".join(result)

    terms = [t for t in re.split(r'\\W+', query.lower()) if len(t) > 2]
    
    scored = []
    for i, b in enumerate(blocks):
        scored.append((_score_passage(b, terms), i, b))
        
    scored.sort(key=lambda x: x[0], reverse=True)
    
    selected = []
    current_len = 0
    for score, i, b in scored:
        if current_len + len(b) > max_chars and selected:
            continue
        selected.append((i, b))
        current_len += len(b) + 2
        if current_len >= max_chars:
            break
            
    selected.sort(key=lambda x: x[0])
    return "\\n\\n[... ...]\\n\\n".join(b for i, b in selected)

'''

if '_score_passage' not in code:
    code = code.replace('def discover_sources', passage_logic + 'def discover_sources')

# Modify open_public_page signature and logic
old_open = 'def open_public_page(url: str, max_chars: int = 12000) -> dict:'
new_open = 'def open_public_page(url: str, max_chars: int = 12000, focus_query: str = "") -> dict:'
code = code.replace(old_open, new_open)

old_extraction = '''        extracted = trafilatura.extract(raw, include_comments=False, include_tables=True, output_format="txt")
        if not extracted:
            status = "extraction_failure"
            content = ""
        else:
            status = "success"
            content = extracted[:max(500, min(int(max_chars or 12000), 24000))]
            if len(extracted) > len(content):
                content += "\\n[TRUNCATED]"'''

new_extraction = '''        extracted = trafilatura.extract(raw, include_comments=False, include_tables=True, output_format="txt")
        if not extracted or len(extracted.strip()) < 50:
            # Fallback to BeautifulSoup
            soup = BeautifulSoup(raw, "html.parser")
            for tag in soup(['script', 'style', 'nav', 'footer', 'header', 'aside']):
                tag.decompose()
            extracted = soup.get_text(separator='\\n\\n', strip=True)
            
        if not extracted or len(extracted.strip()) < 20:
            status = "extraction_failure"
            content = ""
        else:
            status = "success"
            # Limit total char budget for performance
            max_limit = max(500, min(int(max_chars or 12000), 24000))
            best_passages = _extract_relevant_passages(extracted, focus_query, max_limit)
            content = best_passages'''

code = code.replace(old_extraction, new_extraction)

old_submit = 'pool.submit(open_public_page, item["url"], max_chars_per_site)'
new_submit = 'pool.submit(open_public_page, item["url"], max_chars_per_site, focus_query=query)'
code = code.replace(old_submit, new_submit)

old_return = '''        metadata = trafilatura.extract_metadata(raw)
        if metadata and metadata.title:
            title = metadata.title
        return _source(title or response.url, response.url, status=status, content=content, http_status=response.status_code)'''

new_return = '''        metadata = trafilatura.extract_metadata(raw)
        if metadata and metadata.title:
            title = metadata.title
            
        final_title = title or response.url
        if status == "success":
            # Cleanly format markdown block
            md_content = f"# {final_title}\\n**URL:** `{response.url}`\\n\\n" + content
            content = md_content
            
        return _source(final_title, response.url, status=status, content=content, http_status=response.status_code)'''

code = code.replace(old_return, new_return)

with open('tools/web_research.py', 'w', encoding='utf-8') as f:
    f.write(code)
print('Patch applied successfully')
