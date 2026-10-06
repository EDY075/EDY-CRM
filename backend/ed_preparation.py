"""Decisões de projeto isoladas de fatos e de propostas externas, com revisão CAS."""
import json
import re
from flask import jsonify, request
import ed_store as store

TEXT = ('objetivo', 'publico', 'oferta', 'cta', 'prospeccao', 'funcionalidades', 'banco', 'administracao')
DESIGN = ('paleta', 'fonte_titulos', 'fonte_texto', 'estilo', 'composicao', 'movimento', 'shader', 'titulos', 'cursor', 'restricoes')
ROLES = ('abertura', 'ambiente', 'servicos', 'produtos', 'pessoas', 'logo', 'referencia')


def direcao_nicho(nicho):
    """Templates editoriais, nunca afirmações sobre marca/empresa/equipe."""
    key = store.normalizar(nicho)
    presets = [
        (('padar', 'restaur', 'cafe'), '#3c2d24, #f4ede2, #b8703c', 'Editorial artesanal com tons de papel e luz quente',
         'Textura orgânica discreta e luz morna; fallback estático.', 'Pontos de luz quente inspirados no forno; sem simular fogo real.'),
        (('academ', 'fitness', 'esport'), '#162523, #f2f4ed, #bbd45c', 'Tipografia forte e composição dinâmica com identidade própria',
         'Fluxo abstrato de energia com contraste controlado; fallback estático.', 'Faíscas abstratas breves inspiradas em energia; sem cobrir conteúdo.'),
        (('veter', 'pet', 'saude', 'clinic'), '#214b52, #f4f7f2, #89c1b1', 'Composição acolhedora e clara, adequada a informações de cuidado',
         'Luz difusa calma e textura discreta; evitar efeitos de alerta.', 'Pontos suaves de luz; evitar faíscas intensas em contexto de cuidado.'),
        (('salao', 'saloe', 'beleza', 'barbear'), '#342c36, #f6f0eb, #b18c7b', 'Editorial com enquadramentos cuidados e tons elegantes',
         'Reflexos abstratos suaves; fallback estático.', 'Brilho fino e discreto associado à luz; sem simular pessoas ou resultados.'),
    ]
    for terms, palette, style, shader, cursor in presets:
        if any(t in key for t in terms):
            return dict(paleta=palette, estilo=style + ' — proposta por template; revisar marca.', shader=shader,
                        cursor='Opcional: ' + cursor + ' Somente ponteiro fino; desativar no celular e em movimento reduzido.')
    return dict(paleta='#173f35, #f5f1e8, #b88946', estilo='Identidade própria; revisar marca e nicho — proposta por template.',
                shader='Opcional: textura abstrata suave adaptada ao nicho; fallback estático.',
                cursor='Opcional: partículas discretas coerentes com a marca; somente ponteiro fino, sem bloquear cliques.')


def defaults(lead):
    b = lead['briefing']
    confirmed = {k: v['valor'] for k, v in lead['fontes'].items() if v.get('verificacao') == 'confirmado_usuario' and v.get('exportavel', True)}
    proposed = {k: b.get(k, '') for k in TEXT}
    proposed.update(objetivo=b.get('objetivo') or 'Apresentar informações confirmadas e facilitar um primeiro contato; objetivo a revisar.',
        publico=b.get('publico') or f'Pessoas interessadas em {lead["nicho"] or "serviços da empresa"}; hipótese de público a validar.',
        oferta=confirmed.get('servicos') or 'Oferta a confirmar com a empresa; não presumir produtos, preços ou condições.',
        cta=b.get('cta') or 'Entrar em contato pelo canal confirmado; revisar a estratégia antes de publicar.')
    result = dict(revisao=0, modo='previa', **proposed,
        design=dict(paleta='#173f35, #f5f1e8, #b88946', fonte_titulos='A definir com a identidade da empresa',
            fonte_texto='Fonte legível; confirmar licença', estilo='Identidade própria; revisar marca e nicho',
            composicao='Abertura com foto dominante, hierarquia tipográfica forte, CTA visível; alternar texto e imagens reais.',
            movimento='Movimento discreto; respeitar prefers-reduced-motion e pausar fora da tela.',
            shader='Opcional: textura abstrata suave, adaptada ao nicho; fallback estático e sem prejudicar contraste.',
            titulos='Entrada curta de título e subtítulo, sem esconder texto quando JavaScript falhar.',
            cursor='Opcional: partículas discretas coerentes com a marca; somente ponteiro fino, sem bloquear cliques.',
            restricoes='Sem animações pesadas no celular; nenhuma imagem ilustrativa apresentada como registro real.'),
        referencias=[], imagens=[], secoes=[dict(id=k, titulo=t, texto=confirmed.get(f, ''), revisado=False)
            for k, t, f in [('abertura', lead['nome'], 'descricao'), ('servicos', 'Serviços', 'servicos'),
                             ('sobre', 'Sobre a empresa', 'descricao'), ('contato', 'Entre em contato', 'telefone')]])
    result['design'].update(direcao_nicho(lead['nicho']))
    return result


def ler(ident):
    lead = store.ler_empresa(ident)
    with store.conectar() as con:
        row = con.execute('SELECT dados FROM ed_preparacoes WHERE empresa_id=?', (ident,)).fetchone()
    return json.loads(row['dados']) if row else defaults(lead)


def validar(ident, data):
    allowed = set(TEXT) | {'revisao', 'modo', 'design', 'referencias', 'imagens', 'secoes'}
    if not isinstance(data, dict) or set(data) != allowed:
        raise ValueError('Preparação inválida; atualize a tela.')
    if type(data['revisao']) is not int or data['revisao'] < 0 or data['modo'] not in ('previa', 'completo'):
        raise ValueError('Modo ou revisão inválidos.')
    out = {k: store.texto(data[k], 4000) for k in TEXT}
    out.update(revisao=data['revisao'], modo=data['modo'])
    if not isinstance(data['design'], dict) or set(data['design']) != set(DESIGN):
        raise ValueError('Direção visual inválida.')
    out['design'] = {k: store.texto(data['design'][k], 2000) for k in DESIGN}
    lead = store.ler_empresa(ident)
    mids = {m['id'] for m in lead['materiais']}
    for key in ('referencias', 'imagens', 'secoes'):
        if not isinstance(data[key], list) or len(data[key]) > 30:
            raise ValueError('Limite de 30 itens por grupo.')
    out['referencias'] = []
    for r in data['referencias']:
        if not isinstance(r, dict) or set(r) != {'url', 'material_id', 'observacao'}:
            raise ValueError('Referência inválida.')
        if r['material_id'] and r['material_id'] not in mids:
            raise ValueError('Imagem de referência não pertence à empresa.')
        out['referencias'].append(dict(url=store.url(r['url']), material_id=store.texto(r['material_id'], 80), observacao=store.texto(r['observacao'], 2000)))
    out['secoes'] = []
    for s in data['secoes']:
        if not isinstance(s, dict) or set(s) != {'id', 'titulo', 'texto', 'revisado'} or not re.fullmatch(r'[a-z0-9_-]{1,60}', s['id']):
            raise ValueError('Seção inválida.')
        out['secoes'].append(dict(id=s['id'], titulo=store.texto(s['titulo'], 300), texto=store.texto(s['texto'], 4000), revisado=store.booleano(s['revisado'])))
    if len({s['id'] for s in out['secoes']}) != len(out['secoes']):
        raise ValueError('Seções repetidas.')
    out['imagens'] = []
    for m in data['imagens']:
        if not isinstance(m, dict) or set(m) != {'material_id', 'funcao', 'natureza', 'pessoa', 'desktop', 'mobile'} or m['material_id'] not in mids or m['funcao'] not in ROLES:
            raise ValueError('Escolha um material desta empresa e uma função válida.')
        if m['natureza'] not in ('a_confirmar', 'registro_empresa', 'ilustrativa', 'referencia'):
            raise ValueError('Identidade da imagem inválida.')
        item = dict(material_id=m['material_id'], funcao=m['funcao'], natureza=m['natureza'], pessoa=store.texto(m['pessoa'], 200))
        for viewport in ('desktop', 'mobile'):
            f = m[viewport]
            if not isinstance(f, dict) or set(f) != {'x', 'y', 'recorte', 'enquadramento'} or f['recorte'] not in ('cover', 'contain'):
                raise ValueError('Enquadramento inválido.')
            if any(type(f[k]) not in (int, float) or not 0 <= f[k] <= 100 for k in ('x', 'y')):
                raise ValueError('Posição deve ficar entre 0 e 100%.')
            item[viewport] = {**f, 'enquadramento': store.texto(f['enquadramento'], 500)}
        out['imagens'].append(item)
    if len({m['material_id'] for m in out['imagens']}) != len(out['imagens']):
        raise ValueError('Posições repetidas para o mesmo material.')
    return out


def salvar(ident, data):
    value = validar(ident, data)
    with store.conectar() as con:
        con.execute('INSERT OR IGNORE INTO ed_preparacoes VALUES (?,?)', (ident, json.dumps(defaults(store.ler_empresa(ident)), ensure_ascii=False)))
        row = con.execute('SELECT dados FROM ed_preparacoes WHERE empresa_id=?', (ident,)).fetchone()
        if json.loads(row['dados'])['revisao'] != value['revisao']:
            return None
        value['revisao'] += 1
        changed = con.execute('UPDATE ed_preparacoes SET dados=? WHERE empresa_id=? AND dados=?', (json.dumps(value, ensure_ascii=False), ident, row['dados']))
        return value if changed.rowcount else None


def pendencias(lead, p):
    result = [f'Definir {k}.' for k in ('objetivo', 'publico', 'oferta', 'cta') if not p[k]]
    result += [f'Revisar texto da seção {s["id"]}.' for s in p['secoes'] if not s['revisado'] or not s['texto']]
    selected = {m['id'] for m in lead['materiais'] if m['autorizado'] and m['selecionado']}
    if not selected:
        result.append('Sem arquivos autorizados selecionados; usar placeholders.')
    for m in p['imagens']:
        if m['material_id'] not in selected:
            result.append(f'Material da função {m["funcao"]} não será anexado: selecione e autorize na galeria.')
        if m['natureza'] == 'a_confirmar' or m['funcao'] == 'pessoas' and not m['pessoa']:
            result.append(f'Confirmar identidade/conteúdo da imagem em {m["funcao"]}; não afirmar identidade sem evidências.')
    if p['modo'] == 'completo':
        result += [f'Definir requisitos de {k}.' for k in ('funcionalidades', 'banco', 'administracao') if not p[k]]
    return result


def registrar(bp):
    @bp.get('/empresas/<ident>/preparacao')
    def get_preparation(ident):
        return jsonify(ler(ident))

    @bp.put('/empresas/<ident>/preparacao')
    def put_preparation(ident):
        p = salvar(ident, request.get_json())
        return (jsonify(p), 200) if p else (jsonify(erro='Preparação alterada em outra tela. Recarregue e compare suas edições antes de salvar.'), 409)

    @bp.get('/empresas/<ident>/preparacao/pendencias')
    def preparation_pending(ident):
        return jsonify(pendencias(store.ler_empresa(ident), ler(ident)))
