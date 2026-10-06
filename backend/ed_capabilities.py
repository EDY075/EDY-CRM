"""Fronteiras substituíveis; recursos futuros nunca recebem status conectado."""
from typing import Protocol
from flask import jsonify

class Discovery(Protocol):
    def discover(self,job:dict)->tuple[list,bool]: ...
class Enrichment(Protocol):
    def scrape(self,url:str)->tuple[str,bytes,str]: ...
class ImageProvider(Protocol):
    def edit(self,original,options:dict,settings:dict)->tuple: ...
class Generation(Protocol):
    def generate(self,context:dict,progress)->dict: ...
class ComponentProvider(Protocol):
    def search(self,query:str,runtime:dict)->list: ...
class Storage(Protocol):
    def upload(self,artifact:dict,settings:dict)->dict: ...
class Publication(Protocol):
    def publish(self,artifact:dict,settings:dict,explicit_action:bool)->dict: ...

EXTENSIONS=[
 dict(id='github',nome='GitHub',finalidade='Versionar código da prévia',configuracao='Repositório escolhido, autenticação e permissões de escrita; adapter remoto futuro.',docs='https://docs.github.com/en/rest'),
 dict(id='cloudflare',nome='Cloudflare Pages',finalidade='Publicação explícita de prévia/produção',configuracao='Conta/projeto, token restrito e adapter de publicação; nenhuma publicação automática.',docs='https://developers.cloudflare.com/pages/'),
 dict(id='storage',nome='Armazenamento remoto',finalidade='Arquivos autorizados e versões',configuracao='Bucket/provedor, retenção, URLs e acesso restrito; armazenamento atual é local.',docs='https://developers.cloudflare.com/r2/'),
 dict(id='webhooks',nome='n8n / webhooks',finalidade='Automação por eventos revisados',configuracao='Endpoint, autenticação e contrato de eventos; envio remoto exige ação explícita. Nenhum envio implementado.',docs='https://docs.n8n.io/integrations/builtin/core-nodes/n8n-nodes-base.webhook/')]

def registrar(bp):
    @bp.get('/capacidades')
    def extension_capabilities():
        from ed_destinations import status
        return jsonify([dict(**x, **{k:v for k,v in status('n8n' if x['id']=='webhooks' else x['id']).items() if k in ('estado','ultima_execucao','consumo')}, limite='Teste de conexão/capacidade implementado. Publicação e envio de eventos não são automáticos.') for x in EXTENSIONS])
