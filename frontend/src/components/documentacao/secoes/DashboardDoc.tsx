import { DocSection, DocH2, DocP, DocList } from "@/components/documentacao/DocSection"

export function DashboardDoc() {
  return (
    <DocSection titulo="Dashboard geral">
      <DocP>
        A página inicial do sistema é uma visão executiva combinada dos dois
        canais — não mostra listas de leads, só métricas e atalhos.
      </DocP>

      <DocH2>O que cada bloco mostra</DocH2>
      <DocList>
        <li>
          <strong>Métricas combinadas</strong>: total de leads ativos
          (separado por canal também), contatados, fechados, taxa de
          conversão e follow-ups para hoje — somando Maps + Instagram.
        </li>
        <li>
          <strong>Follow-ups de hoje</strong>: lista dos leads com follow-up
          vencido ou para hoje, dos dois canais juntos, com atalho direto pra
          cada um.
        </li>
        <li>
          <strong>Funil de conversão combinado</strong>: quantos leads
          alcançaram cada estágio (novo → contatado → respondeu → fechou),
          somando os dois canais.
        </li>
        <li>
          <strong>Ranking de nichos combinado</strong>: total e taxa de
          conversão por nicho, somando os dois canais quando o nome do nicho
          coincide.
        </li>
        <li>
          <strong>Atalhos</strong>: cards de navegação rápida para Leads do
          Google Maps, Leads do Instagram e Analytics do Maps.
        </li>
      </DocList>
    </DocSection>
  )
}
