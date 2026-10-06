"""21st HTTP MCP: descoberta real de ferramentas, sem geração hospedada automática."""
import json,time
import requests
import ed_secrets

class Components21st:
    def test(self,settings):
        key=ed_secrets.get('twentyfirst')
        if not key:raise ValueError('Sem chave 21st atual. Chaves antigas Magic foram revogadas pelo fornecedor.')
        headers={'x-api-key':key,'Content-Type':'application/json','Accept':'application/json, text/event-stream'}
        with requests.Session() as session:
            session.trust_env=False
            def call(message):
                started=time.monotonic()
                try:
                    with session.post('https://21st.dev/api/mcp',headers=headers,json=message,timeout=(5,25),allow_redirects=False,stream=True) as res:
                        if not 200<=res.status_code<300:raise ValueError(f'21st MCP respondeu HTTP {res.status_code}; confirme chave e plano. Nenhuma geração realizada.')
                        sid=res.headers.get('Mcp-Session-Id')
                        if sid:headers['Mcp-Session-Id']=sid[:200]
                        if res.status_code==202:return {}
                        chunks=[];size=0
                        for chunk in res.iter_content(16384):
                            size+=len(chunk)
                            if size>1_000_000 or time.monotonic()-started>30:raise ValueError('Resposta MCP acima do limite.')
                            chunks.append(chunk)
                        content=b''.join(chunks).decode('utf-8')
                        if 'text/event-stream' in res.headers.get('Content-Type',''):
                            events=[line[5:].strip() for line in content.splitlines() if line.startswith('data:')]
                            if not events:raise ValueError('MCP não retornou evento de resposta.')
                            value=json.loads(events[-1])
                        else:value=json.loads(content)
                        if value.get('error'):raise ValueError('MCP recusou a operação (código '+str(value['error'].get('code'))+'). Não repetir automaticamente.')
                        return value.get('result',{})
                except (requests.RequestException,json.JSONDecodeError,UnicodeError):raise ValueError('Falha de rede ou interpretação no MCP 21st.') from None
            response=call({'jsonrpc':'2.0','id':1,'method':'initialize','params':{'protocolVersion':'2025-03-26','capabilities':{},'clientInfo':{'name':'edy-crm','version':'0.3.0'}}})
            version=response.get('protocolVersion')
            if version:headers['MCP-Protocol-Version']=version
            call({'jsonrpc':'2.0','method':'notifications/initialized'})
            tools=call({'jsonrpc':'2.0','id':2,'method':'tools/list','params':{}}).get('tools',[])
            names=[t.get('name') for t in tools if isinstance(t,dict) and isinstance(t.get('name'),str)]
            if not names:raise ValueError('21st não retornou ferramentas disponíveis para esta chave.')
            usage=None
            if 'get_usage' in names:
                result=call({'jsonrpc':'2.0','id':3,'method':'tools/call','params':{'name':'get_usage','arguments':{}}})
                if result.get('isError'):raise ValueError('21st recusou a consulta de consumo; geração hospedada continua bloqueada.')
                data=result.get('structuredContent')
                if not isinstance(data,dict):
                    data={}
                    for part in result.get('content',[]):
                        if part.get('type')=='text':
                            try:value=json.loads(part.get('text',''))
                            except (TypeError,ValueError):continue
                            if isinstance(value,dict):data=value;break
                # Somente flags conhecidas; respostas externas não entram como credenciais/contexto.
                if type(data.get('aiGenerationEnabled')) is bool:usage={'aiGenerationEnabled':data['aiGenerationEnabled']}
            detail=' Geração hospedada habilitada na conta, mas não solicitada.' if usage and usage['aiGenerationEnabled'] else ' Acesso à geração hospedada não validado ou desabilitado.'
            return dict(mensagem='MCP autenticado. Ferramentas disponíveis: '+', '.join(names[:30])+'. Runtime habilita somente consulta de componentes; geração hospedada não é chamada automaticamente.'+detail+' Obtenção de componente e licença precisam de validação própria.',consumo=usage)
