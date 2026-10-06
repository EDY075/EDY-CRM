# Verificação da distribuição pública

Rodada de **5 de outubro de 2026**, em Windows, Python 3.12.10, Node.js 24.17.0 e Chrome. Relatório da cópia pública isolada, a partir do snapshot local `eba7049`; não soma execuções repetidas nem confunde testes com operações de fornecedores.

## Instalação e checks

| Verificação executada | Resultado e alcance |
|---|---|
| `configurar-ed-crm.ps1`, pasta nova | Ambiente Python e dependências npm próprios, a partir dos locks; build concluído. Nenhum banco/sessão do CRM em uso foi copiado |
| `python -m pytest -q --disable-warnings --basetemp=.cache/pytest-public-final` | **675 testes passaram em 147,95 s**. Inclui bancos temporários, adaptadores com mocks, exportação, contexto, versões e processos; não certifica acesso externo |
| `npm run build` | TypeScript e Vite concluídos após a atualização pontual de dependência |
| `npm run lint` | **0 erros; 2 avisos herdados** de Fast Refresh, em `frontend/src/components/ui/button.tsx:67` e `badge.tsx:49` |
| `npm audit` | **0 vulnerabilidades conhecidas** no lock do frontend na data da consulta. Não cobre desktop legado nem todo serviço externo |
| `pip-audit -r backend/requirements-lock.txt --no-deps --disable-pip` | **0 vulnerabilidades conhecidas** no lock Python na data da consulta. Consulta a advisories não equivale a revisão integral de código |
| Seed fictício pelo pipeline existente | 3 empresas, briefs revisados, materiais próprios, oportunidades, tarefas, pacotes e 3 construções locais concluídas; execução idempotente e rejeição de banco diferente testadas |
| Iframe em porta alternativa | HTML estático permite somente a origem loopback configurada na CSP; origem remota recusada. Abertura real em 5180, além da porta padrão 5128 |

O audit inicial encontrou o advisory de source-map-js; foi aplicada somente a atualização transitiva **1.2.1 → 1.2.2**, mantendo as outras dependências. Fonte: [GHSA-68fv-2mgg-jv7q](https://github.com/advisories/GHSA-68fv-2mgg-jv7q).

Depois dos commits de distribuição, um **clone Git limpo** foi instalado novamente com o script documentado e iniciado em 5181, com outro `data-demo/` próprio. As três prévias devolveram HTTP 200, identidade da empresa correspondente e origem correta na CSP. O banco `data/` não existia nesse clone. Os 33 hashes do pacote exportado permaneceram idênticos após o checkout. As seis regressões de distribuição passaram novamente (**6 testes em 5,75 s**); são repetição de parte dos 675, não seis testes adicionais.

Não execute duas sessões de pytest usando a mesma pasta `--basetemp`: elas removem/recriam os mesmos arquivos. O `pytest.ini` mantém os temporários no checkout.

## Aplicação realmente servida

O checkout público foi servido com banco próprio de demonstração em loopback, porta 5180, preservando o CRM original na porta 5128. Foram inspecionados dashboard, leads, galeria de estudos, montagem, HTML dentro do iframe e compositor de texto/voz. As capturas são da interface real, com dados fictícios.

Desktop e viewport de celular de **390 px** foram conferidos no Chrome. Dashboard e HTML abriram sem overflow horizontal na largura móvel; imagens locais carregaram. A navegação de demonstração e os controles de desktop/celular foram usados. Isso é uma inspeção dirigida, não uma certificação geral de acessibilidade, desempenho ou todos os dispositivos. Os temas e movimentos existentes foram preservados; nenhum novo redesign foi feito nesta rodada.

As ilustrações do exemplo são desenhos geométricos originais, sem IA. As prévias foram produzidas pelo construtor local `template_construcao`. O compositor mostra microfone/transcrição revisável, mas **não foi feita nova gravação humana ou inferência Codex no checkout público**. A validação real anterior está delimitada no [case](CASE-STUDY.md) e na [matriz de integrações](INTEGRACOES.md).

Testes de navegador adicionais em `frontend/tests/` usam Playwright e exigem seu browser/runtime de teste, além dos endpoints e configurações indicados em cada arquivo. Não foram contados como executados nesta rodada. Desktop Electron/instalador legado e Linux/macOS não foram empacotados ou validados.

## Publicação e privacidade

`scripts/auditar-publicacao.py` verifica nomes privados/gerados, tamanho e padrões conhecidos de credenciais no índice e em todos os blobs do histórico público. A auditoria do histórico limpo não apresentou achados. Ela omite valores encontrados e não substitui revisão humana. Arquivos de banco, uploads reais, `.env`, logs, backups, caches, binários de runtime e autenticação nativa permanecem fora do Git público.

Documentos e capturas foram revisados para não expor carteira, conta autenticada ou materiais comerciais privados. O exemplo exportado pode ser extraído em outra pasta; documentos, manifestos e materiais usam caminhos relativos. O README e as capturas foram verificados após a publicação no GitHub; o autor, branch e commit remoto são conferidos separadamente do estado local.

Limitações de permissão, modelo e licença de materiais continuam valendo. Clonar o projeto não configura Google, Instagram, API de imagens, voz externa ou runtime/login Codex. Publicar este case não publica páginas de clientes nem envia mensagens de prospecção.
