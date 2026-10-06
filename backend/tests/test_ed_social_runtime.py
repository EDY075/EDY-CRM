import io,json,zipfile,hashlib
import pytest
from test_ed_enrich import client


def lead(client):return client.post('/api/ed/empresas',json={'nome':'Empresa teste','descricao':'Texto manual revisado','confirmado':True}).get_json()


def test_perfil_and_carousel_normalization():
    from ed_social import perfil,normalizar
    assert perfil('https://www.instagram.com/empresa.teste/')=='empresa.teste'
    for p in ('https://instagram.com/p/abc','https://evil.org/empresa','abc?token=segredo'):
        with pytest.raises(ValueError):perfil(p)
    r=normalizar([{'id':'123','url':'https://instagram.com/p/123/','caption':'Legenda','timestamp':'2026-10-04','childPosts':[
        {'id':'1','displayUrl':'https://cdn.example.org/original1.jpg','dimensionsWidth':1080,'dimensionsHeight':1350},
        {'id':'2','displayUrl':'https://cdn.example.org/original2.jpg','dimensionsWidth':1200,'dimensionsHeight':800}]}],'apify','empresa')
    assert len(r['imagens'])==2
    assert r['imagens'][1]['carrossel_indice']==1
    assert not any(m['autorizado'] for m in r['imagens'])
    assert r['imagens'][0]['largura']==1080


def test_credential_missing_association_race_and_manual_preservation(client,monkeypatch):
    monkeypatch.setattr('ed_secrets.get',lambda p:'')
    e=lead(client);url='/api/ed/empresas/'+e['id']+'/instagram'
    data=dict(fornecedor='apify',perfil='empresa',modo='materiais',consulta='',limite=2,orcamento=.05)
    assert client.post(url+'/pesquisar',json=data).status_code==400
    confirmed=client.post(url+'/confirmar',json={'perfil':'@empresa','valor_anterior':'','evidencia':'Telefone e endereço conferidos no perfil e no site.'}).get_json()
    assert confirmed['estado']=='confirmado'
    assert client.post(url+'/confirmar',json={'perfil':'outra','valor_anterior':'','evidencia':'Revisão de outra conta com telefone confirmado.'}).status_code==409
    assert client.get('/api/ed/empresas/'+e['id']).get_json()['descricao']=='Texto manual revisado'


def test_partial_job_error_and_zero_results_are_not_success(client,monkeypatch):
    from ed_social import ApifyPublic
    monkeypatch.setattr('ed_secrets.get',lambda p:'test-only-secret')
    e=lead(client);root='/api/ed/empresas/'+e['id']+'/instagram'
    def fail(self,job,progress):
        progress(70,'Resultados parciais',parcial={'perfis':[{'usuario':'teste'}],'imagens':[],'pendencias':[]})
        raise ValueError('Fornecedor HTTP 429; nenhuma ficha alterada.')
    monkeypatch.setattr(ApifyPublic,'collect',fail)
    data=dict(fornecedor='apify',perfil='',modo='descobrir',consulta='Empresa Recife',limite=2,orcamento=.05)
    j=client.post(root+'/pesquisar',json=data).get_json()
    assert j['estado']=='erro' and j['parcial']['perfis']
    monkeypatch.setattr(ApifyPublic,'collect',lambda *a:({'perfis':[],'imagens':[],'pendencias':[]},None))
    j=client.post(root+'/pesquisar',json=data).get_json();assert j['estado']=='erro'
    assert 'zero resultados' in j['mensagem']
    assert client.get('/api/ed/empresas/'+e['id']).get_json()['descricao']==e['descricao']


def test_codex_contract_and_resource_paths(tmp_path):
    from ed_runtime import validate_files,validate_references
    with pytest.raises(ValueError):validate_files({'files':[{'path':'../crm.db','content':'x'}],'pendencias':[]})
    files=[{'path':'index.html','content':'<link rel="stylesheet" href="style.css"><img src="materiais/foto.png">'}]
    with pytest.raises(ValueError):validate_references(tmp_path,files)
    (tmp_path/'style.css').write_text('body{}');(tmp_path/'materiais').mkdir();(tmp_path/'materiais/foto.png').write_bytes(b'x')
    validate_references(tmp_path,files)
    with pytest.raises(ValueError):validate_references(tmp_path,[{'path':'index.html','content':'<script src="https://evil.org/x.js"></script>'}])


def test_image_protection_restores_pixels_and_original(client):
    from PIL import Image
    e=lead(client);data=io.BytesIO();Image.new('RGB',(100,100),'#345678').save(data,'PNG')
    m=client.post('/api/ed/empresas/'+e['id']+'/materiais',data={'arquivo':(io.BytesIO(data.getvalue()),'original.png')}).get_json()
    root='/api/ed/empresas/'+e['id']+'/materiais/'+m['id']+'/studio'
    options=dict(acao='local',natureza='pessoa',protegidas=[[.2,.2,.5,.5]],recorte=[0,0,1,1],exposicao=1.5,contraste=1,destino='desktop',instrucoes='Proteger identidade')
    v=client.post(root+'/editar',json=options).get_json()
    output=Image.open(io.BytesIO(client.get(v['arquivo_url']).data))
    assert output.getpixel((30,30))[:3]==(52,86,120)
    assert output.getpixel((5,5))[:3]!=(52,86,120)
    assert client.get(m['arquivo_url']).data==data.getvalue()


def test_portable_export_contract_is_owned_and_versions_are_immutable(client,tmp_path):
    e=lead(client);eid=e['id'];root='/api/ed/empresas/'+eid
    c=client.get(root+'/composicao').get_json();c['secoes'][0]['alternativas'][0]['titulo']='Texto refinado manual'
    client.put(root+'/composicao',json=c)
    exported=client.post(root+'/exportacoes').get_json();content=client.get(exported['zip_url']).data
    with zipfile.ZipFile(io.BytesIO(content)) as z:
        expected={'empresa.md','briefing.md','DESIGN.md','referencias.md','conteudo.json','materiais.json','composicao.json','prompt-codex.md','LEIA-ME.md'}
        assert expected<=set(z.namelist());z.extractall(tmp_path/'outro-local')
        assert json.loads(z.read('conteudo.json'))['exportacao_id']==exported['id']
        assert json.loads(z.read('composicao.json'))['secoes'][0]['alternativas'][0]['titulo']=='Texto refinado manual'
        assert b'ED_CRM_' not in content
    assert client.get(exported['zip_url']).data==content
    other=lead(client)
    assert client.post('/api/ed/empresas/'+other['id']+'/construcoes',json=dict(exportacao_id=exported['id'],modo='plano',modelo='gpt-6.1-sol',instrucoes='',anterior='')).status_code==400


def test_cancelled_task_cannot_commit_late_result(client):
    import ed_tasks,ed_services
    e=lead(client)
    with client.application.app_context():
        def worker(job,progress):
            cancelled=ed_services.ler_job(job['id']);cancelled['estado']='cancelada';ed_services.save(cancelled)
            progress(90,'Não aplicar depois do cancelamento')
            pytest.fail('Job cancelado continuou')
        job=ed_tasks.iniciar('local','teste_cancelamento',e['id'],{},worker)
        assert job['estado']=='cancelada' and 'resultado' not in job
