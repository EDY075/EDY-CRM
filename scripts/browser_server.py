"""Servidor isolado para verificação no navegador. Dados ficam no projeto."""
import sys
import uuid
from pathlib import Path

root = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(root / 'backend'))
from ed_app import criar_app
from waitress import serve
import ed_enrich
import base64

app = criar_app({'DATA_DIR': root / '.cache' / f'browser-data-{uuid.uuid4().hex}', 'RUN_JOBS': False, 'RUN_SITE_JOBS': True})
# Somente neste servidor de testes: HTML e imagem fictícios, nenhuma rede externa.
def fixture_read(url, **kwargs):
    if url.startswith('https://blocked.example.org'):
        if url.endswith('/robots.txt'):
            return url, b'User-agent: *\nDisallow: /', 'text/plain'
        raise ValueError('Teste: página bloqueada não deve ser consultada.')
    if not url.startswith('https://example.org'):
        raise ValueError('Servidor de testes: rede externa desativada.')
    if url.endswith('/robots.txt'):
        return url, b'User-agent: *\nAllow: /', 'text/plain'
    if url.endswith('/logo.png'):
        return url, base64.b64decode('iVBORw0KGgoAAAANSUhEUgAAAAEAAAABCAQAAAC1HAwCAAAAC0lEQVR42mNk+A8AAQUBAScY42YAAAAASUVORK5CYII='), 'image/png'
    return url, b'''<html><meta name="description" content="Empresa ficticia para validar enriquecimento.">
      <a href="tel:+558100000000">Contato ficticio</a><a href="https://instagram.com/fixture.ed/">Instagram ficticio</a>
      <img src="/logo.png" alt="Logo ficticio de teste"></html>''', 'text/html'
ed_enrich.ler_url = fixture_read
serve(app, host='127.0.0.1', port=5129)
