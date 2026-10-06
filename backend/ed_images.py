"""Estúdio local e edição externa separada. Original nunca é sobrescrito."""
import hashlib
import io
import json
import math
import base64
from PIL import Image, ImageEnhance, ImageFilter, ImageStat, ImageOps, ImageDraw
from flask import jsonify, request, send_file
import ed_store as store
from ed_services import lock


def original(company,mid):
    from ed_routes import material
    m=material(company,mid)
    path=store.arquivo_seguro('materiais',company+'/'+m['arquivo'])
    if not path.is_file(): raise ValueError('Original ausente. Envie o arquivo novamente como novo material.')
    return m,path


def carregar(path):
    with Image.open(path) as source:
        if source.width*source.height>24_000_000: raise ValueError('Imagem acima de 24 megapixels.')
        return ImageOps.exif_transpose(source).convert('RGBA')


def analisar(m,path):
    im=carregar(path); w,h=im.size
    small=im.convert('L'); small.thumbnail((256,256))
    stat=ImageStat.Stat(small); edges=ImageStat.Stat(small.filter(ImageFilter.FIND_EDGES)).mean[0]
    hist=small.histogram(); total=sum(hist)
    dark=sum(hist[:16])/total; bright=sum(hist[240:])/total
    reasons=[]
    if w<1200: reasons.append('Largura abaixo de 1200 px: pode perder detalhe na abertura desktop.')
    if min(w,h)<600: reasons.append('Lado menor abaixo de 600 px: prefira cartão pequeno ou solicite original maior.')
    if dark>.35: reasons.append('Muitos pixels próximos do preto. Pode ser estética intencional; confira detalhe nas sombras.')
    if bright>.35: reasons.append('Muitos pixels claros. Confira se há áreas estouradas ou um fundo intencionalmente claro.')
    if edges<8: reasons.append('Baixo contraste de bordas: possível desfoque ou imagem lisa. Heurística não identifica a causa.')
    return dict(largura=w,altura=h,proporcao=round(w/h,3),bytes=path.stat().st_size,
        brilho_medio=round(stat.mean[0],1),contraste_bordas=round(edges,1),sombras=round(dark,3),claros=round(bright,3),
        motivos=reasons or ['Dimensões adequadas para avaliação visual; confira o recorte e a identidade do conteúdo.'],
        incertezas=['Compressão perceptual, enquadramento, espaço para texto, identidade e conteúdo exigem revisão visual. Métricas não são uma nota objetiva de qualidade.'],
        adequacao={'abertura':'Candidata: revisar recorte desktop/mobile' if w>=1200 else 'Solicitar maior resolução ou limitar largura',
                   'galeria':'Revisar visualmente','produto':'Exige confirmação do produto real','equipe':'Exige identificação e autorização; não deduzida da imagem'})


def retangulo(raw):
    if not isinstance(raw,list) or len(raw)!=4 or any(type(x) not in (int,float) or not math.isfinite(x) or x<0 or x>1 for x in raw):
        raise ValueError('Recorte/região deve conter x, y, largura e altura entre 0 e 1.')
    x,y,w,h=raw
    if w<=0 or h<=0 or x+w>1.00001 or y+h>1.00001: raise ValueError('Região fora da imagem.')
    return raw


def pixels(rect,size):
    x,y,w,h=rect; W,H=size
    return (round(x*W),round(y*H),round((x+w)*W),round((y+h)*H))


def validar(data):
    allowed={'acao','recorte','exposicao','contraste','destino','instrucoes','natureza','protegidas','logo_id','fundo','cor_fundo'}
    if not isinstance(data,dict) or set(data)-allowed: raise ValueError('Configuração de imagem inválida.')
    out=dict(acao=data.get('acao','local'),recorte=retangulo(data.get('recorte',[0,0,1,1])),destino=store.texto(data.get('destino','desktop'),30),
             instrucoes=store.texto(data.get('instrucoes',''),4000),natureza=data.get('natureza','a_confirmar'),protegidas=data.get('protegidas',[]),logo_id=data.get('logo_id',''),fundo=data.get('fundo','preservar'),cor_fundo=data.get('cor_fundo','#ffffff'))
    if out['acao'] not in ('local','ia') or out['natureza'] not in ('pessoa','produto','ambiente','ilustracao','a_confirmar'): raise ValueError('Ação ou natureza inválida.')
    if not isinstance(out['protegidas'],list) or len(out['protegidas'])>10: raise ValueError('Até dez regiões protegidas.')
    out['protegidas']=[retangulo(x) for x in out['protegidas']]
    for key in ('exposicao','contraste'):
        v=data.get(key,1)
        if type(v) not in (float,int) or not math.isfinite(v) or not .5<=v<=1.5: raise ValueError('Ajustes devem ficar entre 0,5 e 1,5.')
        out[key]=v
    import re
    if not isinstance(out['fundo'],str) or out['fundo'] not in ('preservar','remover_claro','substituir_claro') or not isinstance(out['cor_fundo'],str) or not re.fullmatch(r'#[0-9a-fA-F]{6}',out['cor_fundo']): raise ValueError('Fundo inválido.')
    if not isinstance(out['logo_id'],str) or len(out['logo_id'])>100: raise ValueError('Logo inválida.')
    if out['acao']=='ia' and out['natureza'] in ('pessoa','produto') and not out['protegidas']:
        raise ValueError('Marque regiões protegidas da pessoa/produto. O prompt não garante preservação da identidade.')
    return out


class OpenAIImages:
    def test(self,settings):
        from ed_connectors import request_json,auth
        model=settings.get('modelo') or 'gpt-image-2.5-sunburst'
        import re
        if not re.fullmatch(r'[a-zA-Z0-9._-]{1,100}',model): raise ValueError('ID de modelo inválido.')
        request_json('GET','https://api.openai.com/v1/models/'+model,headers=auth('openai_imagens'))
        return dict(mensagem='Modelo consultado com autenticação. Edição ainda requer permissões, saldo e uma operação concluída.',consumo=None)

    def edit(self,im,options,settings):
        import requests,ed_secrets,time
        key=ed_secrets.get('openai_imagens')
        if not key: raise ValueError('Sem chave da API de imagens. O plano Codex não fornece essa credencial. Use ajustes locais.')
        prompt=options['instrucoes']
        if len(prompt)<10: raise ValueError('Descreva a edição desejada (mínimo dez caracteres).')
        source=io.BytesIO(); im.save(source,'PNG')
        mask=Image.new('RGBA',im.size,(0,0,0,0)); draw=ImageDraw.Draw(mask)
        for rect in options['protegidas']: draw.rectangle(pixels(rect,im.size),fill=(255,255,255,255))
        mask_bytes=io.BytesIO(); mask.save(mask_bytes,'PNG')
        model=settings.get('modelo') or 'gpt-image-2.5-sunburst'
        with requests.Session() as session:
            session.trust_env=False
            try:
                with session.post('https://api.openai.com/v1/images/edits',headers={'Authorization':'Bearer '+key},
                    data={'model':model,'prompt':prompt+' Preserve as regiões protegidas, identidade e características reais. Não invente texto, rótulos ou detalhes comerciais.','n':'1','size':'auto'},
                    files={'image':('original.png',source.getvalue(),'image/png'),'mask':('mask.png',mask_bytes.getvalue(),'image/png')},timeout=(5,120),allow_redirects=False,stream=True) as res:
                    if not 200<=res.status_code<300: raise ValueError(f'Edição recusada: HTTP {res.status_code}. Confira modelo, acesso e saldo. Nenhuma versão gerada.')
                    chunks=[]; length=0;began=time.monotonic()
                    for chunk in res.iter_content(65536):
                        if time.monotonic()-began>150:raise ValueError('Resposta de imagem excedeu o prazo de leitura.')
                        length+=len(chunk)
                        if length>16_000_000: raise ValueError('Resposta de imagem excedeu 16 MB.')
                        chunks.append(chunk)
                    value=json.loads(b''.join(chunks))
                content=base64.b64decode(value['data'][0]['b64_json'],validate=True)
                edited=carregar(io.BytesIO(content))
            except (requests.RequestException,KeyError,TypeError,ValueError) as exc:
                if isinstance(exc,ValueError) and str(exc).startswith(('Edição recusada','Resposta de imagem')): raise
                raise ValueError('Resposta de imagem inválida ou falha de rede; original preservado.') from None
        # A máscara do modelo não é garantia pixel a pixel. Restaurar regiões do original.
        if options['protegidas'] and edited.size!=im.size:
            raise ValueError('Fornecedor alterou dimensões; não é seguro restaurar regiões protegidas. Versão rejeitada.')
        for rect in options['protegidas']:
            box=pixels(rect,im.size); edited.paste(im.crop(box),box[:2])
        usage={k:v for k,v in value.get('usage',{}).items() if type(v) in (int,float)}
        return edited,model,usage


def editar(company,mid,options,job_id=None):
    from ed_tasks import ativo
    m,path=original(company,mid); im=carregar(path); original_hash=hashlib.sha256(path.read_bytes()).hexdigest()
    if len(m.get('versoes',[]))>=12: raise ValueError('Limite de doze versões por original. Preserve as versões e envie novo material se necessário.')
    model='Pillow local'; usage=None; nature='imagem_tratada'
    if options['acao']=='ia':
        from ed_services import config
        im,model,usage=OpenAIImages().edit(im,options,config('openai_imagens')); nature='imagem_editada_ia'
    original_image=carregar(path)
    im=ImageEnhance.Brightness(im).enhance(options['exposicao'])
    im=ImageEnhance.Contrast(im).enhance(options['contraste'])
    if options['fundo']!='preservar':
        if im.width*im.height>4_000_000: raise ValueError('Remoção local de fundo limitada a 4 megapixels. Use recorte ou IA.')
        pixels_data=[]
        for r,g,b,a in im.getdata():
            if min(r,g,b)>240:
                if options['fundo']=='remover_claro': a=0
                else:
                    color=options['cor_fundo']; r,g,b=[int(color[i:i+2],16) for i in (1,3,5)]
            pixels_data.append((r,g,b,a))
        im.putdata(pixels_data)
    for rect in options['protegidas']:
        if im.size!=original_image.size: raise ValueError('Dimensões incompatíveis para proteger regiões.')
        box=pixels(rect,im.size); im.paste(original_image.crop(box),box[:2])
    box=pixels(options['recorte'],im.size)
    if box[2]-box[0]<16 or box[3]-box[1]<16: raise ValueError('Recorte menor que 16 pixels.')
    im=im.crop(box)
    dependencies=[]
    if options['logo_id']:
        logo,logo_path=original(company,options['logo_id'])
        if not logo['autorizado']: raise ValueError('Logo precisa de autorização; nenhum desenho de marca será inventado.')
        logo_im=carregar(logo_path); logo_im.thumbnail((max(16,im.width//5),max(16,im.height//5)))
        im.alpha_composite(logo_im,(max(0,im.width-logo_im.width-16),max(0,im.height-logo_im.height-16)))
        dependencies=[logo['id']]; nature='composicao'
    vid=store.novo_id(); name=f'{mid}-{vid}.png'; out=store.arquivo_seguro('materiais',company+'/'+name)
    content=io.BytesIO(); im.save(content,'PNG'); version=dict(id=vid,arquivo=name,largura=im.width,altura=im.height,criado_em=store.agora(),
        original_id=mid,original_sha256=original_hash,sha256=hashlib.sha256(content.getvalue()).hexdigest(),modelo=model,
        instrucoes=options,natureza=nature,dependencias=dependencies,estado='para_revisao',consumo=usage,
        arquivo_url=f'/api/ed/empresas/{company}/materiais/{mid}/studio/versoes/{vid}/arquivo')
    with lock,store.conectar() as con:
        if job_id: ativo(job_id)
        row=con.execute('SELECT dados FROM ed_materiais WHERE id=? AND empresa_id=?',(mid,company)).fetchone()
        current=json.loads(row['dados']); versions=current.setdefault('versoes',[])
        if len(versions)>=12: raise ValueError('Limite de versões alcançado durante a edição.')
        if hashlib.sha256(path.read_bytes()).hexdigest()!=original_hash: raise ValueError('Original mudou durante edição; versão rejeitada.')
        out.write_bytes(content.getvalue()); versions.append(version)
        con.execute('UPDATE ed_materiais SET dados=? WHERE id=? AND empresa_id=?',(json.dumps(current,ensure_ascii=False),mid,company))
    return version


def arquivo_exportacao(company,m):
    selected=m.get('versao_exportacao','original')
    if selected=='original': return m['arquivo'],None
    version=next((v for v in m.get('versoes',[]) if v['id']==selected and v['estado']=='aprovada'),None)
    if not version: raise ValueError('Versão selecionada não está aprovada.')
    from ed_routes import material
    for dep in version.get('dependencias',[]):
        if not material(company,dep)['autorizado']: raise ValueError('Autorização da logo usada na composição foi revogada.')
    return version['arquivo'],version


def registrar(bp):
    @bp.get('/empresas/<company>/materiais/<mid>/studio')
    def image_inspect(company,mid):
        m,path=original(company,mid)
        return jsonify(avaliacao=analisar(m,path),original_sha256=hashlib.sha256(path.read_bytes()).hexdigest(),
                       versoes=m.get('versoes',[]),versao_exportacao=m.get('versao_exportacao','original'))

    @bp.post('/empresas/<company>/materiais/<mid>/studio/editar')
    def image_edit(company,mid):
        options=validar(request.get_json()); original(company,mid)
        if options['acao']=='ia':
            import ed_secrets
            if not ed_secrets.get('openai_imagens'): raise ValueError('Sem credencial da API de imagens; ajustes locais continuam disponíveis.')
            from ed_tasks import iniciar
            def worker(job,progress):
                progress(25,'Editando com o fornecedor. Cancelamento impede aplicação tardia; consumo remoto pode ocorrer.')
                from ed_services import log,fingerprint
                try:
                    version=editar(company,mid,options,job['id'])
                    log('openai_imagens',dict(estado='conectado',mensagem='Edição retornou arquivo validado; versão aguarda revisão visual.',data=store.agora(),consumo=version['consumo'],fingerprint=fingerprint('openai_imagens')))
                    return version
                except ValueError:
                    log('openai_imagens',dict(estado='erro',mensagem='Edição falhou; original preservado. Consulte a operação.',data=store.agora(),fingerprint=fingerprint('openai_imagens')))
                    raise
            return jsonify(iniciar('openai_imagens','imagem',company,dict(material_id=mid),worker)),202
        return jsonify(editar(company,mid,options)),201

    @bp.post('/empresas/<company>/materiais/<mid>/studio/selecionar')
    def image_select(company,mid):
        d=request.get_json()
        if not isinstance(d,dict) or set(d)!={'versao','selecionado'}: raise ValueError('Seleção inválida.')
        chosen=store.booleano(d['selecionado'])
        with lock,store.conectar() as con:
            row=con.execute('SELECT dados FROM ed_materiais WHERE id=? AND empresa_id=?',(mid,company)).fetchone()
            if not row: raise LookupError('Material não encontrado nesta empresa.')
            m=json.loads(row['dados'])
            if chosen and not m['autorizado']: raise ValueError('Confirme autorização antes de selecionar.')
            v=next((x for x in m.get('versoes',[]) if x['id']==d['versao']),None)
            if d['versao']!='original' and not v: raise LookupError('Versão não pertence ao original.')
            if v: v['estado']='aprovada' if chosen else 'rejeitada'
            if chosen: m['versao_exportacao']=d['versao']; m['selecionado']=True
            elif m.get('versao_exportacao')==d['versao']: m['versao_exportacao']='original'; m['selecionado']=False
            if chosen: arquivo_exportacao(company,dict(id=mid,**m))
            con.execute('UPDATE ed_materiais SET dados=? WHERE id=? AND empresa_id=?',(json.dumps(m,ensure_ascii=False),mid,company))
        return jsonify(m)

    @bp.get('/empresas/<company>/materiais/<mid>/studio/versoes/<vid>/arquivo')
    def image_version_file(company,mid,vid):
        m,_=original(company,mid)
        v=next((x for x in m.get('versoes',[]) if x['id']==vid),None)
        if not v: raise LookupError('Versão não encontrada nesta empresa.')
        return send_file(store.arquivo_seguro('materiais',company+'/'+v['arquivo']))
