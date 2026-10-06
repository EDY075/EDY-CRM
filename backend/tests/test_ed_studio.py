import copy
from test_ed_enrich import client


def test_composition_versions_conflicts_locks_and_ownership(client):
    lead = client.post('/api/ed/empresas', json={'nome':'Padaria real para teste','nicho':'Padarias'}).get_json()
    root = '/api/ed/empresas/'+lead['id']+'/composicao'
    state = client.get(root).get_json()
    assert len(state['secoes'][0]['alternativas']) == 4
    assert len({a['layout'] for a in state['secoes'][0]['alternativas']}) == 4
    state['secoes'][0]['escolhida'] = 'b'
    saved = client.put(root, json=state).get_json()
    assert saved['revisao'] == 1
    assert client.put(root, json=state).status_code == 409
    saved['secoes'][0]['fixada'] = True
    locked = client.put(root, json=saved).get_json()
    locked['secoes'][0]['escolhida'] = 'c'
    assert client.put(root,json=locked).status_code == 400
    unlocked = client.get(root).get_json(); unlocked['secoes'][0]['fixada'] = False
    unlocked['secoes'][0]['alternativas'][0]['material_id'] = 'outra-empresa'
    assert client.put(root,json=unlocked).status_code == 400
    assert len(client.get(root+'/historico').get_json()) == 2


def test_image_original_and_local_version_rights(client):
    import io, hashlib
    from PIL import Image
    lead = client.post('/api/ed/empresas', json={'nome':'Teste imagens'}).get_json()
    data=io.BytesIO(); Image.new('RGB',(600,400),'#654321').save(data,'PNG'); original=data.getvalue()
    m = client.post('/api/ed/empresas/'+lead['id']+'/materiais',data={'arquivo':(io.BytesIO(original),'produto.png'),'origem':'Original próprio','atribuicao':'Titular','autorizado':'true'}).get_json()
    root='/api/ed/empresas/'+lead['id']+'/materiais/'+m['id']+'/studio'
    quality=client.get(root).get_json()
    assert quality['original_sha256']==hashlib.sha256(original).hexdigest()
    assert quality['avaliacao']['largura']==600
    version=client.post(root+'/editar',json={'acao':'local','recorte':[0,0,.5,1],'exposicao':1.1,'contraste':1,'destino':'mobile','instrucoes':'Recorte à esquerda','natureza':'produto','protegidas':[]}).get_json()
    assert version['largura']==300
    assert client.get(m['arquivo_url']).data==original
    assert client.post(root+'/selecionar',json={'versao':version['id'],'selecionado':True}).status_code==200
    client.patch('/api/ed/empresas/'+lead['id']+'/materiais/'+m['id'],json={'selecionado':False,'autorizado':False})
    assert client.post(root+'/selecionar',json={'versao':version['id'],'selecionado':True}).status_code==400
    assert client.get(m['arquivo_url']).data==original
