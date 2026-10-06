import io,json,zipfile
import pytest
from PIL import Image
from test_ed_enrich import client

def company(client):return client.post('/api/ed/empresas',json={'nome':'Padaria de teste','nicho':'Padarias','confirmado':True,'descricao':'Edição manual preservada'}).get_json()
def upload(client,e,name='foto.png'):
    out=io.BytesIO();Image.new('RGB',(600,400),'#876543').save(out,'PNG')
    return client.post('/api/ed/empresas/'+e['id']+'/materiais',data={'arquivo':(io.BytesIO(out.getvalue()),name),'origem':'Original próprio de teste','atribuicao':'Titular','autorizado':'true'}).get_json()

@pytest.mark.parametrize('kind,title',[('landing','landing page'),('site','site completo'),('dashboard','dashboard'),('admin','painel administrativo')])
def test_export_prompt_uses_final_composition_type(client,kind,title):
    e=company(client);root='/api/ed/empresas/'+e['id']
    c=client.get(root+'/composicao').get_json();c['tipo']=kind
    assert client.put(root+'/composicao',json=c).status_code==200
    export=client.post(root+'/exportacoes').get_json()
    archive=zipfile.ZipFile(io.BytesIO(client.get(export['zip_url']).data))
    prompt=archive.read('prompt-codex.md').decode()
    assert title in prompt.splitlines()[0]
    assert json.loads(archive.read('conteudo.json'))['tipo']==kind
    if kind in ('dashboard','admin'):assert 'Prepare uma landing page navegável' not in prompt
    assert 'não houve leitura de perfis' not in archive.read('empresa.md').decode()

@pytest.mark.parametrize('content',[
    '<video poster="ausente.png"></video>',
    '<div style="background-image:url(ausente.png)"></div>',
    '<style>@import "ausente.css";</style>',
    '<style>body{background:url(https://externo.test/foto.png)}</style>',
])
def test_runtime_checks_inline_and_media_resources(tmp_path,content):
    from ed_runtime import validate_references
    with pytest.raises(ValueError):validate_references(tmp_path,[{'path':'index.html','content':content}])

def test_import_validation_does_not_persist_bad_contract(client):
    e=company(client);root='/api/ed/empresas/'+e['id']+'/composicao'
    state=client.get(root).get_json();before=json.loads(json.dumps(state))
    state['secoes'][0]['alternativas']=[{}, {}, {}, {}]
    assert client.post(root+'/validar',json=state).status_code==400
    assert client.get(root).get_json()==before
    assert client.get(root+'/historico').get_json()==[]
    assert before['identidade']['fundo']=='#f4ede2' and before['identidade']['tinta']=='#3c2d24'

def test_image_api_missing_invalid_response_and_original_preserved(client,monkeypatch):
    from ed_images import OpenAIImages
    e=company(client);m=upload(client,e);root='/api/ed/empresas/'+e['id']+'/materiais/'+m['id']+'/studio'
    original=client.get(m['arquivo_url']).data
    monkeypatch.setattr('ed_secrets.get',lambda p:'')
    options={'acao':'ia','natureza':'ilustracao','instrucoes':'Melhorar apresentação da ilustração'}
    assert client.post(root+'/editar',json=options).status_code==400
    monkeypatch.setattr('ed_secrets.get',lambda p:'secret-test-only')
    def fail(*args):raise ValueError('Edição recusada: HTTP 401. Nenhuma versão gerada.')
    monkeypatch.setattr(OpenAIImages,'edit',fail)
    job=client.post(root+'/editar',json=options).get_json()
    assert job['estado']=='erro' and 'HTTP 401' in job['mensagem']
    assert client.get(m['arquivo_url']).data==original
    assert client.get(root).get_json()['versoes']==[]

def test_edited_export_keeps_original_and_revoked_dependency_blocks(client):
    e=company(client);m=upload(client,e);logo=upload(client,e,'logo.png');root='/api/ed/empresas/'+e['id']
    client.patch(root+'/materiais/'+logo['id'],json={'selecionado':True})
    version=client.post(root+'/materiais/'+m['id']+'/studio/editar',json={'acao':'local','logo_id':logo['id'],'recorte':[0,0,.7,1]}).get_json()
    assert client.post(root+'/materiais/'+m['id']+'/studio/selecionar',json={'versao':version['id'],'selecionado':True}).status_code==200
    export=client.post(root+'/exportacoes').get_json()
    archive=zipfile.ZipFile(io.BytesIO(client.get(export['zip_url']).data))
    manifest=json.loads(archive.read('materiais.json'))
    original=next(x for x in manifest if x.get('papel')=='original_preservado')
    assert archive.read(original['arquivo'])==client.get(m['arquivo_url']).data
    client.patch(root+'/materiais/'+logo['id'],json={'selecionado':False,'autorizado':False})
    assert client.post(root+'/exportacoes').status_code==400

def test_social_signals_remain_candidates():
    from ed_social import evidencias
    result={'perfis':[{'nome':'Empresa X','bio':'Curitiba, telefone 41999999999','site':'https://sites.google.com/view/empresa-x'}]}
    evidencias(result,{'nome':'Empresa X','cidade':'Curitiba','bairro':'','telefone':'41 99999-9999','site':'https://sites.google.com/view/empresa-x'})
    assert len(result['perfis'][0]['evidencias'])==4
    assert result['perfis'][0]['estado']=='candidato'

def test_mobile_approved_variant_is_portable_and_unreviewed_excluded(client):
    e=company(client);m=upload(client,e);root='/api/ed/empresas/'+e['id'];studio=root+'/materiais/'+m['id']+'/studio'
    desktop=client.post(studio+'/editar',json={'acao':'local','destino':'desktop'}).get_json()
    mobile=client.post(studio+'/editar',json={'acao':'local','destino':'mobile','recorte':[0,0,.5,1]}).get_json()
    pending=client.post(studio+'/editar',json={'acao':'local','destino':'mobile'}).get_json()
    for v in (mobile,desktop):assert client.post(studio+'/selecionar',json={'versao':v['id'],'selecionado':True}).status_code==200
    c=client.get(root+'/composicao').get_json();c['secoes'][0]['alternativas'][0]['material_id']=m['id'];client.put(root+'/composicao',json=c)
    response=client.post(root+'/exportacoes');assert response.status_code==201,response.get_json()
    export=response.get_json();archive=zipfile.ZipFile(io.BytesIO(client.get(export['zip_url']).data))
    comp=json.loads(archive.read('composicao.json'));a=comp['secoes'][0]['alternativas'][0]
    assert a['arquivo'].endswith(desktop['arquivo']) and a['arquivo_mobile'].endswith(mobile['arquivo'])
    assert 'srcset="'+a['arquivo_mobile']+'"' in archive.read('previa-local.html').decode()
    assert not any(pending['id'] in name for name in archive.namelist())
    assert '/api/ed/' not in archive.read('materiais.json').decode()

def test_mcp_missing_and_http_failure_do_not_claim_connection(monkeypatch):
    from ed_components import Components21st
    monkeypatch.setattr('ed_secrets.get',lambda p:'')
    with pytest.raises(ValueError,match='Sem chave'):Components21st().test({})
    monkeypatch.setattr('ed_secrets.get',lambda p:'secret-test-only')
    class Response:
        status_code=401
        def __enter__(self):return self
        def __exit__(self,*args):pass
    class Session:
        def __enter__(self):return self
        def __exit__(self,*args):pass
        def post(self,*args,**kwargs):return Response()
    monkeypatch.setattr('ed_components.requests.Session',Session)
    with pytest.raises(ValueError,match='HTTP 401'):Components21st().test({})

def test_runtime_failed_turn_and_package_snapshot(client,monkeypatch,tmp_path):
    import ed_runtime
    e=company(client);root='/api/ed/empresas/'+e['id'];export=client.post(root+'/exportacoes').get_json()
    state=client.get(root+'/composicao').get_json();state['secoes'][0]['escolhida']='b';client.put(root+'/composicao',json=state)
    class RPC:
        fail=False
        def __init__(self,*args):pass
        def login(self,mode):return {'modo':mode,'tipo':'chatgpt'}
        def close(self):pass
        def call(self,method,params):return {'thread':{'id':'test-thread'}} if method=='thread/start' else {}
        def receive(self,timeout):
            if self.fail:return {'method':'turn/completed','params':{'turn':{'status':'failed','error':{'codexErrorInfo':'modelNotFound'}}}}
            if not getattr(self,'sent',False):
                self.sent=True
                return {'method':'item/completed','params':{'item':{'type':'agentMessage','text':json.dumps({'files':[{'path':'index.html','content':'<!doctype html><title>Teste</title>'}],'pendencias':[]})}}}
            return {'method':'turn/completed','params':{'turn':{'status':'completed'}}}
    monkeypatch.setattr(ed_runtime,'RPC',RPC);monkeypatch.setattr(ed_runtime,'artefact_root',lambda c,j:tmp_path/j)
    params={'exportacao_id':export['id'],'modo':'plano','modelo':'gpt-6.1-sol','instrucoes':'','anterior':''}
    job=client.post(root+'/construcoes',json=params).get_json()
    assert job['estado']=='concluida' and job['resultado']['composicao_revisao']==0
    RPC.fail=True
    failed=client.post(root+'/construcoes',json=params).get_json()
    assert failed['estado']=='erro' and 'modelNotFound' in failed['mensagem'] and 'resultado' not in failed
    assert not (tmp_path/failed['id']/'index.html').exists()
