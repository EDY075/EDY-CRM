from ed_workspace import submit
"""Busca pequena e explícita em OSM; uma fonte por campanha, sem fallback pago."""
import json
import math
from concurrent.futures import ThreadPoolExecutor
from datetime import datetime, timezone
from threading import RLock

import requests

import ed_store as store

NICHOS = {
    'Salões de beleza': ('shop', 'hairdresser'), 'Barbearias': ('shop', 'hairdresser'),
    'Restaurantes': ('amenity', 'restaurant'), 'Cafeterias': ('amenity', 'cafe'),
    'Padarias': ('shop', 'bakery'), 'Pet shops': ('shop', 'pet'),
    'Academias': ('leisure', 'fitness_centre'), 'Clínicas': ('amenity', 'clinic'),
    'Dentistas': ('amenity', 'dentist'), 'Farmácias': ('amenity', 'pharmacy'),
    'Hotéis': ('tourism', 'hotel'), 'Oficinas': ('shop', 'car_repair'),
}
UFS = {'AC': 'Acre', 'AL': 'Alagoas', 'AP': 'Amapá', 'AM': 'Amazonas', 'BA': 'Bahia',
       'CE': 'Ceará', 'DF': 'Distrito Federal', 'ES': 'Espírito Santo', 'GO': 'Goiás',
       'MA': 'Maranhão', 'MT': 'Mato Grosso', 'MS': 'Mato Grosso do Sul', 'MG': 'Minas Gerais',
       'PA': 'Pará', 'PB': 'Paraíba', 'PR': 'Paraná', 'PE': 'Pernambuco', 'PI': 'Piauí',
       'RJ': 'Rio de Janeiro', 'RN': 'Rio Grande do Norte', 'RS': 'Rio Grande do Sul',
       'RO': 'Rondônia', 'RR': 'Roraima', 'SC': 'Santa Catarina', 'SP': 'São Paulo',
       'SE': 'Sergipe', 'TO': 'Tocantins'}
NOMINATIM = 'https://nominatim.openstreetmap.org/search'
# Instância documentada com uso permitido em qualquer projeto; FOSSGIS limita uso comercial.
OVERPASS = 'https://maps.mail.ru/osm/tools/overpass/api/interpreter'
HEADERS = {'User-Agent': 'EdCRM-local/0.1 (personal business research; https://github.com/nando0x/ProspectOS)',
           'Accept': 'application/json'}
executor = ThreadPoolExecutor(max_workers=1, thread_name_prefix='ed-pesquisa')
creation_lock = RLock()


def listar():
    with store.conectar() as con:
        return [dict(id=r['id'], **json.loads(r['dados'])) for r in con.execute(
            'SELECT * FROM ed_campanhas ORDER BY rowid DESC')]


def atualizar(ident, **changes):
    with store.conectar() as con:
        row = con.execute('SELECT dados FROM ed_campanhas WHERE id=?', (ident,)).fetchone()
        if not row:
            raise LookupError('Campanha não encontrada.')
        data = json.loads(row['dados'])
        data.update(changes)
        con.execute('UPDATE ed_campanhas SET dados=? WHERE id=?', (json.dumps(data, ensure_ascii=False), ident))
    return dict(id=ident, **data)


def ler(ident):
    found = next((x for x in listar() if x['id'] == ident), None)
    if not found:
        raise LookupError('Campanha não encontrada.')
    return found


def validar(data):
    if not isinstance(data, dict) or set(data) - {'nicho', 'cidade', 'uf', 'bairro', 'limite','prioridade'}:
        raise ValueError('Parâmetros de campanha inválidos.')
    if data.get('nicho') not in NICHOS:
        raise ValueError('Escolha um nicho suportado pela fonte OSM.')
    limit = data.get('limite', 10)
    if type(limit) is not int or not 1 <= limit <= 50:
        raise ValueError('Use um limite entre 1 e 50 empresas.')
    city = store.texto(data.get('cidade', ''), 120)
    state = store.texto(data.get('uf', ''), 2).upper()
    if not city or state not in UFS:
        raise ValueError('Informe cidade e uma UF válida.')
    priority=data.get('prioridade','padrao')
    if priority not in ('padrao','site_ausente','contato_disponivel'): raise ValueError('Critério de prioridade inválido.')
    return dict(nicho=data['nicho'], cidade=city, uf=state,
                bairro=store.texto(data.get('bairro', ''), 120), limite=limit,prioridade=priority)


def pode_iniciar():
    jobs = listar()
    with store.conectar() as con:
        operations = [json.loads(r['dados']) for r in con.execute('SELECT dados FROM ed_operacoes')]
    tests = [x for x in operations if x['fornecedor'] == 'osm']
    if any(x['estado'] in ('na_fila', 'pesquisando') for x in tests):
        raise ValueError('Um teste OpenStreetMap está em andamento. Aguarde ou cancele em Integrações.')
    if any(x['estado'] in ('na_fila', 'pesquisando') for x in jobs):
        raise ValueError('Uma busca já está em andamento. Aguarde ou cancele.')
    recent = [x.get('iniciado_em', x['criado_em']) for x in jobs]
    recent.extend(x['criado_em'] for x in tests)
    if recent and (datetime.now(timezone.utc) - datetime.fromisoformat(max(recent))).total_seconds() < 60:
        raise ValueError('A fonte permite apenas uma campanha por minuto neste app. Aguarde antes de repetir.')


def iniciar(data, app, idempotency_key=None):
    params = validar(data)
    with creation_lock:
        if idempotency_key:
            prior=next((j for j in listar() if j.get('chave')==idempotency_key),None)
            if prior:return prior
        pode_iniciar()
        ident = store.novo_id()
        job = dict(**params, estado='na_fila', mensagem='Aguardando pesquisa na fonte configurada.',
                   progresso=0, etapa='fila',
                   execucao_id=store.novo_id(), endpoint_overpass=OVERPASS,
                   chave=idempotency_key,criado_em=store.agora(), iniciado_em=store.agora(), encontrados=0, novos=0,
                   repetidos=0, empresa_ids=[], fonte='OpenStreetMap', cobertura='Limitada aos estabelecimentos mapeados.')
        with store.conectar() as con:
            con.execute('INSERT INTO ed_campanhas VALUES (?,?)', (ident, json.dumps(job, ensure_ascii=False)))
    if app.config['RUN_JOBS']:
        submit(executor,executar, app, ident, job['execucao_id'])
    return dict(id=ident, **job)


def acionar(ident, action, app):
    with creation_lock:
        job = ler(ident)
        if action == 'cancelar' and job['estado'] in ('na_fila', 'pesquisando'):
            return atualizar(ident, estado='cancelada', mensagem='Cancelada. Registros já coletados foram preservados.')
    if action == 'retomar' and job['estado'] in ('cancelada', 'erro', 'interrompida', 'parcial', 'sem_resultados'):
        if not store.config()['osm_habilitado']:
            raise ValueError('Ative a fonte antes de retomar.')
        with creation_lock:
            pode_iniciar()
            updated = atualizar(ident, estado='na_fila', iniciado_em=store.agora(),
                                 progresso=0, etapa='fila',
                                 execucao_id=store.novo_id(), endpoint_overpass=OVERPASS, mensagem='Retomada solicitada.',historico_execucoes=job.get('historico_execucoes',[])+[{k:job.get(k) for k in ('estado','execucao_id','iniciado_em','mensagem','encontrados','novos','repetidos')}])
        if app.config['RUN_JOBS']:
            submit(executor,executar, app, ident, updated['execucao_id'])
        return updated
    raise ValueError('Ação indisponível para esta campanha.')


def obter_json(method, endpoint, **kwargs):
    # Destinos fixos e sem redirects: dados externos não escolhem URLs de fetch.
    with requests.request(method, endpoint, headers=HEADERS, timeout=(10, 45),
                          allow_redirects=False, stream=True, **kwargs) as response:
        if response.status_code in (429, 503, 504):
            raise ValueError(f'Fonte temporariamente indisponível ou limitada: HTTP {response.status_code} em {endpoint}. Tente retomar mais tarde.')
        if response.status_code != 200:
            raise ValueError(f'Fonte respondeu com HTTP {response.status_code}. Nenhum resultado foi simulado.')
        content = bytearray()
        for chunk in response.iter_content(64 * 1024):
            content.extend(chunk)
            if len(content) > 4 * 1024 * 1024:
                raise ValueError('Resposta acima do limite local. Restrinja a busca por bairro.')
        try:
            return json.loads(content)
        except (ValueError, UnicodeError) as exc:
            raise ValueError('A fonte retornou um formato inesperado.') from exc


def localizar(job):
    key = 'geo:' + store.normalizar(job['cidade'] + job['uf'])
    with store.conectar() as con:
        row = con.execute('SELECT valor FROM ed_config WHERE chave=?', (key,)).fetchone()
    if row:
        return json.loads(row['valor'])
    params = dict(city=job['cidade'], state=UFS[job['uf']], country='Brazil',
                  countrycodes='br', format='jsonv2', limit=1, addressdetails=1)
    # Bairro é uma restrição textual adicional na consulta Overpass, sem segunda geocodificação.
    locations = obter_json('GET', NOMINATIM, params=params)
    if not isinstance(locations, list) or not locations:
        raise ValueError('Localidade não encontrada. Confira cidade e UF.')
    box = [float(x) for x in locations[0]['boundingbox']]
    south, north, west, east = box
    if not all(math.isfinite(x) for x in box) or not (-90 <= south < north <= 90 and -180 <= west < east <= 180):
        raise ValueError('A fonte retornou limites geográficos inválidos.')
    if north - south > 2 or east - west > 2:
        raise ValueError('Área municipal muito grande para a fonte pública nesta versão. Use cadastro manual.')
    with store.conectar() as con:
        con.execute('INSERT OR REPLACE INTO ed_config VALUES (?,?)', (key, json.dumps(box)))
    return box


def consultar(job):
    def progress(value,phase,message):
        if job.get('id'):atualizar_execucao(job['id'],job['execucao_id'],progresso=value,etapa=phase,mensagem=message)
    progress(10,'localidade','Localizando cidade e estado no OpenStreetMap…')
    south, north, west, east = localizar(job)
    key, value = NICHOS[job['nicho']]
    query = f'[out:json][timeout:30];nwr["{key}"="{value}"]["name"]({south},{west},{north},{east});out tags {job["limite"] * 4};'
    progress(30,'consulta','Consultando estabelecimentos. Aguardando resposta do servidor Overpass…')
    data = obter_json('POST', OVERPASS, data={'data': query})
    progress(65,'resultados','Resposta recebida. Validando os registros da fonte…')
    if not isinstance(data, dict) or not isinstance(data.get('elements'), list):
        raise ValueError('Resposta da busca inválida.')
    elements = data['elements']
    if job.get('bairro'):
        # OSM nem sempre preenche bairro: não assumir que resultados são daquela área.
        elements = [x for x in elements if store.normalizar(job['bairro']) in store.normalizar(
            x.get('tags', {}).get('addr:suburb', '') + ' ' + x.get('tags', {}).get('addr:neighbourhood', ''))]
    if job.get('prioridade')=='site_ausente':
        elements.sort(key=lambda x:bool(x.get('tags',{}).get('website') or x.get('tags',{}).get('contact:website')))
    elif job.get('prioridade')=='contato_disponivel':
        elements.sort(key=lambda x:not bool(x.get('tags',{}).get('phone') or x.get('tags',{}).get('contact:phone')))
    return elements[:job['limite']], bool(data.get('remark'))


def converter(element, job):
    tags = element['tags']
    if element['type'] not in ('node', 'way', 'relation') or not isinstance(element['id'], int):
        raise ValueError('Identificador OSM inválido.')
    origin = f'https://www.openstreetmap.org/{element["type"]}/{element["id"]}'
    def text(key):
        return str(tags.get(key, ''))[:500]
    def link(key, other):
        value = text(key) or text(other)
        if value and not value.startswith(('http://', 'https://')):
            value = 'https://' + value
        try:
            return store.url(value)
        except ValueError:
            return ''
    return dict(nome=text('name'), nicho=job['nicho'], cidade=job['cidade'], uf=job['uf'],
                bairro=text('addr:suburb') or text('addr:neighbourhood'),
                endereco=', '.join(filter(None, [text('addr:street'), text('addr:housenumber')])),
                telefone=text('contact:phone') or text('phone'),
                site=link('contact:website', 'website'), instagram=link('contact:instagram', 'instagram'),
                horarios=text('opening_hours'), fonte_url=origin)


def execucao_ativa(ident, execucao_id):
    current = ler(ident)
    return current['estado'] == 'pesquisando' and current.get('execucao_id') == execucao_id


def atualizar_execucao(ident, execucao_id, **changes):
    with creation_lock:
        if execucao_ativa(ident, execucao_id):
            return atualizar(ident, **changes)
    return None


def executar(app, ident, execucao_id=None):
    with app.app_context():
        with creation_lock:
            current = ler(ident)
            execucao_id = execucao_id or current.get('execucao_id')
            if current['estado'] != 'na_fila' or current.get('execucao_id') != execucao_id:
                return
            job = atualizar(ident, estado='pesquisando', progresso=5,etapa='inicio', mensagem='Iniciando consulta à fonte configurada…')
        try:
            from ed_connectors import ADAPTERS
            elements, partial = ADAPTERS['osm'].discover(job)
            ids = list(job['empresa_ids'])
            new, repeated = job['novos'], job['repetidos']
            for element in elements:
                with creation_lock:
                    if not execucao_ativa(ident, execucao_id):
                        return
                    values = converter(element, job)
                    lead, created = store.gravar_empresa(values, fonte_id=f'osm:{element["type"]}/{element["id"]}',
                                                         fornecedor='OpenStreetMap')
                    if lead['id'] not in ids:
                        ids.append(lead['id'])
                    new += int(created)
                    repeated += int(not created)
                    atualizar_execucao(ident, execucao_id, empresa_ids=ids, encontrados=len(ids), novos=new,
                        repetidos=repeated, progresso=70+int((new+repeated)/(max(1,len(elements))+job['novos']+job['repetidos'])*25),etapa='organizando', mensagem=f'{len(ids)} empresas relacionadas à campanha.')
            atualizar_execucao(ident, execucao_id, estado='sem_resultados' if not elements else 'parcial' if partial else 'concluida',
                           progresso=100,etapa='encerrada',
                           mensagem=f'{len(elements)} resultados nesta consulta; cobertura limitada ao OSM. '
                           'Site ausente no cadastro não confirma ausência de site. '
                           + ('A fonte informou coleta parcial.' if partial else 'Confira identidade e contatos.'))
        except (requests.RequestException, ValueError, KeyError, TypeError) as exc:
            message = str(exc) if isinstance(exc, ValueError) else 'Falha de rede ou formato na fonte. Tente retomar depois.'
            atualizar_execucao(ident, execucao_id, estado='erro', mensagem=message,erro_tipo='http' if 'HTTP ' in message else 'rede' if isinstance(exc,requests.RequestException) else 'interpretacao')
