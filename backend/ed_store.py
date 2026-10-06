"""Dados do Ed CRM; reaproveita a conexão SQLite da base ProspectOS."""
import json
import unicodedata
import uuid
from contextlib import contextmanager
from datetime import datetime, timezone
from pathlib import Path
from urllib.parse import urlsplit

from flask import current_app
import db

ETAPAS = ['encontrado', 'pesquisando', 'documento_pronto', 'exportado_codex', 'previa_pronta']
CAMPOS = ['nome', 'nicho', 'cidade', 'uf', 'bairro', 'endereco', 'telefone', 'site',
          'instagram', 'servicos', 'horarios', 'descricao', 'email', 'redes_sociais']
EXTRAS = ['fonte_url', 'fonte_busca_url', 'fonte_mapa_url', 'confirmado', 'demonstracao', 'etapa', 'observacoes', 'briefing']
BRIEFING = ['objetivo', 'publico', 'cta', 'secoes', 'direcao', 'diagnostico', 'complemento']


def agora():
    return datetime.now(timezone.utc).isoformat(timespec='seconds')


def novo_id():
    return uuid.uuid4().hex


def pasta():
    from ed_workspace import data_directory
    selected=data_directory.get()
    if selected is not None:return Path(selected)
    return Path(current_app.config['DATA_DIR'])


@contextmanager
def conectar():
    con = db.conectar(pasta() / 'ed-crm.db')
    try:
        with con:
            yield con
    finally:
        con.close()


def preparar():
    for sub in ['', 'materiais', 'exportacoes']:
        (pasta() / sub).mkdir(parents=True, exist_ok=True)
    with conectar() as con:
        con.executescript('''
            CREATE TABLE IF NOT EXISTS ed_empresas (
                id TEXT PRIMARY KEY, dados TEXT NOT NULL, fonte_id TEXT UNIQUE,
                criado_em TEXT NOT NULL, atualizado_em TEXT NOT NULL);
            CREATE TABLE IF NOT EXISTS ed_materiais (
                id TEXT PRIMARY KEY, empresa_id TEXT NOT NULL REFERENCES ed_empresas(id),
                dados TEXT NOT NULL);
            CREATE TABLE IF NOT EXISTS ed_exportacoes (
                id TEXT PRIMARY KEY, empresa_id TEXT NOT NULL REFERENCES ed_empresas(id),
                versao INTEGER NOT NULL, criado_em TEXT NOT NULL, manifesto TEXT NOT NULL);
            CREATE TABLE IF NOT EXISTS ed_previas (
                id TEXT PRIMARY KEY, empresa_id TEXT NOT NULL REFERENCES ed_empresas(id),
                dados TEXT NOT NULL);
            CREATE TABLE IF NOT EXISTS ed_campanhas (
                id TEXT PRIMARY KEY, dados TEXT NOT NULL);
            CREATE TABLE IF NOT EXISTS ed_config (chave TEXT PRIMARY KEY, valor TEXT NOT NULL);
            CREATE TABLE IF NOT EXISTS ed_pesquisas (
                id TEXT PRIMARY KEY, empresa_id TEXT NOT NULL REFERENCES ed_empresas(id), dados TEXT NOT NULL);
            CREATE TABLE IF NOT EXISTS ed_preparacoes (
                empresa_id TEXT PRIMARY KEY REFERENCES ed_empresas(id), dados TEXT NOT NULL);
            CREATE TABLE IF NOT EXISTS ed_operacoes (
                id TEXT PRIMARY KEY, dados TEXT NOT NULL);
        ''')
        from ed_sites import migrar
        migrar(con)
        # Recuperação explícita após encerramento do processo: não repetir requisições sozinho.
        for row in con.execute('SELECT id,dados FROM ed_campanhas').fetchall():
            job = json.loads(row['dados'])
            if current_app.config.get('RECOVER_JOBS', True) and job['estado'] in ('na_fila', 'pesquisando'):
                job.update(estado='interrompida', mensagem='Servidor reiniciado. Use Retomar para continuar.')
                con.execute('UPDATE ed_campanhas SET dados=? WHERE id=?', (json.dumps(job), row['id']))
        if current_app.config.get('RECOVER_JOBS', True):
            for row in con.execute('SELECT id,dados FROM ed_operacoes').fetchall():
                job = json.loads(row['dados'])
                if job['estado'] in ('na_fila', 'pesquisando'):
                    job.update(estado='interrompida', mensagem='Servidor reiniciado. Tente novamente; decisões manuais preservadas.')
                    con.execute('UPDATE ed_operacoes SET dados=? WHERE id=?', (json.dumps(job), row['id']))
            for row in con.execute('SELECT id,dados FROM ed_pesquisas').fetchall():
                job = json.loads(row['dados'])
                if job['estado'] in ('na_fila', 'pesquisando'):
                    job.update(estado='interrompida', mensagem='Servidor reiniciado; resultados parciais preservados. Pesquise novamente para continuar.')
                    con.execute('UPDATE ed_pesquisas SET dados=? WHERE id=?', (json.dumps(job), row['id']))
            for row in con.execute('SELECT dados FROM ed_operacoes').fetchall():
                job=json.loads(row['dados'])
                if job['tipo']=='voice_transcription' and job['estado'] not in ('na_fila','pesquisando') and not job['parametros'].get('manter_audio'):
                    name=job['parametros'].get('arquivo','')
                    if name and Path(name).name==name:(pasta()/'voz'/name).unlink(missing_ok=True)
    from ed_library import setup
    setup()
    from ed_adaptive import setup as setup_adaptive
    setup_adaptive()
    from ed_crm import setup as setup_crm
    setup_crm()
    from ed_workflows import setup as setup_workflows
    setup_workflows()
    from ed_batches import recover
    recover()


def texto(value, maximo=2000):
    if not isinstance(value, str) or len(value) > maximo or '\x00' in value:
        raise ValueError(f'Texto inválido. Limite de {maximo} caracteres.')
    return value.strip()


def booleano(value):
    if not isinstance(value, bool):
        raise ValueError('Informe verdadeiro ou falso.')
    return value


def url(value):
    value = texto(value)
    if not value:
        return ''
    parsed = urlsplit(value)
    if parsed.scheme not in ('http', 'https') or not parsed.hostname or parsed.username or parsed.password:
        raise ValueError('Use uma URL http/https sem credenciais.')
    return value


def validar_dados(data):
    if not isinstance(data, dict) or set(data) - set(CAMPOS + EXTRAS):
        raise ValueError('Campos desconhecidos na ficha.')
    out = {}
    for key, value in data.items():
        if key == 'briefing':
            if not isinstance(value, dict) or set(value) - set(BRIEFING):
                raise ValueError('Briefing inválido.')
            out[key] = {k: texto(v, 12000 if k == 'complemento' else 4000) for k, v in value.items()}
        elif key in ('confirmado', 'demonstracao'):
            out[key] = booleano(value)
        elif key in ('site', 'instagram', 'fonte_url', 'fonte_busca_url', 'fonte_mapa_url'):
            out[key] = url(value)
        else:
            out[key] = texto(value, 4000 if key in ('servicos', 'observacoes', 'descricao', 'redes_sociais') else 500)
    if 'nome' in out and not out['nome']:
        raise ValueError('Informe o nome da empresa.')
    if 'etapa' in out and out['etapa'] not in ETAPAS:
        raise ValueError('Etapa inválida.')
    return out


def fonte(campo, valor, fornecedor, origem, verificado=False):
    return dict(campo=campo, valor=valor, fornecedor=fornecedor, url=origem,
                consultado_em=agora(), verificacao='confirmado_usuario' if verificado else 'a_confirmar',
                retencao={'manual': 'Cadastro do usuário', 'site_empresa': 'Contexto do site; direitos dos materiais a revisar'}.get(fornecedor, 'ODbL 1.0'),
                exportavel=True)


def gravar_empresa(data, ident=None, fonte_id=None, fornecedor='manual'):
    values = validar_dados(data)
    with conectar() as con:
        existing = None
        if fonte_id:
            existing = con.execute('SELECT * FROM ed_empresas WHERE fonte_id=?', (fonte_id,)).fetchone()
            if existing:
                # Repetição da busca preserva edições, materiais e histórico locais.
                return ler_empresa(existing['id']), False
        if ident:
            existing = con.execute('SELECT * FROM ed_empresas WHERE id=?', (ident,)).fetchone()
            if not existing:
                raise LookupError('Empresa não encontrada.')
        base = json.loads(existing['dados']) if existing else {
            **{k: '' for k in CAMPOS}, 'confirmado': False, 'demonstracao': False,
            'etapa': 'encontrado', 'observacoes': '', 'briefing': {}, 'fontes': {}, 'fonte_url': '',
        }
        old = json.loads(json.dumps(base))
        base.update({k: v for k, v in values.items() if k != 'briefing'})
        base['briefing'] = {**base['briefing'], **values.get('briefing', {})}
        if not base['nome']:
            raise ValueError('Informe o nome da empresa.')
        for key in CAMPOS:
            if key == 'site' and old.get('site') == base['site']:
                # A confirmação geral da ficha não muda o vínculo do site.
                continue
            verification_requested = 'confirmado' in values and fornecedor == 'manual' and (
                old.get('confirmado') != base['confirmado'] or
                base['confirmado'] and base['fontes'].get(key, {}).get('verificacao') != 'confirmado_usuario')
            if key in values and (old.get(key) != base[key] or verification_requested):
                if base[key]:
                    if old.get(key) == base[key] and key in base['fontes']:
                        base['fontes'][key] = {**base['fontes'][key], 'verificacao':
                            'confirmado_usuario' if base['confirmado'] else 'a_confirmar'}
                    else:
                        base['fontes'][key] = fonte(key, base[key], fornecedor, base['fonte_url'],
                                                   base['confirmado'] if fornecedor == 'manual' else False)
                else:
                    base['fontes'].pop(key, None)
        from ed_sites import ajustar_gravacao
        ajustar_gravacao(base, old, values)
        ident = ident or novo_id()
        created = existing['criado_em'] if existing else agora()
        con.execute('''INSERT INTO ed_empresas VALUES (?,?,?,?,?)
            ON CONFLICT(id) DO UPDATE SET dados=excluded.dados, atualizado_em=excluded.atualizado_em''',
            (ident, json.dumps(base, ensure_ascii=False), fonte_id, created, agora()))
    return ler_empresa(ident), existing is None


def normalizar(value):
    return ''.join(c for c in unicodedata.normalize('NFKD', value.lower()) if c.isalnum())


def pendencias(lead):
    items = [f'Confirmar {key}: informação não localizada.' for key in
             ('telefone', 'endereco', 'site', 'instagram', 'servicos', 'horarios') if not lead.get(key)]
    if any(x['verificacao'] == 'a_confirmar' for x in lead['fontes'].values()):
        items.append('Conferir identidade do estabelecimento e informações com a empresa.')
    if lead.get('associacao_site', {}).get('estado') != 'confirmado':
        items.append('Associação do site pendente: conferir URL, identidade e evidências; outras fontes e upload continuam disponíveis.')
    items.append('Confirmar objetivo, público, CTA e decisões de design do briefing.')
    return items


def listar_empresas():
    with conectar() as con:
        rows = con.execute('SELECT * FROM ed_empresas ORDER BY criado_em DESC').fetchall()
        exports = {r['empresa_id']: r['total'] for r in con.execute(
            'SELECT empresa_id, COUNT(*) AS total FROM ed_exportacoes GROUP BY empresa_id')}
        previews = {r['empresa_id']: r['total'] for r in con.execute(
            'SELECT empresa_id, COUNT(*) AS total FROM ed_previas GROUP BY empresa_id')}
    leads = [dict(id=r['id'], **json.loads(r['dados']), criado_em=r['criado_em'],
                  atualizado_em=r['atualizado_em']) for r in rows]
    for lead in leads:
        for campo in CAMPOS:
            lead.setdefault(campo, '')
        from ed_sites import status
        lead['associacao_site'] = status(lead)
        lead.setdefault('fonte_busca_url', '')
        lead.setdefault('fonte_mapa_url', '')
        lead.setdefault('historico_site', [])
        lead.setdefault('links_fontes', [])
        lead['total_exportacoes'] = exports.get(lead['id'], 0)
        lead['total_previas'] = previews.get(lead['id'], 0)
        lead['possiveis_duplicatas'] = [x['id'] for x in leads if x['id'] != lead['id'] and not x.get('crm_arquivada') and (
            (normalizar(x['nome']) == normalizar(lead['nome']) and normalizar(x['cidade']) == normalizar(lead['cidade']))
            or (lead['telefone'] and normalizar(x['telefone']) == normalizar(lead['telefone'])))]
        lead['pendencias'] = pendencias(lead)
    return leads


def ler_empresa(ident):
    lead = next((x for x in listar_empresas() if x['id'] == ident), None)
    if not lead:
        raise LookupError('Empresa não encontrada.')
    with conectar() as con:
        lead['materiais'] = [dict(id=r['id'], **json.loads(r['dados'])) for r in con.execute(
            'SELECT * FROM ed_materiais WHERE empresa_id=?', (ident,))]
        lead['exportacoes'] = [dict(id=r['id'], versao=r['versao'], criado_em=r['criado_em'],
            zip_url=f'/api/ed/empresas/{ident}/exportacoes/{r["id"]}/zip',
            markdown_url=f'/api/ed/empresas/{ident}/exportacoes/{r["id"]}/markdown') for r in con.execute(
            'SELECT * FROM ed_exportacoes WHERE empresa_id=? ORDER BY versao DESC', (ident,))]
        lead['previas'] = [dict(id=r['id'], **json.loads(r['dados'])) for r in con.execute(
            'SELECT * FROM ed_previas WHERE empresa_id=? ORDER BY rowid DESC', (ident,))]
    return lead


def config():
    with conectar() as con:
        row = con.execute("SELECT valor FROM ed_config WHERE chave='osm_habilitado'").fetchone()
    return {'osm_habilitado': bool(row and json.loads(row['valor']))}


def arquivo_seguro(sub, nome):
    root = (pasta() / sub).resolve()
    resolved = (root / nome).resolve()
    if not resolved.is_relative_to(root) or resolved == root:
        raise ValueError('Caminho de arquivo inválido.')
    return resolved
