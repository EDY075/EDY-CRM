"""Adaptadores testados com mocks; não são provas de operação no fornecedor."""
import json
import pytest
from test_ed_enrich import client
import ed_destinations as d

def test_no_secrets_and_no_network_on_listing(client,monkeypatch):
    monkeypatch.setenv('ED_CRM_CLOUDFLARE_TOKEN','SEGREDO-NAO-RETORNAR')
    monkeypatch.setattr(d,'request_json',lambda *a,**k:pytest.fail('GET local não consulta fornecedor'))
    result=client.get('/api/ed/destinos')
    assert result.status_code==200 and 'SEGREDO' not in result.text
    assert next(x for x in result.json if x['id']=='cloudflare')['estado']=='configurado_nao_validado'

@pytest.mark.parametrize('provider,data',[('github',{'repositorio':'../../x'}),('github',{'modo':'automatico'}),('cloudflare',{'account_id':'invalida'}),('n8n',{'base_url':'https://user:token@example.org'}),('n8n',{'base_url':'https://example.org?token=x'}),('storage',{'bucket':'../../outro'}),('storage',{'region':'../../api'}),('storage',{'tipo':'privado'})])
def test_rejects_unsafe_configuration(client,provider,data):
    assert client.put('/api/ed/destinos/'+provider,json=data).status_code==400

def test_github_identity_repo_proof_changed_config_invalidates(client,monkeypatch):
    monkeypatch.setattr(d.shutil,'which',lambda _: 'gh.exe')
    monkeypatch.setattr(d,'github_get',lambda path,c: {'login':'conta-teste'} if path=='/user' else [{'id':1,'full_name':'org/site','permissions':{'push':True},'private':True}])
    job=client.post('/api/ed/destinos/github/testar').json
    assert job['estado']=='concluida' and job['resultado']['capacidade']=='repositorios_leitura'
    card=next(x for x in client.get('/api/ed/destinos').json if x['id']=='github')
    assert card['estado']=='limitado' and card['prova']['conta']=='conta-teste'
    result=client.put('/api/ed/destinos/github',json={'repositorio':'org/site'})
    assert result.json['estado']=='configurado_nao_validado' and result.json['prova']=={}

def test_provider_error_is_not_success_and_cannot_expose_remote_body(client,monkeypatch):
    monkeypatch.setenv('ED_CRM_CLOUDFLARE_TOKEN','CHAVE-PRIVADA')
    monkeypatch.setattr(d,'request_json',lambda *a,**k: (_ for _ in ()).throw(RuntimeError('CHAVE-PRIVADA erro externo')))
    job=client.post('/api/ed/destinos/cloudflare/testar').json
    assert job['estado']=='erro' and 'resultado' not in job
    assert 'CHAVE-PRIVADA' not in json.dumps(job)

def test_cloudflare_allowlist_omits_provider_secrets(client,monkeypatch):
    monkeypatch.setenv('ED_CRM_CLOUDFLARE_TOKEN','token')
    client.put('/api/ed/destinos/cloudflare',json={'account_id':'a'*32})
    monkeypatch.setattr(d,'request_json',lambda *a,**k:dict(success=True,result=[dict(id='p',name='site',source={'type':'github'},deployment_configs={'production':{'env_vars':{'secret':{'value':'SEGREDO'}}}})]))
    job=client.post('/api/ed/destinos/cloudflare/testar').json
    assert job['estado']=='concluida' and job['resultado']['recursos'][0]['modo']=='git'
    assert 'SEGREDO' not in json.dumps(job)

def test_n8n_private_network_rejected_before_sending_key(client,monkeypatch):
    monkeypatch.setenv('ED_CRM_N8N_KEY','SEGREDO')
    client.put('/api/ed/destinos/n8n',json={'base_url':'https://127.0.0.1'})
    result=client.post('/api/ed/destinos/n8n/testar').json
    assert result['estado']=='erro' and 'privados' in result['mensagem']

def test_storage_key_scope_and_traversal(client):
    import ed_remote_storage as storage
    with client.application.app_context():
        assert storage.key('lead','versao','foto.png')=='edy/principal/lead/versoes/versao/foto.png'
        with pytest.raises(ValueError):storage.key('../outro','v','foto.png')

def test_storage_roundtrip_checks_hash(client,monkeypatch):
    import io
    import ed_remote_storage as storage
    class Fake:
        data=b''
        def head_bucket(self,**kw):pass
        def put_object(self,**kw):self.data=kw['Body'];return {}
        def get_object(self,**kw):return {'Body':io.BytesIO(self.data)}
        def generate_presigned_url(self,*a,**kw):assert kw['ExpiresIn']==300;return 'https://example.org/?assinatura=nao_persistir'
        def close(self):pass
    fake=Fake();monkeypatch.setattr(storage,'client',lambda _:fake)
    with client.application.app_context():
        out=storage.test({'bucket':'privado'})
        assert out['capacidade']=='objeto_gravado_e_lido'
        assert 'assinatura' not in json.dumps(out)
    fake.get_object=lambda **kw:dict(Body=io.BytesIO(b'alterada'))
    with client.application.app_context(),pytest.raises(ValueError,match='integridade'):storage.test({'bucket':'privado'})
