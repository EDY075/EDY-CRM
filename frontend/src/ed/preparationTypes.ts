export interface Framing { x: number; y: number; recorte: string; enquadramento: string }
export interface Placement { material_id: string; funcao: string; natureza: string; pessoa: string; desktop: Framing; mobile: Framing }
export interface Section { id: string; titulo: string; texto: string; revisado: boolean }
export interface Preparation {
  revisao: number; modo: string; objetivo: string; publico: string; oferta: string; cta: string; prospeccao: string;
  funcionalidades: string; banco: string; administracao: string;
  design: Record<string, string>; referencias: { url: string; material_id: string; observacao: string }[];
  imagens: Placement[]; secoes: Section[]
}
export interface Connector { status_acesso?:string;adaptador?:string;autenticacao?:string;conta_projeto?:string;autenticacao_validada_em?:string;operacoes_validadas?:Record<string,string>; nome: string; finalidade: string; estado: string; credencial_presente: boolean;
  configuracao: string; recursos: string[]; limites: string; docs: string; config: Record<string, string>;
  ultima_execucao: string; consumo: Record<string, number> | null; mensagem: string; implementacao_pendente: string[] }
export interface Operation<Result = unknown> { id: string; fornecedor: string; estado: string; mensagem: string; progresso: number;
  resultado?: Result; revisao?: number; proposta?: { prospeccao: string; secoes: Omit<Section, 'revisado'>[] } }
