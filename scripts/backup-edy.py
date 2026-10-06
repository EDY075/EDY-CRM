"""Backup/restauração offline em diretório novo, sem segredos de fornecedores."""
import argparse
import hashlib
import json
import sqlite3
from pathlib import Path
from datetime import datetime,timezone
import zipfile
import tempfile
from contextlib import closing

root=Path(__file__).resolve().parents[1]
parser=argparse.ArgumentParser();parser.add_argument('acao',choices=('criar','restaurar'));parser.add_argument('--arquivo');parser.add_argument('--destino');args=parser.parse_args()
if args.acao=='criar':
    output=root/'data/backups';output.mkdir(parents=True,exist_ok=True)
    archive=output/('edy-'+datetime.now(timezone.utc).strftime('%Y%m%d-%H%M%S')+'.zip')
    cache=root/'.cache/backup';cache.mkdir(parents=True,exist_ok=True)
    with tempfile.TemporaryDirectory(dir=cache) as tmp,zipfile.ZipFile(archive,'w',zipfile.ZIP_DEFLATED) as z:
        files=[]
        for base in [root/'data',*(root/'data/workspaces').glob('*')] if (root/'data/workspaces').exists() else [root/'data']:
            for database in base.glob('*.db'):
                name=database.relative_to(root/'data').as_posix();snap=Path(tmp)/(hashlib.sha256(name.encode()).hexdigest()+'.db')
                with closing(sqlite3.connect(database)) as source,closing(sqlite3.connect(snap)) as target:source.backup(target);assert target.execute('PRAGMA integrity_check').fetchone()[0]=='ok'
                raw=snap.read_bytes();z.writestr(name,raw);files.append(dict(arquivo=name,sha256=hashlib.sha256(raw).hexdigest()))
            for folder in ('materiais','exportacoes','biblioteca','visuais'):
                for file in (base/folder).rglob('*'):
                    if file.is_file():
                        name=file.relative_to(root/'data').as_posix();raw=file.read_bytes();z.writestr(name,raw);files.append(dict(arquivo=name,sha256=hashlib.sha256(raw).hexdigest()))
        z.writestr('integridade-backup.json',json.dumps(files,indent=2))
    print(archive.relative_to(root).as_posix(),len(files),'arquivos; credenciais/runtime/chave de sessão excluídos')
else:
    if not args.arquivo or not args.destino:raise SystemExit('Informe --arquivo e --destino (pasta nova dentro deste projeto).')
    source=(root/args.arquivo).resolve();target=(root/args.destino).resolve()
    if not source.is_relative_to(root) or not target.is_relative_to(root) or target.exists():raise SystemExit('Restauração exige pasta nova dentro do projeto; não sobrescreve banco atual.')
    with zipfile.ZipFile(source) as z:
        files=json.loads(z.read('integridade-backup.json'))
        for entry in files:
            name=entry['arquivo'];dest=(target/name).resolve();raw=z.read(name)
            if not dest.is_relative_to(target) or ':' in name or '\\' in name or hashlib.sha256(raw).hexdigest()!=entry['sha256']:raise SystemExit('Backup inválido.')
        for entry in files:
            dest=target/entry['arquivo'];dest.parent.mkdir(parents=True,exist_ok=True);dest.write_bytes(z.read(entry['arquivo']))
    for db in target.rglob('*.db'):
        with closing(sqlite3.connect(db)) as con:assert con.execute('PRAGMA integrity_check').fetchone()[0]=='ok'
    print('Restauração conferida em',target.relative_to(root).as_posix(),'; dados atuais preservados.')
