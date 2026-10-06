"""Pacote de código para entrega posterior. Nenhuma publicação ou chamada remota."""
import hashlib
import io
import json
import zipfile
from flask import jsonify, send_file
import ed_store as store


def bundle(company, ident):
    from ed_services import ler_job
    from ed_runtime import artefact_root, validate_references
    lead = store.ler_empresa(company)
    job = ler_job(ident)
    if job.get('empresa_id') != company or job['tipo'] not in ('codex_construcao', 'template_construcao') or job['estado'] != 'concluida':
        raise ValueError('Escolha uma construção concluída desta empresa.')
    root = artefact_root(company, ident).resolve()
    files = {}
    code = []
    complete=job.get('resultado',{}).get('escopo')=='completo'
    names=('index.html', 'style.css', 'app.js', 'README.md', 'previa-local.css')+ (('app.py','requirements.txt','projeto.json','INICIAR.md') if complete else ())
    for name in names:
        path = root / name
        if path.is_file():
            if not path.resolve().is_relative_to(root): raise ValueError('Arquivo fora do projeto.')
            files[name] = path.read_bytes()
            if name.endswith(('.html', '.css', '.js')): code.append(dict(path=name, content=files[name].decode('utf-8')))
    if 'index.html' not in files: raise ValueError('Código da prévia ausente.')
    validate_references(root, code)
    inventory = json.loads((root / 'materiais.json').read_text(encoding='utf-8'))
    for item in inventory:
        name = item.get('arquivo')
        if not name: continue
        path = (root / name).resolve()
        if not name.startswith('materiais/') or not path.is_relative_to(root): raise ValueError('Caminho de material inválido.')
        raw = path.read_bytes()
        if hashlib.sha256(raw).hexdigest() != item['sha256']: raise ValueError('Material mudou. Preserve o original e exporte nova revisão.')
        files[name] = raw
    files['materiais.json'] = json.dumps(inventory, ensure_ascii=False, indent=2).encode()
    if complete:
        files['ENTREGA-COMPLETA.md']=('Execute python -m venv .venv; instale requirements.txt e execute python app.py --port 5163. Abra /setup para criar seu administrador. Banco novo em data/site.db, sem importar usuários, senhas ou dados pessoais do ambiente anterior. Backend Flask/SQLite exige hospedagem própria; Cloudflare Pages hospeda somente a prévia estática. Publicação posterior.').encode()
    provider=job.get('resultado',{}).get('provedor') or job.get('resultado',{}).get('origem') or 'Codex nativo'
    startup=('Crie uma .venv, instale requirements.txt e execute `python app.py --port 5163`. Abra http://127.0.0.1:5163/setup para criar o administrador. Consulte INICIAR.md. O servidor HTTP estático não executa login, banco ou painel.\n\n' if complete else 'Execute `python -m http.server 5163 --bind 127.0.0.1` nesta pasta. Abra http://127.0.0.1:5163.\n\n')
    files['ENTREGA.md'] = ('# '+('Site completo' if complete else 'Prévia local')+' — publicação posterior\n\nEmpresa: '+lead['nome']+'\n\n'
        'Recomendação para refinamento no Codex: GPT-6.1 Sol · Alto · Padrão. Origem desta versão: '+provider+'. Revise pendências, teclado, recortes e direitos antes de compartilhar.\n\n'+startup+
        'GitHub: escolha um repositório com Contents Write. Use uma branch nova e confira o diff; nenhuma branch ou arquivo remoto foi alterado.\n\n'
        'Cloudflare Pages: confirme o projeto e se usa Git ou Direct Upload. Esta pasta contém HTML estático pronto para revisão. Não publique nesta rodada. '
        'Flask/SQLite não são hospedados em Pages; aplicações completas exigem infraestrutura própria.\n\n'
        'R2/S3: materiais têm situação de uso no manifesto. Valide bucket privado, gravação/leitura e links temporários antes de enviar. '
        'Chaves e credenciais não acompanham o projeto.\n\n'
        'Referências comerciais foram usadas apenas como contexto visual e não fazem parte dos assets da página.\n').encode()
    files['integridade-entrega.json'] = json.dumps(dict(schema=1, empresa_id=company, construcao_id=ident,
        publicado=False, arquivos=[dict(arquivo=n,sha256=hashlib.sha256(raw).hexdigest()) for n,raw in files.items()]),ensure_ascii=False,indent=2).encode()
    if sum(map(len,files.values())) > 25_000_000: raise ValueError('Entrega acima de 25 MB.')
    out = io.BytesIO()
    with zipfile.ZipFile(out,'w',zipfile.ZIP_DEFLATED) as z:
        for name, raw in files.items(): z.writestr(name,raw)
    out.seek(0)
    return out


def registrar(bp):
    @bp.get('/empresas/<company>/construcoes/<ident>/entrega', endpoint='delivery_bundle')
    def download(company,ident):
        return send_file(bundle(company,ident),as_attachment=True,download_name='previa-edy-entrega.zip',mimetype='application/zip')
