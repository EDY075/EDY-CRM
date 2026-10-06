import { DocSection, DocH2, DocP, DocList, DocCallout } from "@/components/documentacao/DocSection"

export function ConfiguracoesDoc() {
  return (
    <DocSection titulo="Configurações de API">
      <DocP>
        Toda geração de mensagem por IA (copy de contato/follow-up nos dois
        canais, classificação de leads do Instagram) depende de pelo menos um
        provedor de IA configurado.
      </DocP>

      <DocH2>Provedores suportados</DocH2>
      <DocList>
        <li>
          <strong>Google Gemini</strong> (<code>gemini-flash-latest</code>)
        </li>
        <li>
          <strong>Groq</strong> (<code>llama-3.3-70b-versatile</code>)
        </li>
        <li>
          <strong>NVIDIA Build</strong> (<code>nemotron-super-49b</code>)
        </li>
      </DocList>
      <DocP>
        Todos têm camada gratuita. Configurar mais de um aumenta a
        confiabilidade — se um estiver sem cota, o sistema tenta o próximo
        automaticamente.
      </DocP>

      <DocH2>Como funciona o fallback</DocH2>
      <DocList>
        <li>Tenta os provedores na ordem: Gemini → Groq → NVIDIA.</li>
        <li>Pula silenciosamente qualquer provedor sem chave configurada.</li>
        <li>
          Se um provedor bateu cota recentemente, fica em "cooldown" por 5
          minutos antes de tentar de novo.
        </li>
        <li>
          Se todos falharem, mostra um erro traduzido pra linguagem simples
          (sem jargão técnico).
        </li>
      </DocList>

      <DocCallout>
        As chaves configuradas pela tela têm prioridade sobre o arquivo{" "}
        <code>.env</code> — mas quem só usa o <code>.env</code> continua
        funcionando normalmente, sem precisar mexer na tela.
      </DocCallout>
    </DocSection>
  )
}
