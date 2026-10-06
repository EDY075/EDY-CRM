import io,json,zipfile
import pytest
from test_ed_enrich import client
import ed_visual_research as visual

def test_html_analysis_is_data_does_not_execute_and_no_false_library_claim():
    p=visual.profile(b'<style>:root{--ink:#123456}h1{font-family:Georgia} @media(max-width:500px){}</style><h1>Referencia</h1><section id="hero"><img src="foto.jpg" alt="foto exclusiva"></section><script>throw Error("never run");window.GSAP={}</script>','https://example.org/')
    assert p['observado']['cores_declaradas']==['#123456']
    assert p['observado']['imagens'][0]['origem']=='https://example.org/foto.jpg'
    assert p['aprovado'] is False and 'não comprovados' in p['inferencias'][0]

def test_visual_research_preserves_revised_reference_and_returns_inactive_proposal(client,monkeypatch):
    monkeypatch.setattr(visual,'destino',lambda u:None)
    monkeypatch.setattr(visual,'robots_checker',lambda j: (j.update(robots={'regra':'Allow: /'}) or (lambda _:1)))
    monkeypatch.setattr(visual,'ler_url',lambda u,**kw:(u,b'<h1>Exemplo</h1><section id="hero"></section>','text/html'))
    old=client.post('/api/ed/biblioteca',json={'titulo':'Decisao manual','conteudo':'Texto preservado','tipo':'referencia'}).json
    result=client.post('/api/ed/biblioteca/pesquisar-visual',json={'titulo':'Pesquisa','url':'https://example.org','fonte':'local'}).json
    assert result['estado']=='concluida'
    suggestion=client.get('/api/ed/biblioteca/'+result['resultado']['biblioteca_id']).json
    assert suggestion['estado']=='inativo'
    assert client.get('/api/ed/biblioteca/'+old['id']).json==old

def test_empty_analysis_and_private_url_never_success(client):
    assert client.post('/api/ed/biblioteca/pesquisar-visual',json={'titulo':'Teste','url':'https://localhost'}).status_code==400
    assert client.post('/api/ed/biblioteca/pesquisar-visual',json={'titulo':'Teste','url':'https://example.org/?token=privado'}).status_code==400
    with pytest.raises(ValueError,match='conteúdo suficiente'):visual.profile(b'<div id="root"></div><script src="app.js"></script>','https://example.org')

def test_visual_reference_image_exported_as_reference_not_company_photo(client):
    from PIL import Image
    lead=client.post('/api/ed/empresas',json={'nome':'Empresa de teste'}).json
    raw=io.BytesIO();Image.new('RGB',(40,30),'#336699').save(raw,'PNG')
    item=client.post('/api/ed/biblioteca/importar',data={'arquivo':(io.BytesIO(raw.getvalue()),'referencia.png'),'titulo':'Screenshot visual','conteudo':'Somente inspiracao, nao usar como foto da empresa.','tipo':'referencia','escopo':'lead','vinculo':lead['id']},content_type='multipart/form-data').json
    item['estado']='ativo';client.put('/api/ed/biblioteca/'+item['id'],json=item)
    exported=client.post('/api/ed/empresas/'+lead['id']+'/exportacoes').json
    archive=client.get(exported['zip_url'])
    with zipfile.ZipFile(io.BytesIO(archive.data)) as z:
        refs=json.loads(z.read('referencias-visuais.json'))
        assert refs[0]['uso']=='referencia_visual_apenas' and refs[0]['arquivo'] in z.namelist()
        assert not any(n.startswith('materiais/') for n in z.namelist())
        assert 'path' not in z.read('referencias-visuais.json').decode()


def test_local_command_preserves_design_request_for_generation(client):
    from ed_assistant import local_plan
    from ed_tools import validate_plan
    lead=client.post('/api/ed/empresas',json={'nome':'Empresa real revisada'}).json
    text='Prepare a prévia desta empresa. Hero editorial e tipografia serifada; preserve o resto.'
    with client.application.app_context():
        plan=validate_plan(local_plan(text,{'empresa_id':lead['id'],'geracao':'codex_nativo'}))
        assert plan['instrucoes']==text and plan['geracao']=='codex_nativo'


def test_reference_photo_cannot_be_embedded_as_company_material(tmp_path):
    from ed_runtime import validate_references
    (tmp_path/'referencias').mkdir();(tmp_path/'referencias'/'foto.jpg').write_bytes(b'image')
    with pytest.raises(ValueError,match='Referência visual'):
        validate_references(tmp_path,[{'path':'index.html','content':'<img src="referencias/foto.jpg">'}])
