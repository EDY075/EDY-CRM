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

## Apresentação em vídeo — 6 de outubro de 2026

Rodada restrita a mídia e documentação. Não houve mudança no código da aplicação, novo build ou nova execução da suíte: os resultados técnicos acima pertencem à entrega de distribuição identificada.

O tour inclui 30 áreas gravadas da demonstração local. Os 30 pontos médios, abertura, encerramento e cortes foram inspecionados; três enquadramentos foram corrigidos. A cobertura de caracteres das legendas foi conferida na fonte Geist latin. O MP4 compacto tem 96 s, 2.880 frames, H.264 1920 × 1080 a 30 fps e AAC estéreo 48 kHz, **9.483.155 bytes**. Master e compacto passaram pela decodificação integral do FFmpeg sem erros. No Chrome, o compacto carregou 96 s de duração e avançou até 19,83 s após iniciar pelo teclado, sem erro de mídia.

Os quatro arquivos de mídia têm hashes e dimensões no [manifesto](assets/media-manifest.json); **41 links relativos** do README, NOTICE e documentos foram conferidos nesta revisão. A versão de maior qualidade fica na release e a compacta no Git. A publicação e a reprodução nativa no README são verificadas após o push.

Um aviso Impeccable de contraste na página local de reprodução assumiu fundo branco, embora o Chrome mostrasse fundo `#080d19`. Os pares reais foram medidos em 17,55:1, 12,35:1 e 9,22:1. Registrou-se exceção somente de `low-contrast` para esse arquivo local ignorado; nenhum detector da aplicação foi desativado. Problemas reais corrigidos: fonte e enquadramentos. Nenhum achado incerto ficou aberto nesse visualizador.

O [roteiro e alcance do vídeo](APRESENTACAO.md) distinguem tour da interface, construção local e operações externas. Não há novos testes de inferência, microfone físico ou coleta de fornecedores nesse vídeo.

Após publicar o commit de mídia `ce9fa4b7be1cb7550d897830ac1b2ad58aeb24a6`, o repositório foi confirmado como **PUBLIC**, conta **EDY075**, branch **main**, com o mesmo SHA remoto. A capa no README carregou largura natural de 1.920 px. O player nativo do GitHub carregou duração de 96 s e avançou até **25,84 s** após iniciar pelo teclado, sem erro de mídia. A [captura da publicação](images/github-video-publicado.png) mostra a reprodução pausada, mantendo o entorno real do README.

Os quatro assets da [release de mídia](https://github.com/EDY075/EDY-CRM/releases/tag/case-media-2026-10-06) foram conferidos por nome e tamanho. O master MP4 respondeu **HTTP 200 sem autenticação**, com 30.735.132 bytes. O índice público de 540 arquivos e os quatro commits existentes nesse ponto foram auditados sem achados dos padrões conhecidos. As alterações de apresentação não modificaram backend, frontend, seed ou exemplo exportado.
