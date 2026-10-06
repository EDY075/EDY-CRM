"""Aplicação gerada EDY: administração local, catálogo, contato e uploads."""
import argparse
import json
import os
import secrets
import sqlite3
from pathlib import Path
from functools import wraps
from contextlib import contextmanager
from time import monotonic
from flask import Flask,request,session,abort,redirect,render_template_string,send_from_directory
from werkzeug.security import generate_password_hash,check_password_hash
from PIL import Image
import io

ROOT=Path(__file__).resolve().parent
LOGIN='''<h1>{{title}}</h1><form method="post"><input type="hidden" name="csrf" value="{{csrf}}"><label>Usuário<input name="usuario" required maxlength="80" autocomplete="username"></label><label>Senha (mínimo 12 caracteres)<input name="senha" type="password" required minlength="12" maxlength="200" autocomplete="{{autocomplete}}"></label><button>Continuar</button></form>'''
SHELL='''<!doctype html><html lang="pt-BR"><meta charset="utf-8"><meta name="viewport" content="width=device-width,initial-scale=1"><title>{{title}} · EDY</title><style>body{margin:0;background:#f5f1e8;color:#183431;font:16px/1.6 Arial}main{max-width:1000px;margin:auto;padding:32px}nav{display:flex;gap:18px;flex-wrap:wrap;border-bottom:1px solid #ccc;padding-bottom:18px}a{color:inherit}label{display:grid;gap:6px;margin:16px 0}input,textarea,select,button{font:inherit;padding:12px;border:1px solid #789;background:#fff;color:#183431;border-radius:4px;max-width:100%;box-sizing:border-box}button{cursor:pointer;background:#123e3b;color:white}table{border-collapse:collapse;width:100%}td,th{text-align:left;padding:12px;border-bottom:1px solid #ccc;overflow-wrap:anywhere}.table-wrap{overflow:auto}img{max-width:200px} :focus-visible{outline:3px solid #b27820;outline-offset:3px}.note{font-size:13px;color:#546c67}</style><main><nav><a href="/">Site</a><a href="/admin">Administração</a><a href="/catalogo">Catálogo</a><a href="/contato">Contato</a></nav><p class="note">Demonstração funcional local · dados de teste separados do CRM · publicação pendente</p>{% if error %}<p role="alert">{{error}}</p>{% endif %}BODY</main></html>'''
CATALOG='''<h1>Catálogo</h1>{% for item in items %}<article><h2>{{item['nome']}}</h2><p>{{item['descricao']}}</p><small>Item demonstrativo ou cadastrado pela administração; não comprova oferta da empresa.</small></article>{% else %}<p>Nenhum item publicado.</p>{% endfor %}'''
CONTACT='''<h1>Contato</h1><p>Formulário de teste: salva neste banco local; nenhum e-mail ou mensagem externa é enviado.</p><form method="post"><input name="csrf" type="hidden" value="{{csrf}}"><label>Nome<input name="nome" required maxlength="120"></label><label>E-mail<input type="email" name="email" required maxlength="200"></label><label>Mensagem<textarea name="mensagem" required maxlength="4000"></textarea></label><button>Salvar mensagem local</button></form>'''
ADMIN='''<h1>Administração</h1><p>Usuário: {{user['usuario']}} · {{user['papel']}}</p><form method="post" action="/sair"><input type="hidden" name="csrf" value="{{csrf}}"><button>Sair</button></form>
{% if 'catalogo' in modules %}<h2>Catálogo · CRUD</h2><form method="post" action="/admin/catalogo"><input type="hidden" name="csrf" value="{{csrf}}"><label>Nome do item<input name="nome" required maxlength="120"></label><label>Descrição<textarea name="descricao" required maxlength="2000"></textarea></label><button>Criar item</button></form><div class="table-wrap"><table><thead><tr><th>Item</th><th>Alterar</th><th>Arquivar</th></tr></thead><tbody>{% for item in items %}<tr><td>{{item['nome']}}</td><td><form method="post" action="/admin/catalogo/{{item['id']}}"><input type="hidden" name="csrf" value="{{csrf}}"><label>Nome<input name="nome" value="{{item['nome']}}" required maxlength="120"></label><label>Descrição<textarea name="descricao" required maxlength="2000">{{item['descricao']}}</textarea></label><button>Salvar item {{item['id']}}</button></form></td><td><form method="post" action="/admin/catalogo/{{item['id']}}/arquivar"><input type="hidden" name="csrf" value="{{csrf}}"><button>Arquivar item {{item['id']}}</button></form></td></tr>{% endfor %}</tbody></table></div>{% endif %}
{% if 'contatos' in modules %}<h2>Mensagens locais</h2>{% for m in messages %}<article><h3>{{m['nome']}}</h3><p>{{m['email']}}</p><p>{{m['mensagem']}}</p></article>{% else %}<p>Nenhuma mensagem recebida.</p>{% endfor %}{% endif %}
{% if 'uploads' in modules %}<h2>Materiais enviados</h2><form method="post" enctype="multipart/form-data" action="/admin/uploads"><input type="hidden" name="csrf" value="{{csrf}}"><label>Imagem própria autorizada<input type="file" name="arquivo" accept="image/png,image/jpeg,image/webp" required></label><button>Enviar imagem</button></form>{% for m in media %}<figure><img src="/uploads/{{m['arquivo']}}" alt="Material enviado pela administração"><figcaption>{{m['nome']}}</figcaption></figure>{% endfor %}{% endif %}
{% if user['papel']=='admin' %}<h2>Criar editor</h2><form method="post" action="/admin/usuarios"><input type="hidden" name="csrf" value="{{csrf}}"><label>Usuário<input name="usuario" required maxlength="80"></label><label>Senha<input type="password" name="senha" minlength="12" maxlength="200" required autocomplete="new-password"></label><button>Criar editor</button></form>{% endif %}'''


def create_app(data_dir=None):
    app=Flask(__name__);data=Path(data_dir or ROOT/'data');data.mkdir(parents=True,exist_ok=True);(data/'uploads').mkdir(exist_ok=True)
    config=json.loads((ROOT/'projeto.json').read_text(encoding='utf-8')) if (ROOT/'projeto.json').exists() else {'modulos':['catalogo','contatos','uploads']}
    modules=config['modulos'];key=data/'session.key'
    if not key.exists():key.write_text(secrets.token_hex(32));os.chmod(key,0o600)
    app.config.update(SECRET_KEY=key.read_text(),SESSION_COOKIE_NAME='edy_project_'+str(config.get('id','demo'))[:12],SESSION_COOKIE_HTTPONLY=True,SESSION_COOKIE_SAMESITE='Strict',MAX_CONTENT_LENGTH=8_000_000)
    attempts={}
    @contextmanager
    def db():
        con=sqlite3.connect(data/'site.db');con.row_factory=sqlite3.Row
        try:
            with con:yield con
        finally:con.close()
    with db() as con:con.executescript('CREATE TABLE IF NOT EXISTS users(id INTEGER PRIMARY KEY,usuario TEXT UNIQUE,senha TEXT,papel TEXT);CREATE TABLE IF NOT EXISTS catalogo(id INTEGER PRIMARY KEY,nome TEXT,descricao TEXT,ativo INTEGER DEFAULT 1);CREATE TABLE IF NOT EXISTS mensagens(id INTEGER PRIMARY KEY,nome TEXT,email TEXT,mensagem TEXT);CREATE TABLE IF NOT EXISTS materiais(id INTEGER PRIMARY KEY,arquivo TEXT,nome TEXT);PRAGMA user_version=1;')
    def csrf():
        if 'csrf' not in session:session['csrf']=secrets.token_hex(24)
        return session['csrf']
    def page(body,title,**args):return render_template_string(SHELL.replace('BODY',body),title=title,csrf=csrf(),modules=modules,config_mode=config.get('modo','aplicacao'),**args)
    def current():
        with db() as con:return con.execute('SELECT id,usuario,papel FROM users WHERE id=?',(session.get('uid'),)).fetchone()
    def auth(fn):
        @wraps(fn)
        def wrapped(*a,**kw):
            if not current():return redirect('/login')
            return fn(*a,**kw)
        return wrapped
    def field(name,maximum):
        value=request.form.get(name,'').strip()
        if not value or len(value)>maximum:abort(400,description='Campo inválido: '+name)
        return value
    @app.before_request
    def protect():
        if request.host.split(':')[0] not in ('127.0.0.1','localhost'):abort(403)
        if request.method=='POST':
            if request.headers.get('Origin') not in (None,request.host_url.rstrip('/')) or request.headers.get('Sec-Fetch-Site')=='cross-site':abort(403)
            expected=session.get('csrf')
            if not expected or not secrets.compare_digest(request.form.get('csrf',''),expected):abort(403)
    @app.after_request
    def headers(r):
        r.headers['Content-Security-Policy']="default-src 'self'; style-src 'self' 'unsafe-inline'; img-src 'self' data:; script-src 'self' 'unsafe-inline'; frame-ancestors 'none'; object-src 'none'; base-uri 'self'; form-action 'self'"
        # no-referrer torna Origin=null em submissões HTML no Chrome. Mantém origem
        # em formulários locais, sem enviar Referer a sites externos.
        r.headers['X-Content-Type-Options']='nosniff';r.headers['Referrer-Policy']='same-origin'
        if request.path.startswith(('/admin','/login','/setup')):r.headers['Cache-Control']='no-store'
        return r
    @app.get('/')
    def index():return send_from_directory(ROOT,'index.html')
    @app.get('/<name>.html')
    def html(name):
        if name not in ('sobre','servicos'):abort(404)
        return send_from_directory(ROOT,name+'.html')
    @app.get('/previa-local.css')
    def style():return send_from_directory(ROOT,'previa-local.css')
    @app.get('/style.css')
    @app.get('/app.js')
    def generated_asset():return send_from_directory(ROOT,request.path.lstrip('/'))
    @app.get('/materiais/<name>')
    def materials(name):return send_from_directory(ROOT/'materiais',name)
    @app.route('/setup',methods=['GET','POST'])
    def setup():
        with db() as con:
            if con.execute('SELECT 1 FROM users LIMIT 1').fetchone():abort(404)
            if request.method=='POST':
                user=field('usuario',80);password=field('senha',200)
                if len(password)<12:abort(400)
                con.execute('INSERT INTO users(usuario,senha,papel) VALUES (?,?,?)',(user,generate_password_hash(password),'admin'))
                return redirect('/login')
        return page(LOGIN,'Criar administrador local',autocomplete='new-password')
    @app.route('/login',methods=['GET','POST'])
    def login():
        if request.method=='POST':
            ip=request.remote_addr;recent=[t for t in attempts.get(ip,[]) if monotonic()-t<300]
            if len(recent)>=8:abort(429)
            attempts[ip]=recent+[monotonic()]
            with db() as con:user=con.execute('SELECT * FROM users WHERE usuario=?',(field('usuario',80),)).fetchone()
            if not user or not check_password_hash(user['senha'],field('senha',200)):return page(LOGIN,'Entrar',autocomplete='current-password',error='Usuário ou senha inválidos.'),401
            session.clear();session['uid']=user['id'];attempts[ip]=[];return redirect('/admin')
        return page(LOGIN,'Entrar',autocomplete='current-password')
    @app.post('/sair')
    def logout():session.clear();return redirect('/login')
    @app.get('/admin')
    @auth
    def admin():
        with db() as con:return page(ADMIN,'Administração',user=current(),items=con.execute('SELECT * FROM catalogo WHERE ativo=1').fetchall(),messages=con.execute('SELECT * FROM mensagens ORDER BY id DESC').fetchall(),media=con.execute('SELECT * FROM materiais').fetchall())
    @app.route('/admin/catalogo',methods=['POST'])
    @app.route('/admin/catalogo/<int:ident>',methods=['POST'])
    @auth
    def catalog_write(ident=None):
        if 'catalogo' not in modules:abort(404)
        name,desc=field('nome',120),field('descricao',2000)
        with db() as con:
            if ident:
                if not con.execute('SELECT id FROM catalogo WHERE id=? AND ativo=1',(ident,)).fetchone():abort(404)
                con.execute('UPDATE catalogo SET nome=?,descricao=? WHERE id=?',(name,desc,ident))
            else:con.execute('INSERT INTO catalogo(nome,descricao) VALUES (?,?)',(name,desc))
        return redirect('/admin')
    @app.post('/admin/catalogo/<int:ident>/arquivar')
    @auth
    def archive(ident):
        if 'catalogo' not in modules:abort(404)
        with db() as con:con.execute('UPDATE catalogo SET ativo=0 WHERE id=?',(ident,))
        return redirect('/admin')
    @app.get('/catalogo')
    def catalog():
        if 'catalogo' not in modules:abort(404)
        with db() as con:return page(CATALOG,'Catálogo',items=con.execute('SELECT * FROM catalogo WHERE ativo=1').fetchall())
    @app.route('/contato',methods=['GET','POST'])
    def contact():
        if 'contatos' not in modules:abort(404)
        if request.method=='POST':
            with db() as con:con.execute('INSERT INTO mensagens(nome,email,mensagem) VALUES (?,?,?)',(field('nome',120),field('email',200),field('mensagem',4000)))
            return page('<h1>Mensagem salva no banco local</h1><p>Nenhuma mensagem enviada externamente.</p>','Contato')
        return page(CONTACT,'Contato')
    @app.post('/admin/uploads')
    @auth
    def upload():
        if 'uploads' not in modules:abort(404)
        file=request.files.get('arquivo')
        if not file:abort(400)
        try:
            raw=file.read(8_000_001)
            if len(raw)>8_000_000:abort(413)
            with Image.open(io.BytesIO(raw)) as image:
                if image.width*image.height>20_000_000:abort(400)
                image=image.convert('RGB');name=secrets.token_hex(16)+'.jpg';image.save(data/'uploads'/name,'JPEG',quality=90)
        except (OSError,ValueError):abort(400,description='Imagem inválida.')
        with db() as con:con.execute('INSERT INTO materiais(arquivo,nome) VALUES (?,?)',(name,Path(file.filename).name[:200]))
        return redirect('/admin')
    @app.get('/uploads/<name>')
    def uploaded(name):
        with db() as con:
            if not con.execute('SELECT 1 FROM materiais WHERE arquivo=?',(name,)).fetchone():abort(404)
        return send_from_directory(data/'uploads',name)
    @app.post('/admin/usuarios')
    @auth
    def user_create():
        if current()['papel']!='admin':abort(403)
        password=field('senha',200)
        if len(password)<12:abort(400)
        try:
            with db() as con:con.execute('INSERT INTO users(usuario,senha,papel) VALUES (?,?,?)',(field('usuario',80),generate_password_hash(password),'editor'))
        except sqlite3.IntegrityError:abort(409)
        return redirect('/admin')
    return app


if __name__=='__main__':
    parser=argparse.ArgumentParser();parser.add_argument('--port',type=int,default=5163);args=parser.parse_args()
    from waitress import serve
    serve(create_app(),host='127.0.0.1',port=args.port,threads=4)
