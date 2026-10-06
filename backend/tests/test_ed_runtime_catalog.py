import json
from test_ed_enrich import client


def test_catalog_is_retained_after_generation_but_never_proves_inference(client,monkeypatch):
    import ed_runtime,ed_store,ed_codex_oauth
    account={'identificador':'conta-A','rotulo':'Teste mock'}
    monkeypatch.setattr(ed_codex_oauth,'native_identity',lambda p:account)
    monkeypatch.setattr(ed_runtime,'probe',lambda m:dict(estado='limitado',modo=m,conta=account,data='2026-10-05',modelos=['gpt-6.1-sol','outro-listado'],modelos_detalhados=[{'slug':x,'display_name':x} for x in ['gpt-6.1-sol','outro-listado']],origem_catalogo='Catálogo de teste; sem fornecedor real'))
    assert client.post('/api/ed/runtime/testar',json={'modo':'plano'}).status_code==200
    with client.application.app_context(),ed_store.conectar() as con:
        # A construção grava diagnóstico operacional independente do catálogo.
        value=dict(estado='conectado',modo='plano',conta=account,mensagem='Inferência mock identificada',data='2026-10-05')
        con.execute('UPDATE ed_config SET valor=? WHERE chave=?',(json.dumps(value),'runtime:diagnostico'))
    result=client.get('/api/ed/runtime').json
    assert result['modelos']==['gpt-6.1-sol','outro-listado'] and result['acessos_modelos']==[]
    monkeypatch.setattr(ed_codex_oauth,'native_identity',lambda p:{'identificador':'conta-B','rotulo':'Outro mock'})
    result=client.get('/api/ed/runtime').json
    assert result['modelos']==[] and result['estado']=='configurado_nao_validado'
