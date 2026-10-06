"""Contrato do fluxo Ed CRM. Rede externa é substituída apenas nos testes."""
import io
import json
import zipfile

import pytest
from PIL import Image

from ed_app import criar_app


@pytest.fixture
def cliente(tmp_path):
    app = criar_app({"TESTING": True, "DATA_DIR": tmp_path, "RUN_JOBS": False})
    with app.test_client() as client:
        yield client


def empresa(cliente, **extra):
    response = cliente.post('/api/ed/empresas', json={
        'nome': 'Ateliê de teste', 'nicho': 'Salões de beleza',
        'cidade': 'Recife', 'uf': 'PE', **extra,
    })
    assert response.status_code == 201
    return response.get_json()


def imagem():
    data = io.BytesIO()
    Image.new('RGB', (24, 24), '#0c7660').save(data, 'PNG')
    data.seek(0)
    return data


def test_fluxo_documento_exportacao_e_previa(cliente):
    lead = empresa(cliente, demonstracao=True)
    ident = lead['id']
    upload = cliente.post(f'/api/ed/empresas/{ident}/materiais', data={
        'arquivo': (imagem(), '../foto.png'), 'categoria': 'ambiente',
        'origem': 'Imagem gerada para teste', 'atribuicao': 'Teste',
        'autorizado': 'true',
    })
    assert upload.status_code == 201
    mid = upload.get_json()['id']
    assert cliente.patch(f'/api/ed/empresas/{ident}/materiais/{mid}',
                         json={'selecionado': True}).status_code == 200
    response = cliente.post(f'/api/ed/empresas/{ident}/exportacoes')
    assert response.status_code == 201
    exported = response.get_json()
    with zipfile.ZipFile(io.BytesIO(cliente.get(exported['zip_url']).data)) as archive:
        names = archive.namelist()
        assert {'empresa.md', 'prompt-codex.md', 'materiais.json', 'LEIA-ME.md'} <= set(names)
        manifest = json.loads(archive.read('materiais.json'))
        assert manifest[0]['arquivo'] in names
        assert all(not name.startswith(('/', '..')) for name in names)
        doc = archive.read('empresa.md').decode()
        assert 'DEMONSTRAÇÃO' in doc
        assert 'Pendências' in doc
        assert 'Não invente' in doc
        assert 'PLACES_API_KEY' not in doc
        assert cliente.get(exported['markdown_url']).data.decode() == doc
    preview = cliente.post(f'/api/ed/empresas/{ident}/previas', json={
        'url': 'https://example.com/previa', 'exportacao_id': exported['id'],
    })
    assert preview.status_code == 201
    ficha = cliente.get(f'/api/ed/empresas/{ident}').get_json()
    assert ficha['previas'][0]['exportacao_id'] == exported['id']
    assert ficha['etapa'] == 'previa_pronta'


def test_duplicatas_sao_sugestoes_sem_unir_filiais(cliente):
    a = empresa(cliente, endereco='Rua A, 1')
    b = empresa(cliente, endereco='Rua B, 2')
    leads = cliente.get('/api/ed/empresas?q=ateliê').get_json()
    assert len(leads) == 2
    assert b['id'] in next(x for x in leads if x['id'] == a['id'])['possiveis_duplicatas']
    assert cliente.get('/api/ed/empresas?q=inexistente').get_json() == []


def test_materiais_nao_autorizados_nao_entram_no_zip(cliente):
    ident = empresa(cliente)['id']
    asset = cliente.post(f'/api/ed/empresas/{ident}/materiais', data={
        'arquivo': (imagem(), 'foto.png'), 'origem': 'Referência interna',
    }).get_json()
    assert cliente.patch(f'/api/ed/empresas/{ident}/materiais/{asset["id"]}',
                         json={'selecionado': True}).status_code == 400
    export = cliente.post(f'/api/ed/empresas/{ident}/exportacoes').get_json()
    with zipfile.ZipFile(io.BytesIO(cliente.get(export['zip_url']).data)) as archive:
        assert json.loads(archive.read('materiais.json')) == []


def test_materiais_e_previas_nao_misturam_empresas(cliente):
    a, b = empresa(cliente), empresa(cliente, nome='Outra empresa')
    asset = cliente.post(f'/api/ed/empresas/{a["id"]}/materiais', data={
        'arquivo': (imagem(), 'foto.png'), 'origem': 'Teste',
    }).get_json()
    assert cliente.get(f'/api/ed/empresas/{b["id"]}/materiais/{asset["id"]}/arquivo').status_code == 404
    export = cliente.post(f'/api/ed/empresas/{a["id"]}/exportacoes').get_json()
    assert cliente.post(f'/api/ed/empresas/{b["id"]}/previas', json={
        'url': 'https://example.com', 'exportacao_id': export['id'],
    }).status_code == 400


def test_validacao_upload_url_e_nomes(cliente):
    assert cliente.post('/api/ed/empresas', json={'nome': ''}).status_code == 400
    lead = empresa(cliente)
    assert cliente.patch(f'/api/ed/empresas/{lead["id"]}', json={'site': 'javascript:alert(1)'}).status_code == 400
    assert cliente.post(f'/api/ed/empresas/{lead["id"]}/materiais', data={
        'arquivo': (io.BytesIO(b'<svg onload="alert(1)"></svg>'), 'foto.png'),
    }).status_code == 400
    assert cliente.post(f'/api/ed/empresas/{lead["id"]}/previas', json={'url': 'file:///C:/secret'}).status_code == 400


def test_busca_sem_fonte_configurada_e_limites(cliente):
    params = {'nicho': 'Salões de beleza', 'cidade': 'Recife', 'uf': 'PE', 'limite': 2}
    assert cliente.post('/api/ed/campanhas', json=params).status_code == 409
    assert cliente.put('/api/ed/config', json={'osm_habilitado': True}).status_code == 200
    assert cliente.post('/api/ed/campanhas', json={**params, 'limite': 999}).status_code == 400
    assert cliente.post('/api/ed/campanhas', json=params).status_code == 201


def test_credenciais_e_campos_desconhecidos_nao_persistem(cliente):
    assert cliente.post('/api/ed/empresas', json={'nome': 'Teste', 'api_key': 'segredo'}).status_code == 400
    assert cliente.put('/api/ed/config', json={'api_key': 'segredo'}).status_code == 400


def test_rotas_legadas_inativas_e_origem_externa_bloqueada(cliente):
    assert cliente.post('/api/buscar', json={}).status_code == 404
    assert cliente.post('/api/ed/empresas', json={'nome': 'Teste'},
                        headers={'Origin': 'https://evil.example'}).status_code == 403


def test_exportacao_e_snapshot_e_falta_de_imagem_interrompe(cliente):
    lead = empresa(cliente)
    ident = lead['id']
    asset = cliente.post(f'/api/ed/empresas/{ident}/materiais', data={
        'arquivo': (imagem(), 'foto.png'), 'origem': 'Fixture própria',
        'atribuicao': 'Teste', 'autorizado': 'true',
    }).get_json()
    cliente.patch(f'/api/ed/empresas/{ident}/materiais/{asset["id"]}', json={'selecionado': True})
    export = cliente.post(f'/api/ed/empresas/{ident}/exportacoes').get_json()
    original = cliente.get(export['markdown_url']).data
    cliente.patch(f'/api/ed/empresas/{ident}', json={'nome': 'Novo nome'})
    assert cliente.get(export['markdown_url']).data == original
    with cliente.application.app_context():
        import ed_store as store
        file = store.arquivo_seguro('materiais', f'{ident}/{asset["arquivo"]}')
        # Move somente a fixture dentro da pasta de testes, simulando uma perda de arquivo.
        file.rename(file.with_suffix('.ausente'))
    response = cliente.post(f'/api/ed/empresas/{ident}/exportacoes')
    assert response.status_code == 400
    assert 'ausente' in response.get_json()['erro']
    assert len(cliente.get(f'/api/ed/empresas/{ident}').get_json()['exportacoes']) == 1


def test_contagens_usam_historico_e_nao_etapa(cliente):
    lead = empresa(cliente)
    ident = lead['id']
    cliente.post(f'/api/ed/empresas/{ident}/exportacoes')
    cliente.post(f'/api/ed/empresas/{ident}/exportacoes')
    cliente.patch(f'/api/ed/empresas/{ident}', json={'etapa': 'encontrado'})
    item = cliente.get('/api/ed/empresas').get_json()[0]
    assert item['total_exportacoes'] == 2
    assert item['total_previas'] == 0


def test_backup_completo_restaura_imagens_e_exportacoes(cliente, tmp_path):
    import shutil
    from pathlib import Path
    ident = empresa(cliente)['id']
    uploaded = cliente.post(f'/api/ed/empresas/{ident}/materiais', data={
        'arquivo': (imagem(), 'imagem.png'), 'origem': 'Teste de backup',
    }).get_json()
    exported = cliente.post(f'/api/ed/empresas/{ident}/exportacoes').get_json()
    original_zip = cliente.get(exported['zip_url']).data
    source = Path(cliente.application.config['DATA_DIR'])
    backup = tmp_path / 'backup-restaurado'
    shutil.copytree(source, backup)
    restored_app = criar_app({'TESTING': True, 'DATA_DIR': backup, 'RUN_JOBS': False})
    with restored_app.test_client() as restored:
        assert restored.get(exported['zip_url']).data == original_zip
        assert restored.get(uploaded['arquivo_url']).status_code == 200
        assert restored.get(f'/api/ed/empresas/{ident}').get_json()['id'] == ident
