"""Acesso estável no CRM; HTML permanece num servidor de origem isolada."""
import json
from flask import jsonify, request
import ed_store as store


class ServingMismatch(ValueError):
    """Arquivos existem, mas o servidor ativo entregou outro conteúdo."""


def owned(company, jid):
    from ed_services import ler_job
    store.ler_empresa(company)
    job=ler_job(jid)
    if job.get('empresa_id')!=company or job['tipo'] not in ('codex_construcao','template_construcao','projeto_funcional'):
        raise LookupError('Construção não pertence a esta empresa/workspace.')
    return job


def code_files(root, job):
    names=job.get('resultado',{}).get('arquivos') or ['index.html']
    # Nunca carregar caminhos escolhidos por código externo fora do artefato.
    files=[]
    for name in names:
        target=(root/name).resolve()
        if not target.is_relative_to(root.resolve()) or not target.is_file():
            raise ValueError('Arquivo da prévia ausente: '+str(name)[:160]+'. Recupere os arquivos ou refine a última versão válida.')
        if target.suffix in ('.html','.css','.js'):
            files.append(dict(path=name,content=target.read_text(encoding='utf-8')))
    if not (root/'index.html').is_file():raise ValueError('index.html ausente. Arquivos originais e versões anteriores preservados.')
    return files


def serving_health(root, files, url):
    """Confere identidade pelo HTML e os recursos locais antes de oferecer a URL."""
    import requests
    from urllib.parse import urlsplit, unquote, quote
    import re
    refs={'index.html'}
    for f in files:
        refs.update(re.findall(r'(?:src|href)=[\x22\x27]([^\x22\x27]+)',f['content']) if f['path'].endswith('.html') else [])
        refs.update(re.findall(r'url\([\s\x22\x27]*([^\x22\x27\s)]+)',f['content']) if f['path'].endswith('.css') else [])
    for ref in refs:
        p=urlsplit(ref)
        if p.scheme or p.netloc or not p.path:continue  # CTA e fragmentos não são arquivos.
        target=(root/unquote(p.path).lstrip('/')).resolve()
        if not target.is_relative_to(root.resolve()) or not target.is_file():continue  # validate_references confere os recursos obrigatórios.
        response=requests.get(url+quote(unquote(p.path).lstrip('/')),timeout=(.4,1),allow_redirects=False)
        if response.status_code!=200 or response.content!=target.read_bytes():raise ServingMismatch('Servidor não entregou o arquivo correto: '+p.path[:160]+'. Abra para recuperar o processo; arquivos salvos preservados.')


def availability(company, jid):
    from ed_runtime import artefact_root, validate_references
    job=owned(company,jid);url=None;reason='Abra para iniciar ou recuperar o servidor local.'
    state='em_construcao'
    if job['estado']=='concluida':
        try:
            root=artefact_root(company,jid);files=code_files(root,job);validate_references(root,files)
            state='servidor_parado';url=active_url(company,jid)
            # Disponibilidade do processo é distinta da inspeção visual da página.
            if url:
                serving_health(root,files,url);state='disponivel';reason='HTML e recursos locais verificados. Aprovação visual e comercial pendentes.'
        except ServingMismatch as exc:state='servidor_parado';reason=str(exc);url=None
        except (ValueError, OSError) as exc:state='arquivos_ausentes';reason=str(exc);url=None
        except __import__('requests').RequestException:state='servidor_parado';reason='Servidor não respondeu. Abra para recuperar o processo.';url=None
    elif job['estado'] not in ('na_fila','pesquisando'):state='falhou';reason=job.get('mensagem','Construção não concluída.')
    return dict(empresa_id=company,construcao_id=jid,estado=state,motivo=reason,url_ativa=url,abrir_url=f'/previas/{company}/{jid}',criado_em=job.get('criado_em'),modelo=job.get('resultado',{}).get('modelo'),escopo=job.get('resultado',{}).get('escopo','previa'))


def projects():
    """Uma versão corrente por empresa; seleção restaurada do estúdio prevalece."""
    with store.conectar() as con:
        jobs=[json.loads(r['dados']) for r in con.execute('SELECT dados FROM ed_operacoes ORDER BY rowid DESC')]
        sessions=[json.loads(r['valor']) for r in con.execute("SELECT valor FROM ed_config WHERE chave LIKE 'refinamento-site:%' ORDER BY rowid DESC")]
    result=[]
    for lead in store.listar_empresas():
        builds=[j for j in jobs if j.get('empresa_id')==lead['id'] and j['tipo'] in ('codex_construcao','template_construcao','projeto_funcional') and j['estado']=='concluida']
        if not builds:continue
        s=next((s for s in sessions if s['empresa_id']==lead['id'] and s.get('atual')),None)
        j=next((j for j in builds if s and j['id']==s['atual']),builds[0])
        item=availability(lead['id'],j['id'])
        from ed_runtime import artefact_root
        capture=artefact_root(lead['id'],j['id'])/'.cache/miniatura.jpg'
        item.update(nome=lead['nome'],nicho=lead['nicho'],cidade=lead['cidade'],versoes=len(builds),miniatura_url=f'/api/ed/empresas/{lead["id"]}/construcoes/{j["id"]}/miniatura' if capture.is_file() else None,refinar_url=f'/empresas/{lead["id"]}/refinar/{s["id"]}' if s and j['id']==s['atual'] else None)
        result.append(item)
    return result


def refine_conversation(company,jid):
    import ed_assistant as assistant
    job=owned(company,jid)
    if job['estado']!='concluida' or job['tipo']!='codex_construcao':raise ValueError('Refinamento nativo requer uma construção concluída. Revise a composição para criar uma nova prévia.')
    with assistant.chat_lock,store.conectar() as con:
        for r in con.execute('SELECT dados FROM ed_chat ORDER BY rowid DESC'):
            chat=json.loads(r['dados']);ctx=chat['contexto']
            if ctx.get('empresa_id')==company and ctx.get('construcao_id')==jid:
                return dict(chat_id=chat['id'],url=f'/empresas/{company}/refinar/{ctx["refinamento_site"]}' if ctx.get('refinamento_site') else '/assistente?chat='+chat['id'])
        chat=dict(id=store.novo_id(),titulo='Refinar · '+store.ler_empresa(company)['nome'],criado_em=store.agora(),contexto=dict(empresa_id=company,construcao_id=jid,geracao='codex_nativo',modo='automatico',escopo=job.get('resultado',{}).get('escopo','previa')),mensagens=[])
        assistant.save(chat)
        return dict(chat_id=chat['id'],url='/assistente?chat='+chat['id'])
def active_url(company,job_id):
    if not company or not job_id:return None
    from ed_services import ler_job,lock
    from ed_runtime import processes
    try:job=ler_job(job_id)
    except LookupError:return None
    if job.get('empresa_id')!=company or job.get('estado')!='concluida' or job.get('tipo') not in ('codex_construcao','template_construcao','projeto_funcional'):return None
    with lock:
        current=processes.get(job_id)
        return current[1] if current and current[0].poll() is None else None


def lead_links(lead):
    for preview in lead['previas']:
        if preview.get('construcao_id'):preview['url_ativa']=active_url(lead['id'],preview['construcao_id'])
    return lead


def workflow_links(job):
    import copy
    job=copy.deepcopy(job)
    built=next((s.get('resultado') for s in job['etapas'] if s['nome'] in ('gerar','refinar')),None) or {}
    for step in job['etapas']:
        value=step.get('resultado')
        if step['nome']=='verificar' and isinstance(value,dict) and value.get('url'):
            value['url_ativa']=active_url(value.get('empresa_id'),built.get('construcao_id'))
            if value.get('empresa_id') and built.get('construcao_id'):
                value['abrir_url']=f'/previas/{value["empresa_id"]}/{built["construcao_id"]}'
        if step['nome']=='prospeccao' and isinstance(value,dict):
            import re
            current=active_url(job['plano'].get('empresa_id'),value.get('construcao_id'))
            old=value.get('url_previa');replacement=current or '[prévia local inativa; reabra pela ficha]'
            value['url_ativa']=current
            for key in ('inicial','whatsapp','email'):
                if isinstance(value.get(key),str):value[key]=value[key].replace(old,replacement) if old else re.sub(r'http://127\.0\.0\.1:\d+/?',replacement,value[key])
    # Diagnóstico legado é projetado sem apagar o erro original nem reenviar inferência.
    if job.get('estado')=='aguardando_dependencia':
        from ed_services import ler_job
        for step in job['etapas']:
            if not step.get('operacao_id'):continue
            try:operation=ler_job(step['operacao_id'])
            except LookupError:continue
            from ed_codex_transport import operation_issue
            if operation['estado'] in ('erro','interrompida') and operation_issue(operation)=='execucao':
                job['estado']='falhou';job['mensagem']='Execução interrompida; nenhuma credencial foi apontada como ausente. '+operation.get('mensagem','')+' Retome explicitamente pelos checkpoints.';step['estado']='erro'
                break
    return job

def thumbnail(company,jid,url):
    import subprocess,shutil,os
    from pathlib import Path
    from ed_runtime import artefact_root
    if active_url(company,jid)!=url:raise ValueError('Construção não está servida nesta sessão.')
    node=shutil.which('node')
    if not node:raise ValueError('Node necessário somente para a miniatura; prévia continua disponível.')
    project=Path(__file__).resolve().parent.parent;root=artefact_root(company,jid)
    out=root/'.cache/miniatura.jpg';out.parent.mkdir(exist_ok=True)
    # Playwright procura o Chrome instalado usando HOMEDRIVE/LOCALAPPDATA no Windows.
    # Credenciais do processo principal continuam fora do subprocesso de captura.
    env={k:v for k,v in os.environ.items() if k.upper() in ('PATH','SYSTEMROOT','WINDIR','HOMEDRIVE','LOCALAPPDATA')}
    env.update(TEMP=str(out.parent),TMP=str(out.parent))
    try:
        subprocess.run([node,str(project/'scripts/capturar-previa.mjs'),url,str(out)],cwd=project,env=env,capture_output=True,check=True,timeout=30,creationflags=getattr(subprocess,'CREATE_NO_WINDOW',0))
    except subprocess.CalledProcessError as exc:
        from ed_codex_transport import sanitize
        detail=sanitize((exc.stderr or b'').decode('utf-8',errors='replace'))[-800:]
        raise ValueError('Captura automática não concluiu (exit '+str(exc.returncode)+'). '+detail) from None
    except subprocess.TimeoutExpired:
        raise ValueError('Captura automática excedeu 30 segundos. A prévia permanece disponível para inspeção no navegador.') from None
    if not out.is_file():raise ValueError('Miniatura ausente; nenhum screenshot simulado.')
    return '/api/ed/empresas/'+company+'/construcoes/'+jid+'/miniatura'

def registrar(bp):
    from flask import send_file
    @bp.get('/previas',endpoint='previews_index')
    def index():return jsonify(projects())

    @bp.get('/empresas/<company>/construcoes/<jid>/disponibilidade',endpoint='preview_availability')
    def status(company,jid):return jsonify(availability(company,jid))

    @bp.post('/empresas/<company>/construcoes/<jid>/conversa',endpoint='preview_conversation')
    def conversation(company,jid):
        if request.get_json()!= {}:raise ValueError('Nenhum contexto externo é aceito ao abrir a conversa.')
        return jsonify(refine_conversation(company,jid))
    @bp.get('/empresas/<company>/construcoes/<jid>/miniatura',endpoint='build_thumbnail')
    def get_thumbnail(company,jid):
        from ed_runtime import artefact_root
        from ed_services import ler_job
        j=ler_job(jid)
        if j.get('empresa_id')!=company or j['estado']!='concluida':raise LookupError('Construção concluída necessária.')
        p=artefact_root(company,jid)/'.cache/miniatura.jpg'
        if not p.is_file():raise LookupError('Captura ainda não preparada.')
        return send_file(p,mimetype='image/jpeg')
