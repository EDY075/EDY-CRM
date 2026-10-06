"""Destinos explícitos: leituras remotas, provas por capacidade e segredos separados.

Não publica nem envia prospecção. Nunca aceita comandos, URLs com tokens ou
respostas brutas do fornecedor no banco. Configuração e prova são por workspace.
"""
import hashlib
import json
import re
import shutil
import subprocess
from urllib.parse import urlsplit
from flask import current_app, jsonify, request, g
import ed_store as store
import ed_secrets
from ed_connectors import request_json
from ed_workspace import submit
from ed_services import pool, lock, ler_job, save as save_job

CATALOG = {
 'github': dict(nome='GitHub',grupo='Publicar e armazenar',finalidade='Escolher repositório e conferir acesso ao código',campos={'modo':'Modo: cli ou token','repositorio':'Repositório: organização/nome'},padrao={'modo':'cli','repositorio':''},acesso='Sessão gh autorizada ou token fine-grained restrito ao repositório; Metadata Read. Escrita requer Contents Write e autorização da operação.',docs='https://docs.github.com/en/rest/users/users#get-the-authenticated-user'),
 'cloudflare': dict(nome='Cloudflare Pages',grupo='Publicar e armazenar',finalidade='Conferir contas, projetos e modalidade de publicação',campos={'account_id':'ID da conta Cloudflare','projeto':'Nome do projeto Pages'},padrao={'account_id':'','projeto':''},acesso='API token restrito com Pages Read e Account Read quando necessário. Pages Write apenas na etapa de publicação autorizada.',docs='https://developers.cloudflare.com/pages/get-started/direct-upload/'),
 'n8n': dict(nome='n8n',grupo='Automatizar',finalidade='Consultar workflows; EDY mantém a fila e os checkpoints',campos={'base_url':'URL HTTPS da instância','workflow_id':'ID do workflow (opcional)'},padrao={'base_url':'','workflow_id':''},acesso='Public API habilitada e API key X-N8N-API-KEY. A chave de webhook é independente; n8n remoto não acessa este localhost.',docs='https://docs.n8n.io/'),
 'storage': dict(nome='R2 / S3 privado',grupo='Publicar e armazenar',finalidade='Guardar arquivos autorizados por workspace e versão',campos={'tipo':'Tipo: r2 ou s3','account_id':'ID da conta R2','bucket':'Bucket privado','region':'Região S3 (R2: auto)'},padrao={'tipo':'r2','account_id':'','bucket':'','region':'auto'},acesso='Access key ID e secret key S3, permissão no bucket privado para Head/Get/Put. URLs temporárias de leitura, nunca bucket público.',docs='https://developers.cloudflare.com/r2/api/s3/api/'),
}
SECRET_NAMES={'github':'ED_CRM_GITHUB_TOKEN','cloudflare':'ED_CRM_CLOUDFLARE_TOKEN','n8n':'ED_CRM_N8N_KEY','storage':'ED_CRM_STORAGE_SECRET','storage_access':'ED_CRM_STORAGE_ACCESS_KEY'}
ed_secrets.ENV.update(SECRET_NAMES)

def config(provider):
    if provider not in CATALOG:raise LookupError('Destino não encontrado.')
    with store.conectar() as con:r=con.execute('SELECT valor FROM ed_config WHERE chave=?',('destino:'+provider,)).fetchone()
    return json.loads(r['valor']) if r else CATALOG[provider]['padrao'].copy()

def fingerprint(provider):
    value=config(provider)
    secrets=ed_secrets.get(provider)+(ed_secrets.get('storage_access') if provider=='storage' else '')
    return hashlib.sha256((json.dumps(value,sort_keys=True)+secrets).encode()).hexdigest()

def status(provider):
    c=config(provider);present=bool(shutil.which('gh')) if provider=='github' and c['modo']=='cli' else bool(ed_secrets.get(provider))
    if provider=='storage':present=present and bool(ed_secrets.get('storage_access'))
    with store.conectar() as con:r=con.execute('SELECT valor FROM ed_config WHERE chave=?',('destino-prova:'+provider,)).fetchone()
    proof=json.loads(r['valor']) if r else {}
    matched=proof.get('fingerprint')==fingerprint(provider)
    return dict(id=provider,**CATALOG[provider],config=c,credencial_presente=present,estado=proof.get('estado') if matched else 'configurado_nao_validado' if present else 'sem_credencial',prova={k:v for k,v in proof.items() if k!='fingerprint'} if matched else {},ultima_execucao=proof.get('data') if matched else None,consumo=None)

def configure(provider,data):
    c=config(provider)
    if not isinstance(data,dict) or set(data)-set(c)-{'credencial','access_key','remover_credencial'}:raise ValueError('Campos de destino inválidos.')
    out={**c,**{k:store.texto(v,300) for k,v in data.items() if k in c}}
    if provider=='github':
        if out['modo'] not in ('cli','token'):raise ValueError('Escolha CLI ou token explicitamente.')
        if out['repositorio'] and not re.fullmatch(r'[A-Za-z0-9_.-]+/[A-Za-z0-9_.-]+',out['repositorio']):raise ValueError('Use organização/repositório.')
    if provider in ('cloudflare','storage'):
        if out['account_id'] and not re.fullmatch(r'[a-fA-F0-9]{32}',out['account_id']):raise ValueError('ID de conta precisa de 32 caracteres hexadecimais.')
    if provider=='cloudflare' and out['projeto'] and not re.fullmatch(r'[a-z0-9-]{1,63}',out['projeto']):raise ValueError('Nome de projeto Pages inválido.')
    if provider=='n8n':
        u=urlsplit(out['base_url'])
        if out['base_url'] and (u.scheme!='https' or not u.hostname or u.username or u.password or u.query or u.fragment or u.port not in (None,443)):raise ValueError('Use URL HTTPS sem credenciais, parâmetros ou portas especiais.')
        if out['workflow_id'] and not re.fullmatch(r'[A-Za-z0-9_-]{1,80}',out['workflow_id']):raise ValueError('ID de workflow inválido.')
        out['base_url']=out['base_url'].rstrip('/')
    if provider=='storage':
        if out['tipo'] not in ('r2','s3') or not re.fullmatch(r'[a-z0-9-]{1,30}',out['region']):raise ValueError('Tipo ou região inválida.')
        if out['bucket'] and (not re.fullmatch(r'[a-z0-9][a-z0-9.-]{1,61}[a-z0-9]',out['bucket']) or '..' in out['bucket']):raise ValueError('Nome de bucket inválido.')
    if type(data.get('remover_credencial',False)) is not bool:raise ValueError('Remoção precisa ser booleana.')
    if data.get('remover_credencial'):
        ed_secrets.put(provider,'')
        if provider=='storage':ed_secrets.put('storage_access','')
    elif data.get('credencial'):ed_secrets.put(provider,data['credencial'])
    if provider=='storage' and data.get('access_key'):ed_secrets.put('storage_access',data['access_key'])
    with store.conectar() as con:
        con.execute('INSERT INTO ed_config VALUES (?,?) ON CONFLICT(chave) DO UPDATE SET valor=excluded.valor',('destino:'+provider,json.dumps(out)))
        con.execute('DELETE FROM ed_config WHERE chave=?',('destino-prova:'+provider,))
    return status(provider)

def github_get(path,c):
    if c['modo']=='token':return request_json('GET','https://api.github.com/'+path.lstrip('/'),headers={'Authorization':'Bearer '+ed_secrets.get('github'),'Accept':'application/vnd.github+json','X-GitHub-Api-Version':'2026-03-10'},allow_list=True)
    executable=shutil.which('gh')
    if not executable:raise ValueError('Instale GitHub CLI oficial e execute gh auth login. Nenhuma conta trocada automaticamente.')
    try:r=subprocess.run([executable,'api',path],capture_output=True,text=True,encoding='utf-8',timeout=30,creationflags=getattr(subprocess,'CREATE_NO_WINDOW',0))
    except (OSError,subprocess.TimeoutExpired):raise ValueError('CLI GitHub não respondeu no prazo; confira login e rede.') from None
    if r.returncode:raise ValueError('GitHub CLI recusou a leitura; confira gh auth status, conta e permissões. Saída privada não registrada.')
    if len(r.stdout)>3_000_000:raise ValueError('Resposta GitHub acima do limite.')
    try:return json.loads(r.stdout)
    except ValueError:raise ValueError('GitHub retornou JSON inválido.') from None

def n8n_get(c):
    """DNS fixado antes de enviar a chave; sem redirects ou proxy do ambiente."""
    import urllib3,certifi
    from ed_enrich import destino
    if not c['base_url']:raise ValueError('Informe a URL HTTPS da instância n8n.')
    parsed,host,ip=destino(c['base_url']+'/api/v1/workflows?limit=20')
    pool=urllib3.HTTPSConnectionPool(ip,server_hostname=host,assert_hostname=host,cert_reqs='CERT_REQUIRED',ca_certs=certifi.where())
    try:
        with pool.request('GET',parsed.path+'?'+parsed.query,headers={'Host':host,'X-N8N-API-KEY':ed_secrets.get('n8n'),'Accept':'application/json','Accept-Encoding':'identity'},redirect=False,retries=False,timeout=urllib3.Timeout(connect=5,read=15),preload_content=False) as res:
            if res.status!=200:raise ValueError('n8n respondeu HTTP '+str(res.status)+'. Confira Public API, escopo e validade da API key; webhook usa outra autenticação.')
            raw=res.read(1_000_001)
            if len(raw)>1_000_000:raise ValueError('Resposta n8n acima do limite.')
            return json.loads(raw)
    except (urllib3.exceptions.HTTPError,ValueError) as exc:
        if isinstance(exc,ValueError) and not isinstance(exc,json.JSONDecodeError):raise
        raise ValueError('Falha de rede ou JSON inválido do n8n. Nenhuma automação executada.') from None
    finally:pool.close()

def test(provider):
    c=config(provider)
    if provider=='github':
        user=github_get('/user',c)
        if not isinstance(user,dict) or not isinstance(user.get('login'),str):raise ValueError('GitHub não confirmou a identidade.')
        repo=c['repositorio']
        rows=[github_get('/repos/'+repo,c)] if repo else github_get('/user/repos?per_page=100&sort=updated',c)
        if not isinstance(rows,list):raise ValueError('GitHub não retornou repositórios.')
        projects=[{'id':str(x['id']),'nome':x['full_name'],'privado':bool(x.get('private')),'escrita':bool(x.get('permissions',{}).get('push'))} for x in rows if isinstance(x,dict) and isinstance(x.get('full_name'),str) and 'id' in x]
        if repo and not any(x['nome'].casefold()==repo.casefold() for x in projects):raise ValueError('O serviço não confirmou o repositório selecionado.')
        return dict(conta=user['login'],recursos=projects,capacidade='repositorios_leitura',mensagem='Identidade e leitura de repositórios validadas. Escrita e publicação continuam pendentes de autorização específica.')
    if provider=='cloudflare':
        headers={'Authorization':'Bearer '+ed_secrets.get(provider)}
        account=c['account_id']
        if not account:
            data=request_json('GET','https://api.cloudflare.com/client/v4/accounts?per_page=50',headers=headers)
            if data.get('success') is not True or not isinstance(data.get('result'),list):raise ValueError('Cloudflare não confirmou as contas.')
            return dict(capacidade='contas_leitura',recursos=[{'id':x['id'],'nome':x['name']} for x in data['result']],mensagem='Contas consultadas. Selecione o ID da conta e teste Pages; projetos e publicação ainda não validados.')
        data=request_json('GET',f'https://api.cloudflare.com/client/v4/accounts/{account}/pages/projects?per_page=100',headers=headers)
        if data.get('success') is not True or not isinstance(data.get('result'),list):raise ValueError('Cloudflare não confirmou os projetos Pages.')
        projects=[{'id':x['id'],'nome':x['name'],'modo':'git' if x.get('source') else 'direct_upload'} for x in data['result'] if isinstance(x,dict) and 'id' in x and 'name' in x]
        if c['projeto'] and not any(x['nome']==c['projeto'] for x in projects):raise ValueError('Projeto selecionado não acessível nesta conta.')
        return dict(conta=account[:6]+'…'+account[-4:],recursos=projects,capacidade='pages_projetos_leitura',mensagem='Projetos Pages consultados e modalidade identificada. Nenhum deploy realizado; Flask/SQLite precisam de hospedagem própria.')
    if provider=='n8n':
        data=n8n_get(c)
        if not isinstance(data,dict) or not isinstance(data.get('data'),list):raise ValueError('n8n não confirmou a consulta de workflows.')
        workflows=[{'id':str(x['id']),'nome':x.get('name','Workflow'),'ativo':bool(x.get('active'))} for x in data['data'] if isinstance(x,dict) and 'id' in x]
        return dict(recursos=workflows,capacidade='workflows_leitura',mensagem='Public API respondeu e workflows foram consultados. Execução de webhook e conectividade com o CRM ainda não validadas.')
    from ed_remote_storage import test as test_storage
    return test_storage(c)

def run(app,ident):
    with app.app_context():
        job=ler_job(ident);provider=job['fornecedor'];fp=fingerprint(provider)
        job.update(estado='pesquisando',progresso=20,mensagem='Conferindo acesso e capacidade no fornecedor.')
        if not save_job(job):return
        try:
            if job.get('autor'):
                from ed_workflows import still_authorized
                g.actor=job['autor'];still_authorized({'autor':g.actor['id'],'workspace':g.actor['workspace']})
                if g.actor['papel']!='administrador':raise ValueError('A permissão de administrador deste teste foi revogada.')
            out=test(provider);job.update(estado='concluida',progresso=100,mensagem=out['mensagem'],resultado=out)
            proof=dict(estado='limitado',data=store.agora(),fingerprint=fp,**out)
        except Exception as exc:
            message=str(exc) if isinstance(exc,ValueError) else 'Falha do fornecedor. Configure o acesso e tente novamente; dados locais preservados.'
            job.update(estado='erro',progresso=100,mensagem=message);proof=dict(estado='erro',mensagem=message,data=store.agora(),fingerprint=fp)
        if save_job(job):
            with store.conectar() as con:con.execute('INSERT INTO ed_config VALUES (?,?) ON CONFLICT(chave) DO UPDATE SET valor=excluded.valor',('destino-prova:'+provider,json.dumps(proof)))

def registrar(bp):
    @bp.get('/destinos',endpoint='destinations_listing')
    def listing():return jsonify([status(x) for x in CATALOG])
    @bp.put('/destinos/<provider>',endpoint='destinations_settings')
    def settings(provider):return jsonify(configure(provider,request.get_json()))
    @bp.post('/destinos/<provider>/testar',endpoint='destinations_test')
    def testing(provider):
        config(provider)
        if not status(provider)['credencial_presente']:raise ValueError(CATALOG[provider]['acesso'])
        with lock,store.conectar() as con:
            jobs=[json.loads(r['dados']) for r in con.execute('SELECT dados FROM ed_operacoes')]
            if any(j['fornecedor']==provider and j['estado'] in ('na_fila','pesquisando') for j in jobs):raise ValueError('Já existe teste deste destino em andamento.')
            job=dict(id=store.novo_id(),fornecedor=provider,tipo='destino_teste',estado='na_fila',progresso=0,criado_em=store.agora(),mensagem='Teste real na fila; não publica nem envia mensagens.',autor=dict(getattr(g,'actor',{})))
            con.execute('INSERT INTO ed_operacoes VALUES (?,?)',(job['id'],json.dumps(job)))
        app=current_app._get_current_object()
        if app.config['RUN_JOBS']:submit(pool,run,app,job['id'])
        else:run(app,job['id'])
        return jsonify(ler_job(job['id'])),201
