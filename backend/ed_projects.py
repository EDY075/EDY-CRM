"""Construção local executável isolada: catálogo/contato/admin, sem simular IA."""
import hashlib
import json
import os
from pathlib import Path
import socket
import subprocess
import sys
import time
import zipfile
from flask import current_app,jsonify,request,send_file
import ed_store as store
from ed_tasks import iniciar
from ed_services import ler_job,lock
def attach_backend(root,job,modules=None):
    """Backend revisado e determinístico; frontend continua gerado pelo motor escolhido."""
    modules=modules or ['catalogo','contatos','uploads']
    (root/'app.py').write_bytes((Path(__file__).parent/'project_template/app.py').read_bytes())
    (root/'projeto.json').write_text(json.dumps(dict(id=job['id'],modo='aplicacao',modulos=modules,empresa_id=job['empresa_id'],demonstracao=True),indent=2),encoding='utf-8')
    (root/'requirements.txt').write_text('Flask>=3.1,<4\nwaitress>=3,<4\nPillow>=12,<13\n',encoding='utf-8')
    (root/'INICIAR.md').write_text('# Site completo local\n\nFrontend gerado por IA, backend Flask/SQLite revisado.\nAbra /setup para criar o administrador com senha própria (mínimo 12 caracteres). Depois /login e /admin.\nMódulos padrão: catálogo CRUD, contatos locais, uploads autorizados, admin/editor com CSRF.\nBanco em data/site.db separado do CRM; nenhum envio comercial, pagamento ou publicação.\nUse `python app.py --port 5163` com requirements instalados. Dados do piloto são demonstração.\nAntes de produção: HTTPS, backups, domínio, política de dados e acesso ao servidor.\n',encoding='utf-8')
    # Refinar o frontend não deve reiniciar o banco da aplicação já construída.
    previous=job['parametros'].get('anterior')
    if previous:
        from ed_runtime import artefact_root
        old=ler_job(previous)
        if old['empresa_id']!=job['empresa_id'] or old['estado']!='concluida':raise ValueError('Banco anterior não pertence a uma versão concluída desta empresa.')
        source=artefact_root(job['empresa_id'],previous)/'data'
        target=root/'data'
        if (source/'site.db').is_file() and not (target/'site.db').exists():
            import sqlite3,shutil
            target.mkdir(exist_ok=True)
            with sqlite3.connect(source/'site.db') as src,sqlite3.connect(target/'site.db') as dst:src.backup(dst)
            if (source/'uploads').exists():shutil.copytree(source/'uploads',target/'uploads',dirs_exist_ok=True)


def build(job,progress):
    from ed_visual_studio import any_activated
    if any_activated(job['empresa_id']):raise ValueError('Esta empresa usa composição visual escolhida. Construa pelo Codex no Estúdio Visual; o template local não reconstrói a proposta aprovada.')
    from ed_runtime import artefact_root
    lead=store.ler_empresa(job['empresa_id']);args=job['parametros']
    export=next((x for x in lead['exportacoes'] if x['id']==args['exportacao_id']),None)
    if not export:raise ValueError('Escolha um pacote desta empresa.')
    root=artefact_root(lead['id'],job['id']);root.mkdir(parents=True,exist_ok=True)
    progress(15,'Extraindo snapshot do pacote; banco do CRM não será copiado.')
    archive=store.arquivo_seguro('exportacoes',lead['id']+'/'+export['id']+'/pacote.zip')
    with zipfile.ZipFile(archive) as z:
        for name in z.namelist():
            dest=(root/name).resolve()
            if not dest.is_relative_to(root.resolve()) or '\\' in name or ':' in name:raise ValueError('Caminho inválido no pacote.')
            dest.parent.mkdir(parents=True,exist_ok=True);dest.write_bytes(z.read(name))
    html=(root/'previa-local.html').read_text(encoding='utf-8')
    mode=args['modo'];modules=args['modulos'] if mode=='aplicacao' else ['contatos'] if mode=='site' else []
    nav='<nav class="project-nav" aria-label="Páginas"><a href="/">Início</a>'+(' <a href="sobre.html">Sobre</a> <a href="servicos.html">Serviços</a>' if mode!='previa' else '')+(' <a href="contato">Formulário local</a>' if 'contatos' in modules else '')+(' <a href="catalogo">Catálogo</a>' if 'catalogo' in modules else '')+(' <a href="admin">Administração local</a>' if mode=='aplicacao' else '')+'</nav>'
    html=html.replace('<main id="pagina"',nav+'<main id="pagina"')
    (root/'index.html').write_text(html,encoding='utf-8')
    if mode!='previa':
        # Páginas derivadas das seções revisadas do próprio pacote, nunca texto de referência.
        import re
        blocks=re.findall(r'(<section\b.*?</section>)',html,re.S)
        for page,kinds in [('sobre',('apresentacao','equipe','processo')),('servicos',('servicos','produtos'))]:
            parts=[b for b in blocks if any('lp-'+k+' ' in b for k in kinds)]
            if not parts:parts=['<section class="lp-section"><h1>'+page.title()+'</h1><p>Conteúdo confirmado para esta página pendente.</p></section>']
            page_html=re.sub(r'(<main id="pagina"[^>]*>).*?(</main>)',lambda m:m[1]+''.join(parts)+m[2],html,flags=re.S)
            page_html=page_html.replace('<title>', '<title>'+page.title()+' · ')
            page_html=page_html.replace('href="#contato"','href="'+('contato' if 'contatos' in modules else '/#contato')+'"')
            page_html=page_html.replace('<h2>','<h1>',1).replace('</h2>','</h1>',1) if '<h1>' not in page_html else page_html
            (root/(page+'.html')).write_text(page_html,encoding='utf-8')
        (root/'app.py').write_bytes((Path(__file__).parent/'project_template/app.py').read_bytes())
        (root/'requirements.txt').write_text('Flask>=3.1,<4\nwaitress>=3,<4\nPillow>=12,<13\n',encoding='utf-8')
        (root/'projeto.json').write_text(json.dumps(dict(id=job['id'],modo=mode,modulos=modules,empresa_id=lead['id'],exportacao_id=export['id'],demonstracao=True),ensure_ascii=False,indent=2),encoding='utf-8')
        (root/'.env.example').write_text('# Local: chave de sessão criada em data/session.key; nenhum segredo do CRM.\n# Não publicar sem configurar HTTPS, backups e proteção do administrador.\n',encoding='utf-8')
    with (root/'previa-local.css').open('a',encoding='utf-8') as css:
        css.write('\n.project-nav{display:flex;gap:24px;flex-wrap:wrap;padding:18px 5vw;border-bottom:1px solid currentColor}.project-nav a{color:inherit;font-size:14px}.project-nav a:focus-visible{outline:3px solid currentColor;outline-offset:4px}\n')
    progress(70,'Gerando instruções e verificando hashes e caminhos relativos.')
    (root/'INICIAR.md').write_text('# Projeto EDY executável\n\nModo: '+mode+' · templates locais, sem inferência IA. GPT-6.1 Sol · Alto · Padrão recomendados para refinamento.\n\n'+('Abra index.html ou sirva com python -m http.server 5163 --bind 127.0.0.1.\n' if mode=='previa' else 'Windows: python -m venv .venv\n.venv/Scripts/python.exe -m pip install -r requirements.txt\n.venv/Scripts/python.exe app.py --port 5163\nAbra http://127.0.0.1:5163/setup para criar o administrador (senha mínima 12 caracteres). O setup fecha após criação. Login: /login.\n')+'\nBanco criado somente em data/site.db; não acompanha a exportação. Mensagens ficam locais, sem envio. Catálogo/usuários são dados de demonstração enquanto não revisados. Modulos: '+', '.join(modules)+'\n\nNão implementa pagamentos, estoque, agenda ou integrações externas. Confira pendências comerciais em empresa.md. Prepare hospedagem, domínio, HTTPS, política de dados e backup antes de produção.\n',encoding='utf-8')
    names=[p for p in root.rglob('*') if p.is_file() and p.suffix!='.zip' and '.cache' not in p.relative_to(root).parts and 'data' not in p.relative_to(root).parts]
    manifest=[dict(arquivo=p.relative_to(root).as_posix(),sha256=hashlib.sha256(p.read_bytes()).hexdigest()) for p in names]
    (root/'integridade-projeto.json').write_text(json.dumps(manifest,indent=2),encoding='utf-8')
    with zipfile.ZipFile(root/'projeto.zip','w',zipfile.ZIP_DEFLATED) as z:
        for p in names+[root/'integridade-projeto.json']:z.write(p,p.relative_to(root).as_posix())
    return dict(exportacao_id=export['id'],modo=mode,modulos=modules,workspace_relativo=lead['id']+'/'+job['id'],origem='template_funcional_local',arquivos=[x['arquivo'] for x in manifest],snapshot=json.loads((root/'contexto-usado.json').read_text(encoding='utf-8'))['snapshot'],publicado=False,mensagem='Projeto executável criado; dados administrativos locais são demonstração.')


def registrar(bp):
    @bp.post('/empresas/<company>/projetos')
    def start(company):
        data=request.get_json();lead=store.ler_empresa(company)
        if not isinstance(data,dict) or set(data)!={'modo','modulos','exportacao_id'} or data['modo'] not in ('previa','site','aplicacao'):raise ValueError('Escolha prévia, site ou aplicação e módulos.')
        if not isinstance(data['modulos'],list) or set(data['modulos'])-{'catalogo','contatos','uploads'}:raise ValueError('Módulos disponíveis: catálogo, contatos, uploads.')
        if data['modo']=='aplicacao' and not data['modulos']:raise ValueError('Selecione ao menos um módulo funcional.')
        if not any(x['id']==data['exportacao_id'] for x in lead['exportacoes']):raise ValueError('Escolha uma exportação desta empresa.')
        return jsonify(iniciar('local','projeto_funcional',company,data,build)),202
    def owned(company,jid):
        job=ler_job(jid)
        if job.get('empresa_id')!=company or job['tipo']!='projeto_funcional' or job['estado']!='concluida':raise ValueError('Projeto concluído desta empresa necessário.')
        from ed_runtime import artefact_root
        return job,artefact_root(company,jid)
    @bp.get('/empresas/<company>/projetos/<jid>/zip')
    def download(company,jid):
        _,root=owned(company,jid);return send_file(root/'projeto.zip',as_attachment=True,download_name='projeto-edy.zip')
    @bp.get('/empresas/<company>/projetos')
    def history(company):
        store.ler_empresa(company)
        with store.conectar() as con:rows=con.execute('SELECT dados FROM ed_operacoes ORDER BY rowid DESC').fetchall()
        return jsonify([j for r in rows if (j:=json.loads(r['dados'])).get('empresa_id')==company and j['tipo']=='projeto_funcional'])
    @bp.post('/empresas/<company>/projetos/<jid>/abrir')
    def open_project(company,jid):
        job,root=owned(company,jid)
        from ed_runtime import processes
        with lock:
            old=processes.get(jid)
            if old and old[0].poll() is None:return jsonify(url=old[1])
            for port in range(5163,5190):
                with socket.socket() as sock:
                    if hasattr(socket,'SO_EXCLUSIVEADDRUSE'):sock.setsockopt(socket.SOL_SOCKET,socket.SO_EXCLUSIVEADDRUSE,1)
                    try:sock.bind(('127.0.0.1',port));break
                    except OSError:continue
            else:raise ValueError('Sem porta livre para projeto local.')
            env={k:v for k,v in os.environ.items() if k.upper() in ('SYSTEMROOT','WINDIR','PATH')};cache=root/'.cache';cache.mkdir(exist_ok=True);env.update(TEMP=str(cache),TMP=str(cache),PYTHONDONTWRITEBYTECODE='1')
            argv=[sys.executable,str(root/'app.py'),'--port',str(port)] if job['parametros']['modo']!='previa' else [sys.executable,str(Path(__file__).resolve().parents[1]/'scripts/preview_static.py'),'--directory',str(root),'--port',str(port),'--crm-origin',current_app.config.get('PREVIEW_FRAME_ORIGIN','http://127.0.0.1:5128')]
            proc=subprocess.Popen(argv,cwd=root,env=env,stdin=subprocess.DEVNULL,stdout=subprocess.DEVNULL,stderr=subprocess.DEVNULL,creationflags=getattr(subprocess,'CREATE_NO_WINDOW',0))
            ready=False
            for _ in range(30):
                try:
                    import requests
                    response=requests.get(f'http://127.0.0.1:{port}/',timeout=.3,allow_redirects=False)
                    if response.status_code==200 and response.content==(root/'index.html').read_bytes():ready=True;break
                except requests.RequestException:pass
                if proc.poll() is not None:break
                time.sleep(.1)
            if not ready:
                proc.terminate();raise ValueError('Projeto não iniciou; consulte dependências e tente abrir novamente.')
            url=f'http://127.0.0.1:{port}/';processes[jid]=(proc,url)
            with store.conectar() as con:
                exists=any(json.loads(r['dados']).get('construcao_id')==jid and json.loads(r['dados']).get('url')==url for r in con.execute('SELECT dados FROM ed_previas WHERE empresa_id=?',(company,)))
                if not exists:con.execute('INSERT INTO ed_previas VALUES (?,?,?)',(store.novo_id(),company,json.dumps(dict(url=url,exportacao_id=job['parametros']['exportacao_id'],observacoes='Projeto funcional local · dados de demonstração · sem publicação',criado_em=store.agora(),construcao_id=jid))))
            return jsonify(url=url,mensagem='Servidor separado, banco próprio e nenhum segredo do CRM no ambiente.')
