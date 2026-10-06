"""Contratos locais; fixtures não comprovam operação Meta/Apify/Google."""
import json
from copy import deepcopy
from urllib.parse import parse_qs, urlsplit
import pytest
from PIL import Image
from test_ed_enrich import client
from test_ed_access import activate
import ed_connected_research as connected


def company(client, username='padaria.teste'):
    return client.post('/api/ed/empresas', json={'nome': 'Padaria & Teste', 'cidade': 'São Paulo', 'uf': 'SP',
                       'instagram': 'https://www.instagram.com/' + username + '/', 'telefone': 'Contato manual'}).json


def confirm(client, lead, username='padaria.teste'):
    r = client.post('/api/ed/empresas/' + lead['id'] + '/instagram/confirmar', json={
        'perfil': username, 'valor_anterior': lead['instagram'], 'evidencia': 'Fixture de teste: contato e endereço conferidos.'})
    assert r.status_code == 200, r.json


def root(lead):
    return '/api/ed/empresas/' + lead['id'] + '/pesquisa-conectada'


def test_diagnostic_read_only_maps_encoding_and_no_secrets(client, monkeypatch):
    import ed_secrets
    monkeypatch.setattr(ed_secrets, 'get', lambda _: 'secret-never-returned')
    lead = company(client)
    before = client.get('/api/ed/biblioteca').json
    d = client.get(root(lead)).json
    assert d['instagram']['estado'] == 'pendente' and not d['captura_disponivel']
    assert all(f['estado'] == 'configurado_nao_testado' for f in d['fontes'])
    assert all(f['operacoes_validadas'] == {} for f in d['fontes'])
    assert 'secret-never-returned' not in json.dumps(d)
    url = urlsplit(d['maps_url'])
    assert url.netloc == 'www.google.com'
    assert parse_qs(url.query) == {'api': ['1'], 'query': ['Padaria & Teste São Paulo SP']}
    assert client.get('/api/ed/empresas/' + lead['id']).json == lead
    assert client.get('/api/ed/biblioteca').json == before
    assert client.get(root({'id': 'missing'})).status_code == 404


def test_skill_install_idempotent_update_preserves_inactive_and_context(client, tmp_path, monkeypatch):
    path = '/api/ed/pesquisa-conectada/skill'
    assert client.post(path, json={'secret': 'forbidden'}).status_code == 400
    first = client.post(path, json={}).json
    assert client.post(path, json={}).json == first
    lead = company(client)
    resolved = client.get('/api/ed/empresas/' + lead['id'] + '/contexto').json
    assert next(s for s in resolved['snapshot'] if s['id'] == first['id'])['sha256'] == first['sha256']
    assert 'carrosséis' in resolved['texto'] and 'não concede' in resolved['texto']
    item = client.get('/api/ed/biblioteca/' + first['id']).json
    assert client.put('/api/ed/biblioteca/' + first['id'], json={**item, 'estado': 'inativo'}).status_code == 200
    updated_skill = tmp_path / 'SKILL.md'
    updated_skill.write_text(connected.SKILL.read_text(encoding='utf-8') + '\nRegra nova de teste.\n', encoding='utf-8')
    monkeypatch.setattr(connected, 'SKILL', updated_skill)
    updated = client.post(path, json={}).json
    assert updated['id'] == first['id'] and updated['versao'] == 3 and updated['estado'] == 'inativo'
    assert client.post(path, json={}).json == updated
    assert client.get(root(lead)).json['skill']['atual']
    assert len(client.get('/api/ed/biblioteca/' + first['id'] + '/versoes').json) == 3


def test_capture_requires_association_and_rejects_arbitrary_inputs(client):
    lead = company(client)
    path = root(lead) + '/capturar-instagram'
    assert client.post(path, json={'chave': 'one'}).status_code == 409
    for fields in ({'chave': 'one', 'url': 'https://elsewhere.test/'}, {'chave': ''}, {'chave': 7}):
        assert client.post(path, json=fields).status_code == 400
    assert client.get(root(lead)).json['capturas'] == []


def test_use_skill_keeps_explicit_selection_and_rejects_stale_changes(client):
    lead = company(client)
    context = '/api/ed/empresas/' + lead['id'] + '/contexto'
    item = client.get('/api/ed/biblioteca').json['items'][0]
    selection = {'selecionados': [item['id']], 'perfil': '', 'elementos': ['tipografia']}
    assert client.put(context, json=selection).status_code == 200
    state = client.get(root(lead)).json
    installed = client.post('/api/ed/pesquisa-conectada/skill', json={}).json
    assert not client.get(root(lead)).json['skill']['selecionada_empresa']
    path = root(lead) + '/skill'
    assert client.post(path, json={'selecao_sha256': state['selecao_sha256']}).status_code == 200
    resolved = client.get(context).json
    assert resolved['selecao'] == {**selection, 'selecionados': [item['id'], installed['id']]}
    assert any(s['id'] == installed['id'] and s['sha256'] == installed['sha256'] for s in resolved['snapshot'])
    assert client.post(path, json={'selecao_sha256': state['selecao_sha256']}).status_code == 409
    assert client.get(root(lead)).json['skill']['selecionada_empresa']


def test_context_change_during_install_is_not_overwritten(client, monkeypatch):
    import ed_store as store
    lead = company(client)
    state = client.get(root(lead)).json
    real_install = connected.install
    choice = {'selecionados': [], 'perfil': 'comercio', 'elementos': ['copy']}
    def concurrent_install():
        item = real_install()
        with store.conectar() as con:
            con.execute('INSERT INTO ed_config VALUES (?,?)', ('biblioteca:' + lead['id'], json.dumps(choice)))
        return item
    monkeypatch.setattr(connected, 'install', concurrent_install)
    assert client.post(root(lead) + '/skill', json={'selecao_sha256': state['selecao_sha256']}).status_code == 409
    assert client.get('/api/ed/empresas/' + lead['id'] + '/contexto').json['selecao'] == choice


def mock_browser(monkeypatch, tmp_path, username='padaria.teste'):
    import ed_visual_research as visual
    import ed_visual_browser as browser
    monkeypatch.setattr(visual, 'destino', lambda _: None)
    monkeypatch.setattr(visual, 'robots_checker', lambda d: (d.update(robots={'regra': 'Allow: /'}) or (lambda _: None)))
    for name in ('desktop.jpg', 'mobile.jpg'):
        Image.new('RGB', (120, 80), '#bb8844').save(tmp_path / name)
    record = dict(titulo='Padaria (@' + username + ') • Instagram', titulos=[username],
                  texto=username + ' Informações fictícias usadas somente no teste unitário. ' * 3,
                  imagens=[dict(largura=120, altura=80)], observacoes=[])
    data = dict(viewports=[deepcopy(record), deepcopy(record)], observacoes=[])
    monkeypatch.setattr(browser, 'render', lambda *args: (data, tmp_path))
    return data


def test_capture_reuses_queue_is_idempotent_and_preserves_manual_edits(client, monkeypatch, tmp_path):
    lead = company(client)
    confirm(client, lead)
    mock_browser(monkeypatch, tmp_path)
    before = client.get('/api/ed/empresas/' + lead['id']).json
    path = root(lead) + '/capturar-instagram'
    job = client.post(path, json={'chave': 'same'}).json
    assert job['estado'] == 'concluida', job
    assert job['parametros']['associacao']['estado'] == 'confirmado'
    assert job['parametros']['perfil_instagram'] == 'padaria.teste'
    assert client.post(path, json={'chave': 'same'}).json['id'] == job['id']
    assert len(client.get(root(lead)).json['capturas']) == 1
    refs = job['resultado']['capturas']
    assert {c['viewport'] for c in refs} == {'desktop', 'mobile'}
    for c in refs:
        assert client.get(c['url']).status_code == 200
    item = client.get('/api/ed/biblioteca/' + job['resultado']['biblioteca_id']).json
    assert item['estado'] == 'inativo' and item['vinculo'] == lead['id']
    assert client.get('/api/ed/empresas/' + lead['id']).json == before
    from ed_app import criar_app
    restarted = criar_app({'TESTING': True, 'DATA_DIR': client.application.config['DATA_DIR'], 'RUN_JOBS': False}).test_client()
    assert restarted.post(path, json={'chave': 'same'}).json['id'] == job['id']
    other = company(client, 'outra.teste')
    confirm(client, other, 'outra.teste')
    assert client.get(root(other)).json['capturas'] == []
    confirm(client, before, 'novo.perfil')
    assert client.post(path, json={'chave': 'same'}).status_code == 409
    assert client.get('/api/ed/operacoes/' + job['id']).json['resultado'] == job['resultado']


@pytest.mark.parametrize('failure', ['login', 'empty', 'no_images', 'changed', 'robots'])
def test_blocked_incomplete_or_changed_profile_is_not_success(client, monkeypatch, tmp_path, failure):
    import ed_visual_research as visual
    lead = company(client)
    confirm(client, lead)
    observed = mock_browser(monkeypatch, tmp_path)
    if failure == 'login':
        for v in observed['viewports']:
            v['titulos'] = ['Log in']  # Mesmo com @usuário no title, não vale como perfil.
    elif failure == 'empty':
        observed['viewports'][0]['texto'] = ''
    elif failure == 'no_images':
        observed['viewports'][1]['imagens'] = []
    elif failure == 'changed':
        import ed_visual_browser
        def change(*args):
            import ed_store as store
            with store.conectar() as con:
                updated = json.loads(con.execute('SELECT dados FROM ed_empresas WHERE id=?', (lead['id'],)).fetchone()['dados'])
                updated['instagram'] = 'https://www.instagram.com/novo/'
                con.execute('UPDATE ed_empresas SET dados=? WHERE id=?', (json.dumps(updated), lead['id']))
            return observed, tmp_path
        monkeypatch.setattr(ed_visual_browser, 'render', change)
    else:
        def robots(d):
            def reject(_):
                raise ValueError('robots.txt: User-agent EdCRM; Disallow: /; leitura proibida.')
            return reject
        monkeypatch.setattr(visual, 'robots_checker', robots)
    before = client.get('/api/ed/biblioteca').json
    job = client.post(root(lead) + '/capturar-instagram', json={'chave': failure}).json
    assert job['estado'] == 'erro' and not job.get('resultado'), job
    assert client.get('/api/ed/biblioteca').json == before
    assert client.get('/api/ed/empresas/' + lead['id']).json['telefone'] == 'Contato manual'
    if failure == 'robots':
        assert 'Disallow: /' in job['mensagem']
    if failure == 'changed':
        assert 'associação mudou' in job['mensagem']


def test_new_routes_respect_workspace_roles_and_csrf(client):
    lead = company(client)
    headers = activate(client)
    assert client.post('/api/ed/pesquisa-conectada/skill', json={}).status_code == 403
    workspace = client.post('/api/ed/acesso/workspaces', headers=headers, json={'nome': 'Workspace teste'}).json
    client.post('/api/ed/acesso/workspace', headers=headers, json={'id': workspace['id']})
    assert client.get(root(lead)).status_code == 404
    assert client.post(root(lead) + '/capturar-instagram', headers=headers, json={'chave': 'no-access'}).status_code == 404
    client.post('/api/ed/acesso/workspace', headers=headers, json={'id': 'principal'})
    assert client.get(root(lead)).status_code == 200
    client.post('/api/ed/acesso/usuarios', headers=headers, json={'nome': 'leitor', 'senha': 'senha leitor segura', 'papel': 'leitura'})
    client.post('/api/ed/acesso/sair', headers=headers)
    client.post('/api/ed/acesso/login', json={'nome': 'leitor', 'senha': 'senha leitor segura'})
    reader_headers = {'X-EDY-CSRF': client.get('/api/ed/acesso/sessao').json['csrf']}
    assert client.get(root(lead)).status_code == 200
    assert client.post('/api/ed/pesquisa-conectada/skill', headers=reader_headers, json={}).status_code == 403


def test_cancelled_capture_has_no_late_reference_write(client, monkeypatch, tmp_path):
    import ed_visual_browser as browser
    import ed_services
    lead = company(client)
    confirm(client, lead)
    observed = mock_browser(monkeypatch, tmp_path)
    before = client.get('/api/ed/biblioteca').json
    def cancel(job, *args):
        j = ed_services.ler_job(job['id'])
        j['estado'] = 'cancelada'
        ed_services.save(j)
        return observed, tmp_path
    monkeypatch.setattr(browser, 'render', cancel)
    result = client.post(root(lead) + '/capturar-instagram', json={'chave': 'cancel'}).json
    assert result['estado'] == 'cancelada' and not result.get('resultado')
    assert client.get('/api/ed/biblioteca').json == before
