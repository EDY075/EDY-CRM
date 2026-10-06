"""Cofre opcional Infisical. Leitura explícita, valores só no backend DPAPI."""
import json
import re
from urllib.parse import urlsplit,quote,urlencode
from flask import jsonify,request
import ed_store as store
import ed_secrets
from ed_connectors import request_json


def config():
    with store.conectar() as con:r=con.execute('SELECT valor FROM ed_config WHERE chave=?',('cofre:config',)).fetchone()
    return json.loads(r['valor']) if r else dict(endpoint='https://us.infisical.com',project_id='',environment='dev',secret_path='/',client_id='',organization_slug='',referencias={})


def status():
    c=config()
    with store.conectar() as con:r=con.execute('SELECT valor FROM ed_config WHERE chave=?',('cofre:teste',)).fetchone()
    return dict(config=c,credencial_presente=bool(ed_secrets.get('infisical')),teste=json.loads(r['valor']) if r else None,armazenamento='Ambiente ou DPAPI do usuário Windows; chave mestra fora do SQLite. Importação explícita do Infisical para cache local criptografado. Codex nativo excluído.')


def validate(data):
    if not isinstance(data,dict) or set(data)-set(config())-{'client_secret'}:raise ValueError('Configuração de cofre inválida.')
    out={**config(),**{k:v for k,v in data.items() if k!='client_secret'}}
    for k in ('endpoint','project_id','environment','secret_path','client_id','organization_slug'):out[k]=store.texto(out[k],500)
    u=urlsplit(out['endpoint'])
    if u.scheme!='https' or not u.hostname or u.username or u.password or u.query or u.fragment or u.path not in ('','/'):raise ValueError('Endpoint do cofre precisa de HTTPS, sem caminho, parâmetros ou credenciais.')
    out['endpoint']=out['endpoint'].rstrip('/')
    refs=out['referencias']
    if not isinstance(refs,dict) or len(refs)>15 or set(refs)-set(ed_secrets.ENV)-{'infisical'} or any(k in refs for k in ('infisical','codex_api')):raise ValueError('Referências inválidas. Credenciais nativas Codex e bootstrap do cofre permanecem separados.')
    out['referencias']={k:store.texto(v,200) for k,v in refs.items()}
    if any(not re.fullmatch(r'[A-Za-z0-9_.-]+',v) for v in refs.values()):raise ValueError('Nome de segredo inválido.')
    return out


def test():
    c=config();secret=ed_secrets.get('infisical')
    if not secret or not c['client_id'] or not c['project_id']:raise ValueError('Faltam client ID/secret da machine identity e projeto Infisical com permissão de leitura.')
    body=dict(clientId=c['client_id'],clientSecret=secret)
    if c['organization_slug']:body['organizationSlug']=c['organization_slug']
    token=request_json('POST',c['endpoint']+'/api/v1/auth/universal-auth/login',payload=body).get('accessToken')
    if not isinstance(token,str) or not token:raise ValueError('Cofre não devolveu token válido.')
    query=urlencode(dict(projectId=c['project_id'],environment=c['environment'],secretPath=c['secret_path']))
    # Lista somente para verificar escopo; descarta valores, não registra corpo do serviço.
    result=request_json('GET',c['endpoint']+'/api/v4/secrets?'+query,headers={'Authorization':'Bearer '+token})
    if not isinstance(result.get('secrets'),list):raise ValueError('Resposta de projeto inválida; acesso não validado.')
    return token,dict(estado='autenticacao_validada',mensagem='Machine identity e leitura do escopo validadas; uso dos provedores precisa de testes próprios.',data=store.agora(),quantidade=len(result['secrets']))


def registrar(bp):
    @bp.get('/cofre')
    def view():return jsonify(status())
    @bp.put('/cofre')
    def save():
        data=request.get_json();out=validate(data)
        if data.get('client_secret'):ed_secrets.put('infisical',data['client_secret'])
        with store.conectar() as con:
            con.execute('INSERT INTO ed_config VALUES (?,?) ON CONFLICT(chave) DO UPDATE SET valor=excluded.valor',('cofre:config',json.dumps(out)))
            con.execute('DELETE FROM ed_config WHERE chave=?',('cofre:teste',))
        return jsonify(status())
    @bp.post('/cofre/testar')
    def connection():
        try:_,out=test()
        except ValueError as exc:out=dict(estado='erro',mensagem=str(exc),data=store.agora())
        with store.conectar() as con:con.execute('INSERT INTO ed_config VALUES (?,?) ON CONFLICT(chave) DO UPDATE SET valor=excluded.valor',('cofre:teste',json.dumps(out)))
        return jsonify(status()),200 if out['estado']!='erro' else 400
    @bp.post('/cofre/importar/<provider>')
    def pull(provider):
        c=config();name=c['referencias'].get(provider)
        if not name:raise ValueError('Configure a referência deste fornecedor no cofre.')
        token,_=test();query=urlencode(dict(projectId=c['project_id'],environment=c['environment'],secretPath=c['secret_path']))
        value=request_json('GET',c['endpoint']+'/api/v4/secrets/'+quote(name,safe='')+'?'+query,headers={'Authorization':'Bearer '+token}).get('secret',{}).get('secretValue')
        if not isinstance(value,str) or not value:raise ValueError('Segredo ausente ou resposta inválida.')
        ed_secrets.put(provider,value)
        from ed_services import log,fingerprint
        log(provider,dict(estado='configurado_nao_validado',mensagem='Credencial importada do Infisical para DPAPI. Teste o fornecedor.',fingerprint=fingerprint(provider)))
        return jsonify(mensagem='Credencial importada no backend; valor não retornado. Validação do fornecedor pendente.')
