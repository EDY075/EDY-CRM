"""Contratos locais: os fornecedores são mocks explicitamente, sem validar acesso real."""
import io,json,zipfile,hashlib
import pytest
from PIL import Image
from werkzeug.exceptions import Conflict
from test_ed_enrich import client
from test_ed_adaptive import lead
from test_ed_adaptive_build import reviewed

def png(color='orange'):
    out=io.BytesIO();Image.new('RGB',(120,240),color).save(out,'PNG');return out.getvalue()

def upload(client,c,section='pagina',color='orange'):
    r=client.post('/api/ed/empresas/'+c+'/estudio/importar',data={'arquivo':(io.BytesIO(png(color)),'candidata.png'),'uso_referencia':'true','secao_id':section})
    assert r.status_code==201,r.json
    return r.json

def state(client,c):return client.get('/api/ed/empresas/'+c+'/estudio').json

def payload(v):return {k:v[k] for k in ('revisao','secoes','quantidade','modo')}|{'direcao':{k:x for k,x in v['direcao'].items() if k not in ('versao','estado')}}

def approved(client,c):
    d=reviewed(client,c);v=upload(client,c)
    s=state(client,c);s=client.post('/api/ed/empresas/'+c+'/estudio/escolher',json={'revisao':s['revisao'],'variante_id':v['id']}).json
    a=client.post('/api/ed/empresas/'+c+'/estudio/aprovar',json={'revisao':s['revisao'],'brief_versao':d['versao'],'confirmar':True})
    assert a.status_code==201,a.json
    return d,a.json,v

def test_candidates_never_approve_or_create_html_and_block_shortcut(client):
    c=lead(client,'Visual piloto')['id'];d=reviewed(client,c)
    v=upload(client,c);s=state(client,c)
    assert s['quantidade']==3 and s['escolhas']=={} and s['aprovacoes']==[]
    assert v['origem']=='importacao_externa'
    r=client.post('/api/ed/empresas/'+c+'/adaptativo/construir',json={'versao':d['versao'],'projeto_id':'','chave':'unapproved'})
    assert r.status_code==409,r.json
    from ed_visual_studio import assert_package
    with client.application.app_context():
        with pytest.raises(Conflict):assert_package(c,{'briefing.md':'sem composição'})

def test_approval_is_immutable_portable_and_sent_to_existing_pipeline(client,tmp_path):
    c=lead(client,'Escolha piloto')['id'];d,a,v=approved(client,c)
    build=client.post('/api/ed/empresas/'+c+'/adaptativo/construir',json={'versao':d['versao'],'projeto_id':'','chave':'visual-click','composicao_id':a['id']})
    assert build.status_code==202,build.json
    chat=client.get('/api/ed/assistente/conversas/'+build.json['chat_id']).json
    assert chat['contexto']['composicao_visual']==a
    assert chat['contexto']['brief_adaptativo']['dossier']['proposta']['objetivo']=='Decisão manual exclusiva'
    assert client.get('/api/ed/empresas/'+c+'/estudio/conversas').json[0]['id']==chat['id']
    export=client.get('/api/ed/empresas/'+c).json['exportacoes'][0]
    from ed_visual_studio import assert_package
    with zipfile.ZipFile(io.BytesIO(client.get(export['zip_url']).data)) as z:
        z.extractall(tmp_path/'outro-diretorio')
        docs={n:z.read(n).decode() for n in z.namelist() if n.endswith(('.md','.json'))}
        snap=json.loads(docs['composicao-aprovada.json']);item=snap['montagem'][0]
        assert not item['arquivo'].startswith(('/', 'C:', 'D:'))
        assert hashlib.sha256(z.read(item['arquivo'])).hexdigest()==v['sha256']
        assert 'Reconstruir com HTML' in docs['DIRECAO-VISUAL.md']
        with client.application.app_context():
            assert assert_package(c,docs)['id']==a['id']
            for field,change in [('arquivo','referencias/falso.png'),('secao',{'id':'fake'})]:
                altered=json.loads(docs['composicao-aprovada.json']);altered['montagem'][0][field]=change
                with pytest.raises(Conflict):assert_package(c,{**docs,'composicao-aprovada.json':json.dumps(altered)})
    another=upload(client,c,color='brown');s=state(client,c)
    client.post('/api/ed/empresas/'+c+'/estudio/escolher',json={'revisao':s['revisao'],'variante_id':another['id']})
    assert state(client,c)['aprovacoes'][0]==a
    r=client.post('/api/ed/empresas/'+c+'/adaptativo/construir',json={'versao':d['versao'],'projeto_id':'','chave':'changed','composicao_id':a['id']})
    assert r.status_code==409
    assert client.post('/api/ed/empresas/'+c+'/adaptativo/construir',json={'versao':d['versao'],'projeto_id':'','chave':'visual-click','composicao_id':a['id']}).json==build.json

def test_direction_and_copy_changes_preserve_history_and_stale_variants(client):
    c=lead(client,'Direção')['id'];v=upload(client,c);s=state(client,c);p=payload(s)
    p['secoes'][0]['texto']='Decisão manual de uma seção'
    r=client.put('/api/ed/empresas/'+c+'/estudio',json=p)
    assert r.status_code==200,r.json
    now=r.json
    assert now['direcao']['versao']==2 and now['historico_direcao'][0]['direcao']['versao']==1
    assert now['variantes'][0]==v
    assert client.post('/api/ed/empresas/'+c+'/estudio/escolher',json={'revisao':now['revisao'],'variante_id':v['id']}).status_code==409
    assert client.put('/api/ed/empresas/'+c+'/estudio',json=p).status_code==409

def test_foreign_variants_jobs_and_malformed_upload_rejected(client):
    a=lead(client,'A')['id'];b=lead(client,'B')['id'];v=upload(client,a)
    assert client.get('/api/ed/empresas/'+b+'/estudio/variantes/'+v['id']+'/arquivo').status_code==404
    assert client.post('/api/ed/empresas/'+b+'/estudio/escolher',json={'revisao':0,'variante_id':v['id']}).status_code==404
    r=client.post('/api/ed/empresas/'+a+'/estudio/importar',data={'arquivo':(io.BytesIO(b'html'),'bad.png'),'uso_referencia':'true'})
    assert r.status_code==400 and len(state(client,a)['variantes'])==1
    assert client.post('/api/ed/empresas/'+a+'/estudio/aprovar',json={'revisao':1,'brief_versao':0,'confirmar':False}).status_code==400

def test_partial_generation_resume_is_idempotent_and_never_selects(client,monkeypatch):
    import ed_visual_providers as providers
    c=lead(client,'Três alternativas')['id'];calls=[]
    def generate(job,prompt,progress):
        calls.append(prompt)
        if len(calls)==2:raise ValueError('HTTP 429 encerrado — mock de limite')
        return png(['orange','white','brown'][len(job['parametros'].get('concluidas',[]))]),{'fornecedor':'mock_de_teste','modelo':'mock','consumo':None}
    monkeypatch.setattr(providers,'generate_image',generate)
    request={'revisao':0,'secao_id':'pagina','quantidade':3,'fornecedor':'codex_nativo','instrucoes':'Mudar composição','origem_id':'','chave':'batch'}
    url='/api/ed/empresas/'+c+'/estudio/gerar';r=client.post(url,json=request)
    assert r.status_code==202 and r.json['estado']=='erro'
    assert len(r.json['parametros']['concluidas'])==1
    assert client.post(url,json=request).json['id']==r.json['id'] and len(calls)==2
    assert client.post(url,json={**request,'instrucoes':'diferente'}).status_code==409
    assert client.post('/api/ed/empresas/'+c+'/estudio/operacoes/'+r.json['id']+'/retomar',json={}).json['estado']=='concluida'
    assert len(calls)==4 and len(state(client,c)['variantes'])==3
    assert state(client,c)['escolhas']=={} and state(client,c)['aprovacoes']==[]
    assert len({v['sha256'] for v in state(client,c)['variantes']})==3
    assert all(v['direcao_versao']==1 for v in state(client,c)['variantes'])
    from ed_app import criar_app
    restarted=criar_app({'TESTING':True,'DATA_DIR':client.application.config['DATA_DIR'],'RUN_JOBS':False})
    assert restarted.test_client().get('/api/ed/empresas/'+c+'/estudio').json==state(client,c)

def test_gateway_and_price_guards_do_not_claim_paid_is_free(client,monkeypatch):
    import ed_visual_providers as p
    for value in ('https://example.org/v1','http://127.0.0.1:20128/v1?key=x','http://user:pass@localhost:20128/v1','http://127.0.0.1:80/v1'):
        with pytest.raises(ValueError):p.gateway_base(value)
    assert p.gateway_base('http://127.0.0.1:20128/v1')
    assert not p.zero({'pricing':[]}) and not p.zero({'pricing':{'prompt':'0.01'}})
    with client.application.app_context():
        monkeypatch.setattr(p.ed_secrets,'get',lambda _: '')
        with pytest.raises(ValueError,match='sem chave'):p.ready('gateway')
        p.record('codex_nativo',{'estado':'operacao_real_validada','operacao':'imagem','turn_id':'completed-test'})
        p.record('codex_nativo',{'estado':'configurado_nao_validado','operacao':'catalogo'})
        assert p.status()['conexoes']['codex_nativo']['ultima_operacao_real']['turn_id']=='completed-test'


@pytest.mark.parametrize('mode',['completed','failed','no_image','bad_bytes'])
def test_native_image_requires_bytes_and_terminal_success(client,monkeypatch,mode):
    import ed_runtime,ed_tasks,ed_visual_providers as p
    from ed_visual_studio import cached_response
    import base64
    c=lead(client,'Streaming imagem mock')['id'];closed=[]
    events=[]
    if mode!='no_image':events.append({'method':'item/completed','params':{'threadId':'thread-mock','turnId':'turn-mock','item':{'type':'imageGeneration','status':'completed','result':base64.b64encode(png() if mode!='bad_bytes' else b'not-an-image').decode()}}})
    events.append({'method':'turn/completed','params':{'threadId':'thread-mock','turn':{'id':'turn-mock','status':'failed' if mode=='failed' else 'completed'}}})
    class RPC:
        audit={'versao':'mock-explicito'}
        def __init__(self,*a):pass
        def login(self,*a):return {}
        def call(self,method,args):return {'imageGeneration':True} if method=='modelProvider/capabilities/read' else {'thread':{'id':'thread-mock'}} if method=='thread/start' else {'turn':{'id':'turn-mock'}}
        def receive(self,*a):return events.pop(0)
        def close(self):closed.append(True)
    monkeypatch.setattr(ed_runtime,'RPC',RPC);monkeypatch.setattr(ed_tasks,'ativo',lambda _:None)
    job={'id':'f'*32,'empresa_id':c,'parametros':{'referencias':[],'concluidas':[],'assinatura':'mock'}}
    with client.application.app_context():
        if mode=='completed':
            raw,details=p.native_image(job,'prompt mock',lambda *a,**k:None)
            assert raw==png() and details['turn_id']=='turn-mock'
            assert cached_response(job)[0]==raw
            assert p.status()['conexoes']['codex_nativo']['ultima_operacao_real']['turn_id']=='turn-mock'
        else:
            with pytest.raises(ValueError):p.native_image(job,'prompt mock',lambda *a,**k:None)
            assert cached_response(job) is None
            assert not p.status()['conexoes']['codex_nativo'].get('ultima_operacao_real')
    assert closed==[True]


def test_paid_image_reservation_blocks_third_call_and_nested_fallback(client,monkeypatch):
    import base64,ed_tasks,ed_visual_providers as p
    c=lead(client,'Orçamento mock')['id'];sent=[]
    monkeypatch.setattr(p,'ready',lambda _:None)
    model={'id':'image-model','architecture':{'output_modalities':['image']}}
    monkeypatch.setattr(p,'catalog',lambda *a,**k:[model])
    def call(provider,method,path,payload=None,**kw):
        if path.endswith('/endpoints'):return {'endpoints':[{'provider_tag':'concrete','pricing':[{'cost_usd':'0.02','unit':'image','billable':'output_image'}]}]}
        sent.append(payload)
        return {'data':[{'b64_json':base64.b64encode(png()).decode()}],'usage':{'cost':0.02}}
    monkeypatch.setattr(p,'call',call);monkeypatch.setattr(ed_tasks,'ativo',lambda _:None)
    cfg={**p.DEFAULT,'politica':'menor_custo','permitir_pago':True,'limite_usd':0.05,'modelo_imagens_openrouter':'image-model'}
    job={'id':'a'*32,'empresa_id':c,'fornecedor':'openrouter','parametros':{'politica':cfg,'quantidade':3,'referencias':[],'concluidas':[],'assinatura':'mock'}}
    with client.application.app_context():
        for i in range(2):p.generate_image(job,'mock',lambda *a,**k:None);job['parametros']['concluidas'].append(str(i))
        with pytest.raises(ValueError,match='excede o orçamento'):p.generate_image(job,'mock',lambda *a,**k:None)
        with pytest.raises(ValueError,match='tarifa verificável'):p.image_endpoint(model,{**cfg,'politica':'so_gratuitos'},0)
    assert len(sent)==2 and all(x['provider']=={'allow_fallbacks':False,'only':['concrete']} for x in sent)


def test_checkpoint_recovers_saved_variant_without_duplicate_provider_call(client,monkeypatch):
    import ed_visual_studio as s,ed_tasks,ed_visual_providers as p
    c=lead(client,'Crash depois de gravar mock')['id'];v=state(client,c)
    job={'id':'b'*32,'empresa_id':c,'fornecedor':'codex_nativo','parametros':{'snapshot':v,'secao_id':'pagina','instrucoes':'mock','quantidade':1,'concluidas':[],'referencias':[],'assinatura':'mock'}}
    monkeypatch.setattr(ed_tasks,'ativo',lambda _:None)
    monkeypatch.setattr(p,'generate_image',lambda *a:(_ for _ in ()).throw(AssertionError('Não repetir chamada concluída')))
    with client.application.app_context():
        first=s.add_variant(c,'','pagina',png(),{'operacao_id':job['id'],'indice':0,'titulo':'Mock salvo antes do crash'})
        result=s.generate_worker(job,lambda *a,**k:None)
    assert result['variantes']==[first['id']] and len(state(client,c)['variantes'])==1


def test_external_executor_checks_portable_approval_and_archive_hash(client,tmp_path):
    import ed_creation_providers as provider,ed_store as store
    c=lead(client,'Pacote de fornecedor alternativo mock')['id'];d,a,v=approved(client,c)
    client.post('/api/ed/empresas/'+c+'/adaptativo/construir',json={'versao':d['versao'],'projeto_id':'','chave':'external-context','composicao_id':a['id']})
    export=client.get('/api/ed/empresas/'+c).json['exportacoes'][0]
    job={'id':'c'*32,'empresa_id':c,'parametros':{'exportacao_id':export['id'],'instrucoes':'mock'}}
    with client.application.app_context():
        root,docs,prompt,images=provider.context(job)
        assert images[0][0].name=='composicao-'+v['id']+'.png'
        assert json.loads(docs['composicao-aprovada.json'])['id']==a['id']
        path=store.arquivo_seguro('exportacoes',c+'/'+export['id']+'/pacote.zip')
        with zipfile.ZipFile(path) as archive:entries={n:archive.read(n) for n in archive.namelist()}
        entries['referencias/composicao-'+v['id']+'.png']=png('black')
        with zipfile.ZipFile(path,'w') as archive:
            for n,raw in entries.items():archive.writestr(n,raw)
        with pytest.raises(ValueError,match='Pacote alterado'):provider.context(job)


def test_visual_config_requires_admin_and_workspace_leads_stay_isolated(client):
    from test_ed_access import activate
    c=lead(client,'Empresa do workspace principal')['id'];upload(client,c)
    headers=activate(client)
    second=client.post('/api/ed/acesso/workspaces',headers=headers,json={'nome':'Outro workspace'}).json
    client.post('/api/ed/acesso/workspace',headers=headers,json={'id':second['id']})
    assert client.get('/api/ed/empresas/'+c+'/estudio').status_code==404
    client.post('/api/ed/acesso/workspace',headers=headers,json={'id':'principal'})
    client.post('/api/ed/acesso/usuarios',headers=headers,json={'nome':'operador visual','senha':'senha local operador segura','papel':'operador'})
    client.post('/api/ed/acesso/sair',headers=headers)
    client.post('/api/ed/acesso/login',json={'nome':'operador visual','senha':'senha local operador segura'})
    op={'X-EDY-CSRF':client.get('/api/ed/acesso/sessao').json['csrf']}
    assert client.put('/api/ed/provedores/visual/config',headers=op,json={'limite_usd':10}).status_code==403
    assert client.put('/api/ed/provedores/visual/config/gateway-painel',headers=op,json={'valor':'password-test-only'}).status_code==403


@pytest.mark.parametrize('mode',[401,403,429,'timeout','network','array'])
def test_provider_errors_keep_http_request_id_and_never_mark_operation(client,monkeypatch,mode):
    import requests,ed_visual_providers as p
    from ed_codex_transport import RuntimeFailure
    class Response:
        status_code=mode if isinstance(mode,int) else 200
        headers={'x-request-id':'request-mock'}
        def __enter__(self):return self
        def __exit__(self,*a):pass
        def iter_content(self,*a):yield json.dumps([] if mode=='array' else {'error':{'message':'Erro simulado do fornecedor'}}).encode()
    class Session:
        def __enter__(self):return self
        def __exit__(self,*a):pass
        def request(self,*a,**kw):
            if mode=='timeout':raise requests.Timeout()
            if mode=='network':raise requests.ConnectionError()
            return Response()
    monkeypatch.setattr(p.requests,'Session',Session);monkeypatch.setattr(p.ed_secrets,'get',lambda _: 'mock-key-not-real')
    with client.application.app_context():
        with pytest.raises(RuntimeFailure) as failure:p.call('openrouter','POST','/images',{})
        if isinstance(mode,int):assert failure.value.diagnostic['http_status']==mode and failure.value.diagnostic['request_id']=='request-mock'
        assert not p.status()['conexoes']['openrouter'].get('ultima_operacao_real')


def test_manual_selection_survives_restart_without_becoming_approval(client):
    from ed_app import criar_app
    c=lead(client,'Seleção persistente mock')['id'];v=upload(client,c)
    chosen=client.post('/api/ed/empresas/'+c+'/estudio/escolher',json={'revisao':1,'variante_id':v['id']}).json
    restarted=criar_app({'TESTING':True,'DATA_DIR':client.application.config['DATA_DIR'],'RUN_JOBS':False,'RECOVER_JOBS':False})
    saved=restarted.test_client().get('/api/ed/empresas/'+c+'/estudio').json
    assert saved==chosen and saved['escolhas']=={'pagina':v['id']} and saved['aprovacoes']==[]


def test_changed_library_context_requires_new_approval_and_preserves_old_snapshot(client,monkeypatch):
    import ed_library
    c=lead(client,'Contexto aprovado mock')['id'];d,a,v=approved(client,c)
    original=ed_library.resolve
    def changed(*args,**kwargs):
        context=original(*args,**kwargs)
        return {**context,'snapshot':context['snapshot']+[{'id':'reference-test','versao':2,'sha256':'changed-mock','tipo':'referencia'}]}
    monkeypatch.setattr(ed_library,'resolve',changed)
    response=client.post('/api/ed/empresas/'+c+'/adaptativo/construir',json={'versao':d['versao'],'projeto_id':'','chave':'changed-library','composicao_id':a['id']})
    assert response.status_code==409,response.json
    assert 'contexto' in response.json['erro'].lower()
    assert state(client,c)['aprovacoes'][0]==a
    assert client.get('/api/ed/empresas/'+c).json['exportacoes']==[]


def test_native_image_proof_belongs_to_validated_account_and_remains_history_on_switch(client,monkeypatch):
    import ed_visual_providers as p,ed_codex_oauth
    monkeypatch.setattr(ed_codex_oauth,'native_identity',lambda _: {'identificador':'conta-A-mock'})
    with client.application.app_context():
        p.record('codex_nativo',{'estado':'operacao_real_validada','operacao':'imagem','turn_id':'completed-A-mock','conta_id':'conta-A-mock'})
        assert p.status()['conexoes']['codex_nativo']['estado']=='operacao_real_validada'
        monkeypatch.setattr(ed_codex_oauth,'native_identity',lambda _: {'identificador':'conta-B-mock'})
        changed=p.status()['conexoes']['codex_nativo']
        assert changed['estado']=='acesso_nao_validado'
        assert changed['ultima_operacao_real']['turn_id']=='completed-A-mock'
        assert changed['ultima_operacao_real']['conta_id']=='conta-A-mock'
        assert 'conta' in changed['mensagem'].lower()
