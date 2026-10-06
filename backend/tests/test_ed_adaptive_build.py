import io
import json
import zipfile
from test_ed_enrich import client
from test_ed_adaptive import lead, analyze, construction


def reviewed(client, company):
    path='/api/ed/empresas/'+company+'/adaptativo'
    d=analyze(client,[company],company).json['resultados'][0]
    d=client.put(path,json={'versao':d['versao'],'proposta':{**d['proposta'],'objetivo':'Decisão manual exclusiva'}}).json
    return client.post(path+'/revisar',json={'versao':d['versao']}).json


def test_build_requires_current_review_and_preserves_manual_version(client):
    a=lead(client,'Piloto de teste');path='/api/ed/empresas/'+a['id']+'/adaptativo'
    d=analyze(client,[a['id']]).json['resultados'][0]
    assert client.post(path+'/construir',json={'versao':d['versao'],'projeto_id':'','chave':'without-review'}).status_code==409
    d=reviewed(client,a['id'])
    payload={'versao':d['versao'],'projeto_id':'','chave':'build-click'}
    r=client.post(path+'/construir',json=payload)
    assert r.status_code==202,r.json
    assert client.post(path+'/construir',json=payload).json==r.json
    chat=client.get('/api/ed/assistente/conversas/'+r.json['chat_id']).json
    pin=chat['contexto']['brief_adaptativo']
    assert pin['dossier']['proposta']['objetivo']=='Decisão manual exclusiva'
    assert pin['dossier']['versao']==d['versao']
    flow=client.get('/api/ed/fluxos/'+r.json['execucao_id']).json
    assert [x['nome'] for x in flow['etapas']]==['exportar','gerar','verificar','prospeccao']
    export=client.get('/api/ed/empresas/'+a['id']).json['exportacoes'][0]
    with zipfile.ZipFile(io.BytesIO(client.get(export['zip_url']).data)) as z:
        assert json.loads(z.read('adaptativo.json'))['proposta']['objetivo']=='Decisão manual exclusiva'
    # Mudança posterior não altera a conversa, nem apaga a versão revisada.
    client.put(path,json={'versao':d['versao'],'proposta':{**d['proposta'],'objetivo':'Nova decisão'}})
    assert client.get('/api/ed/assistente/conversas/'+chat['id']).json['contexto']['brief_adaptativo']==pin
    assert client.post(path+'/construir',json={**payload,'chave':'stale'}).status_code==409
    assert client.post(path+'/construir',json={**payload,'versao':999}).status_code==409


def test_changed_sources_require_new_review_and_other_project_is_rejected(client):
    a=lead(client,'Cliente A');b=lead(client,'Cliente B');d=reviewed(client,a['id'])
    construction(client,b['id'],'project-b')
    path='/api/ed/empresas/'+a['id']+'/adaptativo/construir'
    assert client.post(path,json={'versao':d['versao'],'projeto_id':'project-b','chave':'other'}).status_code==400
    assert client.patch('/api/ed/empresas/'+a['id'],json={'telefone':'123','confirmado':True}).status_code==200
    assert client.post(path,json={'versao':d['versao'],'projeto_id':'','chave':'changed'}).status_code==409


def test_refinement_keeps_selected_brief_and_project_rules_after_restart(client):
    import ed_tools,ed_workflows,ed_store
    a=lead(client,'Cliente selecionado');other=lead(client,'Outro cliente');d=reviewed(client,a['id'])
    path='/api/ed/empresas/'+a['id']+'/adaptativo'
    result=client.post(path+'/construir',json={'versao':d['versao'],'projeto_id':'','chave':'x'*80}).json
    chat_id=result['chat_id']
    construction(client,a['id'],'built-a');construction(client,a['id'],'other-project');construction(client,other['id'],'built-b')
    with client.application.app_context():
        import ed_assistant
        chat=ed_assistant.conversation(chat_id);chat['contexto']['construcao_id']='built-a';ed_assistant.save(chat)
    assert client.put('/api/ed/assistente/conversas/'+chat_id+'/projeto',json={'construcao_id':'other-project'}).status_code==400
    assert client.put('/api/ed/assistente/conversas/'+chat_id+'/projeto',json={'construcao_id':'built-b'}).status_code==400
    rule='Somente este projeto: manter a legenda editorial no rodapé da figura.'
    assert client.post(path+'/correcoes',json={'titulo':'Regra local','conteudo':rule,'escopo':'projeto','projeto_id':'built-a','origem_feedback':'usuario_explicito'}).status_code==201
    client.put(path,json={'versao':d['versao'],'proposta':{**d['proposta'],'objetivo':'Outra versão posterior'}})
    from ed_app import criar_app
    app=criar_app({'TESTING':True,'DATA_DIR':client.application.config['DATA_DIR'],'RUN_JOBS':False})
    restarted=app.test_client()
    message=restarted.post('/api/ed/assistente/conversas/'+chat_id+'/mensagens',json={'texto':'Refine o contato sem alterar as demais seções.','chave':'refine'}).json
    assert message['plano']['construcao_id']=='built-a'
    with app.app_context():
        job=ed_workflows.patch(message['execucao_id'],estado='executando')
        export=ed_tools.execute_step(job,0)
        zip_path=ed_store.arquivo_seguro('exportacoes',a['id']+'/'+export['id']+'/pacote.zip')
        with zipfile.ZipFile(zip_path) as z:
            selected=json.loads(z.read('adaptativo.json'))
            assert selected['versao']==d['versao']
            assert selected['proposta']['objetivo']=='Decisão manual exclusiva'
            assert rule in z.read('instrucoes-site.md').decode()
        import ed_library
        assert rule not in ed_library.resolve(other['id'])['texto']
        assert rule not in ed_library.resolve(a['id'],'other-project')['texto']
    assert len(restarted.get(path+'/versoes').json)==4


def test_rule_change_while_queued_stops_before_inference(client):
    import ed_workflows,ed_tools
    from werkzeug.exceptions import Conflict
    import pytest
    a=lead(client,'Fila com revisão');d=reviewed(client,a['id']);path='/api/ed/empresas/'+a['id']+'/adaptativo'
    r=client.post(path+'/construir',json={'versao':d['versao'],'projeto_id':'','chave':'queued'}).json
    client.post(path+'/correcoes',json={'titulo':'Nova regra','conteudo':'Não iniciar antes de revisar esta direção.','escopo':'lead','projeto_id':'','origem_feedback':'usuario_explicito'})
    with client.application.app_context():
        job=ed_workflows.patch(r['execucao_id'],estado='executando')
        with pytest.raises(Conflict,match='Regras ou referências'):ed_tools.execute_step(job,0)


def test_funnel_updates_do_not_invalidate_review_but_facts_do(client):
    a=lead(client,'Revisão estável');d=reviewed(client,a['id']);path='/api/ed/empresas/'+a['id']
    client.patch(path,json={'etapa':'exportado_codex'})
    assert client.get(path+'/adaptativo').json['revisao']['documental']==d['revisao']['documental']
    client.patch(path,json={'telefone':'123','confirmado':True})
    assert client.get(path+'/adaptativo').json['revisao']['documental']=='desatualizada'


def test_static_build_rejects_invalid_js_without_running_it(tmp_path):
    from ed_runtime import validate_static_build
    import pytest
    files=[{'path':'index.html','content':'<script src="app.js"></script>'}]
    (tmp_path/'app.js').write_text('function broken( {',encoding='utf-8')
    with pytest.raises(ValueError,match='sintaxe'):validate_static_build(tmp_path,files)
    # Um script que falharia ao EXECUTAR pode passar na análise de sintaxe.
    (tmp_path/'app.js').write_text('throw new Error("não executar");',encoding='utf-8')
    result=validate_static_build(tmp_path,files)
    assert result['javascript']=='node --check' and result['visual']=='pendente de inspeção'


def test_output_schema_prevents_model_backup_outside_contract():
    from ed_runtime import FILE_SCHEMA
    assert set(FILE_SCHEMA['properties']['files']['items']['properties']['path']['enum'])=={'index.html','style.css','app.js','README.md'}


def test_static_build_accepts_internal_svg_masks_but_still_rejects_missing_files(tmp_path):
    import pytest
    from ed_runtime import validate_static_build
    html='<svg aria-hidden="true"><defs><clipPath id="organic"><path d="M0 0"/></clipPath></defs></svg><section style="clip-path:url(#organic)">Texto real</section>'
    css='.shape{filter:url(#grain);clip-path:url(#organic)}'
    (tmp_path/'index.html').write_text(html,encoding='utf-8');(tmp_path/'style.css').write_text(css,encoding='utf-8')
    files=[dict(path='index.html',content=html),dict(path='style.css',content=css)]
    assert validate_static_build(tmp_path,files)['arquivos']=='validados'
    with pytest.raises(ValueError,match='ausente'):
        validate_static_build(tmp_path,[dict(path='style.css',content='.x{clip-path:url(missing.svg#organic)}')])


def test_partial_refinement_inherits_code_but_never_old_materials(tmp_path):
    import hashlib,pytest
    from ed_runtime import inherit_static_files,validate_static_build
    before=tmp_path/'before';after=tmp_path/'after';before.mkdir();after.mkdir()
    (before/'style.css').write_text('body{color:#222}',encoding='utf-8')
    (before/'app.js').write_bytes(b'const unchanged=true;\r\nconst portable=true;\r\n')
    (before/'materiais').mkdir();(before/'materiais/revoked.jpg').write_bytes(b'old-authorized-image')
    originals={f.name:hashlib.sha256(f.read_bytes()).hexdigest() for f in before.glob('*') if f.is_file()}
    files,inherited=inherit_static_files([dict(path='index.html',content='<link href="style.css" rel="stylesheet"><script src="app.js"></script>')],before)
    assert {f['arquivo'] for f in inherited}=={'style.css','app.js'}
    for f in files:(after/f['path']).write_text(f['content'],encoding='utf-8',newline='')
    assert validate_static_build(after,files)['javascript']=='node --check'
    assert originals=={f.name:hashlib.sha256(f.read_bytes()).hexdigest() for f in before.glob('*') if f.is_file()}
    for inherited_file in inherited:
        assert hashlib.sha256((after/inherited_file['arquivo']).read_bytes()).hexdigest()==inherited_file['sha256']
    assert not (after/'materiais/revoked.jpg').exists()
    with pytest.raises(ValueError,match='ausente'):
        validate_static_build(after,[dict(path='index.html',content='<img src="materiais/revoked.jpg">')])


def test_rejected_contract_can_retry_once_preserving_first_attempt(client,monkeypatch,tmp_path):
    # Mock somente da inferência externa; domínio, histórico e arquivos são reais.
    import ed_store,ed_tasks,ed_services
    a=lead(client,'Recuperação de teste');ident='contract-failure'
    root=tmp_path/'workspace';root.mkdir();(root/'contexto-executor.json').write_text('{"turno":"primeiro"}')
    (root/'.cache').mkdir();(root/'.cache/resposta-codex.json').write_text('{"primeira_resposta":"contrato rejeitado"}')
    monkeypatch.setattr('ed_runtime.artefact_root',lambda *args:root)
    monkeypatch.setattr('ed_creation_providers.generate',lambda job,progress:{'recovery_test':True})
    with client.application.app_context(),ed_store.conectar() as con:
        job=dict(id=ident,empresa_id=a['id'],tipo='codex_construcao',estado='erro',parametros={},diagnostico={'categoria':'contrato_codigo'},turn_id='first-turn',mensagem='Contrato rejeitado',autor={})
        con.execute('INSERT INTO ed_operacoes VALUES (?,?)',(ident,json.dumps(job)))
    with client.application.app_context():
        assert ed_tasks.retry_generation(ident)
        saved=ed_services.ler_job(ident)
        assert saved['estado']=='concluida'
        assert saved['historico_tentativas'][0]['turn_id']=='first-turn'
        assert not ed_tasks.retry_generation(ident)
    assert json.loads((root/'.cache/contexto-executor-tentativa-1.json').read_text())=={'turno':'primeiro'}
    assert json.loads((root/'.cache/resposta-codex-tentativa-1.json').read_text())=={'primeira_resposta':'contrato rejeitado'}


def test_completed_inference_revalidation_never_overwrites_changed_files(client,monkeypatch,tmp_path):
    import hashlib,pytest,zipfile
    import ed_runtime
    root=tmp_path/'completed';root.mkdir();(root/'.cache').mkdir()
    content='<h1>Prévia concluída</h1><svg><defs><clipPath id="shape"/></defs></svg><div style="clip-path:url(#shape)">Texto</div>'
    (root/'index.html').write_text(content,encoding='utf-8')
    raw=json.dumps({'files':[{'path':'index.html','content':content}],'pendencias':['Fotos autorizadas pendentes']})
    (root/'.cache/resposta-codex.json').write_text(raw,encoding='utf-8')
    (root/'briefing.md').write_text('Brief revisado',encoding='utf-8')
    ledger={'turn_id':'completed-turn','thread_id':'original-thread','brief':{'versao':6},'documentos':[{'arquivo':'briefing.md','sha256':hashlib.sha256((root/'briefing.md').read_bytes()).hexdigest()}]}
    (root/'contexto-executor.json').write_text(json.dumps(ledger),encoding='utf-8')
    archive=tmp_path/'pacote.zip'
    with zipfile.ZipFile(archive,'w') as z:z.writestr('manifesto-pacote.json',json.dumps({'arquivos':ledger['documentos']}))
    monkeypatch.setattr(ed_runtime,'artefact_root',lambda *args:root)
    monkeypatch.setattr('ed_visual_studio.assert_package',lambda *args:None)
    monkeypatch.setattr('ed_store.ler_empresa',lambda *args:{'exportacoes':[{'id':'export-one'}]})
    monkeypatch.setattr('ed_store.arquivo_seguro',lambda *args:archive)
    monkeypatch.setattr(ed_runtime,'record_model',lambda *args,**kwargs:None)
    job={'id':'original-operation','empresa_id':'lead','inferencia_concluida':True,'turn_id':'completed-turn','diagnostico':{'categoria':'contrato_codigo'},'parametros':{'exportacao_id':'export-one','modelo':'fixture','modo':'plano'}}
    with client.application.app_context():
        result=ed_runtime.revalidate_completed(job,lambda *args:None)
        assert result['recuperacao']['metodo']=='revalidacao_sem_inferencia'
        assert result['turn_id']=='completed-turn' and result['build_estatico']['arquivos']=='validados'
        (root/'index.html').write_text('Edição manual preservada',encoding='utf-8')
        with pytest.raises(ValueError,match='Código mudou'):ed_runtime.revalidate_completed(job,lambda *args:None)
        assert (root/'index.html').read_text(encoding='utf-8')=='Edição manual preservada'
        with pytest.raises(ValueError,match='não comprovadamente'):ed_runtime.revalidate_completed({**job,'inferencia_concluida':False},lambda *args:None)


def test_generation_and_revalidation_reject_revoked_package_material(client):
    import pytest,ed_store,ed_export,ed_runtime
    from PIL import Image
    a=lead(client,'Material com direito revogado');base='/api/ed/empresas/'+a['id']
    image=io.BytesIO();Image.new('RGB',(32,32),'wheat').save(image,'PNG');image.seek(0)
    material=client.post(base+'/materiais',data={'arquivo':(image,'autorizada.png'),'origem':'Fixture própria','atribuicao':'Teste','autorizado':'true'}).json
    assert client.patch(base+'/materiais/'+material['id'],json={'selecionado':True}).status_code==200
    with client.application.app_context():
        package={'materiais.json':json.dumps(ed_export.inventario(ed_store.ler_empresa(a['id'])))}
        ed_runtime.assert_current_materials(ed_store.ler_empresa(a['id']),package)
    assert client.patch(base+'/materiais/'+material['id'],json={'selecionado':False}).status_code==200
    with client.application.app_context(),pytest.raises(ValueError,match='seleção|autorização'):
        ed_runtime.assert_current_materials(ed_store.ler_empresa(a['id']),package)
    assert client.patch(base+'/materiais/'+material['id'],json={'autorizado':False}).status_code==200
    with client.application.app_context(),pytest.raises(ValueError,match='autorização'):
        ed_runtime.assert_current_materials(ed_store.ler_empresa(a['id']),package)
    assert client.get(base+'/materiais/'+material['id']+'/arquivo').status_code==200
