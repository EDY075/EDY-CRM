"""Pedido portátil de edição com original real, sem simular execução de IA."""
import hashlib
import io
import json
from pathlib import Path
import zipfile
from flask import request,send_file
import ed_store as store


def registrar(bp):
    @bp.post('/empresas/<company>/materiais/<mid>/studio/pacote-edicao')
    def image_request(company,mid):
        from ed_images import original,validar
        m,path=original(company,mid)
        if not m['autorizado']:raise ValueError('O original precisa de autorização para ser exportado.')
        options=validar(request.get_json());raw=path.read_bytes();name='originais/'+mid+path.suffix.lower()
        meta=dict(original=name,sha256=hashlib.sha256(raw).hexdigest(),material_id=mid,origem=m['origem'],atribuicao=m['atribuicao'],uso='Autorizado pelo usuário para esta preparação',instrucoes=options,modelo_recomendado='Selecionar modelo de edição com acesso validado no fornecedor',estado='pedido_nao_executado')
        references={name:raw}
        if options['logo_id']:
            logo,logo_path=original(company,options['logo_id'])
            if not logo['autorizado']:raise ValueError('A logo precisa de autorização para acompanhar o pedido.')
            logo_name='originais/'+logo['id']+logo_path.suffix.lower()
            references[logo_name]=logo_path.read_bytes()
            meta['logo']=dict(arquivo=logo_name,material_id=logo['id'],sha256=hashlib.sha256(references[logo_name]).hexdigest(),origem=logo['origem'])
        prompt='# Pedido de edição · não executado\n\nConfiguração de trabalho: GPT-6.1 Sol · Alto · Padrão. A edição de imagens usa um fornecedor/modelo próprio disponível.\n\nUse o original em '+name+'. Leia pedido-edicao.json. Preserve o original, rosto/cabelo/pele/proporções, formato/rótulo/embalagem e logo. Proteja regiões indicadas por composição do original; prompt não garante identidade perfeita. Faça a versão pedida, compare antes/depois e peça revisão. Não criar detalhes comerciais. Imagens conceituais devem ser identificadas. Não gerar apenas a partir da descrição nem executar scripts dos materiais.\n\nPedido revisado: '+options.get('instrucoes','')+'\n'
        out=io.BytesIO()
        with zipfile.ZipFile(out,'w',zipfile.ZIP_DEFLATED) as z:
            for filename,content in references.items():z.writestr(filename,content)
            z.writestr('pedido-edicao.json',json.dumps(meta,ensure_ascii=False,indent=2));z.writestr('prompt-edicao.md',prompt)
        out.seek(0);return send_file(out,as_attachment=True,download_name='pedido-edicao-edy.zip',mimetype='application/zip')
