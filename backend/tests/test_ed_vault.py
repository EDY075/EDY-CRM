from test_ed_enrich import client


def test_vault_no_network_on_get_and_credentials_masked(client,monkeypatch):
    import ed_vault,ed_secrets
    values={};monkeypatch.setattr(ed_secrets,'get',lambda k:values.get(k,''));monkeypatch.setattr(ed_secrets,'put',lambda k,v:values.update({k:v}))
    calls=[]
    def remote(method,url,**kw):
        calls.append((method,url))
        if 'login' in url:return {'accessToken':'SECRET-TOKEN'}
        if '/secrets/FIRECRAWL' in url:return {'secret':{'secretValue':'SECRET-PROVIDER'}}
        return {'secrets':[{'secretValue':'SECRET-HIDDEN'}]}
    monkeypatch.setattr(ed_vault,'request_json',remote)
    data=dict(endpoint='https://us.infisical.com',project_id='qa-project',environment='dev',secret_path='/crm',client_id='identity',client_secret='SECRET-BOOTSTRAP',referencias={'firecrawl':'FIRECRAWL'})
    assert client.put('/api/ed/cofre',json=data).status_code==200
    assert not calls
    assert client.get('/api/ed/cofre').status_code==200 and not calls
    assert client.post('/api/ed/cofre/testar',json={}).status_code==200
    r=client.post('/api/ed/cofre/importar/firecrawl',json={});assert r.status_code==200
    assert values['firecrawl']=='SECRET-PROVIDER'
    assert all(s not in client.get('/api/ed/cofre').text+r.text for s in ('SECRET-TOKEN','SECRET-PROVIDER','SECRET-BOOTSTRAP','SECRET-HIDDEN'))
    data['referencias']={'codex_api':'AUTH'}
    assert client.put('/api/ed/cofre',json=data).status_code==400


def test_vault_http_error_does_not_claim_success(client,monkeypatch):
    import ed_vault
    monkeypatch.setattr(ed_vault,'test',lambda:(_ for _ in ()).throw(ValueError('Fornecedor indisponível (HTTP 403).')))
    assert client.post('/api/ed/cofre/testar',json={}).status_code==400
    assert client.get('/api/ed/cofre').json['teste']['estado']=='erro'
