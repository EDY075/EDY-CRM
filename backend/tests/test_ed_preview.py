import json
from test_ed_enrich import client


def test_thumbnail_keeps_browser_location_without_passing_credentials(client,monkeypatch,tmp_path):
    import ed_preview,ed_runtime,subprocess,shutil
    monkeypatch.setattr(ed_preview,'active_url',lambda *args:'http://127.0.0.1:5139/')
    monkeypatch.setattr(ed_runtime,'artefact_root',lambda *args:tmp_path)
    monkeypatch.setattr(shutil,'which',lambda name:'node.exe')
    monkeypatch.setenv('HOMEDRIVE','C:')
    monkeypatch.setenv('LOCALAPPDATA','C:/Users/test/AppData/Local')
    monkeypatch.setenv('OPENAI_API_KEY','never-pass-this')
    monkeypatch.setenv('APIFY_TOKEN','never-pass-this-either')
    def capture(args,**kwargs):
        # Contrato de ambiente apenas; não é evidência de captura real.
        assert kwargs['env']['HOMEDRIVE']=='C:'
        assert kwargs['env']['LOCALAPPDATA']=='C:/Users/test/AppData/Local'
        assert 'OPENAI_API_KEY' not in kwargs['env'] and 'APIFY_TOKEN' not in kwargs['env']
        assert kwargs['env']['TEMP']==str(tmp_path/'.cache')
        (tmp_path/'.cache/miniatura.jpg').write_bytes(b'fixture')
    monkeypatch.setattr(subprocess,'run',capture)
    assert ed_preview.thumbnail('company','build','http://127.0.0.1:5139/').endswith('/miniatura')


def test_previous_port_is_not_a_live_link_for_another_company_or_construction(client,monkeypatch):
    # Registry of synthetic processes: proves association, not an external operation.
    import ed_store as store,ed_runtime
    from ed_preview import active_url
    a=client.post('/api/ed/empresas',json={'nome':'Empresa QA A'}).json
    b=client.post('/api/ed/empresas',json={'nome':'Empresa QA B'}).json
    jid_a,jid_b=store.novo_id(),store.novo_id()
    with client.application.app_context(),store.conectar() as con:
        for jid,lead in [(jid_a,a),(jid_b,b)]:
            con.execute('INSERT INTO ed_operacoes VALUES (?,?)',(jid,json.dumps(dict(id=jid,empresa_id=lead['id'],tipo='projeto_funcional',estado='concluida'))))
        con.execute('INSERT INTO ed_previas VALUES (?,?,?)',(store.novo_id(),a['id'],json.dumps(dict(url='http://127.0.0.1:5163/',construcao_id=jid_a,criado_em=store.agora(),exportacao_id=''))))
        job=dict(id=store.novo_id(),plano={'acao':'preparar','empresa_id':a['id']},estado='concluida',etapas=[dict(nome='gerar',resultado={'construcao_id':jid_a}),dict(nome='verificar',resultado={'empresa_id':a['id'],'url':'http://127.0.0.1:5163/'})])
        con.execute('INSERT INTO ed_fluxos VALUES (?,?,?)',(job['id'],'teste-porta',json.dumps(job)))
    class Alive:
        def poll(self):return None
    monkeypatch.setitem(ed_runtime.processes,jid_b,(Alive(),'http://127.0.0.1:5163/'))
    assert client.get('/api/ed/empresas/'+a['id']).json['previas'][0]['url_ativa'] is None
    assert client.get('/api/ed/fluxos/'+job['id']).json['etapas'][1]['resultado']['url_ativa'] is None
    with client.application.app_context():assert active_url(a['id'],jid_b) is None
    monkeypatch.setitem(ed_runtime.processes,jid_a,(Alive(),'http://127.0.0.1:5164/'))
    assert client.get('/api/ed/empresas/'+a['id']).json['previas'][0]['url_ativa']=='http://127.0.0.1:5164/'
    assert client.get('/api/ed/fluxos/'+job['id']).json['etapas'][1]['resultado']['url_ativa']=='http://127.0.0.1:5164/'
    with client.application.app_context(),store.conectar() as con:
        recorded=json.loads(con.execute('SELECT dados FROM ed_fluxos WHERE id=?',(job['id'],)).fetchone()[0])
        assert recorded['etapas'][1]['resultado']==job['etapas'][1]['resultado']
    class Dead:
        def poll(self):return 0
    monkeypatch.setitem(ed_runtime.processes,jid_a,(Dead(),'http://127.0.0.1:5164/'))
    assert client.get('/api/ed/empresas/'+a['id']).json['previas'][0]['url_ativa'] is None
