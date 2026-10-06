import io
import json
import zipfile
from test_ed_enrich import client


def lead(client, name, **fields):
    return client.post('/api/ed/empresas', json={'nome': name, **fields}).json


def analyze(client, ids, key='analyze'):
    return client.post('/api/ed/adaptativo/analisar', json={'empresa_ids': ids, 'chave': key})


def test_selection_facts_idempotency_and_no_fiction_import(client):
    a = lead(client, 'Empresa teste A', servicos='Produto revisado', confirmado=True)
    b = lead(client, 'Empresa teste B', telefone='Contato pendente')
    excluded = lead(client, 'Empresa não selecionada')
    r = analyze(client, [a['id'], b['id']])
    assert r.status_code == 201
    assert [x['empresa_id'] for x in r.json['resultados']] == [a['id'], b['id']]
    assert r.json['resultados'][0]['fatos']['servicos']['valor'] == 'Produto revisado'
    assert 'telefone' not in r.json['resultados'][1]['fatos']
    assert r.json['resultados'][1]['candidatos']['telefone']['valor'] == 'Contato pendente'
    assert analyze(client, [a['id'], b['id']]).json == r.json
    assert analyze(client, [a['id']], 'analyze').status_code == 409
    assert client.get('/api/ed/empresas/'+excluded['id']+'/adaptativo').json['versao'] == 0
    assert len(client.get('/api/ed/empresas').json) == 3
    assert analyze(client, [a['id'], 'inexistente'], 'invalid').status_code == 404


def test_manual_brief_survives_refresh_and_restart(client):
    a = lead(client, 'Empresa revisão')
    d = analyze(client, [a['id']]).json['resultados'][0]
    path = '/api/ed/empresas/'+a['id']+'/adaptativo'
    updated = client.put(path, json={'versao':d['versao'], 'proposta':{**d['proposta'], 'objetivo':'Decisão específica do operador'}})
    assert updated.status_code == 200
    assert client.put(path, json={'versao':d['versao'], 'proposta':d['proposta']}).status_code == 409
    newer = analyze(client, [a['id']], 'new').json['resultados'][0]
    assert newer['proposta']['objetivo'] == 'Decisão específica do operador'
    assert newer['edicoes_preservadas'] == ['objetivo']
    from ed_app import criar_app
    app = criar_app({'TESTING':True, 'DATA_DIR':client.application.config['DATA_DIR'], 'RUN_JOBS':False})
    assert app.test_client().get(path).json['proposta']['objetivo'] == 'Decisão específica do operador'
    assert len(client.get(path+'/versoes').json) == 3


def construction(client, company, ident, previous=''):
    import ed_store
    with client.application.app_context(), ed_store.conectar() as con:
        value = dict(id=ident, empresa_id=company, tipo='codex_construcao', estado='concluida', parametros={'anterior':previous}, resultado={'anterior':previous})
        con.execute('INSERT INTO ed_operacoes VALUES (?,?)', (ident,json.dumps(value)))


def test_correction_candidate_approval_and_project_isolation(client):
    a = lead(client, 'Cliente A'); b = lead(client, 'Cliente B')
    construction(client,a['id'],'project-a'); construction(client,a['id'],'project-a-v2','project-a')
    construction(client,a['id'],'project-other'); construction(client,b['id'],'project-b')
    path='/api/ed/empresas/'+a['id']+'/adaptativo/correcoes'
    payload={'titulo':'Regra de um projeto', 'conteudo':'Preservar o enquadramento lateral aprovado.', 'escopo':'projeto', 'projeto_id':'project-a-v2', 'origem_feedback':'observacao_modelo'}
    r=client.post(path,json=payload)
    assert r.status_code == 201 and r.json['estado']=='inativo'
    def context(company,project=''):
        return client.get('/api/ed/empresas/'+company+'/contexto',query_string={'projeto_id':project}).json['texto']
    assert payload['conteudo'] not in context(a['id'],'project-a')
    approved=client.post(path+'/'+r.json['id']+'/aprovar',json={'versao':1})
    assert approved.status_code == 200
    assert payload['conteudo'] in context(a['id'],'project-a-v2')
    assert payload['conteudo'] not in context(a['id'],'project-other')
    assert payload['conteudo'] not in context(a['id'])
    assert payload['conteudo'] not in context(b['id'],'project-b')
    assert client.post(path,json={**payload,'projeto_id':'project-b'}).status_code == 400
    assert client.post(path,json={**payload,'escopo':'global'}).status_code == 400


def test_export_has_skill_brief_sources_and_review_not_visual_approval(client):
    a=lead(client,'Negócio para pacote',telefone='123')
    d=analyze(client,[a['id']]).json['resultados'][0]
    path='/api/ed/empresas/'+a['id']+'/adaptativo'
    review=client.post(path+'/revisar',json={'versao':d['versao']})
    assert review.status_code==200
    assert review.json['revisao']['visual']=='nao_executada'
    assert review.json['revisao']['documental']=='com_pendencias'
    export=client.post('/api/ed/empresas/'+a['id']+'/exportacoes').json
    with zipfile.ZipFile(io.BytesIO(client.get(export['zip_url']).data)) as z:
        for name in ('analise-adaptativa.md','brief-adaptativo.md','instrucoes-site.md','revisao-adaptativa.json','.agents/skills/crm-sites-adaptativo/SKILL.md'):
            assert name in z.namelist()
        dossier=json.loads(z.read('adaptativo.json'))
        assert ('Método: '+dossier['metodo']) in z.read('brief-adaptativo.md').decode()
        assert 'telefone' not in dossier['fatos']
        assert '123' in dossier['candidatos']['telefone']['valor']
        assert dossier['revisao']['visual']=='nao_executada'
        manifest=json.loads(z.read('manifesto-pacote.json'))
        import hashlib
        for item in manifest['arquivos']:
            assert hashlib.sha256(z.read(item['arquivo'])).hexdigest()==item['sha256']


def test_revoked_confirmation_and_updated_preparation_do_not_export_stale_facts(client):
    a=lead(client,'Empresa revisão de fontes',servicos='Serviço aprovado',confirmado=True)
    analyze(client,[a['id']])
    client.patch('/api/ed/empresas/'+a['id'],json={'servicos':'Serviço aprovado','confirmado':False})
    d=client.get('/api/ed/empresas/'+a['id']+'/adaptativo').json
    assert 'servicos' not in d['fatos']
    assert d['revisao']['documental']=='desatualizada'
    p=client.get('/api/ed/empresas/'+a['id']+'/preparacao').json
    p['design']['composicao']='Nova direção manual para a empresa'
    client.put('/api/ed/empresas/'+a['id']+'/preparacao',json=p)
    export=client.post('/api/ed/empresas/'+a['id']+'/exportacoes').json
    with zipfile.ZipFile(io.BytesIO(client.get(export['zip_url']).data)) as z:
        current=json.loads(z.read('adaptativo.json'))
        assert 'servicos' not in current['fatos']
        assert p['design']['composicao'] in current['proposta']['direcao']


def test_native_proposal_is_not_applied_and_manual_fields_survive(client,monkeypatch):
    import ed_adaptive
    a=lead(client,'Empresa sugestões')
    d=analyze(client,[a['id']]).json['resultados'][0]
    path='/api/ed/empresas/'+a['id']+'/adaptativo'
    d=client.put(path,json={'versao':d['versao'],'proposta':{**d['proposta'],'objetivo':'Objetivo manual'}}).json
    def mock_inference(job,progress):
        # Teste do contrato e persistência, não operação validada com o fornecedor.
        value=ed_adaptive.effective(a['id'])
        return {'proposta':{k:'Sugestão '+k for k in ed_adaptive.FIELDS},'observacoes_candidatas':['Observação para revisar'], 'versao_base':value['versao'],'projeto_id':'','fontes_hash':ed_adaptive.source_hash(value)}
    monkeypatch.setattr(ed_adaptive,'propose_native',mock_inference)
    body={'versao':d['versao'],'projeto_id':'','chave':'mock-only'}
    job=client.post(path+'/codex',json=body).json
    assert job['estado']=='concluida'
    assert client.post(path+'/codex',json=body).json['id']==job['id']
    assert client.get(path).json['proposta']==d['proposta']
    applied=client.post(path+'/codex/'+job['id']+'/aplicar',json={'versao':d['versao']})
    assert applied.status_code==200
    assert applied.json['proposta']['objetivo']=='Objetivo manual'
    assert applied.json['proposta']['jornada']=='Sugestão jornada'
    assert applied.json['observacoes_candidatas']==['Observação para revisar']
    assert not client.get(path+'/correcoes').json
    export=client.post('/api/ed/empresas/'+a['id']+'/exportacoes').json
    with zipfile.ZipFile(io.BytesIO(client.get(export['zip_url']).data)) as z:
        package=json.loads(z.read('adaptativo.json'))
        assert 'observacoes_candidatas' not in package
        assert package['observacoes_candidatas_pendentes']==1
    assert client.post(path+'/codex/'+job['id']+'/aplicar',json={'versao':d['versao']}).status_code==409


def test_native_failure_and_changed_sources_never_overwrite_brief(client,monkeypatch):
    import ed_adaptive
    a=lead(client,'Empresa falha')
    d=analyze(client,[a['id']]).json['resultados'][0]
    path='/api/ed/empresas/'+a['id']+'/adaptativo'
    def fail(job,progress):raise ValueError('Teste: autenticação indisponível')
    monkeypatch.setattr(ed_adaptive,'propose_native',fail)
    job=client.post(path+'/codex',json={'versao':d['versao'],'projeto_id':'','chave':'failed'}).json
    assert job['estado']=='erro'
    assert client.post(path+'/codex/'+job['id']+'/aplicar',json={'versao':d['versao']}).status_code==409
    assert client.get(path).json['proposta']==d['proposta']


def test_project_export_inherits_company_brief_but_not_other_project_corrections(client):
    a=lead(client,'Empresa múltiplos projetos')
    d=analyze(client,[a['id']]).json['resultados'][0]
    path='/api/ed/empresas/'+a['id']+'/adaptativo'
    client.put(path,json={'versao':d['versao'],'proposta':{**d['proposta'],'copy':'Copy revisada para este cliente'}})
    construction(client,a['id'],'project-a');construction(client,a['id'],'project-b')
    correction=client.post(path+'/correcoes',json={'titulo':'Só no projeto A','conteudo':'Decisão específica do projeto A','escopo':'projeto','projeto_id':'project-a','origem_feedback':'usuario_explicito'}).json
    for project in ('project-a','project-b'):
        e=client.post('/api/ed/empresas/'+a['id']+'/exportacoes',json={'projeto_id':project}).json
        with zipfile.ZipFile(io.BytesIO(client.get(e['zip_url']).data)) as z:
            d=json.loads(z.read('adaptativo.json'))
            assert d['proposta']['copy']=='Copy revisada para este cliente'
            assert (correction['conteudo'] in z.read('instrucoes-site.md').decode())==(project=='project-a')
