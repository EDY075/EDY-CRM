"""Contratos testados com transporte mock; não comprovam operação de fornecedor."""
import io
import json
import zipfile
from PIL import Image
from test_ed_enrich import client


def test_native_visual_inputs_and_portable_delivery(client,monkeypatch,tmp_path):
    import ed_runtime
    import ed_codex_transport
    lead=client.post('/api/ed/empresas',json={'nome':'Empresa demonstrativa'}).json
    raw=io.BytesIO();Image.new('RGB',(40,30),'#123456').save(raw,'PNG')
    item=client.post('/api/ed/biblioteca/importar',data={'arquivo':(io.BytesIO(raw.getvalue()),'referencia.png'),'titulo':'Referência autorizada só para inspiração','conteudo':'Composição editorial','tipo':'referencia','escopo':'lead','vinculo':lead['id']}).json
    item['estado']='ativo';client.put('/api/ed/biblioteca/'+item['id'],json=item)
    base='/api/ed/empresas/'+lead['id'];export=client.post(base+'/exportacoes').json
    captured=[]
    class RPC:
        audit={'versao':'mock'}
        def __init__(self,*args):pass
        def login(self,mode):return {'identificador':'mock-account'}
        def call(self,method,params):
            if method=='turn/start':captured.extend(params['input']);return {'turn':{'id':'u'}}
            return {'thread':{'id':'t'}}
        def close(self):pass
    monkeypatch.setattr(ed_runtime,'RPC',RPC)
    monkeypatch.setattr(ed_runtime,'artefact_root',lambda company,job:tmp_path/job)
    monkeypatch.setattr(ed_runtime,'consume',lambda *args,**kw:(json.dumps({'files':[{'path':'index.html','content':'<!doctype html><title>Prévia de teste</title>'}],'pendencias':[]}),{}))
    job=client.post(base+'/construcoes',json={'exportacao_id':export['id'],'modo':'plano','modelo':'gpt-6.1-sol','instrucoes':'Preserve fatos','anterior':''}).json
    assert job['estado']=='concluida'
    assert any(x['type']=='localImage' and x['path'].endswith('.png') for x in captured)
    assert job['resultado']['imagens_enviadas'][0]['uso']=='referencia_visual'
    delivered=client.get(base+'/construcoes/'+job['id']+'/entrega')
    assert delivered.status_code==200
    with zipfile.ZipFile(io.BytesIO(delivered.data)) as archive:
        assert 'index.html' in archive.namelist() and 'ENTREGA.md' in archive.namelist()
        assert not any(x.startswith(('referencias/','skills/','.cache/')) for x in archive.namelist())
        assert json.loads(archive.read('integridade-entrega.json'))['publicado'] is False
    other=client.post('/api/ed/empresas',json={'nome':'Outra empresa'}).json
    assert client.get('/api/ed/empresas/'+other['id']+'/construcoes/'+job['id']+'/entrega').status_code==400
