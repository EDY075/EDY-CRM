import io
import json
from PIL import Image
from test_ed_enrich import client
from test_ed_adaptive import lead, construction
from test_ed_adaptive_build import reviewed


def selected(client, name='Cliente do estúdio'):
    a=lead(client,name); reviewed(client,a['id'])
    base='/api/ed/empresas/'+a['id']
    b=io.BytesIO();Image.new('RGB',(120,240),'wheat').save(b,'PNG');b.seek(0)
    v=client.post(base+'/estudio/importar',data={'arquivo':(b,'conceito.png'),'uso_referencia':'true','secao_id':'pagina'}).json
    s=client.get(base+'/estudio').json
    assert client.post(base+'/estudio/escolher',json={'revisao':s['revisao'],'variante_id':v['id']}).status_code==200
    return a,v,base


def test_context_review_preserves_selection_brief_history_and_guards(client):
    import ed_site_refinement,ed_visual_studio
    from werkzeug.exceptions import Conflict
    import pytest
    a,v,base=selected(client)
    s=client.post(base+'/refinamento-site',json={'projeto_id':'','variante_id':v['id']}).json
    finish(client,s,'preserved-context-version')
    s=client.get(base+'/refinamento-site/'+s['id']).json
    old=client.get(base+'/estudio').json['autorizacoes_trabalho'][0]
    added=client.post('/api/ed/biblioteca',json={'titulo':'Correção restrita a este cliente','conteudo':'Preservar a galeria aprovada.','escopo':'lead','vinculo':a['id']}).json
    route=base+'/refinamento-site/'+s['id']
    s=client.get(route).json
    review=s['revisao_contexto']
    assert any(x['titulo']==added['titulo'] for x in review['alteracoes'])
    with client.application.app_context(),pytest.raises(Conflict):
        ed_visual_studio.approval(a['id'],'',old['id'])
    assert client.post(route+'/contexto',json={'autorizacao_id':old['id'],'contexto_hash':'stale'}).status_code==409
    payload={k:review[k] for k in ('autorizacao_id','contexto_hash')}
    refreshed=client.post(route+'/contexto',json=payload)
    assert refreshed.status_code==200,refreshed.json
    new=refreshed.json
    assert new['chat_id']==s['chat_id'] and new['atual']==s['atual']
    assert new['brief_versao']==s['brief_versao'] and new['variante_id']==v['id']
    assert new['revisao_contexto'] is None and new['autorizacao_id']!=old['id']
    assert client.get(base+'/estudio').json['autorizacoes_trabalho'][0]==old
    assert client.post(route+'/contexto',json=payload).json['autorizacao_id']==new['autorizacao_id']
    with client.application.app_context():
        assert ed_site_refinement.get(a['id'],s['id'])['revisoes_contexto'][0]['anterior']==old['id']
    # Atualizar contexto nunca autoriza mudar montagem/brief/fotos silenciosamente.
    client.put('/api/ed/biblioteca/'+added['id'],json={'versao':added['versao'],'conteudo':'Nova instrução.'})
    state=client.get(base+'/estudio').json
    fields={k:state[k] for k in ('revisao','secoes','quantidade','modo')}
    fields['direcao']={k:x for k,x in state['direcao'].items() if k not in ('versao','estado')}
    fields['direcao']['estilo']='Composição alterada, exige outra revisão'
    assert client.put(base+'/estudio',json=fields).status_code==200
    review=client.get(route).json['revisao_contexto']
    assert client.post(route+'/contexto',json={k:review[k] for k in payload}).status_code==409


def test_work_authorization_and_idempotent_existing_pipeline(client):
    a,v,base=selected(client)
    payload={'projeto_id':'','variante_id':v['id']}
    r=client.post(base+'/refinamento-site',json=payload)
    assert r.status_code==202,r.json
    s=r.json
    assert s['estado']=='construindo'
    assert client.post(base+'/refinamento-site',json=payload).json['id']==s['id']
    visual=client.get(base+'/estudio').json
    assert not visual['aprovacoes']
    assert len(visual['autorizacoes_trabalho'])==1
    chat=client.get('/api/ed/assistente/conversas/'+s['chat_id']).json
    assert chat['contexto']['brief_adaptativo']['dossier']['proposta']['objetivo']=='Decisão manual exclusiva'
    flow=client.get('/api/ed/fluxos/'+s['execucao_id']).json
    assert flow['plano']['geracao']=='codex_nativo'
    assert [e['nome'] for e in flow['etapas']]==['exportar','gerar','verificar','prospeccao']


def test_command_durable_while_building_and_other_company_rejected(client):
    a,v,base=selected(client)
    s=client.post(base+'/refinamento-site',json={'projeto_id':'','variante_id':v['id']}).json
    route='/api/ed/assistente/conversas/'+s['chat_id']+'/mensagens'
    msg=client.post(route,json={'texto':'Diminuir espaço da hero, preservando as demais seções.','chave':'queue-1'})
    assert msg.status_code==202,msg.json
    assert msg.json['estado_fila']=='aguardando_base'
    assert client.post(route,json={'texto':msg.json['texto'],'chave':'queue-1'}).json['id']==msg.json['id']
    another=lead(client,'Outro cliente')
    assert client.get('/api/ed/empresas/'+another['id']+'/refinamento-site/'+s['id']).status_code==404
    from ed_app import criar_app
    app=criar_app({'TESTING':True,'DATA_DIR':client.application.config['DATA_DIR'],'RUN_JOBS':False})
    restored=app.test_client().get(base+'/refinamento-site/'+s['id']).json
    assert restored['comandos'][0]['texto']==msg.json['texto']
    assert restored['estado']=='pausada'


def test_html_reference_static_analysis_original_and_scoped_chat(client):
    a=lead(client,'Referência de teste')
    chat=client.post('/api/ed/assistente/conversas',json={'empresa_id':a['id']}).json
    html=b'''<style>:root{--brand:#ac6438} h1{font-family:Georgia;animation:entrada 1s}@keyframes entrada{from{opacity:0;transform:translateY(20px)}to{opacity:1}}</style><section><img src="foto-local.jpg"></section><script src="https://cdn.example.org/gsap.min.js"></script><script>fetch('/api/ed/cofre');IntersectionObserver</script>'''
    r=client.post('/api/ed/assistente/conversas/'+chat['id']+'/anexos',data={'arquivo':(io.BytesIO(html),'site.html')})
    assert r.status_code==201,r.json
    c=client.get('/api/ed/assistente/conversas/'+chat['id']).json
    item=client.get('/api/ed/biblioteca/'+c['contexto']['anexos'][0]['id']).json
    assert item['estado']=='inativo'
    assert 'GSAP' in item['conteudo'] and 'entrada' in item['conteudo'] and 'Georgia' in item['conteudo']
    assert item['analise_html']['executado'] is False
    assert client.get(item['original']['url']).data==html
    assert client.get(item['original']['url']).headers['Content-Disposition'].startswith('attachment')


def finish(client, s, ident, base=''):
    import ed_store,ed_workflows
    construction(client,s['empresa_id'],ident,base)
    with client.application.app_context(),ed_store.conectar() as con:
        job=json.loads(con.execute('SELECT dados FROM ed_operacoes WHERE id=?',(ident,)).fetchone()['dados'])
        job.update(fornecedor='mock_contract',resultado={**job['resultado'],'modelo':'mock','build_estatico':{'estado':'validado'},'arquivos':['index.html','style.css'],'arquivos_devolvidos':['style.css']})
        con.execute('UPDATE ed_operacoes SET dados=? WHERE id=?',(json.dumps(job),ident))
        con.commit()
        flow=ed_workflows.get(s['execucao_id'])
        for step in flow['etapas']:
            step.update(estado='concluida',resultado={'construcao_id':ident,'tipo':'codex_construcao'} if step['nome'] in ('gerar','refinar') else {})
        flow['estado']='parcial';ed_workflows.write(flow)


def test_ordered_refinement_restore_and_late_result_preserved(client):
    import ed_site_refinement
    a,v,base=selected(client)
    s=client.post(base+'/refinamento-site',json={'projeto_id':'','variante_id':v['id']}).json
    msg_route='/api/ed/assistente/conversas/'+s['chat_id']+'/mensagens'
    client.post(msg_route,json={'texto':'Reduza a hero.','chave':'first-command'})
    client.post(msg_route,json={'texto':'Anime o subtítulo, sem alterar galeria.','chave':'second-command'})
    finish(client,s,'version-one')
    with client.application.app_context():s=ed_site_refinement.sync(ed_site_refinement.get(a['id'],s['id']))
    assert s['atual']=='version-one'
    assert s['comandos'][0]['estado_fila']=='executando'
    assert s['comandos'][1]['estado_fila']=='aguardando_base'
    flow=client.get('/api/ed/fluxos/'+s['execucao_id']).json
    assert flow['plano']['construcao_id']=='version-one'
    finish(client,s,'version-two','version-one')
    with client.application.app_context():s=ed_site_refinement.sync(ed_site_refinement.get(a['id'],s['id']))
    assert s['atual']=='version-two'
    assert s['comandos'][1]['estado_fila']=='executando'
    # Enquanto o segundo comando está executando, restauração invalida sua aplicação tardia.
    restored=client.post(base+'/refinamento-site/'+s['id']+'/restaurar',json={'versao_id':'version-one'})
    assert restored.status_code==200,restored.json
    finish(client,s,'version-three','version-two')
    latest=client.get(base+'/refinamento-site/'+s['id']).json
    assert latest['atual']=='version-one'
    assert len(latest['versoes'])==3
    assert latest['comandos'][1]['estado_fila']=='concluida'
    assert client.post(base+'/refinamento-site',json={'projeto_id':'','variante_id':v['id']}).json['chat_id']==s['chat_id']
    assert client.post(base+'/refinamento-site/'+s['id']+'/restaurar',json={'versao_id':'unknown-version'}).status_code==404


def test_failed_build_keeps_last_good_and_reviewed_voice_uses_same_queue(client):
    import ed_store,ed_workflows
    a,v,base=selected(client)
    s=client.post(base+'/refinamento-site',json={'projeto_id':'','variante_id':v['id']}).json
    finish(client,s,'good-version')
    s=client.get(base+'/refinamento-site/'+s['id']).json
    with client.application.app_context(),ed_store.conectar() as con:
        con.execute('INSERT INTO ed_operacoes VALUES (?,?)',('stt-fixture',json.dumps(dict(id='stt-fixture',tipo='voice_transcription',estado='concluida',resultado={'texto':'Espasso da hero'},fornecedor='fixture'))))
    msg=client.post('/api/ed/assistente/conversas/'+s['chat_id']+'/mensagens',json={'texto':'Diminuir o espaço da hero.','chave':'voice-refined','origem':'voz','transcricao_id':'stt-fixture'}).json
    assert msg['estado_fila']=='executando'
    assert msg['transcricao_original']=='Espasso da hero' and msg['texto_revisado']=='Diminuir o espaço da hero.'
    with client.application.app_context():ed_workflows.patch(msg['execucao_id'],estado='aguardando_dependencia',mensagem='Build falhou: arquivo de imagem ausente')
    s=client.get(base+'/refinamento-site/'+s['id']).json
    assert s['atual']=='good-version' and s['estado']=='aguardando_dependencia'
    assert len(s['versoes'])==1
    bad=client.post('/api/ed/assistente/conversas/'+s['chat_id']+'/mensagens',json={'texto':'','chave':'empty','origem':'voz'})
    assert bad.status_code==400


def test_unselected_and_stale_candidates_never_generate(client):
    a,v,base=selected(client)
    assert client.post(base+'/refinamento-site',json={'projeto_id':'','variante_id':'foreign'}).status_code==409
    s=client.get(base+'/estudio').json
    fields={k:s[k] for k in ('revisao','secoes','quantidade','modo')}
    fields['direcao']={k:v for k,v in s['direcao'].items() if k not in ('versao','estado')}
    fields['direcao']['estilo']='Outra direção solicitada pelo operador'
    assert client.put(base+'/estudio',json=fields).status_code==200
    assert client.post(base+'/refinamento-site',json={'projeto_id':'','variante_id':v['id']}).status_code==409


def test_html_does_not_activate_global_preferences_and_version_is_pinned(client):
    a,v,base=selected(client)
    s=client.post(base+'/refinamento-site',json={'projeto_id':'','variante_id':v['id']}).json
    path='/api/ed/assistente/conversas/'+s['chat_id']+'/anexos'
    html=b'<style>.unique-pao-rule{transition:opacity 400ms;font-family:Georgia}</style>'
    assert client.post(path,data={'arquivo':(io.BytesIO(html),'referencia.html')}).status_code==201
    import ed_assistant,ed_library
    with client.application.app_context():
        ctx=ed_assistant.execution_context(s['chat_id'])
        ref=ctx['referencias'][0]
        assert ref['versao']==1 and ref['analise_html']['executado'] is False
        assert 'unique-pao-rule' in ref['conteudo']
        assert 'unique-pao-rule' not in ed_library.resolve(a['id'])['texto']
    another=lead(client,'Sem referência de outra empresa')
    assert 'unique-pao-rule' not in client.get('/api/ed/empresas/'+another['id']+'/contexto').json['texto']


def test_section_gaps_keep_chat_and_command_until_composition_complete(client):
    a=lead(client,'Montagem por seção');reviewed(client,a['id']);base='/api/ed/empresas/'+a['id']
    state=client.get(base+'/estudio').json
    def upload(section):
        b=io.BytesIO();Image.new('RGB',(120,240),'wheat').save(b,'PNG');b.seek(0)
        return client.post(base+'/estudio/importar',data={'arquivo':(b,'conceito.png'),'uso_referencia':'true','secao_id':section}).json
    v=upload(state['secoes'][0]['id']);state=client.get(base+'/estudio').json
    client.post(base+'/estudio/escolher',json={'revisao':state['revisao'],'variante_id':v['id']})
    s=client.post(base+'/refinamento-site',json={'projeto_id':'','variante_id':v['id']}).json
    assert s['estado']=='escolhas_pendentes' and s['lacunas'] and not s['execucao_id']
    msg=client.post('/api/ed/assistente/conversas/'+s['chat_id']+'/mensagens',json={'texto':'Preserve a seção escolhida.','chave':'gap-message'})
    assert msg.json['estado_fila']=='aguardando_base'
    # Completar montagem no mesmo projeto não perde a conversa que já recebeu o comando.
    for section in state['secoes'][1:]:
        option=upload(section['id']);state=client.get(base+'/estudio').json
        client.post(base+'/estudio/escolher',json={'revisao':state['revisao'],'variante_id':option['id']})
    result=client.post(base+'/refinamento-site/'+s['id']+'/continuar',json={})
    assert result.status_code==202,result.json
    assert result.json['chat_id']==s['chat_id'] and result.json['estado']=='construindo'
    assert result.json['comandos'][0]['texto']=='Preserve a seção escolhida.'


def test_queue_recovery_between_intent_and_flow_binding(client):
    import ed_site_refinement,ed_assistant,ed_workflows
    a,v,base=selected(client)
    s=client.post(base+'/refinamento-site',json={'projeto_id':'','variante_id':v['id']}).json
    finish(client,s,'base-crash')
    s=client.get(base+'/refinamento-site/'+s['id']).json
    msg=client.post('/api/ed/assistente/conversas/'+s['chat_id']+'/mensagens',json={'texto':'Corrija somente o espaçamento.','chave':'crash-window'}).json
    with client.application.app_context():
        saved=ed_site_refinement.get(a['id'],s['id'])
        flow_id=saved['comandos'][0]['execucao_id']
        saved['tentativas']=[t for t in saved['tentativas'] if not t.get('comando_id')]
        ed_site_refinement.save(saved)
        restored=ed_site_refinement.sync(saved)
        assert restored['tentativas'][-1]['execucao_id']==flow_id
        assert len([j for j in ed_workflows.listing() if j['id']==flow_id])==1
    assert client.post('/api/ed/assistente/conversas/'+s['chat_id']+'/mensagens',json={'texto':'Outro conteúdo','chave':'crash-window'}).status_code==409


def test_queue_recovers_saved_message_after_interrupted_request(client):
    import ed_assistant,ed_site_refinement
    a,v,base=selected(client)
    s=client.post(base+'/refinamento-site',json={'projeto_id':'','variante_id':v['id']}).json
    with client.application.app_context():
        chat=ed_assistant.conversation(s['chat_id'])
        chat['mensagens'].append(dict(id='orphan-msg',papel='usuario',texto='Recuperar este comando.',chave='orphan-key',origem='texto',criado_em='2026-10-05T00:00:00+00:00'))
        ed_assistant.save(chat)
        recovered=ed_site_refinement.sync(ed_site_refinement.get(a['id'],s['id']),dispatch=False)
        assert recovered['comandos'][0]['id']=='orphan-msg'
    assert client.get(base+'/refinamento-site/'+s['id']).json['comandos'][0]['texto']=='Recuperar este comando.'


def test_changed_selected_composition_cannot_start_old_session(client):
    import ed_site_refinement
    a,v,base=selected(client)
    s=client.post(base+'/refinamento-site',json={'projeto_id':'','variante_id':v['id']}).json
    with client.application.app_context():
        old=ed_site_refinement.get(a['id'],s['id'])
        old.update(execucao_id=None,autorizacao_id=None)
        ed_site_refinement.save(old)
    state=client.get(base+'/estudio').json
    fields={k:state[k] for k in ('revisao','secoes','quantidade','modo')}
    fields['direcao']={k:v for k,v in state['direcao'].items() if k not in ('versao','estado')}
    fields['direcao']['estilo']='Direção substituída pelo operador'
    assert client.put(base+'/estudio',json=fields).status_code==200
    assert client.post(base+'/refinamento-site/'+s['id']+'/continuar',json={}).status_code==409
    assert client.get(base+'/refinamento-site/'+s['id']).json['chat_id']==s['chat_id']


def test_initial_flow_binding_recovery_keeps_single_brief_message(client):
    import hashlib,ed_store,ed_site_refinement
    a,v,base=selected(client)
    s=client.post(base+'/refinamento-site',json={'projeto_id':'','variante_id':v['id']}).json
    key='adaptativo-construcao:'+a['id']+':'+hashlib.sha256(('studio:'+s['id']).encode()).hexdigest()[:32]
    with client.application.app_context(),ed_store.conectar() as con:
        cached=json.loads(con.execute('SELECT valor FROM ed_config WHERE chave=?',(key,)).fetchone()['valor'])
        cached.pop('resultado')
        con.execute('UPDATE ed_config SET valor=? WHERE chave=?',(json.dumps(cached),key))
        con.commit()
        value=ed_site_refinement.get(a['id'],s['id']);value['execucao_id']=None;ed_site_refinement.save(value)
    resumed=client.post(base+'/refinamento-site/'+s['id']+'/continuar',json={})
    assert resumed.status_code==202,resumed.json
    assert resumed.json['execucao_id']==s['execucao_id']
    assert len([m for m in resumed.json['mensagens'] if m.get('origem')=='brief_revisado'])==1


def test_studio_and_commands_respect_workspace_and_readonly_role(client):
    from test_ed_access import activate
    a,v,base=selected(client)
    s=client.post(base+'/refinamento-site',json={'projeto_id':'','variante_id':v['id']}).json
    headers=activate(client)
    workspace=client.post('/api/ed/acesso/workspaces',headers=headers,json={'nome':'Outro workspace'}).json
    assert client.post('/api/ed/acesso/workspace',headers=headers,json={'id':workspace['id']}).status_code==200
    assert client.get(base+'/refinamento-site/'+s['id']).status_code==404
    assert client.post('/api/ed/assistente/conversas/'+s['chat_id']+'/mensagens',headers=headers,json={'texto':'Não vazar contexto.','chave':'cross-workspace'}).status_code==404
    assert client.post('/api/ed/acesso/workspace',headers=headers,json={'id':'principal'}).status_code==200
    client.post('/api/ed/acesso/usuarios',headers=headers,json={'nome':'leitor','senha':'senha leitor segura','papel':'leitura'})
    client.post('/api/ed/acesso/sair',headers=headers)
    client.post('/api/ed/acesso/login',json={'nome':'leitor','senha':'senha leitor segura'})
    headers={'X-EDY-CSRF':client.get('/api/ed/acesso/sessao').json['csrf']}
    assert client.get(base+'/refinamento-site/'+s['id']).status_code==200
    assert client.post(base+'/refinamento-site/'+s['id']+'/continuar',headers=headers,json={}).status_code==403
    assert client.put(base+'/refinamento-site/'+s['id']+'/rascunho',headers=headers,json={'texto':'Sem permissão'}).status_code==403
