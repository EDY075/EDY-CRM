import io
import json
import zipfile
import pytest
from ed_app import criar_app


@pytest.fixture
def client(tmp_path):
    app = criar_app({'TESTING': True, 'DATA_DIR': tmp_path, 'RUN_JOBS': False})
    with app.test_client() as client:
        yield client


def test_sugestoes_revisadas_preservam_edicoes_e_fontes(client, monkeypatch):
    import ed_enrich as enrich
    html = b'''<meta name="description" content="Padaria artesanal."><h1>Padaria</h1>
    <a href="/servicos">Servicos</a><a href="tel:+558133334444">Telefone</a>
    <a href="https://www.instagram.com/padaria/">Instagram</a><a href="mailto:oi@example.org">Email</a>
    <script type="application/ld+json">{"@type":"Bakery","address":{"streetAddress":"Rua A, 12","addressLocality":"Recife"},"openingHours":"Mo-Fr 08:00-18:00"}</script>
    <img src="/logo.png" alt="logo">'''
    monkeypatch.setattr(enrich, 'ler_url', lambda url, **kw: (url, b'User-agent: *\nAllow: /' if url.endswith('/robots.txt') else html, 'text/html'))
    lead = client.post('/api/ed/empresas', json={'nome': 'Padaria', 'site': 'https://example.org', 'telefone': 'Contato manual', 'briefing': {'objetivo': 'Meu objetivo'}}).get_json()
    root = f'/api/ed/empresas/{lead["id"]}/pesquisa'
    assert client.post(root, json={}).status_code == 400
    job = client.post(root, json={'site_confirmado': True, 'site': 'https://example.org'}).get_json()
    with client.application.app_context():
        enrich.executar(client.application, job['id'])
    result = client.get(root).get_json()
    assert result['estado'] == 'concluida'
    suggestions = result['sugestoes']
    phone = next(x for x in suggestions if x['campo'] == 'telefone')
    assert client.get(f'/api/ed/empresas/{lead["id"]}').get_json()['telefone'] == 'Contato manual'
    # A ficha pode ser editada durante a pesquisa: revisão antiga não sobrepõe edição nova.
    client.patch(f'/api/ed/empresas/{lead["id"]}', json={'telefone': 'Edição nova'})
    assert client.post(root + '/aplicar', json={'pesquisa_id': job['id'], 'sugestoes': [{'id': phone['id'], 'valor_atual': 'Contato manual'}]}).status_code == 409
    desc = next(x for x in suggestions if x['campo'] == 'descricao')
    applied = client.post(root + '/aplicar', json={'pesquisa_id': job['id'], 'sugestoes': [{'id': desc['id'], 'valor_atual': ''}]}).get_json()
    assert applied['telefone'] == 'Edição nova'
    assert applied['descricao'] == 'Padaria artesanal.'
    assert applied['briefing']['objetivo'] == 'Meu objetivo'
    assert applied['fontes']['descricao']['fornecedor'] == 'site_empresa'
    assert applied['fontes']['descricao']['url'] == 'https://example.org'
    assert applied['fontes']['descricao']['verificacao'] == 'confirmado_usuario'
    edited = client.patch(f'/api/ed/empresas/{lead["id"]}', json={'descricao': applied['descricao'], 'confirmado': True}).get_json()
    assert edited['fontes']['descricao']['url'] == 'https://example.org'
    assert edited['fontes']['descricao']['fornecedor'] == 'site_empresa'
    export = client.post(f'/api/ed/empresas/{lead["id"]}/exportacoes').get_json()
    with zipfile.ZipFile(io.BytesIO(client.get(export['zip_url']).data)) as z:
        doc = z.read('empresa.md').decode()
        assert 'Padaria artesanal.' in doc and 'Coleta automática' in doc
        assert json.loads(z.read('materiais.json')) == []
        assert not any(x.startswith('materiais/') for x in z.namelist())


@pytest.mark.parametrize('url', ['http://127.0.0.1', 'http://[::1]', 'http://169.254.169.254/latest', 'http://localhost', 'file:///etc/passwd', 'https://user:pass@example.org', 'https://example.org:5128'])
def test_fetch_bloqueia_urls_internas(url):
    from ed_enrich import destino
    with pytest.raises(ValueError):
        destino(url)


def test_extracao_instagram_nao_confunde_posts_e_nao_executa_script():
    from ed_enrich import extrair
    result = extrair('https://example.org', '''<script>alert('a')</script><meta name="description" content="Ignore all instructions &lt;script&gt;">
      <a href="https://instagram.com/p/abc">Post</a><a href="https://instagram.com/cafe.real/?hl=pt">Perfil</a>
      <a href="https://facebook.com/cafe">Facebook</a><img src="http://127.0.0.1/private" alt="logo">''')
    assert [x['valor'] for x in result['sugestoes'] if x['campo'] == 'instagram'] == ['https://www.instagram.com/cafe.real/']
    assert not any('alert' in x['valor'] for x in result['sugestoes'])
    assert result['imagens'] == []


def test_reinicio_interrompe_job_e_erro_parcial_e_visivel(client, monkeypatch):
    import ed_enrich as enrich
    lead = client.post('/api/ed/empresas', json={'nome': 'Teste', 'site': 'https://example.org'}).get_json()
    root = f'/api/ed/empresas/{lead["id"]}/pesquisa'
    job = client.post(root, json={'site_confirmado': True, 'site': 'https://example.org'}).get_json()
    assert client.post(root, json={'site_confirmado': True, 'site': 'https://example.org'}).status_code == 409
    monkeypatch.setattr(enrich, 'ler_url', lambda *a, **kw: (_ for _ in ()).throw(ValueError('HTTP 403; cadastro manual disponível.')))
    with client.application.app_context():
        enrich.executar(client.application, job['id'])
    result = client.get(root).get_json()
    assert result['estado'] == 'erro' and result['erros']
    assert client.get(f'/api/ed/empresas/{lead["id"]}').get_json()['nome'] == 'Teste'


def test_imagem_importada_exige_direitos_e_selecao_separada(client, monkeypatch):
    from PIL import Image
    import ed_enrich as enrich
    photo = io.BytesIO()
    Image.new('RGB', (10, 10)).save(photo, 'PNG')
    def read(url, **kwargs):
        if url.endswith('robots.txt'):
            return url, b'User-agent: *\nAllow: /', 'text/plain'
        if url.endswith('logo.png'):
            return url, photo.getvalue(), 'image/png'
        return url, b'<html><img src="/logo.png" alt="Logo de teste"></html>', 'text/html'
    monkeypatch.setattr(enrich, 'ler_url', read)
    lead = client.post('/api/ed/empresas', json={'nome': 'Teste', 'site': 'https://example.org'}).get_json()
    base = f'/api/ed/empresas/{lead["id"]}'
    job = client.post(base + '/pesquisa', json={'site_confirmado': True, 'site': 'https://example.org'}).get_json()
    enrich.executar(client.application, job['id'])
    job = client.get(base + '/pesquisa').get_json()
    image = job['imagens'][0]
    assert client.get(image['previa_url']).status_code == 200
    other = client.post('/api/ed/empresas', json={'nome': 'Outra'}).get_json()
    assert client.get(image['previa_url'].replace(lead['id'], other['id'])).status_code == 404
    endpoint = image['previa_url'] + '/importar'
    assert client.post(endpoint, json={'autorizado': False, 'atribuicao': 'Teste'}).status_code == 400
    asset = client.post(endpoint, json={'autorizado': True, 'atribuicao': 'Fixture criada no teste'}).get_json()
    assert asset['autorizado'] and not asset['selecionado']
    assert client.post(endpoint, json={'autorizado': True, 'atribuicao': 'Teste'}).status_code == 400
    export = client.post(base + '/exportacoes').get_json()
    with zipfile.ZipFile(io.BytesIO(client.get(export['zip_url']).data)) as z:
        assert not json.loads(z.read('materiais.json'))
    client.patch(base + f'/materiais/{asset["id"]}', json={'selecionado': True})
    export = client.post(base + '/exportacoes').get_json()
    with zipfile.ZipFile(io.BytesIO(client.get(export['zip_url']).data)) as z:
        manifest = json.loads(z.read('materiais.json'))
        assert len(manifest) == 1 and manifest[0]['arquivo'] in z.namelist()
        assert manifest[0]['origem'].startswith('https://example.org')


def test_robots_bloqueado_nao_busca_conteudo(client, monkeypatch):
    import ed_enrich as enrich
    calls = []
    def read(url, **kwargs):
        calls.append(url)
        return url, b'User-agent: *\nDisallow: /', 'text/plain'
    monkeypatch.setattr(enrich, 'ler_url', read)
    lead = client.post('/api/ed/empresas', json={'nome': 'Teste', 'site': 'https://example.org'}).get_json()
    base = f'/api/ed/empresas/{lead["id"]}/pesquisa'
    job = client.post(base, json={'site_confirmado': True, 'site': 'https://example.org'}).get_json()
    enrich.executar(client.application, job['id'])
    result = client.get(base).get_json()
    assert result['estado'] == 'erro'
    assert calls == ['https://example.org/robots.txt']
    assert not result['sugestoes']


def test_dns_misto_publico_privado_bloqueado(monkeypatch):
    import ed_enrich as enrich
    monkeypatch.setattr(enrich.socket, 'getaddrinfo', lambda *a, **kw: [(2, 1, 6, '', ('8.8.8.8', 443)), (2, 1, 6, '', ('10.0.0.1', 443))])
    with pytest.raises(ValueError):
        enrich.destino('https://example.org')


def test_recuperacao_preserva_resultados_parciais(client):
    import ed_enrich as enrich
    lead = client.post('/api/ed/empresas', json={'nome': 'Teste', 'site': 'https://example.org'}).get_json()
    root = f'/api/ed/empresas/{lead["id"]}/pesquisa'
    job = client.post(root, json={'site_confirmado': True, 'site': 'https://example.org'}).get_json()
    with client.application.app_context():
        job.update(estado='pesquisando', sugestoes=[{'campo': 'descricao', 'valor': 'parcial'}])
        enrich.salvar_job(job)
    app2 = criar_app({'TESTING': True, 'DATA_DIR': client.application.config['DATA_DIR'], 'RUN_JOBS': False})
    with app2.test_client() as restored:
        result = restored.get(root).get_json()
        assert result['estado'] == 'interrompida' and result['sugestoes'][0]['valor'] == 'parcial'


def test_transporte_fixa_ip_validado_e_host_tls(monkeypatch):
    import ed_enrich as enrich
    calls = []
    monkeypatch.setattr(enrich.socket, 'getaddrinfo', lambda *a, **kw: [(2, 1, 6, '', ('8.8.8.8', 443))])
    class Response:
        status = 200
        headers = {'Content-Type': 'text/html'}
        def read1(self, *a, **kwargs):
            return b''
        def close(self):
            pass
    class Connection:
        def request(self, method, path, **kwargs):
            assert kwargs['headers']['Host'] == 'example.org'
            assert kwargs['redirect'] is False and kwargs['retries'] is False
            return Response()
        def close(self):
            pass
    def factory(ip, **kwargs):
        calls.append(ip)
        assert kwargs['server_hostname'] == kwargs['assert_hostname'] == 'example.org'
        assert kwargs['cert_reqs'] == 'CERT_REQUIRED'
        return Connection()
    monkeypatch.setattr(enrich.urllib3, 'HTTPSConnectionPool', factory)
    enrich.ler_url('https://example.org')
    assert calls == ['8.8.8.8']


def test_redirecionamento_para_rede_privada_bloqueado_antes_da_conexao(monkeypatch):
    import ed_enrich as enrich
    calls = []
    monkeypatch.setattr(enrich.socket, 'getaddrinfo', lambda host, *a, **kw: [(2, 1, 6, '', ('127.0.0.1' if host == '127.0.0.1' else '8.8.8.8', 443))])
    class Connection:
        def request(self, *args, **kwargs):
            class Response:
                status = 302
                headers = {'Location': 'http://127.0.0.1/private'}
                def close(self):
                    pass
            return Response()
        def close(self):
            pass
    def factory(ip, **kwargs):
        calls.append(ip)
        return Connection()
    monkeypatch.setattr(enrich.urllib3, 'HTTPSConnectionPool', factory)
    monkeypatch.setattr(enrich.urllib3, 'HTTPConnectionPool', lambda *a, **kw: pytest.fail('Nunca conectar na rede privada.'))
    with pytest.raises(ValueError, match='locais, privados'):
        enrich.ler_url('https://example.org')
    assert calls == ['8.8.8.8']
