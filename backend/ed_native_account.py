"""Segue somente o cache nativo autorizado; nunca envia tokens à API ou ao banco."""
import json,os,shutil
from datetime import datetime
from pathlib import Path
from threading import RLock
from flask import jsonify,request
import ed_store as store
from ed_codex_oauth import native_identity

lock=RLock();active={}
def source():return Path(os.environ.get('CODEX_HOME') or Path.home()/'.codex')/'auth.json'
def setting():
    with store.conectar() as con:r=con.execute("SELECT valor FROM ed_config WHERE chave='runtime:seguir-conta'").fetchone()
    return json.loads(r['valor']) if r else {'ativo':False,'estado':'desativado'}
def save(value):
    with store.conectar() as con:con.execute('INSERT INTO ed_config VALUES (?,?) ON CONFLICT(chave) DO UPDATE SET valor=excluded.valor',('runtime:seguir-conta',json.dumps(value,ensure_ascii=False)))

def newer_session(incoming,current):
    """Mesma conta com login renovado; nunca sobrescreve um cache mais recente."""
    try:
        source_value=json.loads(incoming.read_text(encoding='utf-8'))
        target_value=json.loads(current.read_text(encoding='utf-8'))
        source_time=datetime.fromisoformat(source_value['last_refresh'].replace('Z','+00:00'))
        target_time=datetime.fromisoformat(target_value['last_refresh'].replace('Z','+00:00'))
        return source_time>target_time and source_value.get('tokens')!=target_value.get('tokens')
    except (OSError,ValueError,TypeError,KeyError):return False
def inspect():
    cfg=setting();home=store.pasta()/'runtime-codex';current=native_identity(home/'auth.json');app=native_identity(source())
    return {**cfg,'conta_aplicativo':app,'conta_runtime':current,'origem':'Cache file do Codex no CODEX_HOME do processo ou ~/.codex; acesso confirmado por account/read.','troca_real_validada':bool(cfg.get('troca_real_validada') and cfg.get('para')==current['identificador']==app['identificador']),'mensagem':cfg.get('mensagem','A troca no aplicativo precisa de teste com o usuário. Nenhum rodízio entre contas.')}
def reconcile(home=None):
    home=home or store.pasta()/'runtime-codex';key=str(home.resolve())
    with lock:
        cfg=setting()
        if not cfg['ativo']:return cfg
        previous=native_identity(home/'auth.json');incoming=native_identity(source())
        same_account=incoming['identificador']==previous['identificador']
        renewed=same_account and incoming['identificador']!='nativa' and newer_session(source(),home/'auth.json')
        changed=not same_account or renewed
        if not changed:
            if incoming['identificador']=='nativa':cfg.update(estado='precisa_login',mensagem='Cache seguido sem identidade ChatGPT; novos jobs aguardam login nativo.');save(cfg);return cfg
            if cfg.get('estado')=='precisa_login':cfg.update(estado='sessao_selecionada',mensagem='Cache nativo voltou a estar disponível. Acesso é conferido pelo app-server antes de executar.');save(cfg)
            if cfg.get('estado')=='desativado':cfg.update(estado='sessao_selecionada',mensagem='Seguindo o cache nativo autorizado; identidade da sessão conferida pelo app-server a cada execução. Troca entre contas ainda não testada no aplicativo.');save(cfg)
            if cfg.get('estado')=='aguardando_checkpoint':cfg.update(estado='conta_atualizada_nao_validada',mensagem='A sessão seguida coincide com a sessão nativa do runtime. Confira acesso e uso.');save(cfg)
            return cfg
        if active.get(key,0):
            cfg.update(estado='aguardando_checkpoint',mensagem='Mudança detectada; aguardando a etapa em andamento terminar antes de atualizar o runtime.');save(cfg);return cfg
        if incoming['identificador']=='nativa':
            # Cache nativo isolado antigo não deve continuar após logout no cache seguido.
            cfg.update(estado='precisa_login',mensagem='A conta seguida não está autenticada. Novos jobs aguardam login nativo; nenhum token de outra rota foi usado.');save(cfg);return cfg
        try:
            auth=json.loads(source().read_text(encoding='utf-8'))
            if auth.get('OPENAI_API_KEY') or not auth.get('tokens',{}).get('access_token'):raise ValueError()
        except (OSError,ValueError,TypeError):
            cfg.update(estado='precisa_login',mensagem='Cache nativo indisponível ou de outra rota. Autentique com ChatGPT no Codex.');save(cfg);return cfg
        from ed_runtime import private_native_cache
        home.mkdir(parents=True,exist_ok=True);private_native_cache(home)
        temporary=home/'auth-sync.tmp';shutil.copyfile(source(),temporary);temporary.replace(home/'auth.json')
        cfg.update(estado='conta_atualizada_nao_validada',de=previous['identificador'],para=incoming['identificador'],verificacao_id=None,troca_real_validada=False,atualizado_em=store.agora(),mensagem='Conta atualizada no cache nativo isolado. Acesso, limite e inferência da nova conta ainda não validados.');save(cfg)
        if renewed:
            cfg.update(evento='sessao_renovada_mesma_conta',mensagem='Nova sessão da mesma conta detectada no aplicativo. Cache isolado atualizado; autenticação e inferência serão conferidas antes de retomar.');save(cfg)
        return cfg
def enter(home):
    with lock:
        cfg=reconcile(home)
        if cfg.get('ativo') and cfg.get('estado') in ('precisa_login','aguardando_checkpoint'):raise ValueError(cfg['mensagem'])
        key=str(home.resolve());active[key]=active.get(key,0)+1
    return key
def leave(key):
    with lock:active[key]=max(0,active.get(key,1)-1)

def verify_changed(job,progress):
    from ed_runtime import small_test
    try:result=small_test(job,progress)
    except ValueError as exc:
        from ed_codex_transport import sanitize
        save({**setting(),'estado':'erro','mensagem':'Conta seguida não concluiu inferência mínima: '+sanitize(str(exc))[:1000]});raise
    with lock:
        cfg=setting();ident=native_identity(store.pasta()/'runtime-codex/auth.json')['identificador']
        if cfg.get('para')!=ident or native_identity(source())['identificador']!=ident:raise ValueError('Conta mudou novamente durante o teste. Nenhum job será retomado nesta sessão.')
        cfg.update(estado='conectado',verificacao_id=job['id'],troca_real_validada=cfg.get('de') not in (None,'nativa',ident),mensagem='Identidade e inferência mínima da conta seguida conferidas pelo runtime nativo. Retomando somente falhas externas seguras.');save(cfg)
    from ed_workflows import listing,action,still_authorized
    from ed_services import ler_job
    for flow in listing():
        if flow['estado']!='aguardando_dependencia':continue
        failed=[ler_job(s['operacao_id']) for s in flow['etapas'] if s['nome'] in ('gerar','refinar') and s.get('operacao_id') and s['estado']!='concluida']
        if not failed or any(j['estado']!='erro' or j.get('diagnostico',{}).get('categoria') not in ('autenticacao','permissao','modelo_recusado') and j.get('diagnostico',{}).get('http_status') not in (402,429) for j in failed):continue
        try:
            still_authorized(flow)
            from flask import g
            g.actor={'id':flow['autor'],'workspace':flow['workspace'],'papel':flow['papel']}
            action(flow['id'],'retomar')
        except (ValueError,LookupError):continue
    return result

def poll():
    from ed_tasks import iniciar
    from ed_services import ler_job
    cfg=reconcile()
    if cfg.get('estado')!='conta_atualizada_nao_validada':return
    from ed_workflows import still_authorized
    from werkzeug.exceptions import Forbidden
    try:still_authorized({'autor':cfg.get('autor','local'),'workspace':cfg.get('workspace','principal')})
    except Forbidden as exc:
        save({**cfg,'estado':'erro','mensagem':exc.description});return
    previous=cfg.get('verificacao_id')
    if previous and ler_job(previous)['estado'] in ('na_fila','pesquisando','erro'):return
    j=iniciar('codex','codex_conta_verificacao',None,{'modo':'plano','modelo':'gpt-6.1-sol'},verify_changed,idempotency_key='conta:'+str(cfg.get('atualizado_em'))+':'+cfg.get('para',''))
    save({**setting(),'verificacao_id':j['id']})
def registrar(bp):
    @bp.get('/runtime/conta-ativa',endpoint='native_follow_status')
    def status():
        reconcile();return jsonify(inspect())
    @bp.put('/runtime/conta-ativa',endpoint='native_follow_config')
    def config():
        d=request.get_json()
        if not isinstance(d,dict) or set(d)!={'ativo'} or type(d['ativo'])!=bool:raise ValueError('Informe ativo booleano.')
        from flask import g
        actor=getattr(g,'actor',{}) or {'id':'local','workspace':'principal'}
        cfg={**setting(),'ativo':d['ativo'],'autor':actor['id'],'workspace':actor['workspace']}
        if d['ativo'] and cfg.get('estado')=='erro':
            cfg.update(estado='conta_atualizada_nao_validada',verificacao_id=None,para=native_identity(source())['identificador'],atualizado_em=store.agora())
        save(cfg);reconcile();return jsonify(inspect())
