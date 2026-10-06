from test_ed_enrich import client
import json
import ed_store as store
import ed_workflows as flows

def company(client):
    return client.post('/api/ed/empresas',json={'nome':'Piloto identificado como teste','nicho':'Padarias','confirmado':True,'descricao':'Informação revisada de teste.'}).get_json()['id']

def test_workflow_template_checkpoint_and_duplicate(client,monkeypatch):
    from flask import jsonify
    ident=company(client);app=client.application
    def opened(c,j):
        # Somente processo/socket substituídos; vínculo e demais domínio/ZIP reais.
        with store.conectar() as con:con.execute('INSERT INTO ed_previas VALUES (?,?,?)',(store.novo_id(),c,json.dumps(dict(url='http://127.0.0.1:5163/',construcao_id=j,criado_em=store.agora()))))
        return jsonify(url='http://127.0.0.1:5163/')
    app.view_functions['ed.open_project']=opened
    data={'plano':{'acao':'preparar','empresa_id':ident,'geracao':'templates'},'chave':'piloto-repetivel'}
    first=client.post('/api/ed/fluxos',json=data).get_json()
    second=client.post('/api/ed/fluxos',json=data).get_json();assert first['id']==second['id']
    with app.app_context():flows.run(app,first['id']);finished=flows.get(first['id'])
    assert finished['estado']=='parcial',finished
    assert all(s['estado']=='concluida' for s in finished['etapas'])
    check=next(s['resultado'] for s in finished['etapas'] if s['nome']=='verificar');assert check['arquivos_verificados']>10
    before=client.get('/api/ed/empresas/'+ident).get_json()
    prospect=next(s['resultado'] for s in finished['etapas'] if s['nome']=='prospeccao')
    assert len(before['exportacoes'])==2 and prospect['enviado'] is False
    assert before['exportacoes'][0]['id']==prospect['exportacao_final']
    from ed_crm import list_records
    with app.app_context():
        opportunity=list_records('oportunidade',ident)[0]
        assert opportunity['pacote_id']==prospect['exportacao_final'] and opportunity['previa_id']==before['previas'][0]['id']
    import io,zipfile
    with zipfile.ZipFile(io.BytesIO(client.get(prospect['zip_url']).data)) as archive:
        text=archive.read('prospeccao.md').decode()
        assert 'WhatsApp' in text and '5163' in text and 'Acompanhamento' in text
    with app.app_context():flows.run(app,first['id'])
    assert len(client.get('/api/ed/empresas/'+ident).get_json()['exportacoes'])==2


def test_research_and_export_preserve_revised_prospect(client):
    import ed_tools,ed_export,io,zipfile
    ident=company(client)
    manual={'whatsapp':'Texto revisado pelo titular, sem contato anterior.'}
    assert client.put('/api/ed/empresas/'+ident+'/prospeccao',json=manual).status_code==200
    with client.application.app_context():
        assert ed_tools.prospect(ident)['whatsapp']==manual['whatsapp']
        export=ed_export.exportar(ident)
    with zipfile.ZipFile(io.BytesIO(client.get(export['zip_url']).data)) as z:
        assert manual['whatsapp'] in z.read('prospeccao.md').decode()
    assert client.post('/api/ed/fluxos',json={'plano':{'acao':'consultar','sem_site':'false'}}).status_code==400


def test_prospect_keeps_spaces_between_editorial_title_lines(client,monkeypatch,tmp_path):
    import ed_tools,ed_runtime
    ident=company(client);jid=store.novo_id()
    (tmp_path/'index.html').write_text('<main><h1>PÃO,<br>perto de você.</h1><h2>Produtos<br>e encomendas.</h2></main>',encoding='utf-8')
    monkeypatch.setattr(ed_runtime,'artefact_root',lambda *args:tmp_path)
    with client.application.app_context(),store.conectar() as con:
        con.execute('INSERT INTO ed_previas VALUES (?,?,?)',(store.novo_id(),ident,json.dumps(dict(url='http://127.0.0.1:5139/',construcao_id=jid,criado_em=store.agora()))))
    with client.application.app_context():
        result=ed_tools.prospect(ident,jid)
        assert result['secoes_propostas']==['PÃO, perto de você.','Produtos e encomendas.']
        assert 'Produtose encomendas' not in result['email']

def test_pause_cancel_restart_preserves_completed_step(client):
    ident=company(client)
    job=client.post('/api/ed/fluxos',json={'plano':{'acao':'preparar','empresa_id':ident}}).get_json()
    assert client.post('/api/ed/fluxos/'+job['id']+'/pausar').get_json()['estado']=='pausada'
    assert client.post('/api/ed/fluxos/'+job['id']+'/retomar').get_json()['estado']=='na_fila'
    with client.application.app_context():
        value=flows.get(job['id']);value['etapas'][0].update(estado='concluida',resultado={'empresa_id':ident});value['estado']='executando';flows.write(value)
        flows.setup();recovered=flows.get(job['id'])
        assert recovered['estado']=='pausada' and recovered['etapas'][0]['estado']=='concluida'
    assert client.post('/api/ed/fluxos/'+job['id']+'/cancelar').get_json()['estado']=='cancelada'

def test_chat_local_tool_and_external_attachment_not_authority(client):
    ident=company(client)
    chat=client.post('/api/ed/assistente/conversas',json={'empresa_id':ident}).get_json()
    data={'texto':'Mostre os leads sem site','chave':'mensagem-idempotente'}
    reply=client.post('/api/ed/assistente/conversas/'+chat['id']+'/mensagens',json=data).get_json()
    assert reply['interpretacao']=='Comando local, sem inferência'
    assert client.post('/api/ed/assistente/conversas/'+chat['id']+'/mensagens',json=data).get_json()['id']==reply['id']
    with client.application.app_context():flows.run(client.application,reply['execucao_id'])
    job=client.get('/api/ed/fluxos/'+reply['execucao_id']).get_json();assert job['etapas'][0]['resultado']['empresas'][0]['id']==ident
    assert client.post('/api/ed/fluxos',json={'plano':{'acao':'shell','comando':'whoami'}}).status_code==400
    assert client.post('/api/ed/fluxos',json={'plano':{'acao':'consultar','workspace':'outro'}}).status_code==400

def test_idempotent_effect_and_locked_composition(client):
    import ed_export,ed_composition
    ident=company(client)
    with client.application.app_context():
        a=ed_export.exportar(ident,idempotency_key='mesmo-efeito');b=ed_export.exportar(ident,idempotency_key='mesmo-efeito');assert a['id']==b['id']
        value=ed_composition.ler(ident);value['secoes'][0]['fixada']=True;ed_composition.salvar(ident,value)
    job=client.post('/api/ed/fluxos',json={'plano':{'acao':'alternativa','empresa_id':ident,'secao':'abertura','alternativa':'b'}}).get_json()
    with client.application.app_context():flows.run(client.application,job['id'])
    assert client.get('/api/ed/fluxos/'+job['id']).get_json()['estado']=='falhou'
    assert client.get('/api/ed/empresas/'+ident+'/composicao').get_json()['secoes'][0]['escolhida']=='a'
