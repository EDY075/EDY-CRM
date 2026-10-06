export interface Fonte {
  campo: string; valor: string; fornecedor: string; url: string
  consultado_em: string; verificacao: string; retencao: string; exportavel: boolean
}
export interface Material {
  natureza?: string
  id: string; arquivo: string; nome_original: string; categoria: string; origem: string
  atribuicao: string; posicao: string; autorizado: boolean; selecionado: boolean; arquivo_url: string
}
export interface Exportacao {
  id: string; versao: number; criado_em: string; zip_url: string; markdown_url: string
}
export interface Previa {
  id: string; url: string; exportacao_id: string; observacoes: string; criado_em: string
  construcao_id?: string; url_ativa?: string | null
}
export interface Briefing {
  objetivo: string; publico: string; cta: string; secoes: string
  direcao: string; diagnostico: string; complemento: string
}
export interface Empresa {
  crm_arquivada?: boolean; crm_unida_em?: string; crm_historicos_relacionados?: string[];
  id: string; nome: string; nicho: string; cidade: string; uf: string; bairro: string
  endereco: string; telefone: string; site: string; instagram: string; servicos: string
  horarios: string; descricao: string; email: string; redes_sociais: string; fonte_url: string; confirmado: boolean; demonstracao: boolean; etapa: string
  observacoes: string; briefing: Partial<Briefing>; fontes: Record<string, Fonte>
  materiais: Material[]; exportacoes: Exportacao[]; previas: Previa[]
  pendencias: string[]; possiveis_duplicatas: string[]; atualizado_em: string
  total_exportacoes: number; total_previas: number
  fonte_busca_url: string; fonte_mapa_url: string;
  associacao_site: { estado: 'pendente' | 'confirmado'; url: string; motivo: string; evidencias: SiteEvidence[] };
  historico_site: { valor_anterior: string; valor_novo: string; motivo: string; registrado_em: string; fonte_anterior: Partial<Fonte> }[];
  links_fontes: { url: string; tipo: string; motivo: string; registrado_em: string }[];
}
export interface SiteEvidence { campo: string; evidencia: string; origem: string; metodo: string }
export interface SiteProposal { site: string; estado: string; mensagem: string; evidencias: SiteEvidence[]; ambiguo: boolean; consultado_em: string; url_final?: string;
  erro?: { tipo: string; mensagem: string }; robots?: Pesquisa['robots'] }
export interface SiteAssociation { associacao: Empresa['associacao_site']; proposta: SiteProposal | null }
export interface Config {
  osm_habilitado: boolean; nichos: string[]; etapas: string[]; fonte: string; atribuicao: string
}
export interface Campanha {
  progresso?:number; etapa?:string; erro_tipo?:string
  id: string; nicho: string; cidade: string; uf: string; bairro: string; limite: number; prioridade?:string
  estado: string; mensagem: string; encontrados: number; novos: number; repetidos: number
  empresa_ids: string[]; criado_em: string
  historico_execucoes?: {execucao_id?:string;iniciado_em?:string;estado:string;mensagem:string;encontrados:number;novos:number;repetidos:number}[]
}
export interface Documento { markdown: string; prompt: string; briefing: Briefing }
export interface Sugestao { id: string; campo: keyof Empresa; valor: string; origem: string; evidencia: string; metodo: string; aplicado: boolean }
export interface Candidata { id: string; url: string; origem: string; descricao: string; categoria: string; previa_url: string; material_id?: string }
export interface Pesquisa { id: string; empresa_id: string; site: string; fornecedor?: string; estado: string; mensagem: string; progresso: number;
  sugestoes: Sugestao[]; imagens: Candidata[]; paginas: { url: string; estado: string }[];
  criado_em?: string;
  diagnostico_atual?: { estado: string; mensagem: string; consultado_em: string; robots?: Pesquisa['robots'] };
  robots?: { user_agent: string; parser: string; documentos: { url: string; url_final?: string; estado: string; http_status?: number; sha256?: string }[];
    avaliacoes: { url: string; caminho: string; permitido: boolean; grupo: string; regra: string; robots_url: string }[] };
  erros: { url: string; mensagem: string; tipo?: string; etapa?: string; http_status?: number; regra?: string; grupo?: string; robots_url?: string; user_agent?: string }[]; pendencias: string[] }
export interface IntegracoesStatus { arquivo_local: boolean; erro_configuracao: string; consulta_externa_ativa: boolean;
  conectores: Record<string, import('./preparationTypes').Connector>;
  locais: { osm: { estado: string; mensagem: string; data: string }; site: { estado: string; mensagem: string; criado_em: string; empresa_id: string } };
  google: { credencial_presente: boolean; pendencias: string[] };
  instagram: { credencial_presente: boolean; app_configurado: boolean; conta_configurada: boolean; versao_configurada: boolean; pendencias: string[] } }
