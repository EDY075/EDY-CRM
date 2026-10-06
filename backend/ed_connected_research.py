"""Compor rotas existentes; nenhuma credencial é entregue ao modelo."""
import hashlib
import json
import re
from pathlib import Path
from urllib.parse import urlencode
from flask import jsonify, request
from werkzeug.exceptions import Conflict
import ed_store as store
from ed_assistant import chat_lock

SKILL = Path(__file__).resolve().parent.parent / '.agents/skills/edy-pesquisa-conectada/SKILL.md'
TITLE = 'EDY Pesquisa Conectada'


def skill_state():
    from ed_library import items
    digest = hashlib.sha256(SKILL.read_text(encoding='utf-8').strip().encode()).hexdigest()
    item = next((i for i in items() if i['tipo'] == 'skill' and i['origem'] == 'skill:edy-pesquisa-conectada'), None)
    return dict(disponivel=True, instalada=bool(item), atual=bool(item and item['sha256'] == digest),
                id=item['id'] if item else None, versao=item['versao'] if item else None,
                estado=item['estado'] if item else 'nao_instalada', sha256=digest)


def install():
    from ed_library import save, get
    with chat_lock:
        state = skill_state()
        if state['atual']:
            return get(state['id'])
        # Atualizar o texto não reativa uma instrução desativada pelo operador.
        fields = dict(tipo='skill', titulo=TITLE, conteudo=SKILL.read_text(encoding='utf-8'), escopo='global',
                      estado=state['estado'] if state['id'] else 'ativo', origem='skill:edy-pesquisa-conectada',
                      capacidades=[], essenciais='Verificar fontes e associação; não conceder acesso, iniciar cobrança ou transformar prints em fotos autorizadas. Preservar revisão e direitos.')
        if state['id']:
            fields['versao'] = state['versao']
        return save(fields, state['id'])


def selection_digest(selection):
    return hashlib.sha256(json.dumps(selection, sort_keys=True, ensure_ascii=False, separators=(',', ':')).encode()).hexdigest()


def use_skill(company, expected):
    from ed_library import selection
    with chat_lock:
        store.ler_empresa(company)
        chosen = selection(company)
        if selection_digest(chosen) != expected:
            raise Conflict('A seleção de contexto mudou. Recarregue; suas escolhas foram preservadas.')
        item = install()
        if item['estado'] != 'ativo':
            raise Conflict('A skill está inativa. Revise e ative na Biblioteca antes de usá-la.')
        with store.conectar() as con:
            con.execute('BEGIN IMMEDIATE')
            row = con.execute('SELECT valor FROM ed_config WHERE chave=?', ('biblioteca:' + company,)).fetchone()
            chosen = json.loads(row['valor']) if row else chosen
            if selection_digest(chosen) != expected:
                raise Conflict('A seleção de contexto mudou. Recarregue; suas escolhas foram preservadas.')
            if chosen['selecionados'] is not None and item['id'] not in chosen['selecionados']:
                if len(chosen['selecionados']) >= 100:
                    raise Conflict('A seleção atingiu 100 itens. Revise a Biblioteca antes de adicionar a skill.')
                chosen['selecionados'].append(item['id'])
                con.execute('INSERT INTO ed_config VALUES (?,?) ON CONFLICT(chave) DO UPDATE SET valor=excluded.valor',
                            ('biblioteca:' + company, json.dumps(chosen, ensure_ascii=False)))
        return readiness(company)


def captures(company):
    result = []
    with store.conectar() as con:
        for row in con.execute('SELECT dados FROM ed_operacoes ORDER BY rowid DESC'):
            job = json.loads(row['dados'])
            if job.get('empresa_id') == company and job.get('parametros', {}).get('pesquisa_conectada'):
                result.append(job)
                if len(result) == 6:
                    break
    return result


def readiness(company):
    from ed_services import cards
    from ed_social import associacao
    from ed_library import selection, resolve
    lead = store.ler_empresa(company)
    connectors, social = cards(), associacao(company)
    sources = []
    for ident in ('apify', 'instagram', 'meta_discovery', 'google', 'firecrawl'):
        c = connectors[ident]
        sources.append(dict(id=ident, nome=c['nome'], estado=c['status_acesso'], credencial_presente=c['credencial_presente'],
                            autenticacao_validada_em=c['autenticacao_validada_em'], operacoes_validadas=c['operacoes_validadas'],
                            acao_necessaria=c['configuracao'], docs=c['docs']))
    query = ' '.join(lead.get(k, '') for k in ('nome', 'cidade', 'uf', 'endereco') if lead.get(k))[:500]
    maps_url = 'https://www.google.com/maps/search/?' + urlencode(dict(api=1, query=query))
    while len(maps_url) > 2048:
        query = query[:-1]
        maps_url = 'https://www.google.com/maps/search/?' + urlencode(dict(api=1, query=query))
    skill = skill_state()
    skill['selecionada_empresa'] = any(i['id'] == skill['id'] for i in resolve(company)['items'])
    return dict(empresa_id=company, skill=skill, selecao_sha256=selection_digest(selection(company)), fontes=sources, instagram=social, site=lead['associacao_site'],
                maps_url=maps_url,
                captura_disponivel=social['estado'] == 'confirmado', capturas=captures(company),
                pendencias=['Consulta Maps por link é manual; não houve coleta Places.',
                            'Captura pública pode falhar por robots, HTTP, login ou conteúdo indisponível.',
                            'Posts e fotos requerem autorização própria; mídia por link pode expirar.'])


def validate_capture(job, observed):
    """Não registrar login, perfil diferente ou renderização vazia como coleta."""
    from ed_social import associacao, perfil
    p = job['parametros']
    social = associacao(job['empresa_id'])
    if social['estado'] != 'confirmado' or perfil(social['url']) != p['perfil_instagram']:
        raise ValueError('A associação mudou durante a captura. Revise o perfil; nenhuma referência foi aplicada.')
    records = observed.get('viewports', [])
    if len(records) != 2:
        raise ValueError('Captura incompleta; desktop e celular precisam de conteúdo para revisão.')
    expected = re.compile(r'(?<![a-z0-9._])@?' + re.escape(p['perfil_instagram']) + r'(?![a-z0-9._])', re.I)
    for r in records:
        text = ' '.join([r.get('titulo', ''), *r.get('titulos', []), r.get('texto', '')])
        images = [i for i in r.get('imagens', []) if i.get('largura', 0) >= 64 and i.get('altura', 0) >= 64]
        headings = r.get('titulos', [])
        login_wall = any(re.search(r'^(log in|login|entrar|iniciar sess[aã]o|sign up|cadastre-se)\b', h, re.I) for h in headings) and not any(expected.search(h) for h in headings)
        if login_wall or not expected.search(text) or len(r.get('texto', '').strip()) < 80 or not images:
            raise ValueError('O Instagram não mostrou conteúdo suficiente do perfil confirmado. Pode haver login, bloqueio ou dependência de JavaScript. Use o conector configurado ou envie arquivos; nenhuma coleta concluída.')


def capture(company, key):
    from ed_social import associacao, perfil
    from ed_tasks import iniciar
    from ed_visual_research import worker
    with chat_lock:
        social = associacao(company)
        if social['estado'] != 'confirmado':
            raise Conflict('Confirme o vínculo do Instagram com a empresa antes de capturar. Cadastro e upload continuam disponíveis.')
        url = 'https://www.instagram.com/' + perfil(social['url']) + '/'
        ticket = 'pesquisa-conectada:captura:' + company + ':' + hashlib.sha256(key.encode()).hexdigest()
        with store.conectar() as con:
            jobs = (json.loads(r['dados']) for r in con.execute('SELECT dados FROM ed_operacoes'))
            previous = next((j for j in jobs if j.get('chave') == ticket), None)
        if previous:
            if previous['parametros']['url'] != url:
                raise Conflict('O perfil mudou. Use uma nova ação de captura; a execução anterior foi preservada.')
            return previous
        lead = store.ler_empresa(company)
        parameters = dict(url=url, titulo=lead['nome'][:100] + ' · Instagram · captura pública', fonte='browser', modo='inspirar',
                          pesquisa_conectada=True, perfil_instagram=perfil(social['url']), associacao=social, skill=skill_state())
        # Chave e execução são gravadas juntas pela fila existente; sobrevive a reinício.
        return iniciar('local', 'visual_reference', company, parameters, worker, idempotency_key=ticket)


def registrar(bp):
    @bp.get('/empresas/<company>/pesquisa-conectada')
    def connected_status(company):
        return jsonify(readiness(company))

    @bp.post('/pesquisa-conectada/skill')
    def connected_install():
        if request.get_json() != {}:
            raise ValueError('Instalação de skill inválida.')
        item = install()
        return jsonify({k: item[k] for k in ('id', 'titulo', 'versao', 'sha256', 'estado')})

    @bp.post('/empresas/<company>/pesquisa-conectada/skill')
    def connected_use_skill(company):
        data = request.get_json()
        if not isinstance(data, dict) or set(data) != {'selecao_sha256'}:
            raise ValueError('Seleção de contexto inválida.')
        return jsonify(use_skill(company, store.texto(data['selecao_sha256'], 64)))

    @bp.post('/empresas/<company>/pesquisa-conectada/capturar-instagram')
    def connected_capture(company):
        data = request.get_json()
        if not isinstance(data, dict) or set(data) != {'chave'}:
            raise ValueError('Selecione o perfil confirmado; não enviar URL ou credencial.')
        key = store.texto(data['chave'], 100)
        if not key.strip():
            raise ValueError('Identificador da captura ausente.')
        return jsonify(capture(company, key)), 202
