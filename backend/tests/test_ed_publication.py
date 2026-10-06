"""Publicação reproduzível: dados fictícios e fronteira de banco demonstrativo."""
from pathlib import Path
import pytest
from test_ed_enrich import client


def test_dashboard_accepts_task_without_optional_due_date(client):
    task=client.post('/api/ed/crm/registros/tarefa',json={'titulo':'Revisão fictícia','concluida':False})
    assert task.status_code==201
    response=client.get('/api/ed/crm/resumo')
    assert response.status_code==200
    assert response.json['vencidas']==0 and response.json['tarefas_abertas']==1


def test_seed_rejects_working_database_before_any_write(client):
    import demonstracao
    with pytest.raises(ValueError,match='só pode operar em data-demo'):
        demonstracao.seed(client.application)
    assert client.get('/api/ed/empresas').json==[]


def test_preview_workspace_respects_checkout_configuration(client,tmp_path):
    from ed_runtime import artefact_root
    client.application.config['PREVIEW_ROOT']=tmp_path/'isolado'/'previas'
    with client.application.app_context():
        assert artefact_root('empresa','projeto')==tmp_path/'isolado'/'previas'/'empresa'/'projeto'


def test_preview_csp_only_allows_selected_loopback_crm(client,monkeypatch,tmp_path):
    import requests,ed_runtime
    from test_ed_preview_access import built
    lead,jid,root=built(client,monkeypatch,tmp_path)
    client.application.config['PREVIEW_FRAME_ORIGIN']='http://127.0.0.1:5180'
    result=client.post(f'/api/ed/empresas/{lead["id"]}/construcoes/{jid}/abrir',json={})
    assert result.status_code==200
    try:
        policy=requests.get(result.json['url'],timeout=4).headers['Content-Security-Policy']
        assert 'frame-ancestors http://127.0.0.1:5180;' in policy
        assert '*' not in policy and 'http://127.0.0.1:5128' not in policy
    finally:
        process=ed_runtime.processes.pop(jid)[0];process.terminate();process.wait(timeout=5)


def test_preview_rejects_remote_frame_origin(tmp_path):
    import subprocess,sys
    root=Path(__file__).resolve().parents[2]
    command=[sys.executable,str(root/'scripts/preview_static.py'),'--directory',str(tmp_path),'--port','5189','--crm-origin','https://external.example']
    result=subprocess.run(command,capture_output=True,timeout=5)
    assert result.returncode==2


def test_complete_seed_is_fictitious_idempotent_and_uses_real_local_constructor(tmp_path,monkeypatch):
    import demonstracao
    from ed_app import criar_app
    directory=tmp_path/'checkout'/'data-demo'
    monkeypatch.setattr(demonstracao,'DEMO_ROOT',directory)
    app=criar_app({'DATA_DIR':directory,'PREVIEW_ROOT':directory/'previas','RUN_JOBS':False})
    demonstracao.seed(app)
    client=app.test_client()
    leads=client.get('/api/ed/empresas').json
    assert len(leads)==3 and all(x['demonstracao'] for x in leads)
    for lead in leads:
        value=client.get('/api/ed/empresas/'+lead['id']).json
        assert all(value[k] for k in ('descricao','servicos','horarios','endereco','telefone','email','site','instagram'))
        assert value['site'].endswith('.example') and value['telefone']=='(00) 0000-0000'
        assert len(value['materiais'])==2 and len(value['exportacoes'])==1
        assert all(m['natureza']=='ilustracao' for m in value['materiais'])
        jobs=client.get('/api/ed/empresas/'+lead['id']+'/construcoes').json
        assert len(jobs)==1 and jobs[0]['tipo']=='template_construcao' and jobs[0]['estado']=='concluida'
        assert (directory/'previas'/lead['id']/jobs[0]['id']/'index.html').is_file()
    demonstracao.seed(app)
    assert len(client.get('/api/ed/empresas').json)==3
    assert client.get('/api/ed/crm/resumo').json['oportunidades']==3
    assert not (tmp_path/'checkout'/'data'/'ed-crm.db').exists()
