from ed_workspace import submit
"""Central local: configuração pública, diagnóstico real e tarefas canceláveis."""
import hashlib
import json
from contextlib import nullcontext
from concurrent.futures import ThreadPoolExecutor
from threading import RLock
from flask import current_app, jsonify, request, has_app_context
import ed_store as store
import ed_secrets
from ed_connectors import ADAPTERS

pool = ThreadPoolExecutor(max_workers=2, thread_name_prefix='ed-provider')
lock = RLock()
CATALOG = {
 'voz':dict(nome='Voz · OpenAI API',finalidade='Transcrição e resposta falada',recursos=['Transcrição em português para revisar antes de executar','Síntese opcional de resposta com silenciar/interromper'],configuracao='ED_CRM_VOICE_KEY ou chave própria no cofre local; API OpenAI com saldo e modelos de áudio. Padrão: gpt-transcribe; síntese gpt-4o-mini-tts. Modelos legados configurados são preservados, com retirada anunciada para 26/02/2027.',limites='Cobrança API separada do Codex. Gravação local limitada a 60 segundos/3 MB. Teste de autenticação não comprova transcrição. Nenhum áudio enviado sem ação Transcrever.',docs='https://developers.openai.com/api/docs/guides/speech-to-text'),
 'twentyfirst':dict(nome='21st.dev MCP',finalidade='Componentes no runtime de geração',recursos=['Handshake e listagem real de ferramentas','Consulta de componentes no app-server quando configurado'],configuracao='Chave atual 21st.dev; servidor HTTP oficial. Chaves antigas Magic não são válidas.',limites='Código/componentes podem depender de plano e licença. Runtime permite busca/consulta, sem chamar geração hospedada 21st automaticamente. Credencial de imagem/Codex é independente.',docs='https://github.com/21st-dev/magic-mcp'),
 'apify':dict(nome='Apify · Instagram público',finalidade='Descoberta e materiais públicos',recursos=['Pesquisar candidatos por nome/localização','Perfil, bio, links, posts e carrosséis','Importação revisada sem substituir a ficha'],configuracao='Token Apify, saldo e condições do Actor apify/instagram-scraper.',limites='Público não significa uso autorizado. Execuções têm teto e prazo; preços variam por plano e evento. Meta e Apify são fluxos separados.',docs='https://apify.com/apify/instagram-scraper'),
 'openai_imagens':dict(nome='OpenAI · Imagens',finalidade='Preparação de imagens',recursos=['Edição a partir do original','Máscaras e restauração de regiões protegidas','Versões e comparação antes/depois'],configuracao='Chave própria da API, saldo e modelo de imagens disponível. Padrão: gpt-image-2.5-sunburst.',limites='Cobrança separada do plano Codex. Prompt/máscara não garantem identidade perfeita; revisão visual obrigatória. O teste de modelo não é uma edição validada.',docs='https://developers.openai.com/api/docs/guides/image-generation'),
 'meta_discovery':dict(nome='Meta · Business Discovery',finalidade='Outros perfis profissionais',recursos=['Consulta de perfil profissional conhecido','Bio, website e mídia suportada, incluindo carrosséis'],configuracao='Facebook Login, token e conta Instagram profissional vinculada à Página; instagram_basic, pages_read_engagement conforme acesso/revisão.',limites='Não pesquisa todos os perfis nem acessa contas pessoais. Conta autorizada via Instagram Login não concede essas permissões. Mídia pode ser omitida por direitos/idade.',docs='https://developers.facebook.com/docs/instagram-platform/instagram-api-with-facebook-login/business-discovery'),
 'google': dict(nome='Google Places (New)', finalidade='Descoberta', recursos=['Teste autenticado com IDs de lugares'],
   configuracao='Places API New, billing, chave restrita no servidor e cotas.', limites='Uso como diretório/prospecção requer avaliação contratual. Conteúdo Places não entra no banco ou ZIP; teste não libera esse uso.', docs='https://developers.google.com/maps/documentation/places/web-service/policies'),
 'firecrawl': dict(nome='Firecrawl', finalidade='Enriquecimento', recursos=['Leitura de HTML renderizado do site confirmado', 'Até quatro páginas; sugestões sujeitas à revisão'],
   configuracao='Chave da API e créditos Firecrawl.', limites='Envia o site confirmado ao fornecedor. Respeita robots.txt; direitos de conteúdo e imagens continuam pendentes.', docs='https://docs.firecrawl.dev/api-reference/endpoint/scrape'),
 'openai': dict(nome='OpenAI', finalidade='IA opcional', recursos=['Propostas de texto por seção', 'Rascunho de prospecção; sem envio'],
   configuracao='Chave da API, saldo e ID de modelo com Structured Outputs disponível na conta.', limites='Envia apenas fatos confirmados e decisões revisadas. Saída é proposta, nunca confirmação factual. Codex e API têm autenticação e cobrança separadas.', docs='https://developers.openai.com/api/docs/guides/structured-outputs'),
 'instagram': dict(nome='Instagram / Meta', finalidade='Conta profissional autorizada', recursos=['Teste da conta autorizada','Consulta e importação revisada de fotos e carrosséis da própria conta'],
   configuracao='App Meta, token instagram_business_basic, ID de conta, versão suportada. OAuth para contas externas depende de permissões/revisão.', limites='Não faz busca universal por nicho. OAuth automático pendente; token manual é suportado. Bio, website e legendas não coletados neste fluxo. Business Discovery exige Facebook Login separado.', docs='https://developers.facebook.com/docs/instagram-platform/instagram-api-with-instagram-login/get-started'),
}


def config(provider):
    with store.conectar() as con:
        row = con.execute('SELECT valor FROM ed_config WHERE chave=?', ('integracao:' + provider,)).fetchone()
    if row:
        return json.loads(row['valor'])
    from ed_integrations import ROOT
    path = ROOT / 'config/integrations.local.json'
    data = {}
    if path.exists() and path.stat().st_size <= 16000:
        try:
            raw = json.loads(path.read_text(encoding='utf-8-sig'))
            data = raw.get('google_places' if provider == 'google' else provider, {}) if isinstance(raw, dict) else {}
            if not isinstance(data, dict):
                data = {}
        except (ValueError, OSError):
            pass
    return {k: str(data.get(k, ''))[:100] for k in ('modelo', 'account_id', 'api_version')}


def fingerprint(provider):
    if provider == 'osm':
        return hashlib.sha256(json.dumps(store.config(), sort_keys=True).encode()).hexdigest()
    return hashlib.sha256((ed_secrets.get(provider) + json.dumps(config(provider), sort_keys=True)).encode()).hexdigest()


def locais():
    with store.conectar() as con:
        rows = con.execute("SELECT chave,valor FROM ed_config WHERE chave='execucao:osm'").fetchall()
        site = con.execute('SELECT empresa_id,dados FROM ed_pesquisas ORDER BY rowid DESC LIMIT 1').fetchone()
    value = json.loads(rows[0]['valor']) if rows else {}
    osm = {k: value.get(k) for k in ('estado', 'mensagem', 'data', 'consumo')}
    if value.get('fingerprint') != fingerprint('osm'):
        osm['estado'] = 'configurado_nao_validado'
    last = json.loads(site['dados']) if site else {}
    return {'osm': osm, 'site': {k: last.get(k) for k in ('estado', 'mensagem', 'criado_em', 'fornecedor', 'empresa_id')}}


def log(provider, value):
    with store.conectar() as con:
        key='validacao:'+provider
        row=con.execute('SELECT valor FROM ed_config WHERE chave=?',(key,)).fetchone()
        verified=json.loads(row['valor']) if row else {}
        if verified.get('fingerprint')!=value.get('fingerprint'):verified={'fingerprint':value.get('fingerprint'),'operacoes':{}}
        kind=value.get('tipo_validacao')
        if kind and value.get('estado') in ('conectado','limitado'):
            verified['autenticacao']=value['data']
            if kind!='autenticacao':verified['operacoes'][kind]=value['data']
            con.execute('INSERT INTO ed_config VALUES (?,?) ON CONFLICT(chave) DO UPDATE SET valor=excluded.valor',(key,json.dumps(verified)))
        con.execute('INSERT INTO ed_config VALUES (?,?) ON CONFLICT(chave) DO UPDATE SET valor=excluded.valor',
            ('execucao:' + provider, json.dumps(value, ensure_ascii=False)))


def cards():
    if not has_app_context():
        return {}
    result = {}
    with store.conectar() as con:
        last = {row['chave'].split(':', 1)[1]: json.loads(row['valor']) for row in con.execute("SELECT chave,valor FROM ed_config WHERE chave LIKE 'execucao:%'")}
        verified={row['chave'].split(':',1)[1]:json.loads(row['valor']) for row in con.execute("SELECT chave,valor FROM ed_config WHERE chave LIKE 'validacao:%'")}
    for provider, info in CATALOG.items():
        issue = ''
        try:
            present = bool(ed_secrets.get(provider))
            matched = last.get(provider, {}).get('fingerprint') == fingerprint(provider)
        except ValueError as exc:
            present, matched, issue = False, False, str(exc)
        previous = last.get(provider, {}) if matched else {}
        proof=verified.get(provider,{}) if present and matched and verified.get(provider,{}).get('fingerprint')==last.get(provider,{}).get('fingerprint') else {}
        message=issue or previous.get('mensagem','')
        access=('acesso_insuficiente' if 'HTTP 403' in message else 'cota_limite' if 'HTTP 429' in message else 'expirado_ou_recusado' if 'HTTP 401' in message else 'erro') if issue or previous.get('estado')=='erro' else 'nao_configurado' if not present else 'limitado' if previous.get('estado')=='limitado' else 'operacao_validada' if proof.get('operacoes') else 'autenticacao_validada' if proof.get('autenticacao') else 'configurado_nao_testado'
        result[provider] = dict(**info, credencial_presente=present, config=config(provider),
            estado='erro' if issue else 'sem_credencial' if not present else previous.get('estado', 'configurado_nao_validado'),
            ultima_execucao=previous.get('data', ''), mensagem=issue or previous.get('mensagem', ''), consumo=previous.get('consumo'),
            implementacao_pendente=['OAuth automático; token manual do painel é suportado'] if provider in ('instagram','meta_discovery') else [], exportavel=provider != 'google')
        result[provider].update(id=provider,versao='1.0',operacoes=info['recursos'],testes='Teste de autenticação e ledger de operações reais; chamadas com mocks não validam o fornecedor.',erros=['autenticação','permissão','limite','rede','resposta inválida'],desconexao='Remover credencial local; variáveis do processo continuam ativas.',adaptador='implementado',status_acesso=access,autenticacao_validada_em=proof.get('autenticacao'),operacoes_validadas=proof.get('operacoes',{}),autenticacao='Chave de API no backend' if provider in ('google','openai','openai_imagens','apify','firecrawl','twentyfirst','voz') else 'Token da conta profissional autorizada',conta_projeto=config(provider).get('account_id','Projeto da chave; identificação não informada pelo fornecedor'))
    return result


def ler_job(ident):
    with store.conectar() as con:
        row = con.execute('SELECT dados FROM ed_operacoes WHERE id=?', (ident,)).fetchone()
    if not row:
        raise LookupError('Operação não encontrada.')
    return json.loads(row['dados'])


def save(job):
    with lock, store.conectar() as con:
        row = con.execute('SELECT dados FROM ed_operacoes WHERE id=?', (job['id'],)).fetchone()
        if row and json.loads(row['dados'])['estado'] in ('cancelada', 'interrompida'):
            return False
        con.execute('UPDATE ed_operacoes SET dados=? WHERE id=?', (json.dumps(job, ensure_ascii=False), job['id']))
        return True


def executar(app, ident):
    with app.app_context():
        job = ler_job(ident)
        if job['estado'] != 'na_fila':
            return
        provider = job['fornecedor']
        fp = fingerprint(provider)
        job.update(estado='pesquisando', progresso=20, mensagem='Solicitando resposta autenticada ao fornecedor.')
        if not save(job):
            return
        try:
            response = ADAPTERS[provider].test(config(provider))
            state = 'limitado' if response.get('limitado') else 'conectado'
            message, usage = response['mensagem'], response.get('consumo')
            job.update(estado='concluida', progresso=100, mensagem=message, consumo=usage)
        except Exception as exc:
            state, message, usage = 'erro', str(exc) if isinstance(exc, ValueError) else 'Falha do fornecedor; continue com os campos manuais.', None
            job.update(estado='erro', progresso=100, mensagem=message)
        # Não manter conteúdo de entrada na operação; guardar somente proposta e revisão.
        job.pop('contexto', None)
        if save(job):
            log(provider, dict(estado=state, mensagem=message, consumo=usage, data=store.agora(), fingerprint=fp,tipo_validacao='autenticacao'))


def start(provider, tipo, app, **extra):
    if provider not in ADAPTERS:
        raise LookupError('Integração não encontrada.')
    if provider != 'osm' and not ed_secrets.get(provider):
        raise ValueError('Sem credencial. Continue com templates ou configure a integração.')
    from ed_search import creation_lock, pode_iniciar
    with lock, (creation_lock if provider == 'osm' else nullcontext()), store.conectar() as con:
        if provider == 'osm':
            if not store.config()['osm_habilitado']:
                raise ValueError('Ative OpenStreetMap antes de testar a fonte.')
            pode_iniciar()
        jobs = [json.loads(r['dados']) for r in con.execute('SELECT dados FROM ed_operacoes')]
        if any(j['fornecedor'] == provider and j['estado'] in ('na_fila', 'pesquisando') for j in jobs):
            raise ValueError('Já existe uma operação deste fornecedor em andamento.')
        job = dict(id=store.novo_id(), fornecedor=provider, tipo=tipo, estado='na_fila', progresso=0,
                   mensagem='Aguardando execução; cancelamento disponível.', criado_em=store.agora(), **extra)
        # Contexto para IA permanece em memória; não guardar dados do fornecedor de descoberta.
        stored = {k: v for k, v in job.items() if k != 'contexto'}
        con.execute('INSERT INTO ed_operacoes VALUES (?,?)', (job['id'], json.dumps(stored, ensure_ascii=False)))
    if app.config['RUN_JOBS']:
        if tipo == 'ia':
            submit(pool,executar_ia, app, job)
        else:
            submit(pool,executar, app, job['id'])
        return stored
    if tipo == 'ia':
        executar_ia(app, job)
    else:
        executar(app, job['id'])
    return ler_job(job['id'])


def executar_ia(app, job):
    # Injeta contexto efêmero somente na execução, com a mesma proteção de cancelamento.
    with app.app_context():
        fp = fingerprint('openai')
        job.update(estado='pesquisando', progresso=20, mensagem='Gerando proposta de texto com fatos confirmados.')
        context = job.pop('contexto')
        if not save(job):
            return
        try:
            proposal, usage = ADAPTERS['openai'].propose(context, config('openai'))
            job.update(estado='concluida', progresso=100, proposta=proposal, consumo=usage, mensagem='Proposta para revisão; nenhuma edição foi substituída.')
            state = 'conectado'
        except Exception as exc:
            state = 'erro'
            job.update(estado='erro', progresso=100, mensagem=str(exc) if isinstance(exc, ValueError) else 'Falha ao gerar; continue pelos templates.')
        if save(job):
            log('openai', dict(estado=state, mensagem=job['mensagem'], consumo=job.get('consumo'), data=store.agora(), fingerprint=fp,tipo_validacao='proposta_texto'))


def registrar(bp):
    @bp.put('/integracoes/<provider>')
    def settings(provider):
        if provider not in CATALOG:
            raise LookupError('Integração não encontrada.')
        data = request.get_json()
        allowed = {'credencial', 'remover_credencial', 'modelo', 'account_id', 'api_version'}
        if not isinstance(data, dict) or set(data) - allowed:
            raise ValueError('Configuração inválida.')
        if data.get('remover_credencial') is True:
            ed_secrets.put(provider, '')
        elif data.get('credencial'):
            ed_secrets.put(provider, data['credencial'])
        value = config(provider)
        for key in ('modelo', 'account_id', 'api_version'):
            if key in data:
                value[key] = store.texto(data[key], 100)
        with store.conectar() as con:
            con.execute('INSERT INTO ed_config VALUES (?,?) ON CONFLICT(chave) DO UPDATE SET valor=excluded.valor', ('integracao:' + provider, json.dumps(value)))
        # Mesmo salvar sem mudança exige validação explícita novamente.
        log(provider, dict(estado='configurado_nao_validado', mensagem='Configuração salva; teste pendente.', fingerprint=fingerprint(provider)))
        return jsonify(cards()[provider])

    @bp.post('/integracoes/<provider>/testar')
    def test(provider):
        return jsonify(start(provider, 'teste', current_app._get_current_object()))

    @bp.get('/operacoes/<ident>')
    def operation(ident):
        return jsonify(ler_job(ident))

    @bp.post('/operacoes/<ident>/cancelar')
    def cancel(ident):
        with lock:
            job = ler_job(ident)
            if job['estado'] in ('na_fila', 'pesquisando'):
                job.update(estado='cancelada', mensagem='Cancelada localmente. Uma requisição já enviada pode consumir cota; nenhuma edição será aplicada.')
                save(job)
                if job['tipo']=='voice_transcription' and not job['parametros'].get('manter_audio'):
                    from pathlib import Path
                    name=job['parametros'].get('arquivo','')
                    if name and Path(name).name==name:(store.pasta()/'voz'/name).unlink(missing_ok=True)
        return jsonify(ler_job(ident))

    @bp.post('/empresas/<ident>/preparacao/ia')
    def generate(ident):
        from ed_preparation import ler
        lead, p = store.ler_empresa(ident), ler(ident)
        data = request.get_json()
        if not isinstance(data, dict) or set(data) != {'revisao'} or data['revisao'] != p['revisao']:
            return jsonify(erro='Salve sua preparação e atualize a revisão antes de gerar.'), 409
        facts = {k: s['valor'] for k, s in lead['fontes'].items() if s['verificacao'] == 'confirmado_usuario' and s.get('exportavel', True)}
        context = dict(fatos_confirmados=facts, objetivo=p['objetivo'], publico=p['publico'], oferta=p['oferta'], cta=p['cta'], secoes=[{'id': s['id']} for s in p['secoes']])
        return jsonify(start('openai', 'ia', current_app._get_current_object(), empresa_id=ident, revisao=p['revisao'], contexto=context)), 201
