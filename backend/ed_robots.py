"""Política e evidência robots.txt. Protego fixado em 0.6.2 (correção ReDoS).

Somente can_fetch decide a permissão. A inspeção interna abaixo serve para
explicar a mesma decisão; testes cobrem o contrato da versão fixada.
"""
from urllib.parse import urlsplit, urlunsplit
from protego import Protego
from protego._utils import _quote_path


class Policy:
    def __init__(self, text):
        self.parser = Protego.parse(text)

    def check(self, url, agent):
        parsed = urlsplit(url)
        path = urlunsplit(('', '', parsed.path or '/', parsed.query, ''))
        # Protego espera URL/path com / inicial, inclusive em host sem barra.
        normalized = urlunsplit((parsed.scheme, parsed.netloc, parsed.path or '/', parsed.query, ''))
        allowed = self.parser.can_fetch(normalized, agent)
        rules = self.parser._get_matching_rule_set(agent)
        matched = next((r for r in rules._rules if r.value.match(_quote_path(normalized))), None) if rules else None
        return dict(url=url, caminho=path, permitido=allowed,
                    grupo=rules.user_agent if rules else '(nenhum)',
                    regra=f'{matched.field.capitalize()}: {matched.value._pattern}' if matched else '(nenhuma regra correspondente)')

    def delay(self, agent):
        return max(1, self.parser.crawl_delay(agent) or 1)
