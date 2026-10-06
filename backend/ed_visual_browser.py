"""Chrome efêmero: nenhuma sessão/credencial; HTTP passa pelo coletor público.

O Chrome não recebe acesso direto à rede de páginas: todas as requisições
são interceptadas, GET somente, sem cookies, IP público fixado e robots.
Service workers, frames, WebSockets, downloads e permissões são bloqueados.
"""
import base64
import hashlib
import json
import os
import secrets
import shutil
import subprocess
import threading
import time
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
from urllib.parse import urlsplit
from ed_enrich import ler_url, mesma_empresa, publico_sintatico
from ed_tasks import ativo
import ed_store as store


def render(job,url,check,progress):
    node=shutil.which('node')
    if not node:raise ValueError('Node.js indisponível. Use HTML/upload ou Firecrawl configurado.')
    root=Path(__file__).resolve().parent.parent
    work=root/'.cache/visual-browser'/job['id'];work.mkdir(parents=True,exist_ok=True)
    token=secrets.token_hex(32)
    network_lock=threading.Lock();budget={'bytes':0,'requests':0};cache={};errors=[]

    class Handler(BaseHTTPRequestHandler):
        def log_message(self,*args):pass
        def do_POST(self):
            if self.path!='/fetch' or not secrets.compare_digest(self.headers.get('Authorization',''),'Bearer '+token):self.send_error(403);return
            try:
                size=int(self.headers.get('Content-Length','0'))
                if not 0<size<=5000:raise ValueError('Pedido inválido.')
                target=json.loads(self.rfile.read(size))['url']
                if not isinstance(target,str) or not publico_sintatico(target):raise ValueError('Destino público inválido.')
                # Documentos devem permanecer no domínio pesquisado; assets podem usar CDNs públicas.
                with network_lock:
                    budget['requests']+=1
                    if budget['requests']>100:raise ValueError('Limite de 100 recursos atingido.')
                    if target in cache:answer=cache[target]
                    else:
                        delay=check(target)
                        if delay and delay>2:raise ValueError('Crawl-delay acima do limite da pesquisa visual; use upload.')
                        if delay:time.sleep(delay)
                        final,raw,mime=ler_url(target,limite=4_000_000,antes_de_ler=check)
                        if 'html' in mime.lower() and not mesma_empresa(final,url):raise ValueError('Documento saiu do domínio da referência.')
                        budget['bytes']+=len(raw)
                        if budget['bytes']>20_000_000:raise ValueError('Limite total de 20 MB atingido.')
                        answer=dict(body=base64.b64encode(raw).decode(),mime=mime or 'application/octet-stream')
                        cache[target]=answer
                status=200
            except (ValueError,KeyError,TypeError) as exc:
                message=str(exc) if isinstance(exc,ValueError) else 'Recurso inválido.'
                # Não persistir querystrings ou conteúdo remoto como mensagem.
                errors.append(dict(host=urlsplit(str(locals().get('target',''))).hostname,motivo=message[:300]))
                answer=dict(erro=message[:300]);status=400
            raw=json.dumps(answer).encode()
            try:self.send_response(status);self.send_header('Content-Type','application/json');self.send_header('Content-Length',str(len(raw)));self.end_headers();self.wfile.write(raw)
            except OSError:pass

    server=ThreadingHTTPServer(('127.0.0.1',0),Handler);server.daemon_threads=True
    threading.Thread(target=server.serve_forever,daemon=True).start()
    env={k:v for k,v in os.environ.items() if k.upper() in ('SYSTEMROOT','WINDIR','PATH','PROGRAMFILES','PROGRAMFILES(X86)','LOCALAPPDATA')}
    env.update(TEMP=str(work),TMP=str(work),EDY_VISUAL_BRIDGE='http://127.0.0.1:'+str(server.server_port)+'/fetch',EDY_VISUAL_TOKEN=token)
    process=None
    try:
        progress(35,'Chrome local: carregando referência em sessão isolada, sem login.')
        process=subprocess.Popen([node,str(root/'scripts/visual-browser.mjs'),url,str(work)],cwd=root,env=env,
            stdout=subprocess.DEVNULL,stderr=subprocess.DEVNULL,creationflags=getattr(subprocess,'CREATE_NO_WINDOW',0))
        deadline=time.monotonic()+60
        while process.poll() is None:
            ativo(job['id'])
            if time.monotonic()>deadline:raise ValueError('Navegação excedeu 60 s. Resultados existentes preservados; tente HTML/upload.')
            time.sleep(.2)
        result_path=work/'resultado.json'
        if not result_path.is_file():raise ValueError('Chrome não iniciou. Confira a instalação do Chrome e npm ci em frontend; nenhuma coleta simulada.')
        result=json.loads(result_path.read_text(encoding='utf-8'))
        if process.returncode or result.get('erro'):raise ValueError('Chrome não obteve conteúdo renderizado suficiente. Revise a URL, robots ou envie referência por arquivo.')
        result['limites_rede']=dict(recursos=budget['requests'],bytes=budget['bytes'],bloqueios=errors[:20])
        progress(65,'Desktop e celular capturados; estilos computados, recortes e controles observados.')
        return result,work
    finally:
        if process and process.poll() is None:process.terminate();process.wait(timeout=8)
        server.shutdown();server.server_close()


def attach_screenshot(item,work,name):
    from PIL import Image
    path=work/name
    raw=path.read_bytes()
    if len(raw)>3_000_000:raise ValueError('Captura excede 3 MB.')
    with Image.open(path) as image:
        if image.width*image.height>16_000_000:raise ValueError('Captura excede dimensões permitidas.')
        image.verify()
    filename=item['id']+'.jpg';dest=store.pasta()/'biblioteca'/filename
    dest.parent.mkdir(exist_ok=True);dest.write_bytes(raw)
    item['original']=dict(arquivo=filename,nome=name,sha256=hashlib.sha256(raw).hexdigest(),url='/api/ed/biblioteca/'+item['id']+'/original')
    with store.conectar() as con:con.execute('UPDATE ed_biblioteca SET dados=? WHERE id=? AND versao=1',(json.dumps(item,ensure_ascii=False),item['id']))
