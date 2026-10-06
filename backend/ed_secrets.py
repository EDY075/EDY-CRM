"""Segredos no processo ou DPAPI do usuário Windows, sempre fora do SQLite/GET."""
import ctypes
from ctypes import wintypes
import json
import os
from threading import RLock
import ed_store as store

ENV = {'google': 'ED_CRM_GOOGLE_PLACES_KEY', 'firecrawl': 'ED_CRM_FIRECRAWL_KEY',
       'openai': 'ED_CRM_OPENAI_KEY', 'instagram': 'ED_CRM_INSTAGRAM_ACCESS_TOKEN',
       'apify':'ED_CRM_APIFY_TOKEN','openai_imagens':'ED_CRM_IMAGES_KEY', 'meta_discovery':'ED_CRM_META_DISCOVERY_TOKEN','codex_api':'ED_CRM_CODEX_API_KEY','twentyfirst':'ED_CRM_21ST_KEY','infisical':'ED_CRM_INFISICAL_CLIENT_SECRET','voz':'ED_CRM_VOICE_KEY','openrouter':'ED_CRM_OPENROUTER_KEY','opencode_server':'ED_CRM_OPENCODE_SERVER_PASSWORD'}
lock = RLock()
ENV['gateway']='ED_CRM_GATEWAY_KEY'
ENV['gateway_dashboard']='ED_CRM_GATEWAY_DASHBOARD_PASSWORD'


class Blob(ctypes.Structure):
    _fields_ = [('size', wintypes.DWORD), ('data', ctypes.POINTER(ctypes.c_ubyte))]


def crypt(content, decrypt=False):
    if os.name != 'nt':
        raise ValueError('Use variáveis do processo neste sistema; armazenamento protegido requer Windows DPAPI.')
    buf = (ctypes.c_ubyte * len(content)).from_buffer_copy(content)
    source, target = Blob(len(content), buf), Blob()
    method = ctypes.windll.crypt32.CryptUnprotectData if decrypt else ctypes.windll.crypt32.CryptProtectData
    if not method(ctypes.byref(source), None, None, None, None, 1, ctypes.byref(target)):
        raise ValueError('Não foi possível acessar o cofre local deste usuário Windows.')
    try:
        return ctypes.string_at(target.data, target.size)
    finally:
        ctypes.windll.kernel32.LocalFree(target.data)


def read():
    p = store.pasta() / 'credenciais.dpapi'
    if not p.exists():
        return {}
    try:
        if p.stat().st_size > 16000:
            raise ValueError()
        return json.loads(crypt(p.read_bytes(), True))
    except (OSError, ValueError, TypeError):
        raise ValueError('Cofre indisponível; reconfigure as credenciais neste usuário Windows.') from None


def get(provider):
    value = os.environ.get(ENV[provider], '').strip()
    if provider == 'openai' and not value:
        value = os.environ.get('OPENAI_API_KEY', '').strip()
    if value:
        return value
    with lock:
        return read().get(provider, '')


def put(provider, value):
    value = store.texto(value, 4000)
    with lock:
        values = read()
        if value:
            values[provider] = value
        else:
            values.pop(provider, None)
        p = store.pasta() / 'credenciais.dpapi'
        tmp = p.with_suffix('.tmp')
        tmp.write_bytes(crypt(json.dumps(values).encode()))
        tmp.replace(p)
