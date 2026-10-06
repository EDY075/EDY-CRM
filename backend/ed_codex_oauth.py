"""Credenciais OAuth do CRM são separadas do cache nativo da CLI."""
import base64
import hashlib
import json
import os
import secrets
import threading
import time
from urllib.parse import urlencode, urlsplit
from pathlib import Path
import requests
import ed_store as store
from ed_codex_transport import RuntimeFailure

ISSUER='https://auth.openai.com'
TOKEN=ISSUER+'/api/accounts/oauth/token'
RESOURCE='https://api.openai.com/v1'
SCOPE='openid profile email offline_access resource.invoke chatgpt.tokens.use.direct'
CALLBACK='http://127.0.0.1:5128/api/ed/runtime/oauth/callback'
mutex=threading.RLock()
pending={}


def read():
    from ed_secrets import crypt
    path=store.pasta()/'codex-oauth.dpapi'
    if not path.exists():return {'host_id':secrets.token_urlsafe(24),'profiles':{},'active':None}
    if path.stat().st_size>1_000_000:raise ValueError('Cofre OAuth inválido; reautorize o CRM.')
    try:return json.loads(crypt(path.read_bytes(),True))
    except (OSError,ValueError):raise ValueError('Cofre OAuth indisponível neste usuário Windows.') from None


def write(value):
    from ed_secrets import crypt
    path=store.pasta()/'codex-oauth.dpapi'
    tmp=path.with_suffix('.tmp')
    tmp.write_bytes(crypt(json.dumps(value).encode()))
    tmp.replace(path)


def http(method,url,**kwargs):
    with requests.Session() as session:
        session.trust_env=False
        try:response=session.request(method,url,timeout=(10,30),allow_redirects=False,**kwargs)
        except requests.RequestException:raise RuntimeFailure({'message':'Falha de rede ao acessar OAuth/OpenAI; nenhuma credencial exposta.'}) from None
    if len(response.content)>1_000_000:raise RuntimeFailure({'message':'Resposta do fornecedor acima do limite.'})
    try:value=response.json()
    except ValueError:value={'message':'Resposta HTTP sem JSON válido.'}
    if not 200<=response.status_code<300:
        raise RuntimeFailure({'httpStatusCode':response.status_code,'request_id':response.headers.get('x-request-id'),'resposta':value})
    return value


def start(profile_id=None):
    with mutex:
        vault=read()
        profile=vault['profiles'].get(profile_id) if profile_id else None
        if profile_id and not profile:raise ValueError('Conta OAuth não encontrada.')
        state,nonce,verifier=(secrets.token_urlsafe(32) for _ in range(3))
        challenge=base64.urlsafe_b64encode(hashlib.sha256(verifier.encode()).digest()).decode().rstrip('=')
        pending.clear() # Uma tentativa local de cada vez; a anterior deixa de ser válida.
        pending[state]={'nonce':nonce,'verifier':verifier,'expires':time.time()+600,'profile':profile_id,'client_id':profile['client_id'] if profile else None}
        write(vault) # Identificador do host existe antes do primeiro redirecionamento.
        params={'client_id':profile['client_id'] if profile else 'dynamic_agent_client','ext_agent_host_id':vault['host_id'],
                'response_type':'code','redirect_uri':CALLBACK,'scope':SCOPE,'resource':RESOURCE,'state':state,'nonce':nonce,
                'code_challenge_method':'S256','code_challenge':challenge}
        if not profile:params['agent_name_hint']='edy_crm'
        return {'url':ISSUER+'/api/accounts/authorize?'+urlencode(params),'mensagem':'Autorize o consumo do plano pelo EDY CRM na página oficial; o login nativo permanece separado.'}


def decode_part(value):
    return base64.urlsafe_b64decode(value+'='*((-len(value))%4))


def verify_identity(token,client_id,nonce):
    """ID token RS256: assinatura oficial, emissor, audience, expiração e nonce."""
    from cryptography.hazmat.primitives import hashes
    from cryptography.hazmat.primitives.asymmetric import rsa,padding
    from cryptography.exceptions import InvalidSignature
    try:
        header,payload,signature=token.split('.')
        h,claims=json.loads(decode_part(header)),json.loads(decode_part(payload))
        if h.get('alg')!='RS256':raise ValueError()
        config=http('GET',ISSUER+'/.well-known/openid-configuration')
        url=config['jwks_uri']
        parsed=urlsplit(url)
        if config.get('issuer')!=ISSUER or parsed.scheme!='https' or parsed.netloc!='auth.openai.com':raise ValueError()
        keys=http('GET',url)['keys']
        jwk=next(k for k in keys if k.get('kid')==h.get('kid') and k.get('kty')=='RSA')
        public=rsa.RSAPublicNumbers(int.from_bytes(decode_part(jwk['e']),'big'),int.from_bytes(decode_part(jwk['n']),'big')).public_key()
        public.verify(decode_part(signature),(header+'.'+payload).encode(),padding.PKCS1v15(),hashes.SHA256())
        aud=claims.get('aud');aud=aud if isinstance(aud,list) else [aud]
        if claims.get('iss')!=ISSUER or client_id not in aud or not isinstance(claims.get('exp'),(int,float)) or claims['exp']<=time.time() or not claims.get('sub') or claims.get('nonce')!=nonce:raise ValueError()
        if len(aud)>1 and claims.get('azp')!=client_id:raise ValueError()
        return claims
    except (ValueError,KeyError,IndexError,TypeError,StopIteration,InvalidSignature):
        raise ValueError('ID token OAuth inválido (assinatura, conta, audiência, expiração ou nonce). Conta anterior preservada.') from None


def callback(args):
    with mutex:
        state=args.get('state','')
        attempt=pending.pop(state,None)
        if not attempt or attempt['expires']<time.time():raise ValueError('Login OAuth expirado ou state inválido. Inicie novamente; nenhuma conta foi alterada.')
        if args.get('error'):raise ValueError('Autorização OAuth não concluída: '+str(args['error'])[:80])
        client_id=attempt['client_id'] or args.get('client_id')
        if not client_id or client_id=='dynamic_agent_client' or (attempt['client_id'] and args.get('client_id',client_id)!=client_id):raise ValueError('Identificador de registro OAuth não corresponde ao login iniciado.')
        code=args.get('code')
        if not code:raise ValueError('Callback OAuth sem código; nenhuma credencial gravada.')
        tokens=http('POST',TOKEN,data={'grant_type':'authorization_code','client_id':client_id,'code':code,'code_verifier':attempt['verifier'],'redirect_uri':CALLBACK,'resource':RESOURCE})
        scopes=tokens.get('scope','').split()
        if not {'chatgpt.tokens.use.direct','resource.invoke'}<=set(scopes):raise ValueError('A autorização não concedeu chatgpt.tokens.use.direct e resource.invoke. Login nativo não substitui essa permissão.')
        claims=verify_identity(tokens.get('id_token',''),client_id,attempt['nonce'])
        if not tokens.get('access_token') or not tokens.get('refresh_token'):raise ValueError('OAuth não forneceu sessão completa; conta anterior preservada.')
        vault=read()
        ident=hashlib.sha256((client_id+'|'+claims['iss']+'|'+claims['sub']).encode()).hexdigest()[:24]
        email=claims.get('email','');label=(email.split('@')[0][:2]+'…@'+email.split('@')[-1]) if '@' in email else 'Conta autorizada '+ident[:6]
        vault['profiles'][ident]={'client_id':client_id,'subject':claims['sub'],'issuer':claims['iss'],'rotulo':label,
            'access_token':tokens['access_token'],'refresh_token':tokens['refresh_token'],'scope':scopes,'expires':time.time()+float(tokens.get('expires_in',3600))}
        vault['active']=ident
        write(vault)
        return ident


def native_identity(path):
    try:
        auth=json.loads(Path(path).read_text(encoding='utf-8'))
        tokens=auth.get('tokens',{})
        raw=tokens.get('id_token','').split('.')[1]
        claims=json.loads(base64.urlsafe_b64decode(raw+'='*((-len(raw))%4)))
        account=tokens.get('account_id','')
        email=claims.get('email','')
        label=(email.split('@')[0][:2]+'…@'+email.split('@')[-1]) if '@' in email else 'Conta nativa'
        return {'identificador':hashlib.sha256(account.encode()).hexdigest()[:16], 'rotulo':label,
                'workspace':account, 'origem':'Cache de autenticação nativa; conta conferida por account/read.'}
    except (OSError,ValueError,IndexError,TypeError):return {'rotulo':'Conta nativa', 'identificador':'nativa', 'origem':'account/read; identificação do cache indisponível.'}


def credential():
    with mutex:
        vault=read();ident=vault.get('active');profile=vault['profiles'].get(ident)
        if not profile:raise ValueError('Falta autorização OAuth própria do EDY CRM para consumir o plano ChatGPT. O login nativo da CLI não concede esse acesso.')
        if not {'resource.invoke','chatgpt.tokens.use.direct'}<=set(profile.get('scope',[])):raise ValueError('Conta OAuth sem escopo de consumo do plano; reautorize o CRM.')
        if profile['expires']<time.time()+60:
            tokens=http('POST',TOKEN,data={'grant_type':'refresh_token','client_id':profile['client_id'],'refresh_token':profile['refresh_token'],'resource':RESOURCE})
            if not tokens.get('access_token'):raise ValueError('Renovação OAuth sem access token; reautorize a conta.')
            profile.update(access_token=tokens['access_token'],refresh_token=tokens.get('refresh_token',profile['refresh_token']),expires=time.time()+float(tokens.get('expires_in',3600)))
            if tokens.get('scope'):profile['scope']=tokens['scope'].split()
            write(vault)
            if not {'resource.invoke','chatgpt.tokens.use.direct'}<=set(profile['scope']):raise ValueError('Renovação retirou o escopo de consumo do plano; reautorize a conta.')
        return profile['access_token'],{'modo':'oauth_plano','tipo':'oauth_consumo_plano','identificador':ident,'rotulo':profile['rotulo'],'origem':'Autorização própria do EDY CRM; conta vinculada ao registro OAuth.'}


def status():
    try:
        with mutex:vault=read()
        return {'estado':'autorizado_nao_validado' if vault.get('active') else 'sem_autorizacao','selecionada':vault.get('active'),
                'contas':[{'id':k,'rotulo':v['rotulo']} for k,v in vault['profiles'].items()]}
    except ValueError as exc:return {'estado':'erro','mensagem':str(exc),'contas':[],'selecionada':None}


def select(ident):
    with mutex:
        vault=read()
        if ident not in vault['profiles']:raise ValueError('Conta OAuth não encontrada.')
        vault['active']=ident;write(vault)


def models(token=None,account=None):
    if token is None:token,account=credential()
    value=http('GET',RESOURCE+'/models',headers={'Authorization':'Bearer '+token})
    entries=value.get('models')
    if not isinstance(entries,list):raise ValueError('Catálogo OAuth não seguiu o contrato models/slug; nenhum identificador inferido do catálogo da CLI.')
    return [{'slug':m['slug'],'display_name':m.get('display_name',m['slug']),'estado':'listado','conta':account['identificador']} for m in entries
            if isinstance(m,dict) and m.get('visibility')=='list' and isinstance(m.get('slug'),str)]


def registrar(bp):
    from flask import jsonify,request,redirect
    @bp.post('/runtime/oauth/iniciar')
    def oauth_start():
        data=request.get_json()
        if not isinstance(data,dict) or set(data)-{'conta'}:raise ValueError('Selecione uma conta ou inicie uma nova autorização.')
        return jsonify(start(data.get('conta')))

    @bp.get('/runtime/oauth/callback')
    def oauth_callback():
        try:
            callback(request.args)
            return redirect('/?oauth=autorizado',303)
        except ValueError as exc:
            # Não devolve código, state ou tokens ao navegador nem os grava em logs.
            return jsonify(erro=str(exc)),400

    @bp.post('/runtime/oauth/selecionar')
    def oauth_select():
        data=request.get_json()
        if not isinstance(data,dict) or set(data)!={'conta'}:raise ValueError('Conta OAuth necessária.')
        select(data['conta'])
        return jsonify(status())

    @bp.post('/runtime/oauth/modelos')
    def oauth_models():
        return jsonify(modelos=models(),conta=credential()[1])
