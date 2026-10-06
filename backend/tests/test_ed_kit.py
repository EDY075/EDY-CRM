import hashlib
import io
import json
import zipfile
from PIL import Image
import pytest
from test_ed_enrich import client


def test_revoked_native_login_has_specific_safe_diagnostic():
    from ed_runtime import RPC
    from ed_codex_transport import RuntimeFailure
    rpc=RPC.__new__(RPC)
    rpc.stderr=['HTTP 401 Unauthorized token_revoked; request id: req_test_123',
                'refresh_token_invalidated; access_token=secret-never-show']
    rpc.call=lambda *args,**kwargs:{'account':None}
    with pytest.raises(RuntimeFailure) as error:rpc.login('plano')
    value=error.value.diagnostic
    assert value['categoria']=='autenticacao' and value['http_status']==401
    assert value['codigo']=='refresh_token_invalidated' and value['request_id']=='req_test_123'
    assert 'secret-never-show' not in str(error.value)


def test_context_conflicts_cap_archival_and_portable_skill(client):
    lead=client.post('/api/ed/empresas',json={'nome':'Empresa QA','nicho':'Saúde'}).json
    for scope,link,value in [('global','','antigo'),('nicho','Saúde','nicho'),('projeto',lead['id'],'decisão atual')]:
        last=client.post('/api/ed/biblioteca',json={'titulo':'Mesmo critério','conteudo':value,'escopo':scope,'vinculo':link,'tipo':'skill'}).json
    ctx=client.get('/api/ed/empresas/'+lead['id']+'/contexto').json
    assert next(x for x in ctx['items'] if x['titulo']=='Mesmo critério')['conteudo']=='decisão atual'
    assert len(ctx['conflitos'])==2
    text=client.get('/api/ed/biblioteca/'+last['id']+'/markdown')
    assert text.headers['Content-Disposition'].startswith('attachment')
    assert text.data.startswith(b'---\nname:')
    last['estado']='arquivado';client.put('/api/ed/biblioteca/'+last['id'],json=last)
    assert next(x for x in client.get('/api/ed/empresas/'+lead['id']+'/contexto').json['items'] if x['titulo']=='Mesmo critério')['conteudo']=='nicho'
    export=client.post('/api/ed/empresas/'+lead['id']+'/exportacoes').json
    with zipfile.ZipFile(io.BytesIO(client.get(export['zip_url']).data)) as z:
        used=json.loads(z.read('contexto-usado.json'))
        assert 'disponiveis' not in used
        assert all('original' not in x for x in used['items'])
        for entry in json.loads(z.read('manifesto-pacote.json'))['arquivos']:
            assert hashlib.sha256(z.read(entry['arquivo'])).hexdigest()==entry['sha256']


def test_image_edit_request_has_original_and_authorized_logo(client):
    lead=client.post('/api/ed/empresas',json={'nome':'QA imagens'}).json
    root='/api/ed/empresas/'+lead['id']
    raw=io.BytesIO();Image.new('RGB',(600,400),'red').save(raw,'PNG');data=raw.getvalue()
    def material(name):return client.post(root+'/materiais',data={'arquivo':(io.BytesIO(data),name),'origem':'Próprio QA','atribuicao':'Autor do teste','autorizado':'true'}).json
    original,logo=material('foto.png'),material('logo.png')
    url=root+'/materiais/'+original['id']+'/studio/pacote-edicao'
    result=client.post(url,json={'logo_id':logo['id'],'instrucoes':'Compor logo original sem redesenhar.'})
    assert result.status_code==200
    with zipfile.ZipFile(io.BytesIO(result.data)) as z:
        meta=json.loads(z.read('pedido-edicao.json'))
        assert z.read(meta['original'])==data and z.read(meta['logo']['arquivo'])==data
        assert meta['estado']=='pedido_nao_executado'
    client.patch(root+'/materiais/'+logo['id'],json={'autorizado':False})
    assert client.post(url,json={'logo_id':logo['id']}).status_code==400


def test_connection_test_never_claims_media_operation(client,monkeypatch):
    import ed_services as services
    monkeypatch.setattr('ed_secrets.get',lambda provider:'qa-secret')
    with client.application.app_context():
        fp=services.fingerprint('apify')
        services.log('apify',dict(estado='conectado',mensagem='Auth test',data='2026-10-05',fingerprint=fp,tipo_validacao='autenticacao'))
        card=services.cards()['apify']
        assert card['status_acesso']=='autenticacao_validada' and card['operacoes_validadas']=={}
        services.log('apify',dict(estado='conectado',mensagem='Collected',data='2026-10-06',fingerprint=fp,tipo_validacao='consulta_midia'))
        assert services.cards()['apify']['status_acesso']=='operacao_validada'
        services.log('apify',dict(estado='erro',mensagem='Fornecedor HTTP 429',data='2026-10-07',fingerprint=fp))
        card=services.cards()['apify']
        assert card['status_acesso']=='cota_limite' and 'consulta_midia' in card['operacoes_validadas']
        monkeypatch.setattr('ed_secrets.get',lambda provider:'changed-secret')
        assert services.cards()['apify']['operacoes_validadas']=={}
