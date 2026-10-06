import type { StatusLead } from "@/types/lead"

export type EtapaInstagram = "raspando" | "enriquecendo" | "classificando" | ""

export interface EstadoAnaliseInstagram {
  rodando: boolean
  mensagem: string
  etapa: EtapaInstagram
  perfis_encontrados: number
  perfis_processados: number
  post_id: number | null
}

export type PrioridadeLead = "alta" | "media" | "baixa" | "descartado"

export interface ContagemLeadsPorPrioridade {
  alta: number | null
  media: number | null
  baixa: number | null
  descartado: number | null
  pendente: number | null
  ignorado: number | null
  total: number
}

export interface PostInstagram {
  id: number
  post_url: string
  criado_em: string
  etapa: "pendente" | "raspando" | "enriquecendo" | "concluido" | "erro"
  total_comentarios: number | null
  total_perfis: number | null
  erro_mensagem: string | null
  nicho_alvo: string | null
  arquivado_em: string | null
  contagem_leads: ContagemLeadsPorPrioridade
  pode_retomar: boolean
}

export interface RespostaMarcarFollowup {
  ok: true
  follow_ups_enviados: number
  ultimo_followup_em: string
  proximo_followup_sugerido: string
}

export interface RespostaGerarMensagemInstagram {
  mensagem: string
  provedor?: string
  avisos?: string[]
}

export interface LeadInstagram {
  id: number
  post_id: number
  username: string
  full_name: string | null
  is_private: boolean | null
  biography: string | null
  seguidores: number | null
  is_business_account: boolean | null
  comentarios: string[]
  prioridade: PrioridadeLead | null
  justificativa: string | null
  sugestao_dm: string | null
  status: StatusLead
  nicho: string | null
  observacoes: string | null
  tags: string | null
  proximo_followup: string | null
  atualizado_em: string | null
  follow_ups_enviados: number
  ultimo_followup_em: string | null
  lead_dificil: boolean
}

export interface MetricasInstagram {
  total: number
  por_status: Record<string, number>
  taxa_conversao: number
  lembretes_hoje: number
}

export interface EstagioFunilInstagram {
  status: StatusLead
  total: number
}

export interface FunilInstagram {
  estagios: EstagioFunilInstagram[]
}

export interface NichoInstagramAnalytics {
  nicho: string
  total: number
  fechados: number
  taxa_conversao: number
}

export interface PorNichoInstagram {
  nichos: NichoInstagramAnalytics[]
}
