# EDY CRM — case de engenharia

**Desenvolvido por EDY GOMES, a partir do ProspectOS.** Este relato descreve um sistema local em evolução, não resultados comerciais ou sites oficiais de clientes.

## Contexto

O objetivo começou com pesquisar uma empresa, revisar informações, escolher imagens e preparar uma landing page de prospecção. Ao acrescentar referências, versões, refinamento e alternativas de executor, ficou necessário manter o contexto entre etapas e explicar o estado real de cada operação.

React, Flask e SQLite foram preservados da base. SQLite oferece persistência local de leads, decisões e checkpoints sem exigir infraestrutura externa; Flask coordena os adaptadores; React apresenta pesquisa, biblioteca, estúdio e conversa. O modo pessoal permanece disponível e usuários/workspaces são opcionais. Migrações são realizadas pelo setup dos módulos, sem exigir um dump privado.

## Decisões

**Revisão antes da execução.** O brief adaptativo conserva versão, fatos confirmados, sugestões e decisões manuais. Regras específicas de empresa/projeto são resolvidas por escopo. Observações do modelo permanecem candidatas até revisão, evitando transformar uma correção local em preferência global.

**Composição antes de HTML.** O estúdio guarda propostas raster, direção visual, escolhas por seção e autorização de trabalho. O executor recebe a composição escolhida, o brief revisado, referências e materiais por meio do pacote/contexto do pipeline existente. Manifestos e snapshots permitem inspecionar o que chegou ao executor. Uma composição escolhida pelo operador não equivale à aprovação pelo titular da empresa.

**Codex nativo e rotas distintas.** O app-server local utiliza a CLI oficial fixada, em cache nativo isolado. O plano ChatGPT e a API com chave são rotas diferentes; não existe troca silenciosa de cobrança. `model/list` é evidência de catálogo, não de acesso. Erros de modelo, autenticação, limite e serviço são mantidos como estados distintos. O streaming é consumido até conclusão; interrupção ou resposta parcial não produz sucesso.

**Fila persistente.** Intenção, IDs de operação, etapas, bases e versões são gravados antes da espera. A recuperação consulta o checkpoint, em vez de criar outro projeto. Concorrência limitada, idempotência, cancelamento cooperativo e verificação da versão base reduzem duplicações e escritas tardias. Restaurar uma versão invalida a aplicação automática de um resultado baseado em outro estado.

**Materiais como dados externos.** Sites, perfis, HTMLs de referência e imagens não são instruções confiáveis. Origem, autorização, seleção, original e versões são registrados. O exportador usa caminhos relativos e confere arquivos/manifestos; materiais apenas por link ou sem permissão não viram fotos locais autorizadas. Nenhuma foto genérica comprova equipe ou instalações.

## Problemas demonstrados e reparos

| Problema observado | Tratamento comprovado no código e na validação local |
|---|---|
| Prévias existiam em disco, mas eram difíceis de localizar | Listagem estável ligada a empresa/construção, ações de abrir/refinar em áreas do CRM e reaproveitamento de conversa |
| Servidor de HTML encerrado após reiniciar o CRM | Recuperação do processo a partir dos mesmos arquivos, sem nova geração; porta disponível escolhida localmente |
| Miniatura pronta parecia indicar página disponível | Estado da página é verificado separadamente: associação, processo e conteúdo entregue, incluindo assets locais |
| Porta antiga podia pertencer a outra versão/empresa | Registro do processo e comparação do HTML servido impedem tratar um servidor incorreto como a prévia esperada |
| Execução longa ou resposta incompleta parecia continuar para sempre | Heartbeat, prazo, classificação de erro e status de conclusão explícito; falha não apaga versões anteriores |
| Comando de voz recebido sem resultado imediatamente claro | Transcrição revisável, comando persistido, progresso resumido, detalhes recolhidos e acesso ao resultado vinculado à versão |
| Tarefa sem vencimento quebrava o resumo | Na preparação pública, campo vazio foi convertido a condição booleana antes da soma; regressão testada |

Na validação privada que originou este snapshot, uma gravação por **microfone físico**, confirmada pelo operador, foi recebida, transcrita localmente e encaminhada ao refinamento nativo. Geração e refinamentos Codex concluídos produziram novas versões associadas ao lead. Também foram abertas seis prévias existentes e preservadas as anteriores. Arquivos privados, conteúdo comercial, identidades de conta e gravação humana não foram publicados. Isso comprova aquele fluxo e ambiente; não certifica todos os microfones, navegadores ou contas.

Uma sessão nativa revogada retornou HTTP 401 com código de invalidação. A renovação autorizada da mesma conta foi recuperada e a inferência concluída posteriormente. Isso não provou restrição de plano nem troca A→B. O fallback OpenCode retornou 403 na rota oficial testada; não foi contornado por identidade de cliente falsa.

## Evidência pública reproduzível

![Interface real com dados fictícios](images/dashboard-desktop.jpg)

O exemplo público substitui carteira e fotos reais por três empresas explicitamente fictícias de nichos diferentes. Dados comerciais completos são inventados **para o exemplo**, contatos não acionáveis e ilustrações próprias são identificados. Exportação e construção determinística são operações locais reais, usando o pipeline de templates existente. Não são inferência de IA nem transcrição simulada.

As [capturas desktop/mobile](DEMONSTRACAO.md) mostram o aplicativo servido no checkout isolado, seleção visual, montagem, HTML disponível e compositor de texto/voz. O [relatório](VERIFICACAO.md) separa testes técnicos, inspeção no navegador e operações externas históricas; mocks de adaptadores não contam como operação do fornecedor.

## Aprendizados e limites

O fluxo ficou mais complexo que o objetivo inicial de gerar uma landing simples. Brief, direção visual, materiais, composição e contextos evitam perda de informação, mas também aumentam decisões e navegação. Simplificar o caminho mais frequente e explicar melhor as dependências é uma oportunidade futura, **não uma entrega concluída** deste case.

Build não avalia acabamento editorial. A qualidade depende de revisão humana de fatos, copy, identidade, recortes, CTAs, teclado, responsividade e movimento. A prévia reprovada pelo operador foi registrada como feedback de projeto; templates locais continuam úteis para experimentar o pipeline, sem serem anunciados como equivalentes à composição personalizada por Codex.

Permanecem acessos externos, permissão de uso dos materiais, modelos locais opcionais para voz e validação de troca entre contas. A aplicação não foi implantada em produção nesta entrega e não publica páginas ou envia prospecção automaticamente. Não há alegação de contratos, conversões ou ganho comercial.

## Publicação sem perda de dados

O histórico original e o CRM em uso foram preservados. O repositório público começa com snapshot limpo de código distribuível, mantém a MIT/atribuição do ProspectOS e exclui bancos, backups, sessões, uploads e evidências com clientes reais. A instalação foi feita do zero em outra pasta, com dependências próprias e banco próprio; não reutiliza credenciais do mantenedor.
