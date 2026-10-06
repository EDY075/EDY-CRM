"""Diagnóstico GET sem rede. Adaptadores executam somente por ações explícitas.

Não reutiliza os tokens/cookies do ProspectOS ou do navegador. Os campos antigos
google/instagram são metadados declarativos; conectores contém estados validados.
"""
import json
import os
import re
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent


def status():
    file = ROOT / 'config/integrations.local.json'
    configured = file.exists()
    issue = ''
    try:
        if configured and file.stat().st_size > 16000:
            raise ValueError()
        data = json.loads((file if configured else ROOT / 'config/integrations.example.json').read_text(encoding='utf-8-sig'))
        google = data['google_places']
        instagram = data['instagram']
        if not isinstance(google, dict) or not isinstance(instagram, dict):
            raise ValueError()
    except (OSError, ValueError, KeyError, TypeError):
        google, instagram = {}, {}
        issue = 'Arquivo local inválido. Confira config/integrations.local.json; nenhum acesso externo foi feito.'
    present = lambda name: bool(os.environ.get(name, '').strip())
    from flask import has_app_context
    from ed_services import cards, locais
    connectors = cards()
    return {
        'conectores': connectors,
        'locais': locais() if has_app_context() else {},
        'arquivo_local': configured, 'erro_configuracao': issue, 'consulta_externa_ativa': False,
        'google': {'credencial_presente': present('ED_CRM_GOOGLE_PLACES_KEY'), 'exportavel': False,
            'modo': 'referencia_transitoria', 'estado': 'caso_de_uso_pendente',
            'pendencias': ['Projeto Google Cloud, billing e Places API (New)', 'Chave restrita no servidor e cotas',
                'Termos limitam diretórios, produtos publicitários, cópia e armazenamento; não adotado como base de prospecção do CRM',
                'Caso de uso, termos públicos, privacidade e atribuição a revisar', 'Conteúdo Places não entra no banco nem no ZIP; somente place_id tem exceção geral de retenção']},
        'instagram': {'credencial_presente': present('ED_CRM_INSTAGRAM_ACCESS_TOKEN'),
            'app_configurado': bool(str(instagram.get('app_id', '')).isdigit()),
            'conta_configurada': bool(str(instagram.get('account_id', '')).isdigit()),
            'versao_configurada': bool(re.fullmatch(r'v\d{2}\.\d+', str(instagram.get('api_version', '')))),
            'estado': 'configuracao_preparada', 'login': 'instagram', 'permissoes': ['instagram_business_basic'],
            'pendencias': ['Aplicativo Meta e conta profissional autorizada', 'OAuth, token e versão suportada no painel Meta',
                'Revisão do aplicativo para uso por contas externas conforme o nível de acesso',
                'Não é busca universal de empresas ou acesso a perfis pessoais; exportar mídia exige direitos próprios']},
    }
