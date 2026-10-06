"""Voz via API própria: não reutiliza o login nativo ChatGPT/Codex."""
import io
import json
import time
from threading import RLock
from functools import wraps
from flask import request,jsonify,send_file,current_app
import requests
import ed_store as store
import ed_secrets
from ed_services import config,log,fingerprint
from ed_connectors import request_json
voice_lock=RLock()
def serialize(function):
    @wraps(function)
    def wrapped(*args,**kwargs):
        with voice_lock:return function(*args,**kwargs)
    return wrapped

def key():
    value=ed_secrets.get('voz')
    if not value:raise ValueError('Transcrição real indisponível: configure ED_CRM_VOICE_KEY (API OpenAI com acesso a áudio e saldo), ou a credencial Voz em Conexões. O plano Codex nativo não fornece esta API. Gravação local e chat por texto continuam disponíveis.')
    return value

def proof(kind,usage=None):
    log('voz',dict(estado='conectado',mensagem='Operação de áudio concluída: '+kind,tipo_validacao=kind,data=store.agora(),fingerprint=fingerprint('voz'),consumo=usage))

class OpenAIVoice:
    def test(self,settings):
        request_json('GET','https://api.openai.com/v1/models',headers={'Authorization':'Bearer '+key()})
        return dict(mensagem='Chave autenticada. Transcrição e síntese ainda dependem de operação real com o modelo selecionado.')

    def transcribe(self,raw,kind):
        settings=config('voz');model=settings.get('modelo') or 'gpt-transcribe'
        if model not in ('gpt-transcribe','gpt-4o-mini-transcribe','gpt-4o-transcribe','whisper-1'):raise ValueError('Modelo de transcrição não suportado por este adaptador.')
        payload=dict(model=model,prompt='Português brasileiro. Comandos de CRM, nichos, empresas e localidades; transcreva fielmente.')
        # O modelo atual aceita languages[]; os modelos legados usam language/response_format.
        if model=='gpt-transcribe':payload['languages[]']='pt'
        else:payload.update(language='pt',response_format='json')
        with requests.post('https://api.openai.com/v1/audio/transcriptions',headers={'Authorization':'Bearer '+key()},data=payload,files={'file':('comando.'+kind,raw,'audio/'+kind)},timeout=(10,90),allow_redirects=False,stream=True) as response:
            if response.status_code!=200:raise ValueError('Provedor de transcrição respondeu HTTP '+str(response.status_code)+'. Request ID: '+str(response.headers.get('x-request-id','não informado'))+'. Nenhum texto foi simulado.')
            body=b''
            for chunk in response.iter_content(65536):
                body+=chunk
                if len(body)>262144:raise ValueError('Transcrição excedeu limite de resposta.')
            value=json.loads(body)
        text=store.texto(value.get('text',''),12000)
        if not text.strip():raise ValueError('Provedor devolveu transcrição vazia.')
        proof('transcricao',value.get('usage'))
        return dict(texto=text,modelo=model,idioma='pt-BR',consumo=value.get('usage'),origem='OpenAI API · operação real',revisao_necessaria=True)

    def speak(self,text):
        with requests.post('https://api.openai.com/v1/audio/speech',headers={'Authorization':'Bearer '+key()},json=dict(model='gpt-4o-mini-tts',voice='coral',input=text,response_format='mp3',instructions='Fale em português brasileiro, de forma clara e calma.'),timeout=(10,90),allow_redirects=False,stream=True) as response:
            if response.status_code!=200:raise ValueError('Síntese respondeu HTTP '+str(response.status_code)+'. Request ID: '+str(response.headers.get('x-request-id','não informado')))
            out=b''
            for chunk in response.iter_content(65536):
                out+=chunk
                if len(out)>4*1024*1024:raise ValueError('Áudio de resposta excedeu 4 MB.')
        if not out:raise ValueError('Fornecedor não retornou áudio.')
        proof('sintese');return out

def registrar(bp):
    @bp.get('/voz/local/status',endpoint='voice_local_status')
    def local_status():
        from ed_voice_local import status
        return jsonify(status())
    @bp.post('/voz/local/instalar',endpoint='voice_local_install')
    def local_install():
        from ed_voice_local import install,status
        from ed_tasks import iniciar
        if status()['instalado']:return jsonify(status())
        return jsonify(iniciar('local','voice_install',None,{},install)),202
    @bp.post('/voz/transcricoes',endpoint='voice_jobs')
    @serialize
    def voice_jobs():
        from pathlib import Path
        from ed_tasks import iniciar
        from ed_services import ler_job
        ident=store.texto(request.form.get('chave',''),80);provider=request.form.get('provedor','local')
        capture=request.form.get('captura_origem','nao_informada')
        if capture not in ('microfone_navegador','upload','nao_informada'):raise ValueError('Origem de captura inválida.')
        if not ident or provider not in ('local','openai','openrouter'):raise ValueError('Informe chave estável e rota de transcrição válida.')
        file=request.files.get('arquivo')
        if not file:raise ValueError('Selecione uma gravação ou arquivo de áudio.')
        raw=file.read(8*1024*1024+1)
        if not 32<=len(raw)<=8*1024*1024:raise ValueError('Áudio vazio ou maior que 8 MB; envie até três minutos.')
        if raw[:4]==b'\x1aE\xdf\xa3':kind='webm'
        elif raw[:4]==b'OggS':kind='ogg'
        elif raw[:4]==b'RIFF' and raw[8:12]==b'WAVE':kind='wav'
        elif raw[4:8]==b'ftyp':kind='mp4'
        elif raw[:3]==b'ID3' or raw[:2] in (b'\xff\xfb',b'\xff\xf3',b'\xff\xf2'):kind='mp3'
        else:raise ValueError('Formato inválido: WAV, WebM, Ogg, MP4/M4A ou MP3.')
        import hashlib
        sha=hashlib.sha256(raw).hexdigest()
        with store.conectar() as con:
            jobs=[json.loads(r['dados']) for r in con.execute('SELECT dados FROM ed_operacoes')]
        prior=next((j for j in jobs if j.get('chave')=='voz-job:'+ident),None)
        if prior:
            if prior['parametros'].get('sha256')!=sha or prior['fornecedor']!=provider:raise ValueError('Chave já usada para outro áudio/rota. Gere uma nova captura.')
            return jsonify(prior),200
        if sum(j['tipo']=='voice_transcription' and j['estado'] in ('na_fila','pesquisando') for j in jobs)>=3:raise ValueError('Há três áudios na fila. Aguarde ou cancele antes de enviar outro.')
        if provider=='local':
            from ed_voice_local import status
            if not status()['instalado']:raise ValueError(status()['mensagem'])
        elif provider=='openai':key()
        else:
            import ed_secrets
            if not ed_secrets.get('openrouter'):raise ValueError('OpenRouter não configurada. A rota local continua disponível; cobrança é independente do Codex.')
        folder=store.pasta()/'voz';folder.mkdir(exist_ok=True);path=folder/(store.novo_id()+'.'+kind);path.write_bytes(raw)
        data=dict(arquivo=path.name,sha256=sha,manter_audio=request.form.get('manter_audio')=='true',bytes=len(raw),captura_origem=capture)
        def worker(job,progress):
            source=store.pasta()/'voz'/job['parametros']['arquivo']
            try:
                if provider=='local':
                    from ed_voice_local import transcribe
                    result=transcribe(source,job,progress)
                else:
                    import av
                    with av.open(str(source),options={'protocol_whitelist':'file'}) as container:
                        if container.duration is None or not .3<=container.duration/av.time_base<=180:raise ValueError('Duração desconhecida/excedida. Use áudio válido de até três minutos.')
                    progress(35,'Transcrição externa explicitamente selecionada. Áudio enviado somente a esta rota.')
                    if provider=='openai':result=OpenAIVoice().transcribe(source.read_bytes(),kind)
                    else:
                        from ed_creation_providers import transcribe as router_transcribe
                        result=router_transcribe(source.read_bytes(),kind)
                result.update(provedor=provider,audio_retido=job['parametros']['manter_audio'],sha256=sha,transcricao_original=result['texto'],captura_origem=job['parametros']['captura_origem'])
                return result
            finally:
                if not job['parametros']['manter_audio']:source.unlink(missing_ok=True)
        try:return jsonify(iniciar(provider,'voice_transcription',None,data,worker,idempotency_key='voz-job:'+ident)),202
        except BaseException:path.unlink(missing_ok=True);raise
    @bp.delete('/voz/transcricoes/<ident>/audio',endpoint='voice_delete_audio')
    def delete_audio(ident):
        from ed_services import ler_job
        job=ler_job(ident)
        if job['tipo']!='voice_transcription':raise ValueError('Não é um job de áudio.')
        if job['estado'] in ('na_fila','pesquisando'):raise ValueError('Cancele/conclua a transcrição antes de apagar o áudio.')
        from pathlib import Path
        name=job['parametros']['arquivo']
        if Path(name).name!=name:raise ValueError('Áudio inválido.')
        (store.pasta()/'voz'/name).unlink(missing_ok=True)
        from ed_services import save
        job.setdefault('resultado',{})['audio_retido']=False
        job['audio_removido_em']=store.agora();save(job)
        return jsonify(mensagem='Áudio removido; histórico textual preservado.')
    @bp.post('/voz/transcrever',endpoint='voice_transcribe')
    @serialize
    def transcribe():
        key();file=request.files.get('arquivo');ident=store.texto(request.form.get('chave',''),80)
        if not file or not ident:raise ValueError('Selecione áudio e chave de idempotência.')
        with store.conectar() as con:prior=con.execute('SELECT valor FROM ed_config WHERE chave=?',('voz:'+ident,)).fetchone()
        if prior:return jsonify(json.loads(prior['valor']))
        raw=file.read(3*1024*1024+1)
        if not 32<=len(raw)<=3*1024*1024:raise ValueError('Use áudio de até 3 MB; a captura no CRM limita a 60 segundos.')
        if raw[:4]==b'\x1aE\xdf\xa3':kind='webm'
        elif raw[:4]==b'OggS':kind='ogg'
        elif raw[:4]==b'RIFF' and raw[8:12]==b'WAVE':kind='wav'
        elif raw[4:8]==b'ftyp':kind='mp4'
        else:raise ValueError('Formato inválido; use WebM, Ogg, WAV ou MP4 de áudio.')
        result=OpenAIVoice().transcribe(raw,kind)
        with store.conectar() as con:con.execute('INSERT INTO ed_config VALUES (?,?) ON CONFLICT(chave) DO UPDATE SET valor=excluded.valor',('voz:'+ident,json.dumps(result,ensure_ascii=False)))
        return jsonify(result)
    @bp.post('/voz/falar',endpoint='voice_speak')
    def speak():
        d=request.get_json()
        if not isinstance(d,dict) or set(d)!={'texto'}:raise ValueError('Informe texto.')
        text=store.texto(d['texto'],2000)
        if not text.strip():raise ValueError('Texto vazio.')
        return send_file(io.BytesIO(OpenAIVoice().speak(text)),mimetype='audio/mpeg')
