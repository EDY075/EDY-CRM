"""Inspeção redigida de índice e histórico Git; nunca imprime valores encontrados."""
import json
import re
import subprocess
from pathlib import Path

ROOT=Path(__file__).resolve().parents[1]
PATTERNS={
    'github-token':rb'gh[pousr]_[A-Za-z0-9]{25,}',
    'openai-key':rb'sk-(?:proj-)?[A-Za-z0-9_-]{28,}',
    'google-key':rb'AIza[A-Za-z0-9_-]{30,}',
    'jwt':rb'eyJ[A-Za-z0-9_-]{16,}\.[A-Za-z0-9_-]{16,}\.[A-Za-z0-9_-]{16,}',
    'private-key':rb'-----BEGIN (?:RSA |EC |OPENSSH )?PRIVATE KEY-----',
}
FORBIDDEN={'data','data-demo','node_modules','.venv','.cache','.tools','logs','work','resources','tasks'}


def private_path(name):
    p=Path(name)
    return (any(part in FORBIDDEN for part in p.parts)
            or p.suffix.lower() in ('.db','.sqlite','.sqlite3','.dpapi','.log')
            or p.name in ('auth.json','access-session.key')
            or (p.name.startswith('.env') and p.name!='.env.example'))


def git(*args):
    return subprocess.check_output(['git',*args],cwd=ROOT)


def main():
    files=list(filter(None,git('ls-files','-z').decode().split('\0')))
    issues=[];scanned=set();largest=0
    def inspect(label,raw):
        nonlocal largest
        largest=max(largest,len(raw))
        if len(raw)>40_000_000:issues.append({'arquivo':label,'motivo':'acima de 40 MB'})
        for name,pattern in PATTERNS.items():
            if re.search(pattern,raw):issues.append({'arquivo':label,'motivo':name+' (valor omitido)'})
    for name in files:
        if private_path(name):
            issues.append({'arquivo':name,'motivo':'arquivo privado/gerado'})
        inspect('indice:'+name,git('show',':'+name))
    has_head=subprocess.run(['git','rev-parse','--verify','--quiet','HEAD'],cwd=ROOT,capture_output=True).returncode==0
    commits=git('rev-list','--all').decode().splitlines() if has_head else []
    for commit in commits:
        for row in git('ls-tree','-r',commit).decode().splitlines():
            meta,name=row.split('\t',1);kind,oid=meta.split()[1:]
            if private_path(name):
                issues.append({'arquivo':'historico:'+name,'motivo':'arquivo privado/gerado'})
            if kind=='blob' and oid not in scanned:
                scanned.add(oid);inspect('historico:'+name,git('cat-file','blob',oid))
    result={'arquivos_indice':len(files),'commits_publicos':len(commits),'blobs_historico':len(scanned),'maior_arquivo_bytes':largest,'achados':issues,'limite':'Padrões e nomes conhecidos; não substitui revisão humana.'}
    print(json.dumps(result,ensure_ascii=False,indent=2))
    return 1 if issues else 0


if __name__=='__main__':raise SystemExit(main())
