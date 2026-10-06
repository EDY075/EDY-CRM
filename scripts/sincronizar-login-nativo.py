"""Sincronização explícita autorizada: cache nativo para cache nativo, nunca API."""
import json
import os
import sys
from pathlib import Path

root = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(root / 'backend'))
from ed_app import criar_app
from ed_runtime import private_native_cache
from ed_secrets import crypt
from ed_codex_oauth import native_identity

if '--confirmar-conta-atual' not in sys.argv:
    raise SystemExit('Exige escolha explícita: --confirmar-conta-atual. Não troca automaticamente.')
source = Path(os.environ.get('CODEX_HOME') or Path.home() / '.codex') / 'auth.json'
target = root / 'data/runtime-codex/auth.json'
value = json.loads(source.read_text(encoding='utf-8'))
if value.get('OPENAI_API_KEY') or not value.get('tokens', {}).get('access_token'):
    raise SystemExit('Cache não contém login nativo ChatGPT. Nenhum fallback de cobrança.')
with criar_app({'RUN_JOBS':False,'RECOVER_JOBS':False}).app_context():
    private_native_cache(target.parent)
    before = native_identity(target)
    backup = target.parent / ('auth-anterior-' + before['identificador'] + '.dpapi')
    if target.exists() and not backup.exists():
        backup.write_bytes(crypt(target.read_bytes()))
    temporary = target.with_suffix('.tmp')
    temporary.write_bytes(source.read_bytes())
    temporary.replace(target)
    after = native_identity(target)
print(json.dumps({'acao': 'conta nativa atual selecionada explicitamente',
                  'conta_anterior_hash': before['identificador'],
                  'conta_atual_hash': after['identificador'],
                  'backup': backup.relative_to(root).as_posix(),
                  'acesso': 'ainda não validado por inferência'}, ensure_ascii=False))
