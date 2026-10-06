# Integrações — capacidade e evidência

Estado da publicação em outubro de 2026. **Implementado ≠ configurado ≠ autenticado ≠ inferência concluída ≠ operação de negócio validada.** Um teste por mock valida o contrato local; não valida permissões nem disponibilidade do fornecedor. As evidências históricas abaixo vieram da instalação privada, cujas sessões/chaves não são distribuídas.

| Rota | Implementação e validação | Acesso ou limite restante |
|---|---|---|
| **Codex nativo / app-server** | Handshake, `account/read`, catálogo, teste pequeno, geração e refinamento reais concluídos; versões e HTML vinculados ao lead. CLI configurada 0.160.0 | Instalar runtime oficial compatível e autorizar login ChatGPT no novo checkout. Acesso ao modelo só comprovado por inferência. Conta ativa A→B não validada |
| Codex OAuth de consumo do plano | Adaptador com modelos/credencial da mesma rota e estados separados | Somente credencial OAuth autorizada para esta rota; não reutilizar sessão nativa como token de outro endpoint. Não comprovado como rota de criação neste case |
| OpenAI Images / imagens nativas | Adaptadores, originais, versões, autorização e progresso. Operação de imagem histórica em conta anterior | Acesso atual não comprovado. API exige chave, modelo disponível e saldo; plano Codex não concede automaticamente a API. Nenhuma geração é simulada sem acesso |
| **Transcrição local** | MediaRecorder, áudio enviado após ação explícita, worker local faster-whisper; gravação humana por microfone confirmada e transcrição real histórica | Download de modelo opcional, espaço em disco, CPU e permissão do navegador. O seed não contém gravação humana ou modelo de voz |
| Voz externa / OpenAI | Adaptador separado para transcrever e síntese opcional | Chave e saldo próprios; autenticação de catálogo não comprova transcrição. Desativado sem configuração |
| OpenRouter | Executor configurável e modelo separado do serviço de transcrição; rota gratuita apenas se autorizada/configurada | Sem chave na validação; inferência pendente. Modelos pagos não entram em fallback automático |
| OpenCode | Integração com runtime/CLI oficial e recuperação de contexto | HTTP 403 real na rota testada; artefato/build/refinamento por fallback não concluídos. Não contornar recusa falsificando cliente |
| 9Router / OmniRoute | Configuração de gateway local isolado; 9Router teve autenticação/catálogo verificados | Inferência pelo gateway não comprovada. OmniRoute é opcional, sem operação validada. Nenhum token nativo importado automaticamente |
| **OpenStreetMap** | Busca via Nominatim/Overpass, origem/atribuição e retomar; consulta real histórica retornou resultado | Serviços públicos podem retornar 429/504 ou ficar indisponíveis. ODbL/atribuição preservadas. OSM não comprova integração Google/Instagram |
| Leitura de site | Coletor local com robots.txt, fontes, sugestões, imagens e proteção de edições; operação histórica real | Site confirmado, rede e permissão do site. Páginas JS podem exigir outra fonte. Um bloqueio correto é mantido |
| Google Places / Maps | Adaptador configurável para referência transitória, campo de identificação, atribuição e exportação restringida | Desativado para alimentar o CRM nesta distribuição. Billing, chave, termos e revisão do caso de uso; nenhuma consulta Places real validada neste case |
| Instagram Login / Meta | Leitura de conta profissional autorizada e materiais suportados; conta pessoal/pesquisa universal não presumidas | App Meta, versão API, permissões, token e autorização do titular; OAuth automático ainda pendente. Nenhuma importação real validada nesta instalação |
| Meta Business Discovery | Rota separada para perfil profissional conhecido, com evidências/carrosséis suportados | Facebook Login, conta profissional vinculada e permissões/revisão específicas. Instagram Login sozinho não concede esse acesso |
| Apify | Adaptador separado de perfis públicos, origem, itens de carrossel e erros parciais | Token, actor/contrato compatível, limites e direitos de uso. Operação real pendente; coleta pública não concede licença das imagens |
| Firecrawl | Leitura alternativa configurável e diagnóstico por etapa | Chave, plano/cota e adequação da URL. Operação real pendente |
| Pesquisa visual de sites | Browser local isolado, captura/consulta e importação com origem; testes de contrato | Browser instalado e fontes acessíveis. Não garante acesso a perfil logado, publicação ou autorização das imagens |
| 21st.dev MCP | Configuração/encaminhamento ao runtime e biblioteca de componentes | Chave, instalação e sessão habilitada; nenhuma chamada real comprovada no piloto |
| GitHub | CLI da conta do autor verificada; leitura de repositórios histórica. Publicação deste case autorizada e verificada separadamente | Um novo usuário precisa autenticar a própria conta. Publicar páginas de clientes requer autorização específica |
| Cloudflare Pages | Destino e configuração guiada | Token/conta, projeto e autorização de publicar; nenhum deploy de cliente nesta entrega |
| Armazenamento remoto / S3 | Adaptador, configuração e controle de materiais | Endpoint, bucket, credenciais e permissão; nenhuma operação remota real validada |
| n8n / webhooks | Preparação de destino, mensagens e recuperação | Endpoint/credencial e consentimento por efeito externo; nenhum envio de prospecção nesta entrega |
| Infisical | Interface/cofre configurável | Servidor, projeto e credencial; sem operação validada |

## Preparar Codex nativo

1. Obtenha a CLI oficial compatível com o manifesto `config/codex-runtime.json` na [distribuição oficial](https://github.com/openai/codex/releases/tag/rust-v0.160.0). Os executáveis não estão no Git.
2. Use `scripts/preparar-runtime-codex.ps1 -Origem <codex.exe> -OrigemCodeModeHost <codex-code-mode-host.exe>`; o script verifica versão/hashes e mantém o runtime em `data/runtime-cli/`.
3. Em **Conexões → Codex**, escolha explicitamente o modo nativo. Faça login com a CLI/cache nativos ou autorize seguir a conta do aplicativo pelo mecanismo implementado. Nenhuma sessão do mantenedor acompanha o clone.
4. Verifique identidade, modelo e teste mínimo **antes** de construir. Se o modelo preferido for recusado, revise o erro e escolha outra opção explicitamente; não mude para API key por conta própria.

Leia a [documentação oficial do app-server](https://developers.openai.com/codex/app-server) e de [autenticação](https://developers.openai.com/codex/auth). Os detalhes de acesso evoluem; os manifestos registram a versão testada deste case, não prometem compatibilidade com todo runtime futuro.

Credenciais opcionais são listadas em `.env.example` e podem ser armazenadas pelo cofre local Windows. Valores preenchidos não mudam status para operação validada. Direitos de armazenamento/uso/exportação e a situação de cada material continuam necessários mesmo após conexão bem-sucedida.
