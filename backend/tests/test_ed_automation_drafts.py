"""Importação preparada, sem afirmar execução no n8n."""
import io
import json
import zipfile
from test_ed_enrich import client

def test_drafts_have_no_remote_effects_or_secrets(client):
    response=client.get('/api/ed/destinos/n8n/rascunhos')
    assert response.status_code==200
    with zipfile.ZipFile(io.BytesIO(response.data)) as z:
        names=z.namelist()
        assert len(names)==4 and 'LEIA-ME.md' in names
        for name in names:
            if name.endswith('.json'):
                flow=json.loads(z.read(name))
                assert flow['active'] is False
                assert {n['type'] for n in flow['nodes']}=={'n8n-nodes-base.manualTrigger','n8n-nodes-base.set','n8n-nodes-base.stickyNote'}
                assert all('credentials' not in n for n in flow['nodes'])
                assert 'rascunho_sem_operacao_remota' in z.read(name).decode()
