"""Completa pins do runtime instalado; não inclui ferramentas avulsas de QA."""
from pathlib import Path
import importlib.metadata as metadata
from packaging.requirements import Requirement
from packaging.utils import canonicalize_name

ROOT = Path(__file__).resolve().parents[1]
file = ROOT / 'backend/requirements-lock.txt'
existing = {}
for raw in file.read_text().splitlines():
    line = raw.strip()
    if line and not line.startswith('#'):
        requirement = Requirement(line)
        existing[canonicalize_name(requirement.name)] = requirement
roots = [Requirement(line) for line in (ROOT/'backend/requirements.txt').read_text().splitlines() if line.strip() and not line.startswith('#')]
pending = [r.name for r in [*existing.values(), *roots]]
pins = {}
while pending:
    name = canonicalize_name(pending.pop())
    if name in pins:
        continue
    distribution = metadata.distribution(name)
    version = distribution.version
    if name in existing:
        assert version in existing[name].specifier, 'Não atualizar pin anterior sem revisão: '+name
    pins[name] = distribution.metadata['Name']+'=='+version
    for raw in distribution.requires or []:
        requirement = Requirement(raw)
        if requirement.marker and not requirement.marker.evaluate({'extra': ''}):
            continue
        assert metadata.version(requirement.name) in requirement.specifier
        pending.append(requirement.name)
for requirement in roots:
    assert metadata.version(requirement.name) in requirement.specifier
file.write_text('\n'.join(pins[name] for name in sorted(pins))+'\n', encoding='utf-8')
print('Pins anteriores preservados; novas dependências de runtime: '+', '.join(sorted(set(pins)-set(existing))))
