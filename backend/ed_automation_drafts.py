"""Rascunhos n8n portáteis; importar não ativa nem executa chamadas remotas."""
import io
import json
import zipfile
from flask import send_file


def bundle():
    out = io.BytesIO()
    flows = [
        ('pesquisa-solicitada', 'Pesquisa solicitada → job EDY', 'pesquisar',
         'O EDY continua dono da fila. Um worker local consulta pedidos autenticados; não exponha localhost.'),
        ('previa-pronta', 'Prévia pronta → armazenamento → atualizar CRM', 'previa_pronta',
         'Confira direitos e hashes, valide bucket privado, depois registre a chave/versão. Não publicar.'),
        ('falha-recuperacao', 'Falha → registrar → recuperar checkpoint', 'falha',
         'Registre o erro e peça retomada ao EDY com a mesma chave. Não repetir automaticamente consumo pago.'),
    ]
    files = {}
    for slug, title, event, note in flows:
        workflow = dict(name='EDY · '+title, active=False, settings={'executionOrder':'v1'},
            nodes=[
                dict(id='manual', name='Teste manual', type='n8n-nodes-base.manualTrigger', typeVersion=1, position=[0,0], parameters={}),
                dict(id='envelope', name='Envelope de demonstração', type='n8n-nodes-base.set', typeVersion=3.4, position=[240,0], parameters={
                    'assignments':{'assignments':[dict(id=k,name=k,type='string',value=v) for k,v in {
                        'evento':event, 'correlacao_id':'demo-nao-executar', 'idempotencia':'demo-nao-executar',
                        'workspace_id':'CONFIGURAR', 'empresa_id':'CONFIGURAR', 'versao_id':'CONFIGURAR',
                        'estado':'rascunho_sem_operacao_remota'}.items()]}, 'options':{}}),
                dict(id='note', name='Configuração obrigatória', type='n8n-nodes-base.stickyNote', typeVersion=1, position=[200,-280], parameters={'content':'## Rascunho — sem integração executada\n'+note+'\nAPI key e credencial de webhook são distintas. Valide assinatura, correlação e idempotência antes de ativar.','height':230,'width':440}),
            ], connections={'Teste manual':{'main':[[{'node':'Envelope de demonstração','type':'main','index':0}]]}}, tags=[])
        files[slug+'.json'] = json.dumps(workflow,ensure_ascii=False,indent=2)
    files['LEIA-ME.md'] = '''# n8n · três rascunhos inativos

Não houve criação, ativação ou execução no fornecedor. Estes fluxos importáveis
preparam os envelopes; ainda não contêm nós de HTTP, upload ou publicação.
O teste manual gera dados de demonstração, identificados como tais.

1. Importe cada JSON e confira os nós antes de ativar. Substitua CONFIGURAR.
2. Habilite a Public API e configure X-N8N-API-KEY no Centro de conexões para
consultar workflows. Essa API não está disponível no trial gratuito do n8n.
3. Para eventos, configure credencial independente de webhook (Header Auth),
validação de payload, ID de correlação e chave de idempotência persistente.
4. Escolha polling autenticado de saída pelo worker local. Um n8n remoto não
alcança 127.0.0.1 deste computador. Não exponha todo o CRM para callbacks.
5. Acrescente os nós específicos após validar essa conectividade e permissões.
O EDY conserva a fila/checkpoints; n8n encaminha eventos, sem segunda fila de geração.
6. Prévia pronta: use somente material autorizado, compare SHA256 após upload,
registre a versão no CRM e não publique nem envie prospecção sem autorização.
7. Falhas: mantenha versões anteriores; retome com a mesma chave e limite.

Documentação: https://docs.n8n.io/connect/n8n-api/authentication
'''
    with zipfile.ZipFile(out,'w',zipfile.ZIP_DEFLATED) as z:
        for name, content in files.items():z.writestr(name,content)
    out.seek(0)
    return out


def registrar(bp):
    @bp.get('/destinos/n8n/rascunhos', endpoint='automation_drafts')
    def download():
        return send_file(bundle(),as_attachment=True,download_name='edy-n8n-rascunhos.zip',mimetype='application/zip')
