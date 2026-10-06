from ed_workspace import submit
"""Jobs por empresa: cancelamento, deduplicação e nenhuma escrita tardia."""
import json
from flask import current_app,g
import ed_store as store
from ed_services import pool, lock, ler_job, save
from concurrent.futures import ThreadPoolExecutor
voice_pool=ThreadPoolExecutor(max_workers=1,thread_name_prefix='edy-voz')
running=set()


def iniciar(provider, kind, company, parameters, worker, idempotency_key=None):
    if company:store.ler_empresa(company)
    elif kind not in ('chat_interpretacao','visual_reference','voice_transcription','voice_install','codex_conta_verificacao'):raise ValueError('Esta operação exige uma empresa.')
    with lock, store.conectar() as con:
        for row in con.execute('SELECT dados FROM ed_operacoes'):
            job=json.loads(row['dados'])
            if idempotency_key and job.get('chave')==idempotency_key:return job
            if kind!='voice_transcription' and job.get('empresa_id')==company and job.get('tipo')==kind and job['estado'] in ('na_fila','pesquisando'):
                raise ValueError('Já existe uma operação equivalente em andamento. Aguarde ou cancele.')
        job=dict(id=store.novo_id(),empresa_id=company,fornecedor=provider,tipo=kind,estado='na_fila',progresso=0,
                 mensagem='Aguardando execução.',criado_em=store.agora(),parametros=parameters,chave=idempotency_key,autor=dict(getattr(g,'actor',{}) or {}))
        con.execute('INSERT INTO ed_operacoes VALUES (?,?)',(job['id'],json.dumps(job,ensure_ascii=False)))
    app=current_app._get_current_object()
    if app.config['RUN_JOBS']: submit(voice_pool if kind in ('voice_transcription','voice_install') else pool,executar,app,job['id'],worker)
    else: executar(app,job['id'],worker)
    return ler_job(job['id'])


def executar(app,ident,worker):
    with lock:
        if ident in running:return
        running.add(ident)
    try:return _executar(app,ident,worker)
    finally:
        with lock:running.discard(ident)

def _executar(app,ident,worker):
    with app.app_context():
        job=ler_job(ident)
        if job['estado']!='na_fila': return
        if job.get('autor'):g.actor=job['autor']
        job.update(estado='pesquisando',progresso=10,mensagem='Preparando operação.')
        if not save(job): return
        def progress(stage,message,**partial):
            job.update(progresso=stage,mensagem=message,**partial)
            if not save(job): raise InterruptedError()
        try:
            if job.get('autor'):
                from ed_workflows import still_authorized
                still_authorized({'autor':job['autor']['id'],'workspace':job['autor']['workspace']})
            result=worker(job,progress)
            job.update(estado='concluida',progresso=100,resultado=result,mensagem='Operação concluída; resultado disponível para revisão.')
        except InterruptedError: return
        except Exception as exc:
            from werkzeug.exceptions import Forbidden
            job.update(estado='erro',progresso=100,mensagem=exc.description if isinstance(exc,Forbidden) else str(exc) if isinstance(exc,ValueError) else 'Falha na operação; resultados parciais preservados. Tente novamente ou use o fluxo manual.')
        save(job)


def ativo(ident):
    if ler_job(ident)['estado'] not in ('na_fila','pesquisando'): raise InterruptedError()

def retry_generation(ident):
    """Falha encerrada ou cancelamento, sem artefato; conserva ID e histórico."""
    with lock:
        job=ler_job(ident);d=job.get('diagnostico',{})
        if ident in running or job['tipo']!='codex_construcao' or job['estado'] not in ('erro','cancelada'):return False
        legacy_contract=job.get('turn_id') and job.get('mensagem')=='Arquivo fora da lista permitida ou repetido; código rejeitado.'
        if job['estado']!='cancelada' and not legacy_contract and d.get('categoria') not in ('autenticacao','permissao','modelo_recusado','contrato_codigo') and d.get('http_status') not in (402,429,500,502,503,504) and d.get('codigo') not in ('timeout','network','usageLimitExceeded','rateLimitExceeded'):return False
        if len(job.get('historico_tentativas',[]))>=1:return False
        from ed_runtime import artefact_root
        root=artefact_root(job['empresa_id'],job['id'])
        revalidation=(root/'index.html').exists() and job.get('inferencia_concluida') and d.get('categoria')=='contrato_codigo'
        if (root/'index.html').exists() and not revalidation:return False
        ledger=root/'contexto-executor.json'
        if ledger.is_file():
            cache=root/'.cache';cache.mkdir(exist_ok=True)
            (cache/'contexto-executor-tentativa-1.json').write_bytes(ledger.read_bytes())
        raw=root/'.cache/resposta-codex.json'
        if raw.is_file():(root/'.cache/resposta-codex-tentativa-1.json').write_bytes(raw.read_bytes())
        job.setdefault('historico_tentativas',[]).append({k:job.get(k) for k in ('estado','mensagem','diagnostico','thread_id','turn_id','runtime')})
        job.update(estado='na_fila',progresso=0,mensagem='Revalidando resposta completa; sem outra inferência.' if revalidation else 'Retomada da construção; mesmo projeto, nova tentativa registrada.')
        with store.conectar() as con:con.execute('UPDATE ed_operacoes SET dados=? WHERE id=?',(json.dumps(job,ensure_ascii=False),ident))
    from ed_creation_providers import generate
    if revalidation:
        from ed_runtime import revalidate_completed
        generate=revalidate_completed
    if current_app.config['RUN_JOBS']:submit(pool,executar,current_app._get_current_object(),ident,generate)
    else:executar(current_app._get_current_object(),ident,generate)
    return True
