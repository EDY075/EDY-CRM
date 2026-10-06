"""Diagnósticos sanitizados e conclusão estrita do streaming app-server."""
import json
import re
import time

SECRET = re.compile(r'(?i)^(authorization|cookie|set-cookie|access_?token|refresh_?token|id_?token|api_?key|code_verifier|client_secret)$')


def sanitize(value):
    if isinstance(value, dict):
        return {k: '[omitido]' if SECRET.match(k) else sanitize(v) for k, v in value.items()}
    if isinstance(value, list): return [sanitize(v) for v in value]
    if not isinstance(value, str): return value
    if value.lstrip().startswith(('{','[')):
        try:return json.dumps(sanitize(json.loads(value)),ensure_ascii=False)
        except ValueError:pass
    value = re.sub(r'(?i)(?:bearer\s+|sk-)[a-z0-9._-]+', '[credencial omitida]', value)
    value = re.sub(r'eyJ[A-Za-z0-9_-]+\.[A-Za-z0-9_-]+\.[A-Za-z0-9_-]+', '[token omitido]', value)
    return re.sub(r'(?i)((?:access_token|refresh_token|id_token|api_key|client_secret|code_verifier|authorization|code|state)=)[^\s&"\x27]+', r'\1[omitido]', value)


def find(value, names, accept=lambda value:True):
    if isinstance(value,str) and value.lstrip().startswith(('{','[')):
        try:return find(json.loads(value),names,accept)
        except ValueError:return None
    if isinstance(value, dict):
        for k, v in value.items():
            if k in names and v is not None and accept(v): return v
        for v in value.values():
            result = find(v, names,accept)
            if result is not None: return result
    if isinstance(value, list):
        for v in value:
            result = find(v, names,accept)
            if result is not None: return result


def operation_issue(operation):
    """Inclui timeouts legados sem código, preservando o diagnóstico original."""
    diagnosis=operation.get('diagnostico') or {}
    if diagnosis.get('codigo') in ('timeout','network') or diagnosis.get('http_status') in (500,502,503,504):return 'execucao'
    error=diagnosis.get('erro') or {}
    text=str(error.get('message','')) if isinstance(error,dict) else ''
    if diagnosis.get('categoria')=='incompleta' and re.fullmatch(r'Prazo de \d+ segundos excedido; sem repetir a chamada\.',text):return 'execucao'
    return None


class RuntimeFailure(ValueError):
    def __init__(self, error, terminal=None):
        error = sanitize(error)
        raw = json.dumps(error, ensure_ascii=False)
        # Algumas versões incluem o corpo HTTP como texto no error.message.
        status = find(error, {'httpStatusCode', 'http_status', 'status_code', 'status'},lambda value:type(value)==int)
        if not isinstance(status,int): status=None
        if status is None:
            match = re.search(r'(?:HTTP\s*|"status"\s*:\s*)([45]\d\d)', raw, re.I)
            if match: status = int(match[1])
        request_id = find(error, {'requestId', 'request_id', 'x-request-id'})
        if request_id is None:
            match = re.search(r'(?:request[_ -]?id|x-request-id)[\s:=\\"\x27]+([\w-]+)', raw, re.I)
            if match: request_id = match[1]
        low = raw.lower()
        if status == 401 or 'unauthorized' in low: category = 'autenticacao'
        elif status == 403: category = 'permissao'
        elif 'modelnotfound' in low or ('model' in low and any(s in low for s in ('not supported', 'not found', 'unsupported', 'not available'))): category = 'modelo_recusado'
        elif terminal in ('interrupted', 'cancelled'): category = 'interrompida'
        elif terminal == 'incomplete': category = 'incompleta'
        else: category = 'servico'
        self.diagnostic = dict(categoria=category, http_status=status, request_id=request_id,
                               codigo=find(error, {'code', 'codexErrorInfo'}), terminal=terminal, erro=error)
        messages = {'modelo_recusado': 'O fornecedor recusou o modelo solicitado.', 'autenticacao': 'A autenticação foi recusada ou expirou.',
                    'permissao': 'A conta/workspace não tem permissão para esta operação.', 'incompleta': 'A resposta terminou incompleta.',
                    'interrompida': 'A geração foi interrompida.', 'servico': 'O app-server/fornecedor não concluiu a solicitação.'}
        super().__init__(messages[category] + (' HTTP ' + str(status) + '.' if status else '') +
                         ' Nenhuma inferência concluída; modelo e cobrança preservados. Detalhes: ' + raw)


def consume(rpc, thread, turn, active, progress, timeout=240):
    start = time.monotonic()
    last = 0
    items = {}
    usage = None
    errors = []
    last_event=start
    while time.monotonic() - start < timeout:
        active()
        event = rpc.receive(2)
        method, params = event.get('method', ''), event.get('params', {})
        if params.get('threadId') and params['threadId'] != thread: continue
        event_turn = params.get('turnId') or params.get('turn', {}).get('id')
        if turn and event_turn and event_turn != turn: continue
        if method:last_event=time.monotonic()
        if time.monotonic()-last>15:
            progress(55, 'Codex em execução; aguardando conclusão. '+str(int(time.monotonic()-start))+' s decorridos.',ultima_atividade_segundos=int(time.monotonic()-last_event),turno_ativo=turn)
            last=time.monotonic()
        if method == 'item/agentMessage/delta':
            key = params.get('itemId', 'legacy')
            item = items.setdefault(key, {'text': '', 'phase': None})
            item['text'] += params.get('delta', '')
            size = sum(len(v['text']) for v in items.values())
            if size > 2_500_000: raise RuntimeFailure({'message': 'Saída acima do limite; interrompida.'}, 'incomplete')
            if time.monotonic() - last > 2:
                progress(55, f'Codex escrevendo; {size} caracteres recebidos. Aguardando conclusão do turno.')
                last = time.monotonic()
        elif method == 'item/completed' and params.get('item', {}).get('type') == 'agentMessage':
            item = params['item']
            items[item.get('id', 'legacy')] = {'text': item.get('text', ''), 'phase': item.get('phase')}
        elif method == 'thread/tokenUsage/updated':
            usage = {k: v for k, v in params.get('tokenUsage', {}).get('last', {}).items() if isinstance(v, (int, float))}
        elif method == 'error':
            errors.append(params.get('error', params))
            progress(55, 'Fornecedor informou um erro; aguardando estado terminal.', erro_parcial=sanitize(errors[-1]))
        elif method == 'turn/completed':
            active() # Cancelamento recebido durante a espera não vira sucesso tardio.
            terminal = params.get('turn', {})
            if terminal.get('status') != 'completed':
                raise RuntimeFailure({'turn': terminal, 'eventos': errors}, terminal.get('status'))
            # Um erro transitório pode ser recuperado pelo servidor. Só o terminal decide.
            candidates = [v['text'] for v in items.values() if v['phase'] == 'final_answer']
            if not candidates: candidates = [v['text'] for v in items.values() if v['phase'] != 'commentary']
            text = candidates[-1] if candidates else ''
            if not text.strip(): raise RuntimeFailure({'message': 'Turno completed sem resposta final.'}, 'incomplete')
            return text, usage
    raise RuntimeFailure({'message': f'Prazo de {timeout} segundos excedido; sem repetir a chamada.', 'code':'timeout'}, 'incomplete')
