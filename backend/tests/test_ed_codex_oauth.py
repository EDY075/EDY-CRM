import base64
import json
import time
from urllib.parse import urlsplit,parse_qs
import pytest
from test_ed_enrich import client
import ed_codex_oauth as oauth


@pytest.fixture
def vault(client,monkeypatch):
    # Somente testes: armazenamento simulado, separado do DPAPI real usado no produto.
    data={'host_id':'test-host','profiles':{},'active':None}
    monkeypatch.setattr(oauth,'read',lambda:data)
    monkeypatch.setattr(oauth,'write',lambda value:None)
    oauth.pending.clear()
    return data


def test_pkce_registration_and_callback_never_exchange_dynamic_id(vault,monkeypatch):
    started=oauth.start();query=parse_qs(urlsplit(started['url']).query)
    state=query['state'][0]
    assert query['client_id']==['dynamic_agent_client']
    assert 'chatgpt.tokens.use.direct' in query['scope'][0]
    assert query['code_challenge_method']==['S256']
    calls=[]
    def http(method,url,**kw):
        calls.append(kw['data'])
        return {'access_token':'own-access','refresh_token':'own-refresh','id_token':'test-id','expires_in':3600,'scope':oauth.SCOPE}
    monkeypatch.setattr(oauth,'http',http)
    monkeypatch.setattr(oauth,'verify_identity',lambda token,client,nonce:{'iss':oauth.ISSUER,'sub':'person','email':'test@example.org'})
    ident=oauth.callback({'state':state,'code':'code-only','client_id':'issued-client'})
    assert calls[0]['client_id']=='issued-client'
    assert calls[0]['redirect_uri']==oauth.CALLBACK
    assert calls[0]['code_verifier']==oauth.pending.get(state,{}).get('verifier',calls[0]['code_verifier'])
    assert vault['active']==ident
    assert 'own-access' not in json.dumps(oauth.status())
    with pytest.raises(ValueError,match='state'):oauth.callback({'state':state,'code':'replay','client_id':'issued-client'})


@pytest.mark.parametrize('failure',['state','denied','client','scope','signature'])
def test_failed_login_preserves_selected_account(vault,monkeypatch,failure):
    vault['active']='old';vault['profiles']['old']={'client_id':'old-client','rotulo':'Anterior'}
    started=oauth.start('old');state=parse_qs(urlsplit(started['url']).query)['state'][0]
    args={'state':state,'code':'once','client_id':'old-client'}
    if failure=='state':args['state']='wrong'
    if failure=='denied':args['error']='access_denied'
    if failure=='client':args['client_id']='other-client'
    monkeypatch.setattr(oauth,'http',lambda *a,**k:{'access_token':'a','refresh_token':'r','id_token':'id','scope':'' if failure=='scope' else oauth.SCOPE})
    monkeypatch.setattr(oauth,'verify_identity',lambda *a:(_ for _ in ()).throw(ValueError('assinatura inválida')))
    with pytest.raises(ValueError):oauth.callback(args)
    assert vault['active']=='old' and list(vault['profiles'])==['old']


def test_same_credential_catalog_exact_service_slugs_and_account(vault,monkeypatch):
    vault['active']='selected';vault['profiles']['selected']={'client_id':'issued','rotulo':'Conta','access_token':'oauth-own-only','refresh_token':'refresh','expires':time.time()+1000,'scope':oauth.SCOPE.split()}
    calls=[]
    def http(method,url,**kw):
        calls.append((url,kw))
        return {'models':[{'slug':'exact-service/slug','display_name':'Display','visibility':'list'},{'slug':'hidden','visibility':'hide'}]}
    monkeypatch.setattr(oauth,'http',http)
    token,account=oauth.credential()
    entries=oauth.models(token,account)
    assert entries[0]['slug']=='exact-service/slug' and len(entries)==1
    assert calls==[(oauth.RESOURCE+'/models',{'headers':{'Authorization':'Bearer oauth-own-only'}})]
    assert entries[0]['conta']=='selected'


def test_refresh_rotates_atomically_and_does_not_request_new_scope(vault,monkeypatch):
    vault['active']='a';vault['profiles']['a']={'client_id':'issued','rotulo':'Conta','access_token':'expired','refresh_token':'old','expires':0,'scope':oauth.SCOPE.split()}
    calls=[]
    def http(method,url,**kw):
        calls.append(kw['data']);return {'access_token':'fresh','refresh_token':'rotated','expires_in':3600}
    monkeypatch.setattr(oauth,'http',http)
    assert oauth.credential()[0]=='fresh'
    assert oauth.credential()[0]=='fresh' and len(calls)==1
    assert calls[0]=={'grant_type':'refresh_token','client_id':'issued','refresh_token':'old','resource':oauth.RESOURCE}
    assert vault['profiles']['a']['refresh_token']=='rotated'


def test_native_cache_does_not_authorize_public_oauth(vault,client,monkeypatch):
    monkeypatch.setattr(oauth,'native_identity',lambda p:{'identificador':'native'})
    with pytest.raises(ValueError,match='própria'):oauth.credential()
    assert client.post('/api/ed/runtime/oauth/modelos',json={}).status_code==400
    assert client.post('/api/ed/runtime/testar',json={'modo':'unknown'}).status_code==400


def test_real_signature_nonce_audience_and_expiry_checks(monkeypatch):
    from cryptography.hazmat.primitives import hashes
    from cryptography.hazmat.primitives.asymmetric import rsa,padding
    key=rsa.generate_private_key(public_exponent=65537,key_size=2048)
    def encode(b):return base64.urlsafe_b64encode(b).decode().rstrip('=')
    public=key.public_key().public_numbers()
    def integer(n):return encode(n.to_bytes((n.bit_length()+7)//8,'big'))
    monkeypatch.setattr(oauth,'http',lambda method,url,**kw:{'issuer':oauth.ISSUER,'jwks_uri':oauth.ISSUER+'/jwks'} if 'configuration' in url else {'keys':[{'kid':'test','kty':'RSA','e':integer(public.e),'n':integer(public.n)}]})
    def token(**changes):
        claims={'iss':oauth.ISSUER,'aud':'client','sub':'person','nonce':'nonce','exp':time.time()+300,**changes}
        msg=encode(json.dumps({'alg':'RS256','kid':'test'}).encode())+'.'+encode(json.dumps(claims).encode())
        return msg+'.'+encode(key.sign(msg.encode(),padding.PKCS1v15(),hashes.SHA256()))
    assert oauth.verify_identity(token(),'client','nonce')['sub']=='person'
    for changes in ({'aud':'other'},{'nonce':'wrong'},{'exp':0},{'iss':'https://evil.org'}):
        with pytest.raises(ValueError,match='ID token'):oauth.verify_identity(token(**changes),'client','nonce')
    tampered=token().rsplit('.',1)[0]+'.'+encode(b'bad-signature')
    with pytest.raises(ValueError,match='ID token'):oauth.verify_identity(tampered,'client','nonce')


def test_subprocess_oauth_provider_uses_own_pinned_credential_only(client,monkeypatch,tmp_path):
    import io
    import ed_runtime
    captured={}
    account={'identificador':'own-account','rotulo':'Own','modo':'oauth_plano'}
    monkeypatch.setenv('ACCESS_TOKEN','native-or-unrelated-must-not-leak')
    monkeypatch.setenv('OPENAI_API_KEY','must-not-switch-billing')
    monkeypatch.setattr('ed_secrets.get',lambda provider:'')
    monkeypatch.setattr(oauth,'credential',lambda:('own-oauth-only',account))
    def models(token,selected):
        assert token=='own-oauth-only' and selected is account
        return [{'slug':'preserve/model-slug','display_name':'Model'}]
    monkeypatch.setattr(oauth,'models',models)
    monkeypatch.setattr(ed_runtime,'command',lambda:['test-runtime'])
    monkeypatch.setattr(ed_runtime,'private_native_cache',lambda home:None)
    monkeypatch.setattr(ed_runtime.subprocess,'check_output',lambda *a,**k:'codex-cli 0.160.0')
    class Process:
        def __init__(self,argv,**kw):
            captured.update(argv=argv,env=kw['env'])
            self.stdin=io.StringIO();self.stdout=io.StringIO();self.stderr=io.StringIO()
        def poll(self):return 0
    monkeypatch.setattr(ed_runtime.subprocess,'Popen',Process)
    monkeypatch.setattr(ed_runtime.RPC,'call',lambda *a,**k:{})
    with client.application.app_context():
        rpc=ed_runtime.RPC(tmp_path/'workspace','oauth_plano')
        assert rpc.login('oauth_plano') is account
        assert captured['env']['ACCESS_TOKEN']=='own-oauth-only'
        assert 'OPENAI_API_KEY' not in captured['env']
        assert 'model_providers.openai_chatgpt_plan.base_url="https://api.openai.com/v1"' in captured['argv']
        assert 'model_providers.openai_chatgpt_plan.requires_openai_auth=false' in captured['argv']
        assert 'model_providers.openai_chatgpt_plan.supports_websockets=false' in captured['argv']
        assert 'chatgptAuthTokens' not in json.dumps(captured['argv'])
        assert 'own-oauth-only' not in json.dumps(rpc.audit)
        rpc.close()
