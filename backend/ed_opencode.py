"""OpenCode oficial supervisionado; sessões isoladas, sem shell/edição pelo modelo."""
import atexit,json,os,secrets,socket,subprocess,time,hashlib
from pathlib import Path
from threading import RLock
from flask import jsonify,current_app
import requests
import ed_store as store
import ed_secrets
from ed_tasks import ativo
from ed_codex_transport import RuntimeFailure,sanitize
from ed_creation_providers import executable,config,record,context,finish

servers={};lock=RLock()
def stop():
    for p,url in list(servers.values()):
        if p.poll() is None:
            p.terminate()
            try:p.wait(timeout=3)
            except subprocess.TimeoutExpired:p.kill()
    servers.clear()
atexit.register(stop)
def server():
    folder=store.pasta()/'runtime-opencode';folder.mkdir(exist_ok=True);ident=str(folder.resolve())
    with lock:
        prior=servers.get(ident)
        if prior and prior[0].poll() is None:return prior[1]
        binary=executable()
        if not binary.is_file():raise ValueError('Runtime OpenCode local não instalado. Conexões mostra a dependência; Codex e exportação continuam disponíveis.')
        manifest=Path(__file__).resolve().parent.parent/'config/opencode-runtime.json'
        expected=json.loads(manifest.read_text(encoding='utf-8')) if manifest.is_file() else None
        with binary.open('rb') as f:sha=hashlib.file_digest(f,'sha256').hexdigest()
        if not expected or expected['sha256']!=sha:raise ValueError('Runtime OpenCode sem hash fixado ou alterado. Reinstale a versão local verificada.')
        for port in range(4101,4120):
            with socket.socket() as sock:
                try:sock.bind(('127.0.0.1',port));break
                except OSError:continue
        else:raise ValueError('Sem porta livre para OpenCode local.')
        password=ed_secrets.get('opencode_server')
        if not password:password=secrets.token_urlsafe(32);ed_secrets.put('opencode_server',password)
        env={k:v for k,v in os.environ.items() if k.upper() in ('PATH','SYSTEMROOT','WINDIR','COMSPEC','PATHEXT')}
        cache=folder/'cache';cache.mkdir(exist_ok=True)
        env.update(OPENCODE_SERVER_PASSWORD=password,OPENCODE_SERVER_USERNAME='opencode',XDG_DATA_HOME=str(folder/'data'),XDG_CONFIG_HOME=str(folder/'config'),XDG_CACHE_HOME=str(cache),XDG_STATE_HOME=str(folder/'state'),TEMP=str(cache),TMP=str(cache),OPENCODE_CONFIG_CONTENT=json.dumps({'permission':{'*':'deny'},'share':'disabled','autoupdate':False,'enabled_providers':['opencode'],'mcp':{},'tools':{'*':False},'instructions':[],'plugins':[]}))
        log=folder/'server.log'
        with log.open('ab') as stream:p=subprocess.Popen([str(binary),'serve','--hostname','127.0.0.1','--port',str(port)],cwd=folder,env=env,stdin=subprocess.DEVNULL,stdout=stream,stderr=stream,creationflags=getattr(subprocess,'CREATE_NO_WINDOW',0))
        url='http://127.0.0.1:'+str(port)
        for _ in range(100):
            if p.poll() is not None:raise ValueError('OpenCode não iniciou. Consulte runtime-opencode/server.log local; credenciais não são exibidas no CRM.')
            try:
                r=requests.get(url+'/global/health',auth=('opencode',password),timeout=.4)
                if r.status_code==200 and r.json().get('healthy'):servers[ident]=(p,url);return url
            except (requests.RequestException,ValueError):pass
            time.sleep(.1)
        p.terminate();raise ValueError('OpenCode não ficou pronto no prazo.')
def call(method,path,body=None,root=None,timeout=20):
    url=server();params={'directory':str(root.resolve())} if root else None
    try:
        with requests.request(method,url+path,json=body,params=params,auth=('opencode',ed_secrets.get('opencode_server')),timeout=(2,timeout),allow_redirects=False,stream=True) as response:
            if response.status_code==204:return {}
            raw=b''
            for part in response.iter_content(65536):
                raw+=part
                if len(raw)>6000000:raise ValueError('Resposta OpenCode acima do limite.')
            try:value=json.loads(raw)
            except ValueError:raise ValueError('OpenCode retornou conteúdo não estruturado.') from None
            if response.status_code>=400:raise RuntimeFailure({'http_status':response.status_code,'erro':value})
            return value
    except requests.RequestException:raise RuntimeFailure({'message':'OpenCode local não respondeu','code':'timeout'}) from None
def catalog():
    value=call('GET','/provider');provider=next((p for p in value.get('all',[]) if p['id']=='opencode'),None)
    models=[]
    for ident,model in (provider or {}).get('models',{}).items():
        cost=model.get('cost',{});zero=all(k in cost and cost[k]==0 for k in ('input','output'))
        if zero:models.append(dict(id=ident,nome=model.get('name',ident),gratuito=True,capacidade=model.get('capabilities',{}),limite=model.get('limit',{}),preco=cost))
    return models
def generate(job,progress,fallback=False):
    root,docs,prompt,images=context(job);cfg=config();ident=cfg['modelo_opencode']
    model=next((m for m in catalog() if m['id']==ident),None)
    if not model or not model['gratuito']:raise ValueError('OpenCode: modelo gratuito configurado não encontrado/preço zero não confirmado. Nenhum modelo pago automático.')
    cap=model['capacidade']
    if not cap.get('toolcall'):raise ValueError('OpenCode: modelo não tem capacidade de ferramentas comprovada.')
    if images and not cap.get('input',{}).get('image'):raise ValueError('OpenCode: modelo não aceita as referências visuais selecionadas; construção pausada.')
    if model['limite'].get('context',0)<len(prompt.encode('utf-8'))+16000+16384*len(images):raise ValueError('OpenCode: reserva conservadora de contexto não cabe na janela, sem corte silencioso.')
    session=call('POST','/session',{'title':'EDY '+job['id'],'permission':[{'permission':'*','pattern':'*','action':'deny'}]},root=root)['id']
    parts=[{'type':'text','text':prompt+'\nRetorne exclusivamente JSON {files:[{path,content}],pendencias:[]} sem markdown. Arquivos apenas index.html/style.css/app.js/README.md. O CRM valida e grava a resposta; nenhuma ferramenta ou shell está autorizada.'}]
    for path,label in images:
        import base64
        mime='image/jpeg' if path.suffix.lower() in ('.jpeg','.jpg') else 'image/'+path.suffix[1:]
        parts.extend([{'type':'text','text':label+' '+path.name},{'type':'file','mime':mime,'url':'data:'+mime+';base64,'+base64.b64encode(path.read_bytes()).decode(),'filename':path.name}])
    ativo(job['id']);progress(30,'OpenCode oficial · '+ident+' · enviando apenas contexto desta empresa.',sessao_opencode=session)
    call('POST','/session/'+session+'/prompt_async',{'model':{'providerID':'opencode','modelID':ident},'parts':parts,'tools':{'bash':False,'edit':False,'write':False,'read':False,'webfetch':False,'websearch':False,'task':False}},root=root)
    deadline=time.monotonic()+360
    try:
        while time.monotonic()<deadline:
            ativo(job['id']);messages=call('GET','/session/'+session+'/message',root=root)
            replies=[m for m in messages if m.get('info',{}).get('role')=='assistant']
            if replies:
                last=replies[-1];info=last['info']
                if info.get('error'):raise RuntimeFailure(info['error'])
                if info.get('time',{}).get('completed'):
                    if info.get('finish') not in ('stop','end_turn'):raise RuntimeFailure({'message':'OpenCode encerrou incompleto','code':info.get('finish')},'incomplete')
                    text=''.join(p.get('text','') for p in last.get('parts',[]) if p['type']=='text')
                    try:output=json.loads(text)
                    except ValueError:raise ValueError('OpenCode não retornou contrato JSON válido; nenhuma página foi considerada pronta.') from None
                    return finish(job,root,docs,output,'opencode',ident,{'custo':info.get('cost'),'tokens':info.get('tokens')},extra={'sessao_opencode':session,'runtime':'OpenCode 1.18.31'})
                size=sum(len(p.get('text','')) for p in last.get('parts',[]) if p['type']=='text');progress(55,'OpenCode trabalhando; '+str(size)+' caracteres. Aguardando conclusão real.')
            time.sleep(1)
        raise RuntimeFailure({'message':'Timeout OpenCode; conclusão incerta. Sessão preservada para revisão.','code':'timeout'})
    except BaseException:
        try:call('POST','/session/'+session+'/abort',root=root)
        except ValueError:pass
        raise
def registrar(bp):
    @bp.post('/provedores/opencode/testar',endpoint='opencode_test')
    def test():
        try:
            health=call('GET','/global/health');models=catalog();result={'estado':'configurado_nao_validado','mensagem':'Runtime autenticado e catálogo consultado. Inferência e geração ainda não validadas.','versao':health.get('version'),'modelos':models,'data':store.agora()}
        except ValueError as e:result={'estado':'erro','mensagem':sanitize(str(e)),'data':store.agora()}
        record('opencode',result);return jsonify(result)
