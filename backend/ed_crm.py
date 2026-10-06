"""Domínio comercial: registros reais, versões, funil, CSV e união recuperável."""
import csv
import hashlib
import io
import json
from datetime import datetime
from flask import jsonify,request,g,send_file
from werkzeug.exceptions import Conflict
import ed_store as store

FIELDS={
 'contato':{'nome','cargo','telefone','email','observacoes'},
 'oportunidade':{'titulo','fase','responsavel','prioridade','origem','tags','valor','motivo','pacote_id','previa_id'},
 'tarefa':{'titulo','vencimento','responsavel','prioridade','concluida','observacoes'},
 'atividade':{'tipo_atividade','texto','proximo_contato','canal'},
 'lista':{'titulo','empresa_ids','objetivo','estado_lista'},
 'visao':{'titulo','filtros'},
}
STAGES=[dict(id=k,nome=v) for k,v in [('novo','Nova oportunidade'),('qualificado','Qualificada'),('proposta','Proposta preparada'),('negociacao','Em conversa'),('ganho','Ganha'),('perdido','Perdida')]]


def setup():
    with store.conectar() as con:con.executescript('''
      CREATE TABLE IF NOT EXISTS ed_crm_registros(id TEXT PRIMARY KEY,tipo TEXT NOT NULL,empresa_id TEXT REFERENCES ed_empresas(id),versao INTEGER NOT NULL,dados TEXT NOT NULL);
      CREATE TABLE IF NOT EXISTS ed_crm_versoes(id TEXT,versao INTEGER,dados TEXT NOT NULL,PRIMARY KEY(id,versao));
      CREATE INDEX IF NOT EXISTS ed_crm_empresa ON ed_crm_registros(empresa_id,tipo);
      CREATE TABLE IF NOT EXISTS ed_crm_unioes(id TEXT PRIMARY KEY,dados TEXT NOT NULL);''')


def config():
    with store.conectar() as con:row=con.execute("SELECT valor FROM ed_config WHERE chave='crm:funil'").fetchone()
    return json.loads(row['valor']) if row else STAGES


def list_records(kind=None,company=None,archived=False):
    with store.conectar() as con:
        rows=con.execute('SELECT dados FROM ed_crm_registros WHERE (? IS NULL OR tipo=?) AND (? IS NULL OR empresa_id=?) ORDER BY rowid DESC',(kind,kind,company,company)).fetchall()
    return [x for r in rows if (x:=json.loads(r['dados'])) and (archived or x['estado']!='arquivado')]


def get(ident):
    with store.conectar() as con:row=con.execute('SELECT dados FROM ed_crm_registros WHERE id=?',(ident,)).fetchone()
    if not row:raise LookupError('Registro não encontrado neste workspace.')
    return json.loads(row['dados'])


def save(kind,data,ident=None,idempotency_key=None):
    if kind not in FIELDS or not isinstance(data,dict):raise ValueError('Tipo de registro inválido.')
    if idempotency_key:
        with store.conectar() as con:prior=con.execute('SELECT valor FROM ed_config WHERE chave=?',('crm-efeito:'+idempotency_key,)).fetchone()
        if prior:return get(prior['valor'])
    old=get(ident) if ident else None
    if old and old['tipo']!=kind:raise ValueError('Tipo não corresponde ao registro.')
    if set(data)-FIELDS[kind]-{'id','tipo','empresa_id','versao','estado','criado_em','atualizado_em','autor'}:raise ValueError('Campos desconhecidos.')
    if old and data.get('versao')!=old['versao']:raise Conflict('Registro mudou. Recarregue antes de salvar.')
    values={**(old or {}),**data};company=values.get('empresa_id') or None
    lead=store.ler_empresa(company) if company else None
    if kind in ('contato','oportunidade') and not lead:raise ValueError('Associe uma empresa.')
    result={}
    for key in FIELDS[kind]:
        value=values.get(key,[] if key in ('tags','empresa_ids') else {} if key=='filtros' else False if key=='concluida' else '')
        if key in ('tags','empresa_ids'):
            if not isinstance(value,list) or len(value)>200:raise ValueError('Lista inválida.')
            result[key]=list(dict.fromkeys(store.texto(v,120) for v in value))
            if key=='empresa_ids':
                for company_id in result[key]:store.ler_empresa(company_id)
        elif key=='filtros':
            if not isinstance(value,dict) or set(value)-{'q','nicho','cidade','etapa','site','tags'}:raise ValueError('Filtros inválidos.')
            result[key]={k:store.texto(v,200) for k,v in value.items()}
        elif key=='concluida':result[key]=store.booleano(value)
        else:result[key]=store.texto(value,4000 if key in ('texto','observacoes','motivo') else 500)
    required='nome' if kind=='contato' else 'texto' if kind=='atividade' else 'titulo'
    if not result[required]:raise ValueError('Informe '+required+'.')
    if kind=='oportunidade':
        result['fase']=result['fase'] or config()[0]['id']
        if result['fase'] not in {s['id'] for s in config()}:raise ValueError('Fase inexistente no funil.')
        if result['fase'] in ('ganho','perdido') and not result['motivo']:raise ValueError('Informe o motivo do ganho/perda.')
        for key,records in [('pacote_id',lead['exportacoes']),('previa_id',lead['previas'])]:
            if result[key] and not any(x.get('id')==result[key] for x in records):raise ValueError('Associação de '+key+' não pertence à empresa.')
    if kind in ('oportunidade','tarefa'):
        result['prioridade']=result['prioridade'] or 'normal'
        if result['prioridade'] not in ('baixa','normal','alta'):raise ValueError('Prioridade inválida.')
    for key in ('vencimento','proximo_contato'):
        if result.get(key):
            try:datetime.fromisoformat(result[key])
            except ValueError:raise ValueError('Data inválida: '+key) from None
    state=values.get('estado','ativo')
    if state not in ('ativo','arquivado'):raise ValueError('Estado inválido.')
    if kind=='oportunidade' and state=='arquivado' and not result['motivo']:raise ValueError('Informe o motivo do arquivamento da oportunidade.')
    result.update(id=ident or store.novo_id(),tipo=kind,empresa_id=company,versao=old['versao']+1 if old else 1,estado=state,criado_em=old['criado_em'] if old else store.agora(),atualizado_em=store.agora(),autor=getattr(g,'actor',{}).get('id','local'))
    with store.conectar() as con:
        con.execute('BEGIN IMMEDIATE')
        if idempotency_key:
            prior=con.execute('SELECT valor FROM ed_config WHERE chave=?',('crm-efeito:'+idempotency_key,)).fetchone()
            if prior:return json.loads(con.execute('SELECT dados FROM ed_crm_registros WHERE id=?',(prior['valor'],)).fetchone()[0])
        if old and con.execute('SELECT versao FROM ed_crm_registros WHERE id=?',(ident,)).fetchone()[0]!=old['versao']:raise Conflict('Atualização concorrente.')
        raw=json.dumps(result,ensure_ascii=False)
        con.execute('INSERT INTO ed_crm_registros VALUES (?,?,?,?,?) ON CONFLICT(id) DO UPDATE SET empresa_id=excluded.empresa_id,versao=excluded.versao,dados=excluded.dados',(result['id'],kind,company,result['versao'],raw))
        con.execute('INSERT INTO ed_crm_versoes VALUES (?,?,?)',(result['id'],result['versao'],raw))
        if idempotency_key:con.execute('INSERT INTO ed_config VALUES (?,?)',('crm-efeito:'+idempotency_key,result['id']))
    return result


def activity(company,text,channel='interno',kind='nota'):
    return save('atividade',dict(empresa_id=company,texto=text,canal=channel,tipo_atividade=kind))


def summary():
    leads=[x for x in store.listar_empresas() if not x.get('crm_arquivada')];opps=list_records('oportunidade');tasks=list_records('tarefa');now=store.agora()
    return dict(empresas=len(leads),reais=sum(not x['demonstracao'] for x in leads),demonstracoes=sum(x['demonstracao'] for x in leads),oportunidades=len(opps),fases=[dict(**s,total=sum(x['fase']==s['id'] for x in opps)) for s in config()],tarefas_abertas=sum(not t['concluida'] for t in tasks),vencidas=sum(bool(not t['concluida'] and t['vencimento'] and t['vencimento'][:10]<now[:10]) for t in tasks),pacotes=sum(x['total_exportacoes'] for x in leads),previas=sum(x['total_previas'] for x in leads),fonte='Registros do workspace atual; não são estimativas de vendas.')


def merge(source,target,choices,revision):
    if source==target:raise ValueError('Escolha empresas diferentes.')
    a,b=store.ler_empresa(source),store.ler_empresa(target)
    if b['atualizado_em']!=revision:raise Conflict('Empresa de destino mudou. Revise a união novamente.')
    if not isinstance(choices,list) or set(choices)-set(store.CAMPOS):raise ValueError('Escolha somente campos comerciais existentes.')
    changes={k:a[k] for k in store.CAMPOS if (not b[k] or k in choices) and a[k]}
    ident=store.novo_id()
    with store.conectar() as con:
        con.execute('BEGIN IMMEDIATE')
        rows=con.execute('SELECT id,dados FROM ed_empresas WHERE id IN (?,?)',(source,target)).fetchall()
        before={r['id']:json.loads(r['dados']) for r in rows}
        actual=con.execute('SELECT atualizado_em FROM ed_empresas WHERE id=?',(target,)).fetchone()[0]
        if actual!=revision:raise Conflict('Empresa alterada durante a revisão. Confira os conflitos novamente.')
        updated=before[target].copy();updated.update(changes)
        updated['fontes']={**updated['fontes'],**{k:a['fontes'][k] for k in changes if k in a['fontes']}}
        updated['crm_historicos_relacionados']=list(dict.fromkeys(updated.get('crm_historicos_relacionados',[])+[source]))
        previous={**before[source],'crm_unida_em':target,'crm_arquivada':True}
        records=con.execute('SELECT id,dados FROM ed_crm_registros WHERE empresa_id=?',(source,)).fetchall()
        snapshot=dict(id=ident,origem=source,destino=target,antes=before,depois={target:updated,source:previous},registros=[dict(r) for r in records],criado_em=store.agora(),estado='aplicada',valores_aplicados=changes)
        con.execute('UPDATE ed_empresas SET dados=?,atualizado_em=? WHERE id=?',(json.dumps(updated,ensure_ascii=False),store.agora(),target))
        con.execute('UPDATE ed_empresas SET dados=? WHERE id=?',(json.dumps(previous,ensure_ascii=False),source))
        for record in records:
            value=json.loads(record['dados']);value['empresa_id']=target
            con.execute('UPDATE ed_crm_registros SET empresa_id=?,dados=? WHERE id=?',(target,json.dumps(value),record['id']))
        con.execute('INSERT INTO ed_crm_unioes VALUES (?,?)',(ident,json.dumps(snapshot,ensure_ascii=False)))
    return dict(id=ident,origem=source,destino=target,estado='aplicada',mensagem='União aplicada; histórico, materiais e pacotes antigos permanecem na ficha de origem vinculada. Restauração disponível.')


def registrar(bp):
    @bp.get('/crm/resumo',endpoint='crm_dashboard')
    def dashboard():return jsonify(summary())
    @bp.get('/crm/funil',endpoint='crm_pipeline')
    def pipeline():return jsonify(config())
    @bp.put('/crm/funil',endpoint='crm_change_pipeline')
    def change_pipeline():
        data=request.get_json()
        if not isinstance(data,list) or not 2<=len(data)<=12 or any(not isinstance(s,dict) or set(s)!={'id','nome'} for s in data):raise ValueError('Funil requer 2 a 12 fases com id/nome.')
        out=[dict(id=store.texto(s['id'],50),nome=store.texto(s['nome'],80)) for s in data]
        if any(not s['id'] or not s['nome'] for s in out) or len({s['id'] for s in out})!=len(out):raise ValueError('Fases vazias ou repetidas.')
        if {x['fase'] for x in list_records('oportunidade')}-{s['id'] for s in out}:raise ValueError('Não remova fases com oportunidades. Mova os registros primeiro.')
        with store.conectar() as con:con.execute('INSERT INTO ed_config VALUES (?,?) ON CONFLICT(chave) DO UPDATE SET valor=excluded.valor',('crm:funil',json.dumps(out)))
        return jsonify(out)
    @bp.get('/crm/registros/<kind>',endpoint='crm_listing')
    def listing(kind):
        if kind not in FIELDS:raise LookupError('Tipo não encontrado.')
        company=request.args.get('empresa_id')
        if company:store.ler_empresa(company)
        values=list_records(kind,company,request.args.get('arquivados')=='true')
        q=request.args.get('q','').casefold();values=[x for x in values if q in json.dumps(x,ensure_ascii=False).casefold()]
        page=int(request.args.get('pagina','1'));limit=int(request.args.get('limite','100'))
        if not 1<=limit<=200 or page<1:raise ValueError('Paginação inválida.')
        return jsonify(items=values[(page-1)*limit:page*limit],total=len(values),pagina=page,limite=limit)
    @bp.post('/crm/registros/<kind>',endpoint='crm_create')
    def create(kind):return jsonify(save(kind,request.get_json())),201
    @bp.put('/crm/registros/<kind>/<ident>',endpoint='crm_update')
    def update(kind,ident):return jsonify(save(kind,request.get_json(),ident))
    @bp.get('/crm/registros/<kind>/<ident>/versoes',endpoint='crm_versions')
    def versions(kind,ident):
        if get(ident)['tipo']!=kind:raise LookupError('Tipo incompatível.')
        with store.conectar() as con:rows=con.execute('SELECT dados FROM ed_crm_versoes WHERE id=? ORDER BY versao DESC',(ident,)).fetchall()
        return jsonify([json.loads(r['dados']) for r in rows])
    @bp.get('/crm/csv',endpoint='crm_export_csv')
    def export_csv():
        out=io.StringIO(newline='');writer=csv.DictWriter(out,fieldnames=store.CAMPOS);writer.writeheader()
        for lead in store.listar_empresas():writer.writerow({k:"'"+lead[k] if lead[k].startswith(('=','+','-','@')) else lead[k] for k in store.CAMPOS})
        return send_file(io.BytesIO(('\ufeff'+out.getvalue()).encode()),as_attachment=True,download_name='empresas-edy.csv',mimetype='text/csv')
    @bp.post('/crm/csv/validar',endpoint='crm_validate_csv')
    def validate_csv():
        file=request.files.get('arquivo')
        if not file:raise ValueError('Selecione CSV UTF-8.')
        raw=file.read(2_000_001)
        if len(raw)>2_000_000:raise ValueError('CSV excede 2 MB.')
        try:
            text=raw.decode('utf-8-sig');dialect=csv.Sniffer().sniff(text[:4096],delimiters=',;');reader=csv.DictReader(io.StringIO(text),dialect=dialect)
        except (UnicodeError,csv.Error):raise ValueError('CSV inválido. Use UTF-8 e separador vírgula/ponto e vírgula.') from None
        if not reader.fieldnames or len(reader.fieldnames)>50 or len(set(reader.fieldnames))!=len(reader.fieldnames):raise ValueError('Cabeçalhos ausentes, repetidos ou acima de 50 colunas.')
        if request.form.get('analisar')=='true':
            return jsonify(cabecalhos=reader.fieldnames,campos=list(store.CAMPOS))
        mapping=request.form.get('mapeamento')
        if mapping:
            try:mapping=json.loads(mapping)
            except (ValueError,TypeError):raise ValueError('Mapeamento inválido.') from None
            if not isinstance(mapping,dict) or set(mapping)-set(reader.fieldnames) or any(v not in (*store.CAMPOS,'') for v in mapping.values()):raise ValueError('Mapeamento inválido.')
            destinations=[v for v in mapping.values() if v]
            if len(set(destinations))!=len(destinations):raise ValueError('Cada campo deve receber somente uma coluna.')
        else:mapping={k:k for k in reader.fieldnames}
        if 'nome' not in mapping.values():raise ValueError('Cabeçalho nome obrigatório. Associe uma coluna ao nome da empresa.')
        rows=[]
        for i,row in enumerate(reader,2):
            if len(rows)>=500:raise ValueError('Limite de 500 linhas por importação.')
            unknown={mapping.get(k,k) for k in row if mapping.get(k,k) and mapping.get(k,k) not in store.CAMPOS}
            data={mapping[k]:v or '' for k,v in row.items() if mapping.get(k) in store.CAMPOS}
            try:store.validar_dados(data);error='Colunas desconhecidas: '+', '.join(str(k) for k in unknown) if unknown else ''
            except ValueError as exc:error=str(exc)
            rows.append(dict(linha=i,dados=data,erro=error))
        key=hashlib.sha256(raw+(json.dumps(mapping,sort_keys=True).encode() if request.form.get('mapeamento') else b'')).hexdigest()
        with store.conectar() as con:con.execute('INSERT INTO ed_config VALUES (?,?) ON CONFLICT(chave) DO UPDATE SET valor=excluded.valor',('csv:'+key,json.dumps(rows,ensure_ascii=False)))
        return jsonify(id=key,linhas=rows,validas=sum(not x['erro'] for x in rows))
    @bp.post('/crm/csv/importar',endpoint='crm_import_csv')
    def import_csv():
        data=request.get_json();key=store.texto(data.get('id',''),64);chosen=data.get('linhas')
        if not isinstance(chosen,list) or any(type(x)!=int for x in chosen) or len(chosen)>500:raise ValueError('Escolha linhas válidas.')
        with store.conectar() as con:row=con.execute('SELECT valor FROM ed_config WHERE chave=?',('csv:'+key,)).fetchone()
        if not row:raise LookupError('Valide este CSV primeiro.')
        rows=json.loads(row['valor']);result=[];selected=[]
        for line in sorted(set(chosen)):
            row=next((x for x in rows if x['linha']==line),None)
            if not row or row['erro']:raise ValueError('Linha inválida: '+str(line))
            selected.append(row)
        for row in selected:
            line=row['linha']
            lead,new=store.gravar_empresa(row['dados'],fonte_id='csv:'+key+':'+str(line),fornecedor='manual');result.append(dict(linha=line,id=lead['id'],novo=new))
        return jsonify(registros=result,mensagem='Dados importados como pendentes de revisão; repetição do mesmo arquivo não duplica.')
    @bp.post('/crm/unioes/avaliar',endpoint='crm_merge_preview')
    def merge_preview():
        d=request.get_json();a=store.ler_empresa(d.get('origem'));b=store.ler_empresa(d.get('destino'))
        if a['id']==b['id']:raise ValueError('Escolha duas empresas.')
        return jsonify(origem=a['id'],destino=b['id'],revisao=b['atualizado_em'],conflitos=[dict(campo=k,origem=a[k],destino=b[k]) for k in store.CAMPOS if a[k] and b[k] and a[k]!=b[k]],historicos_preservados=['materiais','exportacoes','previas','pesquisas','composicoes'])
    @bp.get('/crm/unioes',endpoint='crm_merge_history')
    def merge_history():
        with store.conectar() as con:rows=con.execute('SELECT dados FROM ed_crm_unioes ORDER BY rowid DESC LIMIT 100').fetchall()
        return jsonify([{k:x[k] for k in ('id','origem','destino','estado','criado_em')} for r in rows if (x:=json.loads(r['dados']))])
    @bp.post('/crm/unioes',endpoint='crm_unite')
    def unite():
        d=request.get_json();return jsonify(merge(d.get('origem'),d.get('destino'),d.get('preferir_origem',[]),d.get('revisao'))),201
    @bp.post('/crm/unioes/<ident>/restaurar',endpoint='crm_restore_merge')
    def restore_merge(ident):
        with store.conectar() as con:
            row=con.execute('SELECT dados FROM ed_crm_unioes WHERE id=?',(ident,)).fetchone()
            if not row:raise LookupError('União inexistente.')
            snapshot=json.loads(row['dados'])
            if snapshot['estado']!='aplicada':raise Conflict('União já restaurada.')
            for uid,expected in snapshot['depois'].items():
                current=json.loads(con.execute('SELECT dados FROM ed_empresas WHERE id=?',(uid,)).fetchone()[0])
                if current!=expected:raise Conflict('Empresa editada após união; restauração automática bloqueada para preservar correções.')
            for record in snapshot['registros']:
                expected={**json.loads(record['dados']),'empresa_id':snapshot['destino']}
                row=con.execute('SELECT dados FROM ed_crm_registros WHERE id=?',(record['id'],)).fetchone()
                if not row or json.loads(row['dados'])!=expected:raise Conflict('Registro comercial editado após união; revise manualmente antes de restaurar.')
            for uid,value in snapshot['antes'].items():con.execute('UPDATE ed_empresas SET dados=?,atualizado_em=? WHERE id=?',(json.dumps(value),store.agora(),uid))
            for record in snapshot['registros']:
                value=json.loads(record['dados']);con.execute('UPDATE ed_crm_registros SET empresa_id=?,dados=? WHERE id=?',(value['empresa_id'],record['dados'],record['id']))
            snapshot['estado']='restaurada';con.execute('UPDATE ed_crm_unioes SET dados=? WHERE id=?',(json.dumps(snapshot),ident))
        return jsonify(mensagem='União restaurada; registros originais recuperados.')
