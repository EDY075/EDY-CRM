"""Diagnóstico e backup online do workspace autorizado, sem segredos."""
import hashlib
import json
import sqlite3
import tempfile
import zipfile
from contextlib import closing
from flask import jsonify,g,send_file,current_app
import ed_store as store

def backup():
    base=store.pasta();target=base/'backups';target.mkdir(exist_ok=True);cache=base/'.cache/backup';cache.mkdir(parents=True,exist_ok=True)
    ident=store.novo_id();path=target/(ident+'.zip');files=[]
    with tempfile.TemporaryDirectory(dir=cache) as tmp,zipfile.ZipFile(path,'w',zipfile.ZIP_DEFLATED) as z:
        # O banco central de usuários é excluído do backup de workspace.
        for db in base.glob('*.db'):
            if db.name!='ed-crm.db':continue
            from pathlib import Path
            snap=Path(tmp)/db.name
            with closing(sqlite3.connect(db)) as source,closing(sqlite3.connect(snap)) as destination:
                source.backup(destination)
                if destination.execute('PRAGMA integrity_check').fetchone()[0]!='ok':raise ValueError('Integridade do banco não confirmada.')
            raw=snap.read_bytes();z.writestr(db.name,raw);files.append(dict(arquivo=db.name,sha256=hashlib.sha256(raw).hexdigest()))
        for folder in ('materiais','exportacoes','biblioteca'):
            for file in (base/folder).rglob('*'):
                if not file.is_file():continue
                name=file.relative_to(base).as_posix();raw=file.read_bytes();z.writestr(name,raw);files.append(dict(arquivo=name,sha256=hashlib.sha256(raw).hexdigest()))
        z.writestr('integridade-backup.json',json.dumps(files,indent=2))
    return dict(id=ident,arquivos=len(files),integridade='ok',download='/api/ed/operacao/backup/'+ident,criado_em=store.agora(),excluidos=['credenciais','runtime Codex','chave de sessão','outros workspaces','usuários centrais'])

def registrar(bp):
    @bp.get('/operacao/diagnostico',endpoint='ops_diagnostics')
    def diagnostics():
        import threading
        from ed_workflows import listing
        with store.conectar() as con:ok=con.execute('PRAGMA quick_check').fetchone()[0]
        jobs=listing()
        return jsonify(backend='Flask/Waitress',banco=ok,workspace=getattr(g,'actor',{}).get('workspace'),worker=dict(concorrencia=1,processo_ativo=bool(current_app.config['RUN_JOBS']),rotinas=any(t.name=='edy-rotinas' for t in threading.enumerate()),na_fila=sum(j['estado']=='na_fila' for j in jobs),executando=sum(j['estado']=='executando' for j in jobs)),restauracao='scripts/backup-edy.py restaurar --arquivo <ZIP relativo> --destino <pasta nova no projeto>',versao='0.4.0')
    @bp.post('/operacao/backup',endpoint='ops_backup')
    def create_backup():return jsonify(backup()),201
    @bp.get('/operacao/backup/<ident>',endpoint='ops_download_backup')
    def download_backup(ident):
        if len(ident)!=32 or any(x not in '0123456789abcdef' for x in ident):raise LookupError('Backup inválido.')
        path=store.pasta()/'backups'/(ident+'.zip')
        if not path.is_file():raise LookupError('Backup não encontrado neste workspace.')
        return send_file(path,as_attachment=True,download_name='backup-workspace-edy.zip')
