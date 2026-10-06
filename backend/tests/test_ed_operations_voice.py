import io,json,zipfile,hashlib
from test_ed_enrich import client


def test_online_workspace_backup_integrity_and_exclusion(client):
    import ed_store as store
    client.post('/api/ed/empresas',json={'nome':'Registro preservado'})
    with client.application.app_context():
        base=store.pasta();(base/'materiais/teste').mkdir();(base/'materiais/teste/original.txt').write_text('arquivo de teste')
        (base/'runtime-codex').mkdir();(base/'runtime-codex/auth.json').write_text('TESTE: segredo excluído')
    result=client.post('/api/ed/operacao/backup').json
    assert result['integridade']=='ok'
    with zipfile.ZipFile(io.BytesIO(client.get(result['download']).data)) as z:
        names=z.namelist();assert 'ed-crm.db' in names
        assert all('auth' not in x and 'ed-access' not in x and 'workspaces' not in x for x in names)
        for f in json.loads(z.read('integridade-backup.json')):
            assert hashlib.sha256(z.read(f['arquivo'])).hexdigest()==f['sha256']
    diag=client.get('/api/ed/operacao/diagnostico').json
    assert diag['banco']=='ok' and diag['worker']['processo_ativo'] is False


def test_voice_missing_access_and_invalid_media_are_not_success(client,monkeypatch):
    import ed_voice
    monkeypatch.setattr(ed_voice.ed_secrets,'get',lambda x:None)
    response=client.post('/api/ed/voz/transcrever',data={'chave':'teste','arquivo':(io.BytesIO(b'x'*40),'comando.webm')})
    assert response.status_code==400 and 'ED_CRM_VOICE_KEY' in response.json['erro']
    monkeypatch.setattr(ed_voice.ed_secrets,'get',lambda x:'mock-only')
    response=client.post('/api/ed/voz/transcrever',data={'chave':'teste','arquivo':(io.BytesIO(b'x'*40),'comando.webm')})
    assert response.status_code==400 and 'Formato inválido' in response.json['erro']


def test_voice_mock_contract_review_and_duplicate(client,monkeypatch):
    # Não valida operação real do fornecedor; prova contrato, falha e idempotência local.
    import ed_voice
    monkeypatch.setattr(ed_voice.ed_secrets,'get',lambda x:'mock-only')
    calls=[]
    def transcribe(self,raw,kind):
        calls.append(kind);return {'texto':'Mostre os leads sem site','revisao_necessaria':True,'origem':'Mock identificado'}
    monkeypatch.setattr(ed_voice.OpenAIVoice,'transcribe',transcribe)
    def submit():return client.post('/api/ed/voz/transcrever',data={'chave':'audio-unico','arquivo':(io.BytesIO(b'\x1aE\xdf\xa3'+b'x'*40),'comando.webm')})
    assert submit().json['revisao_necessaria'] is True
    assert submit().json['origem']=='Mock identificado' and calls==['webm']
    monkeypatch.setattr(ed_voice.OpenAIVoice,'transcribe',lambda *a:(_ for _ in ()).throw(ValueError('HTTP 401 · request-id-teste')))
    r=client.post('/api/ed/voz/transcrever',data={'chave':'erro','arquivo':(io.BytesIO(b'OggS'+b'x'*40),'comando.ogg')})
    assert r.status_code==400 and 'request-id-teste' in r.json['erro']


def test_voice_current_and_legacy_http_contracts_are_separate(client,monkeypatch):
    # Mock HTTP: valida os contratos documentados, não acesso real ao fornecedor.
    import ed_voice
    monkeypatch.setattr(ed_voice.ed_secrets,'get',lambda x:'mock-only')
    monkeypatch.setattr(ed_voice,'proof',lambda *a:None)
    calls=[]
    class Response:
        status_code=200
        def __enter__(self):return self
        def __exit__(self,*args):pass
        def iter_content(self,*args):yield b'{"text":"Revisar empresa","languages":[{"code":"pt"}]}'
    def post(url,**kwargs):calls.append(kwargs);return Response()
    monkeypatch.setattr(ed_voice.requests,'post',post)
    monkeypatch.setattr(ed_voice,'config',lambda *args:{})
    assert ed_voice.OpenAIVoice().transcribe(b'audio','webm')['modelo']=='gpt-transcribe'
    assert calls[-1]['data']['languages[]']=='pt' and 'response_format' not in calls[-1]['data']
    monkeypatch.setattr(ed_voice,'config',lambda *args:{'modelo':'gpt-4o-mini-transcribe'})
    assert ed_voice.OpenAIVoice().transcribe(b'audio','webm')['modelo']=='gpt-4o-mini-transcribe'
    assert calls[-1]['data']['language']=='pt' and calls[-1]['data']['response_format']=='json'
