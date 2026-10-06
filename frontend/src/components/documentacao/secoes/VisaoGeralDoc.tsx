import {
  DocSection,
  DocH2,
  DocP,
  DocList,
} from "@/components/documentacao/DocSection"

export function VisaoGeralDoc() {
  return (
    <DocSection titulo="Visão geral">
      <DocP>
        Esta é uma ferramenta de prospecção de leads com dois canais de
        captação independentes — <strong>Google Maps</strong> e{" "}
        <strong>Instagram</strong> — que compartilham o mesmo vocabulário de
        funil, tags, observações e follow-up inteligente, mas com fluxos de
        captação bem diferentes entre si.
      </DocP>

      <DocH2>Os dois canais</DocH2>
      <DocList>
        <li>
          <strong>Google Maps</strong>: busca empresas por nicho + cidade
          (ex.: "corretor de imóveis em Curitiba"), filtra automaticamente só
          as que têm nota alta e não têm site cadastrado — são as candidatas
          mais óbvias a fechar um site novo.
        </li>
        <li>
          <strong>Instagram</strong>: analisa os comentários de um post
          específico, identificando pessoas que comentaram e classificando
          automaticamente por IA quem parece ser dono de negócio dentro de um
          nicho-alvo que você escolhe.
        </li>
      </DocList>

      <DocH2>Conceitos que valem para os dois canais</DocH2>
      <DocList>
        <li>
          <strong>Status do funil</strong>: todo lead progride por{" "}
          <em>novo → contatado → respondeu → fechou</em>. Existem também dois
          estados que saem do funil: <em>recusou</em> (disse não) e{" "}
          <em>ignorado</em> (você escondeu o lead, mas ele continua no banco,
          recuperável).
        </li>
        <li>
          <strong>Nicho</strong>: no Maps, extraído automaticamente do texto
          da busca. No Instagram, identificado pela IA na classificação (e
          editável depois).
        </li>
        <li>
          <strong>Prioridade</strong>: só existe no Instagram (alta / média /
          baixa / descartado) — indica o quão promissor é aquele perfil.
        </li>
        <li>
          <strong>Lead difícil</strong>: um selo que aparece quando um lead já
          recebeu pelo menos um follow-up e está há mais de 5 dias parado em{" "}
          <em>novo</em> ou <em>contatado</em>. É só um aviso visual — arquivar
          ou não continua sendo sempre sua decisão.
        </li>
      </DocList>

      <DocH2>Onde cada coisa fica</DocH2>
      <DocList>
        <li>
          <strong>Dashboard</strong> (página inicial): métricas combinadas dos
          dois canais, funil e ranking de nichos somados, e atalhos para as
          outras áreas.
        </li>
        <li>
          <strong>Google Maps</strong>: lista/kanban de leads, busca nova,
          follow-up, templates.
        </li>
        <li>
          <strong>Instagram</strong>: análise de posts, leads classificados
          por prioridade, follow-up, posts arquivados.
        </li>
        <li>
          <strong>Configurações</strong>: chaves de API dos provedores de IA.
        </li>
      </DocList>
    </DocSection>
  )
}
