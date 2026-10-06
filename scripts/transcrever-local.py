"""Worker sem rede. JSON stdin/stdout; mantém somente o modelo em memória."""
import json
import sys
import time
from pathlib import Path
import numpy as np
from faster_whisper import WhisperModel
from faster_whisper.audio import decode_audio

def main():
    model=WhisperModel(sys.argv[1],device='cpu',compute_type='int8',cpu_threads=4,num_workers=1,local_files_only=True)
    for line in sys.stdin:
        try:
            d=json.loads(line)
            import av
            with av.open(d['arquivo'],options={'protocol_whitelist':'file'}) as container:
                if container.duration is not None and container.duration/av.time_base>180:raise ValueError('Áudio excede três minutos.')
            audio=decode_audio(d['arquivo'],sampling_rate=16000)
            duration=len(audio)/16000
            if not .3<=duration<=180:raise ValueError('Áudio deve durar de 0,3 a 180 segundos.')
            # Evita hallucinations em silêncio e conteúdo obtido apenas do prompt.
            if np.sqrt(np.mean(audio**2))<.002:raise ValueError('Áudio silencioso ou sem fala audível. Grave novamente; nenhum comando foi criado.')
            start=time.monotonic()
            segments,info=model.transcribe(audio,language='pt',beam_size=5,vad_filter=True,condition_on_previous_text=False,
                initial_prompt='Vocabulário: EDY, Codex, PÃO, landing page, Recife, São Paulo, hero, briefing, painel administrativo.')
            accepted=[s for s in segments if s.no_speech_prob<.7 and s.avg_logprob>-1.2]
            text=' '.join(s.text.strip() for s in accepted).strip()
            if not text:raise ValueError('Nenhuma fala reconhecida. Revise microfone ou envie outro áudio.')
            print(json.dumps(dict(id=d['id'],texto=text,modelo='small',origem='faster-whisper local · operação real',idioma='pt-BR',
                duracao_audio=round(duration,3),tempo_transcricao=round(time.monotonic()-start,3),consumo={'custo_externo':0},revisao_necessaria=True),ensure_ascii=False),flush=True)
        except Exception as exc:
            print(json.dumps({'id':locals().get('d',{}).get('id'),'erro':str(exc) if isinstance(exc,ValueError) else 'Não foi possível decodificar/transcrever o áudio. Use WAV, WebM, Ogg, MP4 ou MP3 válido.'},ensure_ascii=False),flush=True)

if __name__=='__main__':main()
