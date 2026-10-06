import json
from test_ed_enrich import client

def test_batch_two_is_optional_and_never_starts_third_active_child(client):
    ids=[client.post('/api/ed/empresas',json={'nome':'QA academia '+str(i),'cidade':'Recife','confirmado':True}).json['id'] for i in range(3)]
    invalid=client.post('/api/ed/lotes',json={'empresa_ids':ids,'chave':'invalid-limit','concorrencia':3})
    assert invalid.status_code==400
    b=client.post('/api/ed/lotes',json={'empresa_ids':ids,'chave':'two-limit','concorrencia':2}).json
    import ed_batches as batches
    with client.application.app_context():
        batches.tick();after=batches.get(b['id']);assert sum(bool(c['fluxo_id']) for c in after['filhos'])==2
        batches.tick();assert sum(bool(c['fluxo_id']) for c in batches.get(b['id'])['filhos'])==2
import ed_store as store
import ed_batches as batches
from ed_tools import validate_plan,steps

def test_eight_results_require_selection_before_build(client):
    with client.application.app_context():
        p=validate_plan({'acao':'pesquisar','nicho':'Academias','cidade':'Recife','uf':'PE','quantidade':8})
        assert steps(p)==['pesquisar']

def test_batch_idempotent_pause_and_pending_eligibility(client):
    ids=[client.post('/api/ed/empresas',json={'nome':'Academia QA '+str(i),'cidade':'Recife','nicho':'Academias','demonstracao':True}).json['id'] for i in range(5)]
    data={'empresa_ids':ids,'chave':'cinco-qa','exigir_confirmadas':False,'geracao':'templates'}
    x=client.post('/api/ed/lotes',json=data).json
    assert len(x['filhos'])==5 and x['concorrencia']==1
    assert client.post('/api/ed/lotes',json=data).json['id']==x['id']
    assert client.post('/api/ed/lotes',json={**data,'empresa_ids':ids[:4]}).status_code==409
    a=client.post('/api/ed/lotes/'+x['id']+'/pausar',json={}).json
    assert a['estado']=='pausada'
    client.post('/api/ed/lotes/'+x['id']+'/retomar',json={})
    with client.application.app_context():
        y=batches.get(x['id']);assert y['filhos'][0]['fluxo_id']==x['filhos'][0]['fluxo_id']
    assert len(client.get('/api/ed/fluxos').json)==1
    assert client.post('/api/ed/lotes/'+x['id']+'/cancelar',json={}).json['estado']=='cancelada'

def test_bad_lead_does_not_block_others(client):
    a=client.post('/api/ed/empresas',json={'nome':'Academia','cidade':'Recife'}).json['id']
    b=client.post('/api/ed/empresas',json={'nome':'Academia QA Elegível','cidade':'Recife'}).json['id']
    x=client.post('/api/ed/lotes',json={'empresa_ids':[a,b],'chave':'parcial','exigir_confirmadas':False}).json
    assert x['filhos'][0]['estado']=='precisa_atencao'
    with client.application.app_context():batches.tick();x=batches.get(x['id'])
    assert x['filhos'][1]['fluxo_id'] and len(client.get('/api/ed/fluxos').json)==1

def test_paid_and_wrong_capability_cannot_be_free_fallback(client,monkeypatch):
    import ed_creation_providers as p
    monkeypatch.setattr(p,'catalog',lambda *a:[{'id':'openrouter/free','pricing':{'prompt':'0.001','completion':'0'},'supported_parameters':['tools'],'architecture':{'input_modalities':['text','image']}}])
    with client.application.app_context():
        import pytest
        with pytest.raises(ValueError,match='preço zero'):p.chosen_router(fallback=True)
    assert client.put('/api/ed/provedores/config',json={'modelo_openrouter':'openrouter/auto'}).status_code==200
    with client.application.app_context():
        monkeypatch.setattr(p,'catalog',lambda *a:[{'id':'openrouter/auto','pricing':{'prompt':'0','completion':'0'}}])
        with pytest.raises(ValueError,match='não é rota gratuita'):p.chosen_router(fallback=True)
    assert client.post('/api/ed/provedores/openrouter/testar',json={}).json['estado']=='erro'

def test_fallback_only_provider_failures_not_local_errors(client,monkeypatch):
    import ed_runtime,ed_creation_providers as p
    from ed_codex_transport import RuntimeFailure
    monkeypatch.setattr(ed_runtime,'generate',lambda *a:(_ for _ in ()).throw(ValueError('Erro de contrato local')))
    monkeypatch.setattr(p,'router_generate',lambda *a,**k:(_ for _ in ()).throw(AssertionError('fallback indevido')))
    with client.application.app_context():
        import pytest
        with pytest.raises(ValueError,match='contrato local'):p.generate({'parametros':{}},lambda *a,**k:None)

def test_long_context_retrieval_keeps_origin_final_and_essential(client):
    lead=client.post('/api/ed/empresas',json={'nome':'Teste guia','nicho':'Academias'}).json
    content=('Texto editorial geral.\n'*2000)+'\nRESTRIÇÃO FINAL: NÃO PUBLICAR.'
    item=client.post('/api/ed/biblioteca',json={'titulo':'Guia extenso','conteudo':content,'essenciais':'Não inventar serviços, não publicar.','tipo':'contexto','escopo':'lead','vinculo':lead['id'],'prioridade':10}).json
    assert item['conteudo']==content.strip()
    r=client.get('/api/ed/empresas/'+lead['id']+'/contexto').json
    assert 'RESTRIÇÃO FINAL' in r['texto'] and 'Não inventar serviços' in r['texto']
    selected=next(x for x in r['items'] if x['id']==item['id'])
    assert selected['recuperacao']['original_preservado'] and selected['sha256']==item['sha256']
