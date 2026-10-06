import io
from test_ed_enrich import client


def test_contacts_pipeline_tasks_versions_and_real_metrics(client):
    lead=client.post('/api/ed/empresas',json={'nome':'Empresa QA','demonstracao':True}).json
    root='/api/ed/crm/registros/'
    contact=client.post(root+'contato',json={'empresa_id':lead['id'],'nome':'Contato QA','cargo':'Titular a confirmar'}).json
    assert contact['versao']==1
    opportunity=client.post(root+'oportunidade',json={'empresa_id':lead['id'],'titulo':'Prévia para revisão','tags':['padaria','padaria']}).json
    assert opportunity['tags']==['padaria']
    opportunity.update(fase='ganho',motivo='')
    assert client.put(root+'oportunidade/'+opportunity['id'],json=opportunity).status_code==400
    opportunity.update(fase='proposta');new=client.put(root+'oportunidade/'+opportunity['id'],json=opportunity).json
    assert new['versao']==2
    assert client.put(root+'oportunidade/'+opportunity['id'],json=opportunity).status_code==409
    task=client.post(root+'tarefa',json={'empresa_id':lead['id'],'titulo':'Conferir fotos','vencimento':'2020-01-01'}).json
    summary=client.get('/api/ed/crm/resumo').json
    assert summary['oportunidades']==1 and summary['tarefas_abertas']==1 and summary['vencidas']==1
    task['concluida']=True;assert client.put(root+'tarefa/'+task['id'],json=task).status_code==200
    stages=client.get('/api/ed/crm/funil').json
    assert client.put('/api/ed/crm/funil',json=[s for s in stages if s['id']!='proposta']).status_code==400
    assert len(client.get(root+'oportunidade/'+new['id']+'/versoes').json)==2


def test_csv_preview_idempotency_and_formula_safe_export(client):
    raw=b'nome,cidade,telefone\r\nEmpresa CSV,Recife,123\r\n,Recife,456\r\n'
    preview=client.post('/api/ed/crm/csv/validar',data={'arquivo':(io.BytesIO(raw),'leads.csv')}).json
    assert preview['validas']==1 and preview['linhas'][1]['erro']
    request={'id':preview['id'],'linhas':[2]}
    one=client.post('/api/ed/crm/csv/importar',json=request).json
    two=client.post('/api/ed/crm/csv/importar',json=request).json
    assert one['registros'][0]['novo'] and not two['registros'][0]['novo']
    assert len(client.get('/api/ed/empresas').json)==1
    assert client.post('/api/ed/crm/csv/importar',json={'id':preview['id'],'linhas':[3]}).status_code==400
    client.post('/api/ed/empresas',json={'nome':'=CSV Formula QA'})
    assert "'=CSV Formula QA" in client.get('/api/ed/crm/csv').data.decode('utf-8-sig')


def test_merge_preserves_old_lead_history_and_restores_without_overwriting_edits(client):
    a=client.post('/api/ed/empresas',json={'nome':'Empresa QA A','telefone':'123'}).json
    b=client.post('/api/ed/empresas',json={'nome':'Empresa QA B'}).json
    preview=client.post('/api/ed/crm/unioes/avaliar',json={'origem':a['id'],'destino':b['id']}).json
    union=client.post('/api/ed/crm/unioes',json={**preview,'preferir_origem':[]}).json
    assert len(client.get('/api/ed/empresas').json)==1
    assert client.get('/api/ed/empresas/'+a['id']).json['crm_unida_em']==b['id']
    assert client.get('/api/ed/empresas/'+b['id']).json['telefone']=='123'
    assert client.post('/api/ed/crm/unioes/'+union['id']+'/restaurar',json={}).status_code==200
    assert len(client.get('/api/ed/empresas').json)==2
    preview=client.post('/api/ed/crm/unioes/avaliar',json={'origem':a['id'],'destino':b['id']}).json
    union=client.post('/api/ed/crm/unioes',json={**preview,'preferir_origem':[]}).json
    client.patch('/api/ed/empresas/'+b['id'],json={'descricao':'Correção posterior manual'})
    assert client.post('/api/ed/crm/unioes/'+union['id']+'/restaurar',json={}).status_code==409
    assert client.get('/api/ed/empresas/'+b['id']).json['descricao']=='Correção posterior manual'


def test_csv_mapping_rejects_collision_and_preserves_data(client):
    import json
    raw=b'Empresa,Local,Desconhecido\nNome revisavel,Recife,nao importar\n'
    def upload(**kw):return client.post('/api/ed/crm/csv/validar',data={'arquivo':(io.BytesIO(raw),'arquivo.csv'),**kw})
    assert upload(analisar='true').json['cabecalhos']==['Empresa','Local','Desconhecido']
    assert upload(mapeamento=json.dumps({'Empresa':'nome','Local':'nome'})).status_code==400
    valid=upload(mapeamento=json.dumps({'Empresa':'nome','Local':'cidade','Desconhecido':''})).json
    assert valid['validas']==1 and valid['linhas'][0]['dados']=={'nome':'Nome revisavel','cidade':'Recife'}
    assert client.get('/api/ed/empresas').json==[]
