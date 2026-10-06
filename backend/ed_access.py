"""Sessão local, papéis e workspaces; banco central não armazena credenciais de provedores."""
import json
import os
import secrets
import sqlite3
from pathlib import Path
from contextlib import contextmanager
from datetime import timedelta
from time import monotonic
from flask import g,session,request,jsonify,abort,current_app
from werkzeug.security import generate_password_hash,check_password_hash
import ed_store as store
from ed_workspace import data_directory

ROLES=('administrador','operador','leitura')

def body():
    value=request.get_json()
    if not isinstance(value,dict):raise ValueError('Envie um objeto JSON.')
    return value


def root():return Path(current_app.config['DATA_DIR'])


@contextmanager
def connection():
    con=sqlite3.connect(root()/'ed-access.db',timeout=15);con.row_factory=sqlite3.Row
    con.execute('PRAGMA foreign_keys=ON')
    try:
        with con:yield con
    finally:con.close()


def directory(workspace):
    if workspace=='principal':return root()
    if len(workspace)!=32 or any(c not in '0123456789abcdef' for c in workspace):raise LookupError('Workspace inválido.')
    return root()/'workspaces'/workspace


def setup(app):
    with app.app_context(),connection() as con:
        con.executescript('''CREATE TABLE IF NOT EXISTS users(id TEXT PRIMARY KEY,nome TEXT UNIQUE NOT NULL,senha TEXT NOT NULL,ativo INTEGER NOT NULL DEFAULT 1);
          CREATE TABLE IF NOT EXISTS workspaces(id TEXT PRIMARY KEY,nome TEXT NOT NULL);
          CREATE TABLE IF NOT EXISTS memberships(user_id TEXT REFERENCES users(id),workspace_id TEXT REFERENCES workspaces(id),papel TEXT NOT NULL,PRIMARY KEY(user_id,workspace_id));
          CREATE TABLE IF NOT EXISTS audit(id INTEGER PRIMARY KEY,usuario TEXT,workspace TEXT,acao TEXT,recurso TEXT,data TEXT);
          INSERT OR IGNORE INTO workspaces VALUES ('principal','Meu workspace');''')
        path=root()/'access-session.key'
        if not path.exists():
            value=secrets.token_bytes(32)
            if os.name=='nt':
                from ed_secrets import crypt
                value=crypt(value)
            path.write_bytes(value);path.chmod(0o600)
        value=path.read_bytes()
        if os.name=='nt':
            from ed_secrets import crypt
            value=crypt(value,True)
        app.config.update(SECRET_KEY=value,SESSION_COOKIE_NAME='edy_crm_session',SESSION_COOKIE_PATH='/api/ed',SESSION_COOKIE_HTTPONLY=True,SESSION_COOKIE_SAMESITE='Strict',PERMANENT_SESSION_LIFETIME=timedelta(hours=8))
        workspace_ids=[r[0] for r in con.execute("SELECT id FROM workspaces WHERE id!='principal'")]
        for ident in workspace_ids:
            token=data_directory.set(directory(ident))
            try:store.preparar()
            finally:data_directory.reset(token)
    attempts={}

    @app.before_request
    def identify():
        if not request.path.startswith('/api/ed'):return
        g.workspace_token=data_directory.set(root())
        with connection() as con:
            count=con.execute('SELECT COUNT(*) FROM users').fetchone()[0]
            user=con.execute('SELECT id,nome FROM users WHERE id=? AND ativo=1',(session.get('uid'),)).fetchone()
            membership=con.execute('SELECT papel FROM memberships WHERE user_id=? AND workspace_id=?',(session.get('uid'),session.get('workspace'))).fetchone()
        if not count:
            g.actor={'id':'local','nome':'Proprietário local','papel':'administrador','workspace':'principal','modo':'local'}
            return
        public=request.path in ('/api/ed/acesso/sessao','/api/ed/acesso/login','/api/ed/health')
        if not user or not membership:
            if public:return
            abort(401,description='Entre para acessar este workspace.')
        g.actor={'id':user['id'],'nome':user['nome'],'papel':membership['papel'],'workspace':session['workspace'],'modo':'sessao'}
        data_directory.set(directory(g.actor['workspace']))
        if request.method not in ('GET','HEAD','OPTIONS'):
            if request.path!='/api/ed/acesso/login' and (not session.get('csrf') or not secrets.compare_digest(request.headers.get('X-EDY-CSRF',''),session['csrf'])):
                abort(403,description='Sessão de formulário inválida. Recarregue e tente novamente.')
            if g.actor['papel']=='leitura' and request.path not in ('/api/ed/acesso/sair','/api/ed/acesso/workspace'):
                abort(403,description='Papel de leitura não permite alterar registros ou executar fornecedores.')
        admin_paths=('/api/ed/acesso/usuarios','/api/ed/acesso/workspaces','/api/ed/cofre','/api/ed/runtime/oauth','/api/ed/operacao/backup','/api/ed/destinos')
        if g.actor['papel']!='administrador' and (any(request.path.startswith(p) for p in admin_paths) or request.method not in ('GET','HEAD') and (request.path in ('/api/ed/config','/api/ed/runtime/conta-ativa') or request.path.startswith(('/api/ed/integracoes/','/api/ed/provedores/config','/api/ed/provedores/visual/config')))):
            abort(403,description='Esta configuração exige papel administrador.')

    @app.teardown_request
    def release(error):
        token=getattr(g,'workspace_token',None)
        if token is not None:data_directory.reset(token);g.workspace_token=None

    @app.after_request
    def audit(response):
        actor=getattr(g,'actor',None)
        if actor and request.method not in ('GET','HEAD','OPTIONS') and request.path.startswith('/api/ed'):
            with connection() as con:
                con.execute('INSERT INTO audit(usuario,workspace,acao,recurso,data) VALUES (?,?,?,?,?)',(actor['id'],actor['workspace'],request.method+' '+str(response.status_code),request.path[:500],store.agora()))
        return response

    @app.get('/api/ed/acesso/sessao',endpoint='ed_acesso_state')
    def state():
        actor=getattr(g,'actor',None)
        with connection() as con:
            rows=con.execute('SELECT w.id,w.nome,m.papel FROM workspaces w JOIN memberships m ON w.id=m.workspace_id WHERE m.user_id=?',(session.get('uid'),)).fetchall() if actor and actor['modo']=='sessao' else []
        return jsonify(ator=actor,workspaces=[dict(r) for r in rows],csrf=session.get('csrf'),login_necessario=actor is None)

    @app.post('/api/ed/acesso/setup',endpoint='ed_acesso_initial')
    def initial():
        data=body();name=store.texto(data.get('nome',''),80);password=store.texto(data.get('senha',''),200)
        if not name or len(password)<12:raise ValueError('Nome e senha de pelo menos 12 caracteres obrigatórios.')
        with connection() as con:
            con.execute('BEGIN IMMEDIATE')
            if con.execute('SELECT 1 FROM users LIMIT 1').fetchone():abort(409,description='Administrador inicial já existe.')
            uid=store.novo_id();con.execute('INSERT INTO users VALUES (?,?,?,1)',(uid,name,generate_password_hash(password)))
            con.execute('INSERT INTO memberships VALUES (?,?,?)',(uid,'principal','administrador'))
        session.clear();session.update(uid=uid,workspace='principal',csrf=secrets.token_hex(24));session.permanent=True
        return jsonify(mensagem='Acesso por usuários ativado. Proprietário local sem login deixou de ter acesso.'),201

    @app.post('/api/ed/acesso/login',endpoint='ed_acesso_login')
    def login():
        ip=request.remote_addr;recent=[t for t in attempts.get(ip,[]) if monotonic()-t<300]
        if len(recent)>=8:abort(429,description='Limite de tentativas. Aguarde cinco minutos.')
        attempts[ip]=recent+[monotonic()]
        data=body();name=store.texto(data.get('nome',''),80);password=store.texto(data.get('senha',''),200)
        with connection() as con:
            user=con.execute('SELECT * FROM users WHERE nome=? AND ativo=1',(name,)).fetchone()
            member=con.execute('SELECT workspace_id FROM memberships WHERE user_id=? ORDER BY workspace_id',(user['id'] if user else '',)).fetchone()
        if not user or not member or not check_password_hash(user['senha'],password):abort(401,description='Usuário ou senha inválidos.')
        session.clear();session.update(uid=user['id'],workspace=member['workspace_id'],csrf=secrets.token_hex(24));session.permanent=True;attempts[ip]=[]
        return jsonify(mensagem='Sessão iniciada.')

    @app.post('/api/ed/acesso/sair',endpoint='ed_acesso_logout')
    def logout():session.clear();return jsonify(mensagem='Sessão encerrada.')

    @app.post('/api/ed/acesso/workspace',endpoint='ed_acesso_choose')
    def choose():
        actor=getattr(g,'actor',None)
        if not actor or actor['modo']!='sessao':raise ValueError('Ative o acesso por usuários antes de selecionar workspaces.')
        ident=store.texto(body().get('id',''),80)
        with connection() as con:
            if not con.execute('SELECT 1 FROM memberships WHERE user_id=? AND workspace_id=?',(actor['id'],ident)).fetchone():abort(403)
        session['workspace']=ident;return jsonify(mensagem='Workspace selecionado. Dados e arquivos isolados.')

    @app.get('/api/ed/acesso/usuarios',endpoint='ed_acesso_users')
    def users():
        with connection() as con:rows=con.execute('SELECT u.id,u.nome,u.ativo,m.papel FROM users u JOIN memberships m ON u.id=m.user_id WHERE m.workspace_id=?',(g.actor['workspace'],)).fetchall()
        return jsonify([dict(r) for r in rows])

    @app.post('/api/ed/acesso/usuarios',endpoint='ed_acesso_create_user')
    def create_user():
        data=body();name=store.texto(data.get('nome',''),80);password=store.texto(data.get('senha',''),200);role=data.get('papel')
        if not name or len(password)<12 or role not in ROLES:raise ValueError('Informe nome, senha de 12 caracteres e papel válido.')
        with connection() as con:
            try:
                uid=store.novo_id();con.execute('INSERT INTO users VALUES (?,?,?,1)',(uid,name,generate_password_hash(password)));con.execute('INSERT INTO memberships VALUES (?,?,?)',(uid,g.actor['workspace'],role))
            except sqlite3.IntegrityError:abort(409,description='Nome de usuário já existe.')
        return jsonify(id=uid,nome=name,papel=role),201

    @app.post('/api/ed/acesso/workspaces',endpoint='ed_acesso_create_workspace')
    def create_workspace():
        actor=g.actor
        if actor['modo']!='sessao':raise ValueError('Ative usuários primeiro. O workspace principal e seus dados serão preservados.')
        name=store.texto(body().get('nome',''),100)
        if not name:raise ValueError('Informe o nome do workspace.')
        ident=store.novo_id();target=directory(ident);target.mkdir(parents=True)
        token=data_directory.set(target)
        try:store.preparar()
        finally:data_directory.reset(token)
        with connection() as con:
            con.execute('INSERT INTO workspaces VALUES (?,?)',(ident,name));con.execute('INSERT INTO memberships VALUES (?,?,?)',(actor['id'],ident,'administrador'))
        return jsonify(id=ident,nome=name),201

    @app.put('/api/ed/acesso/usuarios/<uid>',endpoint='ed_acesso_change_user')
    def change_user(uid):
        d=body()
        if not d or set(d)-{'papel','revogar'} or d.get('papel') not in (*ROLES,None) or ('revogar' in d and type(d['revogar']) is not bool):raise ValueError('Informe papel válido ou revogar booleano.')
        actor=g.actor
        with connection() as con:
            con.execute('BEGIN IMMEDIATE')
            member=con.execute('SELECT papel FROM memberships WHERE user_id=? AND workspace_id=?',(uid,actor['workspace'])).fetchone()
            if not member:raise LookupError('Usuário não pertence a este workspace.')
            count=con.execute("SELECT COUNT(*) FROM memberships WHERE workspace_id=? AND papel='administrador'",(actor['workspace'],)).fetchone()[0]
            if member['papel']=='administrador' and count==1 and (d.get('revogar') or d.get('papel')!='administrador'):abort(409,description='Mantenha ao menos um administrador neste workspace.')
            if d.get('revogar') is True:con.execute('DELETE FROM memberships WHERE user_id=? AND workspace_id=?',(uid,actor['workspace']))
            elif d.get('papel'):con.execute('UPDATE memberships SET papel=? WHERE user_id=? AND workspace_id=?',(d['papel'],uid,actor['workspace']))
        return jsonify(mensagem='Acesso atualizado neste workspace. Permissões são reavaliadas pelo worker; outros workspaces preservados.')
