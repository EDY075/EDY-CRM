"""Lote persistente: um fluxo filho por empresa, sem repetir efeitos concluídos."""
import json,time,threading
from flask import current_app,g,jsonify,request
from werkzeug.exceptions import Forbidden,Conflict
import ed_store as store
from ed_workflows import start,get as flow_get,action as flow_action,lock,still_authorized

def listing():
    with store.conectar() as con:rows=con.execute("SELECT valor FROM ed_config WHERE chave LIKE 'lote:%' ORDER BY rowid DESC LIMIT 30").fetchall()
    return [json.loads(r['valor']) for r in rows]
def get(ident):
    with store.conectar() as con:r=con.execute('SELECT valor FROM ed_config WHERE chave=?',('lote:'+ident,)).fetchone()
    if not r:raise LookupError('Lote não encontrado neste workspace.')
    return json.loads(r['valor'])
def save(value):
    value['atualizado_em']=store.agora()
    with store.conectar() as con:con.execute('INSERT INTO ed_config VALUES (?,?) ON CONFLICT(chave) DO UPDATE SET valor=excluded.valor',('lote:'+value['id'],json.dumps(value,ensure_ascii=False)))
def recover():
    if not current_app.config.get('RECOVER_JOBS',True):return
    for x in listing():
        if x['estado']=='executando':x.update(estado='pausada',mensagem='Servidor reiniciado. Retome o lote pelos checkpoints; construções existentes não serão duplicadas.');save(x)
def eligibility(lead,require_confirmed=True):
    reasons=[]
    if lead.get('crm_arquivada'):reasons.append('Empresa arquivada.')
    if not lead['nome'].strip() or store.normalizar(lead['nome']) in ('academia','padaria','salao','restaurante'):reasons.append('Nome genérico; identidade pendente.')
    if require_confirmed and not lead['confirmado']:reasons.append('Identidade ainda não revisada.')
    if not lead['cidade'] and not lead['endereco']:reasons.append('Localização ausente.')
    return reasons
def start_batch(data):
    if not isinstance(data,dict) or set(data)-{'empresa_ids','chave','geracao','instrucoes','exigir_confirmadas','escopo','concorrencia'}:raise ValueError('Lote inválido.')
    ids=data.get('empresa_ids');key=store.texto(data.get('chave',''),100)
    if not key or not isinstance(ids,list) or not 1<=len(ids)<=5 or len(set(ids))!=len(ids):raise ValueError('Selecione de uma a cinco empresas distintas e uma chave estável.')
    generation=data.get('geracao','codex_nativo')
    if generation not in ('codex_nativo','openrouter','opencode','templates'):raise ValueError('Motor de criação inválido.')
    required=data.get('exigir_confirmadas',True)
    if type(required)!=bool:raise ValueError('Critério de confirmação inválido.')
    leads=[store.ler_empresa(i) for i in ids]
    concurrency=data.get('concorrencia',1)
    if type(concurrency)!=int or not 1<=concurrency<=2:raise ValueError('Concorrência do lote: uma ou duas empresas; padrão conservador um.')
    actor=getattr(g,'actor',{}) or {'id':'local','workspace':'principal','papel':'administrador'}
    with lock:
        old=next((x for x in listing() if x['chave']==key),None)
        if old:
            if [x['empresa_id'] for x in old['filhos']]!=ids:raise Conflict('Chave do lote já usada para outra seleção.')
            return old
        if any(x['estado']=='executando' for x in listing()):raise Conflict('Já existe um lote em execução. Pause ou conclua antes de iniciar outro.')
        x=dict(id=store.novo_id(),chave=key,estado='executando',autor=actor['id'],workspace=actor['workspace'],criado_em=store.agora(),geracao=generation,concorrencia=concurrency,
            instrucoes=store.texto(data.get('instrucoes',''),12000),escopo=data.get('escopo','previa'),exigir_confirmadas=required,
            filhos=[dict(empresa_id=l['id'],nome=l['nome'],estado='pendente',fluxo_id=None,motivos=eligibility(l,required)) for l in leads],prontas=0,mensagem='Lote criado; uma construção por vez. Seleção manual não confirma fatos, fotos ou identidade.')
        if x['escopo'] not in ('previa','completo'):raise ValueError('Escopo inválido.')
        save(x)
    tick();return get(x['id'])
def sync(x):
    from ed_preview import active_url
    from ed_services import ler_job
    for child in x['filhos']:
        if not child.get('fluxo_id'):continue
        flow=flow_get(child['fluxo_id']);child['etapas']=flow['etapas'];child['mensagem']=flow['mensagem'];child['fluxo_estado']=flow['estado']
        built=next((s.get('resultado') for s in flow['etapas'] if s['nome']=='gerar'),None) or {}
        verified=next((s.get('resultado') for s in flow['etapas'] if s['nome']=='verificar'),None) or {}
        prospect=next((s.get('resultado') for s in flow['etapas'] if s['nome']=='prospeccao'),None)
        if built.get('construcao_id'):
            jid=built['construcao_id'];job=ler_job(jid)
            child.update(construcao_id=jid,url_ativa=active_url(child['empresa_id'],jid),miniatura_url=verified.get('miniatura_url'),prospeccao=prospect)
            if job['estado']=='concluida' and verified.get('url') and prospect:child.update(estado='pronta_para_revisao',mensagem='Prévia renderizada e texto preparado. Aprovação visual e direitos ainda requerem revisão.')
        if child['estado']!='pronta_para_revisao':
            child['estado']={'na_fila':'executando','executando':'executando','pausada':'pausada','cancelada':'cancelada'}.get(flow['estado'],'precisa_atencao')
    x['prontas']=sum(c['estado']=='pronta_para_revisao' for c in x['filhos']);x['mensagem']=str(x['prontas'])+' de '+str(len(x['filhos']))+' prévias prontas para revisão.'
    return x
def tick():
    with lock:
        for x in listing():
            if x['estado'] not in ('executando','pausada'):continue
            sync(x);save(x)
            active_count=sum(c['estado']=='executando' for c in x['filhos'])
            if x['estado']!='executando' or active_count>=x.get('concorrencia',1):continue
            # Pausar o fluxo não cancela a inferência filha. Aguarde seu checkpoint.
            from ed_services import ler_job
            if any(c['estado']!='executando' and c.get('fluxo_id') and any(ler_job(s['operacao_id'])['estado'] in ('na_fila','pesquisando') for s in flow_get(c['fluxo_id'])['etapas'] if s.get('operacao_id')) for c in x['filhos']):continue
            try:still_authorized(x)
            except Forbidden as e:x.update(estado='pausada',mensagem=e.description);save(x);continue
            pending=next((c for c in x['filhos'] if c['estado']=='pendente'),None)
            if not pending:
                if active_count:continue
                x.update(estado='concluida' if x['prontas']==len(x['filhos']) else 'parcial');save(x);continue
            lead=store.ler_empresa(pending['empresa_id']);reasons=eligibility(lead,x['exigir_confirmadas'])
            if reasons:pending.update(estado='precisa_atencao',motivos=reasons,mensagem='Revise elegibilidade ou ajuste os critérios; os outros leads continuam.');save(x);continue
            position=x['filhos'].index(pending)
            directions=['Hero tipográfico em duas colunas, fundo papel e barra de contexto local.','Hero central imersivo com blocos de informação em mosaico e CTA fixo acessível.','Hero editorial assimétrico com índice lateral e narrativa por etapas.','Hero horizontal com hierarquia monumental e galeria dividida, quando houver materiais autorizados.','Hero compacto com manifesto, cards amplos e convite em faixa contrastante.']
            instruction=x['instrucoes']+'\nDireção específica desta alternativa: '+directions[position]+'\nAdapte à empresa '+lead['nome']+' em '+lead['cidade']+'. Nunca invente serviços ou usar fotos/fatos de outra empresa. Aplique as instruções EDY e reprovação visual da PÃO. Não repetir um template com nome/cor trocados.'
            try:
                f=start(dict(acao='preparar',empresa_id=lead['id'],geracao=x['geracao'],modo='automatico',instrucoes=instruction,escopo=x['escopo']),key='lote:'+x['id']+':'+lead['id'])
                pending.update(fluxo_id=f['id'],estado='executando');save(x)
            except (ValueError,Conflict) as e:pending.update(estado='precisa_atencao',mensagem=str(e));save(x)
def action(ident,command,company=None):
    with lock:
        x=get(ident);actor=getattr(g,'actor',{})
        if actor.get('id')!=x['autor'] and actor.get('papel')!='administrador':raise Forbidden('Somente autor/administrador controla o lote.')
        if command not in ('pausar','retomar','cancelar'):raise ValueError('Controle inválido.')
        if x['estado']=='concluida':return sync(x)
        children=[c for c in x['filhos'] if not company or c['empresa_id']==company]
        if not children:raise LookupError('Empresa não pertence ao lote.')
        for c in children:
            if c['estado']=='pronta_para_revisao':continue
            if c.get('fluxo_id'):
                f=flow_get(c['fluxo_id'])
                if command=='retomar' and all(s['estado']=='concluida' for s in f['etapas']):continue
                try:flow_action(f['id'],command)
                except ValueError:pass
            c['estado']={'pausar':'pausada','cancelar':'cancelada','retomar':'pendente' if not c.get('fluxo_id') else 'executando'}[command]
        if not company:x['estado']={'pausar':'pausada','cancelar':'cancelada','retomar':'executando'}[command]
        else:
            if command=='retomar':x['estado']='executando'
        save(x)
    if command=='retomar':tick()
    return get(ident)
def scheduler(app):
    if not app.config['RUN_JOBS']:return
    def loop():
        from ed_workspace import data_directory
        from ed_access import connection,directory
        while True:
            with app.app_context():
                with connection() as con:ids=[r[0] for r in con.execute('SELECT id FROM workspaces')]
                for ident in ids:
                    token=data_directory.set(directory(ident))
                    try:
                        tick()
                        from ed_native_account import poll
                        poll()
                    except Exception:app.logger.exception('Falha do scheduler de lotes; resultados mantidos.')
                    finally:data_directory.reset(token)
            time.sleep(2)
    threading.Thread(target=loop,daemon=True,name='edy-lotes').start()
def registrar(bp):
    @bp.get('/lotes',endpoint='batches_list')
    def batches_list():
        with lock:return jsonify([sync(x) for x in listing()])
    @bp.post('/lotes',endpoint='batches_start')
    def batches_start():return jsonify(start_batch(request.get_json())),202
    @bp.get('/lotes/<ident>',endpoint='batches_get')
    def batches_get(ident):return jsonify(sync(get(ident)))
    @bp.post('/lotes/<ident>/<command>',endpoint='batches_control')
    def control(ident,command):return jsonify(action(ident,command,(request.get_json() or {}).get('empresa_id')))
