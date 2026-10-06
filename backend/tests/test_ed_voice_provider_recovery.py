"""Contratos simulados; não comprovam operação dos fornecedores externos."""
import json
from decimal import Decimal
import pytest
from test_ed_enrich import client

def test_zero_price_must_cover_every_tariff_and_budget_before_call(client,monkeypatch):
    import ed_creation_providers as p
    assert not p.free({'pricing':{'prompt':'0','completion':'0','web_search':'0.1'}})
    assert not p.free({'pricing':{'prompt':'0','completion':'0','unknown':'?'}})
    with client.application.app_context():
        monkeypatch.setattr(p,'config',lambda:{**p.DEFAULT,'permitir_pago':True,'limite_usd':0.001})
        with pytest.raises(ValueError,match='reservar'):p.budget({'pricing':{'prompt':'0.01','completion':'0.01'}},[{'content':'Texto'}],[])
        monkeypatch.setattr(p,'config',lambda:{**p.DEFAULT,'permitir_pago':True,'limite_usd':1})
        cost=p.budget({'pricing':{'prompt':'0.000001','completion':'0.000001'}},[{'content':'Texto'}],[])
        assert cost>Decimal('0.016')
        with pytest.raises(ValueError,match='Tarifas'):p.budget({'pricing':{'prompt':'0.000001','completion':'0','request':'0.01'}},[],[])

def test_classified_limit_handoff_and_no_paid_route(client,monkeypatch,tmp_path):
    import ed_runtime,ed_creation_providers as p
    from ed_codex_transport import RuntimeFailure
    monkeypatch.setattr(ed_runtime,'generate',lambda *a:(_ for _ in ()).throw(RuntimeFailure({'http_status':429,'code':'usageLimitExceeded'})))
    monkeypatch.setattr(p,'config',lambda:{**p.DEFAULT,'fallback_ordem':['openrouter']})
    monkeypatch.setattr(p,'status',lambda:{'openrouter':{'credencial_presente':True}})
    monkeypatch.setattr(p,'context',lambda *a:(tmp_path,{},'somente contexto deste lead',[]))
    monkeypatch.setattr(p,'ativo',lambda *a:None)
    calls=[]
    def alternative(job,progress,fallback=False):
        assert fallback is True;calls.append(job['id']);return {'modelo':'rota-zero','arquivos':['index.html']}
    monkeypatch.setattr(p,'router_generate',alternative)
    with client.application.app_context():
        result=p.generate({'id':'uma-versao','empresa_id':'um-lead','parametros':{}},lambda *a,**k:None)
    checkpoint=json.loads((tmp_path/'handoff-provedor.json').read_text(encoding='utf-8'))
    assert calls==['uma-versao'] and result['fallback']==checkpoint
    assert checkpoint['erro_anterior']['http_status']==429 and checkpoint['empresa_id']=='um-lead'

def test_account_update_waits_for_old_executor_and_keeps_secret_out_of_status(client,monkeypatch,tmp_path):
    import ed_native_account as n,ed_runtime,ed_store as store
    old=tmp_path/'runtime';old.mkdir();(old/'auth.json').write_text('{"tokens":{"access_token":"old-test"}}')
    source=tmp_path/'app-auth.json';source.write_text('{"tokens":{"access_token":"new-test"}}')
    monkeypatch.setattr(n,'source',lambda:source)
    monkeypatch.setattr(n,'native_identity',lambda path:{'identificador':'A' if path==old/'auth.json' and 'old-test' in path.read_text() else 'B','rotulo':'mascarada'})
    monkeypatch.setattr(ed_runtime,'private_native_cache',lambda *a:None)
    with client.application.app_context():
        n.save({'ativo':True,'estado':'conectado'})
        key=str(old.resolve());n.active[key]=1
        assert n.reconcile(old)['estado']=='aguardando_checkpoint'
        assert 'old-test' in (old/'auth.json').read_text()
        n.leave(key)
        cfg=n.reconcile(old)
        assert cfg['estado']=='conta_atualizada_nao_validada' and cfg['de']=='A' and cfg['para']=='B'
        assert 'new-test' in (old/'auth.json').read_text()
        assert 'new-test' not in json.dumps(cfg)
        assert cfg['troca_real_validada'] is False


def test_same_account_new_session_waits_and_never_reverts_newer_cache(client,monkeypatch,tmp_path):
    import ed_native_account as n,ed_runtime
    old=tmp_path/'runtime';old.mkdir();target=old/'auth.json'
    source=tmp_path/'app-auth.json'
    def auth(token,date):return json.dumps({'last_refresh':date,'tokens':{'access_token':token}})
    target.write_text(auth('old-fixture','2026-10-05T12:00:00Z'))
    source.write_text(auth('new-fixture','2026-10-05T13:00:00Z'))
    monkeypatch.setattr(n,'source',lambda:source)
    monkeypatch.setattr(n,'native_identity',lambda path:{'identificador':'same-account','rotulo':'mascarada'})
    monkeypatch.setattr(ed_runtime,'private_native_cache',lambda *a:None)
    with client.application.app_context():
        n.save({'ativo':True,'estado':'erro','verificacao_id':'old-failed-test'})
        key=str(old.resolve());n.active[key]=1
        assert n.reconcile(old)['estado']=='aguardando_checkpoint'
        assert 'old-fixture' in target.read_text()
        n.leave(key)
        cfg=n.reconcile(old)
        assert cfg['evento']=='sessao_renovada_mesma_conta' and cfg['verificacao_id'] is None
        assert cfg['de']==cfg['para']=='same-account' and not cfg['troca_real_validada']
        assert 'new-fixture' not in json.dumps(cfg)
        target.write_text(auth('runtime-newer-fixture','2026-10-05T14:00:00Z'))
        n.reconcile(old)
        assert 'runtime-newer-fixture' in target.read_text()

def test_refinement_copies_application_db_without_copying_session_secret(client,monkeypatch,tmp_path):
    import sqlite3,ed_runtime,ed_projects
    root=tmp_path/'new';root.mkdir();source=tmp_path/'old';(source/'data/uploads').mkdir(parents=True)
    with sqlite3.connect(source/'data/site.db') as con:con.executescript("CREATE TABLE teste(valor TEXT);INSERT INTO teste VALUES('persistente');")
    (source/'data/session.key').write_text('segredo apenas do ambiente antigo')
    monkeypatch.setattr(ed_runtime,'artefact_root',lambda *a:source)
    monkeypatch.setattr(ed_projects,'ler_job',lambda *a:{'empresa_id':'empresa-a','estado':'concluida'})
    ed_projects.attach_backend(root,{'id':'new','empresa_id':'empresa-a','parametros':{'anterior':'old'}})
    with sqlite3.connect(root/'data/site.db') as con:assert con.execute('SELECT valor FROM teste').fetchone()[0]=='persistente'
    assert not (root/'data/session.key').exists()

def test_voice_not_retained_is_cleaned_after_interruption(client):
    import ed_store as store
    with client.application.app_context():
        path=store.pasta()/'voz';path.mkdir(exist_ok=True);(path/'qa.wav').write_bytes(b'QA')
        with store.conectar() as con:con.execute('INSERT INTO ed_operacoes VALUES (?,?)',('qa-clean',json.dumps({'id':'qa-clean','tipo':'voice_transcription','estado':'pesquisando','parametros':{'arquivo':'qa.wav','manter_audio':False}})))
        store.preparar()
        assert not (path/'qa.wav').exists()

def test_completed_refinement_advances_chat_unless_user_changed_version(client,monkeypatch):
    import ed_assistant as a,ed_services
    company=client.post('/api/ed/empresas',json={'nome':'QA versões'}).json['id']
    chat=client.post('/api/ed/assistente/conversas',json={'empresa_id':company}).json
    version={'id':'nova','empresa_id':company,'estado':'concluida','resultado':{'escopo':'completo'}}
    monkeypatch.setattr(ed_services,'ler_job',lambda *args:version)
    flow={'chat_id':chat['id'],'plano':{'construcao_id':'anterior'},'etapas':[{'nome':'refinar','estado':'concluida','resultado':{'construcao_id':'nova'}},{'nome':'verificar','estado':'concluida','resultado':{'url':'http://127.0.0.1:5133/'}}]}
    with client.application.app_context():
        chat['contexto']['construcao_id']='anterior';a.save(chat);a.advance_project(flow)
        assert a.conversation(chat['id'])['contexto']['construcao_id']=='nova'
        chat['contexto']['construcao_id']='escolha-manual';a.save(chat);a.advance_project(flow)
        assert a.conversation(chat['id'])['contexto']['construcao_id']=='escolha-manual'

def test_cancel_parent_cancels_only_active_child_and_keeps_finished(client):
    import ed_workflows as w,ed_services,ed_store as store
    company=client.post('/api/ed/empresas',json={'nome':'QA cancelamento'}).json['id']
    parent=client.post('/api/ed/fluxos',json={'plano':{'acao':'preparar','empresa_id':company}}).json
    with client.application.app_context():
        for ident,state in [('active','pesquisando'),('finished','concluida')]:
            with store.conectar() as con:con.execute('INSERT INTO ed_operacoes VALUES (?,?)',(ident,json.dumps({'id':ident,'empresa_id':company,'tipo':'codex_construcao','estado':state,'parametros':{}})))
        value=w.get(parent['id']);value['etapas'][0]['operacao_id']='finished';value['etapas'][1]['operacao_id']='active';w.write(value)
    assert client.post('/api/ed/fluxos/'+parent['id']+'/cancelar').json['estado']=='cancelada'
    with client.application.app_context():
        assert ed_services.ler_job('active')['estado']=='cancelada'
        assert ed_services.ler_job('finished')['estado']=='concluida'

def test_refinement_refreshes_context_before_execution():
    from ed_tools import steps
    assert steps({'acao':'refinar'})==['exportar','refinar','verificar','prospeccao']

def test_parallel_workers_never_write_same_company_together(client,monkeypatch):
    import threading,time,ed_workflows as w
    one=client.post('/api/ed/empresas',json={'nome':'QA empresa um'}).json['id']
    two=client.post('/api/ed/empresas',json={'nome':'QA empresa dois'}).json['id']
    jobs=[client.post('/api/ed/fluxos',json={'plano':{'acao':'preparar','empresa_id':c}}).json for c in (one,one,two)]
    first=threading.Event();other=threading.Event();release=threading.Event();started=[];guard=threading.Lock()
    def execute(app,ident):
        company=w.get(ident)['plano']['empresa_id']
        with guard:started.append(ident)
        if ident==jobs[0]['id']:first.set();assert release.wait(5)
        if company==two:other.set()
        w.patch(ident,estado='concluida')
    monkeypatch.setattr(w,'_run',execute)
    threads=[threading.Thread(target=w.run,args=(client.application,j['id'])) for j in jobs]
    threads[0].start();assert first.wait(3)
    threads[1].start();threads[2].start();assert other.wait(3)
    assert jobs[1]['id'] not in started
    release.set()
    for thread in threads:thread.join(5);assert not thread.is_alive()
    assert set(started)=={j['id'] for j in jobs}
    assert not w.projects_in_flight

def test_prospect_respects_confirmed_website_instead_of_calling_it_candidate(client,monkeypatch):
    import ed_tools as t,ed_store as store
    lead=client.post('/api/ed/empresas',json={'nome':'QA site confirmado','site':'https://example.org/','confirmado':True}).json
    with client.application.app_context():
        value=store.ler_empresa(lead['id']);value['associacao_site']['estado']='confirmado'
        value['fontes']['site']['verificacao']='confirmado_usuario'
        monkeypatch.setattr(t.store,'ler_empresa',lambda *args:value)
        text=t.prospect(lead['id'])['whatsapp']
        assert 'site associado e confirmado' in text and 'site candidato' not in text

def test_legacy_prospect_never_exposes_a_reused_local_port(monkeypatch):
    import ed_preview as p
    monkeypatch.setattr(p,'active_url',lambda *args:None)
    flow={'plano':{'empresa_id':'lead'},'etapas':[{'nome':'prospeccao','resultado':{'whatsapp':'Prévia http://127.0.0.1:5131/ não publicada.'}}]}
    value=p.workflow_links(flow)['etapas'][0]['resultado']
    assert '5131' not in value['whatsapp'] and 'inativa' in value['whatsapp']
