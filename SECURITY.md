# Segurança e publicação

Esta aplicação foi verificada para uso **local em loopback**, não como serviço público de produção. O servidor recusa hosts remotos; prévias usam processos/origens separados e iframe restrito. Não altere o bind para expor o CRM na internet sem revisão de autenticação, rede e implantação.

Credenciais dos conectores ficam no processo ou cofre DPAPI do usuário Windows, fora dos campos públicos do banco. Sessões nativas do Codex e API keys são rotas distintas. Autenticação não comprova direito de usar um modelo; uma operação incompleta não deve virar sucesso.

Esta distribuição não contém bancos, usuários reais, sessões, backups, uploads de clientes, `.env`, tokens, caches, runtimes baixados ou logs privados. Foi preparada como snapshot de histórico limpo, sem reescrever o histórico de desenvolvimento. O seed só opera no banco `data-demo/` do próprio checkout. Não use dados da demonstração para contatar empresas.

Antes de contribuir, execute `python scripts/auditar-publicacao.py` com arquivos adicionados ao índice Git. O script verifica nomes proibidos, padrões conhecidos de credenciais, tamanho e os blobs do histórico público. Ele não é uma prova universal de ausência de segredos: revisão humana e scanners adicionais continuam necessários. Não inclua valores sensíveis nos relatórios ou issues.

Se encontrar uma vulnerabilidade, use o canal privado de segurança do GitHub, quando habilitado, ou comunique ao mantenedor sem publicar exploração, credenciais ou dados de terceiros. Não abra issue pública com tokens ou dumps. Caso uma credencial seja exposta, remover o arquivo não revoga a credencial: é necessária rotação no serviço correspondente.
