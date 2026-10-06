"""Conhecimento versionado; referências são dados, skills são instruções revisadas."""
import hashlib
import json
import re
from pathlib import Path
import io
from flask import jsonify, request, send_file
from werkzeug.exceptions import Conflict
import ed_store as store

PROFILES = {
 'artistico':dict(nome='Editorial artístico',cores=['#141414','#ece6db','#c1957a'],descricao='Hero dividido, títulos serifados, arco fotográfico, portfólio filtrável e processo. Arcos apenas quando coerentes.',movimento='Entradas suaves; detalhes de ponteiro opcionais.'),
 'comercio':dict(nome='Comércio editorial',cores=['#123e3b','#f5f1e8','#d5b778'],descricao='Fotografia de produto, categorias, contraste papel/verde, manifesto e jornada de conversa. Dourado final da cascata.',movimento='Galeria com filtros, lightbox e cartões acessíveis.'),
 'celebracao':dict(nome='Serviço e celebração',cores=['#76262e','#f5f0e7','#b28b59'],descricao='Fotografia imersiva desktop, tratamento próprio mobile, histórias, serviço, pessoas identificadas e convite.',movimento='Entradas discretas e ornamentos por interação; sem shaders obrigatórios.')}
SKILLS = {
 'Direção visual EDY':'Fotografia protagonista, contraste editorial entre títulos e corpo, alternância de superfícies e ritmo entre seções. Adapte à marca; não copie fotos ou dados das referências.',
 'Fotografia fiel':'Use os originais autorizados. Preserve identidade, produtos, embalagem e logo; proteja regiões/componha originais se a fidelidade exata for necessária. Identifique imagens conceituais. Prompt sozinho não garante identidade.',
 'Composição por seção':'Quatro alternativas devem mudar distribuição e hierarquia, fundo, enquadramento ou interação. FAQ, rodapé, galeria e serviços têm estruturas próprias. Preserve seções fixadas.',
 'Movimento com propósito':'Cursor nativo, efeitos de ponteiro somente mouse fino, reduced-motion estático, pause com aba oculta. Títulos legíveis sem esperar animação. Priorize transform e opacity.',
 'Responsividade e acessibilidade':'Verifique 390, 768 e desktop; teclado, foco, labels, contraste, zoom e ausência de overflow. Diálogos devem restaurar foco; formulários precisam de erros claros.',
 'Copy com evidências':'Não invente serviços, preços, equipe, depoimentos, endereço ou métricas. Separe fatos confirmados de sugestões. Use pendências e placeholders identificados.',
 'SEO técnico':'Título e descrição específicos, hierarquia h1/h2, alt descritivo, navegação com URLs relativas. Não gerar schema comercial para dados ainda não confirmados.',
 'Backend e administração':'Banco separado do CRM, login seguro, papéis, validação de entradas, CRUD com persistência, CSRF, migrações, .env.example sem segredos e testes. Módulos comerciais externos dependem de acesso explícito.'}


def setup():
    with store.conectar() as con:
        con.execute('CREATE TABLE IF NOT EXISTS ed_biblioteca (id TEXT, versao INTEGER, dados TEXT NOT NULL, PRIMARY KEY(id,versao))')
        exists=con.execute('SELECT 1 FROM ed_biblioteca LIMIT 1').fetchone()
    if not exists:
        save(dict(tipo='contexto',titulo='Preferências EDY aprovadas',conteudo='EDY CRM. GPT-6.1 Sol · Alto · Padrão. Preserve dados e versões. Temas do CRM independentes das páginas. Fotos reais exigem autorização. Nunca trocar modelo ou cobrança silenciosamente.',escopo='global',origem='CONTEXTO-EDY · kit 05/10/2026'))
        for title,content in SKILLS.items():save(dict(tipo='skill',titulo=title,conteudo=content,escopo='global',origem='Kit EDY · instruções materializadas no pacote/runtime'))
        for key,p in PROFILES.items():save(dict(tipo='referencia',titulo=p['nome'],conteudo=p['descricao']+' '+p['movimento'],escopo='global',origem='EDY-DESIGN · referência visual; direitos não transferidos',perfil=key,elementos=['composicao','tipografia','movimento']))


def get(ident):
    with store.conectar() as con:r=con.execute('SELECT dados FROM ed_biblioteca WHERE id=? ORDER BY versao DESC LIMIT 1',(ident,)).fetchone()
    if not r:raise LookupError('Item da biblioteca não encontrado.')
    return json.loads(r['dados'])


def items():
    with store.conectar() as con:rows=con.execute('SELECT dados FROM ed_biblioteca b WHERE versao=(SELECT MAX(versao) FROM ed_biblioteca WHERE id=b.id) ORDER BY rowid DESC').fetchall()
    return [json.loads(r['dados']) for r in rows]


def save(data,ident=None):
    if not isinstance(data,dict):raise ValueError('Item inválido.')
    old=get(ident) if ident else None
    if old and data.get('versao')!=old['versao']:raise Conflict('Item mudou em outra janela. Recarregue antes de salvar.')
    merged={**(old or {}),**data}
    for key,opts,default in [('tipo',('contexto','referencia','skill'),'contexto'),('escopo',('global','nicho','lead','projeto'),'global'),('estado',('ativo','inativo','arquivado'),'ativo')]:
        if merged.get(key,default) not in opts:raise ValueError('Tipo, escopo ou estado inválido.')
        merged[key]=merged.get(key,default)
    out={k:store.texto(merged.get(k,''),250000 if k=='conteudo' else 500) for k in ('titulo','conteudo','vinculo','origem','perfil','licenca')}
    out['essenciais']=store.texto(merged.get('essenciais',''),6000)
    out['prioridade']=merged.get('prioridade',5)
    if type(out['prioridade'])!=int or not 0<=out['prioridade']<=10:raise ValueError('Prioridade deve ser de 0 a 10.')
    if not out['titulo'] or not out['conteudo']:raise ValueError('Informe título e conteúdo.')
    if merged['escopo'] in ('lead','projeto'):store.ler_empresa(out['vinculo'])
    if merged['escopo']=='nicho' and not out['vinculo']:raise ValueError('Informe o nicho deste item.')
    for key in ('capacidades','elementos'):
        val=merged.get(key,[])
        if not isinstance(val,list) or len(val)>15:raise ValueError('Lista inválida.')
        out[key]=[store.texto(v,100) for v in val]
    out.update({k:merged[k] for k in ('tipo','escopo','estado')},id=ident or store.novo_id(),versao=(old['versao']+1 if old else 1),criado_em=old['criado_em'] if old else store.agora(),atualizado_em=store.agora())
    out['projeto_id']=store.texto(merged.get('projeto_id',''),80)
    if out['projeto_id']:
        if out['escopo']!='projeto':raise ValueError('Projeto específico exige escopo projeto.')
        from ed_adaptive import project_key
        out['projeto_id']=project_key(out['vinculo'],out['projeto_id'])
    out['correcao_adaptativa']=store.booleano(merged.get('correcao_adaptativa',False))
    out['origem_feedback']=merged.get('origem_feedback','')
    if out['origem_feedback'] not in ('','usuario_explicito','observacao_modelo','observacao_revisada'):raise ValueError('Origem de feedback inválida.')
    if out['origem_feedback']=='observacao_modelo':out['estado']='inativo'
    if old and old.get('original'):out['original']=old['original']
    if old and old.get('analise_html'):out['analise_html']=old['analise_html']
    out['sha256']=hashlib.sha256(out['conteudo'].encode()).hexdigest()
    with store.conectar() as con:
        try:con.execute('INSERT INTO ed_biblioteca VALUES (?,?,?)',(out['id'],out['versao'],json.dumps(out,ensure_ascii=False)))
        except Exception as exc:
            import sqlite3
            if isinstance(exc,sqlite3.IntegrityError):raise Conflict('Versão concorrente. Recarregue.') from None
            raise
    return out


def selection(company):
    with store.conectar() as con:r=con.execute('SELECT valor FROM ed_config WHERE chave=?',('biblioteca:'+company,)).fetchone()
    return json.loads(r['valor']) if r else dict(selecionados=None,perfil='',elementos=['composicao','tipografia','movimento'])


def eligible(item,lead,project=''):
    if item.get('projeto_id'):
        if not project:return False
        from ed_adaptive import project_key
        if item['projeto_id']!=project_key(lead['id'],project):return False
    return item['estado']=='ativo' and (item['escopo']=='global' or item['escopo']=='nicho' and store.normalizar(item['vinculo'])==store.normalizar(lead['nicho']) or item['escopo'] in ('lead','projeto') and item['vinculo']==lead['id'])


def retrieve(item,query,budget):
    """Índice lexical determinístico; origem/offset e texto completo ficam preservados."""
    content=item['conteudo'];terms=set(re.findall(r'\w{3,}',query.casefold()))
    pieces=[(offset,content[offset:offset+1600]) for offset in range(0,len(content),1600)]
    ranked=sorted(pieces,key=lambda x:(sum(t in x[1].casefold() for t in terms),-x[0]),reverse=True)
    chosen=[];size=0
    # Início e final sempre participam; requisitos no final não somem silenciosamente.
    order=[pieces[0],pieces[-1],*ranked] if pieces else []
    for offset,text in order:
        if any(x['inicio']==offset for x in chosen):continue
        if size+len(text)>budget:continue
        chosen.append(dict(inicio=offset,fim=offset+len(text),texto=text));size+=len(text)
    chosen.sort(key=lambda x:x['inicio'])
    return {**item,'conteudo':'\n[…]\n'.join(x['texto'] for x in chosen),'recuperacao':dict(metodo='lexical + início/final',total_caracteres=len(content),trechos=chosen,original_preservado=True)}

def resolve(company,project=''):
    lead=store.ler_empresa(company);sel=selection(company)
    if project:
        from ed_adaptive import project_key
        project=project_key(company,project)
    available=[x for x in items() if eligible(x,lead,project)]
    chosen=[x for x in available if x.get('correcao_adaptativa') or (sel['selecionados'] is None and (x['tipo']!='referencia' or not x['perfil'] or x['perfil']==sel['perfil'])) or sel['selecionados'] is not None and x['id'] in sel['selecionados']]
    # Atual explícito/projeto precede nicho/global para títulos que representam a mesma decisão.
    chosen.sort(key=lambda x:({'global':0,'nicho':1,'lead':2,'projeto':3}[x['escopo']],x.get('prioridade',5),x['atualizado_em']),reverse=True)
    used=[];seen=set();conflicts=[];size=0;pending=[];essential_items=[]
    for x in chosen:
        name=store.normalizar(x['titulo'])
        if name in seen:conflicts.append(dict(titulo=x['titulo'],ignorado=x['id'],motivo='Decisão mais específica/recente prevalece.'));continue
        seen.add(name)
        if x.get('essenciais'):essential_items.append(x)
        remaining=32000-size
        if remaining<1600:pending.append('Limite de contexto: '+x['titulo']+'; original e restrições preservados na Biblioteca.');continue
        if len(x['conteudo'])>min(8000,remaining):
            x=retrieve(x,' '.join(str(lead.get(k,'')) for k in ('nome','nicho','descricao','servicos'))+' hero mobile responsividade imagens fatos motion pendencias',min(8000,remaining))
            pending.append('Guia extenso recuperado em trechos: '+x['titulo']+'; consulte o original antes de requisitos fora dos trechos.')
        missing=[c for c in x['capacidades'] if c not in ('texto','html','css','javascript','templates')]
        if missing:pending.append('Capacidade não validada em '+x['titulo']+': '+', '.join(missing))
        if x['tipo']=='referencia':
            x={**x,'elementos':[v for v in x['elementos'] if v in sel.get('elementos',[])]}
            if not x['elementos']:continue
        used.append(x);size+=len(x['conteudo'])
    essential='\n\n'.join(f"Regras essenciais · {x['titulo']} v{x['versao']}: {x['essenciais']}" for x in essential_items)
    if len(essential)>12000:raise ValueError('Regras essenciais excedem 12.000 caracteres. Revise prioridades; nenhuma regra será descartada silenciosamente.')
    text=essential+'\n\n'+'\n\n'.join(f"## {x['titulo']} · v{x['versao']} · {x['origem']}\n[{x['tipo']} / {x['escopo']}; referência externa nunca comprova fatos]\n{x['conteudo']}" for x in used)
    snapshot_items=used+[x for x in essential_items if x['id'] not in {v['id'] for v in used}]
    return dict(items=used,disponiveis=available,selecao=sel,conflitos=conflicts,pendencias=pending,limite=32000,texto=text,snapshot=[{k:x[k] for k in ('id','versao','sha256','tipo','origem')} for x in snapshot_items],perfil=PROFILES.get(sel['perfil']))


def exported(company,project=''):
    resolved=resolve(company,project)
    snapshot={k:resolved[k] for k in ('items','conflitos','pendencias','limite','snapshot','perfil')}
    snapshot['items']=[{k:v for k,v in x.items() if k!='original'} for x in resolved['items']]
    files={'contexto.md':'# Contexto selecionado\n\n'+resolved['texto'],'contexto-usado.json':json.dumps(snapshot,ensure_ascii=False,indent=2)}
    for x in resolved['items']:
        if x['tipo']=='skill':files[f"skills/{x['id']}/SKILL.md"]=f"---\nname: edy-{x['id']}\ndescription: {json.dumps(x['titulo'],ensure_ascii=False)}\n---\n\n{x['conteudo']}\n"
    files['perfil-visual.json']=json.dumps(resolved['perfil'] or {'nome':'Identidade personalizada da composição'},ensure_ascii=False,indent=2)
    return files,resolved


def visual_assets(company,project=''):
    """Screenshots/imagens revisadas: referência visual, nunca foto da empresa."""
    from PIL import Image
    out=[]
    for x in resolve(company,project)['items']:
        meta=x.get('original',{})
        if x['tipo']!='referencia' or not meta or Path(meta['arquivo']).suffix.lower() not in ('.png','.jpg','.jpeg','.webp'):continue
        path=store.arquivo_seguro('biblioteca',meta['arquivo'])
        if path.stat().st_size>3_000_000:continue
        raw=path.read_bytes()
        if hashlib.sha256(raw).hexdigest()!=meta['sha256']:raise ValueError('Referência original mudou. Reimporte antes de exportar.')
        with Image.open(io.BytesIO(raw)) as image:
            if image.width*image.height>16_000_000:continue
            image.verify()
        out.append(dict(arquivo='referencias/'+x['id']+Path(path).suffix,sha256=meta['sha256'],bytes=len(raw),titulo=x['titulo'],origem=x['origem'],uso='referencia_visual_apenas',path=path))
        if len(out)>=4:break
    return out


def import_file(file, fields, *, text_limit=8_000_000):
    if not file:raise ValueError('Selecione um arquivo.')
    suffix=Path(file.filename).suffix.lower()
    if suffix not in ('.html','.htm','.md','.txt','.json','.png','.jpg','.jpeg','.webp','.pdf'):raise ValueError('Use HTML, Markdown, texto, JSON, PDF ou imagem.')
    limit=8_000_000 if suffix in ('.html','.htm') else min(text_limit,8_000_000)
    raw=file.read(limit+1)
    if not raw or len(raw)>limit:raise ValueError('Arquivo vazio ou acima do limite: '+str(limit)+' bytes.')
    content=fields.get('conteudo','');analysis=None
    if suffix in ('.html','.htm'):
        from ed_html_reference import analyze,describe
        analysis=analyze(raw);content=(content+'\n\n'+describe(analysis)).strip()
    elif suffix in ('.md','.txt','.json'):
        try:content=content or raw.decode('utf-8-sig',errors='strict')
        except UnicodeError:raise ValueError('Arquivo de texto deve usar UTF-8.') from None
    else:content=content or 'Referência anexada; análise e direitos pendentes. Não reutilizar como registro real de outra empresa.'
    elements=fields.get('elementos','composicao,tipografia,movimento')
    if isinstance(elements,str):elements=[x.strip() for x in elements.split(',')]
    data={**fields,'estado':'inativo','conteudo':content,'tipo':fields.get('tipo','referencia'),'elementos':elements}
    x=save(data);name=x['id']+suffix;root=store.pasta()/'biblioteca';root.mkdir(exist_ok=True);(root/name).write_bytes(raw)
    x['original']=dict(arquivo=name,nome=Path(file.filename).name,sha256=hashlib.sha256(raw).hexdigest(),url='/api/ed/biblioteca/'+x['id']+'/original')
    if analysis:x['analise_html']=analysis
    with store.conectar() as con:con.execute('UPDATE ed_biblioteca SET dados=? WHERE id=? AND versao=1',(json.dumps(x,ensure_ascii=False),x['id']))
    return x


def registrar(bp):
    @bp.get('/biblioteca')
    def listing():
        query=request.args.get('q','').casefold();kind=request.args.get('tipo','')
        out=[x for x in items() if (not kind or kind==x['tipo']) and query in (x['titulo']+' '+x['conteudo']).casefold()]
        return jsonify(items=out,total=len(out))
    @bp.post('/biblioteca')
    def create():return jsonify(save(request.get_json())),201
    @bp.get('/biblioteca/<ident>')
    def detail(ident):return jsonify(get(ident))
    @bp.put('/biblioteca/<ident>')
    def update(ident):return jsonify(save(request.get_json(),ident))
    @bp.get('/biblioteca/<ident>/versoes')
    def versions(ident):
        get(ident)
        with store.conectar() as con:rows=con.execute('SELECT dados FROM ed_biblioteca WHERE id=? ORDER BY versao DESC',(ident,)).fetchall()
        return jsonify([json.loads(r['dados']) for r in rows])
    @bp.get('/biblioteca/<ident>/original')
    def original(ident):
        x=get(ident);meta=x.get('original')
        if not meta:raise LookupError('Original ausente.')
        return send_file(store.pasta()/'biblioteca'/meta['arquivo'],as_attachment=True,download_name=meta['nome'])
    @bp.get('/biblioteca/<ident>/markdown')
    def markdown(ident):
        x=get(ident)
        # Frontmatter JSON scalars são válidos em YAML; não interpolar títulos como YAML cru.
        header=('---\nname: edy-'+x['id']+'\ndescription: '+json.dumps(x['titulo'],ensure_ascii=False)+'\n---\n\n') if x['tipo']=='skill' else '# '+x['titulo']+'\n\n'
        content=header+x['conteudo']+'\n\n<!-- ID '+x['id']+' · v'+str(x['versao'])+' · SHA256 '+x['sha256']+' -->\n'
        return send_file(io.BytesIO(content.encode()),as_attachment=True,download_name='SKILL.md' if x['tipo']=='skill' else x['id']+'.md',mimetype='text/markdown')
    @bp.post('/biblioteca/importar')
    def importing():return jsonify(import_file(request.files.get('arquivo'),dict(request.form))),201
    @bp.get('/perfis-estilo')
    def profiles():return jsonify(PROFILES)
    @bp.get('/empresas/<company>/contexto')
    def context(company):return jsonify(resolve(company,request.args.get('projeto_id','')))
    @bp.put('/empresas/<company>/contexto')
    def choose(company):
        lead=store.ler_empresa(company);data=request.get_json()
        if not isinstance(data,dict) or set(data)-{'selecionados','perfil','elementos'}:raise ValueError('Seleção inválida.')
        out={**selection(company),**data};ids=out['selecionados']
        if ids is not None and (not isinstance(ids,list) or len(ids)>100 or any(not isinstance(x,str) for x in ids)):raise ValueError('Seleção inválida.')
        allowed={x['id'] for x in items() if eligible(x,lead)}
        if ids is not None and set(ids)-allowed:raise ValueError('Item inativo ou pertencente a outro escopo/empresa.')
        if out['perfil'] not in ('',*PROFILES):raise ValueError('Perfil inválido.')
        if not isinstance(out['elementos'],list) or set(out['elementos'])-{'composicao','tipografia','movimento','fotografia','copy','componentes'}:raise ValueError('Elementos inválidos.')
        with store.conectar() as con:con.execute('INSERT INTO ed_config VALUES (?,?) ON CONFLICT(chave) DO UPDATE SET valor=excluded.valor',('biblioteca:'+company,json.dumps(out)))
        return jsonify(resolve(company))
