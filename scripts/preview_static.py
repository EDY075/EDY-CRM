"""Servidor estático de prévia. Sem APIs, execução de backend ou acesso fora da pasta."""
import argparse
from pathlib import Path
from http.server import ThreadingHTTPServer,SimpleHTTPRequestHandler
from urllib.parse import urlsplit,unquote

def crm_origin(value):
    url=urlsplit(value)
    if url.scheme!='http' or url.hostname not in ('127.0.0.1','localhost') or url.username or url.password or url.path or url.query or url.fragment or not url.port or not 1024<=url.port<=65535:
        raise argparse.ArgumentTypeError('Origem do CRM deve ser HTTP loopback com porta explícita.')
    return value

p=argparse.ArgumentParser();p.add_argument('--directory',required=True);p.add_argument('--port',type=int,required=True);p.add_argument('--crm-origin',type=crm_origin,default='http://127.0.0.1:5128');args=p.parse_args()
root=Path(args.directory).resolve()
class Handler(SimpleHTTPRequestHandler):
    def __init__(self,*a,**kw):super().__init__(*a,directory=str(root),**kw)
    def allowed(self):
        path=(root/unquote(urlsplit(self.path).path).lstrip('/')).resolve()
        if not path.is_relative_to(root) or any(x.startswith('.') for x in path.relative_to(root).parts):self.send_error(403);return False
        if path.is_dir() and not (path/'index.html').is_file():self.send_error(403);return False
        return True
    def do_GET(self):
        if self.allowed():super().do_GET()
    def do_HEAD(self):
        if self.allowed():super().do_HEAD()
    def end_headers(self):
        self.send_header('Content-Security-Policy',"default-src 'self'; img-src 'self' data:; script-src 'self' 'unsafe-inline'; style-src 'self' 'unsafe-inline'; connect-src 'none'; frame-src 'none'; frame-ancestors "+args.crm_origin+"; object-src 'none'; base-uri 'none'; form-action 'none'")
        self.send_header('X-Content-Type-Options','nosniff');self.send_header('Referrer-Policy','no-referrer');super().end_headers()
    def log_message(self,*a):pass
ThreadingHTTPServer(('127.0.0.1',args.port),Handler).serve_forever()
