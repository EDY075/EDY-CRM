from test_ed_enrich import client
from flask import g


def activate(client):
    result=client.post('/api/ed/acesso/setup',json={'nome':'admin','senha':'senha local teste segura'})
    assert result.status_code==201,result.json
    info=client.get('/api/ed/acesso/sessao').json
    return {'X-EDY-CSRF':info['csrf']}


def test_workspace_separates_every_existing_domain_and_backend_roles(client):
    legacy=client.post('/api/ed/empresas',json={'nome':'Registro principal preservado'}).json
    headers=activate(client)
    assert client.post('/api/ed/empresas',json={'nome':'Sem CSRF'}).status_code==403
    reader=client.post('/api/ed/acesso/usuarios',headers=headers,json={'nome':'leitor','senha':'senha leitor segura','papel':'leitura'})
    assert reader.status_code==201
    workspace=client.post('/api/ed/acesso/workspaces',headers=headers,json={'nome':'Segundo workspace'}).json
    assert client.post('/api/ed/acesso/workspace',headers=headers,json={'id':workspace['id']}).status_code==200
    assert client.get('/api/ed/empresas').json==[]
    assert client.get('/api/ed/empresas/'+legacy['id']).status_code==404
    assert client.post('/api/ed/empresas',headers=headers,json={'nome':'Empresa do segundo workspace'}).status_code==201
    second=client.get('/api/ed/empresas').json[0]
    assert client.post('/api/ed/acesso/workspace',headers=headers,json={'id':'principal'}).status_code==200
    assert client.get('/api/ed/empresas/'+second['id']).status_code==404
    assert client.get('/api/ed/empresas/'+legacy['id']).json['nome']==legacy['nome']
    client.post('/api/ed/acesso/sair',headers=headers)
    assert client.get('/api/ed/empresas').status_code==401
    client.post('/api/ed/acesso/login',json={'nome':'leitor','senha':'senha leitor segura'})
    reader_headers={'X-EDY-CSRF':client.get('/api/ed/acesso/sessao').json['csrf']}
    assert client.get('/api/ed/empresas/'+legacy['id']).status_code==200
    assert client.patch('/api/ed/empresas/'+legacy['id'],headers=reader_headers,json={'nome':'Bloqueado'}).status_code==403
    assert client.get('/api/ed/acesso/usuarios').status_code==403
    assert client.post('/api/ed/acesso/workspace',headers=reader_headers,json={'id':workspace['id']}).status_code==403


def test_worker_keeps_workspace_after_request_ends(client,tmp_path):
    from concurrent.futures import ThreadPoolExecutor
    from ed_workspace import data_directory,submit
    import ed_store
    pool=ThreadPoolExecutor(max_workers=1)
    token=data_directory.set(tmp_path/'owned')
    app=client.application
    def worker():
        with app.app_context():return ed_store.pasta()
    try:future=submit(pool,worker)
    finally:data_directory.reset(token)
    assert future.result()==tmp_path/'owned'
    pool.shutdown()


def test_role_revocation_and_last_admin_protect_worker(client):
    import ed_workflows as flows
    from ed_access import connection
    headers=activate(client)
    admin=client.get('/api/ed/acesso/usuarios').json[0]
    assert client.put('/api/ed/acesso/usuarios/'+admin['id'],headers=headers,json={'papel':'leitura'}).status_code==409
    assert client.put('/api/ed/acesso/usuarios/'+admin['id'],headers=headers,json={'revogar':'true'}).status_code==400
    operator=client.post('/api/ed/acesso/usuarios',headers=headers,json={'nome':'operador','senha':'senha operador segura','papel':'operador'}).json
    client.post('/api/ed/acesso/sair',headers=headers)
    client.post('/api/ed/acesso/login',json={'nome':'operador','senha':'senha operador segura'})
    op_headers={'X-EDY-CSRF':client.get('/api/ed/acesso/sessao').json['csrf']}
    job=client.post('/api/ed/fluxos',headers=op_headers,json={'plano':{'acao':'consultar'}}).json
    client.post('/api/ed/acesso/sair',headers=op_headers)
    client.post('/api/ed/acesso/login',json={'nome':'admin','senha':'senha local teste segura'})
    headers={'X-EDY-CSRF':client.get('/api/ed/acesso/sessao').json['csrf']}
    assert client.put('/api/ed/acesso/usuarios/'+operator['id'],headers=headers,json={'papel':'leitura'}).status_code==200
    with client.application.app_context():flows.run(client.application,job['id'])
    failed=client.get('/api/ed/fluxos/'+job['id']).json
    assert failed['estado']=='falhou' and failed['etapas'][0]['tentativas']==0
    assert 'revogada' in failed['mensagem']
    assert client.put('/api/ed/acesso/usuarios/'+operator['id'],headers=headers,json={'revogar':True}).status_code==200
    with client.application.app_context(),connection() as con:
        assert not con.execute('SELECT 1 FROM memberships WHERE user_id=?',(operator['id'],)).fetchone()


def test_queued_provider_operation_rechecks_current_role(client,monkeypatch):
    import ed_tasks
    from ed_services import ler_job
    from flask import g
    headers=activate(client)
    user=client.post('/api/ed/acesso/usuarios',headers=headers,json={'nome':'operador','senha':'senha operador segura','papel':'operador'}).json
    execute=ed_tasks.executar;monkeypatch.setattr(ed_tasks,'executar',lambda *args:None)
    called=[]
    with client.application.app_context():
        g.actor={'id':user['id'],'papel':'operador','workspace':'principal'}
        job=ed_tasks.iniciar('codex','chat_interpretacao',None,{},lambda *args:called.append(True))
    assert client.put('/api/ed/acesso/usuarios/'+user['id'],headers=headers,json={'papel':'leitura'}).status_code==200
    execute(client.application,job['id'],lambda *args:called.append(True))
    with client.application.app_context():finished=ler_job(job['id'])
    assert finished['estado']=='erro' and 'revogada' in finished['mensagem'] and not called
