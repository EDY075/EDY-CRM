from datetime import datetime, timedelta, timezone

import pytest
import requests

from ed_app import criar_app
import ed_search
import ed_store as store


@pytest.fixture
def app(tmp_path):
    return criar_app({'TESTING': True, 'DATA_DIR': tmp_path, 'RUN_JOBS': False})


def params():
    return dict(nicho='Salões de beleza', cidade='Recife', uf='PE', limite=2)


def elemento(ident=1):
    return dict(type='node', id=ident, tags={'name': 'Empresa de teste OSM',
                'addr:street': 'Rua de teste', 'phone': '+55 81 1111-1111'})


def aging(ident):
    return ed_search.atualizar(ident, iniciado_em=(datetime.now(timezone.utc) - timedelta(minutes=2)).isoformat())


def test_busca_importa_dados_com_fontes_e_repeticao_preserva_edicoes(app, monkeypatch):
    monkeypatch.setattr(ed_search, 'consultar', lambda job: ([elemento()], False))
    with app.app_context():
        job = ed_search.iniciar(params(), app)
    ed_search.executar(app, job['id'])
    with app.app_context():
        lead = store.listar_empresas()[0]
        assert lead['fontes']['nome']['fornecedor'] == 'OpenStreetMap'
        assert lead['fontes']['nome']['verificacao'] == 'a_confirmar'
        assert lead['fontes']['nome']['url'].endswith('/node/1')
        assert lead['site'] == ''
        store.gravar_empresa({'nome': 'Nome corrigido pelo cliente', 'confirmado': True}, lead['id'])
        aging(job['id'])
        repeated = ed_search.iniciar(params(), app)
    ed_search.executar(app, repeated['id'])
    with app.app_context():
        assert len(store.listar_empresas()) == 1
        assert store.listar_empresas()[0]['nome'] == 'Nome corrigido pelo cliente'
        assert ed_search.ler(repeated['id'])['repetidos'] == 1


def test_falha_de_rede_nao_fabrica_empresas_e_permite_retomada(app, monkeypatch):
    def fail(job):
        raise requests.Timeout('private-detail-must-not-leak')
    monkeypatch.setattr(ed_search, 'consultar', fail)
    with app.app_context():
        job = ed_search.iniciar(params(), app)
    ed_search.executar(app, job['id'])
    with app.app_context():
        assert ed_search.ler(job['id'])['estado'] == 'erro'
        assert store.listar_empresas() == []
        assert 'private-detail' not in ed_search.ler(job['id'])['mensagem']
        aging(job['id'])
    with app.test_client() as client:
        client.put('/api/ed/config', json={'osm_habilitado': True})
        assert client.post(f'/api/ed/campanhas/{job["id"]}/retomar').status_code == 200
    monkeypatch.setattr(ed_search, 'consultar', lambda job: ([elemento()], True))
    ed_search.executar(app, job['id'])
    with app.app_context():
        assert ed_search.ler(job['id'])['estado'] == 'parcial'
        assert len(store.listar_empresas()) == 1


def test_progress_http_failure_and_resume_does_not_claim_completion(app,monkeypatch):
    calls=[]
    def response(method,endpoint,**kwargs):
        calls.append(endpoint)
        if endpoint==ed_search.NOMINATIM:return [{'boundingbox':['-8.1','-8.0','-35.0','-34.9']}]
        raise ValueError('Fonte temporariamente indisponível: HTTP 504 em '+endpoint)
    monkeypatch.setattr(ed_search,'obter_json',response)
    with app.app_context():job=ed_search.iniciar(params(),app)
    ed_search.executar(app,job['id'])
    with app.app_context():
        failed=ed_search.ler(job['id'])
        assert failed['estado']=='erro' and failed['erro_tipo']=='http'
        assert failed['progresso']==30 and failed['etapa']=='consulta'
        assert failed['encontrados']==0 and store.listar_empresas()==[]
        assert calls==[ed_search.NOMINATIM,ed_search.OVERPASS]


def test_cancela_antes_da_coleta_e_reinicio_marca_interrupcao(app, monkeypatch):
    with app.app_context():
        job = ed_search.iniciar(params(), app)
        ed_search.acionar(job['id'], 'cancelar', app)
    def forbidden(job):
        pytest.fail('Cancelamento deve impedir consulta externa')
    monkeypatch.setattr(ed_search, 'consultar', forbidden)
    ed_search.executar(app, job['id'])
    with app.app_context():
        assert store.listar_empresas() == []
        aging(job['id'])
        next_job = ed_search.iniciar(params(), app)
        store.preparar()
        assert ed_search.ler(next_job['id'])['estado'] == 'interrompida'


def test_consulta_restringe_nicho_area_limite_e_cache(app, monkeypatch):
    calls = []
    def fake(method, endpoint, **kwargs):
        calls.append((method, endpoint, kwargs))
        if endpoint == ed_search.NOMINATIM:
            return [{'boundingbox': ['-8.15', '-8.0', '-35.0', '-34.8']}]
        return {'elements': [elemento(x) for x in range(8)]}
    monkeypatch.setattr(ed_search, 'obter_json', fake)
    with app.app_context():
        values, partial = ed_search.consultar(params())
        assert len(values) == 2 and not partial
        values, _ = ed_search.consultar(params())
        assert len([c for c in calls if c[1] == ed_search.NOMINATIM]) == 1
        assert '["shop"="hairdresser"]' in calls[1][2]['data']['data']
        assert 'out tags 8;' in calls[1][2]['data']['data']


def test_limite_de_campanhas_e_parametros_nao_sao_comandos(app):
    with app.app_context():
        ed_search.iniciar(params(), app)
        with pytest.raises(ValueError, match='andamento'):
            ed_search.iniciar(params(), app)
        with pytest.raises(ValueError):
            ed_search.validar({**params(), 'nicho': '"];out;'})


def test_edicao_de_briefing_preserva_proveniencia(app):
    with app.app_context():
        lead, _ = store.gravar_empresa({'nome': 'Teste OSM', 'cidade': 'Recife',
                    'fonte_url': 'https://www.openstreetmap.org/node/1'}, fornecedor='OpenStreetMap')
        store.gravar_empresa({'nome': lead['nome'], 'confirmado': False,
                              'briefing': {'cta': 'Contato'}}, lead['id'])
        assert store.ler_empresa(lead['id'])['fontes']['nome']['fornecedor'] == 'OpenStreetMap'


def test_resposta_da_execucao_cancelada_nao_contamina_retomada(app, monkeypatch):
    def resposta_atrasada(job):
        with app.app_context():
            ed_search.acionar(job['id'], 'cancelar', app)
            aging(job['id'])
            with store.conectar() as con:
                con.execute("INSERT INTO ed_config VALUES ('osm_habilitado','true')")
            ed_search.acionar(job['id'], 'retomar', app)
        return [elemento()], False
    monkeypatch.setattr(ed_search, 'consultar', resposta_atrasada)
    with app.app_context():
        job = ed_search.iniciar(params(), app)
    ed_search.executar(app, job['id'])
    with app.app_context():
        assert ed_search.ler(job['id'])['estado'] == 'na_fila'
        assert store.listar_empresas() == []
