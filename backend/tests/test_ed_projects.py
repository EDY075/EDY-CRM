import importlib.util
from pathlib import Path
import re
from test_ed_enrich import client


def load_app(path):
    spec=importlib.util.spec_from_file_location('project_test',path);module=importlib.util.module_from_spec(spec);spec.loader.exec_module(module);return module


def test_admin_csrf_auth_crud_roles_and_persistence(tmp_path):
    module=load_app(Path(__file__).parents[1]/'project_template/app.py');app=module.create_app(tmp_path/'site');c=app.test_client()
    def post(url,**data):
        with c.session_transaction() as s:data['csrf']=s['csrf']
        return c.post(url,data=data)
    assert c.get('/admin').status_code==302
    assert c.post('/setup',data={'csrf':'INVALID','usuario':'a','senha':'senha longa teste'}).status_code==403
    c.get('/setup');assert c.post('/setup',data={'usuario':'a','senha':'senha longa teste'}).status_code==403
    assert post('/setup',usuario='qa-admin',senha='senha longa teste').status_code==302
    assert c.get('/setup').status_code==404
    c.get('/login');assert post('/login',usuario='qa-admin',senha='senha longa teste').status_code==302
    c.get('/admin');assert post('/admin/catalogo',nome='<script>teste</script>',descricao='Item QA').status_code==302
    html=c.get('/catalogo').data;assert b'&lt;script&gt;' in html and b'<script>teste' not in html
    assert post('/admin/catalogo/1',nome='Item refinado',descricao='Persistente QA').status_code==302
    assert post('/admin/usuarios',usuario='editor',senha='senha editor teste').status_code==302
    post('/sair');c.get('/login');post('/login',usuario='editor',senha='senha editor teste');c.get('/admin')
    assert post('/admin/usuarios',usuario='intruso',senha='senha editor teste').status_code==403
    assert post('/admin/catalogo/1/arquivar').status_code==302
    assert b'Item refinado' not in c.get('/catalogo').data
    c.get('/contato');assert post('/contato',nome='Teste',email='qa@example.test',mensagem='Contato local').status_code==200
    again=module.create_app(tmp_path/'site').test_client();assert again.get('/setup').status_code==404
    assert (tmp_path/'site/site.db').is_file()

def test_browser_form_policy_keeps_origin_strict(tmp_path):
    module=load_app(Path(__file__).parents[1]/'project_template/app.py');c=module.create_app(tmp_path/'site').test_client()
    r=c.get('/setup');assert r.headers['Referrer-Policy']=='same-origin'
    with c.session_transaction() as s:token=s['csrf']
    assert c.post('/setup',data={'csrf':token,'usuario':'qa','senha':'senha longa teste'},headers={'Origin':'null'}).status_code==403
    assert c.post('/setup',data={'csrf':token,'usuario':'qa','senha':'senha longa teste'},headers={'Origin':'http://localhost'}).status_code==302


def test_project_selection_ownership_and_missing_access(client):
    lead=client.post('/api/ed/empresas',json={'nome':'QA'}).json
    url='/api/ed/empresas/'+lead['id']+'/projetos'
    assert client.post(url,json={'modo':'aplicacao','modulos':[],'exportacao_id':'ausente'}).status_code==400
    assert client.post('/api/ed/cofre/testar',json={}).status_code==400
    assert 'client_secret' not in client.get('/api/ed/cofre').text


def test_portable_project_has_integrity_and_runs_with_own_db(client,tmp_path,monkeypatch):
    import ed_runtime,json,zipfile,io,hashlib
    monkeypatch.setattr(ed_runtime,'artefact_root',lambda company,job:tmp_path/'generated'/company/job)
    lead=client.post('/api/ed/empresas',json={'nome':'Empresa QA','demonstracao':True}).json
    root='/api/ed/empresas/'+lead['id']
    exported=client.post(root+'/exportacoes').json
    result=client.post(root+'/projetos',json={'modo':'aplicacao','modulos':['catalogo','contatos','uploads'],'exportacao_id':exported['id']}).json
    assert result['estado']=='concluida',result
    raw=client.get(root+'/projetos/'+result['id']+'/zip').data
    extracted=tmp_path/'portable';extracted.mkdir()
    with zipfile.ZipFile(io.BytesIO(raw)) as z:
        assert not any('site.db' in n or 'session.key' in n for n in z.namelist())
        for x in json.loads(z.read('integridade-projeto.json')):assert hashlib.sha256(z.read(x['arquivo'])).hexdigest()==x['sha256']
        z.extractall(extracted)
    module=load_app(extracted/'app.py');c=module.create_app().test_client()
    assert c.get('/setup').status_code==200
    assert (extracted/'data/site.db').exists()
    assert c.get('/index.html').status_code==404
    assert c.get('/').status_code==200
    assert c.get('/sobre.html').status_code==200
    assert c.get('/app.py').status_code==404
