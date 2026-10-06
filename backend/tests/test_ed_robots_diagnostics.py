import pytest
from test_ed_enrich import client
import ed_enrich as enrich


def run(client, monkeypatch, robots, page=b'<meta name="description" content="Texto publicado">', site='https://example.org'):
    calls = []
    def read(url, **kwargs):
        calls.append(url)
        value = robots if url.endswith('/robots.txt') else page
        if isinstance(value, Exception):
            raise value
        return url, value, 'text/plain' if url.endswith('/robots.txt') else 'text/html'
    monkeypatch.setattr(enrich, 'ler_url', read)
    lead = client.post('/api/ed/empresas', json={'nome': 'Teste', 'site': site, 'telefone': 'Edição manual'}).get_json()
    base = f'/api/ed/empresas/{lead["id"]}'
    before = client.get(base).get_json()
    job = client.post(base+'/pesquisa', json={'site': site, 'site_confirmado': True}).get_json()
    enrich.executar(client.application, job['id'])
    after = client.get(base).get_json()
    assert after['telefone'] == before['telefone']
    assert after['materiais'] == before['materiais']
    return client.get(base+'/pesquisa').get_json(), calls


def test_query_vazia_na_regra_nao_bloqueia_inicio(client, monkeypatch):
    job, calls = run(client, monkeypatch, b'User-agent: *\nDisallow: /?\nDisallow: /search\nAllow: /search/about')
    assert 'https://example.org' in calls
    assert job['estado'] == 'concluida'
    assert job['robots']['avaliacoes'][0]['permitido'] is True


def test_bloqueio_explica_regra_sem_alegar_javascript(client, monkeypatch):
    job, calls = run(client, monkeypatch, b'User-agent: *\nDisallow: /')
    assert calls == ['https://example.org/robots.txt']
    assert job['erros'][0]['tipo'] == 'robots_regra'
    assert job['erros'][0]['regra'] == 'Disallow: /'
    assert job['robots']['user_agent'] == enrich.AGENT
    assert 'Nenhuma página lida' in job['mensagem']
    assert not any('JavaScript' in p for p in job['pendencias'])


@pytest.mark.parametrize('error,kind', [(ValueError('HTTP 503; indisponível'), 'http'), (ValueError('Falha de conexão, timeout ou certificado TLS'), 'rede')])
def test_falha_de_robots_nao_e_regra(client, monkeypatch, error, kind):
    job, calls = run(client, monkeypatch, error)
    assert job['estado'] == 'erro'
    assert job['erros'][0]['tipo'] == kind
    assert job['erros'][0]['etapa'] == 'robots'
    assert calls == ['https://example.org/robots.txt']


def test_html_em_robots_e_diagnostico_de_interpretacao(client, monkeypatch):
    job, calls = run(client, monkeypatch, b'<html>Captcha</html>')
    assert job['estado'] == 'erro'
    assert job['erros'][0]['tipo'] == 'interpretacao'
    assert len(calls) == 1


def test_html_vazio_nao_e_pesquisa_concluida(client, monkeypatch):
    job, _ = run(client, monkeypatch, b'User-agent: *\nAllow: /', page=b'<html><div id="root"></div><script src="/app.js"></script></html>')
    assert job['estado'] == 'sem_resultados'
    assert job['paginas'][0]['javascript_possivel'] is True
    assert 'possivelmente' in job['mensagem']


@pytest.mark.parametrize('rules,url,allowed,rule', [
    ('Disallow: /search\nAllow: /search/about', '/search/about', True, 'Allow: /search/about'),
    ('Disallow: /search\nAllow: /search/about', '/search?q=salon', False, 'Disallow: /search'),
    ('Disallow: /?\nAllow: /?hl=', '/?hl=pt', True, 'Allow: /?hl='),
    ('Disallow: /?\nAllow: /?hl=', '/', True, '(nenhuma regra correspondente)'),
    ('Disallow: /\nAllow: /', '/', True, 'Allow: /'),
    ('Disallow: /*.pdf$', '/catalogo.pdf', False, 'Disallow: /*.pdf$'),
    ('Disallow: /*.pdf$', '/catalogo.pdfx', True, '(nenhuma regra correspondente)'),
    ('Disallow: /café', '/caf%C3%A9', False, 'Disallow: /caf%C3%A9'),
    ('Disallow: /private', '/Private', True, '(nenhuma regra correspondente)'),
])
def test_precedencia_query_wildcards_encoding(rules, url, allowed, rule):
    from ed_robots import Policy
    result = Policy('User-agent: *\n'+rules).check('https://example.org'+url, enrich.AGENT)
    assert result['permitido'] is allowed
    assert result['regra'] == rule


def test_grupos_especificos_mesclados_e_delay():
    from ed_robots import Policy
    p = Policy('User-agent: *\nDisallow: /\n\nUser-agent: EdCRM\nDisallow: /a\nCrawl-delay: 3\n\nUser-agent: EdCRM\nDisallow: /b')
    assert p.check('https://example.org/', enrich.AGENT)['permitido']
    assert not p.check('https://example.org/a', enrich.AGENT)['permitido']
    assert not p.check('https://example.org/b', enrich.AGENT)['permitido']
    assert p.delay(enrich.AGENT) == 3


def test_http_404_robots_permite_leitura(client, monkeypatch):
    job, _ = run(client, monkeypatch, ValueError('HTTP 404; arquivo ausente'))
    assert job['estado'] == 'concluida'
    assert job['robots']['documentos'][0]['http_status'] == 404


def test_diagnostico_nao_reconfirma_site_ou_muda_execucao(client, monkeypatch):
    import json
    import ed_store as store
    job, _ = run(client, monkeypatch, b'User-agent: *\nDisallow: /')
    base = f'/api/ed/empresas/{job["empresa_id"]}'
    before = client.get(base).get_json()
    calls = []
    def read(url, **kwargs):
        calls.append(url)
        return url, b'User-agent: *\nDisallow: /?\nDisallow: /search', 'text/plain'
    monkeypatch.setattr(enrich, 'ler_url', read)
    result = client.post(base+f'/pesquisas/{job["id"]}/diagnostico').get_json()
    assert result['estado'] == 'permitida'
    assert calls == ['https://example.org/robots.txt']
    assert client.get(base).get_json() == before
    assert client.get(base+'/pesquisa').get_json()['diagnostico_atual'] == result
    with client.application.app_context(), store.conectar() as con:
        saved = json.loads(con.execute('SELECT dados FROM ed_pesquisas WHERE id=?', (job['id'],)).fetchone()['dados'])
    assert saved == job
    other = client.post('/api/ed/empresas', json={'nome': 'Outra'}).get_json()
    assert client.post(f'/api/ed/empresas/{other["id"]}/pesquisas/{job["id"]}/diagnostico').status_code == 404


def test_firecrawl_alternativo_registra_origem_sem_sobrepor(client, monkeypatch):
    import ed_secrets
    from ed_connectors import ADAPTERS
    monkeypatch.setattr(ed_secrets, 'get', lambda provider: 'fixture-only')
    monkeypatch.setattr(enrich, 'ler_url', lambda url, **kw: (url, b'User-agent: *\nAllow: /', 'text/plain'))
    monkeypatch.setattr(ADAPTERS['firecrawl'], 'scrape', lambda url: (url, b'<meta name="description" content="Conteudo renderizado">', 'text/html'))
    lead = client.post('/api/ed/empresas', json={'nome': 'Teste', 'site': 'https://example.org', 'descricao': 'Minha edição'}).get_json()
    base = f'/api/ed/empresas/{lead["id"]}'
    job = client.post(base+'/pesquisa', json={'site': lead['site'], 'site_confirmado': True, 'fornecedor': 'firecrawl'}).get_json()
    enrich.executar(client.application, job['id'])
    result = client.get(base+'/pesquisa').get_json()
    assert result['estado'] == 'concluida'
    assert result['paginas'][0]['fornecedor'] == 'firecrawl'
    assert client.get(base).get_json()['descricao'] == 'Minha edição'
    suggestion = result['sugestoes'][0]
    applied = client.post(base+'/pesquisa/aplicar', json={'pesquisa_id': job['id'], 'sugestoes': [{'id': suggestion['id'], 'valor_atual': 'Minha edição'}]}).get_json()
    assert applied['fontes']['descricao']['coletor'] == 'firecrawl'


def test_firecrawl_nao_contorna_regra_robots(client, monkeypatch):
    import ed_secrets
    from ed_connectors import ADAPTERS
    monkeypatch.setattr(ed_secrets, 'get', lambda provider: 'fixture-only')
    monkeypatch.setattr(enrich, 'ler_url', lambda url, **kw: (url, b'User-agent: *\nDisallow: /', 'text/plain'))
    monkeypatch.setattr(ADAPTERS['firecrawl'], 'scrape', lambda url: pytest.fail('Não contornar regra com outra fonte'))
    lead = client.post('/api/ed/empresas', json={'nome': 'Teste', 'site': 'https://example.org'}).get_json()
    base = f'/api/ed/empresas/{lead["id"]}/pesquisa'
    job = client.post(base, json={'site': lead['site'], 'site_confirmado': True, 'fornecedor': 'firecrawl'}).get_json()
    enrich.executar(client.application, job['id'])
    result = client.get(base).get_json()
    assert result['estado'] == 'erro'
    assert result['erros'][0]['tipo'] == 'robots_regra'


def test_redirect_local_confere_politica_antes_de_requisitar_destino(monkeypatch):
    from ed_robots import Policy
    monkeypatch.setattr(enrich.socket, 'getaddrinfo', lambda *a, **kw: [(2, 1, 6, '', ('8.8.8.8', 443))])
    calls = []
    class Connection:
        def request(self, method, path, **kwargs):
            calls.append(path)
            class Response:
                status = 302
                headers = {'Location': '/private'}
                def close(self):
                    pass
            return Response()
        def close(self):
            pass
    monkeypatch.setattr(enrich.urllib3, 'HTTPSConnectionPool', lambda *a, **kw: Connection())
    def check(url):
        if not Policy('User-agent: *\nDisallow: /private').check(url, enrich.AGENT)['permitido']:
            raise enrich.ReadError('Destino bloqueado', 'robots_regra')
    with pytest.raises(enrich.ReadError, match='Destino bloqueado'):
        enrich.ler_url('https://example.org/', antes_de_ler=check)
    assert calls == ['/']
