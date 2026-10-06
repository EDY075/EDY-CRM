"""Fila durável por workspace, com checkpoints de domínio e efeitos identificados.

Um worker no processo limita concorrência. Não há execução com o computador
desligado. Reinício pausa trabalho sem repetir uma inferência ambígua.
"""
import json
import time
from concurrent.futures import ThreadPoolExecutor
from threading import RLock,Condition
from datetime import datetime, timezone, timedelta
from flask import current_app, g, jsonify, request
from werkzeug.exceptions import Conflict, Forbidden
import ed_store as store
from ed_workspace import submit

pool=ThreadPoolExecutor(max_workers=2,thread_name_prefix='edy-workflow')
lock=RLock()
writers=Condition(RLock())
projects_in_flight=set()
FINAL=('concluida','parcial','falhou','cancelada')

class Waiting(ValueError):pass

def setup():
    with store.conectar() as con:
        con.executescript('''CREATE TABLE IF NOT EXISTS ed_fluxos(id TEXT PRIMARY KEY,chave TEXT UNIQUE NOT NULL,dados TEXT NOT NULL);
          CREATE TABLE IF NOT EXISTS ed_chat(id TEXT PRIMARY KEY,dados TEXT NOT NULL);
          CREATE TABLE IF NOT EXISTS ed_rotinas(id TEXT PRIMARY KEY,dados TEXT NOT NULL);''')
        if current_app.config.get('RECOVER_JOBS',True):
            for row in con.execute('SELECT * FROM ed_fluxos').fetchall():
                job=json.loads(row['dados'])
                if job['estado'] in ('na_fila','executando'):
                    job.update(estado='pausada',mensagem='Servidor reiniciado. Retome os checkpoints; efeitos ambíguos exigem revisão.',atualizado_em=store.agora())
                    con.execute('UPDATE ed_fluxos SET dados=? WHERE id=?',(json.dumps(job,ensure_ascii=False),row['id']))

def get(ident):
    with store.conectar() as con:row=con.execute('SELECT dados FROM ed_fluxos WHERE id=?',(ident,)).fetchone()
    if not row:raise LookupError('Execução não encontrada neste workspace.')
    return json.loads(row['dados'])

def listing():
    with store.conectar() as con:rows=con.execute('SELECT dados FROM ed_fluxos ORDER BY rowid DESC LIMIT 100').fetchall()
    return [json.loads(r['dados']) for r in rows]

def write(job):
    job['atualizado_em']=store.agora()
    with store.conectar() as con:con.execute('UPDATE ed_fluxos SET dados=? WHERE id=?',(json.dumps(job,ensure_ascii=False),job['id']))

def patch(ident,**changes):
    with lock:
        job=get(ident);job.update(changes);write(job);return job

def check(ident):
    if get(ident)['estado']!='executando':raise InterruptedError()

def checkpoint(ident,index,**changes):
    with lock:
        check(ident);job=get(ident);job['etapas'][index].update(changes);write(job)

def start(plan,key=None,chat=None):
    from ed_tools import validate_plan,steps
    plan=validate_plan(plan)
    actor=dict(getattr(g,'actor',{}) or {'id':'local','workspace':'principal','papel':'administrador','modo':'local'})
    if actor['papel']=='leitura':raise Forbidden('Papel de leitura não pode executar ferramentas.')
    key=store.texto(key or store.novo_id(),100)
    if not key:raise ValueError('Chave de idempotência vazia.')
    with lock,store.conectar() as con:
        found=con.execute('SELECT dados FROM ed_fluxos WHERE chave=?',(key,)).fetchone()
        if found:return json.loads(found['dados'])
        if sum(x['estado'] in ('na_fila','executando') for x in listing())>=5:raise Conflict('Fila com cinco execuções. Aguarde ou cancele uma delas.')
        job=dict(id=store.novo_id(),estado='na_fila',mensagem='Aguardando worker local.',criado_em=store.agora(),atualizado_em=store.agora(),plano=plan,
          autor=actor['id'],papel=actor['papel'],workspace=actor['workspace'],chat_id=chat,etapas=[dict(nome=s,estado='pendente',tentativas=0,resultado=None) for s in steps(plan)],limites=dict(leads=plan.get('quantidade',1),previas=1,tentativas=2,timeout_etapa=1260,modelos=['gpt-6.1-sol'],envio=False,publicacao=False))
        con.execute('INSERT INTO ed_fluxos VALUES (?,?,?)',(job['id'],key,json.dumps(job,ensure_ascii=False)))
    dispatch(job)
    return get(job['id'])

def dispatch(job):
    app=current_app._get_current_object()
    if app.config['RUN_JOBS']:submit(pool,run,app,job['id'])

def still_authorized(job):
    if job['autor']=='local':
        from ed_access import connection
        with connection() as con:
            if con.execute('SELECT 1 FROM users LIMIT 1').fetchone():raise Forbidden('Acesso local substituído por usuários. Inicie uma nova execução autenticada.')
        return
    from ed_access import connection
    with connection() as con:
        row=con.execute('SELECT m.papel FROM memberships m JOIN users u ON u.id=m.user_id WHERE user_id=? AND workspace_id=? AND u.ativo=1',(job['autor'],job['workspace'])).fetchone()
    if not row or row['papel']=='leitura':raise Forbidden('A autorização da execução foi revogada.')
    # O papel capturado no início não concede privilégios após uma alteração.
    g.actor={**getattr(g,'actor',{}),'id':job['autor'],'workspace':job['workspace'],'papel':row['papel']}

def run(app,ident):
    """Um escritor por empresa; pesquisa sem empresa serializa o workspace."""
    with app.app_context():
        job=get(ident)
        if job['estado']!='na_fila':return
        workspace=str(store.pasta().resolve());company=job['plano'].get('empresa_id') or '*'
        key=(workspace,company)
        with writers:
            while any(w==workspace and (company=='*' or c=='*' or c==company) for w,c in projects_in_flight):
                if get(ident)['estado']!='na_fila':return
                writers.wait(.25)
            projects_in_flight.add(key)
        try:_run(app,ident)
        finally:
            with writers:projects_in_flight.discard(key);writers.notify_all()
            if job.get('chat_id'):
                from ed_assistant import conversation
                from ed_site_refinement import get as session_get, sync
                try:
                    context=conversation(job['chat_id'])['contexto']
                    if context.get('refinamento_site'):sync(session_get(context['empresa_id'],context['refinamento_site']))
                except (ValueError,LookupError,Conflict,Forbidden):app.logger.warning('Refinamento aguardando revisão: %s',ident)

def _run(app,ident):
    from ed_tools import execute_step
    with app.app_context():
        with lock:
            job=get(ident)
            if job['estado']!='na_fila':return
            job.update(estado='executando',mensagem='Executando etapas reais.');write(job)
        g.actor=dict(id=job['autor'],workspace=job['workspace'],papel=job['papel'],modo='worker')
        try:
            for i,step in enumerate(job['etapas']):
                check(ident);still_authorized(job)
                if step['estado']=='concluida':continue
                current=get(ident)['etapas'][i]
                if current['tentativas']>=2:raise Waiting('Limite de duas tentativas nesta etapa. Revise a dependência e inicie outro plano.')
                checkpoint(ident,i,estado='executando',tentativas=current['tentativas']+1,iniciado_em=store.agora())
                patch(ident,mensagem='Etapa: '+step['nome'])
                result=execute_step(get(ident),i)
                check(ident)
                checkpoint(ident,i,estado='concluida',resultado=result,concluido_em=store.agora())
            results=[s['resultado'] for s in get(ident)['etapas']]
            partial=any(isinstance(x,dict) and x.get('pendencias') for x in results)
            from ed_assistant import advance_project
            advance_project(get(ident))
            patch(ident,estado='parcial' if partial else 'concluida',mensagem='Resultados salvos. Há pendências para revisar.' if partial else 'Todas as etapas concluídas.',concluido_em=store.agora())
        except InterruptedError:return
        except Waiting as exc:patch(ident,estado='aguardando_dependencia',mensagem=str(exc))
        except Exception as exc:
            from ed_codex_transport import sanitize
            message=sanitize(str(exc)) if isinstance(exc,(ValueError,LookupError,Forbidden,Conflict)) else 'Falha interna. Resultados anteriores preservados; consulte o log local.'
            patch(ident,estado='falhou',mensagem=message)

def action(ident,action):
    with lock:
        job=get(ident)
        actor=getattr(g,'actor',{})
        if actor.get('id')!=job['autor'] and actor.get('papel')!='administrador':raise Forbidden('Somente autor ou administrador pode controlar esta execução.')
        if action=='pausar' and job['estado'] in ('na_fila','executando'):job.update(estado='pausada',mensagem='Pausada. Requisição em curso pode terminar; seu resultado será recuperado pelo ID.')
        elif action=='cancelar' and job['estado'] not in ('concluida','cancelada'):
            job.update(estado='cancelada',mensagem='Cancelamento cooperativo solicitado; resultados gravados permanecem disponíveis.')
            from ed_services import ler_job,save
            for step in job['etapas']:
                child=step.get('operacao_id')
                if not child:continue
                try:
                    operation=ler_job(child)
                    if operation['estado'] in ('na_fila','pesquisando'):
                        operation.update(estado='cancelada',mensagem='Fluxo cancelado; nenhuma nova escrita será aceita.');save(operation)
                except LookupError:
                    from ed_search import ler,acionar
                    try:
                        if ler(child)['estado'] in ('na_fila','pesquisando'):acionar(child,'cancelar',current_app._get_current_object())
                    except LookupError:pass
        elif action=='retomar' and job['estado'] in ('pausada','falhou','aguardando_dependencia','parcial','cancelada'):
            if all(s['estado']=='concluida' for s in job['etapas']):raise ValueError('Etapas já executadas. Revise as pendências na ficha; nenhuma duplicação será feita.')
            # A retomada passa a utilizar a autorização atual, nunca a identidade proposta pelo modelo.
            job.update(autor=actor.get('id','local'),papel=actor.get('papel','administrador'),estado='na_fila',mensagem='Retomada por checkpoints, sem repetir etapas concluídas.')
        else:raise ValueError('Ação indisponível neste estado.')
        write(job)
    if job['estado']=='na_fila':dispatch(job)
    return job

def wait_child(job,index,child,reader,timeout=1260):
    """ID persistido antes da espera; reinício não dispara outra chamada paga."""
    deadline=time.monotonic()+timeout
    while time.monotonic()<deadline:
        check(job['id']);value=reader(child)
        state=value['estado']
        if state in ('na_fila','pesquisando'):time.sleep(.3);continue
        if state in ('concluida','parcial','sem_resultados','bloqueada','dependente_js'):return value
        from ed_codex_transport import operation_issue
        if state in ('erro','interrompida') and operation_issue(value)=='execucao':
            raise ValueError('Execução interrompida por timeout, rede ou serviço; não é falta de credencial. '+value.get('mensagem','')+' Checkpoint e versões preservados. Retome explicitamente; nenhuma repetição automática.')
        raise Waiting('Operação '+child+' terminou em '+state+': '+value.get('mensagem','')+' Resultados mantidos; confira a operação antes de repetir.')
    raise Waiting('Prazo da etapa excedido. ID '+child+' preservado; retomada consulta a mesma operação.')

def registrar(bp):
    @bp.get('/fluxos',endpoint='fluxos_list')
    def fluxos_list():
        from ed_preview import workflow_links
        return jsonify([workflow_links(j) for j in listing()])
    @bp.get('/fluxos/<ident>',endpoint='fluxos_get')
    def fluxos_get(ident):
        from ed_preview import workflow_links
        return jsonify(workflow_links(get(ident)))
    @bp.post('/fluxos',endpoint='fluxos_create')
    def fluxos_create():
        data=request.get_json()
        if not isinstance(data,dict) or set(data)-{'plano','chave'}:raise ValueError('Contrato de execução inválido.')
        return jsonify(start(data.get('plano'),data.get('chave'))),202
    @bp.post('/fluxos/<ident>/<op>',endpoint='fluxos_action')
    def fluxos_action(ident,op):return jsonify(action(ident,op))
    @bp.get('/rotinas',endpoint='rotinas_list')
    def rotinas_list():
        with store.conectar() as con:return jsonify([json.loads(r['dados']) for r in con.execute('SELECT dados FROM ed_rotinas ORDER BY rowid DESC')])
    @bp.put('/rotinas/<ident>',endpoint='rotinas_save')
    @bp.post('/rotinas',endpoint='rotinas_create')
    def rotinas_save(ident=None):
        from ed_tools import validate_plan
        d=request.get_json()
        if not isinstance(d,dict) or set(d)-{'nome','intervalo_minutos','ativo','plano','condicao'}:raise ValueError('Rotina inválida.')
        interval=d.get('intervalo_minutos')
        if type(interval)!=int or not 60<=interval<=10080:raise ValueError('Intervalo de 60 minutos a 7 dias.')
        if d.get('condicao') not in ('sempre','sem_execucao_ativa'):raise ValueError('Condição inválida.')
        value=dict(id=ident or store.novo_id(),nome=store.texto(d.get('nome',''),120),intervalo_minutos=interval,ativo=store.booleano(d.get('ativo')),plano=validate_plan(d.get('plano')),condicao=d['condicao'],autor=g.actor['id'],workspace=g.actor['workspace'],papel=g.actor['papel'],proxima=store.agora(),gatilho='intervalo_com_processo_ativo')
        if not value['nome']:raise ValueError('Informe nome.')
        with store.conectar() as con:
            if ident:
                old=con.execute('SELECT dados FROM ed_rotinas WHERE id=?',(ident,)).fetchone()
                if not old:raise LookupError('Rotina não encontrada.')
                if json.loads(old['dados'])['autor']!=g.actor['id'] and g.actor['papel']!='administrador':raise Forbidden('Somente autor ou administrador pode editar a rotina.')
            con.execute('INSERT INTO ed_rotinas VALUES (?,?) ON CONFLICT(id) DO UPDATE SET dados=excluded.dados',(value['id'],json.dumps(value,ensure_ascii=False)))
        return jsonify(value),201

def tick():
    """Uma ocorrência identificada por horário; sem encadear automações."""
    with store.conectar() as con:rows=con.execute('SELECT dados FROM ed_rotinas').fetchall()
    for row in rows:
        routine=json.loads(row['dados'])
        if not routine['ativo'] or routine['proxima']>store.agora():continue
        g.actor=dict(id=routine['autor'],workspace=routine['workspace'],papel=routine['papel'],modo='rotina')
        try:
            still_authorized({**routine,'estado':'executando'})
            if routine['condicao']=='sem_execucao_ativa' and any(x['estado'] in ('na_fila','executando') for x in listing()):continue
            job=start(routine['plano'],'rotina:'+routine['id']+':'+routine['proxima'])
            routine.update(ultima_execucao=job['id'],erro='',proxima=(datetime.now(timezone.utc)+timedelta(minutes=routine['intervalo_minutos'])).isoformat(timespec='seconds'))
        except (ValueError,Forbidden,Conflict) as exc:routine.update(ativo=False,erro=str(exc))
        with store.conectar() as con:con.execute('UPDATE ed_rotinas SET dados=? WHERE id=?',(json.dumps(routine,ensure_ascii=False),routine['id']))

def start_scheduler(app):
    import threading
    if not app.config['RUN_JOBS']:return
    def loop():
        from ed_workspace import data_directory
        while True:
            with app.app_context():
                from ed_access import connection,directory
                with connection() as con:ids=[r[0] for r in con.execute('SELECT id FROM workspaces')]
                for ident in ids:
                    token=data_directory.set(directory(ident))
                    try:
                        tick()
                        from ed_site_refinement import tick as tick_refinement
                        tick_refinement()
                    except Exception:
                        app.logger.exception('Falha no scheduler EDY; nenhuma credencial registrada.')
                    finally:data_directory.reset(token)
            time.sleep(30)
    threading.Thread(target=loop,daemon=True,name='edy-rotinas').start()
