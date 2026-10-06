"""Contratos locais com worker substituído; inferência real registrada no piloto."""
import io
from test_ed_enrich import client
import ed_voice_local
import ed_store as store

def payload(key='voz-a',raw=None,keep=False):
    return {'chave':key,'arquivo':(io.BytesIO(raw or b'RIFF'+b'x'*4+b'WAVE'+b'x'*40),'comando.wav'),'manter_audio':str(keep).lower()}

def test_missing_model_keeps_text_route(client,monkeypatch):
    monkeypatch.setattr(ed_voice_local,'status',lambda:{'instalado':False,'mensagem':'Instale os pesos'})
    r=client.post('/api/ed/voz/transcricoes',data=payload())
    assert r.status_code==400 and 'pesos' in r.json['erro']


def test_capture_origin_is_recorded_but_not_claimed_as_hardware_validation(client,monkeypatch):
    monkeypatch.setattr(ed_voice_local,'status',lambda:{'instalado':True})
    monkeypatch.setattr(ed_voice_local,'transcribe',lambda *a:dict(texto='Ajuste de teste',revisao_necessaria=True))
    for origin in ('microfone_navegador','upload','nao_informada'):
        r=client.post('/api/ed/voz/transcricoes',data={**payload('origin-'+origin),'captura_origem':origin})
        assert r.status_code==202,r.json
        assert r.json['parametros']['captura_origem']==origin
        assert r.json['resultado']['captura_origem']==origin
        assert 'hardware_validado' not in r.json['resultado']
    assert client.post('/api/ed/voz/transcricoes',data={**payload('fake'),'captura_origem':'teste-fisico-aprovado'}).status_code==400

def test_transcript_review_separate_idempotent_and_retention(client,monkeypatch):
    monkeypatch.setattr(ed_voice_local,'status',lambda:{'instalado':True})
    calls=[]
    def transcribe(path,job,progress):
        assert path.exists();calls.append(job['id'])
        return dict(texto='Mostre os leads sem cite',revisao_necessaria=True)
    monkeypatch.setattr(ed_voice_local,'transcribe',transcribe)
    a=client.post('/api/ed/voz/transcricoes',data=payload()).json
    assert a['estado']=='concluida' and a['resultado']['transcricao_original'].endswith('cite')
    assert client.post('/api/ed/voz/transcricoes',data=payload()).json['id']==a['id']
    assert len(calls)==1
    with client.application.app_context():assert not list((store.pasta()/'voz').glob('*'))
    chat=client.post('/api/ed/assistente/conversas',json={}).json
    assert client.get('/api/ed/fluxos').json==[] # gravação/transcrição não cria construção
    msg={'texto':'Mostre os leads sem site','chave':'comando-um','origem':'voz','transcricao_id':a['id']}
    sent=client.post('/api/ed/assistente/conversas/'+chat['id']+'/mensagens',json=msg).json
    assert sent['transcricao_original'].endswith('cite') and sent['texto_revisado'].endswith('site')
    assert client.post('/api/ed/assistente/conversas/'+chat['id']+'/mensagens',json=msg).json['id']==sent['id']
    assert len(client.get('/api/ed/fluxos').json)==1
    retained=client.post('/api/ed/voz/transcricoes',data=payload('reter',keep=True)).json
    with client.application.app_context():assert len(list((store.pasta()/'voz').glob('*')))==1
    assert client.delete('/api/ed/voz/transcricoes/'+retained['id']+'/audio').status_code==200
    assert client.get('/api/ed/operacoes/'+retained['id']).json['resultado']['audio_retido'] is False

def test_failure_is_not_completed_and_retry_is_new(client,monkeypatch):
    monkeypatch.setattr(ed_voice_local,'status',lambda:{'instalado':True})
    monkeypatch.setattr(ed_voice_local,'transcribe',lambda *a:(_ for _ in ()).throw(ValueError('Áudio silencioso')))
    j=client.post('/api/ed/voz/transcricoes',data=payload()).json
    assert j['estado']=='erro' and 'silencioso' in j['mensagem'] and 'resultado' not in j
    with client.application.app_context():assert not list((store.pasta()/'voz').glob('*'))
    assert client.post('/api/ed/voz/transcricoes',data=payload('retry')).json['id']!=j['id']

def test_bad_transcript_does_not_pollute_chat(client):
    chat=client.post('/api/ed/assistente/conversas',json={}).json
    r=client.post('/api/ed/assistente/conversas/'+chat['id']+'/mensagens',json={'texto':'Mostre leads','chave':'a','transcricao_id':'inexistente'})
    assert r.status_code==404
    assert client.get('/api/ed/assistente/conversas/'+chat['id']).json['mensagens']==[]
