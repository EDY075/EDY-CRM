import json
import pytest
from test_ed_enrich import client


@pytest.mark.parametrize('url,field', [
    ('http://google.com.br', 'fonte_busca_url'),
    ('https://www.google.com/search?q=salao', 'fonte_busca_url'),
    ('https://google.com.br/?q=salao', 'fonte_busca_url'),
    ('https://www.bing.com/search?q=salao', 'fonte_busca_url'),
    ('https://duckduckgo.com/?q=salao', 'fonte_busca_url'),
    ('https://www.google.com/maps/place/Salao/', 'fonte_mapa_url'),
    ('https://maps.app.goo.gl/Abc12', 'fonte_mapa_url'),
    ('https://www.openstreetmap.org/node/123', 'fonte_mapa_url'),
    ('https://sites.google.com/', 'fonte_busca_url'),
])
def test_links_de_fonte_nao_se_tornam_site_oficial(client, url, field):
    lead = client.post('/api/ed/empresas', json={'nome': 'Empresa', 'site': url, 'confirmado': True}).get_json()
    assert lead['site'] == ''
    assert lead[field] == url
    assert lead['associacao_site']['estado'] == 'pendente'
    assert lead['historico_site'][-1]['valor_anterior'] == url
    assert 'site' not in lead['fontes']


def test_links_de_fonte_nao_apagam_site_empresarial_existente(client):
    lead = client.post('/api/ed/empresas', json={'nome': 'Empresa', 'site': 'https://example.org/empresa'}).get_json()
    edited = client.patch('/api/ed/empresas/'+lead['id'], json={'site': 'https://google.com/search?q=empresa'}).get_json()
    assert edited['site'] == lead['site']
    assert edited['fonte_busca_url'].startswith('https://google.com/search')


@pytest.mark.parametrize('url', ['https://padariaartesanal.com.br/', 'https://sites.google.com/view/padaria-do-bairro/inicio', 'https://sites.google.com/site/padariadobairro/', 'https://example.org/?utm_source=google', 'https://google.com.example.org/', 'https://padaria.wixsite.com/pao'])
def test_sites_validos_permanecem_candidatos_mesmo_confirmacao_geral(client, url):
    lead = client.post('/api/ed/empresas', json={'nome': 'Empresa', 'site': url, 'confirmado': True}).get_json()
    assert lead['site'] == url
    assert lead['associacao_site']['estado'] == 'pendente'
    assert lead['fontes']['site']['verificacao'] == 'a_confirmar'


def test_legacy_generico_e_revisado_uma_vez_sem_alterar_outros_dados(client):
    import ed_store as store
    lead = client.post('/api/ed/empresas', json={'nome': 'Salão', 'telefone': 'Contato revisado', 'confirmado': True}).get_json()
    with client.application.app_context(), store.conectar() as con:
        row = con.execute('SELECT dados FROM ed_empresas WHERE id=?',(lead['id'],)).fetchone()
        data = json.loads(row['dados']); data['site'] = 'http://google.com.br'
        data['fontes']['site'] = store.fonte('site', data['site'], 'OpenStreetMap', 'https://openstreetmap.org/node/123', True)
        previous = data['fontes']['site'].copy()
        con.execute('UPDATE ed_empresas SET dados=? WHERE id=?',(json.dumps(data),lead['id']))
    with client.application.app_context():
        store.preparar();store.preparar()
    revised = client.get('/api/ed/empresas/'+lead['id']).get_json()
    assert revised['site'] == '' and revised['telefone'] == 'Contato revisado'
    assert revised['fontes']['telefone'] == lead['fontes']['telefone']
    assert len(revised['historico_site']) == 1
    assert revised['historico_site'][0]['fonte_anterior'] == previous
    assert revised['associacao_site']['estado'] == 'pendente'


def test_verificacao_propoe_evidencias_sem_confirmar_automaticamente(client, monkeypatch):
    import ed_enrich
    html = b'<h1>Padaria Bela</h1><p>Rua A, Recife</p><a href="tel:+558133334444">Contato</a>'
    monkeypatch.setattr(ed_enrich, 'ler_url', lambda url, **kw: (url, b'User-agent: *\nAllow: /' if url.endswith('robots.txt') else html, 'text/plain' if url.endswith('robots.txt') else 'text/html'))
    lead = client.post('/api/ed/empresas', json={'nome': 'Padaria Bela', 'cidade': 'Recife', 'telefone': '+55 81 3333-4444', 'site': 'https://example.org'}).get_json()
    base = '/api/ed/empresas/'+lead['id']
    response = client.post(base+'/site/verificar', json={'site': lead['site']})
    assert response.status_code == 200
    result = response.get_json()
    assert {e['campo'] for e in result['evidencias']} >= {'nome','localizacao','contato'}
    assert result['estado'] == 'pendente'
    assert client.get(base).get_json()['associacao_site']['estado'] == 'pendente'
    assert client.post(base+'/site/confirmar', json={'site': lead['site'], 'evidencia': ''}).status_code == 400
    confirmed = client.post(base+'/site/confirmar', json={'site': lead['site'], 'evidencia': 'Conferi nome, Recife e telefone na página.'}).get_json()
    assert confirmed['associacao_site']['estado'] == 'confirmado'
    assert confirmed['fontes']['site']['verificacao'] == 'confirmado_usuario'
    client.patch(base,json={'site':'https://example.org/outro'})
    assert client.post(base+'/site/confirmar', json={'site': lead['site'], 'evidencia': 'Conferência referente à revisão antiga.'}).status_code == 409


def test_candidato_sem_correspondencia_fica_ambiguo(client, monkeypatch):
    import ed_enrich
    monkeypatch.setattr(ed_enrich, 'ler_url', lambda url, **kw: (url, b'User-agent: *\nAllow: /' if url.endswith('robots.txt') else b'<h1>Outra empresa</h1>', 'text/plain' if url.endswith('robots.txt') else 'text/html'))
    lead=client.post('/api/ed/empresas',json={'nome':'Padaria Bela','site':'https://sites.google.com/view/padaria'}).get_json()
    result=client.post('/api/ed/empresas/'+lead['id']+'/site/verificar',json={'site':lead['site']}).get_json()
    assert result['ambiguo'] and result['evidencias']==[]
