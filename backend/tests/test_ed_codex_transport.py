import json
import queue
import pytest
from test_ed_enrich import client


def test_legacy_timeout_is_execution_failure_and_nested_list_diagnosis():
    from ed_codex_transport import operation_issue,RuntimeFailure
    old={'diagnostico':{'categoria':'incompleta','erro':{'message':'Prazo de 600 segundos excedido; sem repetir a chamada.'}}}
    assert operation_issue(old)=='execucao'
    assert operation_issue({'diagnostico':{'categoria':'autenticacao','http_status':401}}) is None
    assert operation_issue({'diagnostico':{'categoria':'incompleta','erro':{'message':'Resposta incompleta por outro motivo'}}}) is None
    nested=RuntimeFailure({'errors':[{'status':403,'request_id':'nested-request'}]})
    assert nested.diagnostic['http_status']==403 and nested.diagnostic['request_id']=='nested-request'


def test_full_error_preserves_status_request_id_and_redacts_credentials():
    from ed_codex_transport import RuntimeFailure
    event = {'message': 'x' * 1400, 'httpStatusCode': 400, 'request_id': 'req-test-123',
             'access_token': 'secret-test', 'detail': 'Bearer abc.def.ghi', 'codexErrorInfo': 'modelNotFound'}
    error = RuntimeFailure(event)
    assert error.diagnostic['categoria'] == 'modelo_recusado'
    assert error.diagnostic['http_status'] == 400
    assert error.diagnostic['request_id'] == 'req-test-123'
    assert len(error.diagnostic['erro']['message']) == 1400
    assert 'secret-test' not in json.dumps(error.diagnostic)
    assert 'abc.def.ghi' not in json.dumps(error.diagnostic)


def test_stream_partial_is_not_success_and_ignores_other_turn():
    from ed_codex_transport import consume, RuntimeFailure
    class RPC:
        def __init__(self, events): self.events = iter(events)
        def receive(self, timeout): return next(self.events)
    foreign = {'method': 'turn/completed', 'params': {'threadId': 'other', 'turn': {'id': 'x', 'status': 'completed'}}}
    partial = {'method': 'item/agentMessage/delta', 'params': {'threadId': 't', 'turnId': 'u', 'itemId': 'i', 'delta': 'partial'}}
    failed = {'method': 'turn/completed', 'params': {'threadId': 't', 'turn': {'id': 'u', 'status': 'failed', 'error': {'message': 'HTTP 401', 'httpStatusCode': 401}}}}
    with pytest.raises(RuntimeFailure) as exc:
        consume(RPC([foreign, partial, failed]), 't', 'u', lambda: None, lambda *a, **k: None)
    assert exc.value.diagnostic['categoria'] == 'autenticacao'


def test_stream_only_final_message_completed_and_usage():
    from ed_codex_transport import consume
    events = iter([
        {'method': 'item/completed', 'params': {'threadId': 't', 'turnId': 'u', 'item': {'type': 'agentMessage', 'id': 'a', 'phase': 'commentary', 'text': 'Working'}}},
        {'method': 'item/completed', 'params': {'threadId': 't', 'turnId': 'u', 'item': {'type': 'agentMessage', 'id': 'b', 'phase': 'final_answer', 'text': '{"ok":true}'}}},
        {'method': 'thread/tokenUsage/updated', 'params': {'threadId': 't', 'turnId': 'u', 'tokenUsage': {'last': {'totalTokens': 12}}}},
        {'method': 'turn/completed', 'params': {'threadId': 't', 'turn': {'id': 'u', 'status': 'completed'}}},
    ])
    class RPC:
        def receive(self, timeout): return next(events)
    text, usage = consume(RPC(), 't', 'u', lambda: None, lambda *a, **k: None)
    assert text == '{"ok":true}' and usage['totalTokens'] == 12


def test_rpc_call_preserves_notifications():
    from ed_runtime import RPC
    rpc = object.__new__(RPC)
    rpc.counter = 0
    rpc.pending = []
    rpc.lines = queue.Queue()
    rpc.lines.put({'method': 'item/agentMessage/delta', 'params': {'delta': 'first'}})
    rpc.lines.put({'id': 1, 'result': {'turn': {'id': 'u'}}})
    rpc.send = lambda value: None
    assert rpc.call('turn/start', {}) == {'turn': {'id': 'u'}}
    assert rpc.receive(2)['params']['delta'] == 'first'


def test_nested_http_error_and_secret_redaction():
    from ed_codex_transport import RuntimeFailure
    error=RuntimeFailure({'message':json.dumps({'status':400,'request_id':'req-original','accessToken':'never-print','error':{'code':'unsupported_model','message':"The 'gpt-6.1-sol' model is not supported"}})})
    assert error.diagnostic['http_status']==400 and error.diagnostic['request_id']=='req-original'
    assert error.diagnostic['codigo']=='unsupported_model'
    assert 'never-print' not in str(error)


@pytest.mark.parametrize('status',[401,403,429,500])
def test_failure_cannot_replace_a_completed_version_or_manual_briefing(client,monkeypatch,tmp_path,status):
    import ed_runtime
    e=client.post('/api/ed/empresas',json={'nome':'Empresa','descricao':'Fato revisado'}).get_json()
    root='/api/ed/empresas/'+e['id']
    export=client.post(root+'/exportacoes').get_json()
    composition=client.get(root+'/composicao').get_json()
    class RPC:
        fail=False
        def __init__(self,*args):self.audit={'versao':'test-only'}
        def login(self,mode):return {'modo':mode,'identificador':'test-account'}
        def close(self):pass
        def call(self,method,params):return {'thread':{'id':'thread'}} if method=='thread/start' else {'turn':{'id':'turn'}}
        def receive(self,timeout):
            if self.fail:return {'method':'turn/completed','params':{'threadId':'thread','turn':{'id':'turn','status':'failed','error':{'httpStatusCode':status,'requestId':'req-failed'}}}}
            if not getattr(self,'sent',False):
                self.sent=True
                return {'method':'item/completed','params':{'threadId':'thread','turnId':'turn','item':{'type':'agentMessage','text':json.dumps({'files':[{'path':'index.html','content':'<title>Original</title>'}],'pendencias':[]})}}}
            return {'method':'turn/completed','params':{'threadId':'thread','turn':{'id':'turn','status':'completed'}}}
    monkeypatch.setattr(ed_runtime,'RPC',RPC);monkeypatch.setattr(ed_runtime,'artefact_root',lambda c,j:tmp_path/j)
    params={'exportacao_id':export['id'],'modo':'plano','modelo':'gpt-6.1-sol','instrucoes':'Pedido manual','anterior':''}
    original=client.post(root+'/construcoes',json=params).get_json()
    assert original['estado']=='concluida'
    RPC.fail=True;params['anterior']=original['id']
    failed=client.post(root+'/construcoes',json=params).get_json()
    assert failed['estado']=='erro' and 'resultado' not in failed
    assert failed['diagnostico']['http_status']==status and failed['diagnostico']['request_id']=='req-failed'
    assert failed['parametros']['modelo']=='gpt-6.1-sol' and failed['parametros']['modo']=='plano' and failed['parametros']['instrucoes']=='Pedido manual'
    assert (tmp_path/original['id']/'index.html').read_text()=='<title>Original</title>'
    assert client.get(root+'/composicao').get_json()==composition
    assert client.get(root).get_json()['descricao']=='Fato revisado'
    assert client.post(root+'/construcoes/'+failed['id']+'/abrir',json={}).status_code==400


def test_cancellation_during_terminal_wait_is_not_completed():
    from ed_codex_transport import consume
    cancelled=False
    class RPC:
        def receive(self,timeout):
            nonlocal cancelled
            cancelled=True
            return {'method':'turn/completed','params':{'turn':{'status':'completed'}}}
    def active():
        if cancelled:raise InterruptedError()
    with pytest.raises(InterruptedError):consume(RPC(),'t',None,active,lambda *a,**k:None)
