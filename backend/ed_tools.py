"""Ferramentas do assistente: contratos fechados e regras partilhadas com a UI.

O modelo propõe parâmetros. Sessão, workspace, limites e execução são locais.
Não há ferramenta de SQL, shell, publicação ou envio de mensagens.
"""
import json
from flask import current_app
from werkzeug.exceptions import Conflict
import ed_store as store
import ed_crm

COMMANDS=('pesquisar','preparar','consultar','registro','enriquecer','exportar','alternativa','refinar_secao','gerar','refinar','material','contexto','execucao','lote')
ALLOWED={
 'pesquisar':{'nicho','cidade','uf','quantidade','objetivo','geracao','modo','instrucoes'},
 'preparar':{'empresa_id','objetivo','geracao','modo','instrucoes','escopo'},
 'lote':{'empresa_ids','geracao','instrucoes','exigir_confirmadas','escopo','concorrencia'},
 'consultar':{'q','sem_site'},
 'registro':{'tipo','registro_id','dados'},
 'enriquecer':{'empresa_id'},'exportar':{'empresa_id'},
 'alternativa':{'empresa_id','secao','alternativa'},'refinar_secao':{'empresa_id','secao','texto'},
 'gerar':{'empresa_id','instrucoes','escopo','geracao'},'refinar':{'empresa_id','instrucoes','construcao_id','escopo','geracao'},
 'material':{'empresa_id','material_id','selecionado'},'contexto':{'empresa_id','item_ids'},
 'execucao':{'execucao_id','comando'},
}

def validate_plan(plan):
    if not isinstance(plan,dict) or plan.get('acao') not in COMMANDS:raise ValueError('Ferramenta desconhecida.')
    action=plan['acao']
    unknown=set(plan)-ALLOWED[action]-{'acao'}
    if unknown:raise ValueError('Parâmetros não permitidos para '+action+': '+', '.join(sorted(unknown))+'.')
    out=dict(plan)
    if action=='pesquisar':
        import ed_search
        amount=plan.get('quantidade',2)
        if type(amount)!=int or not 1<=amount<=25:raise ValueError('Pesquise entre 1 e 25 leads. Acima de cinco, selecione as empresas antes de criar o lote.')
        ed_search.validar(dict(nicho=plan.get('nicho'),cidade=plan.get('cidade'),uf=plan.get('uf'),limite=amount))
        out['quantidade']=amount
    if action in ('preparar','pesquisar'):
        out.setdefault('geracao','templates');out.setdefault('modo','automatico')
        if out['geracao'] not in ('templates','codex_nativo','openrouter','opencode','gateway') or out['modo'] not in ('assistido','automatico'):raise ValueError('Modo ou geração inválidos; nenhuma cobrança API é escolhida pelo assistente.')
    if 'escopo' in out and out['escopo'] not in ('previa','completo'):raise ValueError('Escolha prévia ou site completo.')
    if action=='lote':
        ids=out.get('empresa_ids')
        if not isinstance(ids,list) or not 1<=len(ids)<=5 or len(set(ids))!=len(ids):raise ValueError('Selecione até cinco empresas distintas.')
        for ident in ids:store.ler_empresa(ident)
        if out.get('geracao','codex_nativo') not in ('codex_nativo','openrouter','opencode','templates','gateway'):raise ValueError('Motor inválido.')
        if type(out.get('concorrencia',1))!=int or not 1<=out.get('concorrencia',1)<=2:raise ValueError('Concorrência entre 1 e 2.')
    if 'empresa_id' in ALLOWED[action]:
        out['empresa_id']=store.texto(plan.get('empresa_id',''),80);store.ler_empresa(out['empresa_id'])
    for key in ('objetivo','instrucoes','texto','q'):
        if key in out:out[key]=store.texto(out[key],12000 if key=='instrucoes' else 4000)
    if 'sem_site' in out:store.booleano(out['sem_site'])
    if action=='registro':
        if plan.get('tipo') not in ed_crm.FIELDS or not isinstance(plan.get('dados'),dict):raise ValueError('Registro inválido.')
        if plan.get('registro_id'):ed_crm.get(plan['registro_id'])
    if action=='alternativa' and plan.get('alternativa') not in ('a','b','c','d'):raise ValueError('Alternativa deve ser a, b, c ou d.')
    if action=='material':
        store.booleano(plan.get('selecionado'))
        if not any(m['id']==plan.get('material_id') for m in store.ler_empresa(out['empresa_id'])['materiais']):raise LookupError('Material não pertence ao lead.')
    if action=='contexto':
        import ed_library
        ids=plan.get('item_ids')
        if not isinstance(ids,list) or len(ids)>30:raise ValueError('Seleção inválida.')
        lead=store.ler_empresa(out['empresa_id'])
        if any(not ed_library.eligible(ed_library.get(i),lead) for i in ids):raise ValueError('Contexto fora do escopo ou inativo.')
    if action=='execucao':
        from ed_workflows import get
        get(plan.get('execucao_id'))
        if plan.get('comando') not in ('pausar','cancelar','retomar'):raise ValueError('Comando de execução inválido.')
    return out

def steps(plan):
    if plan['acao']=='pesquisar' and plan.get('quantidade',2)>5:return ['pesquisar']
    if plan['acao'] in ('pesquisar','preparar'):
        return (['pesquisar'] if plan['acao']=='pesquisar' else [])+['organizar','enriquecer','preparar','compor','exportar','gerar','verificar','prospeccao']
    if plan['acao'] in ('gerar','refinar'):return ['exportar',plan['acao'],'verificar','prospeccao']
    return [plan['acao']]

def previous(job,name):
    return next((s['resultado'] for s in job['etapas'] if s['nome']==name and s.get('resultado')),None)

def company(job):
    result=previous(job,'organizar')
    ident=result['empresa_id'] if result else job['plano'].get('empresa_id')
    return store.ler_empresa(ident)

def child_step(job,index,create,reader):
    from ed_workflows import lock,get,checkpoint,wait_child
    with lock:
        step=get(job['id'])['etapas'][index]
        if step.get('operacao_id'):ident=step['operacao_id']
        else:
            value=create();ident=value['id'];checkpoint(job['id'],index,operacao_id=ident)
    if step['nome'] in ('gerar','refinar') and step.get('tentativas',0)>1:
        from ed_tasks import retry_generation,running
        import time
        deadline=time.monotonic()+30
        while ident in running and reader(ident)['estado'] in ('cancelada','erro') and time.monotonic()<deadline:
            from ed_workflows import check
            check(job['id']);time.sleep(.2)
        retry_generation(ident)
    return wait_child(job,index,ident,reader)

def prospect(company_id,construction_id=None):
    lead=store.ler_empresa(company_id)
    previews=lead['previas'];confirmed={k:v['valor'] for k,v in lead['fontes'].items() if v.get('verificacao')=='confirmado_usuario'}
    identity=lead['nome']
    selected=next((x for x in previews if x.get('construcao_id')==construction_id),None) if construction_id else (previews[0] if previews else None)
    preview=selected['url'] if selected else '[link da prévia a registrar]'
    location=', '.join(filter(None,(lead['bairro'],lead['cidade'])))
    detail=' Os serviços revisados foram organizados para facilitar a escolha: '+confirmed['servicos'][:240]+'.' if confirmed.get('servicos') else ' Deixei espaço para vocês confirmarem modalidades e diferenciais, sem inventar ofertas.'
    message=f'Olá, equipe {identity}. Encontrei o cadastro de vocês'+(' em '+location if location else '')+f' e preparei uma proposta de apresentação digital para {identity}.{detail} Posso mostrar a prévia ({preview}) e ouvir o que gostariam de ajustar? Ainda não foi publicada.'
    version=next((x for x in previews if x.get('url')==preview),{})
    result=dict(inicial=message,whatsapp=message,email_assunto='Prévia personalizada para '+identity+(' · '+lead['cidade'] if lead['cidade'] else ''),email=message+'\n\nMinha proposta é organizar identidade, informações e caminho de contato numa página própria. Fotos, canais e pendências comerciais serão revisados com vocês antes de compartilhar ou publicar.',resumo='Proposta específica para '+identity+'; cadastro em '+(location or 'localização pendente')+'.',acompanhamento='Olá, equipe '+identity+'! Faz sentido conversarmos sobre a proposta de apresentação em '+(location or 'sua região')+'? Posso adaptar a prévia à identidade de vocês.',construcao_id=version.get('construcao_id'),previa_id=version.get('id'),url_previa=preview,contatos_confirmados={k:confirmed[k] for k in ('telefone','email') if k in confirmed},enviado=False,pendencias=lead['pendencias'])
    from urllib.parse import urlsplit
    candidate=lead.get('site','');host=urlsplit(candidate).hostname or ''
    if lead.get('associacao_site',{}).get('estado')=='confirmado' and confirmed.get('site'):
        observation='Considerei o site associado e confirmado no CRM para preparar uma nova direção visual. A proposta mantém as informações revisadas e permite comparar apresentação, navegação e contato com a presença atual.'
    elif 'instagram.com' in host:
        observation='O cadastro aponta um perfil social candidato; a proposta organiza uma página própria para apresentar a empresa e centralizar o contato, após confirmar esse vínculo.'
    elif 'matricula' in urlsplit(candidate).path.lower():
        observation='Há um link candidato de matrícula no cadastro. A proposta apresenta a empresa antes desse passo; confirmaremos a associação e a jornada de inscrição com vocês.'
    elif candidate:
        observation='O cadastro inclui um endereço de site candidato. Preparei uma direção alternativa para comparar com a presença atual, depois de confirmar que esse endereço pertence à empresa.'
    else:
        observation='Não havia um site confirmado no cadastro consultado. A proposta cria um ponto de apresentação e contato próprio; podemos confirmar juntos o canal que vocês já utilizam.'
    proposed=[]
    if version.get('construcao_id'):
        from ed_runtime import artefact_root
        from lxml import html as html_parser
        path=artefact_root(company_id,version['construcao_id'])/'index.html'
        if path.is_file():
            page=html_parser.fromstring(path.read_bytes(),parser=html_parser.HTMLParser(no_network=True,encoding='utf-8'))
            proposed=[' '.join(' '.join(h.itertext()).split())[:160] for h in page.xpath('//main//h1 | //main//h2')][:7]
    locality=('O cadastro indica '+location+'; a localização ainda precisa ser conferida. ' if location and not lead['confirmado'] else ('A proposta considera '+location+'. ' if location else ''))
    short=f'Olá, equipe {identity}. Preparei uma prévia para vocês. '+locality+observation+' Posso mostrar e ouvir os ajustes? '+preview
    detailed=short+'\n\n'+('A composição proposta trabalha estas seções: '+ ' / '.join(proposed)+'.\n' if proposed else '')+detail.strip()+' Fotos, identidade, localização e contatos serão revisados com vocês antes de compartilhar. Não é uma página oficial nem foi publicada.'
    result.update(inicial=short,whatsapp=short,email=detailed,resumo=observation,secoes_propostas=proposed,observacao_cadastral=observation)
    with store.conectar() as con:
        prior=con.execute('SELECT valor FROM ed_config WHERE chave=?',('prospeccao:'+company_id,)).fetchone()
        if prior:
            revised=json.loads(prior['valor'])
            if revised.get('revisado_em'):
                result.update({k:revised[k] for k in ('inicial','whatsapp','email_assunto','email','resumo','acompanhamento','revisado_em') if k in revised})
                if revised.get('construcao_id') and revised['construcao_id']!=result.get('construcao_id'):
                    result['nova_versao_para_revisar']={k:result.get(k) for k in ('construcao_id','previa_id','url_previa')}
                    result.update({k:revised[k] for k in ('construcao_id','previa_id','url_previa') if k in revised})
        con.execute('INSERT INTO ed_config VALUES (?,?) ON CONFLICT(chave) DO UPDATE SET valor=excluded.valor',('prospeccao:'+company_id,json.dumps(result,ensure_ascii=False)))
    return result

def execute_step(job,index):
    from ed_workflows import Waiting,checkpoint,lock,get
    p=job['plano'];name=job['etapas'][index]['nome'];app=current_app._get_current_object();key=job['id']+':'+name
    if name=='lote':
        from ed_batches import start_batch
        result=start_batch({k:v for k,v in p.items() if k!='acao'}|{'chave':key})
        return dict(lote_id=result['id'],pendencias=['Lote iniciado. As prévias só estarão prontas após geração e renderização de cada empresa.'])
    if name=='pesquisar':
        import ed_search
        if not store.config()['osm_habilitado']:raise Waiting('OpenStreetMap desativado. Ative a fonte em Configurações → Conexões e retome.')
        result=child_step(job,index,lambda:ed_search.iniciar(dict(nicho=p['nicho'],cidade=p['cidade'],uf=p['uf'],limite=p['quantidade']),app,idempotency_key=key),ed_search.ler)
        if not result['empresa_ids']:raise Waiting('A pesquisa não encontrou empresas. Confira nicho/localidade ou fonte; coleta vazia não conclui o fluxo.')
        return dict(empresa_ids=result['empresa_ids'],fonte='OpenStreetMap',campanha_id=result['id'],pendencias=['Identidade e dados obtidos do mapa exigem revisão.'])
    if name=='organizar':
        acquired=previous(job,'pesquisar');ids=acquired['empresa_ids'] if acquired else [p['empresa_id']]
        leads=[store.ler_empresa(i) for i in ids]
        # Escolha reproduzível pelo volume de informações, sem auto-confirmar identidade.
        generic={'academia','padaria','restaurante','salao','cafe','hotel','clinica','barbearia','farmacia'}
        leads.sort(key=lambda x:(x['confirmado'],store.normalizar(x['nome']) not in generic,sum(bool(x.get(k)) for k in ('descricao','telefone','site','endereco','servicos'))),reverse=True)
        created=[]
        for lead in leads:
            found=next((x for x in ed_crm.list_records('oportunidade',lead['id']) if x['origem']=='fluxo:'+job['id']),None)
            if not found:found=ed_crm.save('oportunidade',dict(empresa_id=lead['id'],titulo='Prévia · '+lead['nome'],origem='fluxo:'+job['id'],tags=['piloto','revisar-identidade']))
            created.append(found['id'])
        return dict(empresa_id=leads[0]['id'],nome=leads[0]['nome'],oportunidade_ids=created,duplicatas={x['id']:x['possiveis_duplicatas'] for x in leads},associacao=leads[0]['associacao_site'],pendencias=[] if leads[0]['confirmado'] else ['Associação cadastral ainda não confirmada; fatos não revisados serão omitidos da página.'])
    if name=='consultar':
        values=[x for x in store.listar_empresas() if not x.get('crm_arquivada') and store.normalizar(p.get('q','')) in store.normalizar(x['nome']+' '+x['nicho']+' '+x['cidade']) and (not p.get('sem_site') or x['associacao_site']['estado']!='confirmado')]
        return dict(empresas=[{k:x[k] for k in ('id','nome','cidade','site','nicho')} for x in values[:50]],total=len(values))
    if name=='registro':
        step=get(job['id'])['etapas'][index]
        if step.get('registro_id'):return ed_crm.get(step['registro_id'])
        with lock:
            result=ed_crm.save(p['tipo'],p['dados'],p.get('registro_id'),idempotency_key=key);checkpoint(job['id'],index,registro_id=result['id'])
        return result
    if name=='execucao':
        from ed_workflows import action
        return action(p['execucao_id'],p.get('comando','pausar'))
    if name=='enriquecer':
        import ed_enrich
        lead=company(job)
        if lead['associacao_site']['estado']!='confirmado':return dict(paginas=0,pendencias=['Sem site associado e confirmado. Consulte Instagram autorizado ou envie materiais; não foi realizada leitura.'])
        result=child_step(job,index,lambda:ed_enrich.iniciar(lead['id'],dict(site_confirmado=True,site=lead['site'],fornecedor='site_local'),app,idempotency_key=key),ed_enrich.ler_job)
        return dict(pesquisa_id=result['id'],paginas=len(result['paginas']),sugestoes=len(result['sugestoes']),imagens_candidatas=len(result['imagens']),pendencias=['Sugestões e direitos das imagens aguardam revisão.']+result.get('pendencias',[]),mensagem=result['mensagem'],erros=result.get('erros',[]))
    if name=='preparar':
        import ed_preparation,ed_library
        lead=company(job);value=ed_preparation.ler(lead['id'])
        # Salvar somente defaults ainda não persistidos. Nunca substituir decisões manuais.
        with store.conectar() as con:exists=con.execute('SELECT 1 FROM ed_preparacoes WHERE empresa_id=?',(lead['id'],)).fetchone()
        if not exists:
            if p.get('objetivo'):value['objetivo']=p['objetivo']
            ed_preparation.salvar(lead['id'],value)
        import ed_adaptive
        dossier=ed_adaptive.prepare(lead['id'],cache='adaptativo-fluxo:'+key)
        resolved=ed_library.resolve(lead['id'])
        return dict(empresa_id=lead['id'],contexto=resolved['snapshot'],revisao=ed_preparation.ler(lead['id'])['revisao'],brief_adaptativo_versao=dossier['versao'],pendencias=ed_preparation.pendencias(lead,value))
    if name=='compor':
        import ed_composition
        lead=company(job);value=ed_composition.ler(lead['id'])
        if not value['revisao']:ed_composition.salvar(lead['id'],value)
        return dict(revisao=ed_composition.ler(lead['id'])['revisao'],secoes=[dict(id=x['id'],tipo=x['tipo'],escolhida=x['escolhida'],alternativas=len(x['alternativas'])) for x in value['secoes']],pendencias=['Alternativas por templates; escolhas mantidas. Textos e direitos continuam sujeitos a revisão.'])
    if name in ('alternativa','refinar_secao'):
        import ed_composition
        lead=company(job);value=ed_composition.ler(lead['id']);section=next((s for s in value['secoes'] if s['id']==p.get('secao')),None)
        if not section:raise ValueError('Seção inexistente; use o ID exibido na composição.')
        if section['fixada']:raise Conflict('Seção fixada. Desfixe na composição antes de refinar.')
        if name=='alternativa':section['escolhida']=p['alternativa']
        else:
            chosen=next(x for x in section['alternativas'] if x['id']==section['escolhida'])
            chosen.update(instrucoes=p['texto'],revisado=False,versao=chosen['versao']+1)
        result=ed_composition.salvar(lead['id'],value)
        if result is None:raise Conflict('Composição mudou durante edição; recarregue.')
        return dict(empresa_id=lead['id'],secao=section['id'],escolhida=section['escolhida'],revisao=result['revisao'],pendencias=['Instrução de refinamento registrada; use Construir prévia para aplicar pelo Codex.'] if name=='refinar_secao' else [])
    if name=='exportar':
        import ed_export
        with lock:
            lead=company(job)
            adaptive_files=None
            visual=None
            if job.get('chat_id'):
                from ed_assistant import conversation
                from ed_adaptive import effective,source_hash,export_value,applicable,project_key
                pin=conversation(job['chat_id'])['contexto'].get('brief_adaptativo')
                visual=conversation(job['chat_id'])['contexto'].get('composicao_visual')
                if pin:
                    project=p.get('construcao_id','')
                    if source_hash(effective(lead['id'],pin['dossier']['projeto_id']))!=pin['fontes_hash']:
                        raise Conflict('Fontes ou materiais do brief selecionado mudaram. Revise o brief e crie uma nova conversa; versões anteriores preservadas.')
                    if p['acao']=='gerar':
                        import ed_library
                        if ed_library.resolve(lead['id'],pin['dossier']['projeto_id'])['snapshot']!=pin['contexto_snapshot']:
                            raise Conflict('Regras ou referências do brief selecionado mudaram na fila. Revise novamente; nenhuma construção foi iniciada.')
                        result=next(x for x in lead['exportacoes'] if x['id']==pin['exportacao_id'])
                        checkpoint(job['id'],index,exportacao_id=result['id']);return result
                    value={**pin['dossier'],'projeto_id':project_key(lead['id'],project),'correcoes_aplicaveis':applicable(lead['id'],project)}
                    adaptive_files=export_value(value)
            result=ed_export.exportar(lead['id'],idempotency_key=key,project_id=p.get('construcao_id',''),adaptive_files=adaptive_files,visual_approval=visual);checkpoint(job['id'],index,exportacao_id=result['id'])
        return result
    if name in ('gerar','refinar'):
        import ed_runtime,ed_tasks,ed_services
        lead=company(job);export=previous(job,'exportar')
        if not export:
            export=ed_export_latest(lead)
        mode=p.get('geracao','codex_nativo' if p['acao'] in ('gerar','refinar') else 'templates')
        if p.get('modo')=='assistido':return dict(pendencias=['Modo assistido: pacote pronto; geração fica disponível na ficha.'],exportacao_id=export['id'])
        if mode=='templates':
            from ed_projects import build
            params=dict(exportacao_id=export['id'],modo='previa',modulos=[])
            result=child_step(job,index,lambda:ed_tasks.iniciar('local','projeto_funcional',lead['id'],params,build,idempotency_key=key),ed_services.ler_job)
        else:
            params=dict(exportacao_id=export['id'],modo='plano',modelo='gpt-6.1-sol',instrucoes=p.get('instrucoes','Crie a prévia com o contexto do pacote. Preserve fatos revisados, materiais permitidos e placeholders identificados. GPT-6.1 Sol; Alto; Padrão.'),anterior=p.get('construcao_id',''),escopo=p.get('escopo','previa'),motor=mode)
            if job.get('chat_id'):
                from ed_assistant import execution_context
                params['conversa_snapshot']=execution_context(job['chat_id'])
            from ed_creation_providers import generate as create_with_policy
            result=child_step(job,index,lambda:ed_tasks.iniciar('codex' if mode=='codex_nativo' else mode,'codex_construcao',lead['id'],params,create_with_policy,idempotency_key=key),ed_services.ler_job)
        return dict(construcao_id=result['id'],tipo=result['tipo'],resultado=result.get('resultado'),modelo='gpt-6.1-sol' if mode!='templates' else 'sem IA',pendencias=(result.get('resultado') or {}).get('pendencias',[]))
    if name=='verificar':
        import zipfile,hashlib
        export=previous(job,'exportar');lead=company(job)
        if not export:export=ed_export_latest(lead)
        path=store.arquivo_seguro('exportacoes',lead['id']+'/'+export['id']+'/pacote.zip')
        with zipfile.ZipFile(path) as archive:
            manifest=json.loads(archive.read('manifesto-pacote.json'))
            for x in manifest['arquivos']:
                if hashlib.sha256(archive.read(x['arquivo'])).hexdigest()!=x['sha256']:raise ValueError('Manifesto divergente: '+x['arquivo'])
        built=previous(job,'gerar') or previous(job,'refinar');url=None
        if built and built.get('construcao_id'):
            # Mesma implementação de serviço/associação usada pelo botão da ficha.
            endpoint='ed.runtime_open' if built['tipo']=='codex_construcao' else 'ed.open_project'
            response=current_app.view_functions[endpoint](lead['id'],built['construcao_id'])
            url=response.get_json()['url']
            preview=next((x for x in store.ler_empresa(lead['id'])['previas'] if x.get('construcao_id')==built['construcao_id']),None)
            for ident in (previous(job,'organizar') or {}).get('oportunidade_ids',[]):
                opportunity=ed_crm.get(ident)
                if opportunity['empresa_id']!=lead['id']:continue
                changes={}
                if not opportunity['pacote_id']:changes['pacote_id']=export['id']
                if preview and not opportunity['previa_id']:changes['previa_id']=preview['id']
                if changes:ed_crm.save('oportunidade',{**opportunity,**changes},ident,idempotency_key=key+':'+ident)
        miniature=None;warnings=['Integridade validada; revisão visual, identidade e aprovação do titular continuam necessárias.']
        if built and url:
            from ed_preview import thumbnail
            try:miniature=thumbnail(lead['id'],built['construcao_id'],url)
            except Exception as exc:
                warnings.append('Miniatura não capturada; abra a prévia para revisar. Nenhuma imagem demonstrativa substituiu o screenshot.')
                if isinstance(exc,ValueError):warnings.append(str(exc))
        return dict(arquivos_verificados=len(manifest['arquivos']),url=url,empresa_id=lead['id'],miniatura_url=miniature,pendencias=warnings)
    if name=='prospeccao':
        import ed_export
        ident=company(job)['id'];built=previous(job,'gerar') or previous(job,'refinar') or {};result=prospect(ident,built.get('construcao_id'))
        # A prévia já foi vinculada: o pacote final contém seu link e os textos revisados.
        adaptive_files=None;visual=None
        if job.get('chat_id'):
            from ed_assistant import conversation
            from ed_adaptive import export_value,applicable,project_key
            pin=conversation(job['chat_id'])['contexto'].get('brief_adaptativo')
            visual=conversation(job['chat_id'])['contexto'].get('composicao_visual')
            if pin:
                project=built.get('construcao_id','')
                adaptive_files=export_value({**pin['dossier'],'projeto_id':project_key(ident,project),'correcoes_aplicaveis':applicable(ident,project)})
        final=ed_export.exportar(ident,idempotency_key=key+':pacote-final',project_id=built.get('construcao_id',''),adaptive_files=adaptive_files,visual_approval=visual)
        initial=previous(job,'exportar') or {}
        for oid in (previous(job,'organizar') or {}).get('oportunidade_ids',[]):
            opportunity=ed_crm.get(oid)
            if opportunity['empresa_id']==ident and opportunity['pacote_id']==initial.get('id'):
                ed_crm.save('oportunidade',{**opportunity,'pacote_id':final['id']},oid,idempotency_key=key+':'+oid)
        result.update(exportacao_final=final['id'],zip_url=final['zip_url'],empresa_id=ident,miniatura_url=(previous(job,'verificar') or {}).get('miniatura_url'))
        return result
    if name=='material':
        lead=company(job);material=next(m for m in lead['materiais'] if m['id']==p['material_id'])
        if p['selecionado'] and not material['autorizado']:raise ValueError('Material com uso pendente não pode ser selecionado automaticamente.')
        with store.conectar() as con:
            row=con.execute('SELECT dados FROM ed_materiais WHERE id=?',(material['id'],)).fetchone();value=json.loads(row['dados']);value['selecionado']=p['selecionado'];con.execute('UPDATE ed_materiais SET dados=? WHERE id=?',(json.dumps(value,ensure_ascii=False),material['id']))
        return dict(material_id=material['id'],selecionado=p['selecionado'])
    if name=='contexto':
        import ed_library
        lead=company(job);sel=ed_library.selection(lead['id']);sel['selecionados']=p['item_ids']
        with store.conectar() as con:con.execute('INSERT INTO ed_config VALUES (?,?) ON CONFLICT(chave) DO UPDATE SET valor=excluded.valor',('biblioteca:'+lead['id'],json.dumps(sel)))
        return dict(contexto=ed_library.resolve(lead['id'])['snapshot'])
    raise ValueError('Etapa não implementada.')

def ed_export_latest(lead):
    if lead['exportacoes']:return lead['exportacoes'][0]
    from ed_export import exportar
    return exportar(lead['id'])
