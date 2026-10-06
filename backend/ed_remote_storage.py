"""S3/R2: cliente explícito, arquivos limitados e chaves isoladas por workspace."""
import hashlib
import io
import re
from flask import g
import boto3
from botocore.config import Config
from botocore.exceptions import BotoCoreError,ClientError
import ed_secrets
import ed_store as store

def client(c):
    if not c['bucket']:raise ValueError('Informe o bucket privado.')
    if c['tipo']=='r2' and not re.fullmatch('[a-fA-F0-9]{32}',c['account_id']):raise ValueError('Informe o ID da conta R2.')
    access,secret=ed_secrets.get('storage_access'),ed_secrets.get('storage')
    if not access or not secret:raise ValueError('Faltam Access key ID e Secret key S3/R2.')
    endpoint='https://'+c['account_id']+'.r2.cloudflarestorage.com' if c['tipo']=='r2' else 'https://s3.'+c['region']+'.amazonaws.com'
    return boto3.client('s3',endpoint_url=endpoint,aws_access_key_id=access,aws_secret_access_key=secret,region_name='auto' if c['tipo']=='r2' else c['region'],config=Config(signature_version='s3v4',connect_timeout=5,read_timeout=15,retries={'max_attempts':0},proxies={},s3={'addressing_style':'path'},request_checksum_calculation='when_required',response_checksum_validation='when_required'))

def key(company,version,name,kind='versoes'):
    workspace=getattr(g,'actor',{}).get('workspace','principal')
    if any(not re.fullmatch('[A-Za-z0-9_-]{1,80}',v) for v in (workspace,company,version)) or kind not in ('originais','versoes'):raise ValueError('Escopo de armazenamento inválido.')
    if not re.fullmatch('[A-Za-z0-9_.-]{1,120}',name) or name in ('.','..'):raise ValueError('Nome de arquivo inválido.')
    return f'edy/{workspace}/{company}/{kind}/{version}/{name}'

def safe_failure(exc):
    code=str(exc.response.get('Error',{}).get('Code','')) if isinstance(exc,ClientError) else 'rede'
    code=code if re.fullmatch('[A-Za-z0-9_-]{1,80}',code) else 'servico'
    return ValueError('Armazenamento recusou a operação ('+code+'). Confira bucket, região e permissões; original local preservado.')

def test(c):
    s3=client(c)
    try:
        s3.head_bucket(Bucket=c['bucket'])
        # Teste não contém dados de cliente. Objeto único, não sobrescreve originais.
        payload=b'EDY CRM - teste autorizado de integridade, sem dados de cliente.\n'
        k=key('diagnostico',store.novo_id(),'integridade.txt')
        sha=hashlib.sha256(payload).hexdigest()
        s3.put_object(Bucket=c['bucket'],Key=k,Body=payload,ContentType='text/plain',Metadata={'sha256':sha})
        result=s3.get_object(Bucket=c['bucket'],Key=k)
        with result['Body'] as stream:raw=stream.read(1025)
        if hashlib.sha256(raw).hexdigest()!=sha:raise ValueError('Falha de integridade no retorno do armazenamento.')
        # Assinatura criada e GET realizado pelo SDK. Validar link é operação distinta.
        s3.generate_presigned_url('get_object',Params={'Bucket':c['bucket'],'Key':k},ExpiresIn=300)
        return dict(capacidade='objeto_gravado_e_lido',recursos=[{'nome':k,'sha256':sha,'bytes':len(payload)}],mensagem='HeadBucket, gravação e leitura de teste concluídas com SHA256 igual. URL assinada gerada por 300 s, ainda não validada por navegação. Privacidade/política do bucket e envio de materiais devem ser revisados; teste preservado no prefixo diagnóstico.')
    except (BotoCoreError,ClientError) as exc:raise safe_failure(exc) from None
    finally:s3.close()

def upload_package(company,export_id):
    from ed_destinations import config,status
    # O exportador é a fronteira de direitos: seu ZIP só inclui materiais elegíveis.
    proof=status('storage')
    if proof['prova'].get('capacidade')!='objeto_gravado_e_lido':raise ValueError('Valide gravação/leitura no bucket antes de enviar um pacote.')
    lead=store.ler_empresa(company)
    if not any(x['id']==export_id for x in lead['exportacoes']):raise LookupError('Pacote não pertence à empresa neste workspace.')
    path=store.arquivo_seguro('exportacoes',company+'/'+export_id+'/pacote.zip')
    if path.stat().st_size>25_000_000:raise ValueError('Pacote excede 25 MB; use envio externo revisado.')
    payload=path.read_bytes();sha=hashlib.sha256(payload).hexdigest();k=key(company,export_id,'pacote-codex.zip')
    c=config('storage');s3=client(c)
    try:
        s3.put_object(Bucket=c['bucket'],Key=k,Body=io.BytesIO(payload),ContentType='application/zip',Metadata={'sha256':sha})
        return dict(chave=k,sha256=sha,bytes=len(payload),privacidade='depende_da_politica_do_bucket',mensagem='Objeto enviado. A ausência de ACL público na requisição não comprova privacidade do bucket.')
    except (BotoCoreError,ClientError) as exc:raise safe_failure(exc) from None
    finally:s3.close()
