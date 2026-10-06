"""Sessão de trabalho: coordena a fila existente, sem outro executor de código.

SQLite guarda intenção, comandos e bases. Uma resposta só altera a versão corrente
se a base/época ainda corresponderem: restaurar invalida a aplicação tardia.
"""
import copy
import json
from flask import current_app, g, jsonify, request
from werkzeug.exceptions import Conflict, Forbidden
import ed_store as store
import ed_assistant as assistant
import ed_workflows as workflows
import ed_visual_studio as visual

PREFIX='refinamento-site:'
SUCCESS=('concluida','parcial')
BUSY=('na_fila','executando')


def save(value):
    value['atualizado_em']=store.agora()
    with store.conectar() as con:
        con.execute('INSERT INTO ed_config VALUES (?,?) ON CONFLICT(chave) DO UPDATE SET valor=excluded.valor',(PREFIX+value['id'],json.dumps(value,ensure_ascii=False)))
    return value


def get(company, ident):
    store.ler_empresa(company)
    with store.conectar() as con:row=con.execute('SELECT valor FROM ed_config WHERE chave=?',(PREFIX+ident,)).fetchone()
    value=json.loads(row['valor']) if row else None
    if not value or value['empresa_id']!=company:raise LookupError('Estúdio não pertence a esta empresa/workspace.')
    return value


def gaps(value):
    sections=[dict(id='pagina',titulo='Página inteira')] if value['escolhas'].get('pagina') else value['secoes']
    return [s['titulo'] for s in sections if not any(v['id']==value['escolhas'].get(s['id']) and v['direcao_versao']==value['direcao']['versao'] for v in value['variantes'])]


def open_studio(company, data):
    if not isinstance(data,dict) or set(data)!={'projeto_id','variante_id'}:raise ValueError('Escolha a proposta e o projeto na galeria.')
    from ed_adaptive import effective, source_hash
    with assistant.chat_lock:
        state=visual.read(company,data['projeto_id'])
        variant=next((v for v in state['variantes'] if v['id']==data['variante_id']),None)
        if not variant or state['escolhas'].get(variant['secao_id'])!=variant['id']:raise Conflict('Escolha esta composição antes de refinar o site.')
        if variant['direcao_versao']!=state['direcao']['versao']:raise Conflict('Esta proposta pertence à direção anterior; escolha uma versão atual.')
        brief=effective(company,state['projeto_id'])
        from ed_library import resolve
        signature=visual.digest(dict(empresa=company,projeto=state['projeto_id'],variante=variant['id'],direcao=state['direcao'],escolhas=state['escolhas'],brief=brief['versao'],fontes=source_hash(brief),contexto=resolve(company,state['projeto_id'])['snapshot']))
        with store.conectar() as con:rows=con.execute('SELECT valor FROM ed_config WHERE chave LIKE ?',(PREFIX+'%',)).fetchall()
        found=next((x for r in rows if (x:=json.loads(r['valor'])).get('assinatura')==signature),None)
        if found:return sync(found)
        ident=store.novo_id()
        chat=dict(id=store.novo_id(),titulo=brief['nome']+' · estúdio do site',criado_em=store.agora(),contexto=dict(empresa_id=company,geracao='codex_nativo',escopo=state['modo'],refinamento_site=ident),mensagens=[])
        assistant.save(chat)
        value=dict(id=ident,empresa_id=company,projeto_id=state['projeto_id'],variante_id=variant['id'],assinatura=signature,chat_id=chat['id'],brief_versao=brief['versao'],criado_em=store.agora(),estado='escolhas_pendentes',lacunas=gaps(state),autorizacao_id=None,execucao_id=None,atual=None,epoca=0,versoes=[],comandos=[],tentativas=[],rascunhos={},autor=copy.deepcopy(getattr(g,'actor',{})))
        save(value)
        return begin(value) if not value['lacunas'] else value


def begin(value):
    """Intenção gravada antes da chamada idempotente; reinício não duplica a base."""
    from ed_adaptive import effective, construct_reviewed
    state=visual.read(value['empresa_id'],value['projeto_id']);value['lacunas']=gaps(state)
    variant=next((v for v in state['variantes'] if v['id']==value['variante_id']),None)
    if not variant or state['escolhas'].get(variant['secao_id'])!=variant['id'] or variant['direcao_versao']!=state['direcao']['versao']:
        raise Conflict('A composição desta conversa mudou. Retorne à galeria e abra a proposta selecionada; comandos e versões anteriores permanecem salvos.')
    if value['lacunas']:return save(value)
    brief=effective(value['empresa_id'],value['projeto_id'])
    if brief['revisao']['documental'] not in ('conforme','com_pendencias'):raise Conflict('Registre a revisão documental do brief antes de construir. Pendências comerciais identificadas podem permanecer.')
    if not value['autorizacao_id']:
        authorization=visual.approve(value['empresa_id'],value['projeto_id'],dict(revisao=state['revisao'],brief_versao=brief['versao'],confirmar=True),working=True)
        value.update(autorizacao_id=authorization['id'],brief_versao=brief['versao']);save(value)
    instruction='Construa a composição selecionada inteira, da abertura ao rodapé, como prévia de trabalho. Use HTML semântico e responsivo com textos, máscaras, mosaicos, links e controles reais, nunca screenshot integral com hotspots. A imagem candidata é direção visual, não fatos comerciais. Identifique fotos conceituais, wordmark provisório e informações pendentes. Preserve copy revisada, fontes e edições manuais. Aplique a identidade e referências deste projeto com tipografia expressiva, recortes e contraste confortável. Não reutilize templates reprovados. Sem publicação ou envio. Modelo GPT-6.1 Sol, raciocínio Alto, velocidade Padrão.'
    result=construct_reviewed(value['empresa_id'],dict(versao=value['brief_versao'],projeto_id=value['projeto_id'],chave='studio:'+value['id'],composicao_id=value['autorizacao_id'],instrucoes=instruction),existing_chat=assistant.conversation(value['chat_id']))
    value.update(estado='construindo',execucao_id=result['execucao_id'],exportacao_id=result['exportacao_id'])
    if not any(t['execucao_id']==result['execucao_id'] for t in value['tentativas']):value['tentativas'].append(dict(execucao_id=result['execucao_id'],tipo='primeira_previa',base=None,epoca=value['epoca'],criado_em=store.agora(),estado='na_fila'))
    return save(value)


def enqueue(chat, message):
    """Contrato do compositor existente; mensagem já validada, incluindo STT revisada."""
    value=get(chat['contexto']['empresa_id'],chat['contexto']['refinamento_site'])
    if len(value['comandos'])>=100:raise ValueError('Limite de 100 comandos nesta sessão; versões preservadas.')
    command={**copy.deepcopy(message),'estado_fila':'aguardando_base' if not value['atual'] else 'na_fila'}
    value['comandos'].append(command);save(value)
    message['estado_fila']=command['estado_fila'];assistant.save(chat)
    sync(value)
    return next(x for x in assistant.conversation(chat['id'])['mensagens'] if x['id']==message['id'])


def sync(value, *, dispatch=True):
    """Reconcilia checkpoints. Leitura simples nunca inicia provedor; scheduler é o escritor."""
    with assistant.chat_lock:
        value=get(value['empresa_id'],value['id']);before=copy.deepcopy(value);changed=False
        chat=assistant.conversation(value['chat_id'])
        # A mensagem é persistida pelo compositor antes de entrar no coordenador.
        # Recuperar a janela entre esses dois checkpoints mantém texto e STT.
        for message in chat['mensagens']:
            if message['papel']=='usuario' and message.get('chave') and not any(c['id']==message['id'] for c in value['comandos']):
                command={**copy.deepcopy(message),'estado_fila':'na_fila' if value['atual'] else 'aguardando_base'}
                value['comandos'].append(command);message['estado_fila']=command['estado_fila'];changed=True
        # Crash entre intenção e ligação da execução: consultar a chave persistida,
        # nunca disparar outro executor nem perder o comando.
        for command in value['comandos']:
            if command['estado_fila']!='executando' or any(t.get('comando_id')==command['id'] for t in value['tentativas']):continue
            with store.conectar() as con:row=con.execute('SELECT dados FROM ed_fluxos WHERE chave=?',('studio-comando:'+command['id'],)).fetchone()
            if row:
                flow=json.loads(row['dados']);command['execucao_id']=flow['id']
                value['tentativas'].append(dict(execucao_id=flow['id'],comando_id=command['id'],tipo='refinamento',base=command['base'],epoca=command['epoca'],criado_em=command['criado_em'],estado=flow['estado']))
            else:command['estado_fila']='na_fila'
            message=next(m for m in chat['mensagens'] if m['id']==command['id']);message['estado_fila']=command['estado_fila'];changed=True
        for attempt in value['tentativas']:
            flow=workflows.get(attempt['execucao_id']);attempt['estado']=flow['estado']
            if attempt.get('comando_id'):
                command=next(c for c in value['comandos'] if c['id']==attempt['comando_id'])
                if not attempt.get('reconciliada'):
                    command['estado_fila']='executando' if flow['estado'] in BUSY else 'aguardando_recuperacao'
                    next(m for m in chat['mensagens'] if m['id']==command['id'])['estado_fila']=command['estado_fila'];changed=True
            if attempt.get('reconciliada') or flow['estado'] not in SUCCESS:continue
            built=next((s for s in flow['etapas'] if s['nome'] in ('gerar','refinar') and s['estado']=='concluida'),None)
            checked=next((s for s in flow['etapas'] if s['nome']=='verificar' and s['estado']=='concluida'),None)
            if not built or not checked:continue
            from ed_services import ler_job
            operation=ler_job(built['resultado']['construcao_id'])
            if operation['empresa_id']!=value['empresa_id'] or operation['estado']!='concluida':raise ValueError('Resultado incompleto ou de outra empresa; nada aplicado.')
            result=operation['resultado'];ident=operation['id']
            if not any(v['id']==ident for v in value['versoes']):
                value['versoes'].append(dict(id=ident,base=attempt['base'],numero=len(value['versoes'])+1,execucao_id=flow['id'],comando_id=attempt.get('comando_id'),criado_em=store.agora(),modelo=result.get('modelo'),fornecedor=operation['fornecedor'],build=result.get('build_estatico'),arquivos=result.get('arquivos',[]),arquivos_devolvidos=result.get('arquivos_devolvidos',[]),arquivos_herdados=result.get('arquivos_herdados',[]),contexto_executor=result.get('contexto_executor'),brief_versao=value['brief_versao'],autorizacao_id=value['autorizacao_id'],pendencias=result.get('pendencias',[])))
            applicable=value['epoca']==attempt['epoca'] and value['atual']==attempt['base']
            if applicable:
                value['atual']=ident;value['epoca']+=1
                chat['contexto'].update(construcao_id=ident,projeto_ativo=dict(id=ident,empresa_id=value['empresa_id'],escopo=chat['contexto'].get('escopo','previa')))
            attempt.update(reconciliada=True,aplicada=applicable,versao_id=ident)
            if attempt.get('comando_id'):
                next(c for c in value['comandos'] if c['id']==attempt['comando_id']).update(estado_fila='concluida',versao_id=ident)
                next(m for m in chat['mensagens'] if m['id']==attempt['comando_id']).update(estado_fila='concluida',versao_id=ident)
            changed=True
        active=next((t for t in reversed(value['tentativas']) if t['estado'] in BUSY),None)
        blocked=next((t for t in reversed(value['tentativas']) if not t.get('reconciliada') and t['estado'] not in SUCCESS+BUSY),None)
        value['estado']='construindo' if active and not value['atual'] else 'refinando' if active else blocked['estado'] if blocked else 'pronta' if value['atual'] else 'escolhas_pendentes'
        if changed:assistant.save(chat)
        if value!=before:save(value)
        queued=next((c for c in value['comandos'] if c['estado_fila'] in ('na_fila','aguardando_base')),None)
        if dispatch and value['atual'] and queued and not active and not blocked:
            # Autorização reavaliada pelo worker; nenhuma identidade vem do modelo.
            g.actor=copy.deepcopy(value['autor'])
            workflows.still_authorized(dict(autor=value['autor']['id'],workspace=value['autor']['workspace'],papel=value['autor']['papel']))
            plan=dict(acao='refinar',empresa_id=value['empresa_id'],construcao_id=value['atual'],geracao='codex_nativo',escopo=chat['contexto'].get('escopo','previa'),instrucoes=queued['texto']+'\nAlteração localizada: preserve todo arquivo e seção não mencionados. Não regenere imagens para uma alteração de CSS. Fatos ausentes permanecem pendentes; imagens conceituais identificadas. Sem publicar ou enviar.')
            # Intento existe antes do dispatch; chave do comando recupera a mesma execução.
            queued.update(estado_fila='executando',base=value['atual'],epoca=value['epoca']);message=next(m for m in chat['mensagens'] if m['id']==queued['id']);message.update(estado_fila='executando',plano=plan)
            chat['contexto']['construcao_id']=value['atual'];assistant.save(chat);save(value)
            flow=workflows.start(plan,'studio-comando:'+queued['id'],chat=value['chat_id'])
            queued['execucao_id']=flow['id'];message['execucao_id']=flow['id'];assistant.save(chat)
            value['tentativas'].append(dict(execucao_id=flow['id'],comando_id=queued['id'],tipo='refinamento',base=value['atual'],epoca=value['epoca'],criado_em=store.agora(),estado=flow['estado']))
            value.update(estado='refinando',execucao_id=flow['id']);save(value)
        return value


def context_review(value):
    """Detecta mudanças sem autorizar, reexportar ou iniciar execução durante leitura."""
    if not value.get('autorizacao_id'):return None
    from ed_library import resolve,items
    state=visual.read(value['empresa_id'],value['projeto_id'])
    previous=next((a for a in state['aprovacoes']+state.get('autorizacoes_trabalho',[]) if a['id']==value['autorizacao_id']),None)
    if not previous:return None
    current=resolve(value['empresa_id'],value['projeto_id'])['snapshot']
    if previous['contexto_snapshot']==current:return None
    titles={x['id']:x['titulo'] for x in items()}
    old={x['id']:x for x in previous['contexto_snapshot']};new={x['id']:x for x in current}
    changes=[dict(titulo=titles.get(ident,'Referência preservada no histórico'),situacao='removido' if ident not in new else 'adicionado' if ident not in old else 'atualizado',versao=new.get(ident,old.get(ident))['versao']) for ident in sorted(old.keys()|new.keys()) if old.get(ident)!=new.get(ident)]
    return dict(autorizacao_id=previous['id'],contexto_hash=visual.digest(current),alteracoes=changes)


def renew_context(value,data):
    """Clique explícito atualiza somente o contexto de uma montagem e brief inalterados."""
    if not isinstance(data,dict) or set(data)!={'autorizacao_id','contexto_hash'}:raise ValueError('Revise as alterações de contexto exibidas no estúdio.')
    if any(workflows.get(t['execucao_id'])['estado'] in BUSY for t in value['tentativas']):raise Conflict('Aguarde ou pause a execução antes de revisar o contexto.')
    review=context_review(value)
    if not review:return value
    if any(data[k]!=review[k] for k in data):raise Conflict('O contexto mudou novamente; confira as alterações atuais.')
    # Só a igualdade do contexto revisado é dispensada. Brief/fontes, montagem
    # corrente e hashes das imagens continuam obrigatórios.
    old=visual.approval(value['empresa_id'],value['projeto_id'],value['autorizacao_id'],current=True,check_context=False)
    state=visual.read(value['empresa_id'],value['projeto_id'])
    renewed=visual.approve(value['empresa_id'],value['projeto_id'],dict(revisao=state['revisao'],brief_versao=old['brief_versao'],confirmar=True),working=True)
    value.setdefault('revisoes_contexto',[]).append(dict(anterior=old['id'],atual=renewed['id'],alteracoes=review['alteracoes'],criado_em=store.agora(),operador=g.actor['id']))
    value['autorizacao_id']=renewed['id']
    chat=assistant.conversation(value['chat_id']);chat['contexto']['composicao_visual']=renewed;assistant.save(chat)
    return save(value)


def response(value):
    value=copy.deepcopy(value)
    value['revisao_contexto']=context_review(value)
    from ed_preview import active_url
    for version in value['versoes']:version['url']=active_url(value['empresa_id'],version['id'])
    value['url']=next((v['url'] for v in value['versoes'] if v['id']==value['atual']),None)
    value['mensagens']=assistant.conversation(value['chat_id'])['mensagens']
    value['rascunho']=value.pop('rascunhos',{}).get(getattr(g,'actor',{}).get('id','local'),'')
    value.pop('autor',None)
    if value['execucao_id']:
        flow=workflows.get(value['execucao_id']);value['fluxo']=dict(estado=flow['estado'],mensagem=flow['mensagem'],etapas=flow['etapas'])
        child=next((s.get('operacao_id') for s in flow['etapas'] if s['estado']=='executando' and s.get('operacao_id')),None)
        if child:
            from ed_services import ler_job
            try:
                operation=ler_job(child)
                value['fluxo']['operacao']={k:operation.get(k) for k in ('id','estado','mensagem','progresso','fornecedor')}
                value['fluxo']['operacao']['modelo']=operation.get('parametros',{}).get('modelo')
            except LookupError:pass
    return value


def tick():
    with store.conectar() as con:rows=con.execute('SELECT valor FROM ed_config WHERE chave LIKE ?',(PREFIX+'%',)).fetchall()
    for row in rows:
        value=json.loads(row['valor'])
        try:
            g.actor=copy.deepcopy(value['autor'])
            sync(value)
        except (ValueError,LookupError,Conflict,Forbidden):current_app.logger.warning('Sessão de refinamento aguardando revisão: %s',value['id'])


def registrar(bp):
    @bp.post('/empresas/<company>/refinamento-site/<ident>/contexto')
    def refinement_context(company,ident):
        with assistant.chat_lock:
            return jsonify(response(renew_context(get(company,ident),request.get_json())))

    @bp.post('/empresas/<company>/refinamento-site')
    def refinement_open(company):return jsonify(response(open_studio(company,request.get_json()))),202

    @bp.get('/empresas/<company>/refinamento-site/<ident>')
    def refinement_get(company,ident):return jsonify(response(sync(get(company,ident),dispatch=False)))

    @bp.put('/empresas/<company>/refinamento-site/<ident>/rascunho')
    def refinement_draft(company,ident):
        data=request.get_json()
        if not isinstance(data,dict) or set(data)!={'texto'}:raise ValueError('Rascunho inválido.')
        with assistant.chat_lock:
            value=get(company,ident);value['rascunhos'][g.actor['id']]=store.texto(data['texto'],12000);save(value)
        return jsonify(salvo=True)

    @bp.post('/empresas/<company>/refinamento-site/<ident>/continuar')
    def refinement_continue(company,ident):
        with assistant.chat_lock:
            value=get(company,ident)
            if not value['execucao_id']:value=begin(value)
            else:workflows.action(value['execucao_id'],'retomar')
            return jsonify(response(sync(value))),202

    @bp.post('/empresas/<company>/refinamento-site/<ident>/restaurar')
    def refinement_restore(company,ident):
        data=request.get_json()
        if not isinstance(data,dict) or set(data)!={'versao_id'}:raise ValueError('Escolha uma versão desta sessão.')
        with assistant.chat_lock:
            value=get(company,ident)
            if not any(v['id']==data['versao_id'] for v in value['versoes']):raise LookupError('Versão não pertence a este estúdio.')
            from ed_services import ler_job
            version=ler_job(data['versao_id'])
            if version['estado']!='concluida' or version['empresa_id']!=company:raise Conflict('A versão deve estar concluída e pertencer à empresa.')
            value.update(atual=version['id'],epoca=value['epoca']+1)
            value.setdefault('restauracoes',[]).append(dict(versao_id=version['id'],operador=g.actor['id'],data=store.agora()))
            chat=assistant.conversation(value['chat_id']);chat['contexto']['construcao_id']=version['id'];assistant.save(chat);save(value)
            return jsonify(response(sync(value,dispatch=False)))
