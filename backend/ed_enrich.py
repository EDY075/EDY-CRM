from ed_workspace import submit
"""Leitura limitada de sites públicos. HTML é dado, nunca código/instrução.

Sugestões não alteram a ficha. TLS validado; conexão fixada no IP público
resolvido para impedir DNS rebinding. Sem cookies, proxies, login ou JS.
"""
import io
import hashlib
import ipaddress
import json
import re
import socket
import time
import warnings
from concurrent.futures import ThreadPoolExecutor
from threading import Lock, RLock
from urllib.parse import parse_qs, unquote, urljoin, urlsplit, urlunsplit
from ed_robots import Policy

import certifi
import urllib3
from flask import current_app, jsonify, request, send_file
from lxml import html as html_parser
from PIL import Image, UnidentifiedImageError

import ed_store as store

pool = ThreadPoolExecutor(max_workers=2, thread_name_prefix='ed-site')
lock = RLock()
image_locks = {}
AGENT = 'EdCRM/0.2 (public website research; local human review)'
MAX_PAGES = 4


class ReadError(ValueError):
    def __init__(self, message, tipo, http_status=None):
        super().__init__(message)
        self.tipo, self.http_status = tipo, http_status


def error_detail(exc, url, etapa):
    message = str(exc)[:600]
    status = getattr(exc, 'http_status', None)
    match = re.search(r'HTTP (\d{3})\b', message)
    status = status or (int(match[1]) if match else None)
    kind = getattr(exc, 'tipo', None) or ('http' if status else 'rede' if any(x in message.lower() for x in ('conexão', 'timeout', 'tls', 'domínio não resolvido')) else 'interpretacao')
    return dict(url=url, mensagem=message, tipo=kind, etapa=etapa, http_status=status, **getattr(exc, 'evidencia', {}))


def robots_checker(job):
    cache = {}
    job['robots'] = dict(user_agent=AGENT, parser='Protego 0.6.2', documentos=[], avaliacoes=[])

    def check(page):
        p = urlsplit(page)
        origin = urlunsplit((p.scheme, p.netloc, '', '', ''))
        robots_url = origin + '/robots.txt'
        if origin not in cache:
            document = dict(url=robots_url, consultado_em=store.agora())
            job['robots']['documentos'].append(document)
            try:
                response_info = {}
                final, content, media = ler_url(robots_url, limite=128000, site=job['site'], resposta=response_info)
                text = content.decode('utf-8-sig', 'replace')
                document.update(url_final=final, http_status=response_info.get('http_status', 200), sha256=hashlib.sha256(content).hexdigest())
                if re.search(r'<(?:!doctype\s+html|html|body)\b', text, re.I) or ('html' in media.lower() and not re.search(r'^\s*user-agent\s*:', text, re.I | re.M)):
                    raise ReadError('robots.txt retornou HTML em vez de regras; não foi possível verificar a política.', 'interpretacao')
                policy = Policy(text)
                document['estado'] = 'verificado'
            except ValueError as exc:
                detail = error_detail(exc, robots_url, 'robots')
                document.update(http_status=detail['http_status'], estado='ausente' if detail['http_status'] == 404 else 'erro')
                if detail['http_status'] == 404:
                    policy = Policy('')
                else:
                    failure = ReadError('Não foi possível verificar robots.txt: ' + detail['mensagem'], detail['tipo'], detail['http_status'])
                    failure.evidencia = {'robots_url': robots_url}
                    raise failure from exc
            cache[origin] = policy
        policy = cache[origin]
        evidence = {**policy.check(page, AGENT), 'robots_url': robots_url, 'user_agent': AGENT}
        if evidence not in job['robots']['avaliacoes']:
            job['robots']['avaliacoes'].append(evidence)
        if not evidence['permitido']:
            failure = ReadError(f'Leitura bloqueada por robots.txt: {evidence["regra"]} no grupo {evidence["grupo"]}, para {evidence["caminho"]}.', 'robots_regra')
            failure.evidencia = {k: evidence[k] for k in ('robots_url', 'user_agent', 'regra', 'grupo', 'caminho')}
            raise failure
        return policy.delay(AGENT)
    return check


def javascript_possible(content):
    # Indício, não diagnóstico garantido: não executar scripts do site.
    tree = html_parser.fromstring(content, parser=html_parser.HTMLParser(no_network=True))
    scripts = bool(tree.xpath('//script[@src]'))
    for node in tree.xpath('//script|//style|//noscript|//template'):
        node.drop_tree()
    return scripts and len(limpo(tree.text_content())) < 120


def destino(url):
    parsed = urlsplit(url)
    if parsed.scheme not in ('https', 'http') or not parsed.hostname or parsed.username or parsed.password:
        raise ValueError('Somente sites http/https públicos, sem credenciais.')
    if parsed.port not in (None, 80 if parsed.scheme == 'http' else 443):
        raise ValueError('Porta de rede não permitida.')
    host = parsed.hostname.encode('idna').decode('ascii')
    try:
        ips = sorted({info[4][0] for info in socket.getaddrinfo(host, parsed.port or (443 if parsed.scheme == 'https' else 80), type=socket.SOCK_STREAM)})
    except OSError as exc:
        raise ReadError('Domínio não resolvido. Confira o site e tente novamente.', 'rede') from exc
    if not ips or any(not ipaddress.ip_address(ip).is_global for ip in ips):
        raise ValueError('Endereços locais, privados e reservados não são permitidos.')
    return parsed, host, ips[0]


def mesma_empresa(a, b):
    # Só o host confirmado e sua variante www; não confiar em sufixos de domínio.
    return urlsplit(a).hostname.removeprefix('www.') == urlsplit(b).hostname.removeprefix('www.')


def ler_url(url, limite=2 * 1024 * 1024, site=None, antes_de_ler=None, resposta=None):
    for _ in range(4):
        parsed, host, ip = destino(url)
        if site and not mesma_empresa(site, url):
            raise ValueError('Redirecionamento saiu do site confirmado; confira a URL final manualmente.')
        if antes_de_ler:
            antes_de_ler(url)
        connection = (urllib3.HTTPSConnectionPool(ip, port=parsed.port or 443,
                      server_hostname=host, assert_hostname=host, cert_reqs='CERT_REQUIRED', ca_certs=certifi.where())
                      if parsed.scheme == 'https' else urllib3.HTTPConnectionPool(ip, port=parsed.port or 80))
        response = None
        started = time.monotonic()
        try:
            response = connection.request('GET', urlunsplit(('', '', parsed.path or '/', parsed.query, '')),
                headers={'Host': host, 'User-Agent': AGENT, 'Accept': 'text/html,image/png,image/jpeg,image/webp,*/*;q=.5', 'Accept-Encoding': 'identity'},
                timeout=urllib3.Timeout(connect=5, read=8), retries=False, redirect=False, preload_content=False)
            if resposta is not None:
                resposta.update(http_status=response.status, url_final=url)
            if response.status in (301, 302, 303, 307, 308):
                url = urljoin(url, response.headers.get('Location', ''))
                continue
            if response.status >= 400:
                raise ReadError(f'HTTP {response.status}; não foi possível ler esta página. Cadastro manual disponível.', 'http', response.status)
            if response.headers.get('Content-Encoding', 'identity').lower() not in ('', 'identity'):
                raise ValueError('O servidor ignorou a solicitação de conteúdo sem compressão; use cadastro manual.')
            content = bytearray()
            while True:
                if time.monotonic() - started > 18:
                    raise ReadError('Tempo máximo de leitura excedido; tente novamente ou use cadastro manual.', 'rede')
                chunk = response.read1(min(65536, limite + 1 - len(content)), decode_content=False)
                if not chunk:
                    break
                content.extend(chunk)
                if len(content) > limite:
                    raise ValueError('Conteúdo excede o limite de leitura.')
            return url, bytes(content), response.headers.get('Content-Type', '')
        except urllib3.exceptions.HTTPError as exc:
            raise ReadError('Falha de conexão, timeout ou certificado TLS; sem contornar a proteção do site.', 'rede') from exc
        finally:
            if response:
                response.close()
            connection.close()
    raise ValueError('Redirecionamentos demais; revise o site manualmente.')


def publico_sintatico(url):
    """Filtro barato na extração; DNS/IP é validado e fixado somente ao buscar."""
    try:
        if len(url) > 2000:
            return False
        p = urlsplit(url)
        if p.scheme not in ('http', 'https') or not p.hostname or p.username or p.password or p.port not in (None, 80, 443):
            return False
        host = p.hostname
        if host == 'localhost' or host.endswith(('.local', '.localhost')):
            return False
        try:
            return ipaddress.ip_address(host).is_global
        except ValueError:
            return '.' in host
    except ValueError:
        return False


def limpo(value, limit=4000):
    return re.sub(r'\s+', ' ', str(value)).strip()[:limit]


def extrair(url, content):
    tree = html_parser.fromstring(content, parser=html_parser.HTMLParser(no_network=True))
    result = {'sugestoes': [], 'imagens': [], 'paginas': []}
    def sugerir(field, value, evidence, method):
        value = limpo(value, 4000 if field in ('descricao', 'servicos', 'redes_sociais') else 500)
        if value and not any(x['campo'] == field and x['valor'] == value for x in result['sugestoes']):
            result['sugestoes'].append(dict(id=store.novo_id(), campo=field, valor=value, origem=url,
                evidencia=limpo(evidence, 700), metodo=method, requer_confirmacao=True, aplicado=False))
    nodes = []
    def walk(node, depth=0):
        if depth > 15:
            return
        if isinstance(node, dict):
            nodes.append(node)
            for val in node.values():
                if isinstance(val, (dict, list)):
                    walk(val, depth + 1)
        elif isinstance(node, list):
            for item in node[:100]:
                walk(item, depth + 1)
    for raw in tree.xpath('//script[@type="application/ld+json"]/text()')[:10]:
        try:
            if len(raw) < 100000:
                walk(json.loads(raw))
        except (ValueError, RecursionError):
            pass
    descriptions = tree.xpath('//meta[translate(@name,"ABCDEFGHIJKLMNOPQRSTUVWXYZ","abcdefghijklmnopqrstuvwxyz")="description"]/@content | //meta[@property="og:description"]/@content')
    if descriptions:
        sugerir('descricao', descriptions[0], descriptions[0], 'Descrição publicada na página')
    for node in nodes:
        kind = node.get('@type', '')
        if isinstance(kind, str) and (kind in ('LocalBusiness', 'Organization', 'Restaurant', 'Bakery', 'Store', 'Dentist', 'Hotel', 'MedicalClinic', 'BeautySalon', 'ProfessionalService') or node.get('address')):
            for field, prop in [('descricao', 'description'), ('telefone', 'telephone'), ('email', 'email'), ('horarios', 'openingHours')]:
                val = node.get(prop)
                if isinstance(val, (str, list)):
                    text = '; '.join(str(x) for x in val if isinstance(x, str)) if isinstance(val, list) else val
                    sugerir(field, text, text, 'Dados estruturados JSON-LD')
            address = node.get('address')
            if isinstance(address, dict):
                text = ', '.join(str(address.get(k, '')) for k in ('streetAddress', 'addressLocality', 'addressRegion', 'postalCode') if isinstance(address.get(k), str))
                sugerir('endereco', text, text, 'Endereço JSON-LD; conferir filial')
            elif isinstance(address, str):
                sugerir('endereco', address, address, 'Endereço JSON-LD')
            hours = node.get('openingHoursSpecification')
            if isinstance(hours, dict):
                hours = [hours]
            if isinstance(hours, list):
                lines = []
                for h in hours[:14]:
                    if isinstance(h, dict) and isinstance(h.get('opens'), str) and isinstance(h.get('closes'), str):
                        day = h.get('dayOfWeek', [])
                        day = day if isinstance(day, list) else [day]
                        lines.append(', '.join(str(x).split('/')[-1] for x in day) + f': {h["opens"]}–{h["closes"]}')
                sugerir('horarios', '; '.join(lines), '; '.join(lines), 'Horários JSON-LD')
        if kind in ('Service', 'Offer') and isinstance(node.get('name'), str):
            sugerir('servicos', node['name'], node['name'], 'Serviço/oferta JSON-LD; confirmar disponibilidade')
    for element in tree.xpath('//script|//style|//noscript|//template'):
        element.drop_tree()
    socials = []
    links = [(a.get('href', ''), limpo(a.text_content(), 250)) for a in tree.xpath('//a[@href]')[:500]]
    # sameAs também pode declarar canais no site, sem acesso ao Instagram.
    for n in nodes:
        same = n.get('sameAs', [])
        for link in ([same] if isinstance(same, str) else same if isinstance(same, list) else []):
            if isinstance(link, str):
                links.append((link, 'sameAs JSON-LD'))
    for href, label in links:
        if href.startswith('tel:'):
            sugerir('telefone', unquote(href[4:].split('?')[0]), href, 'Link de contato do site')
        if href.startswith('mailto:'):
            sugerir('email', href[7:].split('?')[0], href, 'E-mail do site')
        absolute = urljoin(url, href).split('#')[0]
        if not publico_sintatico(absolute):
            continue
        p = urlsplit(absolute)
        host = p.hostname.removeprefix('www.')
        match = re.fullmatch(r'/([A-Za-z0-9_.]+)/?', p.path)
        if host == 'instagram.com' and match and match[1].lower() not in ('p', 'reel', 'reels', 'tv', 'explore', 'accounts', 'stories', 'direct'):
            canonical = f'https://www.instagram.com/{match[1]}/'
            sugerir('instagram', canonical, f'Link publicado no site confirmado: {href}; {label}', 'Vínculo publicado no site; identidade do perfil a confirmar')
        if host in ('facebook.com', 'linkedin.com', 'youtube.com', 'tiktok.com', 'x.com', 'instagram.com'):
            socials.append(absolute)
        if host in ('wa.me', 'api.whatsapp.com'):
            phone = p.path.strip('/') if host == 'wa.me' else parse_qs(p.query).get('phone', [''])[0]
            digits = re.sub(r'\D', '', phone)
            if 8 <= len(digits) <= 15:
                sugerir('telefone', f'https://wa.me/{digits}', f'Canal WhatsApp publicado no site: {digits}', 'Canal WhatsApp publicado no site')
        if mesma_empresa(url, absolute) and re.search(r'servi[cç]|sobre|quem.somos|contat|about|service|contact|produto|menu|cardap', p.path + ' ' + label, re.I):
            if absolute not in result['paginas'] and not re.search(r'\.(pdf|jpg|png|zip|mp4)$', p.path, re.I):
                result['paginas'].append(absolute)
    if socials:
        sugerir('redes_sociais', '\n'.join(dict.fromkeys(socials))[:4000], '; '.join(dict.fromkeys(socials)), 'Links sociais publicados no site')
    # Texto conservador: cada trecho é uma sugestão, sem deduzir serviço pela categoria.
    texts = [limpo(' '.join(e.itertext()), 600) for e in tree.xpath('//address|//p|//li|//h2|//h3')[:350]]
    if not any(x['campo'] == 'descricao' for x in result['sugestoes']):
        paragraphs = [limpo(' '.join(e.itertext()), 900) for e in tree.xpath('//p[not(ancestor::nav) and not(ancestor::header) and not(ancestor::footer)]')[:150]]
        description = next((t for t in paragraphs if 50 < len(t) < 900 and re.search(r'somos|fundad|oferece|conectar|miss[aã]o|nossa empresa|nosso compromisso', t, re.I)), '')
        sugerir('descricao', description, description, 'Descrição no texto visível; revisar afirmações comerciais')
    if not any(x['campo'] == 'endereco' for x in result['sugestoes']):
        address = next((t for t in texts if re.search(r'\b(rua|avenida|av\.|r\.|estrada|rodovia|alameda|praça)\s+\S', t, re.I) and re.search(r'\d', t) and len(t) < 500), '')
        sugerir('endereco', address, address, 'Trecho visível com endereço; confirmar filial')
    hours = next((t for t in texts if re.search(r'(seg[au]|segunda|hor[aá]rio|funcionamento|segunda.feira)', t, re.I) and re.search(r'\d{1,2}[:h]\d{0,2}', t) and len(t) < 500), '')
    sugerir('horarios', hours, hours, 'Trecho visível de horários')
    if not hours:
        hours = next((t for t in texts if len(t) < 200 and re.search(r'\b24\s*(?:h|horas|hrs)\b', t, re.I)), '')
        sugerir('horarios', hours, hours, 'Horário no texto visível; conferir unidade e serviço')
    visible = limpo(tree.text_content(), 20000)
    for email in list(dict.fromkeys(re.findall(r'[\w.+-]+@[\w.-]+\.[a-zA-Z]{2,}', visible)))[:3]:
        sugerir('email', email, email, 'Contato no texto visível')
    if not any(x['campo'] == 'telefone' for x in result['sugestoes']):
        phone = re.search(r'(?:\+55\s*)?\(?\d{2}\)?[\s.-]+\d{4,5}[\s.-]\d{4}\b', visible)
        if phone:
            sugerir('telefone', phone[0], phone[0], 'Contato no texto visível')
    if re.search(r'servi|service|produto|menu|cardap', urlsplit(url).path, re.I):
        headers = [limpo(' '.join(e.itertext()), 180) for e in tree.xpath('//h2[not(ancestor::nav) and not(ancestor::header) and not(ancestor::footer)]|//h3[not(ancestor::nav) and not(ancestor::header) and not(ancestor::footer)]')[:50]]
        headers = list(dict.fromkeys(t for t in headers if 3 < len(t) < 180 and not re.search(r'contato|onde estamos|sobre n[oó]s|not[ií]cias|menu|siga|redes sociais|clientes dizem|depoimento|servi[cç]os .*qualidade', t, re.I)))[:16]
        sugerir('servicos', '; '.join(headers), '; '.join(headers), 'Trechos da página de serviços; revisar navegação e ofertas')
    images = [(e.get('src') or e.get('data-src') or (e.get('srcset', '').split(',')[0].strip().split(' ')[0]), e.get('alt', '')) for e in tree.xpath('//img')[:100]]
    images += [(x, 'Imagem de compartilhamento') for x in tree.xpath('//meta[@property="og:image"]/@content')[:2]]
    for src, alt in images:
        candidate = urljoin(url, src)
        if not src or not publico_sintatico(candidate) or urlsplit(candidate).path.lower().endswith(('.gif', '.ico')):
            continue
        if any(x['url'] == candidate for x in result['imagens']):
            continue
        text = (alt + ' ' + urlsplit(candidate).path).lower()
        category = next((cat for cat, pattern in [('logo', r'logo|marca|brand'), ('fachada', r'fachada|exterior|front'), ('ambiente', r'ambiente|interior|sala|room'), ('produto', r'produto|product|prato|food|cake')] if re.search(pattern, text)), 'referencia')
        result['imagens'].append(dict(id=store.novo_id(), url=candidate, origem=url, descricao=limpo(alt, 300), categoria=category,
            autorizado=False, selecionado=False, aviso='Categoria sugerida; verificar identidade e direitos antes de exportar.'))
    return result


def ler_job(ident):
    with store.conectar() as con:
        row = con.execute('SELECT dados FROM ed_pesquisas WHERE id=?', (ident,)).fetchone()
    if not row:
        raise LookupError('Pesquisa não encontrada.')
    return json.loads(row['dados'])


def salvar_job(job):
    job['atualizado_em'] = store.agora()
    with lock, store.conectar() as con:
        row = con.execute('SELECT dados FROM ed_pesquisas WHERE id=?', (job['id'],)).fetchone()
        if row and json.loads(row['dados'])['estado'] in ('cancelada', 'interrompida'):
            return False
        con.execute('UPDATE ed_pesquisas SET dados=? WHERE id=?', (json.dumps(job, ensure_ascii=False), job['id']))
        return True


def ultima(empresa):
    store.ler_empresa(empresa)
    with store.conectar() as con:
        row = con.execute('SELECT dados FROM ed_pesquisas WHERE empresa_id=? ORDER BY rowid DESC LIMIT 1', (empresa,)).fetchone()
    if not row:
        return None
    job = json.loads(row['dados'])
    with store.conectar() as con:
        diagnostic = con.execute('SELECT valor FROM ed_config WHERE chave=?', ('diagnostico:pesquisa:' + job['id'],)).fetchone()
    if diagnostic:
        job['diagnostico_atual'] = json.loads(diagnostic['valor'])
    return job


def diagnosticar(empresa, ident):
    """Somente robots.txt. Não reconfirma site, coleta HTML ou altera a execução."""
    job = ler_job(ident)
    if job['empresa_id'] != empresa:
        raise LookupError('Pesquisa de outra empresa.')
    result = dict(site=job['site'], consultado_em=store.agora(), pesquisa_id=ident, erros=[])
    try:
        robots_checker(result)(job['site'])
        result.update(estado='permitida', mensagem='A política atual permite a URL inicial para este coletor. Isso não confirma a identidade da empresa nem a disponibilidade de conteúdo. Revise o site antes de uma nova pesquisa.')
    except ValueError as exc:
        detail = error_detail(exc, job['site'], 'robots')
        result.update(estado='bloqueada' if detail['tipo'] == 'robots_regra' else 'erro', mensagem=detail['mensagem'], erros=[detail])
    with store.conectar() as con:
        con.execute('INSERT INTO ed_config VALUES (?,?) ON CONFLICT(chave) DO UPDATE SET valor=excluded.valor',
                    ('diagnostico:pesquisa:' + ident, json.dumps(result, ensure_ascii=False)))
    return result


def iniciar(empresa, data, app, idempotency_key=None):
    if not isinstance(data, dict) or set(data) - {'site_confirmado', 'site', 'fornecedor'} or not {'site_confirmado', 'site'} <= set(data) or data['site_confirmado'] is not True:
        raise ValueError('Confirme que o site pertence a esta empresa antes da pesquisa.')
    provider = data.get('fornecedor', 'site_local')
    if provider not in ('site_local', 'firecrawl'):
        raise ValueError('Fornecedor de enriquecimento inválido.')
    if provider == 'firecrawl':
        from ed_secrets import get
        if not get('firecrawl'):
            raise ValueError('Firecrawl sem credencial. Escolha Leitura local para continuar.')
    lead = store.ler_empresa(empresa)
    if data['site'] != lead['site']:
        raise ValueError('O site foi alterado. Atualize a tela e confirme a URL novamente.')
    if not lead['site'] or not publico_sintatico(lead['site']):
        raise ValueError('Cadastre um site público válido na ficha.')
    from ed_sites import classificar
    if classificar(lead['site'])['tipo'] != 'candidato':
        raise ValueError('Busca, mapa ou URL genérica não pode ser site oficial. Revise a associação na ficha.')
    with lock:
        if idempotency_key:
            with store.conectar() as con:
                for row in con.execute('SELECT dados FROM ed_pesquisas WHERE empresa_id=?',(empresa,)):
                    prior=json.loads(row['dados'])
                    if prior.get('chave')==idempotency_key:return prior
        previous = ultima(empresa)
        if previous and previous['estado'] in ('na_fila', 'pesquisando'):
            return None
        job = dict(id=store.novo_id(), chave=idempotency_key,empresa_id=empresa, site=lead['site'], fornecedor=provider, estado='na_fila', mensagem='Aguardando leitura do site confirmado.',
            criado_em=store.agora(), atualizado_em=store.agora(), paginas=[], sugestoes=[], imagens=[], erros=[], progresso=0,
            pendencias=['Confirmar informações atuais e filial; associação do Instagram depende de revisão.', 'Direitos de imagens não são concedidos pela presença no site.'])
        with store.conectar() as con:
            row = con.execute('SELECT dados FROM ed_empresas WHERE id=?', (empresa,)).fetchone()
            base = json.loads(row['dados'])
            if base['site'] != data['site']:
                raise ValueError('O site foi alterado. Atualize a tela e confirme novamente.')
            base['fontes']['site'] = {**base['fontes'].get('site', store.fonte('site', base['site'], 'manual', base['site'])),
                'verificacao': 'confirmado_usuario', 'revisado_em': store.agora()}
            base['associacao_site'] = dict(estado='confirmado', url=base['site'], motivo='Associação confirmada explicitamente para a pesquisa.',
                evidencias=base.get('associacao_site', {}).get('evidencias', []))
            saved = con.execute('UPDATE ed_empresas SET dados=?,atualizado_em=? WHERE id=? AND dados=?', (json.dumps(base, ensure_ascii=False), store.agora(), empresa, row['dados']))
            if not saved.rowcount:
                raise ValueError('A ficha mudou. Atualize a tela antes de pesquisar.')
            con.execute('INSERT INTO ed_pesquisas VALUES (?,?,?)', (job['id'], empresa, json.dumps(job)))
        if app.config.get('RUN_SITE_JOBS', app.config['RUN_JOBS']):
            submit(pool,executar, app, job['id'])
        return job


def executar(app, ident):
    with app.app_context():
        job = ler_job(ident)
        if job['estado'] != 'na_fila':
            return
        job.update(estado='pesquisando', mensagem='Conferindo robots.txt e lendo a página inicial.')
        if not salvar_job(job):
            return
        started = time.monotonic()
        try:
            root = job['site']
            check = robots_checker(job)
            delay = 1
            queue = [root]
            while queue and len(job['paginas']) < MAX_PAGES and time.monotonic() - started < 75:
                if ler_job(ident)['estado'] in ('cancelada', 'interrompida'):
                    return
                page = queue.pop(0)
                if any(x['url'] == page for x in job['paginas']):
                    continue
                job['mensagem'] = f'Lendo página {len(job["paginas"])+1} de até {MAX_PAGES}: {urlsplit(page).path or "/"}'
                if not salvar_job(job):
                    return
                try:
                    delay = check(page)
                    if delay > 10:
                        raise ReadError('O site exige um intervalo de coleta maior que esta pesquisa suporta. Use cadastro manual.', 'limite')
                    if job.get('fornecedor') == 'firecrawl':
                        from ed_connectors import ADAPTERS
                        final, content, media = ADAPTERS['firecrawl'].scrape(page)
                        check(final)
                    else:
                        final, content, media = ler_url(page, site=root, antes_de_ler=check)
                    if media and 'html' not in media:
                        raise ReadError('A página não retornou HTML.', 'conteudo')
                    extracted = extrair(final, content)
                    job['paginas'].append({'url': page, 'url_final': final, 'estado': 'lida', 'consultado_em': store.agora(), 'bytes': len(content),
                                          'javascript_possivel': javascript_possible(content), 'fornecedor': job.get('fornecedor', 'site_local')})
                    for s in extracted['sugestoes']:
                        if len(job['sugestoes']) < 40 and not any(x['campo'] == s['campo'] and x['valor'] == s['valor'] for x in job['sugestoes']):
                            job['sugestoes'].append(s)
                    for image in extracted['imagens']:
                        if len(job['imagens']) < 12 and not any(x['url'] == image['url'] for x in job['imagens']):
                            image['previa_url'] = f'/api/ed/empresas/{job["empresa_id"]}/pesquisas/{ident}/imagens/{image["id"]}'
                            job['imagens'].append(image)
                    queue.extend(x for x in extracted['paginas'][:10] if x not in queue)
                except (ValueError, TypeError, html_parser.etree.ParserError) as exc:
                    job['paginas'].append({'url': page, 'estado': 'erro'})
                    stage = 'robots' if getattr(exc, 'evidencia', {}).get('robots_url') else 'pagina'
                    job['erros'].append(error_detail(exc, page, stage))
                job['progresso'] = min(95, len(job['paginas']) * 25)
                if not salvar_job(job):
                    return
                if queue:
                    time.sleep(delay)
            good = sum(x['estado'] == 'lida' for x in job['paginas'])
            results = bool(job['sugestoes'] or job['imagens'])
            state = ('parcial' if job['erros'] else 'concluida') if good and results else 'sem_resultados' if good else 'erro'
            message = f'{good} páginas lidas; {len(job["sugestoes"])} sugestões e {len(job["imagens"])} imagens candidatas. Revise antes de aplicar.'
            if not good:
                message = 'Nenhuma página lida. Pesquisa não concluída. ' + (job['erros'][0]['mensagem'] if job['erros'] else 'Nenhum conteúdo acessível.')
            elif not results:
                message = f'{good} páginas lidas, sem informações comerciais ou imagens extraíveis. Pesquisa sem resultados.'
                if any(p.get('javascript_possivel') for p in job['paginas']):
                    message += ' Conteúdo possivelmente dependente de JavaScript; confirme no navegador ou tente Firecrawl configurado.'
            job.update(estado=state, progresso=100, mensagem=message)
        except Exception as exc:
            job.update(estado='erro', mensagem='Pesquisa interrompida; informações manuais preservadas.', progresso=100)
            job['erros'].append(error_detail(exc, job['site'], 'pagina'))
        if salvar_job(job) and job.get('fornecedor') == 'firecrawl':
            from ed_services import fingerprint, log
            log('firecrawl', dict(estado='conectado' if job['estado'] == 'concluida' else 'limitado' if job['estado'] == 'parcial' else 'erro',
                mensagem=job['mensagem'], data=store.agora(), consumo=None, tipo_validacao='leitura_site', fingerprint=fingerprint('firecrawl')))


def revisar(empresa, data):
    if not isinstance(data, dict) or set(data) != {'pesquisa_id', 'sugestoes'} or not isinstance(data['sugestoes'], list) or not 1 <= len(data['sugestoes']) <= 40:
        raise ValueError('Selecione sugestões para confirmar.')
    with lock, store.conectar() as con:
        job = ler_job(store.texto(data['pesquisa_id'], 80))
        if job['empresa_id'] != empresa:
            raise LookupError('Pesquisa de outra empresa.')
        if job['estado'] in ('na_fila', 'pesquisando'):
            raise ValueError('Aguarde a conclusão da leitura antes de aplicar sugestões.')
        row = con.execute('SELECT dados FROM ed_empresas WHERE id=?', (empresa,)).fetchone()
        base = json.loads(row['dados'])
        if base['site'] != job['site']:
            return None
        reviewed = []
        fields = set()
        for choice in data['sugestoes']:
            if not isinstance(choice, dict) or set(choice) != {'id', 'valor_atual'}:
                raise ValueError('Revisão inválida.')
            store.texto(choice['id'], 80)
            store.texto(choice['valor_atual'], 4000)
            s = next((s for s in job['sugestoes'] if s['id'] == choice['id']), None)
            if not s or s['campo'] in fields:
                raise ValueError('Escolha uma sugestão por campo.')
            field = s['campo']
            if base.get(field, '') != choice['valor_atual']:
                return None
            fields.add(field)
            reviewed.append(s)
        for s in reviewed:
            store.validar_dados({s['campo']: s['valor']})
            base[s['campo']] = s['valor']
            base['fontes'][s['campo']] = {**store.fonte(s['campo'], s['valor'], 'site_empresa', s['origem'], True),
                'consultado_em': job['criado_em'], 'evidencia': s['evidencia'], 'metodo': s['metodo'], 'pesquisa_id': job['id'], 'coletor': job.get('fornecedor', 'site_local')}
            s.update(aplicado=True, revisado_em=store.agora())
        updated = con.execute('UPDATE ed_empresas SET dados=?,atualizado_em=? WHERE id=? AND dados=?', (json.dumps(base, ensure_ascii=False), store.agora(), empresa, row['dados']))
        if not updated.rowcount:
            return None
        # Mesma transação para registro de revisão e ficha.
        con.execute('UPDATE ed_pesquisas SET dados=? WHERE id=?', (json.dumps(job, ensure_ascii=False), job['id']))
    return store.ler_empresa(empresa)


def candidato(empresa, pesquisa, imagem):
    job = ler_job(pesquisa)
    if job['empresa_id'] != empresa:
        raise LookupError('Pesquisa de outra empresa.')
    image = next((x for x in job['imagens'] if x['id'] == imagem), None)
    if not image:
        raise LookupError('Imagem candidata não encontrada.')
    return job, image


def imagem_candidata(job, image):
    file = store.arquivo_seguro('referencias', f'{job["id"]}/{image["id"]}.img')
    with lock:
        image_lock = image_locks.setdefault((job['id'], image['id']), Lock())
    # A espera de uma imagem externa não bloqueia início/revisão de pesquisas.
    with image_lock:
        if file.exists() and time.time() - file.stat().st_mtime < 86400:
            return file
        final, content, _ = ler_url(image['url'], limite=8 * 1024 * 1024)
        try:
            with warnings.catch_warnings():
                warnings.simplefilter('error', Image.DecompressionBombWarning)
                with Image.open(io.BytesIO(content)) as im:
                    if im.format not in ('PNG', 'JPEG', 'WEBP') or im.width * im.height > 24_000_000:
                        raise ValueError('Prévia exige PNG, JPEG ou WebP com até 24 megapixels.')
                    im.verify()
        except (UnidentifiedImageError, OSError, Image.DecompressionBombError, Image.DecompressionBombWarning) as exc:
            raise ValueError('Imagem não disponível neste formato; use upload manual.') from exc
        file.parent.mkdir(parents=True, exist_ok=True)
        file.write_bytes(content)
    return file


def registrar(bp):
    @bp.post('/empresas/<empresa>/pesquisas/<pesquisa>/diagnostico')
    def diagnostico(empresa, pesquisa):
        return jsonify(diagnosticar(empresa, pesquisa))

    @bp.post('/empresas/<empresa>/pesquisas/<pesquisa>/cancelar')
    def cancelar(empresa, pesquisa):
        with lock:
            job = ler_job(pesquisa)
            if job['empresa_id'] != empresa:
                raise LookupError('Pesquisa de outra empresa.')
            if job['estado'] in ('na_fila', 'pesquisando'):
                job.update(estado='cancelada', mensagem='Pesquisa cancelada; resultados parciais e edições preservados. Uma requisição já enviada pode consumir cota.')
                salvar_job(job)
        return jsonify(ler_job(pesquisa))

    @bp.get('/empresas/<empresa>/pesquisa')
    def pesquisa(empresa):
        return jsonify(ultima(empresa))

    @bp.post('/empresas/<empresa>/pesquisa')
    def pesquisar(empresa):
        job = iniciar(empresa, request.get_json(), current_app._get_current_object())
        if not job:
            return jsonify(erro='Uma pesquisa desta empresa já está em andamento.'), 409
        return jsonify(job), 201

    @bp.post('/empresas/<empresa>/pesquisa/aplicar')
    def aplicar(empresa):
        lead = revisar(empresa, request.get_json())
        if not lead:
            return jsonify(erro='A ficha ou o site mudou desde a revisão. Atualize a tela e revise novamente; nenhuma informação foi substituída.'), 409
        return jsonify(lead)

    @bp.get('/empresas/<empresa>/pesquisas/<pesquisa>/imagens/<imagem>')
    def previa_candidata(empresa, pesquisa, imagem):
        job, candidate = candidato(empresa, pesquisa, imagem)
        file = imagem_candidata(job, candidate)
        with Image.open(file) as im:
            media = Image.MIME[im.format]
        return send_file(file, mimetype=media)

    @bp.post('/empresas/<empresa>/pesquisas/<pesquisa>/imagens/<imagem>/importar')
    def importar(empresa, pesquisa, imagem):
        data = request.get_json()
        if not isinstance(data, dict) or set(data) != {'autorizado', 'atribuicao'} or data['autorizado'] is not True or not store.texto(data['atribuicao'], 1000):
            raise ValueError('Confirme permissão de exportação e informe titular/atribuição.')
        job, candidate = candidato(empresa, pesquisa, imagem)
        file = imagem_candidata(job, candidate)
        with lock:
            job, candidate = candidato(empresa, pesquisa, imagem)
            if len(store.ler_empresa(empresa)['materiais']) >= 30:
                raise ValueError('Limite de 30 imagens por empresa.')
            if candidate.get('material_id'):
                raise ValueError('Esta imagem já está na galeria.')
            with Image.open(file) as im:
                ext = {'PNG': 'png', 'JPEG': 'jpg', 'WEBP': 'webp'}[im.format]
            mid = store.novo_id()
            target = store.arquivo_seguro('materiais', f'{empresa}/{mid}.{ext}')
            target.parent.mkdir(parents=True, exist_ok=True)
            target.write_bytes(file.read_bytes())
            asset = dict(arquivo=target.name, nome_original=urlsplit(candidate['url']).path.rsplit('/', 1)[-1][:300] or target.name,
                categoria=candidate['categoria'], origem=candidate['origem'] + ' → ' + candidate['url'],
                atribuicao=store.texto(data['atribuicao'], 1000), posicao='A confirmar na galeria', autorizado=True,
                selecionado=False, criado_em=store.agora(), arquivo_url=f'/api/ed/empresas/{empresa}/materiais/{mid}/arquivo')
            candidate.update(material_id=mid, autorizado=True)
            with store.conectar() as con:
                con.execute('INSERT INTO ed_materiais VALUES (?,?,?)', (mid, empresa, json.dumps(asset, ensure_ascii=False)))
                con.execute('UPDATE ed_pesquisas SET dados=? WHERE id=?', (json.dumps(job, ensure_ascii=False), pesquisa))
            return jsonify(id=mid, **asset), 201
