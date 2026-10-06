import io
import json
import zipfile
import hashlib
import pytest
from ed_app import criar_app


@pytest.fixture
def client(tmp_path):
    with criar_app({'TESTING': True, 'DATA_DIR': tmp_path, 'RUN_JOBS': False}).test_client() as c:
        yield c


def lead(c):
    return c.post('/api/ed/empresas', json={'nome': 'Empresa teste', 'descricao': 'Descrição revisada',
        'confirmado': True, 'site': 'https://example.org', 'telefone': 'Contato manual'}).get_json()['id']


def test_preparation_revision_and_portable_package(client):
    ident = lead(client)
    endpoint = f'/api/ed/empresas/{ident}/preparacao'
    p = client.get(endpoint).get_json()
    assert p['revisao'] == 0
    p['objetivo'] = 'Decisão manual'
    p['referencias'] = [{'url': 'https://example.org/design', 'material_id': '', 'observacao': 'Inspiração'},
                       {'url': 'https://example.org/image.png', 'material_id': '', 'observacao': 'Imagem somente por link'}]
    assert client.put(endpoint, json=p).status_code == 200
    assert client.put(endpoint, json=p).status_code == 409
    assert client.get(endpoint).get_json()['objetivo'] == 'Decisão manual'
    exported = client.post(f'/api/ed/empresas/{ident}/exportacoes').get_json()
    with zipfile.ZipFile(io.BytesIO(client.get(exported['zip_url']).data)) as z:
        assert {'empresa.md', 'briefing.md', 'DESIGN.md', 'referencias.md', 'materiais.json', 'prompt-codex.md', 'LEIA-ME.md'} <= set(z.namelist())
        assert 'Decisão manual' in z.read('briefing.md').decode()
        assert 'GPT-6.1 Sol' in z.read('prompt-codex.md').decode()
        assert 'raciocínio Alto' in z.read('prompt-codex.md').decode()
        assert not any('/' in n and not n.startswith(('materiais/','skills/','.agents/skills/crm-sites-adaptativo/')) for n in z.namelist())
        assert '.agents/skills/crm-sites-adaptativo/SKILL.md' in z.namelist()
        assert all(not n.startswith(('/', '\\')) and '..' not in n.split('/') and ':' not in n for n in z.namelist())
        assert all(m['disponibilidade'] == 'somente_link' and not m.get('arquivo') for m in json.loads(z.read('materiais.json')))


def test_connectors_no_secret_leak_and_failure(client, monkeypatch):
    import ed_connectors as providers
    monkeypatch.setenv('ED_CRM_OPENAI_KEY', 'secret-not-for-client')
    def unavailable(*args, **kwargs):
        raise ValueError('Fornecedor indisponível (HTTP 503).')
    monkeypatch.setattr(providers, 'request_json', unavailable)
    before = client.get('/api/ed/integracoes/status').get_json()['conectores']['openai']
    assert before['estado'] == 'configurado_nao_validado'
    result = client.post('/api/ed/integracoes/openai/testar', json={})
    assert result.status_code == 200
    assert result.get_json()['estado'] == 'erro'
    assert 'secret-not-for-client' not in client.get('/api/ed/integracoes/status').data.decode()
    ident = lead(client)
    assert client.get(f'/api/ed/empresas/{ident}').get_json()['telefone'] == 'Contato manual'


def test_cancel_research_preserves_partial_and_manual(client):
    ident = lead(client)
    job = client.post(f'/api/ed/empresas/{ident}/pesquisa', json={'site_confirmado': True, 'site': 'https://example.org'}).get_json()
    result = client.post(f'/api/ed/empresas/{ident}/pesquisas/{job["id"]}/cancelar', json={})
    assert result.status_code == 200
    assert result.get_json()['estado'] == 'cancelada'
    assert client.get(f'/api/ed/empresas/{ident}').get_json()['telefone'] == 'Contato manual'


def test_invalid_preparation_material_and_unreviewed_fact(client):
    ident = lead(client)
    endpoint = f'/api/ed/empresas/{ident}/preparacao'
    p = client.get(endpoint).get_json()
    p['imagens'] = [{'material_id': 'other-company', 'funcao': 'abertura'}]
    assert client.put(endpoint, json=p).status_code == 400
    client.patch(f'/api/ed/empresas/{ident}', json={'servicos': 'Não verificado', 'confirmado': False})
    export = client.post(f'/api/ed/empresas/{ident}/exportacoes').get_json()
    with zipfile.ZipFile(io.BytesIO(client.get(export['zip_url']).data)) as z:
        text = z.read('empresa.md').decode()
        assert 'Não verificado' not in text.split('## Fontes')[0]
        assert json.loads(z.read('materiais.json')) == []


def test_ai_is_a_proposal_and_cancelled_result_never_overwrites(client, monkeypatch):
    import ed_services as services
    monkeypatch.setenv('ED_CRM_OPENAI_KEY', 'test-secret')
    ident = lead(client)
    p = client.get(f'/api/ed/empresas/{ident}/preparacao').get_json()
    p['prospeccao'] = 'Texto manual protegido'
    p = client.put(f'/api/ed/empresas/{ident}/preparacao', json=p).get_json()
    monkeypatch.setattr(services.ADAPTERS['openai'], 'propose', lambda *a: ({'prospeccao': 'Proposta externa', 'secoes': []}, {'total_tokens': 20}))
    response = client.post(f'/api/ed/empresas/{ident}/preparacao/ia', json={'revisao': p['revisao']})
    assert response.status_code == 201
    assert response.get_json()['proposta']['prospeccao'] == 'Proposta externa'
    assert client.get(f'/api/ed/empresas/{ident}/preparacao').get_json()['prospeccao'] == 'Texto manual protegido'
    with client.application.app_context():
        job = response.get_json()
        job['estado'] = 'pesquisando'
        services.save(job)
    assert client.post(f'/api/ed/operacoes/{job["id"]}/cancelar', json={}).get_json()['estado'] == 'cancelada'
    with client.application.app_context():
        job.update(estado='concluida', mensagem='Resposta atrasada')
        assert not services.save(job)
    assert client.get(f'/api/ed/operacoes/{job["id"]}').get_json()['estado'] == 'cancelada'


def test_research_cancel_blocks_late_write(client):
    import ed_enrich as enrich
    ident = lead(client)
    job = client.post(f'/api/ed/empresas/{ident}/pesquisa', json={'site_confirmado': True, 'site': 'https://example.org'}).get_json()
    client.post(f'/api/ed/empresas/{ident}/pesquisas/{job["id"]}/cancelar', json={})
    with client.application.app_context():
        job.update(estado='concluida', mensagem='Resposta atrasada')
        assert not enrich.salvar_job(job)
    assert client.get(f'/api/ed/empresas/{ident}/pesquisa').get_json()['estado'] == 'cancelada'


def test_dpapi_secret_is_not_plaintext_and_settings_reset_validation(client, tmp_path, monkeypatch):
    import os
    if os.name != 'nt':
        pytest.skip('DPAPI é um recurso Windows; outros sistemas usam ambiente do processo.')
    import ed_secrets
    monkeypatch.delenv('ED_CRM_FIRECRAWL_KEY', raising=False)
    secret = 'local-secret-for-encryption-test'
    result = client.put('/api/ed/integracoes/firecrawl', json={'credencial': secret})
    assert result.status_code == 200
    assert result.get_json()['estado'] == 'configurado_nao_validado'
    assert secret.encode() not in (tmp_path / 'credenciais.dpapi').read_bytes()
    assert secret not in client.get('/api/ed/integracoes/status').data.decode()
    with client.application.app_context():
        assert ed_secrets.get('firecrawl') == secret


def test_firecrawl_failure_keeps_manual_and_offers_local_fallback(client, monkeypatch):
    import ed_enrich as enrich
    import ed_connectors as connectors
    monkeypatch.setenv('ED_CRM_FIRECRAWL_KEY', 'fake')
    monkeypatch.setattr(enrich, 'ler_url', lambda url, **kw: (url, b'User-agent: *\nAllow: /', 'text/plain'))
    def failure(url):
        raise ValueError('Fornecedor indisponível (HTTP 402).')
    monkeypatch.setattr(connectors.ADAPTERS['firecrawl'], 'scrape', failure)
    ident = lead(client)
    job = client.post(f'/api/ed/empresas/{ident}/pesquisa', json={'site_confirmado': True, 'site': 'https://example.org', 'fornecedor': 'firecrawl'}).get_json()
    enrich.executar(client.application, job['id'])
    latest = client.get(f'/api/ed/empresas/{ident}/pesquisa').get_json()
    assert latest['estado'] == 'erro'
    assert '402' in latest['erros'][0]['mensagem']
    assert client.get(f'/api/ed/empresas/{ident}').get_json()['telefone'] == 'Contato manual'
    assert client.post(f'/api/ed/empresas/{ident}/pesquisa', json={'site_confirmado': True, 'site': 'https://example.org'}).status_code == 201


def test_niche_templates_are_design_suggestions_not_business_facts(client):
    plans = []
    for niche in ('Padarias', 'Academias', 'Veterinária', 'Salões de beleza'):
        ident = client.post('/api/ed/empresas', json={'nome': 'Empresa fictícia', 'nicho': niche}).get_json()['id']
        plan = client.get(f'/api/ed/empresas/{ident}/preparacao').get_json()
        plans.append(plan['design']['cursor'])
        assert 'confirmar' in plan['oferta'].lower()
        assert all(not s['revisado'] for s in plan['secoes'])
        assert not client.get(f'/api/ed/empresas/{ident}').get_json()['servicos']
    assert len(set(plans)) == 4


def test_selected_image_export_has_identity_framing_and_hash(client):
    from PIL import Image
    ident = lead(client)
    image = io.BytesIO()
    Image.new('RGB', (24, 30), '#445566').save(image, 'PNG')
    image.seek(0)
    m = client.post(f'/api/ed/empresas/{ident}/materiais', data={'arquivo': (image, 'C:\\temporary\\fixture.png'),
        'origem': 'Fixture própria', 'atribuicao': 'Teste', 'autorizado': 'true'}).get_json()
    # Simular metadado antigo com caminho Windows, preservando o arquivo local real.
    import ed_store as store
    with client.application.app_context(), store.conectar() as con:
        row = con.execute('SELECT dados FROM ed_materiais WHERE id=?', (m['id'],)).fetchone()
        saved = json.loads(row['dados'])
        saved['nome_original'] = 'C:\\temporary\\fixture.png'
        con.execute('UPDATE ed_materiais SET dados=? WHERE id=?', (json.dumps(saved), m['id']))
    assert client.patch(f'/api/ed/empresas/{ident}/materiais/{m["id"]}', json={'selecionado': True}).status_code == 200
    endpoint = f'/api/ed/empresas/{ident}/preparacao'
    p = client.get(endpoint).get_json()
    p['imagens'] = [{'material_id': m['id'], 'funcao': 'abertura', 'natureza': 'ilustrativa', 'pessoa': '',
        'desktop': {'x': 25, 'y': 50, 'recorte': 'cover', 'enquadramento': 'Espaço para texto'},
        'mobile': {'x': 75, 'y': 50, 'recorte': 'contain', 'enquadramento': 'Imagem inteira'}}]
    p['referencias'] = [{'url': 'https://example.org', 'material_id': m['id'], 'observacao': 'Referência sem copiar'}]
    assert client.put(endpoint, json=p).status_code == 200
    exported = client.post(f'/api/ed/empresas/{ident}/exportacoes').get_json()
    with zipfile.ZipFile(io.BytesIO(client.get(exported['zip_url']).data)) as z:
        manifest = json.loads(z.read('materiais.json'))
        asset = next(x for x in manifest if x.get('arquivo'))
        assert asset['nome_original'] == 'fixture.png'
        assert asset['direcao']['natureza'] == 'ilustrativa'
        assert asset['direcao']['mobile']['x'] == 75
        assert asset['sha256'] == hashlib.sha256(z.read(asset['arquivo'])).hexdigest()
        assert '25% 50%' in z.read('DESIGN.md').decode()
        assert 'C:\\temporary' not in z.read('materiais.json').decode()


def test_osm_connection_test_does_not_insert_leads_and_shares_rate_limit(client, monkeypatch):
    import ed_search
    client.put('/api/ed/config', json={'osm_habilitado': True})
    monkeypatch.setattr(ed_search, 'consultar', lambda job: ([{'id': 123}], False))
    result = client.post('/api/ed/integracoes/osm/testar', json={})
    assert result.status_code == 200
    assert result.get_json()['estado'] == 'concluida'
    assert client.get('/api/ed/empresas').get_json() == []
    assert client.post('/api/ed/integracoes/osm/testar', json={}).status_code == 400
    assert client.post('/api/ed/campanhas', json={'nicho': 'Salões de beleza', 'cidade': 'Recife', 'uf': 'PE', 'limite': 1}).status_code == 400
