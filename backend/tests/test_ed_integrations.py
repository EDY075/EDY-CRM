import json
from ed_app import criar_app


def test_status_somente_presenca_sem_credenciais_ou_acesso(monkeypatch, tmp_path):
    import ed_integrations
    monkeypatch.setenv('ED_CRM_GOOGLE_PLACES_KEY', 'SEGREDO-GOOGLE-TESTE')
    monkeypatch.setenv('ED_CRM_INSTAGRAM_ACCESS_TOKEN', 'SEGREDO-META-TESTE')
    app = criar_app({'TESTING': True, 'DATA_DIR': tmp_path, 'RUN_JOBS': False})
    with app.test_client() as client:
        result = client.get('/api/ed/integracoes/status')
        assert result.status_code == 200
        assert 'SEGREDO' not in result.data.decode()
        data = result.get_json()
        assert data['google']['credencial_presente']
        assert data['instagram']['credencial_presente']
        assert not data['consulta_externa_ativa']
        assert not data['google']['exportavel']


def test_config_invalida_nao_expoe_o_arquivo(monkeypatch, tmp_path):
    import ed_integrations
    root = tmp_path / 'project'
    (root / 'config').mkdir(parents=True)
    (root / 'config/integrations.local.json').write_text(json.dumps({'token': 'SEGREDO'}))
    monkeypatch.setattr(ed_integrations, 'ROOT', root)
    data = ed_integrations.status()
    assert data['erro_configuracao']
    assert 'SEGREDO' not in json.dumps(data)
