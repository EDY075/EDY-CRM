"""Contrato de montagem versionado. Templates renderizados, nunca IA simulada."""
import copy
import json
import re
from flask import jsonify,request
import ed_store as store
from ed_services import lock

TYPES=('landing','site','dashboard','admin')
LAYOUTS=('editorial','imersiva','mosaico','compacta')
KINDS=('hero','apresentacao','servicos','produtos','galeria','equipe','processo','faq','prova','contato','cta','rodape','dados','operacoes')
MOTION={'titulos':('nenhum','suave','escalonado'),'transicoes':('nenhuma','revelar'),'imagens':('nenhuma','zoom'),
        'cartoes':('nenhuma','elevar'),'botoes':('nenhuma','deslocar'),'cursor':('nenhum','halo'),'parallax':('desligado','leve'),'shader':('desligado','gradiente')}


def alternativas(title,text,reviewed=False):
    return [dict(id=letter,layout=layout,titulo=title,texto=text,cta='Entrar em contato',material_id='',desktop=[50,50],mobile=[50,50],
                 revisado=reviewed,instrucoes='',origem='template_local',versao=1) for letter,layout in zip('abcd',LAYOUTS)]


def defaults(company):
    import ed_preparation
    lead=store.ler_empresa(company); p=ed_preparation.ler(company)
    palette=re.findall(r'#[0-9a-fA-F]{6}',p['design'].get('paleta',''))
    sections=[]
    for i,s in enumerate(p['secoes']):
        kind='hero' if i==0 else ('contato' if 'contato' in store.normalizar(s['titulo']) or 'localizacao' in store.normalizar(s['titulo']) else 'servicos')
        sections.append(dict(id=s['id'],tipo=kind,escolhida='a',fixada=False,alternativas=alternativas(s['titulo'],s['texto'],s['revisado'])))
    if not sections: sections=[dict(id='hero',tipo='hero',escolhida='a',fixada=False,alternativas=alternativas(lead['nome'],''))]
    return dict(schema=1,revisao=0,tipo='site' if p.get('modo')=='completo' else 'landing',requisitos={k:'' for k in ('paginas','navegacao','funcionalidades','dados','autenticacao','permissoes','operacoes')},
        identidade=dict(fundo=palette[1] if len(palette)>1 else '#f6f0e6',tinta=palette[0] if palette else '#2e281e',acento=palette[-1] if palette else '#8c502f',fonte='moderna' if any(x in store.normalizar(lead['nicho']) for x in ('clin','saude','academ','fitness')) else 'editorial'),
        movimento={k:v[0] for k,v in MOTION.items()},referencias=[],aprovacao_titular=dict(estado='pendente',evidencia=''),secoes=sections)


def ler(company):
    store.ler_empresa(company)
    with store.conectar() as con: row=con.execute('SELECT valor FROM ed_config WHERE chave=?',('composicao:'+company,)).fetchone()
    return json.loads(row['valor']) if row else defaults(company)


def validar(data,lead):
    model=defaults(lead['id'])
    if not isinstance(data,dict) or set(data)!=set(model) or data['schema']!=1 or type(data['revisao'])!=int or data['revisao']<0 or data['tipo'] not in TYPES:
        raise ValueError('Contrato de composição inválido. Use o schema 1 exportado pelo estúdio.')
    out=copy.deepcopy(data)
    if not isinstance(out['requisitos'],dict) or set(out['requisitos'])!=set(model['requisitos']): raise ValueError('Requisitos inválidos.')
    out['requisitos']={k:store.texto(v,4000) for k,v in out['requisitos'].items()}
    identity=out['identidade']
    if not isinstance(identity,dict) or set(identity)!=set(model['identidade']): raise ValueError('Identidade inválida.')
    for key in ('fundo','tinta','acento'):
        if not isinstance(identity[key],str) or not re.fullmatch(r'#[0-9a-fA-F]{6}',identity[key]): raise ValueError('Use cores hexadecimais com seis dígitos.')
    if identity['fonte'] not in ('editorial','moderna'): raise ValueError('Fonte inválida.')
    if not isinstance(out['movimento'],dict) or set(out['movimento'])!=set(MOTION) or any(v not in MOTION[k] for k,v in out['movimento'].items()): raise ValueError('Direção de movimento inválida.')
    approval=out['aprovacao_titular']
    if not isinstance(approval,dict) or set(approval)!={'estado','evidencia'} or approval['estado'] not in ('pendente','aprovado'): raise ValueError('Aprovação inválida.')
    approval['evidencia']=store.texto(approval['evidencia'],2000)
    if approval['estado']=='aprovado' and len(approval['evidencia'])<15: raise ValueError('Registre evidência da aprovação pelo titular.')
    materials={x['id'] for x in lead['materiais']}
    if not isinstance(out['referencias'],list) or len(out['referencias'])>30: raise ValueError('Até trinta referências.')
    for ref in out['referencias']:
        if not isinstance(ref,dict) or set(ref)!={'url','material_id','nicho','secoes','elementos','observacoes'}: raise ValueError('Referência inválida.')
        ref['url']=store.url(ref['url'])
        if ref['material_id'] and ref['material_id'] not in materials: raise ValueError('Screenshot pertence a outro estabelecimento ou está ausente.')
        for key in ('nicho','secoes','elementos','observacoes'): ref[key]=store.texto(ref[key],2000)
    if not isinstance(out['secoes'],list) or not 1<=len(out['secoes'])<=30: raise ValueError('Use entre uma e trinta seções.')
    ids=set()
    for section in out['secoes']:
        if not isinstance(section,dict) or set(section)!={'id','tipo','escolhida','fixada','alternativas'}: raise ValueError('Seção inválida.')
        sid=section['id']
        if not isinstance(sid,str) or not re.fullmatch(r'[a-zA-Z0-9_-]{1,80}',sid) or sid in ids: raise ValueError('ID de seção inválido ou repetido.')
        ids.add(sid)
        if section['tipo'] not in KINDS or section['escolhida'] not in 'abcd' or len(section['escolhida'])!=1: raise ValueError('Tipo ou escolha inválida.')
        store.booleano(section['fixada'])
        alts=section['alternativas']
        if not isinstance(alts,list) or len(alts)!=4 or {a.get('id') for a in alts if isinstance(a,dict)}!=set('abcd'): raise ValueError('Cada seção precisa de quatro alternativas a, b, c e d.')
        for alt in alts:
            if set(alt)!=set(alternativas('','')[0]) or alt['layout'] not in LAYOUTS: raise ValueError('Alternativa inválida. Importe o contrato estruturado, sem código executável.')
            for key in ('titulo','texto','cta','instrucoes','origem'): alt[key]=store.texto(alt[key],4000 if key in ('texto','instrucoes') else 300)
            if alt['material_id'] and alt['material_id'] not in materials: raise ValueError('Imagem pertence a outra empresa ou está ausente.')
            for key in ('desktop','mobile'):
                pos=alt[key]
                if not isinstance(pos,list) or len(pos)!=2 or any(type(n) not in (float,int) or not 0<=n<=100 for n in pos): raise ValueError('Enquadramento deve ficar entre 0 e 100%.')
            store.booleano(alt['revisado'])
            if type(alt['versao'])!=int or not 1<=alt['versao']<=10000: raise ValueError('Versão de alternativa inválida.')
    return out


def salvar(company,data):
    lead=store.ler_empresa(company); out=validar(data,lead)
    with lock,store.conectar() as con:
        row=con.execute('SELECT valor FROM ed_config WHERE chave=?',('composicao:'+company,)).fetchone()
        before=json.loads(row['valor']) if row else defaults(company)
        if before['revisao']!=out['revisao']: return None
        for section in before['secoes']:
            match=next((s for s in out['secoes'] if s['id']==section['id']),None)
            if section['fixada'] and (not match or (match['fixada'] and match!=section)):
                raise ValueError('Desfixe a seção antes de alterar ou remover a escolha.')
        out['revisao']+=1
        con.execute('INSERT INTO ed_config VALUES (?,?) ON CONFLICT(chave) DO UPDATE SET valor=excluded.valor',('composicao:'+company,json.dumps(out,ensure_ascii=False)))
        con.execute('INSERT INTO ed_config VALUES (?,?)',('composicao-historico:'+company+':'+store.novo_id(),json.dumps(dict(criado_em=store.agora(),composicao=out),ensure_ascii=False)))
    return out


def registrar(bp):
    @bp.post('/empresas/<company>/composicao/validar')
    def composition_validate(company): return jsonify(validar(request.get_json(),store.ler_empresa(company)))

    @bp.get('/empresas/<company>/composicao')
    def composition_get(company): return jsonify(ler(company))

    @bp.put('/empresas/<company>/composicao')
    def composition_put(company):
        result=salvar(company,request.get_json())
        if result is None: return jsonify(erro='Composição mudou em outra janela. Recarregue; suas edições locais continuam no formulário.'),409
        return jsonify(result)

    @bp.get('/empresas/<company>/composicao/historico')
    def composition_history(company):
        store.ler_empresa(company)
        with store.conectar() as con:
            rows=con.execute('SELECT valor FROM ed_config WHERE chave LIKE ? ORDER BY rowid DESC',('composicao-historico:'+company+':%',)).fetchall()
        return jsonify([json.loads(r['valor']) for r in rows])
