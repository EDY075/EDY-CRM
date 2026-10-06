"""Transcrição local: pesos persistentes, worker supervisionado e sem segredos."""
import atexit
import hashlib
import json
import os
from pathlib import Path
import queue
import subprocess
import sys
import threading
import time
from flask import current_app
import ed_store as store
from ed_tasks import ativo

MODEL='small'
_workers={}
_guard=threading.RLock()

def model_root():return Path(__file__).resolve().parent.parent/'.cache/whisper'/MODEL

def status():
    path=model_root();manifest=path/'integridade.json'
    ready=manifest.is_file() and all((path/n).is_file() for n in ('model.bin','config.json','tokenizer.json'))
    return dict(provedor='local',modelo=MODEL,multilingue=True,dispositivo='CPU · int8 · 4 threads',instalado=ready,
        estado='instalado' if ready else 'modelo_nao_instalado',idioma='pt-BR',concorrencia=1,
        mensagem='Transcrição local, sem serviço externo após download.' if ready else 'Instale os pesos multilíngues pelo CRM; texto e captura continuam disponíveis.')

def install(job,progress):
    from huggingface_hub import snapshot_download,HfApi
    root=model_root();root.mkdir(parents=True,exist_ok=True)
    progress(15,'Baixando pesos multilíngues small (~500 MB), uma vez neste projeto.')
    # Revisão identificada pelo serviço; manifest não presume integridade pelo nome.
    revision=HfApi(token=False).model_info('Systran/faster-whisper-small').sha
    snapshot_download('Systran/faster-whisper-small',revision=revision,local_dir=str(root),
        cache_dir=str(root.parent/'download'),allow_patterns=['*.json','*.bin','*.txt'],token=False)
    ativo(job['id']);progress(85,'Verificando arquivos do modelo local.')
    files={}
    for p in root.iterdir():
        if p.is_file() and p.name!='integridade.json':
            with p.open('rb') as f:files[p.name]=hashlib.file_digest(f,'sha256').hexdigest()
    if not all(n in files for n in ('model.bin','config.json','tokenizer.json')):raise ValueError('Download incompleto. Tente instalar novamente; texto preservado.')
    (root/'integridade.json').write_text(json.dumps(dict(repositorio='Systran/faster-whisper-small',revisao=revision,sha256=files),indent=2),encoding='utf-8')
    return status()

class Worker:
    def __init__(self):
        root=model_root();manifest=json.loads((root/'integridade.json').read_text(encoding='utf-8'))
        for name,sha in manifest['sha256'].items():
            p=(root/name).resolve()
            if not p.is_relative_to(root.resolve()):raise ValueError('Manifesto de modelo inválido.')
            with p.open('rb') as f:
                if hashlib.file_digest(f,'sha256').hexdigest()!=sha:raise ValueError('Modelo local mudou. Reinstale os pesos antes de transcrever.')
        project=Path(__file__).resolve().parent.parent
        temp=project/'.cache/tmp';temp.mkdir(parents=True,exist_ok=True)
        env={k:v for k,v in os.environ.items() if k.upper() in ('PATH','SYSTEMROOT','WINDIR')}
        env.update(TEMP=str(temp),TMP=str(temp),HF_HUB_OFFLINE='1',OMP_NUM_THREADS='4',PYTHONDONTWRITEBYTECODE='1',PYTHONIOENCODING='utf-8')
        self.proc=subprocess.Popen([sys.executable,str(project/'scripts/transcrever-local.py'),str(root)],env=env,cwd=project,
            stdin=subprocess.PIPE,stdout=subprocess.PIPE,stderr=subprocess.DEVNULL,text=True,encoding='utf-8',creationflags=getattr(subprocess,'CREATE_NO_WINDOW',0))
        self.lines=queue.Queue()
        def read():
            try:
                for line in self.proc.stdout:
                    try:self.lines.put(json.loads(line))
                    except ValueError:pass
            except (OSError,UnicodeError):pass
            finally:self.lines.put({'erro':'Worker de áudio encerrou. Tente novamente.'})
        threading.Thread(target=read,daemon=True).start()
    def close(self):
        if self.proc.poll() is None:
            self.proc.terminate()
            try:self.proc.wait(timeout=3)
            except subprocess.TimeoutExpired:self.proc.kill();self.proc.wait(timeout=3)
        for stream in (self.proc.stdin,self.proc.stdout):
            if stream:stream.close()

def stop():
    for w in list(_workers.values()):w.close()
    _workers.clear()
atexit.register(stop)

def transcribe(path,job,progress):
    if not status()['instalado']:raise ValueError(status()['mensagem'])
    with _guard:
        deadline=time.monotonic()+120
        ativo(job['id']);key=str(store.pasta().resolve());worker=_workers.get(key)
        if not worker or worker.proc.poll() is not None:
            progress(20,'Carregando modelo local; próximos áudios reutilizam o worker.')
            worker=Worker();_workers[key]=worker
        progress(35,'Transcrevendo localmente em português. O áudio não saiu do computador.')
        worker.proc.stdin.write(json.dumps({'arquivo':str(path.resolve()),'id':job['id']})+'\n');worker.proc.stdin.flush()
        try:
            while time.monotonic()<deadline:
                ativo(job['id'])
                try:value=worker.lines.get(timeout=.25)
                except queue.Empty:continue
                if value.get('erro'):raise ValueError(value['erro'])
                if value.get('id')!=job['id']:continue
                return value
            raise ValueError('Transcrição local excedeu 120 segundos. Reduza o áudio e tente novamente.')
        except BaseException:
            worker.close();_workers.pop(key,None);raise
