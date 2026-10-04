import os
os.environ.setdefault('DOTENV_FILE', r'C:\Users\Thomas Adrian\OneDrive\Desktop\agente_pessoal\.env')
from dotenv import load_dotenv
load_dotenv()

from providers.vision_agent import available_candidates
candidates = available_candidates()
print('Vision candidates after .env fix:')
for c in candidates:
    print(f'  {c["provider"]}/{c["model"]}')
print(f'Total: {len(candidates)}')