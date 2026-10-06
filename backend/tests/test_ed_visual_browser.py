import json
from pathlib import Path
from PIL import Image
import ed_visual_browser as browser
import ed_visual_research as visual
from test_ed_enrich import client


def test_browser_failure_never_creates_reference_or_reports_success(client,monkeypatch):
 monkeypatch.setattr(visual,'destino',lambda u:None)
 monkeypatch.setattr(visual,'robots_checker',lambda j: (j.update(robots={}) or (lambda _:0)))
 def fail(*args):raise ValueError('Chrome indisponível; nenhum conteúdo coletado.')
 monkeypatch.setattr(browser,'render',fail)
 before=client.get('/api/ed/biblioteca').json
 result=client.post('/api/ed/biblioteca/pesquisar-visual',json={'titulo':'Falha','url':'https://example.org','fonte':'browser'}).json
 assert result['estado']=='erro'
 assert client.get('/api/ed/biblioteca').json==before


def test_browser_results_are_inactive_and_both_images_attached(client,monkeypatch,tmp_path):
 monkeypatch.setattr(visual,'destino',lambda u:None)
 monkeypatch.setattr(visual,'robots_checker',lambda j: (j.update(robots={}) or (lambda _:0)))
 for name in ('desktop','mobile'):Image.new('RGB',(400,300),'#286582').save(tmp_path/(name+'.jpg'))
 observed={'viewports':[{'viewport':'desktop','titulos':['Exemplo']}],'observacoes':['XHR bloqueado; limites explícitos.']}
 monkeypatch.setattr(browser,'render',lambda *args:(observed,tmp_path))
 result=client.post('/api/ed/biblioteca/pesquisar-visual',json={'titulo':'Render','url':'https://example.org','fonte':'browser'}).json
 assert result['estado']=='concluida'
 for ident in ('biblioteca_id','biblioteca_mobile_id'):
  item=client.get('/api/ed/biblioteca/'+result['resultado'][ident]).json
  assert item['estado']=='inativo' and item['original']['sha256']
 assert len(result['resultado']['capturas'])==2


def test_chrome_bridge_rejects_private_target_and_no_provider_secret(client,monkeypatch):
 import requests
 monkeypatch.setenv('OPENAI_API_KEY','do-not-inherit')
 monkeypatch.setattr(browser,'ativo',lambda _:None)
 def forbidden(*a,**k):raise AssertionError('Private URL reached collector')
 monkeypatch.setattr(browser,'ler_url',forbidden)
 class Process:
  returncode=0
  def __init__(self,args,**kw):
   env=kw['env'];assert 'OPENAI_API_KEY' not in env
   headers={'Authorization':'Bearer '+env['EDY_VISUAL_TOKEN']}
   res=requests.post(env['EDY_VISUAL_BRIDGE'],headers=headers,json={'url':'http://127.0.0.1/admin'},timeout=2)
   assert res.status_code==400
   assert requests.post(env['EDY_VISUAL_BRIDGE'],json={'url':'https://example.org'},timeout=2).status_code==403
   Path(args[-1],'resultado.json').write_text(json.dumps({'erro':'Teste do isolamento'}))
  def poll(self):return 0
 monkeypatch.setattr(browser.subprocess,'Popen',Process)
 import pytest
 with pytest.raises(ValueError,match='conteúdo renderizado'):
  browser.render({'id':'test-bridge'},'https://example.org',lambda _:0,lambda *args:None)
