import io
import json
import zipfile
from test_ed_enrich import client


def test_library_versions_scope_and_actual_export(client):
    a = client.post('/api/ed/empresas', json={'nome':'Empresa A','nicho':'Padarias'}).get_json()
    b = client.post('/api/ed/empresas', json={'nome':'Empresa B','nicho':'Saúde'}).get_json()
    item = client.post('/api/ed/biblioteca', json=dict(tipo='contexto',titulo='Decisão só A',conteudo='Usar cobre fosco.',escopo='lead',vinculo=a['id'],origem='Usuário')).get_json()
    assert item['versao'] == 1
    item['conteudo'] = 'Usar cobre e papel.'
    edited = client.put('/api/ed/biblioteca/'+item['id'],json=item)
    assert edited.status_code == 200
    assert edited.json['versao'] == 2
    assert client.put('/api/ed/biblioteca/'+item['id'],json=item).status_code == 409
    assert len(client.get('/api/ed/biblioteca/'+item['id']+'/versoes').json) == 2
    assert item['id'] not in [x['id'] for x in client.get('/api/ed/empresas/'+b['id']+'/contexto').json['items']]
    exported = client.post('/api/ed/empresas/'+a['id']+'/exportacoes').json
    with zipfile.ZipFile(io.BytesIO(client.get(exported['zip_url']).data)) as z:
        assert 'Usar cobre e papel.' in z.read('contexto.md').decode()
        assert json.loads(z.read('contexto-usado.json'))['items']
        assert 'contexto.md' in z.read('prompt-codex.md').decode()
        assert 'skills/' in '\n'.join(z.namelist())


def test_reference_import_is_data_not_executable(client):
    raw = b'<html><style>:root{--ink:#111111;--ink:#222222}</style><script>SECRET_INSTRUCTION()</script><h1>Marca alheia</h1></html>'
    r = client.post('/api/ed/biblioteca/importar',data={'arquivo':(io.BytesIO(raw),'ref.html'),'titulo':'Visual','escopo':'global','elementos':'composicao, movimento'})
    assert r.status_code == 201
    assert 'SECRET_INSTRUCTION' not in r.json['conteudo']
    assert 'Marca alheia' not in r.json['conteudo']
    assert r.json['original']['sha256']
    assert client.get(r.json['original']['url']).headers['Content-Disposition'].startswith('attachment')


def test_context_selection_rejects_other_lead(client):
    a = client.post('/api/ed/empresas',json={'nome':'A'}).json
    b = client.post('/api/ed/empresas',json={'nome':'B'}).json
    item = client.post('/api/ed/biblioteca',json=dict(tipo='skill',titulo='Privada',conteudo='Apenas A.',escopo='projeto',vinculo=a['id'])).json
    assert client.put('/api/ed/empresas/'+b['id']+'/contexto',json={'selecionados':[item['id']],'perfil':'artistico'}).status_code == 400


def test_essential_scope_precedence_survives_context_budget(client):
    company=client.post('/api/ed/empresas',json={'nome':'Real no teste'}).json
    for index in range(4):
        assert client.post('/api/ed/biblioteca',json=dict(titulo=f'Guia extenso {index}',conteudo='x'*8000,escopo='lead',vinculo=company['id'],prioridade=10)).status_code==201
    specific=client.post('/api/ed/biblioteca',json=dict(titulo='CTA aprovado',conteudo='Contrato específico',essenciais='Conversar, sem pedidos.',escopo='lead',vinculo=company['id'],prioridade=1)).json
    broader=client.post('/api/ed/biblioteca',json=dict(titulo='CTA aprovado',conteudo='Contrato genérico',essenciais='Regra ultrapassada',escopo='global')).json
    result=client.get('/api/ed/empresas/'+company['id']+'/contexto').json
    assert specific['id'] not in [x['id'] for x in result['items']]
    assert specific['id'] in [x['id'] for x in result['snapshot']]
    assert 'Conversar, sem pedidos.' in result['texto']
    assert 'Regra ultrapassada' not in result['texto']
    assert broader['id'] in [x['ignorado'] for x in result['conflitos']]
