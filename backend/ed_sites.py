"""Associação de URL: classificação não é prova de identidade nem autorização."""
import json
import re
from urllib.parse import parse_qs, urlsplit
from flask import jsonify, request


def classificar(url):
    p = urlsplit(url)
    host = (p.hostname or '').lower().removeprefix('www.')
    path = p.path.rstrip('/')
    if not url:
        return dict(tipo='ausente', motivo='Nenhum site informado.')
    google = bool(re.fullmatch(r'google\.(?:com(?:\.[a-z]{2})?|[a-z]{2}|co\.[a-z]{2})', host))
    map_link = ((host in ('maps.app.goo.gl', 'goo.gl') and (host != 'goo.gl' or path.startswith('/maps')))
                or host in ('openstreetmap.org', 'maps.google.com', 'maps.google.com.br', 'mapquest.com')
                or (google and (path == '/maps' or path.startswith('/maps/'))))
    if map_link:
        return dict(tipo='mapa', motivo='Link de mapas/localização; não comprova site próprio da empresa.')
    if host == 'sites.google.com':
        if re.match(r'^/(?:view|site)/[^/]+(?:/|$)', path) and not any(k in parse_qs(p.query) for k in ('q', 'search')):
            return dict(tipo='candidato', motivo='Página específica em Google Sites; conferir nome, filial e contato.')
        return dict(tipo='generica', motivo='URL genérica ou de administração do Google Sites; informe a página pública específica.')
    engines = {'bing.com', 'duckduckgo.com', 'search.yahoo.com', 'yahoo.com', 'search.brave.com', 'ecosia.org', 'yandex.com', 'yandex.ru', 'baidu.com'}
    if google or host in engines:
        return dict(tipo='busca', motivo='Página de buscador/pesquisa; guardar como fonte, não como site oficial.')
    if path.lower() in ('/search', '/busca', '/pesquisa') or any(k in parse_qs(p.query) for k in ('q', 'query', 'search')):
        return dict(tipo='busca', motivo='URL de resultados de pesquisa; informe a página específica da empresa.')
    return dict(tipo='candidato', motivo='URL candidata; domínio ou plataforma por si só não confirma a associação.')


def registrar_historico(base, anterior, motivo, novo=''):
    import ed_store as store
    base.setdefault('historico_site', []).append(dict(valor_anterior=anterior, valor_novo=novo,
        fonte_anterior=base.get('fontes', {}).get('site', {}).copy(), motivo=motivo, registrado_em=store.agora()))


def separar_fonte(base, value, origem=''):
    """Retém a URL exata e sua classificação, sem certificar dados comerciais."""
    import ed_store as store
    result = classificar(value)
    field = 'fonte_mapa_url' if result['tipo'] == 'mapa' else 'fonte_busca_url'
    base[field] = value
    base.setdefault('fontes', {})[field] = store.fonte(field, value, 'referencia_url', origem or value)
    base['fontes'][field]['retencao'] = 'Link de referência; conteúdo e associação sujeitos à revisão'
    links = base.setdefault('links_fontes', [])
    if not any(x['url'] == value for x in links):
        links.append(dict(url=value, tipo=result['tipo'], motivo=result['motivo'], registrado_em=store.agora()))
    return result


def ajustar_gravacao(base, old, values):
    import ed_store as store
    value = values.get('site', base.get('site', ''))
    category = classificar(value)
    if value and category['tipo'] != 'candidato':
        original_source = old.get('fontes', {}).get('site', {})
        retained = old.get('site', '') if classificar(old.get('site', ''))['tipo'] == 'candidato' else ''
        registrar_historico(base, value, category['motivo'], retained)
        if original_source and old.get('site') == value:
            base['historico_site'][-1]['fonte_anterior'] = original_source.copy()
        separar_fonte(base, value, original_source.get('url', '') or base.get('fonte_url', ''))
        base['site'] = retained
        if retained:
            base['fontes']['site'] = original_source
        else:
            base['fontes'].pop('site', None)
            base['associacao_site'] = dict(estado='pendente', url='', motivo=category['motivo'], evidencias=[])
    elif 'site' in values and value != old.get('site', ''):
        if old.get('site'):
            registrar_historico(base, old['site'], 'URL alterada; nova associação requer revisão.', value)
            base['historico_site'][-1]['fonte_anterior'] = old.get('fontes', {}).get('site', {}).copy()
        base['associacao_site'] = dict(estado='pendente', url=value, motivo=category['motivo'], evidencias=[])
        if value:
            base['fontes']['site']['verificacao'] = 'a_confirmar'
    for key in ('fonte_busca_url', 'fonte_mapa_url'):
        if key in values:
            if base[key]:
                base['fontes'][key] = store.fonte(key, base[key], 'referencia_url', base[key])
                base['fontes'][key]['retencao'] = 'Link de referência; não é site oficial'
            else:
                base['fontes'].pop(key, None)


def status(lead):
    candidate = classificar(lead['site'])
    confirmed = candidate['tipo'] == 'candidato' and lead['fontes'].get('site', {}).get('verificacao') == 'confirmado_usuario'
    saved = lead.get('associacao_site', {})
    return dict(estado='confirmado' if confirmed else 'pendente', url=lead['site'],
                motivo=saved.get('motivo') or candidate['motivo'], evidencias=saved.get('evidencias', []) if saved.get('url') == lead['site'] else [])


def migrar(con):
    """Reclassificação idempotente dos sites inequivocamente genéricos."""
    import ed_store as store
    for row in con.execute('SELECT id,dados FROM ed_empresas').fetchall():
        base = json.loads(row['dados'])
        value = base.get('site', '')
        if not value or classificar(value)['tipo'] == 'candidato':
            continue
        old = json.loads(row['dados'])
        ajustar_gravacao(base, old, {'site': value})
        con.execute('UPDATE ed_empresas SET dados=?,atualizado_em=? WHERE id=? AND dados=?',
            (json.dumps(base, ensure_ascii=False), store.agora(), row['id'], row['dados']))


def evidencias(lead, final, content):
    from lxml import html
    import ed_store as store
    tree = html.fromstring(content, parser=html.HTMLParser(no_network=True))
    links = tree.xpath('//a/@href')
    for node in tree.xpath('//script|//style|//noscript|//template'):
        node.drop_tree()
    text = re.sub(r'\s+', ' ', tree.text_content()).strip()
    normalized = store.normalizar(text)
    found = []
    def add(field, value, method):
        found.append(dict(campo=field, evidencia=value, origem=final, metodo=method))
    name = store.normalizar(lead['nome'])
    if len(name) >= 5 and name in normalized:
        add('nome', lead['nome'], 'Nome publicado coincide; homônimos continuam possíveis')
    for value in [lead.get('endereco', ''), lead.get('cidade', '')]:
        if len(store.normalizar(value)) >= 4 and store.normalizar(value) in normalized:
            add('localizacao', value, 'Trecho coincide; conferir filial e endereço completo')
            break
    phone = re.sub(r'\D', '', lead.get('telefone', ''))
    tels = [re.sub(r'\D', '', link[4:]) for link in links if link.startswith('tel:')]
    if len(phone) >= 8 and any(t == phone or t.removeprefix('55') == phone.removeprefix('55') for t in tels):
        add('contato', lead['telefone'], 'Telefone do link tel: coincide com o cadastro')
    email = lead.get('email', '').lower()
    if email and any(link.lower().split('?')[0] == 'mailto:'+email for link in links):
        add('contato', email, 'E-mail publicado coincide com o cadastro')
    social = lead.get('instagram', '').rstrip('/').lower()
    if social and any(link.rstrip('/').lower() == social for link in links):
        add('vinculo_social', lead['instagram'], 'Site aponta para o perfil cadastrado; vínculo ainda requer revisão')
    return found


def registrar(bp):
    import ed_store as store
    @bp.get('/empresas/<ident>/site/associacao')
    def association(ident):
        lead = store.ler_empresa(ident)
        with store.conectar() as con:
            row = con.execute('SELECT valor FROM ed_config WHERE chave=?', ('associacao:site:'+ident,)).fetchone()
        proposal = json.loads(row['valor']) if row else None
        if proposal and (proposal['site'] != lead['site'] or proposal['contexto'] != {k:lead[k] for k in ('nome','cidade','endereco','telefone','email','instagram')}):
            proposal = None
        return jsonify(associacao=status(lead), proposta=proposal)

    @bp.post('/empresas/<ident>/site/verificar')
    def verify(ident):
        import ed_enrich as enrich
        lead = store.ler_empresa(ident)
        data = request.get_json()
        if not isinstance(data, dict) or set(data) != {'site'} or data['site'] != lead['site']:
            return jsonify(erro='O site mudou; atualize antes de verificar.'), 409
        if classificar(lead['site'])['tipo'] != 'candidato':
            raise ValueError('Sem URL empresarial candidata. Adicione uma página específica ou use as outras fontes.')
        diagnostic = {'site':lead['site']}
        check = enrich.robots_checker(diagnostic)
        result = dict(site=lead['site'], estado='pendente', evidencias=[], ambiguo=True, consultado_em=store.agora(),
                      contexto={k:lead[k] for k in ('nome','cidade','endereco','telefone','email','instagram')})
        try:
            if check(lead['site']) > 10:
                raise enrich.ReadError('Intervalo exigido pelo site excede o limite desta verificação.', 'limite')
            def before(url):
                if classificar(url)['tipo'] != 'candidato':
                    raise enrich.ReadError('Redirecionamento para busca/mapa/URL genérica; associação não confirmada.', 'associacao')
                check(url)
            final, content, media = enrich.ler_url(lead['site'], site=lead['site'], antes_de_ler=before)
            if classificar(final)['tipo'] != 'candidato':
                raise enrich.ReadError('A página redirecionou para busca/mapa/URL genérica. Associação não confirmada.', 'associacao')
            if media and 'html' not in media.lower():
                raise enrich.ReadError('A página não retornou HTML.', 'conteudo')
            found = evidencias(lead, final, content)
            strong = len({e['campo'] for e in found}) >= 2 and any(e['campo'] in ('contato','vinculo_social') for e in found)
            result.update(evidencias=found, ambiguo=not strong, url_final=final,
                mensagem='Correspondências para revisão; não confirmam automaticamente a empresa.' if strong else 'Associação ambígua: evidências insuficientes. Confira nome, endereço, contato ou vínculo social.')
        except ValueError as exc:
            result.update(mensagem=str(exc), erro=enrich.error_detail(exc, lead['site'], 'associacao'))
        result['robots'] = diagnostic.get('robots')
        with store.conectar() as con:
            con.execute('INSERT INTO ed_config VALUES (?,?) ON CONFLICT(chave) DO UPDATE SET valor=excluded.valor',
                ('associacao:site:'+ident, json.dumps(result, ensure_ascii=False)))
        return jsonify(result)

    @bp.post('/empresas/<ident>/site/confirmar')
    def confirm(ident):
        data = request.get_json()
        if not isinstance(data, dict) or set(data) != {'site','evidencia'}:
            raise ValueError('Informe a URL e a evidência revisada da associação.')
        evidence = store.texto(data['evidencia'], 2000)
        if len(evidence) < 15:
            raise ValueError('Descreva a evidência de vínculo: nome, localização, contato ou perfil social (mínimo 15 caracteres).')
        with store.conectar() as con:
            row = con.execute('SELECT dados FROM ed_empresas WHERE id=?', (ident,)).fetchone()
            if not row:
                raise LookupError('Empresa não encontrada.')
            base = json.loads(row['dados'])
            if base['site'] != data['site']:
                return jsonify(erro='O site mudou; reveja a associação.'), 409
            if classificar(base['site'])['tipo'] != 'candidato':
                raise ValueError('Link genérico, busca ou mapa não pode ser confirmado como site oficial.')
            registrar_historico(base, base['site'], 'Associação revisada pelo usuário.', base['site'])
            base['fontes']['site'] = {**base['fontes'].get('site', store.fonte('site', base['site'], 'manual', base['site'])),
                'verificacao':'confirmado_usuario', 'evidencia':evidence, 'revisado_em':store.agora()}
            base['associacao_site'] = dict(estado='confirmado', url=base['site'], motivo='Vínculo confirmado após revisão humana.',
                evidencias=[dict(campo='revisao_usuario', evidencia=evidence, origem=base['site'], metodo='Conferência manual')])
            updated = con.execute('UPDATE ed_empresas SET dados=?,atualizado_em=? WHERE id=? AND dados=?',
                (json.dumps(base, ensure_ascii=False), store.agora(),ident,row['dados']))
            if not updated.rowcount:
                return jsonify(erro='A ficha mudou durante a revisão. Atualize antes de confirmar.'), 409
        return jsonify(store.ler_empresa(ident))
