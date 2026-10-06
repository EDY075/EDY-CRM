"""Artefatos isolados; estes testes não comprovam inferência de fornecedor."""
import json
import pytest
from test_ed_enrich import client


def built(client, monkeypatch, tmp_path):
    import ed_store as store, ed_runtime
    lead=client.post('/api/ed/empresas',json={'nome':'Prévia QA'}).json
    jid=store.novo_id()
    root=tmp_path/'site';root.mkdir()
    (root/'index.html').write_text('<!doctype html><html><head><title>QA</title><link rel="stylesheet" href="style.css"></head><body>QA</body></html>')
    (root/'style.css').write_text('body{color:navy}')
    job=dict(id=jid,empresa_id=lead['id'],tipo='codex_construcao',estado='concluida',criado_em=store.agora(),parametros={'exportacao_id':'qa'},resultado={'arquivos':['index.html','style.css'],'escopo':'previa'})
    with client.application.app_context(),store.conectar() as con:con.execute('INSERT INTO ed_operacoes VALUES (?,?)',(jid,json.dumps(job)))
    monkeypatch.setattr(ed_runtime,'artefact_root',lambda *a:root)
    return lead,jid,root


def test_stable_listing_and_missing_asset(client,monkeypatch,tmp_path):
    lead,jid,root=built(client,monkeypatch,tmp_path)
    item=client.get('/api/ed/previas').json[0]
    assert item['abrir_url']==f'/previas/{lead["id"]}/{jid}'
    assert item['estado']=='servidor_parado' and not item['url_ativa']
    (root/'style.css').unlink()
    status=client.get(f'/api/ed/empresas/{lead["id"]}/construcoes/{jid}/disponibilidade').json
    assert status['estado']=='arquivos_ausentes' and 'style.css' in status['motivo']


def test_open_recovers_dead_process_without_new_generation(client,monkeypatch,tmp_path):
    import ed_runtime
    lead,jid,root=built(client,monkeypatch,tmp_path)
    route=f'/api/ed/empresas/{lead["id"]}/construcoes/{jid}/abrir'
    r=client.post(route,json={});assert r.status_code==200,r.json
    first=ed_runtime.processes[jid][0]
    assert r.json['estado']=='disponivel'
    assert client.post(route,json={}).json['url']==r.json['url']
    assert ed_runtime.processes[jid][0] is first
    first.terminate();first.wait(timeout=5)
    again=client.post(route,json={});assert again.status_code==200,again.json
    assert ed_runtime.processes[jid][0] is not first
    assert client.get('/api/ed/previas').json[0]['construcao_id']==jid
    ed_runtime.processes.pop(jid)[0].terminate()


def test_other_lead_cannot_open_or_refine_build(client,monkeypatch,tmp_path):
    lead,jid,root=built(client,monkeypatch,tmp_path)
    other=client.post('/api/ed/empresas',json={'nome':'Outra QA'}).json
    for action in ('disponibilidade','conversa'):
        url=f'/api/ed/empresas/{other["id"]}/construcoes/{jid}/{action}'
        assert (client.get(url) if action=='disponibilidade' else client.post(url,json={})).status_code==404


def test_wrong_server_content_is_recoverable_without_claiming_missing_files(client,monkeypatch,tmp_path):
    import ed_preview
    lead,jid,root=built(client,monkeypatch,tmp_path)
    monkeypatch.setattr(ed_preview,'active_url',lambda *a:'http://127.0.0.1:5131/')
    def mismatch(*args):raise ed_preview.ServingMismatch('Servidor entregou outra versão.')
    monkeypatch.setattr(ed_preview,'serving_health',mismatch)
    status=client.get(f'/api/ed/empresas/{lead["id"]}/construcoes/{jid}/disponibilidade').json
    assert status['estado']=='servidor_parado' and status['url_ativa'] is None
    assert (root/'index.html').is_file()


def test_refinement_conversation_is_pinned_and_idempotent(client,monkeypatch,tmp_path):
    import ed_assistant
    lead,jid,root=built(client,monkeypatch,tmp_path)
    url=f'/api/ed/empresas/{lead["id"]}/construcoes/{jid}/conversa'
    a=client.post(url,json={});assert a.status_code==200,a.json
    assert client.post(url,json={}).json==a.json
    chat=client.get('/api/ed/assistente/conversas/'+a.json['chat_id']).json
    assert chat['contexto']['empresa_id']==lead['id'] and chat['contexto']['construcao_id']==jid
    assert chat['contexto']['geracao']=='codex_nativo'
    assert client.post(url,json={'empresa_id':'injected'}).status_code==400
