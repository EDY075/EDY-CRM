import {
  DocSection,
  DocH2,
  DocP,
  DocList,
  DocCallout,
} from "@/components/documentacao/DocSection"

export function InstagramDoc() {
  return (
    <DocSection titulo="Instagram">
      <DocP>
        O canal do Instagram analisa os comentários de um post específico,
        pra achar pessoas que demonstraram interesse ou se identificam como
        dono de negócio dentro de um nicho que você escolhe.
      </DocP>

      <DocH2>Como analisar um post</DocH2>
      <DocP>
        Cole a URL de um post (<code>/p/</code>, <code>/reel/</code> ou{" "}
        <code>/tv/</code>) e, opcionalmente, um <strong>nicho-alvo</strong>{" "}
        (ex.: "advogados"). O nicho-alvo direciona a classificação por IA —
        sem ele, a análise é mais genérica.
      </DocP>

      <DocH2>O que acontece por trás (3 etapas)</DocH2>
      <DocList>
        <li>
          <strong>Raspagem</strong>: extrai todos os comentários do post
          (usuário + texto).
        </li>
        <li>
          <strong>Enriquecimento</strong>: consulta cada perfil único —
          público ou privado, bio, seguidores, se é conta comercial.
        </li>
        <li>
          <strong>Classificação por IA</strong>: para cada perfil público,
          avalia bio/seguidores/comentários e retorna prioridade, nicho
          identificado, justificativa e uma sugestão de DM pronta.
        </li>
      </DocList>
      <DocCallout variante="warning">
        Perfis privados são descartados automaticamente antes da
        classificação, sem gastar chamada de IA. A etapa de enriquecimento
        usa a sua conta pessoal do Instagram — use com moderação para reduzir
        risco de bloqueio.
      </DocCallout>

      <DocH2>Prioridade</DocH2>
      <DocP>
        Cada lead recebe uma prioridade: <strong>alta</strong>,{" "}
        <strong>média</strong>, <strong>baixa</strong> ou{" "}
        <strong>descartado</strong>. É reeditável manualmente a qualquer
        momento.
      </DocP>

      <DocH2>Sugestão de DM e follow-up</DocH2>
      <DocP>
        A sugestão de DM vem pronta da classificação, mas pode ser regerada
        (contato ou follow-up), editada manualmente, ou usada como base pra um
        template. O follow-up inteligente funciona igual ao do Google Maps:
        marcar como enviado, sugestão de próxima data, e selo de lead
        difícil.
      </DocP>

      <DocH2>Arquivar e excluir posts</DocH2>
      <DocP>
        Um post analisado pode ser <strong>arquivado</strong> (some da lista
        principal, mas continua recuperável) e depois, na aba "Arquivados",{" "}
        <strong>restaurado</strong> ou <strong>excluído definitivamente</strong>{" "}
        — o que apaga o post e todos os leads dele de vez do banco.
      </DocP>
    </DocSection>
  )
}
