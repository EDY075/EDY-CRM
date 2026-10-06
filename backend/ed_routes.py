import io
import json
import warnings
from threading import Lock

from flask import Blueprint, abort, current_app, jsonify, request, send_file
from PIL import Image, UnidentifiedImageError

import ed_export
import ed_store as store

bp = Blueprint('ed', __name__, url_prefix='/api/ed')
export_lock = Lock()


@bp.get('/health')
def health():
    return jsonify(app='EDY CRM', versao='0.4.0')


@bp.get('/integracoes/status')
def integracoes_status():
    from ed_integrations import status
    return jsonify(status())


@bp.get('/config')
def config():
    from ed_search import NICHOS
    return jsonify(**store.config(), nichos=list(NICHOS), etapas=store.ETAPAS,
                   fonte='OpenStreetMap / Overpass / Nominatim',
                   atribuicao='© OpenStreetMap contributors — ODbL 1.0')


@bp.put('/config')
def salvar_config():
    data = request.get_json()
    if not isinstance(data, dict) or set(data) != {'osm_habilitado'}:
        raise ValueError('Configuração inválida.')
    value = store.booleano(data['osm_habilitado'])
    with store.conectar() as con:
        con.execute('INSERT INTO ed_config VALUES (?,?) ON CONFLICT(chave) DO UPDATE SET valor=excluded.valor',
                    ('osm_habilitado', json.dumps(value)))
    return jsonify(**store.config())


@bp.get('/empresas')
def empresas():
    result = store.listar_empresas()
    if request.args.get('arquivadas')!='true':result=[x for x in result if not x.get('crm_arquivada')]
    q = store.normalizar(request.args.get('q', ''))
    for key in ('nicho', 'cidade', 'etapa'):
        if request.args.get(key):
            result = [x for x in result if store.normalizar(request.args[key]) in store.normalizar(x[key])]
    if q:
        result = [x for x in result if q in store.normalizar(x['nome'] + ' ' + x['cidade'] + ' ' + x['nicho'])]
    if request.args.get('duplicatas') == 'true':
        result = [x for x in result if x['possiveis_duplicatas']]
    if request.args.get('site') == 'nao_informado':
        result = [x for x in result if not x['site']]
    elif request.args.get('site') == 'informado':
        result = [x for x in result if x['site']]
    return jsonify(result)


@bp.post('/empresas')
def criar_empresa():
    lead, _ = store.gravar_empresa(request.get_json())
    return jsonify(lead), 201


@bp.get('/empresas/<ident>')
def ficha(ident):
    from ed_preview import lead_links
    return jsonify(lead_links(store.ler_empresa(ident)))


@bp.patch('/empresas/<ident>')
def editar_empresa(ident):
    lead, _ = store.gravar_empresa(request.get_json(), ident)
    return jsonify(lead)


@bp.post('/empresas/<ident>/materiais')
def upload(ident):
    lead = store.ler_empresa(ident)
    if len(lead['materiais']) >= 30:
        raise ValueError('Limite de 30 imagens por empresa nesta versão.')
    file = request.files.get('arquivo')
    if not file or not file.filename:
        raise ValueError('Selecione uma imagem PNG, JPEG ou WebP.')
    content = file.read(8 * 1024 * 1024 + 1)
    if len(content) > 8 * 1024 * 1024:
        raise ValueError('Imagem acima de 8 MB.')
    try:
        with warnings.catch_warnings():
            warnings.simplefilter('error', Image.DecompressionBombWarning)
            with Image.open(io.BytesIO(content)) as image:
                ext = {'PNG': 'png', 'JPEG': 'jpg', 'WEBP': 'webp'}.get(image.format)
                if not ext or image.width * image.height > 24_000_000:
                    raise ValueError('Use PNG, JPEG ou WebP com até 24 megapixels.')
                image.verify()
    except (UnidentifiedImageError, OSError, Image.DecompressionBombError, Image.DecompressionBombWarning) as exc:
        raise ValueError('O arquivo não é uma imagem válida.') from exc
    mid = store.novo_id()
    authorized = request.form.get('autorizado', 'false') == 'true'
    origin = store.texto(request.form.get('origem', ''), 1000)
    attribution = store.texto(request.form.get('atribuicao', ''), 1000)
    if authorized and (not origin or not attribution):
        raise ValueError('Informe origem e atribuição para confirmar o uso.')
    name = f'{mid}.{ext}'
    nature=request.form.get('natureza','a_confirmar')
    if nature not in ('a_confirmar','fotografia_original','ilustracao','logo','referencia'):raise ValueError('Natureza do original inválida.')
    target = store.arquivo_seguro('materiais', f'{ident}/{name}')
    target.parent.mkdir(parents=True, exist_ok=True)
    data = dict(arquivo=name, nome_original=store.texto(file.filename, 300),natureza=nature,
                categoria=store.texto(request.form.get('categoria', 'referencia'), 100),
                origem=origin, atribuicao=attribution,
                posicao=store.texto(request.form.get('posicao', 'Galeria; confirmar conteúdo'), 500),
                autorizado=authorized, selecionado=False, criado_em=store.agora(),
                arquivo_url=f'/api/ed/empresas/{ident}/materiais/{mid}/arquivo')
    target.write_bytes(content)
    with store.conectar() as con:
        con.execute('INSERT INTO ed_materiais VALUES (?,?,?)', (mid, ident, json.dumps(data, ensure_ascii=False)))
    return jsonify(id=mid, **data), 201


def material(ident, mid):
    lead = store.ler_empresa(ident)
    found = next((x for x in lead['materiais'] if x['id'] == mid), None)
    if not found:
        raise LookupError('Material não encontrado nesta empresa.')
    return found


@bp.patch('/empresas/<ident>/materiais/<mid>')
def editar_material(ident, mid):
    data = request.get_json()
    allowed = {'selecionado', 'autorizado', 'origem', 'atribuicao', 'categoria', 'posicao'}
    if not isinstance(data, dict) or set(data) - allowed:
        raise ValueError('Campos inválidos no material.')
    m = material(ident, mid)
    m.update({k: store.booleano(v) if k in ('autorizado', 'selecionado') else store.texto(v, 1000)
              for k, v in data.items()})
    if m['autorizado'] and (not m['origem'] or not m['atribuicao']):
        raise ValueError('Origem e atribuição são necessárias.')
    if m['selecionado'] and not m['autorizado']:
        raise ValueError('Confirme autorização de uso antes de selecionar para exportação.')
    saved = {k: v for k, v in m.items() if k != 'id'}
    with store.conectar() as con:
        con.execute('UPDATE ed_materiais SET dados=? WHERE id=? AND empresa_id=?',
                    (json.dumps(saved, ensure_ascii=False), mid, ident))
    return jsonify(m)


@bp.get('/empresas/<ident>/materiais/<mid>/arquivo')
def arquivo_material(ident, mid):
    m = material(ident, mid)
    file = store.arquivo_seguro('materiais', f'{ident}/{m["arquivo"]}')
    if not file.exists():
        raise LookupError('Arquivo ausente no armazenamento local.')
    return send_file(file)


@bp.get('/empresas/<ident>/documento')
def documento(ident):
    lead = store.ler_empresa(ident)
    files, assets = ed_export.pacote(lead)
    text, prompt = files['empresa.md'], files['prompt-codex.md']
    return jsonify(markdown=text, prompt=prompt, materiais=assets, briefing=ed_export.briefing(lead))


@bp.post('/empresas/<ident>/exportacoes')
def exportar(ident):
    data=request.get_json(silent=True) or {}
    if not isinstance(data,dict) or set(data)-{'projeto_id'}:raise ValueError('Exportação inválida.')
    project=data.get('projeto_id','')
    if project:
        from ed_adaptive import project_key
        project=project_key(ident,project)
    with export_lock:
        return jsonify(ed_export.exportar(ident,project_id=project)), 201


@bp.get('/empresas/<ident>/exportacoes/<eid>/<formato>')
def baixar(ident, eid, formato):
    lead = store.ler_empresa(ident)
    if formato not in ('zip', 'markdown') or not any(x['id'] == eid for x in lead['exportacoes']):
        abort(404)
    name = 'pacote.zip' if formato == 'zip' else 'empresa.md'
    file = store.arquivo_seguro('exportacoes', f'{ident}/{eid}/{name}')
    if not file.is_file():
        raise LookupError('Exportação ausente no armazenamento local.')
    return send_file(file, as_attachment=True, download_name=f'ed-crm-{ident[:8]}-{name}')


@bp.post('/empresas/<ident>/previas')
def previa(ident):
    lead = store.ler_empresa(ident)
    data = request.get_json()
    if not isinstance(data, dict) or set(data) - {'url', 'exportacao_id', 'observacoes'}:
        raise ValueError('Prévia inválida.')
    link = store.url(data.get('url', ''))
    if not link:
        raise ValueError('Informe o link da prévia.')
    eid = data.get('exportacao_id', '')
    if not any(x['id'] == eid for x in lead['exportacoes']):
        raise ValueError('Escolha um pacote exportado desta empresa.')
    item = dict(url=link, exportacao_id=eid, observacoes=store.texto(data.get('observacoes', '')),
                criado_em=store.agora())
    ident_previa = store.novo_id()
    with store.conectar() as con:
        con.execute('INSERT INTO ed_previas VALUES (?,?,?)', (ident_previa, ident, json.dumps(item)))
    store.gravar_empresa({'etapa': 'previa_pronta'}, ident)
    return jsonify(id=ident_previa, **item), 201


@bp.get('/campanhas')
def campanhas():
    from ed_search import listar
    return jsonify(listar())


@bp.post('/campanhas')
def buscar():
    from ed_search import iniciar
    if not store.config()['osm_habilitado']:
        return jsonify(erro='Fonte pendente. Ative OpenStreetMap em Integrações ou cadastre uma empresa manualmente.'), 409
    return jsonify(iniciar(request.get_json(), current_app._get_current_object())), 201


@bp.post('/campanhas/<ident>/<acao>')
def acao_campanha(ident, acao):
    from ed_search import acionar
    return jsonify(acionar(ident, acao, current_app._get_current_object()))


import ed_enrich
ed_enrich.registrar(bp)
import ed_preparation
ed_preparation.registrar(bp)
import ed_services
ed_services.registrar(bp)
import ed_sites
ed_sites.registrar(bp)
import ed_images
ed_images.registrar(bp)
import ed_composition
ed_composition.registrar(bp)
import ed_visual_studio, ed_visual_providers
ed_visual_studio.registrar(bp)
ed_visual_providers.registrar(bp)
import ed_social
ed_social.registrar(bp)
from ed_connectors import ADAPTERS
ADAPTERS.update(apify=ed_social.ApifyPublic(),openai_imagens=ed_images.OpenAIImages(),meta_discovery=ed_social.MetaDiscovery())
from ed_components import Components21st
ADAPTERS['twentyfirst']=Components21st()
import ed_runtime
ed_runtime.registrar(bp)
import ed_capabilities
ed_capabilities.registrar(bp)
import ed_library
ed_library.registrar(bp)
import ed_adaptive
ed_adaptive.registrar(bp)
import ed_vault
ed_vault.registrar(bp)
import ed_projects
ed_projects.registrar(bp)
import ed_image_export
ed_image_export.registrar(bp)
import ed_crm
ed_crm.registrar(bp)
import ed_workflows
ed_workflows.registrar(bp)
import ed_assistant
ed_assistant.registrar(bp)
import ed_voice
ed_voice.registrar(bp)
ADAPTERS['voz']=ed_voice.OpenAIVoice()
import ed_operations
ed_operations.registrar(bp)
import ed_destinations
ed_destinations.registrar(bp)
import ed_visual_research
ed_visual_research.registrar(bp)

import ed_delivery
ed_delivery.registrar(bp)
import ed_automation_drafts
ed_automation_drafts.registrar(bp)
import ed_batches
ed_batches.registrar(bp)
import ed_creation_providers
ed_creation_providers.registrar(bp)
import ed_opencode
ed_opencode.registrar(bp)

import ed_preview
ed_preview.registrar(bp)
import ed_site_refinement
ed_site_refinement.registrar(bp)
import ed_connected_research
ed_connected_research.registrar(bp)
